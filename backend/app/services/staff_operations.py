import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import case, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.cash import authoritative_cash_change
from app.domain.enums import (
    BookingStatus,
    CancellationStatus,
    ComplaintStatus,
    JobStatus,
    OutboxStatus,
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
    BusinessSettings,
    CancellationRequest,
    Expense,
    Job,
    JobComplaint,
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
    CalendarJob,
    CancellationItem,
    CancellationReview,
    CashPaymentResult,
    CashTenderAction,
    CommunicationHistoryItem,
    JobAction,
    JobDelayNotification,
    JobDirectExpense,
    JobTimelineEvent,
    ReportSummary,
    StaffCalendar,
    StaffJob,
    StaffJobList,
    StaffMember,
    StaffVehicle,
    StartTripAction,
    TeamAssignmentOption,
)
from app.services.customer_communications import discard_unsent_appointment_reminders
from app.services.job_consumption import consumption_summaries, process_job_consumption
from app.services.loyalty import evaluate_loyalty_for_job, release_booking_rewards
from app.services.scheduling import _lock_slot_sequence
from app.services.smart_scheduling import (
    choose_team_for_booking,
    evaluate_teams_for_interval,
    lock_schedule_day,
)

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
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
    lock: bool = False,
) -> Any:
    statement = (
        select(
            Job,
            Booking,
            Payment,
            StaffProfile.display_name.label("assigned_staff_name"),
            ScheduleResource.name.label("assigned_team_name"),
        )
        .join(Booking, Booking.id == Job.booking_id)
        .join(Payment, Payment.booking_id == Booking.id)
        .outerjoin(StaffProfile, StaffProfile.id == Job.assigned_staff_id)
        .outerjoin(ScheduleResource, ScheduleResource.id == Job.assigned_resource_id)
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
        statement = statement.where(
            Job.assigned_resource_id.is_(None),
            Job.assigned_staff_id.is_(None),
            Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
        )
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
    normalized_search = " ".join(search.split()) if search else ""
    if normalized_search:
        escaped = normalized_search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                Booking.customer_first_name.ilike(pattern, escape="\\"),
                Booking.customer_surname.ilike(pattern, escape="\\"),
                func.concat_ws(" ", Booking.customer_first_name, Booking.customer_surname).ilike(
                    pattern, escape="\\"
                ),
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
    "job_arrived": "Arrived at location",
    "job_started": "Wash started",
    "job_completed": "Wash completed",
    "cash_payment_recorded": "Cash payment recorded",
    "booking_rescheduled_by_staff": "Appointment rescheduled",
    "customer_delay_notified": "Customer delay update queued",
    "inspection_completed": "Vehicle inspection completed",
    "checklist_updated": "Service checklist updated",
    "checklist_completed": "Service checklist completed",
    "before_photo_added": "Before photo added",
    "after_photo_added": "After photo added",
    "damage_photo_added": "Damage photo added",
    "issue_photo_added": "Issue photo added",
    "quality_issue_reported": "Quality issue reported",
    "complaint_opened": "Complaint opened",
    "complaint_under_review": "Complaint under review",
    "complaint_resolved": "Complaint resolved",
    "complaint_rejected": "Complaint rejected",
    "rewash_approved": "Rewash approved",
    "rewash_scheduled": "Rewash scheduled",
    "rewash_completed": "Rewash completed",
}


