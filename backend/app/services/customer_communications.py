import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutboxStatus
from app.models.entities import NotificationOutbox


def queue_customer_email_if_available(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    booking_id: uuid.UUID,
    notification_type: str,
    dedupe_key: str,
    recipient: str | None,
    payload: dict[str, object],
    next_attempt_at: datetime,
) -> NotificationOutbox | None:
    """Queue customer email only when the booking captured a usable recipient."""

    normalized_recipient = recipient.strip() if recipient else ""
    if not normalized_recipient:
        return None
    record = NotificationOutbox(
        business_id=business_id,
        booking_id=booking_id,
        channel="email",
        notification_type=notification_type,
        dedupe_key=dedupe_key,
        recipient=normalized_recipient,
        payload=payload,
        status=OutboxStatus.PENDING,
        next_attempt_at=next_attempt_at,
    )
    session.add(record)
    return record


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
