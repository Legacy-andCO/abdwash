import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.staff_operations import _serialize_jobs


class _Rows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


def _staff_row(email: str, *, customer_profile_id: uuid.UUID | None = None) -> tuple:
    now = datetime(2026, 8, 27, 9, tzinfo=UTC)
    booking_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        assigned_staff_id=None,
        assigned_resource_id=None,
        status="assigned",
        scheduled_start=now,
        scheduled_end=now,
        en_route_at=None,
        estimated_arrival_at=None,
        arrived_at=None,
        started_at=None,
        completed_at=None,
    )
    booking = SimpleNamespace(
        id=booking_id,
        reference=f"AW-{str(booking_id)[:8]}",
        customer_profile_id=customer_profile_id,
        customer_first_name="Ahmed",
        customer_surname="Mohammed",
        customer_phone="+971505555555",
        customer_email=email,
        written_address="Abu Dhabi",
        location_url="https://www.google.com/maps/search/?api=1&query=24.4,54.4",
        latitude=None,
        longitude=None,
        location_instructions=None,
        total_amount_minor=10000,
        currency_code="AED",
    )
    payment = SimpleNamespace(status="pending", method="pay_after_service")
    return job, booking, payment, None


@pytest.mark.asyncio
async def test_staff_job_list_uses_booking_email_snapshot_for_guest_and_customer() -> None:
    session = SimpleNamespace(execute=AsyncMock(return_value=_Rows([])))
    rows = [
        _staff_row("guest@example.com"),
        _staff_row("customer@example.com", customer_profile_id=uuid.uuid4()),
    ]

    jobs = await _serialize_jobs(session, rows)

    assert [job.customer_email for job in jobs] == [
        "guest@example.com",
        "customer@example.com",
    ]
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_staff_job_detail_keeps_historical_booking_email() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Rows([]), _Rows([])])
    )
    row = _staff_row("booked-address@example.com", customer_profile_id=uuid.uuid4())

    job = (await _serialize_jobs(session, [row], include_timeline=True))[0]

    assert job.customer_email == "booked-address@example.com"
    assert session.execute.await_count == 2
