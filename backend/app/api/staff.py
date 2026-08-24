import uuid
from datetime import date
from typing import Annotated, cast

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.auth.dependencies import ManagerContext, SessionDep, StaffContext, staff_context
from app.core.config import get_settings
from app.domain.enums import JobStatus
from app.domain.errors import DomainError
from app.integrations.eta import GoogleRoutesEtaProvider
from app.integrations.supabase_admin import SupabaseAdminClient
from app.models.entities import Booking, Job, JobEvent
from app.schemas.customer import CustomerRescheduleCreate
from app.schemas.staff import (
    AssignmentAction,
    AttendanceAction,
    AttendanceList,
    AttendanceRecord,
    CancellationItem,
    CancellationReview,
    JobAction,
    LeaveCreate,
    LeaveReview,
    LeaveView,
    OperationsDashboard,
    OwnProfileUpdate,
    ReportSummary,
    ReportV2,
    ShiftAssignmentCreate,
    ShiftAssignmentView,
    ShiftCreate,
    ShiftView,
    StaffAccountCreate,
    StaffAccountUpdate,
    StaffJob,
    StaffJobList,
    StaffMember,
    StaffProfileView,
    StartTripAction,
    TeamCreate,
    TeamDetail,
    TeamMembersUpdate,
    TeamSummary,
    TeamUpdate,
    TemporaryPasswordUpdate,
)
from app.services.customers import reschedule_customer_booking
from app.services.staff_accounts import (
    create_staff_account,
    get_own_profile,
    list_staff_accounts,
    reset_staff_password,
    update_own_profile,
    update_staff_account,
)
from app.services.staff_operations import (
    assign_job,
    get_job,
    list_cancellations,
    list_jobs,
    list_team,
    record_cash,
    report_summary,
    review_cancellation,
    start_trip,
    transition_job,
)
from app.services.workforce import (
    assign_shift,
    clock_in,
    clock_out,
    create_leave,
    create_shift,
    create_team,
    get_team,
    list_attendance,
    list_leave,
    list_shift_assignments,
    list_shifts,
    list_teams,
    operations_dashboard,
    replace_team_members,
    report_v2,
    review_leave,
    update_team,
)

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])
logger = structlog.get_logger()
StaffDep = Annotated[StaffContext, Depends(staff_context)]


@router.get("/context")
async def context(
    value: Annotated[StaffContext, Depends(staff_context)],
) -> dict[str, str | None]:
    return {
        "staff_id": str(value.staff_id),
        "business_id": str(value.business_id),
        "business_name": value.business_name,
        "role": value.role,
        "timezone": value.timezone,
        "display_name": value.display_name,
        "username": value.username,
        "phone": value.phone,
    }


def _admin(request: Request) -> SupabaseAdminClient:
    settings = get_settings()
    return SupabaseAdminClient(
        cast(httpx.AsyncClient, request.app.state.http_client),
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )


@router.get("/profile", response_model=StaffProfileView)
async def own_profile(session: SessionDep, context: StaffDep) -> StaffProfileView:
    return await get_own_profile(session, context)


