import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus, HoldStatus, JobStatus, SlotStatus
from app.domain.errors import ConflictError, DomainError
from app.domain.scheduling import SlotWindow, cancellation_allowed
from app.models.entities import (
    Booking,
    BookingService,
    BookingServiceAddon,
    BookingVehicle,
    BusinessSettings,
    CancellationRequest,
    CustomerProfile,
    Job,
    JobEvent,
    NotificationOutbox,
    ScheduleSlot,
    SlotHoldGroup,
)
from app.repositories.business import load_default_business
from app.schemas.customer import (
    CustomerBookingDetail,
    CustomerBookingListResponse,
    CustomerBookingStatus,
    CustomerBookingSummary,
    CustomerContextResponse,
    CustomerProfileResponse,
    CustomerRescheduleCreate,
    ManagerRescheduleCreate,
)
from app.schemas.public import BookingVehicleSummary
from app.services.booking_snapshots import vehicle_summaries_from_rows
from app.services.scheduling import _lock_slot_sequence, hold_token_hash, policy_for_day
from app.services.smart_scheduling import choose_team_for_booking, lock_schedule_day


@dataclass(frozen=True)
class CustomerScope:
    identity: VerifiedIdentity
    business_id: uuid.UUID
    profile: CustomerProfile | None


async def load_customer_scope(session: AsyncSession, identity: VerifiedIdentity) -> CustomerScope:
    configuration = await load_default_business(session)
    profile = (
        await session.scalars(
            select(CustomerProfile).where(
                CustomerProfile.auth_user_id == identity.user_id,
                CustomerProfile.business_id == configuration.business.id,
                CustomerProfile.is_active.is_(True),
            )
        )
    ).one_or_none()
    return CustomerScope(identity, configuration.business.id, profile)


async def customer_context(
    session: AsyncSession, identity: VerifiedIdentity
) -> CustomerContextResponse:
    scope = await load_customer_scope(session, identity)
    if scope.profile is None:
        return CustomerContextResponse(profile=None, booking_count=0)
    booking_count = (
        await session.scalar(
            select(func.count(Booking.id)).where(Booking.customer_profile_id == scope.profile.id)
        )
    ) or 0
    return CustomerContextResponse(
        profile=CustomerProfileResponse(
            id=scope.profile.id,
            first_name=scope.profile.first_name,
            surname=scope.profile.surname,
            email=scope.profile.email,
            phone=scope.profile.phone,
        ),
        booking_count=booking_count,
    )


def map_customer_status(booking_status: str, job_status: str | None) -> CustomerBookingStatus:
    if booking_status == BookingStatus.CANCELLED or job_status == JobStatus.CANCELLED:
        return CustomerBookingStatus(
            key="cancelled", label="Cancelled", stage=0, job_status=job_status
        )
    if booking_status == BookingStatus.CANCELLATION_REQUESTED:
        return CustomerBookingStatus(
            key="cancellation_requested",
            label="Cancellation requested",
            stage=0,
            job_status=job_status,
        )
    if booking_status == BookingStatus.COMPLETED or job_status == JobStatus.COMPLETED:
        return CustomerBookingStatus(
            key="completed", label="Completed", stage=5, job_status=job_status
        )
    if job_status == JobStatus.IN_PROGRESS:
        return CustomerBookingStatus(
            key="in_progress", label="Wash in progress", stage=4, job_status=job_status
        )
    if job_status == JobStatus.ARRIVED:
        return CustomerBookingStatus(
            key="arrived", label="Driver has arrived", stage=3, job_status=job_status
        )
    if job_status == JobStatus.EN_ROUTE:
        return CustomerBookingStatus(
            key="en_route", label="Driver on the way", stage=2, job_status=job_status
        )
    if job_status == JobStatus.ASSIGNED:
        return CustomerBookingStatus(
            key="assigned", label="Team assigned", stage=1, job_status=job_status
        )
    if booking_status == BookingStatus.PENDING_PAYMENT:
        return CustomerBookingStatus(
            key="pending_payment", label="Payment pending", stage=0, job_status=job_status
        )
    return CustomerBookingStatus(
        key="confirmed", label="Booking confirmed", stage=0, job_status=job_status
    )


