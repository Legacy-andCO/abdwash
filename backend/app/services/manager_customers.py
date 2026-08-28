import uuid

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import LoyaltyEventType
from app.domain.errors import DomainError
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    CustomerAddress,
    CustomerProfile,
    Job,
    JobComplaint,
    LoyaltyEvent,
    LoyaltyReward,
    Vehicle,
)
from app.schemas.customer import (
    CustomerAddressResponse,
    CustomerAddressWrite,
    CustomerVehicleResponse,
    CustomerVehicleWrite,
)
from app.schemas.manager_customers import (
    ManagerCustomerBooking,
    ManagerCustomerBookingVehicle,
    ManagerCustomerDetail,
    ManagerCustomerList,
    ManagerCustomerListItem,
    ManagerCustomerUpdate,
)
from app.services.customer_profiles import (
    address_response,
    load_saved_customer_details,
    profile_response,
    vehicle_response,
)
from app.services.loyalty import loyalty_summary


def _normalized_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized or None


async def _owned_profile(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    *,
    lock: bool = False,
) -> CustomerProfile:
    statement = select(CustomerProfile).where(
        CustomerProfile.id == customer_id,
        CustomerProfile.business_id == context.business_id,
        CustomerProfile.is_active.is_(True),
    )
    if lock:
        statement = statement.with_for_update()
    profile = await session.scalar(statement)
    if profile is None:
        raise DomainError("CUSTOMER_NOT_FOUND", "Customer not found.", status_code=404)
    return profile