async def _serialize_jobs(
    session: AsyncSession,
    rows: Any,
    *,
    include_timeline: bool = False,
    context: StaffContext | None = None,
) -> list[StaffJob]:
    unpacked = [_job_row_values(row) for row in rows]
    booking_ids = [booking.id for _job, booking, _payment, _staff, _team in unpacked]
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
    consumption_by_job = {}
    direct_expenses_by_job: dict[uuid.UUID, list[JobDirectExpense]] = {}
    if include_timeline and rows:
        job_ids = [job.id for job, _booking, _payment, _staff, _team in unpacked]
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
            delay = event.metadata_json.get("delay_minutes")
            detail = (
                f"Amount recorded: {int(amount) / 100:.2f}"
                if amount is not None
                else f"Delay: {int(delay)} minutes"
                if delay is not None
                else None
            )
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
        if context is not None:
            consumption_by_job = await consumption_summaries(session, context, job_ids)
            if _can_manage(context):
                expense_rows = (
                    await session.execute(
                        select(Expense)
                        .where(
                            Expense.business_id == context.business_id,
                            Expense.related_job_id.in_(job_ids),
                            Expense.status == "active",
                        )
                        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
                    )
                ).scalars()
                for expense in expense_rows:
                    if expense.related_job_id is None:
                        continue
                    direct_expenses_by_job.setdefault(expense.related_job_id, []).append(
                        JobDirectExpense(
                            id=expense.id,
                            expense_date=expense.expense_date,
                            description=expense.description,
                            amount_minor=expense.amount_minor,
                            currency_code=expense.currency_code,
                        )
                    )
    return [
        StaffJob(
            id=job.id,
            booking_id=booking.id,
            booking_reference=booking.reference,
            assigned_staff_id=job.assigned_staff_id,
            assigned_staff_name=staff_name,
            assigned_team_id=job.assigned_resource_id,
            assigned_team_name=team_name,
            assignment_source=getattr(job, "assignment_source", None),
            assigned_at=getattr(job, "assigned_at", None),
            assigned_by_staff_id=getattr(job, "assigned_by_staff_id", None),
            expected_duration_minutes=(
                getattr(job, "expected_duration_minutes", None)
                or max(15, int((job.scheduled_end - job.scheduled_start).total_seconds() // 60))
            ),
            status=job.status,
            scheduled_start=job.scheduled_start,
            scheduled_end=job.scheduled_end,
            en_route_at=job.en_route_at,
            estimated_arrival_at=job.estimated_arrival_at,
            arrived_at=job.arrived_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            customer_name=f"{booking.customer_first_name} {booking.customer_surname}",
            customer_phone=booking.customer_phone,
            customer_email=booking.customer_email,
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
            consumption=consumption_by_job.get(job.id),
            direct_expenses=(
                direct_expenses_by_job.get(job.id, [])
                if context is not None and _can_manage(context)
                else None
            ),
            direct_expenses_total_minor=(
                sum(item.amount_minor for item in direct_expenses_by_job.get(job.id, []))
                if context is not None and _can_manage(context)
                else None
            ),
        )
        for job, booking, payment, staff_name, team_name in unpacked
    ]


def _job_row_values(row: Any) -> tuple[Any, Any, Any, str | None, str | None]:
    """Read the explicit job projection without positional-unpack fragility."""

    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return (
            mapping[Job],
            mapping[Booking],
            mapping[Payment],
            mapping["assigned_staff_name"],
            mapping["assigned_team_name"],
        )
    # Unit-test adapters historically use tuple rows. Keep that small seam while
    # production SQLAlchemy rows use the named projection above.
    return row[0], row[1], row[2], row[3], row[4] if len(row) > 4 else None


async def list_jobs(session: AsyncSession, context: StaffContext, **filters: Any) -> StaffJobList:
    limit = min(int(filters.pop("limit", 50)), 100)
    offset = int(filters.pop("offset", 0))
    rows = await _job_rows(session, context, offset=offset, limit=limit + 1, **filters)
    more = len(rows) > limit
    return StaffJobList(
        jobs=await _serialize_jobs(session, rows[:limit], context=context),
        next_offset=offset + limit if more else None,
    )


async def list_job_calendar(
    session: AsyncSession,
    context: StaffContext,
    *,
    start_date: date,
    end_date: date,
) -> StaffCalendar:
    day_count = (end_date - start_date).days + 1
    if day_count < 1 or day_count > 42:
        raise DomainError(
            "CALENDAR_RANGE_INVALID",
            "Calendar requests must cover between 1 and 42 days.",
            status_code=400,
        )
    zone = ZoneInfo(context.timezone)
    starts_at = datetime.combine(start_date, time.min, zone).astimezone(UTC)
    ends_at = datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(UTC)
    vehicle_label = (
        select(func.concat_ws(" ", BookingVehicle.make, BookingVehicle.model))
        .where(BookingVehicle.booking_id == Job.booking_id)
        .order_by(BookingVehicle.position)
        .limit(1)
        .scalar_subquery()
    )
    service_label = (
        select(BookingService.service_name)
        .join(BookingVehicle, BookingVehicle.id == BookingService.booking_vehicle_id)
        .where(BookingVehicle.booking_id == Job.booking_id)
        .order_by(BookingVehicle.position)
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(
            Job.id.label("job_id"),
            Job.scheduled_start,
            Job.scheduled_end,
            Job.status,
            Job.assigned_resource_id.label("team_id"),
            ScheduleResource.name.label("team_short_name"),
            vehicle_label.label("vehicle_label"),
            service_label.label("service_label"),
        )
        .select_from(Job)
        .outerjoin(ScheduleResource, ScheduleResource.id == Job.assigned_resource_id)
        .where(
            Job.business_id == context.business_id,
            Job.scheduled_start >= starts_at,
            Job.scheduled_start < ends_at,
            Job.status != JobStatus.CANCELLED,
        )
        .order_by(Job.scheduled_start, Job.id)
    )
    if not _can_manage(context):
        team_job = exists(
            select(TeamMembership.id).where(
                TeamMembership.resource_id == Job.assigned_resource_id,
                TeamMembership.staff_profile_id == context.staff_id,
                TeamMembership.is_active.is_(True),
            )
        )
        statement = statement.where(
            or_(Job.assigned_staff_id == context.staff_id, team_job)
        )
    rows = (await session.execute(statement)).mappings().all()
    return StaffCalendar(
        jobs=[
            CalendarJob(
                job_id=row["job_id"],
                scheduled_start=row["scheduled_start"],
                scheduled_end=row["scheduled_end"],
                local_date=row["scheduled_start"].astimezone(zone).date(),
                status=row["status"],
                team_id=row["team_id"],
                team_short_name=row["team_short_name"],
                vehicle_label=row["vehicle_label"] or "Vehicle",
                service_label=row["service_label"] or "Service",
            )
            for row in rows
        ]
    )


_COMMUNICATION_LABELS = {
    "booking_confirmed": "Booking confirmation",
    "appointment_reminder": "Appointment reminder",
    "driver_en_route": "Team en route",
    "team_arrived": "Team arrived",
    "team_delayed": "Delay update",
    "booking_rescheduled": "Appointment rescheduled",
    "cancellation_requested": "Cancellation request received",
    "booking_cancelled": "Cancellation confirmed",
    "job_completed": "Service completed",
    "payment_pending": "Payment pending",
}


async def list_job_communications(
    session: AsyncSession, context: StaffContext, job_id: uuid.UUID
) -> list[CommunicationHistoryItem]:
    if not _can_manage(context):
        raise DomainError("FORBIDDEN", "Manager access is required.", status_code=403)
    rows = (
        await session.execute(
            select(NotificationOutbox)
            .select_from(NotificationOutbox)
            .join(Job, Job.booking_id == NotificationOutbox.booking_id)
            .where(
                Job.id == job_id,
                Job.business_id == context.business_id,
                NotificationOutbox.notification_type.in_(_COMMUNICATION_LABELS),
            )
            .order_by(NotificationOutbox.created_at, NotificationOutbox.id)
            .limit(100)
        )
    ).scalars()
    result = []
    for row in rows:
        detail = None
        if row.notification_type == "team_delayed":
            minutes = row.payload.get("delay_minutes")
            detail = f"{minutes} minutes" if isinstance(minutes, int) else None
        result.append(
            CommunicationHistoryItem(
                id=row.id,
                event=_COMMUNICATION_LABELS[row.notification_type],
                state=(
                    "sent"
                    if row.status == OutboxStatus.SENT
                    else "failed"
                    if row.status == OutboxStatus.FAILED
                    else "queued"
                ),
                created_at=row.created_at,
                sent_at=row.sent_at,
                detail=detail,
            )
        )
    return result


async def notify_customer_delay(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    request: JobDelayNotification,
) -> CommunicationHistoryItem:
    if not _can_manage(context):
        raise DomainError("FORBIDDEN", "Manager access is required.", status_code=403)
    job, booking, _payment, _staff, _team = _job_row_values(
        await _locked_job(session, context, job_id)
    )
    existing = await session.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.business_id == context.business_id,
            NotificationOutbox.dedupe_key == f"job-delay:{job.id}:{request.client_event_id}",
        )
    )
    if existing is not None:
        return CommunicationHistoryItem(
            id=existing.id,
            event=_COMMUNICATION_LABELS["team_delayed"],
            state=(
                "sent"
                if existing.status == OutboxStatus.SENT
                else "failed"
                if existing.status == OutboxStatus.FAILED
                else "queued"
            ),
            created_at=existing.created_at,
            sent_at=existing.sent_at,
            detail=f"{request.delay_minutes} minutes",
        )
    if job.status not in {JobStatus.ASSIGNED, JobStatus.EN_ROUTE}:
        raise ConflictError(
            "DELAY_NOTIFICATION_NOT_AVAILABLE",
            "Delay updates are available before the team arrives.",
        )
    now = datetime.now(UTC)
    record = NotificationOutbox(
        business_id=context.business_id,
        booking_id=booking.id,
        channel="email",
        notification_type="team_delayed",
        dedupe_key=f"job-delay:{job.id}:{request.client_event_id}",
        recipient=booking.customer_email,
        payload={
            "booking_reference": booking.reference,
            "delay_minutes": request.delay_minutes,
        },
        status=OutboxStatus.PENDING,
        next_attempt_at=now,
    )
    session.add(record)
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="customer_delay_notified",
            client_event_id=request.client_event_id,
            client_timestamp=request.client_timestamp,
            metadata_json={"delay_minutes": request.delay_minutes},
        )
    )
    await session.flush()
    return CommunicationHistoryItem(
        id=record.id,
        event=_COMMUNICATION_LABELS["team_delayed"],
        state="queued",
        created_at=record.created_at,
        sent_at=None,
        detail=f"{request.delay_minutes} minutes",
    )