def _action_eligibility(
    booking: Booking, settings: BusinessSettings, job_status: str | None
) -> tuple[bool, bool]:
    eligible = booking.status == BookingStatus.CONFIRMED and cancellation_allowed(
        booking.scheduled_start, settings.cancellation_cutoff_hours
    )
    reschedule = eligible and job_status not in {
        JobStatus.IN_PROGRESS,
        JobStatus.COMPLETED,
        JobStatus.CANCELLED,
        JobStatus.EN_ROUTE,
        JobStatus.ARRIVED,
    }
    return eligible, reschedule


def _summary(
    booking: Booking,
    job_status: str | None,
    *,
    cancellation_eligible: bool,
    reschedule_eligible: bool,
    vehicles: list[BookingVehicleSummary],
    estimated_arrival_at: datetime | None = None,
) -> CustomerBookingSummary:
    if booking.status == BookingStatus.CANCELLED:
        category = "cancelled"
    elif booking.status == BookingStatus.COMPLETED or booking.scheduled_end < datetime.now(UTC):
        category = "past"
    else:
        category = "upcoming"
    return CustomerBookingSummary(
        id=booking.id,
        reference=booking.reference,
        status=map_customer_status(booking.status, job_status),
        payment_status=booking.payment_status,
        scheduled_start=booking.scheduled_start,
        scheduled_end=booking.scheduled_end,
        vehicle_count=booking.vehicle_count,
        total_amount_minor=booking.total_amount_minor,
        currency_code=booking.currency_code,
        written_address=booking.written_address,
        vehicles=vehicles,
        created_at=booking.created_at,
        cancellation_eligible=cancellation_eligible,
        reschedule_eligible=reschedule_eligible,
        estimated_arrival_at=estimated_arrival_at,
        category=category,
    )


async def list_customer_bookings(
    session: AsyncSession, identity: VerifiedIdentity
) -> CustomerBookingListResponse:
    scope = await load_customer_scope(session, identity)
    if scope.profile is None:
        return CustomerBookingListResponse(bookings=[])
    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == scope.business_id)
        )
    ).one()
    rows = (
        await session.execute(
            select(
                Booking,
                Job.status.label("job_status"),
                Job.estimated_arrival_at.label("estimated_arrival_at"),
            )
            .outerjoin(Job, Job.booking_id == Booking.id)
            .where(Booking.customer_profile_id == scope.profile.id)
            .order_by(
                case(
                    (
                        and_(
                            Booking.scheduled_end >= datetime.now(UTC),
                            Booking.status.notin_(
                                [BookingStatus.CANCELLED, BookingStatus.COMPLETED]
                            ),
                        ),
                        0,
                    ),
                    else_=1,
                ),
                Booking.scheduled_start.desc(),
            )
            .limit(100)
        )
    ).all()
    # Named row fields keep consumers stable if the SELECT gains another scalar.
    booking_ids = [row.Booking.id for row in rows]
    vehicle_rows = (
        (
            await session.execute(
                select(BookingVehicle, BookingService, BookingServiceAddon)
                .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
                .outerjoin(
                    BookingServiceAddon,
                    BookingServiceAddon.booking_vehicle_id == BookingVehicle.id,
                )
                .where(BookingVehicle.booking_id.in_(booking_ids))
                .order_by(BookingVehicle.booking_id, BookingVehicle.position)
            )
        ).all()
        if booking_ids
        else []
    )
    vehicles_by_booking = vehicle_summaries_from_rows(vehicle_rows)
    bookings = []
    for row in rows:
        booking = row.Booking
        job_status = row.job_status
        estimated_arrival_at = row.estimated_arrival_at
        cancellation_eligible, reschedule_eligible = _action_eligibility(
            booking, settings, job_status
        )
        bookings.append(
            _summary(
                booking,
                job_status,
                cancellation_eligible=cancellation_eligible,
                reschedule_eligible=reschedule_eligible,
                vehicles=vehicles_by_booking.get(booking.id, []),
                estimated_arrival_at=estimated_arrival_at,
            )
        )
    return CustomerBookingListResponse(bookings=bookings)