async def list_manager_customers(
    session: AsyncSession,
    context: StaffContext,
    *,
    search: str | None,
    offset: int,
    limit: int,
) -> ManagerCustomerList:
    term = _normalized_search(search)
    vehicle_count = (
        select(func.count(Vehicle.id))
        .where(Vehicle.customer_id == CustomerProfile.id, Vehicle.is_active.is_(True))
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    booking_count = (
        select(func.count(Booking.id))
        .where(Booking.customer_profile_id == CustomerProfile.id)
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    latest_booking = (
        select(func.max(Booking.created_at))
        .where(Booking.customer_profile_id == CustomerProfile.id)
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    reward_count = (
        select(func.count(LoyaltyReward.id))
        .where(
            LoyaltyReward.customer_profile_id == CustomerProfile.id,
            LoyaltyReward.business_id == context.business_id,
            LoyaltyReward.status == "available",
        )
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    credit_total = (
        select(func.coalesce(func.sum(LoyaltyEvent.quantity), 0))
        .where(
            LoyaltyEvent.customer_profile_id == CustomerProfile.id,
            LoyaltyEvent.business_id == context.business_id,
            LoyaltyEvent.event_type.in_(
                [
                    LoyaltyEventType.QUALIFYING_WASH,
                    LoyaltyEventType.MANUAL_CREDIT,
                    LoyaltyEventType.MANUAL_DEBIT,
                ]
            ),
        )
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    consumed_credits = (
        select(func.coalesce(func.sum(LoyaltyReward.required_washes), 0))
        .where(
            LoyaltyReward.customer_profile_id == CustomerProfile.id,
            LoyaltyReward.business_id == context.business_id,
        )
        .correlate(CustomerProfile)
        .scalar_subquery()
    )
    required_washes = int(
        await session.scalar(
            select(BusinessSettings.loyalty_required_washes).where(
                BusinessSettings.business_id == context.business_id
            )
        )
        or 9
    )
    statement = select(
        CustomerProfile,
        vehicle_count.label("active_vehicle_count"),
        booking_count.label("booking_count"),
        latest_booking.label("latest_booking_at"),
        reward_count.label("available_rewards"),
        credit_total.label("loyalty_credit_total"),
        consumed_credits.label("loyalty_consumed_credits"),
    ).where(
        CustomerProfile.business_id == context.business_id,
        CustomerProfile.is_active.is_(True),
    )
    if term:
        pattern = f"%{term}%"
        plate_match = exists(
            select(Vehicle.id).where(
                Vehicle.customer_id == CustomerProfile.id,
                Vehicle.is_active.is_(True),
                func.lower(Vehicle.plate_number).like(pattern),
            )
        )
        statement = statement.where(
            or_(
                func.lower(CustomerProfile.first_name).like(pattern),
                func.lower(CustomerProfile.surname).like(pattern),
                func.lower(CustomerProfile.first_name + " " + CustomerProfile.surname).like(
                    pattern
                ),
                func.lower(CustomerProfile.email).like(pattern),
                func.lower(CustomerProfile.phone).like(pattern),
                plate_match,
            )
        )
    rows = (
        await session.execute(
            statement.order_by(CustomerProfile.first_name, CustomerProfile.surname)
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    return ManagerCustomerList(
        customers=[
            ManagerCustomerListItem(
                id=profile.id,
                first_name=profile.first_name,
                surname=profile.surname,
                email=profile.email,
                phone=profile.phone,
                active_vehicle_count=active_vehicle_count,
                booking_count=bookings,
                latest_booking_at=latest,
                available_rewards=available,
                loyalty_progress_washes=max(0, credits - consumed),
                loyalty_required_washes=required_washes,
            )
            for (
                profile,
                active_vehicle_count,
                bookings,
                latest,
                available,
                credits,
                consumed,
            ) in page
        ],
        next_offset=offset + limit if len(rows) > limit else None,
    )


async def manager_customer_detail(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    *,
    history_offset: int = 0,
    history_limit: int = 30,
) -> ManagerCustomerDetail:
    profile = await _owned_profile(session, context, customer_id)
    addresses, vehicles = await load_saved_customer_details(session, customer_id)
    booking_rows = list(
        (
            await session.scalars(
                select(Booking)
                .where(
                    Booking.business_id == context.business_id,
                    Booking.customer_profile_id == customer_id,
                )
                .order_by(Booking.scheduled_start.desc())
                .offset(history_offset)
                .limit(history_limit + 1)
            )
        ).all()
    )
    bookings = booking_rows[:history_limit]
    booking_ids = [item.id for item in bookings]
    vehicle_rows = (
        await session.execute(
            select(BookingVehicle, BookingService.service_name)
            .select_from(BookingVehicle)
            .outerjoin(
                BookingService,
                BookingService.booking_vehicle_id == BookingVehicle.id,
            )
            .where(BookingVehicle.booking_id.in_(booking_ids))
            .order_by(BookingVehicle.booking_id, BookingVehicle.position)
        )
    ).all()
    vehicles_by_booking: dict[uuid.UUID, list[ManagerCustomerBookingVehicle]] = {
        booking_id: [] for booking_id in booking_ids
    }
    for vehicle, service_name in vehicle_rows:
        vehicles_by_booking[vehicle.booking_id].append(
            ManagerCustomerBookingVehicle(
                make=vehicle.make,
                model=vehicle.model,
                plate_number=vehicle.plate_number,
                service_name=service_name,
            )
        )
    job_rows = (
        await session.execute(
            select(
                Job.booking_id,
                Job.id,
                Job.status,
                func.count(JobComplaint.id).label("complaint_count"),
            )
            .select_from(Job)
            .outerjoin(JobComplaint, JobComplaint.original_job_id == Job.id)
            .where(Job.booking_id.in_(booking_ids), Job.business_id == context.business_id)
            .group_by(Job.booking_id, Job.id, Job.status)
        )
    ).all()
    jobs_by_booking = {
        booking_id: (job_id, job_status, complaint_count)
        for booking_id, job_id, job_status, complaint_count in job_rows
    }
    return ManagerCustomerDetail(
        profile=profile_response(profile),
        addresses=addresses,
        vehicles=vehicles,
        bookings=[
            ManagerCustomerBooking(
                id=item.id,
                reference=item.reference,
                status=item.status,
                payment_status=item.payment_status,
                scheduled_start=item.scheduled_start,
                total_amount_minor=item.total_amount_minor,
                currency_code=item.currency_code,
                vehicle_count=item.vehicle_count,
                job_id=(jobs_by_booking.get(item.id) or (None, None, 0))[0],
                job_status=(jobs_by_booking.get(item.id) or (None, None, 0))[1],
                complaint_count=(jobs_by_booking.get(item.id) or (None, None, 0))[2],
                vehicles=vehicles_by_booking.get(item.id, []),
            )
            for item in bookings
        ],
        bookings_next_offset=(
            history_offset + history_limit if len(booking_rows) > history_limit else None
        ),
        loyalty=await loyalty_summary(
            session, business_id=context.business_id, customer_profile_id=customer_id
        ),
    )


async def update_manager_customer(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    request: ManagerCustomerUpdate,
) -> ManagerCustomerDetail:
    profile = await _owned_profile(session, context, customer_id, lock=True)
    profile.first_name = request.first_name
    profile.surname = request.surname
    profile.phone = request.phone
    await session.flush()
    return await manager_customer_detail(session, context, customer_id)


async def _owned_address(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
) -> tuple[CustomerProfile, CustomerAddress]:
    profile = await _owned_profile(session, context, customer_id, lock=True)
    address = await session.scalar(
        select(CustomerAddress)
        .where(CustomerAddress.id == address_id, CustomerAddress.customer_id == profile.id)
        .with_for_update()
    )
    if address is None:
        raise DomainError("ADDRESS_NOT_FOUND", "Saved location not found.", status_code=404)
    return profile, address


async def create_manager_address(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    request: CustomerAddressWrite,
) -> CustomerAddressResponse:
    profile = await _owned_profile(session, context, customer_id, lock=True)
    count = int(
        await session.scalar(
            select(func.count(CustomerAddress.id)).where(CustomerAddress.customer_id == profile.id)
        )
        or 0
    )
    make_default = request.is_default or count == 0
    if make_default:
        await session.execute(
            update(CustomerAddress)
            .where(CustomerAddress.customer_id == profile.id)
            .values(is_default=False)
        )
    address = CustomerAddress(
        customer_id=profile.id,
        label=request.label,
        written_address=request.written_address,
        location_url=str(request.location_url),
        latitude=request.latitude,
        longitude=request.longitude,
        location_instructions=request.instructions,
        is_default=make_default,
    )
    session.add(address)
    await session.flush()
    return address_response(address)


async def update_manager_address(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    request: CustomerAddressWrite,
) -> CustomerAddressResponse:
    profile, address = await _owned_address(session, context, customer_id, address_id)
    if request.is_default:
        await session.execute(
            update(CustomerAddress)
            .where(CustomerAddress.customer_id == profile.id, CustomerAddress.id != address.id)
            .values(is_default=False)
        )
    address.label = request.label
    address.written_address = request.written_address
    address.location_url = str(request.location_url)
    address.latitude = request.latitude
    address.longitude = request.longitude
    address.location_instructions = request.instructions
    address.is_default = request.is_default or address.is_default
    await session.flush()
    return address_response(address)


async def delete_manager_address(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
) -> None:
    profile, address = await _owned_address(session, context, customer_id, address_id)
    was_default = address.is_default
    await session.delete(address)
    await session.flush()
    if was_default:
        replacement = await session.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == profile.id)
            .order_by(CustomerAddress.created_at)
            .limit(1)
            .with_for_update()
        )
        if replacement is not None:
            replacement.is_default = True


async def _owned_vehicle(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    vehicle_id: uuid.UUID,
) -> Vehicle:
    await _owned_profile(session, context, customer_id, lock=True)
    vehicle = await session.scalar(
        select(Vehicle)
        .where(
            Vehicle.id == vehicle_id,
            Vehicle.customer_id == customer_id,
            Vehicle.is_active.is_(True),
        )
        .with_for_update()
    )
    if vehicle is None:
        raise DomainError("VEHICLE_NOT_FOUND", "Saved vehicle not found.", status_code=404)
    return vehicle


async def create_manager_vehicle(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    request: CustomerVehicleWrite,
) -> CustomerVehicleResponse:
    await _owned_profile(session, context, customer_id, lock=True)
    vehicle = Vehicle(customer_id=customer_id, **request.model_dump())
    session.add(vehicle)
    await session.flush()
    return vehicle_response(vehicle)


async def update_manager_vehicle(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    request: CustomerVehicleWrite,
) -> CustomerVehicleResponse:
    vehicle = await _owned_vehicle(session, context, customer_id, vehicle_id)
    for field, value in request.model_dump().items():
        setattr(vehicle, field, value)
    await session.flush()
    return vehicle_response(vehicle)


async def deactivate_manager_vehicle(
    session: AsyncSession,
    context: StaffContext,
    customer_id: uuid.UUID,
    vehicle_id: uuid.UUID,
) -> None:
    vehicle = await _owned_vehicle(session, context, customer_id, vehicle_id)
    vehicle.is_active = False
    await session.flush()
