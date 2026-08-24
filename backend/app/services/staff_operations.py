import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import case, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import (
    BookingStatus,
    CancellationStatus,
    JobStatus,
    PaymentStatus,
    SlotStatus,
    StaffRole,
)
from app.domain.errors import ConflictError, DomainError
from app.domain.scheduling import SlotWindow
from app.domain.state_machines import JOB_TRANSITIONS, validate_transition
from app.integrations.eta import EtaResult
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    CancellationRequest,
    Job,
    JobEvent,
    NotificationOutbox,
    Payment,
    PaymentTransaction,
    ScheduleResource,
    ScheduleSlot,
    StaffProfile,
    TeamMembership,
)
from app.schemas.staff import (
    AssignmentAction,
    CancellationItem,
    CancellationReview,
    JobAction,
    JobTimelineEvent,
    ReportSummary,
    StaffJob,
    StaffJobList,
    StaffMember,
    StaffVehicle,
    StartTripAction,
)
from app.services.scheduling import _lock_slot_sequence

logger = structlog.get_logger()


def _can_manage(context: StaffContext) -> bool:
    return context.role in {StaffRole.MANAGER, StaffRole.ADMIN}


async def _job_rows(
    session: AsyncSession,
    context: StaffContext,
    *,
    job_id: uuid.UUID | None = None,
    day: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    view: str | None = None,
    scope: str = "my",
    status: str | None = None,
    team_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    service_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
    lock: bool = False,
) -> Any:
    statement = (
        select(Job, Booking, Payment, StaffProfile.display_name)
        .join(Booking, Booking.id == Job.booking_id)
        .join(Payment, Payment.booking_id == Booking.id)
        .outerjoin(StaffProfile, StaffProfile.id == Job.assigned_staff_id)
        .where(Job.business_id == context.business_id)
    )
    if job_id:
        statement = statement.where(Job.id == job_id)
    if not _can_manage(context) or scope != "all":
        team_job = exists(
            select(TeamMembership.id).where(
                TeamMembership.resource_id == Job.assigned_resource_id,
                TeamMembership.staff_profile_id == context.staff_id,
                TeamMembership.is_active.is_(True),
            )
        )
        statement = statement.where(or_(Job.assigned_staff_id == context.staff_id, team_job))
    if day:
        zone = ZoneInfo(context.timezone)
        start = datetime.combine(day, time.min, zone).astimezone(UTC)
        end = start + timedelta(days=1)
        statement = statement.where(Job.scheduled_start >= start, Job.scheduled_start < end)
    elif start_date or end_date:
        zone = ZoneInfo(context.timezone)
        if start_date:
            start = datetime.combine(start_date, time.min, zone).astimezone(UTC)
            statement = statement.where(Job.scheduled_start >= start)
        if end_date:
            end = datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(UTC)
            statement = statement.where(Job.scheduled_start < end)
    if view == "upcoming":
        statement = statement.where(
            Job.scheduled_start >= datetime.now(UTC),
            Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
        )
    elif view == "history":
        statement = statement.where(Job.status.in_([JobStatus.COMPLETED, JobStatus.CANCELLED]))
    elif view == "unassigned":
        statement = statement.where(Job.status == JobStatus.UNASSIGNED)
    if status:
        statement = statement.where(Job.status == status)
    if team_id:
        statement = statement.where(Job.assigned_resource_id == team_id)
    if staff_id:
        statement = statement.where(Job.assigned_staff_id == staff_id)
    if payment_method:
        statement = statement.where(Payment.method == payment_method)
    if service_id:
        statement = statement.where(
            exists(
                select(BookingService.id).where(
                    BookingService.booking_id == Booking.id,
                    BookingService.service_id == service_id,
                )
            )
        )
    ordering = Job.scheduled_start.desc() if view == "history" else Job.scheduled_start
    statement = statement.order_by(ordering).offset(offset).limit(limit)
    if lock:
        statement = statement.with_for_update(of=Job)
    return (await session.execute(statement)).all()


_EVENT_LABELS = {
    "job_assigned": "Assigned",
    "job_reassigned": "Assignment changed",
    "trip_started": "Trip started",
    "job_started": "Wash started",
    "job_completed": "Wash completed",
    "cash_payment_recorded": "Cash payment recorded",
    "booking_rescheduled_by_staff": "Appointment rescheduled",
}


