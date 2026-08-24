import asyncio
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.domain.enums import OutboxStatus
from app.integrations.notifications.base import NotificationProvider
from app.integrations.notifications.factory import create_notification_provider
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    NotificationOutbox,
)
from app.services.management_tokens import create_management_token

logger = structlog.get_logger()


async def claim_batch(
    factory: async_sessionmaker[AsyncSession], *, worker_id: str, batch_size: int
) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    stale = now - timedelta(minutes=5)
    async with factory() as session, session.begin():
        records = list(
            (
                await session.scalars(
                    select(NotificationOutbox)
                    .where(
                        or_(
                            NotificationOutbox.status.in_(
                                [OutboxStatus.PENDING, OutboxStatus.RETRY]
                            ),
                            (
                                (NotificationOutbox.status == OutboxStatus.PROCESSING)
                                & (NotificationOutbox.locked_at < stale)
                            ),
                        ),
                        NotificationOutbox.next_attempt_at <= now,
                    )
                    .order_by(NotificationOutbox.next_attempt_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for record in records:
            record.status = OutboxStatus.PROCESSING
            record.locked_at = now
            record.locked_by = worker_id
        return [record.id for record in records]


async def process_record(
    factory: async_sessionmaker[AsyncSession],
    provider: NotificationProvider,
    record_id: uuid.UUID,
    *,
    worker_id: str,
    public_web_url: str | None,
) -> Literal["sent", "retry", "skipped"]:
    try:
        async with factory() as session:
            record = await session.get(NotificationOutbox, record_id)
            if (
                record is None
                or record.status != OutboxStatus.PROCESSING
                or record.locked_by != worker_id
            ):
                return "skipped"
            payload = await delivery_payload(
                session,
                record,
                public_web_url=public_web_url,
            )
            notification = (
                record.channel,
                record.recipient,
                record.notification_type,
                payload,
            )
            await session.rollback()
        await provider.send(
            channel=notification[0],
            recipient=notification[1],
            notification_type=notification[2],
            payload=notification[3],
            idempotency_key=f"notification-{record_id}",
        )
    except Exception as exc:  # provider boundary intentionally catches and retries
        async with factory() as session, session.begin():
            record = await session.get(NotificationOutbox, record_id, with_for_update=True)
            if record is not None and record.locked_by == worker_id:
                mark_delivery_failed(record, exc, now=datetime.now(UTC))
        logger.warning("notification_retry", notification_id=str(record_id))
        return "retry"
    async with factory() as session, session.begin():
        record = await session.get(NotificationOutbox, record_id, with_for_update=True)
        if record is not None and record.locked_by == worker_id:
            mark_delivery_succeeded(record, now=datetime.now(UTC))
    return "sent"


async def delivery_payload(
    session: AsyncSession,
    record: NotificationOutbox,
    *,
    public_web_url: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = dict(record.payload)
    if record.notification_type not in {"booking_confirmed", "driver_en_route"}:
        return payload
    if record.booking_id is None or not public_web_url:
        raise RuntimeError("Booking email delivery configuration is incomplete")
    booking = await session.get(Booking, record.booking_id)
    if booking is None:
        raise RuntimeError("Booking notification has no booking")
    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == booking.business_id)
        )
    ).one()
    vehicles = (
        await session.execute(
            select(BookingVehicle.make, BookingVehicle.model, BookingService.service_name)
            .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
            .where(BookingVehicle.booking_id == booking.id)
            .order_by(BookingVehicle.position)
        )
    ).all()
    token = create_management_token(booking.id)
    payload.update(
        {
            "customer_first_name": booking.customer_first_name,
            "scheduled_start": booking.scheduled_start.isoformat(),
            "scheduled_end": booking.scheduled_end.isoformat(),
            "timezone": settings.timezone,
            "vehicle_count": booking.vehicle_count,
            "vehicles": [
                {"make": make, "model": model, "service_name": service_name}
                for make, model, service_name in vehicles
            ],
            "written_address": booking.written_address,
            "total_amount_minor": booking.total_amount_minor,
            "currency_code": booking.currency_code,
            "payment_choice": booking.payment_choice,
            "payment_status": booking.payment_status,
            "management_url": f"{public_web_url.rstrip('/')}/manage#{token}",
            "cancellation_cutoff_hours": settings.cancellation_cutoff_hours,
        }
    )
    return payload


def mark_delivery_succeeded(record: NotificationOutbox, *, now: datetime) -> None:
    record.status = OutboxStatus.SENT
    record.sent_at = now
    record.locked_at = None
    record.locked_by = None
    record.last_error = None


def mark_delivery_failed(record: NotificationOutbox, exc: Exception, *, now: datetime) -> None:
    record.attempt_count += 1
    record.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
    record.locked_at = None
    record.locked_by = None
    if record.attempt_count >= 8:
        record.status = OutboxStatus.FAILED
        return
    record.status = OutboxStatus.RETRY
    delay = min(3600, 30 * (2 ** (record.attempt_count - 1)))
    record.next_attempt_at = now + timedelta(seconds=delay)


async def dispatch_once(
    factory: async_sessionmaker[AsyncSession],
    provider: NotificationProvider,
    *,
    worker_id: str,
    batch_size: int,
    public_web_url: str | None,
) -> dict[str, int]:
    record_ids = await claim_batch(factory, worker_id=worker_id, batch_size=batch_size)
    results = await asyncio.gather(
        *(
            process_record(
                factory,
                provider,
                record_id,
                worker_id=worker_id,
                public_web_url=public_web_url,
            )
            for record_id in record_ids
        )
    )
    return {
        "claimed": len(record_ids),
        "sent": results.count("sent"),
        "retry": results.count("retry"),
        "skipped": results.count("skipped"),
    }


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(15))
    provider = create_notification_provider(settings, http_client)
    worker_id = f"{socket.gethostname()}-{uuid.uuid4()}"
    logger.info("notification_worker_started", worker_id=worker_id)
    try:
        while True:
            result = await dispatch_once(
                factory,
                provider,
                worker_id=worker_id,
                batch_size=settings.outbox_batch_size,
                public_web_url=settings.public_web_url,
            )
            if not result["claimed"]:
                await asyncio.sleep(settings.outbox_poll_seconds)
    finally:
        await http_client.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
