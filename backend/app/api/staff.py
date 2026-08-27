import asyncio
import uuid
from datetime import date, datetime
from typing import Annotated, cast
from zoneinfo import ZoneInfo

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
from app.integrations.supabase_storage import SupabaseStorageAdminClient
from app.models.entities import Booking, Job, JobPhoto
from app.schemas.customer import ManagerRescheduleCreate
from app.schemas.staff import (
    AssignmentAction,
    AttendanceAction,
    AttendanceList,
    AttendanceOverviewItem,
    AttendanceRecord,
    CancellationItem,
    CancellationReview,
    JobAction,
    JobChecklistUpdate,
    JobComplaintCreate,
    JobComplaintReview,
    JobInspectionInput,
    JobPhotoCreate,
    JobPhotoUploadGrant,
    JobPhotoView,
    JobQualityIssueCreate,
    JobQualityView,
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
    StaffPasswordReset,
    StaffPasswordResetResult,
    StaffProfileView,
    StartTripAction,
    SyncState,
    TeamCreate,
    TeamDetail,
    TeamMembersUpdate,
    TeamSummary,
    TeamUpdate,
    TemporaryPasswordUpdate,
)
from app.services.customers import reschedule_managed_booking
from app.services.job_quality import (
    add_issue,
    confirm_photo,
    create_complaint,
    get_job_quality,
    load_pending_photo,
    prepare_photo_upload,
    review_complaint,
    save_inspection,
    update_checklist,
)
from app.services.staff_accounts import (
    create_staff_account,
    get_own_profile,
    list_staff_accounts,
    reset_staff_password,
    reset_staff_password_choice,
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
from app.services.sync_state import bump_sync_revisions, get_sync_state
from app.services.workforce import (
    assign_shift,
    attendance_overview,
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


def _photo_storage(request: Request) -> SupabaseStorageAdminClient:
    settings = get_settings()
    return SupabaseStorageAdminClient(
        cast(httpx.AsyncClient, request.app.state.http_client),
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.job_photo_bucket,
    )


@router.get("/context")
async def context(
    value: Annotated[StaffContext, Depends(staff_context)],
) -> dict[str, str | bool | None]:
    return {
        "staff_id": str(value.staff_id),
        "business_id": str(value.business_id),
        "business_name": value.business_name,
        "role": value.role,
        "timezone": value.timezone,
        "display_name": value.display_name,
        "username": value.username,
        "phone": value.phone,
        "must_change_password": value.must_change_password,
    }


@router.get("/sync-state", response_model=SyncState)
async def sync_state(session: SessionDep, context: StaffDep) -> SyncState:
    return await get_sync_state(session, context.business_id)


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
    return await create_staff_account(session, context, payload, _admin(request))


@router.patch("/users/{staff_id}", response_model=StaffProfileView)
async def staff_user_update(
    staff_id: uuid.UUID,
    payload: StaffAccountUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> StaffProfileView:
    async with session.begin():
        result = await update_staff_account(session, context, staff_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/users/{staff_id}/temporary-password", status_code=204)
async def staff_user_password(
    staff_id: uuid.UUID,
    payload: TemporaryPasswordUpdate,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    await reset_staff_password(
        session, context, staff_id, payload.temporary_password, _admin(request)
    )


@router.post("/users/{staff_id}/password", response_model=StaffPasswordResetResult)
async def staff_user_password_reset(
    staff_id: uuid.UUID,
    payload: StaffPasswordReset,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> StaffPasswordResetResult:
    return await reset_staff_password_choice(
        session,
        context,
        staff_id,
        mode=payload.mode,
        new_password=payload.new_password,
        admin=_admin(request),
    )


@router.get("/teams", response_model=list[TeamSummary])
async def teams(session: SessionDep, context: StaffDep) -> list[TeamSummary]:
    return await list_teams(session, context)


@router.post("/teams", response_model=TeamDetail, status_code=201)
async def team_create(
    payload: TeamCreate, session: SessionDep, context: ManagerContext
) -> TeamDetail:
    async with session.begin():
        result = await create_team(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce", "schedule")
        return result


@router.get("/teams/{team_id}", response_model=TeamDetail)
async def team_get(team_id: uuid.UUID, session: SessionDep, context: StaffDep) -> TeamDetail:
    return await get_team(session, context, team_id)


@router.patch("/teams/{team_id}", response_model=TeamDetail)
async def team_update(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        result = await update_team(session, context, team_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce", "schedule")
        return result


@router.put("/teams/{team_id}/members", response_model=TeamDetail)
async def team_members(
    team_id: uuid.UUID,
    payload: TeamMembersUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        result = await replace_team_members(session, context, team_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


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


@router.get("/attendance/overview", response_model=list[AttendanceOverviewItem])
async def attendance_status_overview(
    session: SessionDep,
    context: StaffDep,
    day: date | None = None,
) -> list[AttendanceOverviewItem]:
    target = day or datetime.now(ZoneInfo(context.timezone)).date()
    return await attendance_overview(session, context, day=target)


@router.post("/attendance/clock-in", response_model=AttendanceRecord)
async def attendance_clock_in(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        result = await clock_in(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/attendance/clock-out", response_model=AttendanceRecord)
async def attendance_clock_out(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        result = await clock_out(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/shifts", response_model=list[ShiftView])
async def shifts(session: SessionDep, context: StaffDep) -> list[ShiftView]:
    return await list_shifts(session, context)


@router.post("/shifts", response_model=ShiftView, status_code=201)
async def shift_create(
    payload: ShiftCreate, session: SessionDep, context: ManagerContext
) -> ShiftView:
    async with session.begin():
        result = await create_shift(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/shift-assignments", response_model=list[ShiftAssignmentView])
async def shift_assignments(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: StaffDep,
) -> list[ShiftAssignmentView]:
    return await list_shift_assignments(session, context, start_date=start_date, end_date=end_date)


@router.put("/shift-assignments", response_model=ShiftAssignmentView)
async def shift_assignment(
    payload: ShiftAssignmentCreate,
    session: SessionDep,
    context: ManagerContext,
) -> ShiftAssignmentView:
    async with session.begin():
        result = await assign_shift(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/leave", response_model=list[LeaveView])
async def leave(
    session: SessionDep, context: StaffDep, status: str | None = None
) -> list[LeaveView]:
    return await list_leave(session, context, status=status)


@router.post("/leave", response_model=LeaveView, status_code=201)
async def leave_create(payload: LeaveCreate, session: SessionDep, context: StaffDep) -> LeaveView:
    async with session.begin():
        result = await create_leave(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/leave/{leave_id}/review", response_model=LeaveView)
async def leave_review(
    leave_id: uuid.UUID,
    payload: LeaveReview,
    session: SessionDep,
    context: ManagerContext,
) -> LeaveView:
    async with session.begin():
        result = await review_leave(session, context, leave_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/dashboard", response_model=OperationsDashboard)
async def dashboard(
    session: SessionDep,
    context: ManagerContext,
    day: date | None = None,
) -> OperationsDashboard:
    target = day or datetime.now(ZoneInfo(context.timezone)).date()
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
    start_date: date | None = None,
    end_date: date | None = None,
    view: Annotated[str | None, Query(pattern="^(today|upcoming|history|unassigned|all)$")] = None,
    status: str | None = None,
    scope: Annotated[str, Query(pattern="^(my|all)$")] = "my",
    team_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    service_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=160),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> StaffJobList:
    return await list_jobs(
        session,
        context,
        day=day,
        start_date=start_date,
        end_date=end_date,
        view=view,
        status=status,
        scope=scope,
        team_id=team_id,
        staff_id=employee_id,
        payment_method=payment_method,
        service_id=service_id,
        search=search,
        offset=offset,
        limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=StaffJob)
async def job_detail(
    job_id: uuid.UUID, session: SessionDep, context: Annotated[StaffContext, Depends(staff_context)]
) -> StaffJob:
    return await get_job(session, context, job_id)


@router.get("/jobs/{job_id}/quality", response_model=JobQualityView)
async def job_quality_detail(
    job_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> JobQualityView:
    async with session.begin():
        result = await get_job_quality(session, context, job_id)
        path_rows = (
            await session.execute(
                select(JobPhoto.id, JobPhoto.storage_path).where(
                    JobPhoto.id.in_([photo.id for photo in result.photos]),
                    JobPhoto.business_id == context.business_id,
                )
            )
        ).all()
        photo_paths: dict[uuid.UUID, str] = {row[0]: row[1] for row in path_rows}
    if not photo_paths:
        return result
    settings = get_settings()
    storage = _photo_storage(request)

    async def signed_access(photo_id: uuid.UUID, path: str) -> tuple[uuid.UUID, str | None]:
        try:
            return (
                photo_id,
                await storage.create_signed_download(path, settings.job_photo_signed_url_seconds),
            )
        except (DomainError, httpx.HTTPError):
            logger.warning("job_photo_access_grant_failed", photo_id=str(photo_id))
            return photo_id, None

    signed = await asyncio.gather(
        *(signed_access(photo_id, path) for photo_id, path in photo_paths.items())
    )
    access_urls = dict(signed)
    return result.model_copy(
        update={
            "photos": [
                photo.model_copy(update={"access_url": access_urls.get(photo.id)})
                for photo in result.photos
            ]
        }
    )


@router.put("/jobs/{job_id}/quality/inspection", status_code=204)
async def job_quality_inspection(
    job_id: uuid.UUID,
    payload: JobInspectionInput,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await save_inspection(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.put("/jobs/{job_id}/quality/checklist", status_code=204)
async def job_quality_checklist(
    job_id: uuid.UUID,
    payload: JobChecklistUpdate,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await update_checklist(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post("/jobs/{job_id}/quality/issues", status_code=201)
async def job_quality_issue(
    job_id: uuid.UUID,
    payload: JobQualityIssueCreate,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await add_issue(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post(
    "/jobs/{job_id}/quality/photos/upload",
    response_model=JobPhotoUploadGrant,
    status_code=201,
)
async def job_quality_photo_upload(
    job_id: uuid.UUID,
    payload: JobPhotoCreate,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> JobPhotoUploadGrant:
    async with session.begin():
        photo = await prepare_photo_upload(session, context, job_id, payload)
    settings = get_settings()
    token = await _photo_storage(request).create_signed_upload(photo.storage_path)
    return JobPhotoUploadGrant(
        photo=JobPhotoView(
            id=photo.id,
            category=photo.category,
            caption=photo.caption,
            status=photo.status,
            created_by_staff_id=photo.created_by_staff_id,
            created_by_staff_name=context.display_name,
            created_at=photo.created_at,
        ),
        bucket=settings.job_photo_bucket,
        path=photo.storage_path,
        upload_token=token,
        max_bytes=settings.job_photo_max_bytes,
    )


@router.post("/jobs/{job_id}/quality/photos/{photo_id}/complete", status_code=204)
async def job_quality_photo_complete(
    job_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> None:
    photo = await load_pending_photo(session, context, job_id, photo_id)
    photo_path = photo.storage_path
    await session.rollback()
    storage = _photo_storage(request)
    object_info = await storage.object_info(photo_path)
    async with session.begin():
        await confirm_photo(
            session,
            context,
            job_id,
            photo_id,
            object_info=object_info,
            max_bytes=get_settings().job_photo_max_bytes,
        )
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post("/jobs/{job_id}/quality/complaints", status_code=201)
async def job_quality_complaint(
    job_id: uuid.UUID,
    payload: JobComplaintCreate,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    async with session.begin():
        await create_complaint(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post("/jobs/{job_id}/quality/complaints/{complaint_id}/review", status_code=204)
async def job_quality_complaint_review(
    job_id: uuid.UUID,
    complaint_id: uuid.UUID,
    payload: JobComplaintReview,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    async with session.begin():
        await review_complaint(session, context, job_id, complaint_id, payload)
        domains = (
            ("jobs", "schedule", "finance") if payload.decision == "approve_rewash" else ("jobs",)
        )
        await bump_sync_revisions(session, context.business_id, *domains)


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
    if (
        provider
        and payload.origin is not None
        and snapshot.latitude is not None
        and snapshot.longitude is not None
    ):
        try:
            eta = await provider.estimate(
                origin=(payload.origin.latitude, payload.origin.longitude),
                destination=(snapshot.latitude, snapshot.longitude),
            )
        except Exception:
            logger.warning("eta_provider_failed", job_id=str(job_id))
    async with session.begin():
        result = await start_trip(session, context, job_id, payload, eta)
        await bump_sync_revisions(session, context.business_id, "jobs")
        return result


@router.post("/jobs/{job_id}/start", response_model=StaffJob)
async def job_start(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.IN_PROGRESS)
        await bump_sync_revisions(session, context.business_id, "jobs")
        return result


@router.post("/jobs/{job_id}/arrive", response_model=StaffJob)
async def job_arrive(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.ARRIVED)
        await bump_sync_revisions(session, context.business_id, "jobs")
        return result


@router.post("/jobs/{job_id}/complete", response_model=StaffJob)
async def job_complete(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.COMPLETED)
        await bump_sync_revisions(session, context.business_id, "jobs")
        return result


@router.post("/jobs/{job_id}/cash-payment", response_model=StaffJob)
async def job_cash(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await record_cash(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "finance")
        return result


@router.patch("/jobs/{job_id}/assignment", response_model=StaffJob)
async def job_assignment(
    job_id: uuid.UUID, payload: AssignmentAction, session: SessionDep, context: ManagerContext
) -> StaffJob:
    async with session.begin():
        result = await assign_job(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule")
        return result


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
        result = await review_cancellation(session, context, cancellation_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule")
        return result


@router.post("/bookings/{booking_id}/reschedule", response_model=StaffJob)
async def manager_reschedule(
    booking_id: uuid.UUID,
    payload: ManagerRescheduleCreate,
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
        await reschedule_managed_booking(
            session,
            booking,
            payload,
            actor_staff_id=context.staff_id,
            confirm_active_reschedule=payload.confirm_active_reschedule,
        )
        job = (await session.scalars(select(Job).where(Job.booking_id == booking.id))).one()
        await session.flush()
        result = await get_job(session, context, job.id)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule")
        return result
