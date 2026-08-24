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
from app.models.entities import Booking, Job, JobEvent
from app.schemas.customer import CustomerRescheduleCreate
from app.schemas.staff import (
    AssignmentAction,
    CancellationItem,
    CancellationReview,
    JobAction,
    ReportSummary,
    StaffJob,
    StaffJobList,
    StaffMember,
    StartTripAction,
)
from app.services.customers import reschedule_customer_booking
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

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])
logger = structlog.get_logger()


@router.get("/context")
async def context(value: Annotated[StaffContext, Depends(staff_context)]) -> dict[str, str]:
    return {
        "staff_id": str(value.staff_id),
        "business_id": str(value.business_id),
        "business_name": value.business_name,
        "role": value.role,
        "timezone": value.timezone,
    }


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
