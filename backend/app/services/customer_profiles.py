import uuid

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import (
    Boolean,
    Integer,
    String,
    cast,
    delete,
    literal,
    null,
    select,
    union_all,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.errors import DomainError
from app.models.entities import CustomerAddress, CustomerProfile, Vehicle
from app.repositories.business import load_default_business
from app.schemas.customer import (
    CustomerAddressResponse,
    CustomerAddressWrite,
    CustomerProfileBootstrap,
    CustomerProfileResponse,
    CustomerProfileUpdate,
    CustomerVehicleResponse,
    CustomerVehicleWrite,
)
from app.services.loyalty import loyalty_summary

email_adapter = TypeAdapter(EmailStr)


def verified_identity_email(identity: VerifiedIdentity) -> str:
    try:
        return str(email_adapter.validate_python(identity.claims.get("email")))
    except ValidationError as exc:
        raise DomainError(
            "AUTH_EMAIL_REQUIRED",
            "A verified email address is required for a customer profile.",
            status_code=400,
        ) from exc


async def provision_customer_profile(
    session: AsyncSession,
    *,
    identity: VerifiedIdentity,
    business_id: uuid.UUID,
    first_name: str,
    surname: str,
    phone: str,
    update_existing: bool,
) -> uuid.UUID:
    values: dict[str, object] = {
        "business_id": business_id,
        "auth_user_id": identity.user_id,
        "first_name": first_name,
        "surname": surname,
        "email": verified_identity_email(identity),
        "phone": phone,
    }
    updates = (
        {
            "first_name": first_name,
            "surname": surname,
            "email": verified_identity_email(identity),
            "phone": phone,
            "is_active": True,
        }
        if update_existing
        else {"auth_user_id": identity.user_id}
    )
    statement = (
        insert(CustomerProfile)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[CustomerProfile.auth_user_id],
            set_=updates,
            where=CustomerProfile.business_id == business_id,
        )
        .returning(CustomerProfile.id)
    )
    profile_id = (await session.scalars(statement)).one_or_none()
    if profile_id is None:
        raise DomainError(
            "CUSTOMER_PROFILE_CONFLICT",
            "This customer identity is already linked to another business.",
            status_code=409,
        )
    return profile_id


def profile_response(profile: CustomerProfile) -> CustomerProfileResponse:
    return CustomerProfileResponse(
        id=profile.id,
        first_name=profile.first_name,
        surname=profile.surname,
        email=profile.email,
        phone=profile.phone,
    )


def address_response(address: CustomerAddress) -> CustomerAddressResponse:
    return CustomerAddressResponse(
        id=address.id,
        label=address.label,
        written_address=address.written_address,
        location_url=address.location_url,
        latitude=float(address.latitude) if address.latitude is not None else None,
        longitude=float(address.longitude) if address.longitude is not None else None,
        location_instructions=address.location_instructions,
        is_default=address.is_default,
    )


def vehicle_response(vehicle: Vehicle) -> CustomerVehicleResponse:
    return CustomerVehicleResponse(
        id=vehicle.id,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        vehicle_type=vehicle.vehicle_type,
        colour=vehicle.colour,
        plate_number=vehicle.plate_number,
        notes=vehicle.notes,
    )


