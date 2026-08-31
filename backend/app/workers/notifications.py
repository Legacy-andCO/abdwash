import asyncio
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.domain.enums import OutboxStatus
from app.domain.timezones import TRIFECTA_TIMEZONE
from app.integrations.notifications.base import NotificationProvider
from app.integrations.notifications.factory import create_notification_provider
from app.integrations.notifications.resend import ResendDeliveryError
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    Job,
    NotificationOutbox,
    Payment,
    PaymentTransaction,
    RevenueInvoice,
)
from app.services.management_tokens import create_management_token

logger = structlog.get_logger()


class StaleNotification(RuntimeError):
    """The queued message no longer represents authoritative booking state."""


async def enqueue_due_appointment_reminders(
    factory: async_sessionmaker[AsyncSession], *, batch_size: int
) -> int:
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        rows = (
            await session.execute(
                select(
                    Booking.id,
                    Booking.business_id,
                    Booking.reference,
                    Booking.customer_email,
                    Booking.scheduled_start,
                )
                .join(
                    BusinessSettings,
                    BusinessSettings.business_id == Booking.business_id,
                )
                .where(
                    BusinessSettings.appointment_reminder_enabled.is_(True),
                    Booking.status == "confirmed",
                    Booking.customer_email.is_not(None),
                    Booking.customer_email != "",
                    Booking.scheduled_start > now,
                    Booking.scheduled_start
                    <= now
                    + func.make_interval(
                        0,
                        0,
                        0,
                        0,
                        BusinessSettings.appointment_reminder_hours_before,
                    ),
                )
                .order_by(Booking.scheduled_start)
                .limit(batch_size)
                .with_for_update(of=Booking, skip_locked=True)
            )
        ).all()
        if not rows:
            return 0
        values = [
            {
                "id": uuid.uuid4(),
                "business_id": business_id,
                "booking_id": booking_id,
                "channel": "email",
                "notification_type": "appointment_reminder",
                "dedupe_key": (
                    f"appointment-reminder:{booking_id}:{int(scheduled_start.timestamp())}"
                ),
                "recipient": customer_email,
                "payload": {
                    "booking_reference": reference,
                    "scheduled_start": scheduled_start.isoformat(),
                },
                "status": OutboxStatus.PENDING,
                "attempt_count": 0,
                "next_attempt_at": now,
            }
            for booking_id, business_id, reference, customer_email, scheduled_start in rows
        ]
        result = await session.execute(
            insert(NotificationOutbox)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    NotificationOutbox.business_id,
                    NotificationOutbox.dedupe_key,
                ],
                index_where=NotificationOutbox.dedupe_key.is_not(None),
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)


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
        claimed: list[uuid.UUID] = []
        for record in records:
            if _stored_permanent_resend_failure(record.last_error):
                record.status = OutboxStatus.FAILED
                record.locked_at = None
                record.locked_by = None
                continue
            record.status = OutboxStatus.PROCESSING
            record.locked_at = now
            record.locked_by = worker_id
            claimed.append(record.id)
        return claimed


def _stored_permanent_resend_failure(last_error: str | None) -> bool:
    if not last_error or "ResendDeliveryError: Resend " not in last_error:
        return False
    return any(f"Resend {status}:" in last_error for status in (400, 401, 403))


async def process_record(
    factory: async_sessionmaker[AsyncSession],
    provider: NotificationProvider,
    record_id: uuid.UUID,
    *,
    worker_id: str,
    public_web_url: str | None,
) -> Literal["sent", "retry", "failed", "skipped"]:
    try:
        async with factory() as session:
            record = await session.get(NotificationOutbox, record_id)
            if (
                record is None
                or record.status != OutboxStatus.PROCESSING
                or record.locked_by != worker_id
            ):
                return "skipped"
            if not record.recipient.strip():
                raise StaleNotification("Notification has no deliverable recipient")
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
        if notification[2] == "appointment_reminder":
            await ensure_reminder_current(
                factory,
                record_id,
                worker_id=worker_id,
            )
        await provider.send(
            channel=notification[0],
            recipient=notification[1],
            notification_type=notification[2],
            payload=notification[3],
            idempotency_key=f"notification-{record_id}",
        )
    except StaleNotification:
        async with factory() as session, session.begin():
            record = await session.get(NotificationOutbox, record_id, with_for_update=True)
            if record is not None and record.locked_by == worker_id:
                await session.delete(record)
        logger.info("notification_stale_skipped", notification_id=str(record_id))
        return "skipped"
    except Exception as exc:  # provider boundary intentionally catches and retries
        notification_type: str | None = None
        attempt_count: int | None = None
        final_status: str | None = None
        async with factory() as session, session.begin():
            record = await session.get(NotificationOutbox, record_id, with_for_update=True)
            if record is not None and record.locked_by == worker_id:
                notification_type = record.notification_type
                mark_delivery_failed(record, exc, now=datetime.now(UTC))
                attempt_count = record.attempt_count
                final_status = record.status
        diagnostic = {
            "notification_id": str(record_id),
            "notification_type": notification_type,
            "attempt_count": attempt_count,
        }
        if isinstance(exc, ResendDeliveryError):
            diagnostic.update(
                {
                    "provider": "resend",
                    "provider_http_status": exc.status_code,
                    "provider_error_code": exc.provider_code,
                    "provider_error": exc.safe_message,
                }
            )
        if final_status == OutboxStatus.FAILED:
            logger.warning("notification_failed", **diagnostic)
            return "failed"
        logger.warning("notification_retry", **diagnostic)
        return "retry"
    async with factory() as session, session.begin():
        record = await session.get(NotificationOutbox, record_id, with_for_update=True)
        if record is not None and record.locked_by == worker_id:
            mark_delivery_succeeded(record, now=datetime.now(UTC))
    return "sent"