async def _serialize_jobs(
    session: AsyncSession, rows: Any, *, include_timeline: bool = False
) -> list[StaffJob]:
    booking_ids = [booking.id for _job, booking, _payment, _name in rows]
    resource_ids = {
        job.assigned_resource_id
        for job, _booking, _payment, _name in rows
        if job.assigned_resource_id is not None
    }
    team_names: dict[uuid.UUID, str] = {}
    if resource_ids:
        team_rows = (
            await session.execute(
                select(ScheduleResource.id, ScheduleResource.name).where(
                    ScheduleResource.id.in_(resource_ids)
                )
            )
        ).all()
        team_names = {team_id: team_name for team_id, team_name in team_rows}
    vehicle_rows = (
        (
            await session.execute(
                select(BookingVehicle, BookingService)
                .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
                .where(BookingVehicle.booking_id.in_(booking_ids))
                .order_by(BookingVehicle.position)
            )
        ).all()
        if booking_ids
        else []
    )
    by_booking: dict[uuid.UUID, list[StaffVehicle]] = {}
    for vehicle, service in vehicle_rows:
        by_booking.setdefault(vehicle.booking_id, []).append(
            StaffVehicle(
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                vehicle_type=vehicle.vehicle_type,
                colour=vehicle.colour,
                plate_number=vehicle.plate_number,
                notes=vehicle.notes,
                service_name=service.service_name,
                amount_minor=service.line_total_minor,
            )
        )
    timeline_by_job: dict[uuid.UUID, list[JobTimelineEvent]] = {}
    if include_timeline and rows:
        job_ids = [job.id for job, _booking, _payment, _name in rows]
        event_rows = (
            await session.execute(
                select(JobEvent, StaffProfile.display_name)
                .outerjoin(StaffProfile, StaffProfile.id == JobEvent.actor_staff_id)
                .where(JobEvent.job_id.in_(job_ids))
                .order_by(JobEvent.server_timestamp.desc())
                .limit(500)
            )
        ).all()
        for event, actor in event_rows:
            amount = event.metadata_json.get("amount_minor")
            detail = f"Amount recorded: {int(amount) / 100:.2f}" if amount is not None else None
            timeline_by_job.setdefault(event.job_id, []).append(
                JobTimelineEvent(
                    id=event.id,
                    occurred_at=event.server_timestamp,
                    event=_EVENT_LABELS.get(
                        event.event_type, event.event_type.replace("_", " ").title()
                    ),
                    actor=actor,
                    detail=detail,
                )
            )
    return [
        StaffJob(
            id=job.id,
            booking_id=booking.id,
            booking_reference=booking.reference,
            assigned_staff_id=job.assigned_staff_id,
            assigned_staff_name=name,
            assigned_team_id=job.assigned_resource_id,
            assigned_team_name=team_names.get(job.assigned_resource_id),
            status=job.status,
            scheduled_start=job.scheduled_start,
            scheduled_end=job.scheduled_end,
            en_route_at=job.en_route_at,
            estimated_arrival_at=job.estimated_arrival_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            customer_name=f"{booking.customer_first_name} {booking.customer_surname}",
            customer_phone=booking.customer_phone,
            written_address=booking.written_address,
            location_url=booking.location_url,
            latitude=float(booking.latitude) if booking.latitude is not None else None,
            longitude=float(booking.longitude) if booking.longitude is not None else None,
            location_instructions=booking.location_instructions,
            payment_status=payment.status,
            payment_method=payment.method,
            total_amount_minor=booking.total_amount_minor,
            currency_code=booking.currency_code,
            vehicles=by_booking.get(booking.id, []),
            timeline=timeline_by_job.get(job.id, []),
        )
        for job, booking, payment, name in rows
    ]


async def list_jobs(session: AsyncSession, context: StaffContext, **filters: Any) -> StaffJobList:
    limit = min(int(filters.pop("limit", 50)), 100)
    offset = int(filters.pop("offset", 0))
    rows = await _job_rows(session, context, offset=offset, limit=limit + 1, **filters)
    more = len(rows) > limit
    return StaffJobList(
        jobs=await _serialize_jobs(session, rows[:limit]),
        next_offset=offset + limit if more else None,
    )


async def get_job(session: AsyncSession, context: StaffContext, job_id: uuid.UUID) -> StaffJob:
    rows = await _job_rows(
        session, context, job_id=job_id, scope="all" if _can_manage(context) else "my", limit=1
    )
    if not rows:
        raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    return (await _serialize_jobs(session, rows, include_timeline=True))[0]


async def _locked_job(session: AsyncSession, context: StaffContext, job_id: uuid.UUID) -> Any:
    rows = await _job_rows(
        session,
        context,
        job_id=job_id,
        scope="all" if _can_manage(context) else "my",
        limit=1,
        lock=True,
    )
    if not rows:
        raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    return rows[0]