async def get_job(session: AsyncSession, context: StaffContext, job_id: uuid.UUID) -> StaffJob:
    rows = await _job_rows(
        session, context, job_id=job_id, scope="all" if _can_manage(context) else "my", limit=1
    )
    if not rows:
        raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    return (
        await _serialize_jobs(session, rows, include_timeline=True, context=context)
    )[0]


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
    job, booking, _payment, _staff_name, _team_name = _job_row_values(
        await _locked_job(session, context, job_id)
    )
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
            dedupe_key=f"job-en-route:{job.id}",
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
    job, booking, payment, _staff_name, _team_name = _job_row_values(
        await _locked_job(session, context, job_id)
    )
    if await _duplicate_event(session, job.id, request.client_event_id):
        return await get_job(session, context, job.id)
    if target == JobStatus.COMPLETED:
        from app.services.job_quality import ensure_completion_quality

        await ensure_completion_quality(session, job.id)
    validate_transition(JobStatus(job.status), target, JOB_TRANSITIONS)
    now = datetime.now(UTC)
    job.status = target
    job.version += 1
    event = {
        JobStatus.ARRIVED: "job_arrived",
        JobStatus.IN_PROGRESS: "job_started",
        JobStatus.COMPLETED: "job_completed",
    }[target]
    if target == JobStatus.ARRIVED:
        job.arrived_at = now
        session.add(
            NotificationOutbox(
                business_id=context.business_id,
                booking_id=booking.id,
                channel="email",
                notification_type="team_arrived",
                dedupe_key=f"job-arrived:{job.id}",
                recipient=booking.customer_email,
                payload={"booking_reference": booking.reference},
                status=OutboxStatus.PENDING,
                next_attempt_at=now,
            )
        )
    if target == JobStatus.IN_PROGRESS:
        job.started_at = now
    if target == JobStatus.COMPLETED:
        await discard_unsent_appointment_reminders(session, booking.id)
        job.completed_at = now
        booking.status = BookingStatus.COMPLETED
        booking.version += 1
        session.add(
            NotificationOutbox(
                business_id=context.business_id,
                booking_id=booking.id,
                channel="email",
                notification_type="job_completed",
                dedupe_key=f"job-completed:{job.id}",
                recipient=booking.customer_email,
                payload={"booking_reference": booking.reference},
                status="pending",
                next_attempt_at=now,
            )
        )
        if payment.status != PaymentStatus.PAID:
            session.add(
                NotificationOutbox(
                    business_id=context.business_id,
                    booking_id=booking.id,
                    channel="email",
                    notification_type="payment_pending",
                    dedupe_key=f"job-payment-pending:{job.id}",
                    recipient=booking.customer_email,
                    payload={"booking_reference": booking.reference},
                    status=OutboxStatus.PENDING,
                    next_attempt_at=now,
                )
            )
        complaint_row = (
            await session.execute(
                select(JobComplaint, Job.booking_id)
                .select_from(JobComplaint)
                .join(Job, Job.id == JobComplaint.original_job_id)
                .where(
                    JobComplaint.correction_job_id == job.id,
                    JobComplaint.business_id == context.business_id,
                    JobComplaint.status == ComplaintStatus.REWASH_APPROVED,
                )
                .with_for_update()
            )
        ).one_or_none()
        if complaint_row is not None:
            complaint, original_booking_id = complaint_row
            complaint.status = ComplaintStatus.RESOLVED
            complaint.reviewed_by_staff_id = context.staff_id
            complaint.reviewed_at = now
            session.add(
                JobEvent(
                    job_id=complaint.original_job_id,
                    booking_id=original_booking_id,
                    actor_staff_id=context.staff_id,
                    event_type="rewash_completed",
                    metadata_json={
                        "complaint_id": str(complaint.id),
                        "correction_job_id": str(job.id),
                    },
                )
            )
            session.add(
                JobEvent(
                    job_id=complaint.original_job_id,
                    booking_id=original_booking_id,
                    actor_staff_id=context.staff_id,
                    event_type="complaint_resolved",
                    metadata_json={"complaint_id": str(complaint.id)},
                )
            )
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
    if target == JobStatus.COMPLETED:
        await process_job_consumption(session, context, job)
        await evaluate_loyalty_for_job(session, business_id=context.business_id, job_id=job.id)
    return await get_job(session, context, job.id)