async def load_saved_customer_details(
    session: AsyncSession, customer_id: uuid.UUID
) -> tuple[list[CustomerAddressResponse], list[CustomerVehicleResponse]]:
    """Load both saved-template collections with one bounded round trip."""

    addresses = select(
        literal("address").label("kind"),
        CustomerAddress.id.label("record_id"),
        CustomerAddress.label.label("value_1"),
        CustomerAddress.written_address.label("value_2"),
        CustomerAddress.location_url.label("value_3"),
        CustomerAddress.location_instructions.label("value_4"),
        cast(null(), String).label("value_5"),
        cast(null(), String).label("value_6"),
        cast(null(), Integer).label("year"),
        CustomerAddress.latitude.label("latitude"),
        CustomerAddress.longitude.label("longitude"),
        CustomerAddress.is_default.label("is_default"),
        CustomerAddress.created_at.label("created_at"),
    ).where(CustomerAddress.customer_id == customer_id)
    vehicles = select(
        literal("vehicle").label("kind"),
        Vehicle.id.label("record_id"),
        Vehicle.make.label("value_1"),
        Vehicle.model.label("value_2"),
        Vehicle.vehicle_type.label("value_3"),
        Vehicle.colour.label("value_4"),
        Vehicle.plate_number.label("value_5"),
        Vehicle.notes.label("value_6"),
        Vehicle.year.label("year"),
        cast(null(), CustomerAddress.latitude.type).label("latitude"),
        cast(null(), CustomerAddress.longitude.type).label("longitude"),
        cast(null(), Boolean).label("is_default"),
        Vehicle.created_at.label("created_at"),
    ).where(Vehicle.customer_id == customer_id, Vehicle.is_active.is_(True))
    saved = union_all(addresses, vehicles).subquery()
    rows = (
        await session.execute(
            select(saved).order_by(
                saved.c.kind,
                saved.c.is_default.desc().nullslast(),
                saved.c.created_at,
            )
        )
    ).mappings()
    address_views: list[CustomerAddressResponse] = []
    vehicle_views: list[CustomerVehicleResponse] = []
    for row in rows:
        if row["kind"] == "address":
            address_views.append(
                CustomerAddressResponse(
                    id=row["record_id"],
                    label=row["value_1"],
                    written_address=row["value_2"],
                    location_url=row["value_3"],
                    latitude=float(row["latitude"]) if row["latitude"] is not None else None,
                    longitude=(
                        float(row["longitude"]) if row["longitude"] is not None else None
                    ),
                    location_instructions=row["value_4"],
                    is_default=bool(row["is_default"]),
                )
            )
        else:
            vehicle_views.append(
                CustomerVehicleResponse(
                    id=row["record_id"],
                    make=row["value_1"],
                    model=row["value_2"],
                    year=row["year"],
                    vehicle_type=row["value_3"],
                    colour=row["value_4"],
                    plate_number=row["value_5"],
                    notes=row["value_6"],
                )
            )
    return address_views, vehicle_views


async def load_customer_profile(
    session: AsyncSession,
    identity: VerifiedIdentity,
    *,
    lock: bool = False,
) -> tuple[uuid.UUID, CustomerProfile | None]:
    configuration = await load_default_business(session)
    statement = select(CustomerProfile).where(
        CustomerProfile.auth_user_id == identity.user_id,
        CustomerProfile.business_id == configuration.business.id,
        CustomerProfile.is_active.is_(True),
    )
    if lock:
        statement = statement.with_for_update()
    profile = (await session.scalars(statement)).one_or_none()
    return configuration.business.id, profile


async def require_customer_profile(
    session: AsyncSession, identity: VerifiedIdentity, *, lock: bool = False
) -> CustomerProfile:
    _business_id, profile = await load_customer_profile(session, identity, lock=lock)
    if profile is None:
        raise DomainError(
            "CUSTOMER_PROFILE_REQUIRED",
            "Save your personal information before adding saved details.",
            status_code=409,
        )
    return profile


async def customer_profile_bootstrap(
    session: AsyncSession, identity: VerifiedIdentity
) -> CustomerProfileBootstrap:
    _business_id, profile = await load_customer_profile(session, identity)
    if profile is None:
        return CustomerProfileBootstrap(
            authenticated_email=verified_identity_email(identity),
            profile=None,
            addresses=[],
            vehicles=[],
            loyalty=None,
        )
    addresses, vehicles = await load_saved_customer_details(session, profile.id)
    return CustomerProfileBootstrap(
        authenticated_email=verified_identity_email(identity),
        profile=profile_response(profile),
        addresses=addresses,
        vehicles=vehicles,
        loyalty=await loyalty_summary(
            session,
            business_id=profile.business_id,
            customer_profile_id=profile.id,
        ),
    )


async def update_customer_profile(
    session: AsyncSession, identity: VerifiedIdentity, request: CustomerProfileUpdate
) -> CustomerProfileBootstrap:
    configuration = await load_default_business(session)
    await provision_customer_profile(
        session,
        identity=identity,
        business_id=configuration.business.id,
        first_name=request.first_name,
        surname=request.surname,
        phone=request.phone,
        update_existing=True,
    )
    await session.flush()
    return await customer_profile_bootstrap(session, identity)


async def list_customer_addresses(
    session: AsyncSession, identity: VerifiedIdentity
) -> list[CustomerAddressResponse]:
    profile = await require_customer_profile(session, identity)
    addresses = (
        await session.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == profile.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at)
        )
    ).all()
    return [address_response(address) for address in addresses]


async def list_customer_vehicles(
    session: AsyncSession, identity: VerifiedIdentity
) -> list[CustomerVehicleResponse]:
    profile = await require_customer_profile(session, identity)
    vehicles = (
        await session.scalars(
            select(Vehicle)
            .where(Vehicle.customer_id == profile.id, Vehicle.is_active.is_(True))
            .order_by(Vehicle.created_at)
        )
    ).all()
    return [vehicle_response(vehicle) for vehicle in vehicles]


