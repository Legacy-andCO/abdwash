import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus
from app.domain.errors import ConflictError
from app.models.entities import (
    Booking,
    BookingVehicle,
    CustomerAddress,
    CustomerPaymentMethod,
    CustomerProfile,
    CustomerReview,
    CustomerReviewPromptState,
    DeletedCustomerIdentity,
    Vehicle,
)
from app.repositories.business import load_default_business


async def delete_customer_domain_account(
    session: AsyncSession, identity: VerifiedIdentity
) -> uuid.UUID:
    configuration = await load_default_business(session)
    existing_tombstone = await session.scalar(
        select(DeletedCustomerIdentity.id).where(
            DeletedCustomerIdentity.auth_user_id == identity.user_id,
            DeletedCustomerIdentity.business_id == configuration.business.id,
        )
    )
    if existing_tombstone is not None:
        return identity.user_id

    profile = (
        await session.scalars(
            select(CustomerProfile)
            .where(
                CustomerProfile.auth_user_id == identity.user_id,
                CustomerProfile.business_id == configuration.business.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if profile is not None:
        active_booking = await session.scalar(
            select(Booking.id)
            .where(
                Booking.customer_profile_id == profile.id,
                Booking.status.not_in(
                    [BookingStatus.COMPLETED, BookingStatus.CANCELLED]
                ),
            )
            .limit(1)
        )
        if active_booking is not None:
            raise ConflictError(
                "ACTIVE_BOOKING_ACCOUNT_DELETION",
                "Complete or cancel active bookings before deleting your account.",
            )
        booking_ids = select(Booking.id).where(Booking.customer_profile_id == profile.id)
        await session.execute(
            update(BookingVehicle)
            .where(BookingVehicle.booking_id.in_(booking_ids))
            .values(vehicle_id=None)
        )
        await session.execute(
            update(Booking)
            .where(Booking.customer_profile_id == profile.id)
            .values(
                customer_profile_id=None,
                customer_first_name="Deleted",
                customer_surname="Customer",
                customer_email=None,
                customer_phone="deleted",
                written_address="Deleted customer address",
                location_url="https://www.google.com/maps",
                latitude=None,
                longitude=None,
                location_instructions=None,
            )
        )
        await session.execute(
            delete(CustomerReview).where(CustomerReview.customer_profile_id == profile.id)
        )
        await session.execute(
            delete(CustomerReviewPromptState).where(
                CustomerReviewPromptState.customer_profile_id == profile.id
            )
        )
        await session.execute(
            delete(CustomerAddress).where(CustomerAddress.customer_id == profile.id)
        )
        await session.execute(
            delete(CustomerPaymentMethod).where(
                CustomerPaymentMethod.customer_id == profile.id
            )
        )
        await session.execute(delete(Vehicle).where(Vehicle.customer_id == profile.id))
        await session.delete(profile)

    session.add(
        DeletedCustomerIdentity(
            business_id=configuration.business.id,
            auth_user_id=identity.user_id,
        )
    )
    await session.flush()
    return identity.user_id