async def _duplicate_event(session: AsyncSession, job_id: uuid.UUID, client_event_id: str) -> bool:
    return (
        await session.scalar(
            select(JobEvent.id).where(
                JobEvent.job_id == job_id, JobEvent.client_event_id == client_event_id
            )
        )
    ) is not None


async def start_trip(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    request: StartTripAction,
    eta: EtaResult | None,
) -> StaffJob:
    job, booking, _payment, _name = await _locked_job(session, context, job_id)
    if await _duplicate_event(session, job.id, request.client_event_id):
        return await get_job(session, context, job.id)
    validate_transition(JobStatus(job.status), JobStatus.EN_ROUTE, JOB_TRANSITIONS)
    now = datetime.now(UTC)
    job.status = JobStatus.EN_ROUTE
    job.en_route_at = now
    job.estimated_arrival_at = now + eta.duration if eta else None
    job.version += 1
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="trip_started",
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={"eta_available": eta is not None},
        )
    )
    session.add(
        NotificationOutbox(
            business_id=context.business_id,
            booking_id=booking.id,
            channel="email",
            notification_type="driver_en_route",
            recipient=booking.customer_email,
            payload={
                "booking_reference": booking.reference,
                "estimated_arrival_at": job.estimated_arrival_at.isoformat()
                if job.estimated_arrival_at
                else None,
            },
            status="pending",
            next_attempt_at=now,
        )
    )
    await session.flush()
    return await get_job(session, context, job.id)


async def transition_job(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    request: JobAction,
    target: JobStatus,
) -> StaffJob:
    job, booking, _payment, _name = await _locked_job(session, context, job_id)
    if await _duplicate_event(session, job.id, request.client_event_id):
        return await get_job(session, context, job.id)
    validate_transition(JobStatus(job.status), target, JOB_TRANSITIONS)
    now = datetime.now(UTC)
    job.status = target
    job.version += 1
    event = "job_started" if target == JobStatus.IN_PROGRESS else "job_completed"
    if target == JobStatus.IN_PROGRESS:
        job.started_at = now
    if target == JobStatus.COMPLETED:
        job.completed_at = now
        booking.status = BookingStatus.COMPLETED
        booking.version += 1
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type=event,
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={},
        )
    )
    await session.flush()
    return await get_job(session, context, job.id)


async def record_cash(
    session: AsyncSession, context: StaffContext, job_id: uuid.UUID, request: JobAction
) -> StaffJob:
    job, booking, payment, _name = await _locked_job(session, context, job_id)
    if await _duplicate_event(session, job.id, request.client_event_id):
        return await get_job(session, context, job.id)
    if payment.status == PaymentStatus.PAID:
        raise ConflictError("PAYMENT_ALREADY_PAID", "This booking is already paid.")
    now = datetime.now(UTC)
    payment.status = PaymentStatus.PAID
    payment.method = "cash"
    payment.paid_at = now
    payment.version += 1
    booking.payment_status = PaymentStatus.PAID
    booking.version += 1
    session.add(
        PaymentTransaction(
            payment_id=payment.id,
            transaction_type="cash_payment",
            status="succeeded",
            amount_minor=payment.amount_minor,
            provider_metadata={
                "actor_staff_id": str(context.staff_id),
                "client_event_id": request.client_event_id,
            },
        )
    )
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="cash_payment_recorded",
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={"amount_minor": payment.amount_minor},
        )
    )
    await session.flush()
    return await get_job(session, context, job.id)