async def record_cash(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    request: CashTenderAction,
) -> CashPaymentResult:
    job, booking, payment, _staff_name, _team_name = _job_row_values(
        await _locked_job(session, context, job_id)
    )
    if await _duplicate_event(session, job.id, request.client_event_id):
        transaction = await session.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.payment_id == payment.id,
                PaymentTransaction.client_event_id == request.client_event_id,
            )
        )
        if transaction is None or transaction.cash_tendered_minor is None:
            raise ConflictError(
                "PAYMENT_RECEIPT_UNAVAILABLE",
                "The payment was recorded, but its cash receipt is unavailable.",
            )
        return CashPaymentResult(
            job=await get_job(session, context, job.id),
            amount_applied_minor=transaction.amount_minor,
            tendered_minor=transaction.cash_tendered_minor,
            change_minor=transaction.cash_change_minor or 0,
        )
    if payment.status == PaymentStatus.PAID:
        raise ConflictError("PAYMENT_ALREADY_PAID", "This booking is already paid.")
    if job.status != JobStatus.COMPLETED:
        raise ConflictError(
            "CASH_PAYMENT_JOB_NOT_COMPLETED",
            "Cash can be recorded only after the job is completed.",
        )
    if payment.amount_minor <= 0:
        raise ConflictError(
            "CASH_PAYMENT_NOT_REQUIRED",
            "This booking has no cash balance to settle.",
        )
    authoritative_change = authoritative_cash_change(
        due_minor=payment.amount_minor,
        tendered_minor=request.tendered_minor,
        submitted_change_minor=request.change_minor,
    )
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
            actor_staff_id=context.staff_id,
            client_event_id=request.client_event_id,
            cash_tendered_minor=request.tendered_minor,
            cash_change_minor=authoritative_change,
            provider_metadata={},
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
            metadata_json={
                "amount_minor": payment.amount_minor,
                "tendered_minor": request.tendered_minor,
                "change_minor": authoritative_change,
            },
        )
    )
    await session.flush()
    await evaluate_loyalty_for_job(session, business_id=context.business_id, job_id=job.id)
    return CashPaymentResult(
        job=await get_job(session, context, job.id),
        amount_applied_minor=payment.amount_minor,
        tendered_minor=request.tendered_minor,
        change_minor=authoritative_change,
    )


