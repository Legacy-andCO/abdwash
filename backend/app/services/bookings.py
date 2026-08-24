import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus, HoldStatus, JobStatus, PaymentStatus, SlotStatus
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    Job,
    JobEvent,
    NotificationOutbox,
    Payment,
    ScheduleSlot,
    Service,
    SlotHoldGroup,
    Vehicle,
)
from app.repositories.business import load_default_business
from app.schemas.public import (
    BookingCreate,
    BookingResponse,
    BookingVehicleSummary,
    CustomerContact,
)
from app.services.customer_profiles import provision_customer_profile
from app.services.management_tokens import create_management_token, management_token_hash
from app.services.scheduling import hold_token_hash


async def create_booking(
    session: AsyncSession,
    request: BookingCreate,
    identity: VerifiedIdentity | None,
) -> BookingResponse:
    now = datetime.now(UTC)
    hold = (
        await session.scalars(
            select(SlotHoldGroup)
            .where(SlotHoldGroup.token_hash == hold_token_hash(request.hold_token))
            .with_for_update()
        )
    ).one_or_none()
    if hold is None:
        raise DomainError("INVALID_HOLD", "The booking hold is invalid.")
    if hold.status != HoldStatus.ACTIVE or hold.expires_at <= now:
        if hold.status == HoldStatus.ACTIVE:
            hold.status = HoldStatus.EXPIRED
        raise ConflictError("HOLD_EXPIRED", "The booking hold has expired.")
    if hold.vehicle_count != len(request.vehicles):
        raise ConflictError(
            "HOLD_VEHICLE_COUNT_MISMATCH",
            "The hold was acquired for a different number of vehicles.",
        )

    slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(ScheduleSlot.hold_group_id == hold.id)
                .order_by(ScheduleSlot.slot_start)
                .with_for_update()
            )
        ).all()
    )
    if len(slots) != hold.required_slot_count or any(
        slot.status != SlotStatus.HELD
        or slot.hold_expires_at is None
        or slot.hold_expires_at <= now
        for slot in slots
    ):
        raise ConflictError("HOLD_EXPIRED", "The booking hold is no longer valid.")

    configuration = await load_default_business(session)
    if configuration.business.id != hold.business_id:
        raise DomainError("INVALID_HOLD", "The booking hold is invalid.")
    service_ids = {vehicle.service_id for vehicle in request.vehicles}
    services = list(
        (
            await session.scalars(
                select(Service).where(
                    Service.id.in_(service_ids),
                    Service.business_id == hold.business_id,
                    Service.is_active.is_(True),
                )
            )
        ).all()
    )
    services_by_id = {service.id: service for service in services}
    if set(services_by_id) != service_ids:
        raise DomainError("INVALID_SERVICE", "One or more selected services are unavailable.")

    customer_profile_id = await _resolve_customer_profile(
        session,
        identity=identity,
        business_id=hold.business_id,
        contact=request.contact,
    )
    await _validate_saved_vehicles(
        session,
        vehicle_ids={item.vehicle_id for item in request.vehicles if item.vehicle_id},
        customer_profile_id=customer_profile_id,
    )

    booking_id = uuid.uuid4()
    reference = f"AW-{secrets.token_hex(5).upper()}"
    management_token = create_management_token(booking_id)
    confirmed = request.payment_choice == "pay_after_service"
    booking_status = BookingStatus.CONFIRMED if confirmed else BookingStatus.PENDING_PAYMENT
    payment_status = PaymentStatus.UNPAID if confirmed else PaymentStatus.PENDING
    total = sum(services_by_id[item.service_id].price_minor for item in request.vehicles)
    booking = Booking(
        id=booking_id,
        business_id=hold.business_id,
        reference=reference,
        customer_profile_id=customer_profile_id,
        hold_group_id=hold.id,
        resource_id=hold.resource_id,
        status=booking_status,
        payment_choice=request.payment_choice,
        payment_status=payment_status,
        scheduled_start=hold.slot_start,
        scheduled_end=hold.slot_end,
        vehicle_count=len(request.vehicles),
        total_amount_minor=total,
        currency_code=configuration.settings.currency_code,
        source=request.source,
        customer_first_name=request.contact.first_name,
        customer_surname=request.contact.surname,
        customer_email=str(request.contact.email),
        customer_phone=request.contact.phone,
        written_address=request.location.written_address,
        location_url=str(request.location.location_url),
        latitude=request.location.latitude,
        longitude=request.location.longitude,
        location_instructions=request.location.instructions,
        management_token_hash=management_token_hash(management_token),
    )
    session.add(booking)
    await session.flush()

    vehicle_summaries: list[BookingVehicleSummary] = []
    for position, requested_vehicle in enumerate(request.vehicles, start=1):
        booking_vehicle = BookingVehicle(
            booking_id=booking.id,
            vehicle_id=requested_vehicle.vehicle_id,
            position=position,
            make=requested_vehicle.make,
            model=requested_vehicle.model,
            year=requested_vehicle.year,
            vehicle_type=requested_vehicle.vehicle_type,
            colour=requested_vehicle.colour,
            plate_number=requested_vehicle.plate_number,
            notes=requested_vehicle.notes,
        )
        session.add(booking_vehicle)
        await session.flush()
        service = services_by_id[requested_vehicle.service_id]
        session.add(
            BookingService(
                booking_id=booking.id,
                booking_vehicle_id=booking_vehicle.id,
                service_id=service.id,
                service_name=service.name,
                unit_price_minor=service.price_minor,
                quantity=1,
                line_total_minor=service.price_minor,
            )
        )
        vehicle_summaries.append(
            BookingVehicleSummary(
                make=requested_vehicle.make,
                model=requested_vehicle.model,
                year=requested_vehicle.year,
                vehicle_type=requested_vehicle.vehicle_type,
                colour=requested_vehicle.colour,
                plate_number=requested_vehicle.plate_number,
                service_name=service.name,
                line_total_minor=service.price_minor,
            )
        )

    session.add(
        Payment(
            booking_id=booking.id,
            status=payment_status,
            method=None,
            provider=None,
            amount_minor=total,
            currency_code=configuration.settings.currency_code,
        )
    )

    if confirmed:
        hold.status = HoldStatus.CONSUMED
        hold.consumed_at = now
        for slot in slots:
            slot.status = SlotStatus.RESERVED
            slot.booking_id = booking.id
            slot.hold_expires_at = None
            slot.version += 1
        job = Job(
            booking_id=booking.id,
            business_id=booking.business_id,
            assigned_resource_id=booking.resource_id,
            status=JobStatus.ASSIGNED,
            scheduled_start=booking.scheduled_start,
            scheduled_end=booking.scheduled_end,
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                event_type="booking_confirmed",
                metadata_json={"source": request.source},
            )
        )
        session.add(
            NotificationOutbox(
                business_id=booking.business_id,
                booking_id=booking.id,
                channel="email",
                notification_type="booking_confirmed",
                recipient=booking.customer_email,
                payload={"booking_reference": booking.reference},
                status="pending",
                next_attempt_at=now,
            )
        )
    else:
        for slot in slots:
            slot.booking_id = booking.id

    await session.flush()
    return BookingResponse(
        id=booking.id,
        reference=booking.reference,
        status=booking.status,
        payment_choice=booking.payment_choice,
        payment_status=booking.payment_status,
        scheduled_start=booking.scheduled_start,
        scheduled_end=booking.scheduled_end,
        vehicle_count=booking.vehicle_count,
        total_amount_minor=booking.total_amount_minor,
        currency_code=booking.currency_code,
        resource_id=booking.resource_id,
        customer_first_name=booking.customer_first_name,
        customer_surname=booking.customer_surname,
        written_address=booking.written_address,
        location_url=booking.location_url,
        location_instructions=booking.location_instructions,
        vehicles=vehicle_summaries,
        management_token=management_token,
    )


async def _resolve_customer_profile(
    session: AsyncSession,
    *,
    identity: VerifiedIdentity | None,
    business_id: uuid.UUID,
    contact: CustomerContact,
) -> uuid.UUID | None:
    if identity is None:
        return None
    return await provision_customer_profile(
        session,
        identity=identity,
        business_id=business_id,
        first_name=contact.first_name,
        surname=contact.surname,
        phone=contact.phone,
        update_existing=False,
    )


async def _validate_saved_vehicles(
    session: AsyncSession,
    *,
    vehicle_ids: set[uuid.UUID],
    customer_profile_id: uuid.UUID | None,
) -> None:
    if not vehicle_ids:
        return
    if customer_profile_id is None:
        raise DomainError("INVALID_VEHICLE", "Saved vehicles require an authenticated customer.")
    found = set(
        (
            await session.scalars(
                select(Vehicle.id).where(
                    Vehicle.id.in_(vehicle_ids),
                    Vehicle.customer_id == customer_profile_id,
                    Vehicle.is_active.is_(True),
                )
            )
        ).all()
    )
    if found != vehicle_ids:
        raise DomainError("INVALID_VEHICLE", "One or more saved vehicles are unavailable.")
