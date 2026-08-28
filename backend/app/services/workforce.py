import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import (
    BookingStatus,
    CancellationStatus,
    JobStatus,
    LeaveStatus,
    PaymentStatus,
)
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AttendanceSession,
    AuditEvent,
    Booking,
    BookingService,
    BusinessSettings,
    CancellationRequest,
    Job,
    LeaveRequest,
    Payment,
    ScheduleResource,
    Shift,
    StaffProfile,
    StaffShiftAssignment,
    TeamMembership,
)
from app.schemas.staff import (
    AttendanceAction,
    AttendanceList,
    AttendanceOverviewItem,
    AttendanceRecord,
    AttentionItem,
    DashboardMetric,
    LeaveCreate,
    LeaveReview,
    LeaveView,
    MixRow,
    OperationsDashboard,
    PerformanceRow,
    ReportPoint,
    ReportSummary,
    ReportV2,
    ShiftAssignmentCreate,
    ShiftAssignmentView,
    ShiftCreate,
    ShiftView,
    TeamCreate,
    TeamDetail,
    TeamMembersUpdate,
    TeamPerformanceRow,
    TeamReference,
    TeamSummary,
    TeamUpdate,
)
from app.services.finance import finance_overview
from app.services.staff_accounts import _profile_data
from app.services.staff_operations import list_jobs


def _day_bounds(day: date, timezone: str) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, ZoneInfo(timezone)).astimezone(UTC)
    return start, start + timedelta(days=1)


