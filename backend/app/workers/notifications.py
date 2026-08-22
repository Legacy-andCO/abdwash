import asyncio
import socket
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.domain.enums import OutboxStatus
from app.integrations.notifications.log import LogNotificationProvider
from app.models.entities import NotificationOutbox

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
    provider: LogNotificationProvider,
    record_id: uuid.UUID,
) -> None:
    async with factory() as session:
        record = await session.get(NotificationOutbox, record_id)
        if record is None or record.status != OutboxStatus.PROCESSING:
            return
        notification = (record.channel, record.recipient, record.notification_type, record.payload)
        await session.rollback()
    try:
        await provider.send(
            channel=notification[0],
            recipient=notification[1],
            notification_type=notification[2],
            payload=notification[3],
        )
    except Exception as exc:  # provider boundary intentionally catches and retries
        async with factory() as session, session.begin():
            record = await session.get(NotificationOutbox, record_id, with_for_update=True)
            if record is not None:
                record.attempt_count += 1
                record.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                record.locked_at = None
                record.locked_by = None
                if record.attempt_count >= 8:
                    record.status = OutboxStatus.FAILED
                else:
                    record.status = OutboxStatus.RETRY
                    delay = min(3600, 30 * (2 ** (record.attempt_count - 1)))
                    record.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        logger.warning("notification_retry", notification_id=str(record_id))
        return
    async with factory() as session, session.begin():
        record = await session.get(NotificationOutbox, record_id, with_for_update=True)
        if record is not None:
            record.status = OutboxStatus.SENT
            record.sent_at = datetime.now(UTC)
            record.locked_at = None
            record.locked_by = None
            record.last_error = None


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    provider = LogNotificationProvider()
    worker_id = f"{socket.gethostname()}-{uuid.uuid4()}"
    logger.info("notification_worker_started", worker_id=worker_id)
    try:
        while True:
            record_ids = await claim_batch(
                factory, worker_id=worker_id, batch_size=settings.outbox_batch_size
            )
            if not record_ids:
                await asyncio.sleep(settings.outbox_poll_seconds)
                continue
            for record_id in record_ids:
                await process_record(factory, provider, record_id)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
