import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.auth.dependencies import SessionDep, required_identity
from app.auth.verifier import VerifiedIdentity
from app.repositories.business import load_default_business
from app.schemas.customer import (
    CustomerAddressResponse,
    CustomerAddressWrite,
    CustomerBookingActionResponse,
    CustomerBookingDetail,
    CustomerBookingListResponse,
    CustomerCancellationCreate,
    CustomerContextResponse,
    CustomerProfileBootstrap,
    CustomerProfileUpdate,
    CustomerRescheduleCreate,
    CustomerVehicleResponse,
    CustomerVehicleWrite,
)
from app.schemas.public import CancellationRequestCreate
from app.services.booking_management import request_booking_cancellation
from app.services.customer_profiles import (
    create_customer_address,
    create_customer_vehicle,
    customer_profile_bootstrap,
    deactivate_customer_vehicle,
    delete_customer_address,
    list_customer_addresses,
    list_customer_vehicles,
    update_customer_address,
    update_customer_profile,
    update_customer_vehicle,
)
from app.services.customers import (
    customer_booking_detail,
    customer_booking_detail_for_record,
    customer_context,
    list_customer_bookings,
    load_owned_booking,
    reschedule_customer_booking,
)
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.sync_state import bump_sync_revisions

router = APIRouter(prefix="/api/v1/customer", tags=["customer"])
IdentityDep = Annotated[VerifiedIdentity, Depends(required_identity)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)]


@router.get("/context", response_model=CustomerContextResponse)
async def context(session: SessionDep, identity: IdentityDep) -> CustomerContextResponse:
    return await customer_context(session, identity)


@router.get("/profile", response_model=CustomerProfileBootstrap)
async def profile(session: SessionDep, identity: IdentityDep) -> CustomerProfileBootstrap:
    return await customer_profile_bootstrap(session, identity)


@router.patch("/profile", response_model=CustomerProfileBootstrap)
async def profile_update(
    request: CustomerProfileUpdate, session: SessionDep, identity: IdentityDep
) -> CustomerProfileBootstrap:
    async with session.begin():
        result = await update_customer_profile(session, identity, request)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
        return result


@router.get("/addresses", response_model=list[CustomerAddressResponse])
async def addresses(session: SessionDep, identity: IdentityDep) -> list[CustomerAddressResponse]:
    return await list_customer_addresses(session, identity)


@router.post("/addresses", response_model=CustomerAddressResponse, status_code=201)
async def address_create(
    request: CustomerAddressWrite, session: SessionDep, identity: IdentityDep
) -> CustomerAddressResponse:
    async with session.begin():
        result = await create_customer_address(session, identity, request)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
        return result


@router.patch("/addresses/{address_id}", response_model=CustomerAddressResponse)
async def address_update(
    address_id: uuid.UUID,
    request: CustomerAddressWrite,
    session: SessionDep,
    identity: IdentityDep,
) -> CustomerAddressResponse:
    async with session.begin():
        result = await update_customer_address(session, identity, address_id, request)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
        return result


@router.delete("/addresses/{address_id}", status_code=204)
async def address_delete(
    address_id: uuid.UUID, session: SessionDep, identity: IdentityDep
) -> Response:
    async with session.begin():
        await delete_customer_address(session, identity, address_id)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
    return Response(status_code=204)


@router.get("/vehicles", response_model=list[CustomerVehicleResponse])
async def vehicles(session: SessionDep, identity: IdentityDep) -> list[CustomerVehicleResponse]:
    return await list_customer_vehicles(session, identity)


@router.post("/vehicles", response_model=CustomerVehicleResponse, status_code=201)
async def vehicle_create(
    request: CustomerVehicleWrite, session: SessionDep, identity: IdentityDep
) -> CustomerVehicleResponse:
    async with session.begin():
        result = await create_customer_vehicle(session, identity, request)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
        return result