async def assign_job(
    session: AsyncSession, context: StaffContext, job_id: uuid.UUID, request: AssignmentAction
) -> StaffJob:
    job, booking, _payment, _name = await _locked_job(session, context, job_id)
    if request.expected_version and request.expected_version != job.version:
        raise ConflictError("JOB_VERSION_CONFLICT", "The job was changed by another user.")
    if (
        job.status not in {JobStatus.UNASSIGNED, JobStatus.ASSIGNED}
        and not request.confirm_active_reassignment
    ):
        raise ConflictError(
            "ACTIVE_JOB_REASSIGNMENT_CONFIRMATION_REQUIRED",
            "Active work requires explicit confirmation.",
        )
    staff = None
    if request.staff_id is not None:
        staff = (
            await session.scalars(
                select(StaffProfile).where(
                    StaffProfile.id == request.staff_id,
                    StaffProfile.business_id == context.business_id,
                    StaffProfile.is_active.is_(True),
                )
            )
        ).one_or_none()
        if staff is None:
            raise DomainError("STAFF_NOT_FOUND", "Active staff member not found.", status_code=404)
    team = None
    if request.team_id is not None:
        team = (
            await session.scalars(
                select(ScheduleResource).where(
                    ScheduleResource.id == request.team_id,
                    ScheduleResource.business_id == context.business_id,
                    ScheduleResource.resource_type == "mobile_team",
                    ScheduleResource.is_active.is_(True),
                )
            )
        ).one_or_none()
        if team is None:
            raise DomainError("TEAM_NOT_FOUND", "Active team not found.", status_code=404)
        if team.id != job.assigned_resource_id:
            await _move_booking_capacity(session, context, job, booking, team)
    previous_staff = job.assigned_staff_id
    previous_team = job.assigned_resource_id
    if staff is not None:
        job.assigned_staff_id = staff.id
    if team is not None:
        job.assigned_resource_id = team.id
    job.status = JobStatus.ASSIGNED if job.status == JobStatus.UNASSIGNED else job.status
    job.version += 1
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type=(
                "job_assigned"
                if previous_staff is None and previous_team is None
                else "job_reassigned"
            ),
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={
                "previous_staff_id": str(previous_staff) if previous_staff else None,
                "previous_team_id": str(previous_team) if previous_team else None,
                "staff_id": str(staff.id) if staff else None,
                "team_id": str(team.id) if team else None,
            },
        )
    )
    await session.flush()
    return await get_job(session, context, job.id)


async def _move_booking_capacity(
    session: AsyncSession,
    context: StaffContext,
    job: Job,
    booking: Booking,
    team: ScheduleResource,
) -> None:
    source_slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(ScheduleSlot.booking_id == booking.id)
                .order_by(ScheduleSlot.slot_start)
                .with_for_update()
            )
        ).all()
    )
    conflict = await session.scalar(
        select(Job.id).where(
            Job.business_id == context.business_id,
            Job.assigned_resource_id == team.id,
            Job.id != job.id,
            Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
            Job.scheduled_start < job.scheduled_end,
            Job.scheduled_end > job.scheduled_start,
        )
    )
    if conflict is not None:
        raise ConflictError(
            "TEAM_ASSIGNMENT_CONFLICT",
            f"{team.name} already has another job during this appointment.",
        )
    if source_slots:
        windows = [SlotWindow(start=slot.slot_start, end=slot.slot_end) for slot in source_slots]
        target_slots = await _lock_slot_sequence(
            session,
            business_id=context.business_id,
            resource_id=team.id,
            windows=windows,
        )
        if target_slots is None:
            raise ConflictError(
                "TEAM_ASSIGNMENT_CONFLICT",
                f"{team.name} has unavailable scheduling capacity for this appointment.",
            )
        for slot in target_slots:
            slot.status = SlotStatus.RESERVED
            slot.booking_id = booking.id
            slot.hold_group_id = None
            slot.hold_expires_at = None
            slot.version += 1
        for slot in source_slots:
            slot.status = SlotStatus.FREE
            slot.booking_id = None
            slot.hold_group_id = None
            slot.hold_expires_at = None
            slot.version += 1
    booking.resource_id = team.id


async def list_team(session: AsyncSession, context: StaffContext) -> list[StaffMember]:
    today = datetime.now(ZoneInfo(context.timezone)).date()
    start = datetime.combine(today, time.min, ZoneInfo(context.timezone)).astimezone(UTC)
    end = start + timedelta(days=1)
    rows = (
        await session.execute(
            select(
                StaffProfile.id,
                StaffProfile.display_name,
                StaffProfile.role,
                func.count(Job.id),
                func.max(
                    case(
                        (
                            Job.status.in_([JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS]),
                            Booking.reference,
                        )
                    )
                ),
                func.max(
                    case((Job.status.in_([JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS]), Job.status))
                ),
            )
            .outerjoin(
                Job,
                (Job.assigned_staff_id == StaffProfile.id)
                & (Job.scheduled_start >= start)
                & (Job.scheduled_start < end),
            )
            .outerjoin(Booking, Booking.id == Job.booking_id)
            .where(
                StaffProfile.business_id == context.business_id, StaffProfile.is_active.is_(True)
            )
            .group_by(StaffProfile.id)
        )
    ).all()
    return [
        StaffMember(
            id=id,
            display_name=name,
            role=role,
            assigned_jobs_today=count,
            current_job_reference=reference,
            current_job_status=status,
        )
        for id, name, role, count, reference, status in rows
    ]


