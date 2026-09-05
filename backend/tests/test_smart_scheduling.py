import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import app.services.smart_scheduling as smart_scheduling
from app.domain.errors import ConflictError
from app.schemas.public import AvailabilitySlot, BookingResponse, HoldCreate, HoldResponse
from app.schemas.staff import AssignmentAction
from app.services.smart_scheduling import (
    AssignmentDecision,
    CapacityItem,
    TeamCandidate,
    TeamEvaluation,
    booking_snapshot_duration_minutes,
    choose_team_for_booking,
    current_selection_duration_minutes,
    evaluate_team,
    operational_duration_minutes,
    rank_evaluations,
)

START = datetime(2035, 1, 2, 12, tzinfo=UTC)


def team(name: str, order: int = 0, identifier: int = 1) -> TeamCandidate:
    return TeamCandidate(
        id=uuid.UUID(int=identifier),
        name=name,
        sort_order=order,
        created_at=datetime(2026, 1, identifier, tzinfo=UTC),
    )


def item(
    candidate: TeamCandidate,
    start: datetime,
    end: datetime,
    *,
    source: str = "job",
    identifier: int = 100,
) -> CapacityItem:
    return CapacityItem(
        resource_id=candidate.id,
        starts_at=start,
        ends_at=end,
        source=source,  # type: ignore[arg-type]
        source_id=uuid.UUID(int=identifier),
    )


def test_operational_duration_sums_vehicle_and_addon_snapshots_with_slot_floor() -> None:
    assert operational_duration_minutes([60, 90], [30], reserved_slot_floor_minutes=120) == 180
    assert operational_duration_minutes([60], [], reserved_slot_floor_minutes=120) == 120


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class _SelectionSession:
    def __init__(self, result_sets: list[list[object]]) -> None:
        self.result_sets = iter(result_sets)

    async def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(next(self.result_sets))


@pytest.mark.asyncio
async def test_current_catalogue_duration_counts_each_vehicle_and_addon_selection() -> None:
    service_id = uuid.uuid4()
    addon_id = uuid.uuid4()
    session = _SelectionSession(
        [
            [SimpleNamespace(id=service_id, estimated_duration_minutes=60)],
            [SimpleNamespace(id=addon_id, default_duration_minutes=20)],
        ]
    )
    duration = await current_selection_duration_minutes(
        session,  # type: ignore[arg-type]
        business_id=uuid.uuid4(),
        service_ids=[service_id, service_id],
        addon_ids=[addon_id, addon_id],
        vehicle_count=2,
        reserved_slot_floor_minutes=120,
    )
    assert duration == 160


@pytest.mark.asyncio
async def test_existing_booking_duration_uses_immutable_snapshots() -> None:
    session = _SelectionSession([[75, 45], [30]])
    duration = await booking_snapshot_duration_minutes(
        session,  # type: ignore[arg-type]
        booking_id=uuid.uuid4(),
        reserved_slot_floor_minutes=120,
    )
    assert duration == 150


def test_actual_overlap_is_a_hard_conflict() -> None:
    candidate = team("A")
    result = evaluate_team(
        candidate,
        [item(candidate, START, START + timedelta(hours=2))],
        starts_at=START + timedelta(hours=1),
        ends_at=START + timedelta(hours=3),
        turnaround_minutes=60,
    )
    assert result.status == "time_conflict"


@pytest.mark.parametrize(
    ("existing_start", "existing_end", "new_start", "new_end"),
    [
        (
            START - timedelta(hours=3),
            START - timedelta(minutes=30),
            START,
            START + timedelta(hours=1),
        ),
        (
            START + timedelta(hours=2),
            START + timedelta(hours=3),
            START,
            START + timedelta(minutes=90),
        ),
    ],
)
def test_previous_and_next_turnaround_are_enforced(
    existing_start: datetime,
    existing_end: datetime,
    new_start: datetime,
    new_end: datetime,
) -> None:
    candidate = team("A")
    result = evaluate_team(
        candidate,
        [item(candidate, existing_start, existing_end)],
        starts_at=new_start,
        ends_at=new_end,
        turnaround_minutes=60,
    )
    assert result.status == "turnaround_conflict"