async def assign_job(
    session: AsyncSession, context: StaffContext, job_id: uuid.UUID, request: AssignmentAction
) -> StaffJob:
    job, booking, _payment, _staff_name, _team_name = _job_row_values(
        await _locked_job(session, context, job_id)
    )
    if await _duplicate_event(session, job.id, request.client_event_id):
        return await get_job(session, context, job.id)
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
    settings = await session.scalar(
        select(BusinessSettings).where(BusinessSettings.business_id == context.business_id)
    )
    if settings is None:
        raise DomainError("SETTINGS_NOT_FOUND", "Business scheduling settings were not found.")
    day = job.scheduled_start.astimezone(ZoneInfo(context.timezone)).date()
    await lock_schedule_day(session, business_id=context.business_id, day=day)
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
    if request.mode == "auto":
        decision = await choose_team_for_booking(
            session,
            business_id=context.business_id,
            day=day,
            timezone=context.timezone,
            starts_at=job.scheduled_start,
            ends_at=job.scheduled_end,
            turnaround_minutes=settings.default_team_turnaround_minutes,
            source="auto",
            exclude_job_id=job.id,
        )
        team = await session.get(ScheduleResource, decision.team.id)
    elif request.team_id is not None:
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
            raise DomainError("TEAM_NOT_AVAILABLE", "Active team not found.", status_code=404)
        await choose_team_for_booking(
            session,
            business_id=context.business_id,
            day=day,
            timezone=context.timezone,
            starts_at=job.scheduled_start,
            ends_at=job.scheduled_end,
            turnaround_minutes=settings.default_team_turnaround_minutes,
            source="manual",
            preferred_team_id=team.id,
            override_turnaround=request.override_turnaround,
            exclude_job_id=job.id,
        )
        if team.id != job.assigned_resource_id:
            await _move_booking_capacity(session, context, job, booking, team)
    previous_staff = job.assigned_staff_id
    previous_team = job.assigned_resource_id
    if staff is not None:
        job.assigned_staff_id = staff.id
    if team is not None:
        job.assigned_resource_id = team.id
    if team is not None or staff is not None:
        job.assignment_source = request.mode
        job.assigned_at = datetime.now(UTC)
        job.assigned_by_staff_id = context.staff_id if request.mode == "manual" else None
    if job.assigned_resource_id is not None or job.assigned_staff_id is not None:
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
                "assignment_source": request.mode,
                "turnaround_overridden": request.override_turnaround,
            },
        )
    )
    await session.flush()
    return await get_job(session, context, job.id)


