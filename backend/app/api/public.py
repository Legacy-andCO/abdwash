from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import SessionDep, optional_identity
from app.auth.verifier import VerifiedIdentity
from app.schemas.public import (
    AvailabilityResponse,
    BookingCreate,
    BookingResponse,
    CatalogueResponse,
    HoldCreate,
    HoldResponse,
)
from app.services.bookings import create_booking
from app.services.catalogue import get_catalogue
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.scheduling import availability_for_date, create_hold

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/catalogue", response_model=CatalogueResponse)
async def catalogue(session: SessionDep) -> CatalogueResponse:
    return await get_catalogue(session)


@router.get("/availability", response_model=AvailabilityResponse)
async def availability(
    session: SessionDep,
    day: Annotated[date, Query(alias="date")],
    vehicle_count: Annotated[int, Query(ge=1, le=20)],
) -> AvailabilityResponse:
    return await availability_for_date(session, day=day, vehicle_count=vehicle_count)


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
            return BookingResponse.model_validate(existing.response_json)
        response = await create_booking(session, request, identity)
        safe_response = response.model_dump(mode="json")
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
