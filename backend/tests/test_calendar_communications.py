import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.dependencies import StaffContext
from app.domain.enums import BookingStatus, JobStatus, OutboxStatus, StaffRole
from app.domain.errors import DomainError
from app.models.entities import NotificationOutbox
from app.services.customer_communications import discard_unsent_appointment_reminders
from app.services.staff_operations import list_job_calendar
from app.workers.notifications import StaleNotification, delivery_payload


def context(role: StaffRole = StaffRole.MANAGER) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=role,
        timezone="Asia/Dubai",
    )


@pytest.mark.asyncio
async def test_calendar_uses_one_bounded_projection_and_business_date() -> None:
    ctx = context()
    job_id = uuid.uuid4()
    scheduled = datetime(2026, 8, 30, 21, 30, tzinfo=UTC)
    mappings = MagicMock()
    mappings.all.return_value = [
        {
            "job_id": job_id,
            "scheduled_start": scheduled,
            "scheduled_end": scheduled + timedelta(hours=2),
            "status": JobStatus.ASSIGNED,
            "team_id": None,
            "team_short_name": None,
            "vehicle_label": "Toyota Camry",
            "service_label": "Standard Wash",
        }
    ]
    result = MagicMock()
    result.mappings.return_value = mappings
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    calendar = await list_job_calendar(
        session,
        ctx,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )

    assert session.execute.await_count == 1
    assert calendar.jobs[0].job_id == job_id
    assert calendar.jobs[0].local_date == date(2026, 8, 31)
    assert calendar.jobs[0].team_short_name is None


@pytest.mark.asyncio
async def test_calendar_rejects_unbounded_ranges() -> None:
    with pytest.raises(DomainError, match="Calendar requests"):
        await list_job_calendar(
            MagicMock(),
            context(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_reschedule_discards_only_unsent_current_reminder() -> None:
    record = NotificationOutbox(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        channel="email",
        notification_type="appointment_reminder",
        recipient="customer@example.com",
        payload={},
        status=OutboxStatus.PENDING,
        next_attempt_at=datetime.now(UTC),
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[record, None])
    session.delete = AsyncMock()

    await discard_unsent_appointment_reminders(session, record.booking_id)

    session.delete.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_stale_reminder_is_not_rendered_or_sent() -> None:
    booking_id = uuid.uuid4()
    record = NotificationOutbox(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        booking_id=booking_id,
        channel="email",
        notification_type="appointment_reminder",
        recipient="customer@example.com",
        payload={
            "booking_reference": "TF-1",
            "scheduled_start": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        },
        status=OutboxStatus.PROCESSING,
        next_attempt_at=datetime.now(UTC),
    )
    booking = SimpleNamespace(
        id=booking_id,
        business_id=record.business_id,
        status=BookingStatus.CANCELLED,
        scheduled_start=datetime(2026, 9, 1, tzinfo=UTC),
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=booking)

    with pytest.raises(StaleNotification):
        await delivery_payload(
            session, record, public_web_url="https://trifecta.example"
        )