async def report_summary(
    session: AsyncSession, context: StaffContext, start_date: date, end_date: date
) -> ReportSummary:
    zone = ZoneInfo(context.timezone)
    start = datetime.combine(start_date, time.min, zone).astimezone(UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(UTC)
    row = (
        await session.execute(
            select(
                func.count(Booking.id),
                func.count(Booking.id).filter(Booking.status == BookingStatus.COMPLETED),
                func.coalesce(func.sum(Booking.total_amount_minor), 0),
                func.coalesce(
                    func.sum(
                        case((Payment.status == PaymentStatus.PAID, Payment.amount_minor), else_=0)
                    ),
                    0,
                ),
                func.coalesce(func.avg(Booking.total_amount_minor), 0),
                func.max(Booking.currency_code),
            )
            .join(Payment, Payment.booking_id == Booking.id)
            .where(
                Booking.business_id == context.business_id,
                Booking.scheduled_start >= start,
                Booking.scheduled_start < end,
            )
        )
    ).one()
    bookings, completed, booked, collected, average, currency = row
    return ReportSummary(
        start_date=start_date,
        end_date=end_date,
        bookings=bookings,
        completed_washes=completed,
        booked_sales_minor=booked,
        collected_revenue_minor=collected,
        outstanding_minor=max(0, booked - collected),
        average_booking_value_minor=int(average),
        currency_code=currency or "AED",
    )


async def list_cancellations(
    session: AsyncSession, context: StaffContext
) -> list[CancellationItem]:
    rows = (
        await session.execute(
            select(CancellationRequest, Booking)
            .join(Booking, Booking.id == CancellationRequest.booking_id)
            .where(
                Booking.business_id == context.business_id,
                CancellationRequest.status == CancellationStatus.REQUESTED,
            )
            .order_by(CancellationRequest.requested_at)
            .limit(100)
        )
    ).all()
    return [
        CancellationItem(
            id=item.id,
            booking_id=booking.id,
            booking_reference=booking.reference,
            customer_name=f"{booking.customer_first_name} {booking.customer_surname}",
            reason=item.reason,
            requested_at=item.requested_at,
            scheduled_start=booking.scheduled_start,
            payment_status=booking.payment_status,
            status=item.status,
        )
        for item, booking in rows
    ]


async def review_cancellation(
    session: AsyncSession,
    context: StaffContext,
    cancellation_id: uuid.UUID,
    request: CancellationReview,
) -> CancellationItem:
    row = (
        await session.execute(
            select(CancellationRequest, Booking, Job)
            .join(Booking, Booking.id == CancellationRequest.booking_id)
            .join(Job, Job.booking_id == Booking.id)
            .where(
                CancellationRequest.id == cancellation_id,
                Booking.business_id == context.business_id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if not row:
        raise DomainError(
            "CANCELLATION_NOT_FOUND", "Cancellation request not found.", status_code=404
        )
    item, booking, job = row
    if item.status != CancellationStatus.REQUESTED:
        return CancellationItem(
            id=item.id,
            booking_id=booking.id,
            booking_reference=booking.reference,
            customer_name=f"{booking.customer_first_name} {booking.customer_surname}",
            reason=item.reason,
            requested_at=item.requested_at,
            scheduled_start=booking.scheduled_start,
            payment_status=booking.payment_status,
            status=item.status,
        )
    now = datetime.now(UTC)
    item.status = request.decision
    item.reviewed_by_staff_id = context.staff_id
    item.reviewed_at = now
    item.review_note = request.review_note
    event_type = "cancellation_rejected"
    if request.decision == CancellationStatus.APPROVED:
        booking.status = BookingStatus.CANCELLED
        job.status = JobStatus.CANCELLED
        booking.version += 1
        job.version += 1
        event_type = "cancellation_approved"
        await session.execute(
            update(ScheduleSlot)
            .where(ScheduleSlot.booking_id == booking.id, ScheduleSlot.slot_start > now)
            .values(
                status=SlotStatus.FREE,
                booking_id=None,
                hold_group_id=None,
                hold_expires_at=None,
                version=ScheduleSlot.version + 1,
            )
        )
    else:
        booking.status = BookingStatus.CONFIRMED
        booking.version += 1
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type=event_type,
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={"review_note": request.review_note},
        )
    )
    await session.flush()
    return CancellationItem(
        id=item.id,
        booking_id=booking.id,
        booking_reference=booking.reference,
        customer_name=f"{booking.customer_first_name} {booking.customer_surname}",
        reason=item.reason,
        requested_at=item.requested_at,
        scheduled_start=booking.scheduled_start,
        payment_status=booking.payment_status,
        status=item.status,
    )
