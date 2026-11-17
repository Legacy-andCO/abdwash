import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import SessionDep, StaffContext, staff_context
from app.core.config import get_settings
from app.domain.errors import DomainError
from app.repositories.business import load_staff_business
from app.schemas.calendar_bookings import (
    CalendarDoubleBookingCreate,
    NormalStaffBookingCreate,
    StaffBookingCatalogue,
    StaffBookingCreate,
    StaffBookingReceipt,
)
from app.schemas.public import AvailabilityResponse
from app.services.calendar_bookings import book_from_calendar, calendar_booking_team_scope
from app.services.catalogue import get_catalogue
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.policy_acceptance import POLICY_REVISION
from app.services.scheduling import availability_for_date
from app.services.sync_state import bump_sync_revisions

router = APIRouter(prefix="/api/v1/staff/calendar-bookings", tags=["staff"])
Staff = Annotated[StaffContext, Depends(staff_context)]


@router.get("/catalogue", response_model=StaffBookingCatalogue)
async def catalogue(session: SessionDep, context: Staff) -> StaffBookingCatalogue:
    configuration = await load_staff_business(session, context.business_id)
    result = await get_catalogue(session, configuration)
    return StaffBookingCatalogue(
        **result.model_dump(),
        policy_revision=POLICY_REVISION,
        public_web_url=get_settings().public_web_url,
    )


@router.get("/availability", response_model=AvailabilityResponse)
async def availability(
    session: SessionDep,
    context: Staff,
    day: Annotated[date, Query(alias="date")],
    service_ids: Annotated[list[uuid.UUID], Query(alias="service_id", min_length=1, max_length=20)],
    addon_ids: Annotated[list[uuid.UUID] | None, Query(alias="addon_id", max_length=200)] = None,
) -> AvailabilityResponse:
    configuration = await load_staff_business(session, context.business_id)
    result = await availability_for_date(
        session,
        day=day,
        vehicle_count=len(service_ids),
        service_ids=service_ids,
        addon_ids=addon_ids,
        configuration=configuration,
        allowed_team_ids=await calendar_booking_team_scope(session, context),
    )
    result.slots = [slot for slot in result.slots if slot.available]
    return result


@router.post("", response_model=StaffBookingReceipt, status_code=201)
async def create(
    payload: NormalStaffBookingCreate,
    session: SessionDep,
    context: Staff,
    idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
) -> StaffBookingReceipt:
    return await _create(payload, session, context, idempotency_key, "staff_calendar_booking")


@router.post("/{job_id}/double-book", response_model=StaffBookingReceipt, status_code=201)
async def double_book(
    job_id: uuid.UUID,
    payload: CalendarDoubleBookingCreate,
    session: SessionDep,
    context: Staff,
    idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
) -> StaffBookingReceipt:
    if payload.overlap.job_id != job_id:
        raise DomainError(
            "APPOINTMENT_NOT_FOUND", "The selected appointment is unavailable.", status_code=404
        )
    return await _create(
        payload, session, context, idempotency_key, "staff_calendar_double_booking"
    )


async def _create(
    payload: StaffBookingCreate,
    session: SessionDep,
    context: Staff,
    idempotency_key: uuid.UUID,
    operation: str,
) -> StaffBookingReceipt:
    scope = f"{context.business_id}:{context.staff_id}"
    key = str(idempotency_key)
    request_hash = canonical_request_hash(payload.model_dump(mode="json"))
    async with session.begin():
        existing = await find_idempotent_response(
            session,
            scope=scope,
            operation=operation,
            key=key,
            request_hash=request_hash,
        )
        if existing:
            return StaffBookingReceipt.model_validate(existing.response_json)
        configuration = await load_staff_business(session, context.business_id)
        result = await book_from_calendar(session, context, configuration, payload)
        await bump_sync_revisions(
            session, context.business_id, "jobs", "schedule", "finance", "customers"
        )
        store_idempotent_response(
            session,
            scope=scope,
            operation=operation,
            key=key,
            request_hash=request_hash,
            response_status=201,
            response_json=result.model_dump(mode="json"),
            resource_id=result.id,
        )
        return result