async def create_customer_address(
    session: AsyncSession, identity: VerifiedIdentity, request: CustomerAddressWrite
) -> CustomerAddressResponse:
    profile = await require_customer_profile(session, identity, lock=True)
    has_address = (
        await session.scalar(
            select(CustomerAddress.id).where(CustomerAddress.customer_id == profile.id).limit(1)
        )
    ) is not None
    make_default = request.is_default or not has_address
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


async def update_customer_address(
    session: AsyncSession,
    identity: VerifiedIdentity,
    address_id: uuid.UUID,
    request: CustomerAddressWrite,
) -> CustomerAddressResponse:
    profile = await require_customer_profile(session, identity, lock=True)
    address = (
        await session.scalars(
            select(CustomerAddress)
            .where(
                CustomerAddress.id == address_id,
                CustomerAddress.customer_id == profile.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if address is None:
        raise DomainError("ADDRESS_NOT_FOUND", "Saved location not found.", status_code=404)
    if request.is_default:
        await session.execute(
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_id == profile.id,
                CustomerAddress.id != address.id,
            )
            .values(is_default=False)
        )
    address.label = request.label
    address.written_address = request.written_address
    address.location_url = str(request.location_url)
    address.latitude = request.latitude
    address.longitude = request.longitude
    address.location_instructions = request.instructions
    # A customer must always retain an effective default while addresses exist.
    # The default moves only by explicitly selecting another address.
    address.is_default = request.is_default or address.is_default
    await session.flush()
    return address_response(address)


async def delete_customer_address(
    session: AsyncSession, identity: VerifiedIdentity, address_id: uuid.UUID
) -> None:
    profile = await require_customer_profile(session, identity, lock=True)
    address = (
        await session.scalars(
            select(CustomerAddress)
            .where(
                CustomerAddress.id == address_id,
                CustomerAddress.customer_id == profile.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if address is None:
        raise DomainError("ADDRESS_NOT_FOUND", "Saved location not found.", status_code=404)
    was_default = address.is_default
    await session.execute(delete(CustomerAddress).where(CustomerAddress.id == address.id))
    if was_default:
        replacement_id = await session.scalar(
            select(CustomerAddress.id)
            .where(
                CustomerAddress.customer_id == profile.id,
                CustomerAddress.id != address.id,
            )
            .order_by(CustomerAddress.created_at)
            .limit(1)
        )
        if replacement_id is not None:
            await session.execute(
                update(CustomerAddress)
                .where(CustomerAddress.id == replacement_id)
                .values(is_default=True)
            )


async def create_customer_vehicle(
    session: AsyncSession, identity: VerifiedIdentity, request: CustomerVehicleWrite
) -> CustomerVehicleResponse:
    profile = await require_customer_profile(session, identity, lock=True)
    vehicle = Vehicle(customer_id=profile.id, **request.model_dump())
    session.add(vehicle)
    await session.flush()
    return vehicle_response(vehicle)


async def update_customer_vehicle(
    session: AsyncSession,
    identity: VerifiedIdentity,
    vehicle_id: uuid.UUID,
    request: CustomerVehicleWrite,
) -> CustomerVehicleResponse:
    profile = await require_customer_profile(session, identity, lock=True)
    vehicle = (
        await session.scalars(
            select(Vehicle)
            .where(
                Vehicle.id == vehicle_id,
                Vehicle.customer_id == profile.id,
                Vehicle.is_active.is_(True),
            )
            .with_for_update()
        )
    ).one_or_none()
    if vehicle is None:
        raise DomainError("VEHICLE_NOT_FOUND", "Saved vehicle not found.", status_code=404)
    for field, value in request.model_dump().items():
        setattr(vehicle, field, value)
    await session.flush()
    return vehicle_response(vehicle)


async def deactivate_customer_vehicle(
    session: AsyncSession, identity: VerifiedIdentity, vehicle_id: uuid.UUID
) -> None:
    profile = await require_customer_profile(session, identity, lock=True)
    vehicle = (
        await session.scalars(
            select(Vehicle)
            .where(
                Vehicle.id == vehicle_id,
                Vehicle.customer_id == profile.id,
                Vehicle.is_active.is_(True),
            )
            .with_for_update()
        )
    ).one_or_none()
    if vehicle is None:
        raise DomainError("VEHICLE_NOT_FOUND", "Saved vehicle not found.", status_code=404)
    vehicle.is_active = False
    await session.flush()