async def load_owned_booking(
    session: AsyncSession,
    identity: VerifiedIdentity,
    booking_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Booking:
    configuration = await load_default_business(session)
    statement = (
        select(Booking)
        .join(CustomerProfile, CustomerProfile.id == Booking.customer_profile_id)
        .where(
            Booking.id == booking_id,
            Booking.business_id == configuration.business.id,
            CustomerProfile.auth_user_id == identity.user_id,
            CustomerProfile.is_active.is_(True),
        )
    )
    if lock:
        statement = statement.with_for_update(of=Booking)
    booking = (await session.scalars(statement)).one_or_none()
    if booking is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    return booking


async def customer_booking_detail(
    session: AsyncSession, identity: VerifiedIdentity, booking_id: uuid.UUID
) -> CustomerBookingDetail:
    booking = await load_owned_booking(session, identity, booking_id)
    return await customer_booking_detail_for_record(session, booking)


async def customer_booking_detail_for_record(
    session: AsyncSession, booking: Booking
) -> CustomerBookingDetail:
    vehicle_rows = (
        await session.execute(
            select(BookingVehicle, BookingService, BookingServiceAddon)
            .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
            .outerjoin(
                BookingServiceAddon,
                BookingServiceAddon.booking_vehicle_id == BookingVehicle.id,
            )
            .where(BookingVehicle.booking_id == booking.id)
            .order_by(BookingVehicle.position)
        )
    ).all()
    job_row = (
        await session.execute(
            select(Job.status, Job.estimated_arrival_at).where(Job.booking_id == booking.id)
        )
    ).one_or_none()
    job_status = job_row[0] if job_row else None
    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == booking.business_id)
        )
    ).one()
    cancellation = (
        await session.scalars(
            select(CancellationRequest)
            .where(CancellationRequest.booking_id == booking.id)
            .order_by(CancellationRequest.requested_at.desc())
            .limit(1)
        )
    ).one_or_none()
    cancellation_eligible, reschedule_eligible = _action_eligibility(booking, settings, job_status)
    summary = _summary(
        booking,
        job_status,
        cancellation_eligible=cancellation_eligible,
        reschedule_eligible=reschedule_eligible,
        vehicles=vehicle_summaries_from_rows(vehicle_rows).get(booking.id, []),
        estimated_arrival_at=job_row[1] if job_row else None,
    )
    return CustomerBookingDetail(
        **summary.model_dump(),
        payment_choice=booking.payment_choice,
        location_url=booking.location_url,
        location_instructions=booking.location_instructions,
        latitude=float(booking.latitude) if booking.latitude is not None else None,
        longitude=float(booking.longitude) if booking.longitude is not None else None,
        cancellation_cutoff_at=booking.scheduled_start
        - timedelta(hours=settings.cancellation_cutoff_hours),
        cancellation_status=cancellation.status if cancellation else None,
        timezone=settings.timezone,
    )


async def reschedule_customer_booking(
    session: AsyncSession,
    booking: Booking,
    request: CustomerRescheduleCreate,
) -> CustomerBookingDetail:
    settings = (
        await session.scalars(
            select(BusinessSettings)
            .where(BusinessSettings.business_id == booking.business_id)
            .with_for_update()
        )
    ).one()
    job = (
        await session.scalars(select(Job).where(Job.booking_id == booking.id).with_for_update())
    ).one()
    _cancellation_eligible, reschedule_eligible = _action_eligibility(booking, settings, job.status)
    if not reschedule_eligible:
        raise ConflictError(
            "RESCHEDULE_NOT_AVAILABLE", "This booking can no longer be rescheduled online."
        )
    return await _reschedule_booking(
        session,
        booking,
        job,
        request,
        source="customer_web",
        actor_staff_id=None,
        reset_active_state=False,
    )


async def reschedule_managed_booking(
    session: AsyncSession,
    booking: Booking,
    request: ManagerRescheduleCreate | CustomerRescheduleCreate,
    *,
    actor_staff_id: uuid.UUID,
    confirm_active_reschedule: bool,
) -> CustomerBookingDetail:
    job = (
        await session.scalars(select(Job).where(Job.booking_id == booking.id).with_for_update())
    ).one()
    if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED} or booking.status in {
        BookingStatus.COMPLETED,
        BookingStatus.CANCELLED,
    }:
        raise ConflictError(
            "RESCHEDULE_NOT_AVAILABLE",
            "Completed or cancelled work cannot be rescheduled.",
        )
    active = job.status in {JobStatus.EN_ROUTE, JobStatus.ARRIVED, JobStatus.IN_PROGRESS}
    if active and not confirm_active_reschedule:
        raise ConflictError(
            "ACTIVE_RESCHEDULE_CONFIRMATION_REQUIRED",
            "Confirm that the active job should be reset before rescheduling.",
        )
    if isinstance(request, ManagerRescheduleCreate) and request.date is not None:
        return await _reschedule_managed_exact(
            session,
            booking,
            job,
            request,
            actor_staff_id=actor_staff_id,
            reset_active_state=active,
        )
    legacy_request = (
        CustomerRescheduleCreate(hold_token=request.hold_token)
        if isinstance(request, ManagerRescheduleCreate)
        else request
    )
    return await _reschedule_booking(
        session,
        booking,
        job,
        legacy_request,
        source="staff_override",
        actor_staff_id=actor_staff_id,
        reset_active_state=active,
    )


