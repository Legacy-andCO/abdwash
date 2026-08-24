import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.auth.dependencies import SessionDep, required_identity
from app.auth.verifier import VerifiedIdentity
from app.schemas.customer import (
    CustomerBookingActionResponse,
    CustomerBookingDetail,
    CustomerBookingListResponse,
    CustomerCancellationCreate,
    CustomerContextResponse,
    CustomerRescheduleCreate,
)
from app.schemas.public import CancellationRequestCreate
from app.services.booking_management import request_booking_cancellation
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

router = APIRouter(prefix="/api/v1/customer", tags=["customer"])
IdentityDep = Annotated[VerifiedIdentity, Depends(required_identity)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=255)
]


@router.get("/context", response_model=CustomerContextResponse)
async def context(session: SessionDep, identity: IdentityDep) -> CustomerContextResponse:
    return await customer_context(session, identity)


@router.get("/bookings", response_model=CustomerBookingListResponse)
async def bookings(
    session: SessionDep, identity: IdentityDep
) -> CustomerBookingListResponse:
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
