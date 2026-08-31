import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import SessionDep, optional_identity
from app.auth.verifier import VerifiedIdentity
from app.schemas.invoices import RevenueInvoiceView
from app.schemas.public import (
    AvailabilityResponse,
    BookingCreate,
    BookingManagementResponse,
    BookingResponse,
    CancellationRequestCreate,
    CancellationRequestResponse,
    CatalogueResponse,
    HoldCreate,
    HoldResponse,
)
from app.services.booking_management import (
    booking_management_response,
    load_managed_booking,
    request_booking_cancellation,
)
from app.services.bookings import create_booking
from app.services.catalogue import get_catalogue
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.invoices import managed_invoice
from app.services.management_tokens import create_management_token
from app.services.scheduling import availability_for_date, create_hold
from app.services.sync_state import bump_sync_revisions

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/catalogue", response_model=CatalogueResponse)
async def catalogue(session: SessionDep) -> CatalogueResponse:
    return await get_catalogue(session)


@router.get("/availability", response_model=AvailabilityResponse)
async def availability(
    session: SessionDep,
    day: Annotated[date, Query(alias="date")],
    vehicle_count: Annotated[int, Query(ge=1, le=20)],
    service_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    addon_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> AvailabilityResponse:
    return await availability_for_date(
        session,
        day=day,
        vehicle_count=vehicle_count,
        service_ids=service_id,
        addon_ids=addon_id,
    )


@router.post("/holds", response_model=HoldResponse, status_code=201)
async def hold(request: HoldCreate, session: SessionDep) -> HoldResponse:
    async with session.begin():
        return await create_hold(session, request)


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def booking(
    request: BookingCreate,
    session: SessionDep,
    identity: Annotated[VerifiedIdentity | None, Depends(optional_identity)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)],
) -> BookingResponse:
    scope = str(identity.user_id) if identity else "public"
    request_hash = canonical_request_hash(request.model_dump(mode="json"))
    async with session.begin():
        existing = await find_idempotent_response(
            session,
            scope=scope,
            operation="create_booking",
            key=idempotency_key,
            request_hash=request_hash,
        )
        if existing is not None:
            retry_response = dict(existing.response_json)
            if existing.resource_id is None:
                raise RuntimeError("Booking idempotency record is missing its resource id")
            retry_response["management_token"] = create_management_token(existing.resource_id)
            return BookingResponse.model_validate(retry_response)
        response = await create_booking(session, request, identity)
        if response.business_id is None:
            raise RuntimeError("Created booking is missing its business")
        await bump_sync_revisions(
            session, response.business_id, "jobs", "schedule", "finance", "customers"
        )
        safe_response = response.model_dump(mode="json")
        safe_response.pop("management_token")
        store_idempotent_response(
            session,
            scope=scope,
            operation="create_booking",
            key=idempotency_key,
            request_hash=request_hash,
            response_status=201,
            response_json=safe_response,
            resource_id=response.id,
        )
        return response


@router.get(
    "/bookings/manage",
    response_model=BookingManagementResponse,
)
async def manage_booking(
    session: SessionDep,
    management_token: Annotated[
        str, Header(alias="X-Booking-Management-Token", min_length=60, max_length=80)
    ],
) -> BookingManagementResponse:
    booking_record = await load_managed_booking(session, management_token)
    return await booking_management_response(session, booking_record)


@router.get(
    "/bookings/manage/invoices/{invoice_id}",
    response_model=RevenueInvoiceView,
)
async def manage_invoice(
    invoice_id: uuid.UUID,
    session: SessionDep,
    management_token: Annotated[
        str, Header(alias="X-Booking-Management-Token", min_length=60, max_length=80)
    ],
) -> RevenueInvoiceView:
    booking_record = await load_managed_booking(session, management_token)
    return await managed_invoice(session, booking_id=booking_record.id, invoice_id=invoice_id)


@router.post(
    "/bookings/manage/cancellation-requests",
    response_model=CancellationRequestResponse,
    status_code=201,
)
async def cancellation_request(
    request: CancellationRequestCreate,
    session: SessionDep,
    management_token: Annotated[
        str, Header(alias="X-Booking-Management-Token", min_length=60, max_length=80)
    ],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=255)],
) -> CancellationRequestResponse:
    request_hash = canonical_request_hash(request.model_dump(mode="json"))
    async with session.begin():
        booking_record = await load_managed_booking(session, management_token, lock=True)
        existing = await find_idempotent_response(
            session,
            scope=f"booking:{booking_record.id}",
            operation="request_cancellation",
            key=idempotency_key,
            request_hash=request_hash,
        )
        if existing is not None:
            return CancellationRequestResponse.model_validate(existing.response_json)
        response = await request_booking_cancellation(session, booking_record, request)
        await bump_sync_revisions(session, booking_record.business_id, "jobs", "customers")
        store_idempotent_response(
            session,
            scope=f"booking:{booking_record.id}",
            operation="request_cancellation",
            key=idempotency_key,
            request_hash=request_hash,
            response_status=201,
            response_json=response.model_dump(mode="json"),
            resource_id=response.id,
        )
        return response