def _queue_reschedule_notification(
    session: AsyncSession,
    booking: Booking,
    *,
    event_id: uuid.UUID,
    previous_start: datetime,
    scheduled_start: datetime,
    now: datetime,
) -> None:
    session.add(
        NotificationOutbox(
            business_id=booking.business_id,
            booking_id=booking.id,
            channel="email",
            notification_type="booking_rescheduled",
            dedupe_key=f"booking-rescheduled:{event_id}",
            recipient=booking.customer_email,
            payload={
                "booking_reference": booking.reference,
                "previous_start": previous_start.isoformat(),
                "scheduled_start": scheduled_start.isoformat(),
            },
            status="pending",
            next_attempt_at=now,
        )
    )


async def _reschedule_managed_exact(
    session: AsyncSession,
    booking: Booking,
    job: Job,
    request: ManagerRescheduleCreate,
    *,
    actor_staff_id: uuid.UUID,
    reset_active_state: bool,
) -> CustomerBookingDetail:
    if request.date is None or request.time is None or request.client_event_id is None:
        raise DomainError("INVALID_RESCHEDULE_TIME", "Select a date and time.")
    duplicate = await session.scalar(
        select(JobEvent.id).where(
            JobEvent.job_id == job.id,
            JobEvent.client_event_id == request.client_event_id,
        )
    )
    if duplicate is not None:
        return await customer_booking_detail_for_record(session, booking)

    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == booking.business_id)
        )
    ).one()
    zone = ZoneInfo(settings.timezone)
    scheduled_start = datetime.combine(request.date, request.time, zone).astimezone(UTC)
    now = datetime.now(UTC)
    if scheduled_start <= now:
        raise ConflictError("RESCHEDULE_TIME_PASSED", "Choose a future appointment time.")
    expected_minutes = job.expected_duration_minutes or max(
        15, int((job.scheduled_end - job.scheduled_start).total_seconds() // 60)
    )
    scheduled_end = scheduled_start + timedelta(minutes=expected_minutes)
    policy = await policy_for_day(session, settings, request.date)
    if policy is None:
        raise ConflictError("BUSINESS_CLOSED", "Trifecta is closed on that date.")
    opening = datetime.combine(request.date, policy.opening_time, zone).astimezone(UTC)
    closing = datetime.combine(request.date, policy.closing_time, zone).astimezone(UTC)
    if scheduled_start < opening or scheduled_end > closing:
        raise ConflictError(
            "OUTSIDE_OPERATING_HOURS",
            "Choose a time that fits within the configured operating hours.",
        )

    await lock_schedule_day(session, business_id=booking.business_id, day=request.date)
    manual = job.assignment_source == "manual"
    if manual and job.assigned_resource_id is None:
        raise ConflictError(
            "BOOKING_ASSIGNMENT_CHANGED",
            "The manual team assignment must be reviewed before rescheduling.",
        )
    decision = await choose_team_for_booking(
        session,
        business_id=booking.business_id,
        day=request.date,
        timezone=settings.timezone,
        starts_at=scheduled_start,
        ends_at=scheduled_end,
        turnaround_minutes=settings.default_team_turnaround_minutes,
        source="manual" if manual else "auto",
        preferred_team_id=job.assigned_resource_id if manual else None,
        override_turnaround=request.override_turnaround if manual else False,
        exclude_job_id=job.id,
    )
    old_slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(ScheduleSlot.booking_id == booking.id)
                .order_by(ScheduleSlot.slot_start, ScheduleSlot.id)
                .with_for_update()
            )
        ).all()
    )
    if not old_slots:
        raise ConflictError(
            "BOOKING_SLOT_CONFLICT",
            "The existing booking schedule could not be changed safely.",
        )
    for slot in old_slots:
        slot.status = SlotStatus.FREE
        slot.booking_id = None
        slot.hold_group_id = None
        slot.hold_expires_at = None
        slot.version += 1
    new_slots = await _lock_slot_sequence(
        session,
        business_id=booking.business_id,
        resource_id=decision.team.id,
        windows=[SlotWindow(start=scheduled_start, end=scheduled_end)],
    )
    if new_slots is None:
        raise ConflictError("BOOKING_SLOT_CONFLICT", "That exact time is no longer available.")
    for slot in new_slots:
        slot.slot_end = scheduled_end
        slot.status = SlotStatus.RESERVED
        slot.booking_id = booking.id
        slot.hold_group_id = None
        slot.hold_expires_at = None
        slot.version += 1

    previous_start = booking.scheduled_start
    previous_end = booking.scheduled_end
    booking.resource_id = decision.team.id
    booking.scheduled_start = scheduled_start
    booking.scheduled_end = scheduled_end
    booking.version += 1
    job.scheduled_start = scheduled_start
    job.scheduled_end = scheduled_end
    job.expected_duration_minutes = expected_minutes
    job.assigned_resource_id = decision.team.id
    if not manual:
        job.assignment_source = "auto"
        job.assigned_at = now
        job.assigned_by_staff_id = None
    job.status = JobStatus.ASSIGNED
    if reset_active_state:
        job.en_route_at = None
        job.estimated_arrival_at = None
        job.arrived_at = None
        job.started_at = None
        job.completed_at = None
    job.version += 1
    event_id = uuid.uuid4()
    session.add(
        JobEvent(
            id=event_id,
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=actor_staff_id,
            event_type="booking_rescheduled",
            client_event_id=request.client_event_id,
            metadata_json={
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
                "scheduled_start": scheduled_start.isoformat(),
                "scheduled_end": scheduled_end.isoformat(),
                "source": "staff_override",
                "assignment_source": job.assignment_source,
                "active_state_reset": reset_active_state,
            },
        )
    )
    _queue_reschedule_notification(
        session,
        booking,
        event_id=event_id,
        previous_start=previous_start,
        scheduled_start=scheduled_start,
        now=now,
    )
    await session.flush()
    return await customer_booking_detail_for_record(session, booking)