@router.patch("/profile", response_model=StaffProfileView)
async def own_profile_update(
    payload: OwnProfileUpdate,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> StaffProfileView:
    async with session.begin():
        return await update_own_profile(
            session,
            context,
            payload,
            _admin(request) if payload.password is not None else None,
        )


@router.get("/users", response_model=list[StaffProfileView])
async def staff_users(session: SessionDep, context: ManagerContext) -> list[StaffProfileView]:
    return await list_staff_accounts(session, context)


@router.post("/users", response_model=StaffProfileView, status_code=201)
async def staff_user_create(
    payload: StaffAccountCreate,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> StaffProfileView:
    async with session.begin():
        return await create_staff_account(session, context, payload, _admin(request))


@router.patch("/users/{staff_id}", response_model=StaffProfileView)
async def staff_user_update(
    staff_id: uuid.UUID,
    payload: StaffAccountUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> StaffProfileView:
    async with session.begin():
        return await update_staff_account(session, context, staff_id, payload)


@router.post("/users/{staff_id}/temporary-password", status_code=204)
async def staff_user_password(
    staff_id: uuid.UUID,
    payload: TemporaryPasswordUpdate,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    async with session.begin():
        await reset_staff_password(
            session, context, staff_id, payload.temporary_password, _admin(request)
        )


@router.get("/teams", response_model=list[TeamSummary])
async def teams(session: SessionDep, context: StaffDep) -> list[TeamSummary]:
    return await list_teams(session, context)


@router.post("/teams", response_model=TeamDetail, status_code=201)
async def team_create(
    payload: TeamCreate, session: SessionDep, context: ManagerContext
) -> TeamDetail:
    async with session.begin():
        return await create_team(session, context, payload)


@router.get("/teams/{team_id}", response_model=TeamDetail)
async def team_get(
    team_id: uuid.UUID, session: SessionDep, context: StaffDep
) -> TeamDetail:
    return await get_team(session, context, team_id)


@router.patch("/teams/{team_id}", response_model=TeamDetail)
async def team_update(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        return await update_team(session, context, team_id, payload)


@router.put("/teams/{team_id}/members", response_model=TeamDetail)
async def team_members(
    team_id: uuid.UUID,
    payload: TeamMembersUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        return await replace_team_members(session, context, team_id, payload)


@router.get("/attendance", response_model=AttendanceList)
async def attendance(
    session: SessionDep,
    context: StaffDep,
    start_date: date,
    end_date: date,
    staff_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AttendanceList:
    return await list_attendance(
        session,
        context,
        start_date=start_date,
        end_date=end_date,
        staff_id=staff_id,
        offset=offset,
        limit=limit,
    )


@router.post("/attendance/clock-in", response_model=AttendanceRecord)
async def attendance_clock_in(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        return await clock_in(session, context, payload)


@router.post("/attendance/clock-out", response_model=AttendanceRecord)
async def attendance_clock_out(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        return await clock_out(session, context, payload)


@router.get("/shifts", response_model=list[ShiftView])
async def shifts(session: SessionDep, context: StaffDep) -> list[ShiftView]:
    return await list_shifts(session, context)


@router.post("/shifts", response_model=ShiftView, status_code=201)
async def shift_create(
    payload: ShiftCreate, session: SessionDep, context: ManagerContext
) -> ShiftView:
    async with session.begin():
        return await create_shift(session, context, payload)


@router.get("/shift-assignments", response_model=list[ShiftAssignmentView])
async def shift_assignments(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: StaffDep,
) -> list[ShiftAssignmentView]:
    return await list_shift_assignments(
        session, context, start_date=start_date, end_date=end_date
    )


@router.put("/shift-assignments", response_model=ShiftAssignmentView)
async def shift_assignment(
    payload: ShiftAssignmentCreate,
    session: SessionDep,
    context: ManagerContext,
) -> ShiftAssignmentView:
    async with session.begin():
        return await assign_shift(session, context, payload)


@router.get("/leave", response_model=list[LeaveView])
async def leave(
    session: SessionDep, context: StaffDep, status: str | None = None
) -> list[LeaveView]:
    return await list_leave(session, context, status=status)


@router.post("/leave", response_model=LeaveView, status_code=201)
async def leave_create(
    payload: LeaveCreate, session: SessionDep, context: StaffDep
) -> LeaveView:
    async with session.begin():
        return await create_leave(session, context, payload)


@router.post("/leave/{leave_id}/review", response_model=LeaveView)
async def leave_review(
    leave_id: uuid.UUID,
    payload: LeaveReview,
    session: SessionDep,
    context: ManagerContext,
) -> LeaveView:
    async with session.begin():
        return await review_leave(session, context, leave_id, payload)


@router.get("/dashboard", response_model=OperationsDashboard)
async def dashboard(
    session: SessionDep,
    context: ManagerContext,
    day: date | None = None,
) -> OperationsDashboard:
    target = day or date.today()
    return await operations_dashboard(session, context, day=target)


@router.get("/reports/v2", response_model=ReportV2)
async def reports_v2(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: ManagerContext,
) -> ReportV2:
    return await report_v2(session, context, start_date, end_date)


@router.get("/management-check")
async def management_check(value: ManagerContext) -> dict[str, str]:
    return {"status": "authorized", "role": value.role}


@router.get("/jobs", response_model=StaffJobList)
async def jobs(
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
    day: Annotated[date | None, Query(alias="date")] = None,
    status: str | None = None,
    scope: Annotated[str, Query(pattern="^(my|all)$")] = "my",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> StaffJobList:
    return await list_jobs(
        session, context, day=day, status=status, scope=scope, offset=offset, limit=limit
    )


@router.get("/jobs/{job_id}", response_model=StaffJob)
async def job_detail(
    job_id: uuid.UUID, session: SessionDep, context: Annotated[StaffContext, Depends(staff_context)]
) -> StaffJob:
    return await get_job(session, context, job_id)


@router.post("/jobs/{job_id}/start-trip", response_model=StaffJob)
async def job_start_trip(
    job_id: uuid.UUID,
    payload: StartTripAction,
    request: Request,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    settings = get_settings()
    provider = (
        GoogleRoutesEtaProvider(
            cast(httpx.AsyncClient, request.app.state.http_client), settings.google_routes_api_key
        )
        if settings.google_routes_api_key
        else None
    )
    snapshot = await get_job(session, context, job_id)
    await session.rollback()
    eta = None
    if provider and snapshot.latitude is not None and snapshot.longitude is not None:
        try:
            eta = await provider.estimate(
                origin=(payload.origin.latitude, payload.origin.longitude),
                destination=(snapshot.latitude, snapshot.longitude),
            )
        except Exception:
            logger.warning("eta_provider_failed", job_id=str(job_id))
    async with session.begin():
        return await start_trip(session, context, job_id, payload, eta)


@router.post("/jobs/{job_id}/start", response_model=StaffJob)
async def job_start(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        return await transition_job(session, context, job_id, payload, JobStatus.IN_PROGRESS)


@router.post("/jobs/{job_id}/complete", response_model=StaffJob)
async def job_complete(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        return await transition_job(session, context, job_id, payload, JobStatus.COMPLETED)


@router.post("/jobs/{job_id}/cash-payment", response_model=StaffJob)
async def job_cash(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        return await record_cash(session, context, job_id, payload)


@router.patch("/jobs/{job_id}/assignment", response_model=StaffJob)
async def job_assignment(
    job_id: uuid.UUID, payload: AssignmentAction, session: SessionDep, context: ManagerContext
) -> StaffJob:
    async with session.begin():
        return await assign_job(session, context, job_id, payload)


@router.get("/team", response_model=list[StaffMember])
async def team(session: SessionDep, context: ManagerContext) -> list[StaffMember]:
    return await list_team(session, context)


@router.get("/reports/summary", response_model=ReportSummary)
async def reports(
    start_date: date, end_date: date, session: SessionDep, context: ManagerContext
) -> ReportSummary:
    return await report_summary(session, context, start_date, end_date)


@router.get("/cancellations", response_model=list[CancellationItem])
async def cancellations(session: SessionDep, context: ManagerContext) -> list[CancellationItem]:
    return await list_cancellations(session, context)


@router.post("/cancellations/{cancellation_id}/review", response_model=CancellationItem)
async def cancellation_review(
    cancellation_id: uuid.UUID,
    payload: CancellationReview,
    session: SessionDep,
    context: ManagerContext,
) -> CancellationItem:
    async with session.begin():
        return await review_cancellation(session, context, cancellation_id, payload)


@router.post("/bookings/{booking_id}/reschedule", response_model=StaffJob)
async def manager_reschedule(
    booking_id: uuid.UUID,
    payload: CustomerRescheduleCreate,
    session: SessionDep,
    context: ManagerContext,
) -> StaffJob:
    async with session.begin():
        booking = (
            await session.scalars(
                select(Booking)
                .where(Booking.id == booking_id, Booking.business_id == context.business_id)
                .with_for_update()
            )
        ).one_or_none()
        if booking is None:
            raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
        await reschedule_customer_booking(session, booking, payload)
        job = (await session.scalars(select(Job).where(Job.booking_id == booking.id))).one()
        session.add(
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                actor_staff_id=context.staff_id,
                event_type="booking_rescheduled_by_staff",
                metadata_json={},
            )
        )
        await session.flush()
        return await get_job(session, context, job.id)