async def assignment_options(
    session: AsyncSession, context: StaffContext, job_id: uuid.UUID
) -> list[TeamAssignmentOption]:
    rows = await _job_rows(session, context, job_id=job_id, scope="all", limit=1)
    if not rows:
        raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    job, _booking, _payment, _staff_name, _team_name = _job_row_values(
        rows[0]
    )
    settings = await session.scalar(
        select(BusinessSettings).where(BusinessSettings.business_id == context.business_id)
    )
    if settings is None:
        raise DomainError("SETTINGS_NOT_FOUND", "Business scheduling settings were not found.")
    day = job.scheduled_start.astimezone(ZoneInfo(context.timezone)).date()
    evaluations = await evaluate_teams_for_interval(
        session,
        business_id=context.business_id,
        day=day,
        timezone=context.timezone,
        starts_at=job.scheduled_start,
        ends_at=job.scheduled_end,
        turnaround_minutes=settings.default_team_turnaround_minutes,
        exclude_job_id=job.id,
    )
    return [
        TeamAssignmentOption(
            team_id=item.team.id,
            team_name=item.team.name,
            status=item.status,
            reason=item.reason,
            same_day_job_count=item.same_day_job_count,
            assigned_minutes=item.assigned_minutes,
        )
        for item in evaluations
    ]


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
            "TEAM_TIME_CONFLICT",
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
                "TEAM_NOT_AVAILABLE",
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
        await discard_unsent_appointment_reminders(session, booking.id)
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
        await release_booking_rewards(session, business_id=context.business_id, booking=booking)
        session.add(
            NotificationOutbox(
                business_id=context.business_id,
                booking_id=booking.id,
                channel="email",
                notification_type="booking_cancelled",
                dedupe_key=f"booking-cancelled:{booking.id}",
                recipient=booking.customer_email,
                payload={"booking_reference": booking.reference},
                status=OutboxStatus.PENDING,
                next_attempt_at=now,
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
