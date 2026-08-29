"""Deterministic V1 capacity and mobile-team assignment.

The module deliberately separates catalogue/snapshot duration, eligibility,
feasibility, and ranking so later travel-time scoring can be added without
changing hold or booking correctness.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as wall_time
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldStatus, JobStatus, LeaveStatus
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    BookingService,
    BookingServiceAddon,
    Job,
    LeaveRequest,
    ScheduleResource,
    Service,
    ServiceAddon,
    SlotHoldGroup,
    StaffProfile,
    TeamMembership,
)

logger = structlog.get_logger()

BLOCKING_JOB_STATUSES = {
    JobStatus.ASSIGNED,
    JobStatus.EN_ROUTE,
    JobStatus.ARRIVED,
    JobStatus.IN_PROGRESS,
}


@dataclass(frozen=True)
class CapacityItem:
    resource_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    source: Literal["job", "hold"]
    source_id: uuid.UUID

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.ends_at - self.starts_at).total_seconds() // 60))


@dataclass(frozen=True)
class TeamCandidate:
    id: uuid.UUID
    name: str
    sort_order: int
    created_at: datetime


@dataclass(frozen=True)
class TeamEvaluation:
    team: TeamCandidate
    status: Literal["available", "turnaround_conflict", "time_conflict", "unavailable"]
    reason: str | None
    same_day_job_count: int
    assigned_minutes: int
    surrounding_margin_minutes: int

    @property
    def feasible(self) -> bool:
        return self.status == "available"


@dataclass(frozen=True)
class AssignmentDecision:
    team: TeamCandidate
    candidate_count: int
    feasible_count: int
    same_day_job_count: int
    assigned_minutes: int
    assignment_source: Literal["auto", "manual"]
    reason: str


def operational_duration_minutes(
    service_minutes: Iterable[int],
    addon_minutes: Iterable[int],
    *,
    reserved_slot_floor_minutes: int,
) -> int:
    """One V1 mobile team services all vehicles sequentially.

    The immutable/current trusted service and add-on minutes are summed.  The
    existing 1–2/3+ slot reservation remains a conservative minimum floor.
    """

    snapshot_total = sum(max(0, value) for value in service_minutes) + sum(
        max(0, value) for value in addon_minutes
    )
    return max(reserved_slot_floor_minutes, snapshot_total)


async def current_selection_duration_minutes(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    service_ids: Sequence[uuid.UUID],
    addon_ids: Sequence[uuid.UUID],
    vehicle_count: int,
    reserved_slot_floor_minutes: int,
) -> int:
    if not service_ids and not addon_ids:
        # Compatibility for existing manager/legacy hold callers. Booking
        # confirmation always recalculates from authoritative selections.
        return reserved_slot_floor_minutes
    if len(service_ids) != vehicle_count:
        raise DomainError(
            "INVALID_SERVICE_SELECTION",
            "Choose one service for each vehicle before selecting a time.",
            status_code=422,
        )
    service_counts = Counter(service_ids)
    services = list(
        (
            await session.scalars(
                select(Service).where(
                    Service.business_id == business_id,
                    Service.id.in_(service_counts),
                    Service.is_active.is_(True),
                    Service.mobile_available.is_(True),
                )
            )
        ).all()
    )
    if {item.id for item in services} != set(service_counts):
        raise DomainError("INVALID_SERVICE", "One or more selected services are unavailable.")
    addon_counts = Counter(addon_ids)
    addons = (
        list(
            (
                await session.scalars(
                    select(ServiceAddon).where(
                        ServiceAddon.business_id == business_id,
                        ServiceAddon.id.in_(addon_counts),
                        ServiceAddon.is_active.is_(True),
                        ServiceAddon.mobile_available.is_(True),
                    )
                )
            ).all()
        )
        if addon_counts
        else []
    )
    if {item.id for item in addons} != set(addon_counts):
        raise DomainError("INVALID_SERVICE_ADDON", "One or more selected add-ons are unavailable.")
    return operational_duration_minutes(
        (service.estimated_duration_minutes * service_counts[service.id] for service in services),
        (addon.default_duration_minutes * addon_counts[addon.id] for addon in addons),
        reserved_slot_floor_minutes=reserved_slot_floor_minutes,
    )


async def booking_snapshot_duration_minutes(
    session: AsyncSession,
    *,
    booking_id: uuid.UUID,
    reserved_slot_floor_minutes: int,
) -> int:
    services = list(
        (
            await session.scalars(
                select(BookingService.expected_duration_minutes).where(
                    BookingService.booking_id == booking_id
                )
            )
        ).all()
    )
    addons = list(
        (
            await session.scalars(
                select(BookingServiceAddon.expected_duration_minutes).where(
                    BookingServiceAddon.booking_id == booking_id
                )
            )
        ).all()
    )
    return operational_duration_minutes(
        services,
        addons,
        reserved_slot_floor_minutes=reserved_slot_floor_minutes,
    )


def _day_bounds(day: date, timezone: str) -> tuple[datetime, datetime]:
    start = datetime.combine(day, wall_time.min, ZoneInfo(timezone)).astimezone(UTC)
    return start, start + timedelta(days=1)


async def lock_schedule_day(session: AsyncSession, *, business_id: uuid.UUID, day: date) -> None:
    """Serialize the startup-scale capacity decision for one business/day."""

    key = f"smart-schedule:{business_id}:{day.isoformat()}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
    )


async def get_eligible_teams(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    day: date,
) -> list[TeamCandidate]:
    teams = list(
        (
            await session.scalars(
                select(ScheduleResource)
                .where(
                    ScheduleResource.business_id == business_id,
                    ScheduleResource.resource_type == "mobile_team",
                    ScheduleResource.is_active.is_(True),
                )
                .order_by(
                    ScheduleResource.sort_order,
                    ScheduleResource.created_at,
                    ScheduleResource.id,
                )
            )
        ).all()
    )
    if not teams:
        return []
    membership_rows = (
        await session.execute(
            select(TeamMembership.resource_id, TeamMembership.staff_profile_id)
            .join(StaffProfile, StaffProfile.id == TeamMembership.staff_profile_id)
            .where(
                TeamMembership.resource_id.in_([team.id for team in teams]),
                TeamMembership.is_active.is_(True),
                StaffProfile.business_id == business_id,
                StaffProfile.is_active.is_(True),
            )
        )
    ).all()
    members: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for resource_id, staff_id in membership_rows:
        members[resource_id].add(staff_id)
    staff_ids = {staff_id for values in members.values() for staff_id in values}
    on_leave = (
        set(
            (
                await session.scalars(
                    select(LeaveRequest.staff_profile_id).where(
                        LeaveRequest.business_id == business_id,
                        LeaveRequest.staff_profile_id.in_(staff_ids),
                        LeaveRequest.status == LeaveStatus.APPROVED,
                        LeaveRequest.start_date <= day,
                        LeaveRequest.end_date >= day,
                    )
                )
            ).all()
        )
        if staff_ids
        else set()
    )
    return [
        TeamCandidate(
            id=team.id,
            name=team.name,
            sort_order=team.sort_order,
            created_at=team.created_at,
        )
        for team in teams
        if members[team.id] and not members[team.id].issubset(on_leave)
    ]


async def load_capacity_items(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    resource_ids: Sequence[uuid.UUID],
    day: date,
    timezone: str,
    exclude_job_id: uuid.UUID | None = None,
    exclude_hold_id: uuid.UUID | None = None,
) -> list[CapacityItem]:
    if not resource_ids:
        return []
    day_start, day_end = _day_bounds(day, timezone)
    job_statement = select(Job).where(
        Job.business_id == business_id,
        Job.assigned_resource_id.in_(resource_ids),
        Job.status.in_(BLOCKING_JOB_STATUSES),
        Job.scheduled_start < day_end,
        Job.scheduled_end > day_start,
    )
    if exclude_job_id is not None:
        job_statement = job_statement.where(Job.id != exclude_job_id)
    jobs = list((await session.scalars(job_statement)).all())
    now = datetime.now(UTC)
    hold_statement = select(SlotHoldGroup).where(
        SlotHoldGroup.business_id == business_id,
        SlotHoldGroup.resource_id.in_(resource_ids),
        SlotHoldGroup.status == HoldStatus.ACTIVE,
        SlotHoldGroup.expires_at > now,
        SlotHoldGroup.slot_start < day_end,
        SlotHoldGroup.slot_end > day_start,
    )
    if exclude_hold_id is not None:
        hold_statement = hold_statement.where(SlotHoldGroup.id != exclude_hold_id)
    holds = list((await session.scalars(hold_statement)).all())
    return [
        CapacityItem(
            resource_id=job.assigned_resource_id,
            starts_at=job.scheduled_start,
            ends_at=job.scheduled_end,
            source="job",
            source_id=job.id,
        )
        for job in jobs
        if job.assigned_resource_id is not None
    ] + [
        CapacityItem(
            resource_id=hold.resource_id,
            starts_at=hold.slot_start,
            ends_at=hold.slot_end,
            source="hold",
            source_id=hold.id,
        )
        for hold in holds
    ]


def evaluate_team(
    team: TeamCandidate,
    items: Sequence[CapacityItem],
    *,
    starts_at: datetime,
    ends_at: datetime,
    turnaround_minutes: int,
) -> TeamEvaluation:
    own = sorted(
        (item for item in items if item.resource_id == team.id), key=lambda item: item.starts_at
    )
    same_day_job_count = sum(item.source == "job" for item in own)
    assigned_minutes = sum(item.duration_minutes for item in own if item.source == "job")
    if any(item.starts_at < ends_at and item.ends_at > starts_at for item in own):
        return TeamEvaluation(
            team,
            "time_conflict",
            "Conflicting job or active hold",
            same_day_job_count,
            assigned_minutes,
            0,
        )
    buffer = timedelta(minutes=turnaround_minutes)
    previous = max(
        (item for item in own if item.ends_at <= starts_at),
        key=lambda item: item.ends_at,
        default=None,
    )
    following = min(
        (item for item in own if item.starts_at >= ends_at),
        key=lambda item: item.starts_at,
        default=None,
    )
    previous_margin = (
        int((starts_at - previous.ends_at).total_seconds() // 60)
        if previous is not None
        else 24 * 60
    )
    next_margin = (
        int((following.starts_at - ends_at).total_seconds() // 60)
        if following is not None
        else 24 * 60
    )
    if (previous is not None and previous.ends_at + buffer > starts_at) or (
        following is not None and ends_at + buffer > following.starts_at
    ):
        return TeamEvaluation(
            team,
            "turnaround_conflict",
            f"Less than the recommended {turnaround_minutes}-minute turnaround",
            same_day_job_count,
            assigned_minutes,
            min(previous_margin, next_margin),
        )
    return TeamEvaluation(
        team,
        "available",
        None,
        same_day_job_count,
        assigned_minutes,
        min(previous_margin, next_margin),
    )


def rank_evaluations(evaluations: Sequence[TeamEvaluation]) -> list[TeamEvaluation]:
    return sorted(
        (item for item in evaluations if item.feasible),
        key=lambda item: (
            0 if item.same_day_job_count == 0 else 1,
            item.same_day_job_count,
            item.assigned_minutes,
            -item.surrounding_margin_minutes,
            item.team.sort_order,
            item.team.created_at,
            str(item.team.id),
        ),
    )


async def evaluate_teams_for_interval(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    day: date,
    timezone: str,
    starts_at: datetime,
    ends_at: datetime,
    turnaround_minutes: int,
    exclude_job_id: uuid.UUID | None = None,
    exclude_hold_id: uuid.UUID | None = None,
) -> list[TeamEvaluation]:
    teams = await get_eligible_teams(session, business_id=business_id, day=day)
    items = await load_capacity_items(
        session,
        business_id=business_id,
        resource_ids=[team.id for team in teams],
        day=day,
        timezone=timezone,
        exclude_job_id=exclude_job_id,
        exclude_hold_id=exclude_hold_id,
    )
    return [
        evaluate_team(
            team,
            items,
            starts_at=starts_at,
            ends_at=ends_at,
            turnaround_minutes=turnaround_minutes,
        )
        for team in teams
    ]


async def choose_team_for_booking(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    day: date,
    timezone: str,
    starts_at: datetime,
    ends_at: datetime,
    turnaround_minutes: int,
    source: Literal["auto", "manual"] = "auto",
    preferred_team_id: uuid.UUID | None = None,
    override_turnaround: bool = False,
    exclude_job_id: uuid.UUID | None = None,
    exclude_hold_id: uuid.UUID | None = None,
) -> AssignmentDecision:
    started = time.perf_counter()
    evaluations = await evaluate_teams_for_interval(
        session,
        business_id=business_id,
        day=day,
        timezone=timezone,
        starts_at=starts_at,
        ends_at=ends_at,
        turnaround_minutes=turnaround_minutes,
        exclude_job_id=exclude_job_id,
        exclude_hold_id=exclude_hold_id,
    )
    chosen: TeamEvaluation | None = None
    if preferred_team_id is not None:
        chosen = next((item for item in evaluations if item.team.id == preferred_team_id), None)
        if chosen is None:
            raise DomainError(
                "TEAM_NOT_AVAILABLE",
                "The selected team is not operationally available.",
                status_code=409,
            )
        if chosen.status == "time_conflict":
            raise ConflictError("TEAM_TIME_CONFLICT", "This team has a conflicting job.")
        if chosen.status == "turnaround_conflict" and not override_turnaround:
            raise ConflictError(
                "TEAM_TURNAROUND_CONFLICT",
                "This team does not have the recommended turnaround between jobs.",
            )
        if chosen.status not in {"available", "turnaround_conflict"}:
            raise DomainError(
                "TEAM_NOT_AVAILABLE", "The selected team is not available.", status_code=409
            )
    else:
        ranked = rank_evaluations(evaluations)
        chosen = ranked[0] if ranked else None
        if chosen is None:
            logger.info(
                "smart_scheduler_decision",
                scheduler_candidate_count=len(evaluations),
                scheduler_feasible_count=0,
                scheduler_duration_ms=round((time.perf_counter() - started) * 1000, 2),
                assignment_source=source,
                result="no_capacity",
            )
            raise ConflictError(
                "NO_TEAM_CAPACITY", "This time is no longer available. Please choose another time."
            )
    feasible_count = sum(item.feasible for item in evaluations)
    decision = AssignmentDecision(
        team=chosen.team,
        candidate_count=len(evaluations),
        feasible_count=feasible_count,
        same_day_job_count=chosen.same_day_job_count,
        assigned_minutes=chosen.assigned_minutes,
        assignment_source=source,
        reason=(
            "Manual team selection"
            if source == "manual"
            else "Selected the available team with the lightest same-day schedule"
        ),
    )
    logger.info(
        "smart_scheduler_decision",
        scheduler_candidate_count=decision.candidate_count,
        scheduler_feasible_count=decision.feasible_count,
        scheduler_duration_ms=round((time.perf_counter() - started) * 1000, 2),
        assignment_source=source,
        result="selected",
    )
    return decision
