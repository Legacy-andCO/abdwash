import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import SessionDep, optional_identity
from app.auth.verifier import VerifiedIdentity
from app.domain.errors import DomainError
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
from app.schemas.reviews import (
    GuestReviewSubmission,
    GuestReviewVerification,
    GuestReviewVerificationResponse,
    PublicReview,
    PublicReviewList,
    PublicReviewSummary,
    ReviewEligibility,
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
from app.services.reviews import (
    clear_guest_review_submission_attempt,
    consume_guest_review_submission_attempt,
    list_public_reviews,
    public_review_summary,
    review_eligibility_for_booking,
    submit_guest_review,
    submit_managed_guest_review,
    verify_guest_review_access,
)
from app.services.scheduling import availability_for_date, create_hold
from app.services.sync_state import bump_sync_revisions

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/catalogue", response_model=CatalogueResponse)
async def catalogue(session: SessionDep) -> CatalogueResponse:
    return await get_catalogue(session)


@router.get("/reviews/summary", response_model=PublicReviewSummary)
async def reviews_summary(session: SessionDep) -> PublicReviewSummary:
    return await public_review_summary(session)


@router.get("/reviews", response_model=PublicReviewList)
async def reviews(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicReviewList:
    return await list_public_reviews(session, limit=limit, offset=offset)


@router.get("/reviews/guest/eligibility", response_model=ReviewEligibility)
async def guest_review_eligibility(
    session: SessionDep,
    management_token: Annotated[
        str, Header(alias="X-Booking-Management-Token", min_length=60, max_length=80)
    ],
) -> ReviewEligibility:
    booking_record = await load_managed_booking(session, management_token)
    return await review_eligibility_for_booking(session, booking_record)


@router.post(
    "/reviews/guest/verify",
    response_model=GuestReviewVerificationResponse,
)
async def guest_review_verify(
    payload: GuestReviewVerification, session: SessionDep
) -> GuestReviewVerificationResponse:
    verification_error: DomainError | None = None
    response: GuestReviewVerificationResponse | None = None
    async with session.begin():
        try:
            response = await verify_guest_review_access(
                session,
                booking_reference=payload.booking_reference,
                phone=payload.phone,
                device_id=payload.device_id,
            )
        except DomainError as exc:
            # Failed verification attempts are security state and must commit even
            # though the caller receives a domain error.
            verification_error = exc
    if verification_error is not None:
        raise verification_error
    if response is None:
        raise RuntimeError("Guest review verification returned no result")
    return response


@router.post("/reviews/guest/submit", response_model=PublicReview, status_code=201)
async def guest_review_submit(
    payload: GuestReviewSubmission,
    session: SessionDep,
    management_token: Annotated[
        str | None, Header(alias="X-Booking-Management-Token", min_length=60, max_length=80)
    ] = None,
) -> PublicReview:
    submission_error: DomainError | None = None
    response: PublicReview | None = None
    async with session.begin():
        proof = management_token or payload.review_token or "missing"
        attempt_id = await consume_guest_review_submission_attempt(
            session,
            authorization_proof=proof,
            device_id=payload.device_id,
        )
        try:
            if management_token:
                booking_record = await load_managed_booking(
                    session, management_token, lock=True
                )
                response = await submit_managed_guest_review(
                    session,
                    booking_record,
                    device_id=payload.device_id,
                    rating=payload.rating,
                    comment=payload.comment,
                )
            elif payload.review_token:
                response = await submit_guest_review(
                    session,
                    review_token=payload.review_token,
                    device_id=payload.device_id,
                    rating=payload.rating,
                    comment=payload.comment,
                )
            else:
                raise DomainError(
                    "REVIEW_AUTHORIZATION_REQUIRED",
                    "Verify a completed booking before leaving a review.",
                    status_code=401,
                )
        except DomainError as exc:
            # Authorization failures commit the hashed limiter state while the
            # original safe domain response is returned to the caller.
            submission_error = exc
        else:
            await clear_guest_review_submission_attempt(session, attempt_id)
    if submission_error is not None:
        raise submission_error
    if response is None:
        raise RuntimeError("Guest review submission returned no result")
    return response


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