def attendance_late_minutes(
    clock_in_at: datetime,
    work_date: date,
    shift_start: time | None,
    timezone: str,
    grace_minutes: int,
) -> int:
    if shift_start is None:
        return 0
    scheduled = datetime.combine(work_date, shift_start, ZoneInfo(timezone)).astimezone(UTC)
    return max(
        0,
        int((clock_in_at - scheduled).total_seconds() // 60) - grace_minutes,
    )


def attendance_category(
    *,
    has_open_session: bool,
    has_closed_session: bool,
    late_minutes: int,
    has_shift: bool,
    shift_started: bool,
    on_approved_leave: bool,
    shift_ended: bool,
) -> tuple[
    Literal[
        "scheduled",
        "working",
        "late",
        "clocked_out",
        "not_clocked_in",
        "off_today",
        "approved_leave",
    ],
    bool,
]:
    """Return the operational status and whether a scheduled shift was missed."""
    if has_open_session:
        return ("late" if late_minutes else "working", False)
    if has_closed_session:
        return ("clocked_out", False)
    if on_approved_leave:
        return ("approved_leave", False)
    if not has_shift:
        return ("off_today", False)
    if not shift_started:
        return ("scheduled", False)
    return ("not_clocked_in", shift_ended)


def _audit(
    session: AsyncSession,
    context: StaffContext,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
    )


async def list_teams(
    session: AsyncSession, context: StaffContext, *, day: date | None = None
) -> list[TeamSummary]:
    target_day = day or datetime.now(ZoneInfo(context.timezone)).date()
    start, end = _day_bounds(target_day, context.timezone)
    rows = (
        await session.execute(
            select(
                ScheduleResource.id,
                ScheduleResource.name,
                ScheduleResource.is_active,
                func.count(distinct(TeamMembership.staff_profile_id)).filter(
                    TeamMembership.is_active.is_(True)
                ),
                func.count(distinct(Job.id)),
                func.max(
                    case(
                        (
                            Job.status.in_(
                                [JobStatus.EN_ROUTE, JobStatus.ARRIVED, JobStatus.IN_PROGRESS]
                            ),
                            Booking.reference,
                        )
                    )
                ),
                func.max(
                    case(
                        (
                            Job.status.in_(
                                [JobStatus.EN_ROUTE, JobStatus.ARRIVED, JobStatus.IN_PROGRESS]
                            ),
                            Job.status,
                        )
                    )
                ),
            )
            .outerjoin(TeamMembership, TeamMembership.resource_id == ScheduleResource.id)
            .outerjoin(
                Job,
                (Job.assigned_resource_id == ScheduleResource.id)
                & (Job.scheduled_start >= start)
                & (Job.scheduled_start < end),
            )
            .outerjoin(Booking, Booking.id == Job.booking_id)
            .where(
                ScheduleResource.business_id == context.business_id,
                ScheduleResource.resource_type == "mobile_team",
            )
            .group_by(ScheduleResource.id)
            .order_by(ScheduleResource.is_active.desc(), ScheduleResource.sort_order)
            .limit(100)
        )
    ).all()
    return [
        TeamSummary(
            id=id,
            name=name,
            is_active=is_active,
            member_count=member_count,
            jobs_today=jobs_today,
            active_job_reference=reference,
            active_job_status=status,
        )
        for id, name, is_active, member_count, jobs_today, reference, status in rows
    ]


async def get_team(session: AsyncSession, context: StaffContext, team_id: uuid.UUID) -> TeamDetail:
    summary = next(
        (team for team in await list_teams(session, context) if team.id == team_id),
        None,
    )
    if summary is None:
        raise DomainError("TEAM_NOT_FOUND", "Team not found.", status_code=404)
    profiles = list(
        (
            await session.scalars(
                select(StaffProfile)
                .join(TeamMembership, TeamMembership.staff_profile_id == StaffProfile.id)
                .where(
                    TeamMembership.resource_id == team_id,
                    TeamMembership.is_active.is_(True),
                    StaffProfile.business_id == context.business_id,
                )
                .order_by(StaffProfile.display_name)
            )
        ).all()
    )
    jobs = await list_jobs(
        session,
        context,
        day=datetime.now(ZoneInfo(context.timezone)).date(),
        scope="all",
        team_id=team_id,
        limit=100,
    )
    return TeamDetail(
        **summary.model_dump(),
        members=[
            _profile_data(profile, [TeamReference(id=team_id, name=summary.name)])
            for profile in profiles
        ],
        jobs=jobs.jobs,
    )


async def create_team(
    session: AsyncSession, context: StaffContext, request: TeamCreate
) -> TeamDetail:
    name = request.name.strip()
    existing = await session.scalar(
        select(ScheduleResource.id).where(
            ScheduleResource.business_id == context.business_id,
            func.lower(ScheduleResource.name) == name.lower(),
        )
    )
    if existing is not None:
        raise ConflictError("TEAM_NAME_TAKEN", "A team with that name already exists.")
    maximum_sort = await session.scalar(
        select(func.coalesce(func.max(ScheduleResource.sort_order), 0)).where(
            ScheduleResource.business_id == context.business_id
        )
    )
    team = ScheduleResource(
        business_id=context.business_id,
        name=name,
        resource_type="mobile_team",
        is_active=True,
        sort_order=int(maximum_sort or 0) + 1,
    )
    session.add(team)
    await session.flush()
    _audit(session, context, "team_created", "schedule_resource", team.id)
    return await get_team(session, context, team.id)


async def update_team(
    session: AsyncSession,
    context: StaffContext,
    team_id: uuid.UUID,
    request: TeamUpdate,
) -> TeamDetail:
    team = await _owned_team(session, context, team_id, lock=True)
    if request.is_active is False and team.is_active:
        future_job = await session.scalar(
            select(Job.id)
            .join(Booking, Booking.id == Job.booking_id)
            .where(
                Job.business_id == context.business_id,
                Job.assigned_resource_id == team.id,
                Job.scheduled_start > datetime.now(UTC),
                Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
            )
            .limit(1)
        )
        if future_job is not None:
            raise ConflictError(
                "TEAM_HAS_FUTURE_JOBS",
                "Reassign future jobs before deactivating this team.",
            )
    if request.name is not None:
        team.name = request.name.strip()
    if request.is_active is not None:
        team.is_active = request.is_active
    _audit(session, context, "team_updated", "schedule_resource", team.id)
    await session.flush()
    return await get_team(session, context, team.id)


async def replace_team_members(
    session: AsyncSession,
    context: StaffContext,
    team_id: uuid.UUID,
    request: TeamMembersUpdate,
) -> TeamDetail:
    await _owned_team(session, context, team_id, lock=True)
    staff_ids = set(request.staff_ids)
    valid_ids = set(
        (
            await session.scalars(
                select(StaffProfile.id).where(
                    StaffProfile.id.in_(staff_ids),
                    StaffProfile.business_id == context.business_id,
                    StaffProfile.is_active.is_(True),
                )
            )
        ).all()
    )
    if valid_ids != staff_ids:
        raise DomainError(
            "STAFF_NOT_FOUND",
            "One or more active staff members were not found.",
            status_code=404,
        )
    memberships = list(
        (
            await session.scalars(
                select(TeamMembership)
                .where(TeamMembership.resource_id == team_id)
                .with_for_update()
            )
        ).all()
    )
    by_staff = {membership.staff_profile_id: membership for membership in memberships}
    for existing_membership in memberships:
        if existing_membership.is_active and existing_membership.staff_profile_id not in staff_ids:
            existing_membership.is_active = False
            _audit(
                session,
                context,
                "team_member_removed",
                "team_membership",
                existing_membership.id,
            )
    for staff_id in staff_ids:
        candidate = by_staff.get(staff_id)
        if candidate is None:
            candidate = TeamMembership(resource_id=team_id, staff_profile_id=staff_id)
            session.add(candidate)
            await session.flush()
            _audit(
                session,
                context,
                "team_member_added",
                "team_membership",
                candidate.id,
            )
        elif not candidate.is_active:
            candidate.is_active = True
            _audit(
                session,
                context,
                "team_member_added",
                "team_membership",
                candidate.id,
            )
    await session.flush()
    return await get_team(session, context, team_id)


async def _owned_team(
    session: AsyncSession,
    context: StaffContext,
    team_id: uuid.UUID,
    *,
    lock: bool = False,
) -> ScheduleResource:
    statement = select(ScheduleResource).where(
        ScheduleResource.id == team_id,
        ScheduleResource.business_id == context.business_id,
        ScheduleResource.resource_type == "mobile_team",
    )
    if lock:
        statement = statement.with_for_update()
    team = (await session.scalars(statement)).one_or_none()
    if team is None:
        raise DomainError("TEAM_NOT_FOUND", "Team not found.", status_code=404)
    return team


async def clock_in(
    session: AsyncSession,
    context: StaffContext,
    request: AttendanceAction,
) -> AttendanceRecord:
    # Serialize clock-in attempts on the owned staff row before checking the partial
    # unique index. This makes simultaneous device taps idempotent instead of surfacing
    # a database uniqueness error from two transactions that both observed no open row.
    await session.scalar(
        select(StaffProfile.id)
        .where(
            StaffProfile.id == context.staff_id,
            StaffProfile.business_id == context.business_id,
        )
        .with_for_update()
    )
    existing = (
        await session.scalars(
            select(AttendanceSession)
            .where(
                AttendanceSession.staff_profile_id == context.staff_id,
                AttendanceSession.clock_out_at.is_(None),
            )
            .with_for_update()
        )
    ).one_or_none()
    if existing is not None:
        return await _attendance_view(session, context, existing)
    item = AttendanceSession(
        business_id=context.business_id,
        staff_profile_id=context.staff_id,
        clock_in_at=datetime.now(UTC),
        clock_in_client_timestamp=request.client_timestamp,
    )
    session.add(item)
    await session.flush()
    _audit(session, context, "attendance_clocked_in", "attendance_session", item.id)
    return await _attendance_view(session, context, item)


async def clock_out(
    session: AsyncSession,
    context: StaffContext,
    request: AttendanceAction,
) -> AttendanceRecord:
    item = (
        await session.scalars(
            select(AttendanceSession)
            .where(AttendanceSession.staff_profile_id == context.staff_id)
            .order_by(AttendanceSession.clock_in_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).one_or_none()
    if item is None:
        raise ConflictError("NOT_CLOCKED_IN", "There is no attendance session to clock out.")
    if item.clock_out_at is None:
        item.clock_out_at = datetime.now(UTC)
        item.clock_out_client_timestamp = request.client_timestamp
        _audit(session, context, "attendance_clocked_out", "attendance_session", item.id)
        await session.flush()
    return await _attendance_view(session, context, item)


async def list_attendance(
    session: AsyncSession,
    context: StaffContext,
    *,
    start_date: date,
    end_date: date,
    staff_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> AttendanceList:
    start, _ = _day_bounds(start_date, context.timezone)
    _, end = _day_bounds(end_date, context.timezone)
    statement = (
        select(AttendanceSession, StaffProfile.display_name)
        .join(StaffProfile, StaffProfile.id == AttendanceSession.staff_profile_id)
        .where(
            AttendanceSession.business_id == context.business_id,
            AttendanceSession.clock_in_at >= start,
            AttendanceSession.clock_in_at < end,
        )
    )
    if context.role == "employee":
        statement = statement.where(AttendanceSession.staff_profile_id == context.staff_id)
    elif staff_id is not None:
        statement = statement.where(AttendanceSession.staff_profile_id == staff_id)
    rows = (
        await session.execute(
            statement.order_by(AttendanceSession.clock_in_at.desc()).offset(offset).limit(limit + 1)
        )
    ).all()
    selected = rows[:limit]
    staff_ids = {item.staff_profile_id for item, _name in selected}
    assignments = (
        await session.execute(
            select(
                StaffShiftAssignment.staff_profile_id,
                StaffShiftAssignment.work_date,
                Shift.start_time,
            )
            .join(Shift, Shift.id == StaffShiftAssignment.shift_id)
            .where(
                StaffShiftAssignment.business_id == context.business_id,
                StaffShiftAssignment.staff_profile_id.in_(staff_ids),
                StaffShiftAssignment.work_date >= start_date,
                StaffShiftAssignment.work_date <= end_date,
            )
        )
    ).all()
    shift_starts = {
        (assignment_staff_id, work_date): shift_start
        for assignment_staff_id, work_date, shift_start in assignments
    }
    grace_minutes = (
        await session.scalar(
            select(BusinessSettings.attendance_grace_minutes).where(
                BusinessSettings.business_id == context.business_id
            )
        )
    ) or 0
    records = [
        await _attendance_view(
            session,
            context,
            item,
            staff_name=name,
            shift_start=shift_starts.get(
                (
                    item.staff_profile_id,
                    item.clock_in_at.astimezone(ZoneInfo(context.timezone)).date(),
                )
            ),
            grace_minutes=grace_minutes,
            prefetched=True,
        )
        for item, name in selected
    ]
    return AttendanceList(
        items=records,
        next_offset=offset + limit if len(rows) > limit else None,
    )


async def attendance_overview(
    session: AsyncSession,
    context: StaffContext,
    *,
    day: date,
    now: datetime | None = None,
) -> list[AttendanceOverviewItem]:
    """Categorize every visible staff member with a bounded set of bulk queries."""
    start, end = _day_bounds(day, context.timezone)
    current = now or datetime.now(UTC)
    staff_statement = select(StaffProfile.id, StaffProfile.display_name).where(
        StaffProfile.business_id == context.business_id,
        StaffProfile.is_active.is_(True),
    )
    if context.role == "employee":
        staff_statement = staff_statement.where(StaffProfile.id == context.staff_id)
    staff_rows = (await session.execute(staff_statement.order_by(StaffProfile.display_name))).all()
    staff_ids = [staff_id for staff_id, _name in staff_rows]
    if not staff_ids:
        return []

    assignment_rows = (
        await session.execute(
            select(
                StaffShiftAssignment.staff_profile_id,
                Shift.name,
                Shift.start_time,
                Shift.end_time,
            )
            .join(Shift, Shift.id == StaffShiftAssignment.shift_id)
            .where(
                StaffShiftAssignment.business_id == context.business_id,
                StaffShiftAssignment.staff_profile_id.in_(staff_ids),
                StaffShiftAssignment.work_date == day,
            )
        )
    ).all()
    assignments = {
        staff_id: (shift_name, shift_start, shift_end)
        for staff_id, shift_name, shift_start, shift_end in assignment_rows
    }
    attendance_rows = (
        (
            await session.execute(
                select(AttendanceSession)
                .where(
                    AttendanceSession.business_id == context.business_id,
                    AttendanceSession.staff_profile_id.in_(staff_ids),
                    AttendanceSession.clock_in_at >= start,
                    AttendanceSession.clock_in_at < end,
                )
                .order_by(AttendanceSession.clock_in_at.desc())
            )
        )
        .scalars()
        .all()
    )
    sessions: dict[uuid.UUID, AttendanceSession] = {}
    for attendance_session in attendance_rows:
        existing = sessions.get(attendance_session.staff_profile_id)
        if existing is None or (
            existing.clock_out_at is not None and attendance_session.clock_out_at is None
        ):
            sessions[attendance_session.staff_profile_id] = attendance_session
    leave_staff_ids = set(
        (
            await session.scalars(
                select(LeaveRequest.staff_profile_id).where(
                    LeaveRequest.business_id == context.business_id,
                    LeaveRequest.staff_profile_id.in_(staff_ids),
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    LeaveRequest.start_date <= day,
                    LeaveRequest.end_date >= day,
                )
            )
        ).all()
    )
    grace_minutes = (
        await session.scalar(
            select(BusinessSettings.attendance_grace_minutes).where(
                BusinessSettings.business_id == context.business_id
            )
        )
    ) or 0
    result: list[AttendanceOverviewItem] = []
    zone = ZoneInfo(context.timezone)
    for staff_id, staff_name in staff_rows:
        assignment = assignments.get(staff_id)
        staff_session = sessions.get(staff_id)
        shift_start = assignment[1] if assignment else None
        shift_end = assignment[2] if assignment else None
        late = (
            attendance_late_minutes(
                staff_session.clock_in_at,
                day,
                shift_start,
                context.timezone,
                grace_minutes,
            )
            if staff_session is not None
            else 0
        )
        shift_ended = bool(
            shift_end is not None
            and current >= datetime.combine(day, shift_end, zone).astimezone(UTC)
        )
        shift_started = bool(
            shift_start is not None
            and current >= datetime.combine(day, shift_start, zone).astimezone(UTC)
        )
        status, missed = attendance_category(
            has_open_session=staff_session is not None and staff_session.clock_out_at is None,
            has_closed_session=staff_session is not None and staff_session.clock_out_at is not None,
            late_minutes=late,
            has_shift=assignment is not None,
            shift_started=shift_started,
            on_approved_leave=staff_id in leave_staff_ids,
            shift_ended=shift_ended,
        )
        finished = (staff_session.clock_out_at or current) if staff_session is not None else current
        worked = (
            max(0, int((finished - staff_session.clock_in_at).total_seconds() // 60))
            if staff_session is not None
            else 0
        )
        result.append(
            AttendanceOverviewItem(
                staff_id=staff_id,
                staff_name=staff_name,
                status=status,
                shift_name=assignment[0] if assignment else None,
                shift_start=shift_start,
                shift_end=shift_end,
                clock_in_at=staff_session.clock_in_at if staff_session else None,
                clock_out_at=staff_session.clock_out_at if staff_session else None,
                worked_minutes=worked,
                late_minutes=late,
                missed_shift=missed,
            )
        )
    return result


async def _attendance_view(
    session: AsyncSession,
    context: StaffContext,
    item: AttendanceSession,
    *,
    staff_name: str | None = None,
    shift_start: time | None = None,
    grace_minutes: int | None = None,
    prefetched: bool = False,
) -> AttendanceRecord:
    if staff_name is None:
        staff_name = (
            await session.scalar(
                select(StaffProfile.display_name).where(StaffProfile.id == item.staff_profile_id)
            )
        ) or "Staff"
    local_day = item.clock_in_at.astimezone(ZoneInfo(context.timezone)).date()
    if not prefetched:
        shift_start = await session.scalar(
            select(Shift.start_time)
            .join(StaffShiftAssignment, StaffShiftAssignment.shift_id == Shift.id)
            .where(
                StaffShiftAssignment.staff_profile_id == item.staff_profile_id,
                StaffShiftAssignment.work_date == local_day,
                StaffShiftAssignment.business_id == context.business_id,
            )
        )
        grace_minutes = (
            await session.scalar(
                select(BusinessSettings.attendance_grace_minutes).where(
                    BusinessSettings.business_id == context.business_id
                )
            )
        ) or 0
    late = attendance_late_minutes(
        item.clock_in_at,
        local_day,
        shift_start,
        context.timezone,
        grace_minutes or 0,
    )
    finished = item.clock_out_at or datetime.now(UTC)
    worked = max(0, int((finished - item.clock_in_at).total_seconds() // 60))
    status = "working" if item.clock_out_at is None else "clocked_out"
    if late:
        status = "late" if item.clock_out_at is None else "clocked_out_late"
    return AttendanceRecord(
        id=item.id,
        staff_id=item.staff_profile_id,
        staff_name=staff_name,
        clock_in_at=item.clock_in_at,
        clock_out_at=item.clock_out_at,
        worked_minutes=worked,
        late_minutes=late,
        status=status,
    )


async def create_shift(
    session: AsyncSession, context: StaffContext, request: ShiftCreate
) -> ShiftView:
    duplicate = await session.scalar(
        select(Shift.id).where(
            Shift.business_id == context.business_id,
            func.lower(Shift.name) == request.name.strip().lower(),
        )
    )
    if duplicate is not None:
        raise ConflictError("SHIFT_NAME_TAKEN", "A shift with this name already exists.")
    shift = Shift(
        business_id=context.business_id,
        name=request.name.strip(),
        start_time=request.start_time,
        end_time=request.end_time,
        is_active=True,
    )
    session.add(shift)
    await session.flush()
    _audit(session, context, "shift_created", "shift", shift.id)
    return _shift_view(shift)


async def list_shifts(session: AsyncSession, context: StaffContext) -> list[ShiftView]:
    shifts = (
        await session.scalars(
            select(Shift)
            .where(Shift.business_id == context.business_id)
            .order_by(Shift.is_active.desc(), Shift.start_time)
            .limit(100)
        )
    ).all()
    return [_shift_view(shift) for shift in shifts]


def _shift_view(shift: Shift) -> ShiftView:
    return ShiftView(
        id=shift.id,
        name=shift.name,
        start_time=shift.start_time,
        end_time=shift.end_time,
        is_active=shift.is_active,
    )


async def assign_shift(
    session: AsyncSession,
    context: StaffContext,
    request: ShiftAssignmentCreate,
) -> ShiftAssignmentView:
    staff = await session.scalar(
        select(StaffProfile.id)
        .where(
            StaffProfile.id == request.staff_id,
            StaffProfile.business_id == context.business_id,
            StaffProfile.is_active.is_(True),
        )
        .with_for_update()
    )
    shift = (
        await session.scalars(
            select(Shift).where(
                Shift.id == request.shift_id,
                Shift.business_id == context.business_id,
                Shift.is_active.is_(True),
            )
        )
    ).one_or_none()
    if staff is None or shift is None:
        raise DomainError(
            "SHIFT_ASSIGNMENT_TARGET_NOT_FOUND",
            "The active staff member or shift was not found.",
            status_code=404,
        )
    if request.team_id is not None:
        await _owned_team(session, context, request.team_id)
        membership = await session.scalar(
            select(TeamMembership.id).where(
                TeamMembership.resource_id == request.team_id,
                TeamMembership.staff_profile_id == request.staff_id,
                TeamMembership.is_active.is_(True),
            )
        )
        if membership is None:
            raise ConflictError(
                "STAFF_NOT_ON_TEAM",
                "Add this employee to the selected team before assigning the shift.",
            )
    assignment = (
        await session.scalars(
            select(StaffShiftAssignment)
            .where(
                StaffShiftAssignment.business_id == context.business_id,
                StaffShiftAssignment.staff_profile_id == request.staff_id,
                StaffShiftAssignment.work_date == request.work_date,
            )
            .with_for_update()
        )
    ).one_or_none()
    if assignment is not None:
        if assignment.business_id != context.business_id:
            raise DomainError("SHIFT_NOT_FOUND", "Shift assignment not found.", status_code=404)
        assignment.shift_id = request.shift_id
        assignment.resource_id = request.team_id
        event_type = "shift_assignment_updated"
    else:
        assignment = StaffShiftAssignment(
            business_id=context.business_id,
            staff_profile_id=request.staff_id,
            shift_id=request.shift_id,
            work_date=request.work_date,
            resource_id=request.team_id,
        )
        session.add(assignment)
        event_type = "shift_assigned"
    await session.flush()
    _audit(session, context, event_type, "shift_assignment", assignment.id)
    return await _shift_assignment_view(session, assignment)


async def list_shift_assignments(
    session: AsyncSession,
    context: StaffContext,
    *,
    start_date: date,
    end_date: date,
) -> list[ShiftAssignmentView]:
    statement = (
        select(
            StaffShiftAssignment,
            StaffProfile.display_name,
            Shift.name,
            Shift.start_time,
            Shift.end_time,
            ScheduleResource.name,
        )
        .join(StaffProfile, StaffProfile.id == StaffShiftAssignment.staff_profile_id)
        .join(Shift, Shift.id == StaffShiftAssignment.shift_id)
        .outerjoin(ScheduleResource, ScheduleResource.id == StaffShiftAssignment.resource_id)
        .where(
            StaffShiftAssignment.business_id == context.business_id,
            StaffShiftAssignment.work_date >= start_date,
            StaffShiftAssignment.work_date <= end_date,
        )
    )
    if context.role == "employee":
        statement = statement.where(StaffShiftAssignment.staff_profile_id == context.staff_id)
    rows = (
        await session.execute(statement.order_by(StaffShiftAssignment.work_date).limit(500))
    ).all()
    return [
        _shift_assignment_data(item, staff_name, shift_name, start, end, team_name)
        for item, staff_name, shift_name, start, end, team_name in rows
    ]


async def _shift_assignment_view(
    session: AsyncSession, item: StaffShiftAssignment
) -> ShiftAssignmentView:
    row = (
        await session.execute(
            select(
                StaffProfile.display_name,
                Shift.name,
                Shift.start_time,
                Shift.end_time,
                ScheduleResource.name,
            )
            .select_from(StaffShiftAssignment)
            .join(
                StaffProfile,
                StaffProfile.id == StaffShiftAssignment.staff_profile_id,
            )
            .join(Shift, Shift.id == StaffShiftAssignment.shift_id)
            .outerjoin(
                ScheduleResource,
                and_(
                    ScheduleResource.id == StaffShiftAssignment.resource_id,
                    ScheduleResource.business_id == StaffShiftAssignment.business_id,
                ),
            )
            .where(
                StaffShiftAssignment.id == item.id,
                StaffShiftAssignment.business_id == item.business_id,
                StaffProfile.business_id == item.business_id,
                Shift.business_id == item.business_id,
            )
        )
    ).one()
    staff_name, shift_name, start_time, end_time, team_name = row
    return _shift_assignment_data(item, staff_name, shift_name, start_time, end_time, team_name)


def _shift_assignment_data(
    item: StaffShiftAssignment,
    staff_name: str,
    shift_name: str,
    start_time: time,
    end_time: time,
    team_name: str | None,
) -> ShiftAssignmentView:
    return ShiftAssignmentView(
        id=item.id,
        staff_id=item.staff_profile_id,
        staff_name=staff_name,
        shift_id=item.shift_id,
        shift_name=shift_name,
        work_date=item.work_date,
        start_time=start_time,
        end_time=end_time,
        team_id=item.resource_id,
        team_name=team_name,
    )


async def create_leave(
    session: AsyncSession, context: StaffContext, request: LeaveCreate
) -> LeaveView:
    overlap = await session.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.staff_profile_id == context.staff_id,
            LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            LeaveRequest.start_date <= request.end_date,
            LeaveRequest.end_date >= request.start_date,
        )
    )
    if overlap is not None:
        raise ConflictError("LEAVE_DATE_CONFLICT", "A leave request already covers these dates.")
    item = LeaveRequest(
        business_id=context.business_id,
        staff_profile_id=context.staff_id,
        start_date=request.start_date,
        end_date=request.end_date,
        reason=request.reason.strip(),
        status=LeaveStatus.PENDING,
    )
    session.add(item)
    await session.flush()
    _audit(session, context, "leave_requested", "leave_request", item.id)
    return await _leave_view(session, item)


async def list_leave(
    session: AsyncSession, context: StaffContext, *, status: str | None = None
) -> list[LeaveView]:
    statement = (
        select(LeaveRequest, StaffProfile.display_name)
        .join(StaffProfile, StaffProfile.id == LeaveRequest.staff_profile_id)
        .where(LeaveRequest.business_id == context.business_id)
    )
    if context.role == "employee":
        statement = statement.where(LeaveRequest.staff_profile_id == context.staff_id)
    if status:
        statement = statement.where(LeaveRequest.status == status)
    rows = (
        await session.execute(statement.order_by(LeaveRequest.created_at.desc()).limit(200))
    ).all()
    return [_leave_data(item, staff_name) for item, staff_name in rows]


async def review_leave(
    session: AsyncSession,
    context: StaffContext,
    leave_id: uuid.UUID,
    request: LeaveReview,
) -> LeaveView:
    item = (
        await session.scalars(
            select(LeaveRequest)
            .where(
                LeaveRequest.id == leave_id,
                LeaveRequest.business_id == context.business_id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if item is None:
        raise DomainError("LEAVE_NOT_FOUND", "Leave request not found.", status_code=404)
    if item.status != LeaveStatus.PENDING:
        return await _leave_view(session, item)
    if request.decision == LeaveStatus.APPROVED:
        start, _ = _day_bounds(item.start_date, context.timezone)
        _, end = _day_bounds(item.end_date, context.timezone)
        team_ids = select(TeamMembership.resource_id).where(
            TeamMembership.staff_profile_id == item.staff_profile_id,
            TeamMembership.is_active.is_(True),
        )
        conflict = await session.scalar(
            select(Job.id).where(
                Job.business_id == context.business_id,
                Job.scheduled_start >= start,
                Job.scheduled_start < end,
                Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
                or_(
                    Job.assigned_staff_id == item.staff_profile_id,
                    Job.assigned_resource_id.in_(team_ids),
                ),
            )
        )
        if conflict is not None:
            raise ConflictError(
                "LEAVE_HAS_ASSIGNED_WORK",
                "Reassign this employee's future work before approving leave.",
            )
    item.status = request.decision
    item.reviewed_by_staff_id = context.staff_id
    item.reviewed_at = datetime.now(UTC)
    item.review_note = request.review_note
    _audit(
        session,
        context,
        "leave_approved" if request.decision == "approved" else "leave_rejected",
        "leave_request",
        item.id,
    )
    await session.flush()
    return await _leave_view(session, item)


async def _leave_view(session: AsyncSession, item: LeaveRequest) -> LeaveView:
    name = await session.scalar(
        select(StaffProfile.display_name).where(StaffProfile.id == item.staff_profile_id)
    )
    return _leave_data(item, name or "Staff")


def _leave_data(item: LeaveRequest, staff_name: str) -> LeaveView:
    return LeaveView(
        id=item.id,
        staff_id=item.staff_profile_id,
        staff_name=staff_name,
        start_date=item.start_date,
        end_date=item.end_date,
        reason=item.reason,
        status=item.status,
        reviewed_at=item.reviewed_at,
        review_note=item.review_note,
    )


async def operations_dashboard(
    session: AsyncSession, context: StaffContext, *, day: date
) -> OperationsDashboard:
    start, end = _day_bounds(day, context.timezone)
    pending_leave_query = (
        select(func.count(LeaveRequest.id))
        .where(
            LeaveRequest.business_id == context.business_id,
            LeaveRequest.status == LeaveStatus.PENDING,
        )
        .correlate(None)
        .scalar_subquery()
    )
    cancellations_query = (
        select(func.count(CancellationRequest.id))
        .join(Booking, Booking.id == CancellationRequest.booking_id)
        .where(
            Booking.business_id == context.business_id,
            CancellationRequest.status == CancellationStatus.REQUESTED,
        )
        .correlate(None)
        .scalar_subquery()
    )
    financial = (
        await session.execute(
            select(
                func.count(Job.id),
                func.count(Job.id).filter(Job.status == JobStatus.COMPLETED),
                func.count(Job.id).filter(Job.status == JobStatus.UNASSIGNED),
                func.count(Job.id).filter(Job.status == JobStatus.EN_ROUTE),
                func.count(Job.id).filter(Job.status == JobStatus.IN_PROGRESS),
                func.coalesce(func.sum(Booking.total_amount_minor), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (Payment.status == PaymentStatus.PAID, Payment.amount_minor),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.max(Booking.currency_code),
                pending_leave_query,
                cancellations_query,
            )
            .select_from(Job)
            .join(Booking, Booking.id == Job.booking_id)
            .join(Payment, Payment.booking_id == Booking.id)
            .where(
                Job.business_id == context.business_id,
                Job.scheduled_start >= start,
                Job.scheduled_start < end,
            )
        )
    ).one()
    (
        jobs,
        completed,
        unassigned,
        en_route,
        washing,
        booked,
        collected,
        currency,
        pending_leave,
        cancellations,
    ) = financial
    attendance_snapshot = await attendance_overview(session, context, day=day)
    clocked_in = sum(item.status in {"working", "late"} for item in attendance_snapshot)
    late_staff = sum(item.status == "late" for item in attendance_snapshot)
    missed_staff = sum(item.missed_shift for item in attendance_snapshot)
    attention = []
    for kind, count, label in (
        ("unassigned_jobs", unassigned, "unassigned jobs"),
        ("leave_requests", pending_leave, "pending leave requests"),
        ("cancellations", cancellations, "cancellation requests"),
        ("late_staff", late_staff, "employees late"),
        ("missed_shifts", missed_staff, "missed shifts"),
    ):
        if count:
            attention.append(AttentionItem(kind=kind, count=count, label=label))
    all_jobs = await list_jobs(session, context, day=day, scope="all", limit=100)
    active = [
        job
        for job in all_jobs.jobs
        if job.status in {JobStatus.EN_ROUTE, JobStatus.ARRIVED, JobStatus.IN_PROGRESS}
    ]
    metrics = [
        DashboardMetric(key="collected", label="Collected", value=collected),
        DashboardMetric(key="booked", label="Booked", value=booked),
        DashboardMetric(key="jobs", label="Jobs", value=jobs),
        DashboardMetric(key="completed", label="Completed", value=completed),
        DashboardMetric(key="en_route", label="En route", value=en_route),
        DashboardMetric(key="washing", label="Washing", value=washing),
        DashboardMetric(key="clocked_in", label="Clocked in", value=clocked_in or 0),
    ]
    return OperationsDashboard(
        date=day,
        currency_code=currency or "AED",
        metrics=metrics,
        attention=attention,
        active_jobs=active,
    )


async def report_v2(
    session: AsyncSession,
    context: StaffContext,
    start_date: date,
    end_date: date,
) -> ReportV2:
    if end_date < start_date or (end_date - start_date).days > 366:
        raise DomainError(
            "INVALID_REPORT_RANGE",
            "Choose a report range of up to 366 days.",
            status_code=422,
        )
    start, _ = _day_bounds(start_date, context.timezone)
    _, end = _day_bounds(end_date, context.timezone)
    local_date = func.date(func.timezone(context.timezone, Booking.scheduled_start))
    rows = (
        await session.execute(
            select(
                local_date,
                func.coalesce(func.sum(Booking.total_amount_minor), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (Payment.status == PaymentStatus.PAID, Payment.amount_minor),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.count(Booking.id),
                func.count(Booking.id).filter(Booking.status == BookingStatus.COMPLETED),
                func.count(Booking.id).filter(Booking.status == BookingStatus.CANCELLED),
                func.max(Booking.currency_code),
            )
            .join(Payment, Payment.booking_id == Booking.id)
            .where(
                Booking.business_id == context.business_id,
                Booking.scheduled_start >= start,
                Booking.scheduled_start < end,
            )
            .group_by(local_date)
            .order_by(local_date)
        )
    ).all()
    series = [
        ReportPoint(
            date=day,
            booked_sales_minor=booked,
            collected_revenue_minor=collected,
            jobs=jobs,
            completed=completed,
            cancelled=cancelled,
        )
        for day, booked, collected, jobs, completed, cancelled, _currency in rows
    ]
    booking_count = sum(int(row[3]) for row in rows)
    booked_total = sum(int(row[1]) for row in rows)
    collected_total = sum(int(row[2]) for row in rows)
    completed_total = sum(int(row[4]) for row in rows)
    report_currency = next((str(row[6]) for row in rows if row[6]), "AED")
    summary = ReportSummary(
        start_date=start_date,
        end_date=end_date,
        bookings=booking_count,
        completed_washes=completed_total,
        booked_sales_minor=booked_total,
        collected_revenue_minor=collected_total,
        outstanding_minor=max(0, booked_total - collected_total),
        average_booking_value_minor=(booked_total // booking_count if booking_count else 0),
        currency_code=report_currency,
    )
    attendance = (
        select(
            AttendanceSession.staff_profile_id.label("staff_id"),
            (
                func.coalesce(
                    func.sum(
                        func.extract(
                            "epoch",
                            func.coalesce(AttendanceSession.clock_out_at, datetime.now(UTC))
                            - AttendanceSession.clock_in_at,
                        )
                    ),
                    0,
                )
                / 3600.0
            ).label("hours"),
        )
        .where(
            AttendanceSession.business_id == context.business_id,
            AttendanceSession.clock_in_at >= start,
            AttendanceSession.clock_in_at < end,
        )
        .group_by(AttendanceSession.staff_profile_id)
        .subquery()
    )
    job_stats = (
        select(
            Job.assigned_staff_id.label("staff_id"),
            func.count(Job.id).filter(Job.status == JobStatus.COMPLETED).label("completed"),
            func.coalesce(
                func.avg(func.extract("epoch", Job.completed_at - Job.started_at) / 60.0).filter(
                    Job.status == JobStatus.COMPLETED
                ),
                0,
            ).label("average_minutes"),
            func.coalesce(func.sum(Booking.total_amount_minor), 0).label("handled"),
        )
        .join(Booking, Booking.id == Job.booking_id)
        .where(
            Job.business_id == context.business_id,
            Job.scheduled_start >= start,
            Job.scheduled_start < end,
            Job.assigned_staff_id.is_not(None),
        )
        .group_by(Job.assigned_staff_id)
        .subquery()
    )
    performance_rows = (
        await session.execute(
            select(
                StaffProfile.id,
                StaffProfile.display_name,
                func.coalesce(attendance.c.hours, 0),
                func.coalesce(job_stats.c.completed, 0),
                func.coalesce(job_stats.c.average_minutes, 0),
                func.coalesce(job_stats.c.handled, 0),
            )
            .outerjoin(attendance, attendance.c.staff_id == StaffProfile.id)
            .outerjoin(job_stats, job_stats.c.staff_id == StaffProfile.id)
            .where(
                StaffProfile.business_id == context.business_id,
                StaffProfile.is_active.is_(True),
            )
            .order_by(StaffProfile.display_name)
        )
    ).all()
    late_rows = (
        await session.execute(
            select(
                AttendanceSession.staff_profile_id,
                AttendanceSession.clock_in_at,
                StaffShiftAssignment.work_date,
                Shift.start_time,
                BusinessSettings.attendance_grace_minutes,
            )
            .join(
                StaffShiftAssignment,
                (StaffShiftAssignment.staff_profile_id == AttendanceSession.staff_profile_id)
                & (
                    StaffShiftAssignment.work_date
                    == func.date(func.timezone(context.timezone, AttendanceSession.clock_in_at))
                ),
            )
            .join(Shift, Shift.id == StaffShiftAssignment.shift_id)
            .join(
                BusinessSettings,
                BusinessSettings.business_id == AttendanceSession.business_id,
            )
            .where(
                AttendanceSession.business_id == context.business_id,
                AttendanceSession.clock_in_at >= start,
                AttendanceSession.clock_in_at < end,
            )
        )
    ).all()
    late_by_staff: dict[uuid.UUID, int] = {}
    for staff_id, clock_in_at, work_date, shift_start, grace_minutes in late_rows:
        if attendance_late_minutes(
            clock_in_at, work_date, shift_start, context.timezone, grace_minutes
        ):
            late_by_staff[staff_id] = late_by_staff.get(staff_id, 0) + 1

    performance = []
    for staff_id, name, hours, completed, average_minutes, handled in performance_rows:
        worked = float(hours)
        performance.append(
            PerformanceRow(
                id=staff_id,
                name=name,
                hours_worked=round(worked, 2),
                late_arrivals=late_by_staff.get(staff_id, 0),
                jobs_completed=completed,
                average_wash_minutes=int(average_minutes),
                jobs_per_worked_hour=round(completed / worked, 2) if worked else 0,
                job_value_handled_minor=handled,
            )
        )
    service_rows = (
        await session.execute(
            select(
                BookingService.service_id,
                BookingService.service_name,
                func.count(BookingService.id),
                func.coalesce(func.sum(BookingService.line_total_minor), 0),
            )
            .join(Booking, Booking.id == BookingService.booking_id)
            .where(
                Booking.business_id == context.business_id,
                Booking.scheduled_start >= start,
                Booking.scheduled_start < end,
                Booking.status != BookingStatus.CANCELLED,
            )
            .group_by(BookingService.service_id, BookingService.service_name)
            .order_by(func.count(BookingService.id).desc())
        )
    ).all()
    service_total = sum(int(count) for _key, _label, count, _amount in service_rows)
    service_mix = [
        MixRow(
            key=str(key),
            label=label,
            count=count,
            amount_minor=amount,
            percentage=round(count * 100 / service_total, 1) if service_total else 0,
        )
        for key, label, count, amount in service_rows
    ]

    payment_rows = (
        await session.execute(
            select(
                Payment.method,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount_minor), 0),
            )
            .join(Booking, Booking.id == Payment.booking_id)
            .where(
                Booking.business_id == context.business_id,
                Booking.scheduled_start >= start,
                Booking.scheduled_start < end,
                Payment.status == PaymentStatus.PAID,
                Payment.method.is_not(None),
            )
            .group_by(Payment.method)
            .order_by(func.sum(Payment.amount_minor).desc())
        )
    ).all()
    payment_total = sum(int(amount) for _method, _count, amount in payment_rows)
    payment_mix = [
        MixRow(
            key=method,
            label=method.replace("_", " ").title(),
            count=count,
            amount_minor=amount,
            percentage=round(amount * 100 / payment_total, 1) if payment_total else 0,
        )
        for method, count, amount in payment_rows
        if method is not None
    ]

    active_day = func.date(func.timezone(context.timezone, Job.scheduled_start))
    team_rows = (
        await session.execute(
            select(
                ScheduleResource.id,
                ScheduleResource.name,
                func.count(Job.id).filter(Job.status == JobStatus.COMPLETED),
                func.coalesce(
                    func.avg(
                        func.extract("epoch", Job.completed_at - Job.started_at) / 60.0
                    ).filter(Job.status == JobStatus.COMPLETED),
                    0,
                ),
                func.coalesce(
                    func.avg(
                        func.extract("epoch", Job.completed_at - Job.scheduled_start) / 60.0
                    ).filter(Job.status == JobStatus.COMPLETED),
                    0,
                ),
                func.coalesce(
                    func.sum(Booking.total_amount_minor).filter(Job.status == JobStatus.COMPLETED),
                    0,
                ),
                func.count(distinct(active_day)),
            )
            .join(Job, Job.assigned_resource_id == ScheduleResource.id)
            .join(Booking, Booking.id == Job.booking_id)
            .where(
                ScheduleResource.business_id == context.business_id,
                Job.scheduled_start >= start,
                Job.scheduled_start < end,
            )
            .group_by(ScheduleResource.id, ScheduleResource.name)
            .order_by(func.count(Job.id).filter(Job.status == JobStatus.COMPLETED).desc())
        )
    ).all()
    team_performance = [
        TeamPerformanceRow(
            id=team_id,
            name=name,
            completed_jobs=completed,
            average_wash_minutes=int(average_wash),
            average_operational_minutes=int(average_operational),
            job_value_handled_minor=handled,
            jobs_per_active_day=round(completed / active_days, 2) if active_days else 0,
        )
        for (
            team_id,
            name,
            completed,
            average_wash,
            average_operational,
            handled,
            active_days,
        ) in team_rows
    ]
    finance = await finance_overview(session, context, start_date, end_date)
    return ReportV2(
        summary=summary,
        series=series,
        staff_performance=performance,
        service_mix=service_mix,
        payment_mix=payment_mix,
        team_performance=team_performance,
        finance=finance,
    )