async def _reschedule_booking(
    session: AsyncSession,
    booking: Booking,
    job: Job,
    request: CustomerRescheduleCreate,
    *,
    source: str,
    actor_staff_id: uuid.UUID | None,
    reset_active_state: bool,
) -> CustomerBookingDetail:
    now = datetime.now(UTC)
    hold = (
        await session.scalars(
            select(SlotHoldGroup)
            .where(SlotHoldGroup.token_hash == hold_token_hash(request.hold_token))
            .with_for_update()
        )
    ).one_or_none()
    if hold is None or hold.business_id != booking.business_id:
        raise DomainError("INVALID_HOLD", "The booking hold is invalid.")
    if hold.status != HoldStatus.ACTIVE or hold.expires_at <= now:
        if hold.status == HoldStatus.ACTIVE:
            hold.status = HoldStatus.EXPIRED
        raise ConflictError("HOLD_EXPIRED", "The booking hold has expired.")
    if hold.vehicle_count != booking.vehicle_count:
        raise ConflictError(
            "HOLD_VEHICLE_COUNT_MISMATCH",
            "The hold was acquired for a different number of vehicles.",
        )
    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == booking.business_id)
        )
    ).one()
    day = hold.slot_start.astimezone(ZoneInfo(settings.timezone)).date()
    await lock_schedule_day(session, business_id=booking.business_id, day=day)
    expected_minutes = job.expected_duration_minutes or max(
        15, int((job.scheduled_end - job.scheduled_start).total_seconds() // 60)
    )
    operational_end = hold.slot_start + timedelta(minutes=expected_minutes)
    day_policy = await policy_for_day(session, settings, day)
    if day_policy is None:
        raise ConflictError(
            "NO_TEAM_CAPACITY", "This time is no longer available. Please choose another time."
        )
    closing = datetime.combine(
        day, day_policy.closing_time, ZoneInfo(day_policy.timezone)
    ).astimezone(UTC)
    if operational_end > closing:
        raise ConflictError(
            "NO_TEAM_CAPACITY", "This time is no longer available. Please choose another time."
        )
    if job.assignment_source == "manual" and job.assigned_resource_id is None:
        raise ConflictError(
            "BOOKING_ASSIGNMENT_CHANGED",
            "The manual team assignment must be reviewed before rescheduling.",
        )
    preferred_team_id = (
        job.assigned_resource_id if job.assignment_source == "manual" else hold.resource_id
    )
    await choose_team_for_booking(
        session,
        business_id=booking.business_id,
        day=day,
        timezone=settings.timezone,
        starts_at=hold.slot_start,
        ends_at=operational_end,
        turnaround_minutes=settings.default_team_turnaround_minutes,
        source="manual" if job.assignment_source == "manual" else "auto",
        preferred_team_id=preferred_team_id,
        exclude_job_id=job.id,
        exclude_hold_id=hold.id,
    )

    slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(
                    or_(
                        ScheduleSlot.booking_id == booking.id,
                        ScheduleSlot.hold_group_id == hold.id,
                    )
                )
                .order_by(ScheduleSlot.id)
                .with_for_update()
            )
        ).all()
    )
    old_slots = [slot for slot in slots if slot.booking_id == booking.id]
    held_slots = [slot for slot in slots if slot.hold_group_id == hold.id]
    if len(held_slots) != hold.required_slot_count or any(
        slot.status != SlotStatus.HELD
        or slot.hold_expires_at is None
        or slot.hold_expires_at <= now
        for slot in held_slots
    ):
        raise ConflictError("HOLD_EXPIRED", "The booking hold is no longer valid.")
    if not old_slots or any(slot.status != SlotStatus.RESERVED for slot in old_slots):
        raise ConflictError(
            "BOOKING_SLOT_CONFLICT", "The existing booking schedule could not be changed safely."
        )

    new_slots = held_slots
    target_resource_id = hold.resource_id
    if job.assignment_source == "manual" and job.assigned_resource_id != hold.resource_id:
        manual_team_id = job.assigned_resource_id
        if manual_team_id is None:
            raise ConflictError(
                "BOOKING_ASSIGNMENT_CHANGED",
                "The manual team assignment must be reviewed before rescheduling.",
            )
        manual_slots = await _lock_slot_sequence(
            session,
            business_id=booking.business_id,
            resource_id=manual_team_id,
            windows=[SlotWindow(start=slot.slot_start, end=slot.slot_end) for slot in held_slots],
        )
        if manual_slots is None:
            raise ConflictError(
                "BOOKING_ASSIGNMENT_CHANGED",
                "The manually selected team cannot keep this new time. Choose another time.",
            )
        new_slots = manual_slots
        target_resource_id = manual_team_id

    previous_start = booking.scheduled_start
    previous_end = booking.scheduled_end
    for slot in old_slots:
        slot.status = SlotStatus.FREE
        slot.booking_id = None
        slot.hold_group_id = None
        slot.hold_expires_at = None
        slot.version += 1
    for slot in held_slots:
        if slot not in new_slots:
            slot.status = SlotStatus.FREE
            slot.booking_id = None
            slot.hold_group_id = None
            slot.hold_expires_at = None
            slot.version += 1
    for slot in new_slots:
        slot.status = SlotStatus.RESERVED
        slot.booking_id = booking.id
        slot.hold_expires_at = None
        slot.version += 1
    hold.status = HoldStatus.CONSUMED
    hold.consumed_at = now
    booking.hold_group_id = hold.id
    hold.resource_id = target_resource_id
    hold.expected_duration_minutes = expected_minutes
    hold.slot_end = operational_end
    booking.resource_id = target_resource_id
    booking.scheduled_start = hold.slot_start
    booking.scheduled_end = operational_end
    booking.version += 1
    job.scheduled_start = hold.slot_start
    job.scheduled_end = operational_end
    job.expected_duration_minutes = expected_minutes
    job.assigned_resource_id = target_resource_id
    if job.assignment_source != "manual":
        job.assignment_source = "auto"
        job.assigned_at = now
        job.assigned_by_staff_id = None
    job.status = JobStatus.ASSIGNED
    if reset_active_state:
        job.en_route_at = None
        job.estimated_arrival_at = None
        job.arrived_at = None
        job.started_at = None
        job.completed_at = None
    job.version += 1
    event_id = uuid.uuid4()
    session.add(
        JobEvent(
            id=event_id,
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=actor_staff_id,
            event_type="booking_rescheduled",
            metadata_json={
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
                "scheduled_start": hold.slot_start.isoformat(),
                "scheduled_end": operational_end.isoformat(),
                "source": source,
                "assignment_source": job.assignment_source,
                "active_state_reset": reset_active_state,
            },
        )
    )
    if source == "staff_override":
        _queue_reschedule_notification(
            session,
            booking,
            event_id=event_id,
            previous_start=previous_start,
            scheduled_start=hold.slot_start,
            now=now,
        )
    await session.flush()
    return await customer_booking_detail_for_record(session, booking)