def test_exact_turnaround_boundary_is_available() -> None:
    candidate = team("A")
    result = evaluate_team(
        candidate,
        [item(candidate, START - timedelta(hours=2), START - timedelta(hours=1))],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    assert result.status == "available"


def test_active_hold_consumes_capacity_but_expired_holds_are_not_input() -> None:
    candidate = team("A")
    result = evaluate_team(
        candidate,
        [item(candidate, START, START + timedelta(hours=2), source="hold")],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    assert result.status == "time_conflict"


def test_big_service_duration_does_not_block_later_same_day_capacity() -> None:
    candidate = team("A")
    big_service = item(
        candidate,
        START,
        START + timedelta(hours=4),
    )
    result = evaluate_team(
        candidate,
        [big_service],
        starts_at=START + timedelta(hours=6),
        ends_at=START + timedelta(hours=8),
        turnaround_minutes=60,
    )
    assert result.status == "available"


def test_ranking_prefers_zero_jobs_then_minutes_then_deterministic_order() -> None:
    busy = team("Busy", identifier=2)
    free = team("Free", identifier=3)
    busy_result = evaluate_team(
        busy,
        [item(busy, START - timedelta(hours=4), START - timedelta(hours=3))],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    free_result = evaluate_team(
        free,
        [],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    assert rank_evaluations([busy_result, free_result])[0].team == free

    short = team("Short", identifier=4)
    long = team("Long", identifier=5)
    short_result = evaluate_team(
        short,
        [item(short, START - timedelta(hours=5), START - timedelta(hours=4))],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    long_result = evaluate_team(
        long,
        [item(long, START - timedelta(hours=6), START - timedelta(hours=4))],
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    assert rank_evaluations([long_result, short_result])[0].team == short


def test_ranking_uses_job_count_margin_and_stable_team_order() -> None:
    first = team("First", order=1, identifier=10)
    second = team("Second", order=2, identifier=11)
    fewer_jobs = TeamEvaluation(first, "available", None, 1, 240, 60)
    more_jobs = TeamEvaluation(second, "available", None, 2, 60, 600)
    assert rank_evaluations([more_jobs, fewer_jobs])[0] == fewer_jobs

    wider_margin = TeamEvaluation(second, "available", None, 1, 240, 180)
    assert rank_evaluations([fewer_jobs, wider_margin])[0] == wider_margin

    tied_first = TeamEvaluation(first, "available", None, 1, 240, 180)
    assert rank_evaluations([wider_margin, tied_first])[0] == tied_first


@pytest.mark.asyncio
async def test_auto_assignment_and_manual_turnaround_override_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = TeamEvaluation(team("Available", identifier=20), "available", None, 0, 0, 1440)
    soft = TeamEvaluation(
        team("Short gap", identifier=21),
        "turnaround_conflict",
        "Short turnaround",
        1,
        120,
        30,
    )

    async def evaluations(*_args: object, **_kwargs: object) -> list[TeamEvaluation]:
        return [soft, available]

    monkeypatch.setattr(smart_scheduling, "evaluate_teams_for_interval", evaluations)
    automatic = await choose_team_for_booking(
        None,  # type: ignore[arg-type]
        business_id=uuid.uuid4(),
        day=START.date(),
        timezone="Asia/Dubai",
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
    )
    assert isinstance(automatic, AssignmentDecision)
    assert automatic.team == available.team
    assert automatic.assignment_source == "auto"

    with pytest.raises(ConflictError) as error:
        await choose_team_for_booking(
            None,  # type: ignore[arg-type]
            business_id=uuid.uuid4(),
            day=START.date(),
            timezone="Asia/Dubai",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            turnaround_minutes=60,
            source="manual",
            preferred_team_id=soft.team.id,
        )
    assert error.value.code == "TEAM_TURNAROUND_CONFLICT"

    overridden = await choose_team_for_booking(
        None,  # type: ignore[arg-type]
        business_id=uuid.uuid4(),
        day=START.date(),
        timezone="Asia/Dubai",
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        turnaround_minutes=60,
        source="manual",
        preferred_team_id=soft.team.id,
        override_turnaround=True,
    )
    assert overridden.team == soft.team
    assert overridden.assignment_source == "manual"


@pytest.mark.asyncio
async def test_manual_overlap_cannot_be_overridden_and_no_capacity_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hard = TeamEvaluation(
        team("Busy", identifier=22), "time_conflict", "Conflicting job", 1, 120, 0
    )

    async def hard_evaluations(*_args: object, **_kwargs: object) -> list[TeamEvaluation]:
        return [hard]

    monkeypatch.setattr(smart_scheduling, "evaluate_teams_for_interval", hard_evaluations)
    with pytest.raises(ConflictError) as error:
        await choose_team_for_booking(
            None,  # type: ignore[arg-type]
            business_id=uuid.uuid4(),
            day=START.date(),
            timezone="Asia/Dubai",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            turnaround_minutes=60,
            source="manual",
            preferred_team_id=hard.team.id,
            override_turnaround=True,
        )
    assert error.value.code == "TEAM_TIME_CONFLICT"

    with pytest.raises(ConflictError) as error:
        await choose_team_for_booking(
            None,  # type: ignore[arg-type]
            business_id=uuid.uuid4(),
            day=START.date(),
            timezone="Asia/Dubai",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            turnaround_minutes=60,
        )
    assert error.value.code == "NO_TEAM_CAPACITY"


def test_assignment_contract_supports_auto_and_explicit_manual_override() -> None:
    automatic = AssignmentAction(client_event_id="auto-event-1", mode="auto")
    assert automatic.team_id is None
    manual = AssignmentAction(
        client_event_id="manual-event-1",
        mode="manual",
        team_id=uuid.uuid4(),
        override_turnaround=True,
    )
    assert manual.override_turnaround is True
    with pytest.raises(ValidationError):
        AssignmentAction(client_event_id="bad-auto-1", mode="auto", team_id=uuid.uuid4())


def test_public_capacity_contract_does_not_expose_team_identity() -> None:
    slot = AvailabilitySlot(
        time=START.time(),
        starts_at=START,
        ends_at=START + timedelta(hours=2),
        available=True,
        required_slot_count=1,
    )
    hold = HoldResponse(
        hold_token="h" * 40,
        starts_at=START,
        ends_at=START + timedelta(hours=2),
        expires_at=START + timedelta(minutes=10),
        required_slot_count=1,
    )
    assert "resource" not in str(slot.model_dump())
    assert "resource" not in str(hold.model_dump())
    assert "resource_id" not in BookingResponse.model_fields
    with pytest.raises(ValidationError):
        HoldCreate(
            date=START.date(),
            start_time=START.time(),
            vehicle_count=1,
            resource_id=uuid.uuid4(),
        )
