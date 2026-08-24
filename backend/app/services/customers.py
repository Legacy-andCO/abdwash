import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus, HoldStatus, JobStatus, SlotStatus
from app.domain.errors import ConflictError, DomainError
from app.domain.scheduling import cancellation_allowed
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    CancellationRequest,
    CustomerProfile,
    Job,
    JobEvent,
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
)
from app.schemas.public import BookingVehicleSummary
from app.services.scheduling import hold_token_hash


@dataclass(frozen=True)
class CustomerScope:
    identity: VerifiedIdentity
    business_id: uuid.UUID
    profile: CustomerProfile | None


async def load_customer_scope(
    session: AsyncSession, identity: VerifiedIdentity
) -> CustomerScope:
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
            select(func.count(Booking.id)).where(
                Booking.customer_profile_id == scope.profile.id
            )
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
            key="completed", label="Completed", stage=4, job_status=job_status
        )
    if job_status == JobStatus.IN_PROGRESS:
        return CustomerBookingStatus(
            key="in_progress", label="Wash in progress", stage=3, job_status=job_status
        )
    if job_status == "en_route":
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
        "en_route",
    }
    return eligible, reschedule


def _summary(
    booking: Booking,
    job_status: str | None,
    *,
    cancellation_eligible: bool,
    reschedule_eligible: bool,
    vehicles: list[BookingVehicleSummary],
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
            select(Booking, Job.status)
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
    booking_ids = [booking.id for booking, _job_status in rows]
    vehicle_rows = (
        await session.execute(
            select(BookingVehicle, BookingService)
            .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
            .where(BookingVehicle.booking_id.in_(booking_ids))
            .order_by(BookingVehicle.booking_id, BookingVehicle.position)
        )
    ).all() if booking_ids else []
    vehicles_by_booking: dict[uuid.UUID, list[BookingVehicleSummary]] = {}
    for vehicle, service in vehicle_rows:
        vehicles_by_booking.setdefault(vehicle.booking_id, []).append(
            BookingVehicleSummary(
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                vehicle_type=vehicle.vehicle_type,
                colour=vehicle.colour,
                plate_number=vehicle.plate_number,
                service_name=service.service_name,
                line_total_minor=service.line_total_minor,
            )
        )
    bookings = []
    for booking, job_status in rows:
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
            select(BookingVehicle, BookingService)
            .join(BookingService, BookingService.booking_vehicle_id == BookingVehicle.id)
            .where(BookingVehicle.booking_id == booking.id)
            .order_by(BookingVehicle.position)
        )
    ).all()
    job_status = (
        await session.scalars(select(Job.status).where(Job.booking_id == booking.id))
    ).one_or_none()
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
    cancellation_eligible, reschedule_eligible = _action_eligibility(
        booking, settings, job_status
    )
    summary = _summary(
        booking,
        job_status,
        cancellation_eligible=cancellation_eligible,
        reschedule_eligible=reschedule_eligible,
        vehicles=[
            BookingVehicleSummary(
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                vehicle_type=vehicle.vehicle_type,
                colour=vehicle.colour,
                plate_number=vehicle.plate_number,
                service_name=service.service_name,
                line_total_minor=service.line_total_minor,
            )
            for vehicle, service in vehicle_rows
        ],
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
    now = datetime.now(UTC)
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
    _cancellation_eligible, reschedule_eligible = _action_eligibility(
        booking, settings, job.status
    )
    if not reschedule_eligible:
        raise ConflictError(
            "RESCHEDULE_NOT_AVAILABLE", "This booking can no longer be rescheduled online."
        )
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
    new_slots = [slot for slot in slots if slot.hold_group_id == hold.id]
    if len(new_slots) != hold.required_slot_count or any(
        slot.status != SlotStatus.HELD
        or slot.hold_expires_at is None
        or slot.hold_expires_at <= now
        for slot in new_slots
    ):
        raise ConflictError("HOLD_EXPIRED", "The booking hold is no longer valid.")
    if not old_slots or any(slot.status != SlotStatus.RESERVED for slot in old_slots):
        raise ConflictError(
            "BOOKING_SLOT_CONFLICT", "The existing booking schedule could not be changed safely."
        )

    previous_start = booking.scheduled_start
    previous_end = booking.scheduled_end
    for slot in old_slots:
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
    booking.resource_id = hold.resource_id
    booking.scheduled_start = hold.slot_start
    booking.scheduled_end = hold.slot_end
    booking.version += 1
    job.scheduled_start = hold.slot_start
    job.scheduled_end = hold.slot_end
    job.version += 1
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            event_type="booking_rescheduled",
            metadata_json={
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
                "scheduled_start": hold.slot_start.isoformat(),
                "scheduled_end": hold.slot_end.isoformat(),
                "source": "customer_web",
            },
        )
    )
    await session.flush()
    return await customer_booking_detail_for_record(session, booking)