@router.patch("/vehicles/{vehicle_id}", response_model=CustomerVehicleResponse)
async def vehicle_update(
    vehicle_id: uuid.UUID,
    request: CustomerVehicleWrite,
    session: SessionDep,
    identity: IdentityDep,
) -> CustomerVehicleResponse:
    async with session.begin():
        result = await update_customer_vehicle(session, identity, vehicle_id, request)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
        return result


@router.delete("/vehicles/{vehicle_id}", status_code=204)
async def vehicle_delete(
    vehicle_id: uuid.UUID, session: SessionDep, identity: IdentityDep
) -> Response:
    async with session.begin():
        await deactivate_customer_vehicle(session, identity, vehicle_id)
        configuration = await load_default_business(session)
        await bump_sync_revisions(session, configuration.business.id, "customers")
    return Response(status_code=204)


@router.get("/bookings", response_model=CustomerBookingListResponse)
async def bookings(session: SessionDep, identity: IdentityDep) -> CustomerBookingListResponse:
    return await list_customer_bookings(session, identity)


@router.get("/bookings/{booking_id}", response_model=CustomerBookingDetail)
async def booking_detail(
    booking_id: uuid.UUID, session: SessionDep, identity: IdentityDep
) -> CustomerBookingDetail:
    return await customer_booking_detail(session, identity, booking_id)


@router.post(
    "/bookings/{booking_id}/cancellation-requests",
    response_model=CustomerBookingActionResponse,
    status_code=201,
)
async def cancellation_request(
    booking_id: uuid.UUID,
    request: CustomerCancellationCreate,
    session: SessionDep,
    identity: IdentityDep,
    idempotency_key: IdempotencyKey,
) -> CustomerBookingActionResponse:
    request_hash = canonical_request_hash(request.model_dump(mode="json"))
    async with session.begin():
        booking = await load_owned_booking(session, identity, booking_id, lock=True)
        scope = f"customer:{identity.user_id}:booking:{booking.id}"
        existing = await find_idempotent_response(
            session,
            scope=scope,
            operation="request_cancellation",
            key=idempotency_key,
            request_hash=request_hash,
        )
        if existing is not None:
            return CustomerBookingActionResponse.model_validate(existing.response_json)
        await request_booking_cancellation(
            session, booking, CancellationRequestCreate(reason=request.reason)
        )
        await bump_sync_revisions(session, booking.business_id, "jobs", "customers")
        response = CustomerBookingActionResponse(
            booking=await customer_booking_detail_for_record(session, booking)
        )
        store_idempotent_response(
            session,
            scope=scope,
            operation="request_cancellation",
            key=idempotency_key,
            request_hash=request_hash,
            response_status=201,
            response_json=response.model_dump(mode="json"),
            resource_id=booking.id,
        )
        return response


@router.post(
    "/bookings/{booking_id}/reschedule",
    response_model=CustomerBookingActionResponse,
)
async def reschedule(
    booking_id: uuid.UUID,
    request: CustomerRescheduleCreate,
    session: SessionDep,
    identity: IdentityDep,
    idempotency_key: IdempotencyKey,
) -> CustomerBookingActionResponse:
    request_hash = canonical_request_hash(request.model_dump(mode="json"))
    async with session.begin():
        booking = await load_owned_booking(session, identity, booking_id, lock=True)
        scope = f"customer:{identity.user_id}:booking:{booking.id}"
        existing = await find_idempotent_response(
            session,
            scope=scope,
            operation="reschedule_booking",
            key=idempotency_key,
            request_hash=request_hash,
        )
        if existing is not None:
            return CustomerBookingActionResponse.model_validate(existing.response_json)
        detail = await reschedule_customer_booking(session, booking, request)
        await bump_sync_revisions(session, booking.business_id, "jobs", "schedule", "customers")
        response = CustomerBookingActionResponse(booking=detail)
        store_idempotent_response(
            session,
            scope=scope,
            operation="reschedule_booking",
            key=idempotency_key,
            request_hash=request_hash,
            response_status=200,
            response_json=response.model_dump(mode="json"),
            resource_id=booking.id,
        )
        return response
