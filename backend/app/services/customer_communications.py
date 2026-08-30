import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutboxStatus
from app.models.entities import NotificationOutbox


async def discard_unsent_appointment_reminders(
    session: AsyncSession, booking_id: uuid.UUID
) -> None:
    """Remove reminder work that no longer represents the authoritative booking."""

    while True:
        record = await session.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.booking_id == booking_id,
                NotificationOutbox.notification_type == "appointment_reminder",
                NotificationOutbox.status.in_(
                    [OutboxStatus.PENDING, OutboxStatus.RETRY, OutboxStatus.PROCESSING]
                ),
            )
            .order_by(NotificationOutbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if record is None:
            return
        await session.delete(record)
        # Request sessions intentionally disable autoflush. Flush now so the deleted
        # reminders cannot be selected repeatedly by later work in this transaction.
        await session.flush()