async def ensure_reminder_current(
    factory: async_sessionmaker[AsyncSession],
    record_id: uuid.UUID,
    *,
    worker_id: str,
) -> None:
    """Recheck reminder authority immediately before the provider boundary."""

    async with factory() as session:
        record = await session.get(NotificationOutbox, record_id)
        if (
            record is None
            or record.status != OutboxStatus.PROCESSING
            or record.locked_by != worker_id
        ):
            raise StaleNotification("Appointment reminder was withdrawn")
        if record.notification_type != "appointment_reminder":
            return
        booking = await session.get(Booking, record.booking_id)
        queued_start = datetime.fromisoformat(str(record.payload.get("scheduled_start")))
        if (
            booking is None
            or booking.status != "confirmed"
            or booking.scheduled_start != queued_start
            or booking.scheduled_start <= datetime.now(UTC)
        ):
            raise StaleNotification("Appointment reminder is no longer current")


async def delivery_payload(
    session: AsyncSession,
    record: NotificationOutbox,
    *,
    public_web_url: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = dict(record.payload)
    if record.notification_type not in {
        "booking_confirmed",
        "driver_en_route",
        "booking_rescheduled",
        "job_completed",
        "appointment_reminder",
        "team_arrived",
        "team_delayed",
        "payment_pending",
        "payment_received",
        "booking_cancelled",
    }:
        return payload
    if record.booking_id is None or not public_web_url:
        raise RuntimeError("Booking email delivery configuration is incomplete")
    booking = await session.get(Booking, record.booking_id)
    if booking is None:
        raise RuntimeError("Booking notification has no booking")
    if record.notification_type == "appointment_reminder":
        queued_start = datetime.fromisoformat(str(payload.get("scheduled_start")))
        if (
            booking.status != "confirmed"
            or booking.scheduled_start != queued_start
            or booking.scheduled_start <= datetime.now(UTC)
        ):
            raise StaleNotification("Appointment reminder is no longer current")
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
            "timezone": TRIFECTA_TIMEZONE,
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
    if record.notification_type == "payment_received":
        invoice_id = uuid.UUID(str(payload.get("invoice_id")))
        invoice = await session.scalar(
            select(RevenueInvoice).where(
                RevenueInvoice.id == invoice_id,
                RevenueInvoice.booking_id == booking.id,
            )
        )
        if invoice is None:
            raise RuntimeError("Payment notification has no invoice")
        payload.update(
            {
                "invoice_number": invoice.invoice_number,
                "invoice_document_type": invoice.document_type,
                "payment_method": invoice.payment_method,
                "amount_paid_minor": invoice.total_minor,
                "invoice_url": (
                    f"{public_web_url.rstrip('/')}/invoice?invoice={invoice.id}#{token}"
                ),
            }
        )
    if record.notification_type == "job_completed":
        job_payment = (
            await session.execute(
                select(Job, Payment)
                .join(Payment, Payment.booking_id == Job.booking_id)
                .where(Job.booking_id == booking.id)
            )
        ).one()
        job, payment = job_payment
        settled_transactions = int(
            await session.scalar(
                select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(
                    PaymentTransaction.payment_id == payment.id,
                    PaymentTransaction.status == "succeeded",
                )
            )
            or 0
        )
        amount_paid_minor = 0
        if payment.status == "paid":
            amount_paid_minor = (
                settled_transactions if settled_transactions > 0 else payment.amount_minor
            )
        duration_seconds = None
        if job.started_at is not None and job.completed_at is not None:
            duration_seconds = max(
                0,
                int((job.completed_at - job.started_at).total_seconds()),
            )
        payload.update(
            {
                "actual_service_duration_seconds": duration_seconds,
                "amount_paid_minor": amount_paid_minor,
                "payment_status": payment.status,
                "payment_method": payment.method,
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
    if isinstance(exc, ResendDeliveryError) and not exc.retryable:
        record.status = OutboxStatus.FAILED
        # The column is intentionally non-null in the existing schema. Failed rows
        # are excluded from claims by status, so no future retry is scheduled.
        record.next_attempt_at = now
        return
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
    try:
        scheduled = await enqueue_due_appointment_reminders(factory, batch_size=batch_size)
    except Exception:
        # Reminder materialization must not block delivery of already-durable outbox work.
        logger.exception("appointment_reminder_enqueue_failed")
        scheduled = 0
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
        "scheduled": scheduled,
        "claimed": len(record_ids),
        "sent": results.count("sent"),
        "retry": results.count("retry"),
        "failed": results.count("failed"),
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
