import uuid
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.scheduling as scheduling
from app.domain.errors import DomainError
from app.domain.scheduling import SchedulePolicy
from app.schemas.public import HoldCreate
from app.services.smart_scheduling import TeamCandidate


def _configuration() -> SimpleNamespace:
    business_id = uuid.uuid4()
    return SimpleNamespace(
        business=SimpleNamespace(id=business_id),
        settings=SimpleNamespace(
            business_id=business_id,
            timezone="Asia/Dubai",
            opening_time=time(9),
            closing_time=time(21),
            slot_duration_minutes=120,
            multi_vehicle_threshold=3,
            multi_vehicle_required_slots=2,
            hold_duration_minutes=10,
            default_team_turnaround_minutes=60,
        ),
    )


def _policy() -> SchedulePolicy:
    return SchedulePolicy(
        timezone="Asia/Dubai",
        opening_time=time(9),
        closing_time=time(21),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        hold_duration_minutes=10,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("service_name", ["Interior Deep Cleaning", "Exterior Polishing"])
async def test_big_service_availability_exposes_only_nine_am(
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
) -> None:
    configuration = _configuration()
    team = TeamCandidate(
        id=uuid.uuid4(),
        name="Team A",
        sort_order=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = AsyncMock()
    rows = MagicMock()
    rows.all.return_value = []
    session.scalars.return_value = rows
    monkeypatch.setattr(scheduling, "load_default_business", AsyncMock(return_value=configuration))
    monkeypatch.setattr(scheduling, "policy_for_day", AsyncMock(return_value=_policy()))
    monkeypatch.setattr(
        scheduling,
        "_selected_service_names",
        AsyncMock(return_value=[service_name]),
    )
    monkeypatch.setattr(
        scheduling,
        "current_selection_duration_minutes",
        AsyncMock(return_value=240),
    )
    monkeypatch.setattr(scheduling, "get_eligible_teams", AsyncMock(return_value=[team]))
    monkeypatch.setattr(scheduling, "load_capacity_items", AsyncMock(return_value=[]))

    response = await scheduling.availability_for_date(
        session,
        day=date(2035, 1, 2),
        vehicle_count=3,
        service_ids=[uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
    )

    assert response.required_start_time == time(9)
    assert response.required_slot_count == 2
    assert [slot.time for slot in response.slots] == [time(9)]
    assert response.slots[0].available is True


@pytest.mark.asyncio
async def test_normal_service_availability_includes_nine_pm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configuration()
    team = TeamCandidate(
        id=uuid.uuid4(),
        name="Team A",
        sort_order=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = AsyncMock()
    rows = MagicMock()
    rows.all.return_value = []
    session.scalars.return_value = rows
    monkeypatch.setattr(scheduling, "load_default_business", AsyncMock(return_value=configuration))
    monkeypatch.setattr(scheduling, "policy_for_day", AsyncMock(return_value=_policy()))
    monkeypatch.setattr(
        scheduling,
        "_selected_service_names",
        AsyncMock(return_value=["Standard Wash"]),
    )
    monkeypatch.setattr(
        scheduling,
        "current_selection_duration_minutes",
        AsyncMock(return_value=120),
    )
    monkeypatch.setattr(scheduling, "get_eligible_teams", AsyncMock(return_value=[team]))
    monkeypatch.setattr(scheduling, "load_capacity_items", AsyncMock(return_value=[]))

    response = await scheduling.availability_for_date(
        session,
        day=date(2035, 1, 2),
        vehicle_count=1,
        service_ids=[uuid.uuid4()],
    )

    assert response.required_start_time is None
    assert response.slots[-1].time == time(21)
    assert response.slots[-1].available is True


@pytest.mark.asyncio
async def test_hold_rejects_late_big_service_before_capacity_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configuration()
    monkeypatch.setattr(scheduling, "load_default_business", AsyncMock(return_value=configuration))
    monkeypatch.setattr(scheduling, "policy_for_day", AsyncMock(return_value=_policy()))
    monkeypatch.setattr(
        scheduling,
        "_selected_service_names",
        AsyncMock(return_value=["Interior Deep Cleaning"]),
    )
    session = AsyncMock()

    with pytest.raises(DomainError) as error:
        await scheduling.create_hold(
            session,
            HoldCreate(
                date=date(2035, 1, 2),
                start_time=time(14),
                vehicle_count=1,
                service_ids=[uuid.uuid4()],
            ),
        )

    assert error.value.code == "SERVICE_START_TIME_RESTRICTED"
    session.flush.assert_not_awaited()
