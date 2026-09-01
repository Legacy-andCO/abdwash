import secrets
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.catalogue import is_vehicle_type
from app.domain.enums import (
    BookingStatus,
    HoldStatus,
    JobStatus,
    LoyaltyEventType,
    LoyaltyRewardStatus,
    PaymentStatus,
    SlotStatus,
)
from app.domain.errors import ConflictError, DomainError
from app.domain.vehicle_identity import normalize_vehicle_plate
from app.models.entities import (
    Booking,
    BookingService,
    BookingServiceAddon,
    BookingVehicle,
    CustomerProfile,
    Job,
    JobEvent,
    LoyaltyEvent,
    LoyaltyReward,
    Payment,
    ScheduleSlot,
    Service,
    ServiceAddon,
    ServicePrice,
    SlotHoldGroup,
    Vehicle,
)
from app.repositories.business import load_default_business
from app.schemas.public import (
    BookingAddonSummary,
    BookingCreate,
    BookingResponse,
    BookingVehicleCreate,
    BookingVehicleSummary,
    CustomerContact,
)
from app.services.customer_communications import queue_customer_email_if_available
from app.services.customer_profiles import provision_customer_profile
from app.services.management_tokens import create_management_token, management_token_hash
from app.services.scheduling import hold_token_hash, policy_for_day
from app.services.smart_scheduling import (
    choose_team_for_booking,
    lock_schedule_day,
    operational_duration_minutes,
)


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
    if any(not service.mobile_available for service in services):
        raise DomainError(
            "SERVICE_CHANNEL_UNAVAILABLE",
            "One or more selected services are not available for mobile bookings.",
        )
    if any(not service.customer_bookable for service in services):
        raise DomainError(
            "SERVICE_NOT_DIRECTLY_BOOKABLE",
            "This product requires package activation and cannot be booked as one ordinary wash.",
            status_code=422,
        )
    if any(not is_vehicle_type(vehicle.vehicle_type) for vehicle in request.vehicles):
        raise DomainError("INVALID_VEHICLE_TYPE", "Choose a supported vehicle type.")
    price_rows = list(
        (
            await session.scalars(
                select(ServicePrice).where(
                    ServicePrice.business_id == hold.business_id,
                    ServicePrice.service_id.in_(service_ids),
                )
            )
        ).all()
    )
    prices = {(row.service_id, row.vehicle_type): row.price_minor for row in price_rows}
    if any(
        (vehicle.service_id, vehicle.vehicle_type) not in prices for vehicle in request.vehicles
    ):
        raise DomainError(
            "SERVICE_PRICE_UNAVAILABLE",
            "The selected service is not priced for this vehicle type.",
        )
    addon_ids = {addon_id for vehicle in request.vehicles for addon_id in vehicle.addon_ids}
    addon_rows = (
        list(
            (
                await session.scalars(
                    select(ServiceAddon).where(
                        ServiceAddon.id.in_(addon_ids),
                        ServiceAddon.business_id == hold.business_id,
                        ServiceAddon.is_active.is_(True),
                        ServiceAddon.mobile_available.is_(True),
                    )
                )
            ).all()
        )
        if addon_ids
        else []
    )
    addons_by_id = {addon.id: addon for addon in addon_rows}
    if set(addons_by_id) != addon_ids:
        raise DomainError("INVALID_SERVICE_ADDON", "One or more selected add-ons are unavailable.")
    for vehicle in request.vehicles:
        if any(
            addons_by_id[addon_id].service_id != vehicle.service_id
            for addon_id in vehicle.addon_ids
        ):
            raise DomainError(
                "SERVICE_ADDON_MISMATCH", "An add-on does not belong to the selected service."
            )

    reserved_floor_minutes = hold.required_slot_count * configuration.settings.slot_duration_minutes
    expected_duration_minutes = operational_duration_minutes(
        (
            services_by_id[vehicle.service_id].estimated_duration_minutes
            for vehicle in request.vehicles
        ),
        (
            addons_by_id[addon_id].default_duration_minutes
            for vehicle in request.vehicles
            for addon_id in vehicle.addon_ids
        ),
        reserved_slot_floor_minutes=reserved_floor_minutes,
    )
    day = hold.slot_start.astimezone(ZoneInfo(configuration.settings.timezone)).date()
    await lock_schedule_day(session, business_id=hold.business_id, day=day)
    operational_end = hold.slot_start + timedelta(minutes=expected_duration_minutes)
    day_policy = await policy_for_day(session, configuration.settings, day)
    if day_policy is None:
        raise ConflictError(
            "NO_TEAM_CAPACITY", "This time is no longer available. Please choose another time."
        )
    closing = datetime.combine(
        day, day_policy.closing_time, ZoneInfo(day_policy.timezone)
    ).astimezone(UTC)
    if expected_duration_minutes > 2880 or operational_end > closing:
        raise ConflictError(
            "NO_TEAM_CAPACITY", "This time is no longer available. Please choose another time."
        )
    # Hold creation takes the business/day advisory lock before any schedule
    # slot rows. Keep confirmation in the same order to avoid a day/slot
    # deadlock under concurrent hold and confirmation requests.
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
    await choose_team_for_booking(
        session,
        business_id=hold.business_id,
        day=day,
        timezone=configuration.settings.timezone,
        starts_at=hold.slot_start,
        ends_at=operational_end,
        turnaround_minutes=configuration.settings.default_team_turnaround_minutes,
        source="auto",
        preferred_team_id=hold.resource_id,
        exclude_hold_id=hold.id,
    )
    hold.expected_duration_minutes = expected_duration_minutes
    hold.slot_end = operational_end

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
    saved_vehicle_ids = await _save_new_customer_vehicles(
        session,
        requested_vehicles=request.vehicles,
        customer_profile_id=customer_profile_id,
    )
    reward_ids = {
        item.loyalty_reward_id for item in request.vehicles if item.loyalty_reward_id is not None
    }
    if len(reward_ids) != sum(item.loyalty_reward_id is not None for item in request.vehicles):
        raise ConflictError(
            "LOYALTY_REWARD_DUPLICATE",
            "Each loyalty reward can be used only once.",
        )
    if reward_ids and not configuration.settings.loyalty_enabled:
        raise ConflictError(
            "LOYALTY_DISABLED",
            "Loyalty rewards are temporarily unavailable.",
        )
    if reward_ids and request.payment_choice != "pay_after_service":
        raise DomainError(
            "LOYALTY_REWARD_PAYMENT_CHOICE",
            "Loyalty rewards currently require Pay After Service.",
            status_code=422,
        )
    rewards_by_id: dict[uuid.UUID, LoyaltyReward] = {}
    if reward_ids:
        if customer_profile_id is None:
            raise DomainError(
                "LOYALTY_AUTH_REQUIRED",
                "Sign in to redeem a loyalty reward.",
                status_code=401,
            )
        rewards = list(
            (
                await session.scalars(
                    select(LoyaltyReward)
                    .where(
                        LoyaltyReward.id.in_(reward_ids),
                        LoyaltyReward.business_id == hold.business_id,
                        LoyaltyReward.customer_profile_id == customer_profile_id,
                    )
                    .with_for_update()
                )
            ).all()
        )
        rewards_by_id = {reward.id: reward for reward in rewards}
        if set(rewards_by_id) != reward_ids or any(
            reward.status != LoyaltyRewardStatus.AVAILABLE for reward in rewards
        ):
            raise ConflictError(
                "LOYALTY_REWARD_UNAVAILABLE",
                "One or more loyalty rewards are no longer available.",
            )
        for requested_vehicle in request.vehicles:
            if requested_vehicle.loyalty_reward_id is None:
                continue
            reward = rewards_by_id[requested_vehicle.loyalty_reward_id]
            if reward.reward_service_id != requested_vehicle.service_id:
                raise DomainError(
                    "LOYALTY_REWARD_SERVICE_MISMATCH",
                    "This reward is valid only for its configured service.",
                    status_code=422,
                )

    booking_id = uuid.uuid4()
    reference = f"AW-{secrets.token_hex(5).upper()}"
    management_token = create_management_token(booking_id)
    confirmed = request.payment_choice == "pay_after_service"
    booking_status = BookingStatus.CONFIRMED if confirmed else BookingStatus.PENDING_PAYMENT
    payment_status = PaymentStatus.UNPAID if confirmed else PaymentStatus.PENDING
    total = sum(
        (0 if item.loyalty_reward_id is not None else prices[(item.service_id, item.vehicle_type)])
        + sum(addons_by_id[addon_id].price_minor for addon_id in item.addon_ids)
        for item in request.vehicles
    )
    if (
        configuration.settings.mobile_minimum_enabled
        and total < configuration.settings.mobile_minimum_minor
    ):
        raise DomainError(
            "MOBILE_MINIMUM_NOT_MET",
            "The mobile booking minimum has not been met.",
            status_code=422,
        )
    if total == 0:
        payment_status = PaymentStatus.PAID
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
        customer_email=str(request.contact.email) if request.contact.email is not None else None,
        customer_phone=request.contact.phone,
        written_address=request.location.written_address,
        location_url=str(request.location.location_url),
        latitude=request.location.latitude,
        longitude=request.location.longitude,
        location_instructions=request.location.instructions,
        billing_company_name=request.billing.company_name if request.billing else None,
        billing_address=request.billing.billing_address if request.billing else None,
        billing_tax_registration_number=(
            request.billing.tax_registration_number if request.billing else None
        ),
        management_token_hash=management_token_hash(management_token),
    )
    session.add(booking)
    await session.flush()

    vehicle_summaries: list[BookingVehicleSummary] = []
    for position, requested_vehicle in enumerate(request.vehicles, start=1):
        booking_vehicle = BookingVehicle(
            booking_id=booking.id,
            vehicle_id=requested_vehicle.vehicle_id or saved_vehicle_ids.get(position),
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
        selected_reward = (
            rewards_by_id.get(requested_vehicle.loyalty_reward_id)
            if requested_vehicle.loyalty_reward_id
            else None
        )
        selected_price = prices[(service.id, requested_vehicle.vehicle_type)]
        discount_minor = selected_price if selected_reward else 0
        booking_service = BookingService(
            booking_id=booking.id,
            booking_vehicle_id=booking_vehicle.id,
            service_id=service.id,
            service_name=service.name,
            unit_price_minor=selected_price,
            list_price_minor=selected_price,
            discount_minor=discount_minor,
            discount_type="loyalty_reward" if selected_reward else None,
            loyalty_reward_id=selected_reward.id if selected_reward else None,
            quantity=1,
            line_total_minor=selected_price - discount_minor,
            expected_duration_minutes=service.estimated_duration_minutes,
        )
        session.add(booking_service)
        await session.flush()
        if selected_reward is not None:
            selected_reward.status = LoyaltyRewardStatus.RESERVED
            selected_reward.reserved_booking_id = booking.id
            selected_reward.reserved_booking_service_id = booking_service.id
            selected_reward.reserved_at = now
            session.add(
                LoyaltyEvent(
                    business_id=booking.business_id,
                    customer_profile_id=customer_profile_id,
                    event_type=LoyaltyEventType.REWARD_RESERVED,
                    quantity=0,
                    booking_id=booking.id,
                    booking_vehicle_id=booking_vehicle.id,
                    reward_id=selected_reward.id,
                    source_key=f"reward-reserved:{selected_reward.id}:{booking.id}",
                )
            )
        addon_summaries: list[BookingAddonSummary] = []
        for addon_id in requested_vehicle.addon_ids:
            addon = addons_by_id[addon_id]
            session.add(
                BookingServiceAddon(
                    booking_id=booking.id,
                    booking_vehicle_id=booking_vehicle.id,
                    service_addon_id=addon.id,
                    addon_name=addon.name,
                    unit_price_minor=addon.price_minor,
                    expected_duration_minutes=addon.default_duration_minutes,
                )
            )
            addon_summaries.append(
                BookingAddonSummary(
                    id=addon.id,
                    name=addon.name,
                    price_minor=addon.price_minor,
                    expected_duration_minutes=addon.default_duration_minutes,
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
                service_id=service.id,
                line_total_minor=(selected_price - discount_minor)
                + sum(item.price_minor for item in addon_summaries),
                list_price_minor=selected_price,
                discount_minor=discount_minor,
                discount_type="loyalty_reward" if selected_reward else None,
                loyalty_reward_id=selected_reward.id if selected_reward else None,
                expected_duration_minutes=service.estimated_duration_minutes,
                addons=addon_summaries,
            )
        )

    session.add(
        Payment(
            booking_id=booking.id,
            status=payment_status,
            method="loyalty" if total == 0 else None,
            provider=None,
            amount_minor=total,
            currency_code=configuration.settings.currency_code,
            paid_at=now if total == 0 else None,
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
            expected_duration_minutes=expected_duration_minutes,
            assignment_source="auto",
            assigned_at=now,
        )
        session.add(job)
        await session.flush()
        from app.services.job_quality import snapshot_checklist_for_job

        await snapshot_checklist_for_job(session, job)
        session.add(
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                event_type="booking_confirmed",
                metadata_json={
                    "source": request.source,
                    "assignment_source": "auto",
                    "expected_duration_minutes": expected_duration_minutes,
                },
            )
        )
        queue_customer_email_if_available(
            session,
            business_id=booking.business_id,
            booking_id=booking.id,
            notification_type="booking_confirmed",
            dedupe_key=f"booking-confirmed:{booking.id}",
            recipient=booking.customer_email,
            payload={"booking_reference": booking.reference},
            next_attempt_at=now,
        )
    else:
        for slot in slots:
            slot.booking_id = booking.id

    await session.flush()
    return BookingResponse(
        id=booking.id,
        business_id=booking.business_id,
        reference=booking.reference,
        status=booking.status,
        payment_choice=booking.payment_choice,
        payment_status=booking.payment_status,
        scheduled_start=booking.scheduled_start,
        scheduled_end=booking.scheduled_end,
        vehicle_count=booking.vehicle_count,
        total_amount_minor=booking.total_amount_minor,
        currency_code=booking.currency_code,
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
        update_existing=True,
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


async def _save_new_customer_vehicles(
    session: AsyncSession,
    *,
    requested_vehicles: list[BookingVehicleCreate],
    customer_profile_id: uuid.UUID | None,
) -> dict[int, uuid.UUID]:
    if customer_profile_id is None:
        return {}
    await session.scalar(
        select(CustomerProfile.id)
        .where(CustomerProfile.id == customer_profile_id)
        .with_for_update()
    )
    existing = list(
        (
            await session.scalars(
                select(Vehicle).where(
                    Vehicle.customer_id == customer_profile_id,
                    Vehicle.is_active.is_(True),
                )
            )
        ).all()
    )
    by_plate = {
        normalize_vehicle_plate(vehicle.plate_number): vehicle.id
        for vehicle in existing
        if vehicle.plate_number and normalize_vehicle_plate(vehicle.plate_number)
    }
    saved: dict[int, uuid.UUID] = {}
    for position, requested in enumerate(requested_vehicles, start=1):
        if requested.vehicle_id is not None:
            continue
        plate_key = normalize_vehicle_plate(requested.plate_number)
        existing_id = by_plate.get(plate_key)
        if existing_id is not None:
            saved[position] = existing_id
            continue
        vehicle = Vehicle(
            customer_id=customer_profile_id,
            make=requested.make,
            model=requested.model,
            year=requested.year,
            vehicle_type=requested.vehicle_type,
            colour=requested.colour,
            plate_number=requested.plate_number,
            notes=requested.notes,
            is_active=True,
        )
        session.add(vehicle)
        await session.flush()
        by_plate[plate_key] = vehicle.id
        saved[position] = vehicle.id
    return saved
