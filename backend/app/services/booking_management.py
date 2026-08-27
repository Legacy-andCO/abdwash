import hmac
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import BookingStatus, CancellationStatus
from app.domain.errors import ConflictError, DomainError
from app.domain.scheduling import cancellation_allowed
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    CancellationRequest,
    Job,
    JobEvent,
    NotificationOutbox,
)
from app.schemas.public import (
    BookingManagementResponse,
    BookingVehicleSummary,
    CancellationRequestCreate,
    CancellationRequestResponse,
)
from app.services.management_tokens import (
    booking_id_from_management_token,
    management_token_hash,
)


async def load_managed_booking(
    session: AsyncSession, management_token: str, *, lock: bool = False
) -> Booking:
    booking_id = booking_id_from_management_token(management_token)
    if booking_id is None:
        raise DomainError("BOOKING_NOT_FOUND", "This booking link is invalid.", status_code=404)
    statement = select(Booking).where(Booking.id == booking_id)
    if lock:
        statement = statement.with_for_update()
    booking = (await session.scalars(statement)).one_or_none()
    if booking is None or not hmac.compare_digest(
        booking.management_token_hash, management_token_hash(management_token)
    ):
        raise DomainError("BOOKING_NOT_FOUND", "This booking link is invalid.", status_code=404)
    return booking


async def booking_management_response(
    session: AsyncSession, booking: Booking
) -> BookingManagementResponse:
    rows = (
        await session.execute(
            select(BookingVehicle, BookingService)
            .join(
                BookingService,
                BookingService.booking_vehicle_id == BookingVehicle.id,
            )
            .where(BookingVehicle.booking_id == booking.id)
            .order_by(BookingVehicle.position)
        )
    ).all()
    cancellation = (
        await session.scalars(
            select(CancellationRequest)
            .where(CancellationRequest.booking_id == booking.id)
            .order_by(CancellationRequest.requested_at.desc())
            .limit(1)
        )
    ).one_or_none()
    settings = (
        await session.scalars(
            select(BusinessSettings).where(BusinessSettings.business_id == booking.business_id)
        )
    ).one()
    cutoff = booking.scheduled_start - timedelta(hours=settings.cancellation_cutoff_hours)
    eligible = booking.status == BookingStatus.CONFIRMED and cancellation_allowed(
        booking.scheduled_start, settings.cancellation_cutoff_hours
    )
    return BookingManagementResponse(
        reference=booking.reference,
        status=booking.status,
        payment_choice=booking.payment_choice,
        payment_status=booking.payment_status,
        scheduled_start=booking.scheduled_start,
        scheduled_end=booking.scheduled_end,
        total_amount_minor=booking.total_amount_minor,
        currency_code=booking.currency_code,
        customer_first_name=booking.customer_first_name,
        customer_surname=booking.customer_surname,
        written_address=booking.written_address,
        location_url=booking.location_url,
        location_instructions=booking.location_instructions,
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
                list_price_minor=service.list_price_minor or service.unit_price_minor,
                discount_minor=service.discount_minor or 0,
                discount_type=service.discount_type,
                loyalty_reward_id=service.loyalty_reward_id,
            )
            for vehicle, service in rows
        ],
        cancellation_eligible=eligible,
        cancellation_cutoff_at=cutoff,
        cancellation_status=cancellation.status if cancellation else None,
        timezone=settings.timezone,
    )


async def request_booking_cancellation(
    session: AsyncSession,
    booking: Booking,
    request: CancellationRequestCreate,
) -> CancellationRequestResponse:
    now = datetime.now(UTC)
    settings = (
        await session.scalars(
            select(BusinessSettings)
            .where(BusinessSettings.business_id == booking.business_id)
            .with_for_update()
        )
    ).one()
    if booking.status != BookingStatus.CONFIRMED:
        raise ConflictError(
            "CANCELLATION_NOT_AVAILABLE",
            "This booking is not eligible for a new cancellation request.",
        )
    if not cancellation_allowed(
        booking.scheduled_start, settings.cancellation_cutoff_hours, now=now
    ):
        raise ConflictError(
            "CANCELLATION_CUTOFF_PASSED",
            (
                "Cancellation requests close "
                f"{settings.cancellation_cutoff_hours} hours before service."
            ),
        )
    cancellation = CancellationRequest(
        booking_id=booking.id,
        requester_type="customer",
        reason=request.reason,
        status=CancellationStatus.REQUESTED,
        requested_at=now,
    )
    session.add(cancellation)
    booking.status = BookingStatus.CANCELLATION_REQUESTED
    booking.version += 1
    job = (await session.scalars(select(Job).where(Job.booking_id == booking.id))).one()
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            event_type="cancellation_requested",
            metadata_json={"requester_type": "customer"},
        )
    )
    session.add(
        NotificationOutbox(
            business_id=booking.business_id,
            booking_id=booking.id,
            channel="email",
            notification_type="cancellation_requested",
            recipient=booking.customer_email,
            payload={
                "booking_reference": booking.reference,
                "scheduled_start": booking.scheduled_start.isoformat(),
                "status": "requested",
            },
            status="pending",
            next_attempt_at=now,
        )
    )
    await session.flush()
    return CancellationRequestResponse(
        id=cancellation.id,
        status=cancellation.status,
        booking=await booking_management_response(session, booking),
    )
