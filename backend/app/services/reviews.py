import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from sqlalchemy import case, delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.core.config import get_settings
from app.domain.enums import BookingStatus
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Booking,
    BookingService,
    CustomerProfile,
    CustomerReview,
    CustomerReviewPromptState,
    GuestReviewVerificationAttempt,
)
from app.repositories.business import load_default_business
from app.schemas.reviews import (
    GuestReviewVerificationResponse,
    PublicReview,
    PublicReviewList,
    PublicReviewSummary,
    ReviewEligibility,
    ReviewPromptOpenResponse,
)
from app.services.customer_profiles import require_customer_profile

REVIEW_TOKEN_TTL = timedelta(minutes=30)
VERIFICATION_WINDOW = timedelta(minutes=15)
MAX_VERIFICATION_ATTEMPTS = 5


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _public_name(first_name: str, surname: str) -> str:
    first = first_name.strip()
    family = surname.strip()
    if first and family:
        return f"{first} {family[0].upper()}."
    return first or "Trifecta Customer"


def _service_name_subquery() -> Any:
    return (
        select(BookingService.service_name)
        .where(BookingService.booking_id == Booking.id)
        .order_by(BookingService.created_at, BookingService.id)
        .limit(1)
        .scalar_subquery()
    )


def _review_view(review: CustomerReview, service_name: str, service_date: datetime) -> PublicReview:
    return PublicReview(
        id=review.id,
        rating=review.rating,
        comment=review.comment,
        reviewer_display_name=review.reviewer_display_name,
        service_name=service_name,
        service_date=service_date,
        published_at=review.published_at,
    )


async def public_review_summary(session: AsyncSession, *, limit: int = 3) -> PublicReviewSummary:
    configuration = await load_default_business(session)
    average, count = (
        await session.execute(
            select(func.avg(CustomerReview.rating), func.count(CustomerReview.id)).where(
                CustomerReview.business_id == configuration.business.id,
                CustomerReview.status == "published",
            )
        )
    ).one()
    rows = (
        await session.execute(
            select(CustomerReview, _service_name_subquery(), Booking.scheduled_start)
            .join(Booking, Booking.id == CustomerReview.booking_id)
            .where(
                CustomerReview.business_id == configuration.business.id,
                CustomerReview.status == "published",
            )
            .order_by(
                case(
                    (func.length(func.trim(CustomerReview.comment)) > 0, 0),
                    else_=1,
                ),
                CustomerReview.rating.desc(),
                CustomerReview.published_at.desc(),
            )
            .limit(limit)
        )
    ).all()
    return PublicReviewSummary(
        average_rating=round(float(average), 1) if average is not None else None,
        total_count=int(count or 0),
        featured_reviews=[_review_view(*row) for row in rows],
    )


async def list_public_reviews(
    session: AsyncSession, *, limit: int, offset: int
) -> PublicReviewList:
    configuration = await load_default_business(session)
    average, count = (
        await session.execute(
            select(func.avg(CustomerReview.rating), func.count(CustomerReview.id)).where(
                CustomerReview.business_id == configuration.business.id,
                CustomerReview.status == "published",
            )
        )
    ).one()
    rows = (
        await session.execute(
            select(CustomerReview, _service_name_subquery(), Booking.scheduled_start)
            .join(Booking, Booking.id == CustomerReview.booking_id)
            .where(
                CustomerReview.business_id == configuration.business.id,
                CustomerReview.status == "published",
            )
            .order_by(CustomerReview.published_at.desc(), CustomerReview.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return PublicReviewList(
        average_rating=round(float(average), 1) if average is not None else None,
        total_count=int(count or 0),
        reviews=[_review_view(*row) for row in rows],
    )


async def _eligibility_for_profile(
    session: AsyncSession, profile: CustomerProfile
) -> ReviewEligibility:
    service_name = _service_name_subquery()
    row = (
        await session.execute(
            select(Booking, service_name)
            .where(
                Booking.business_id == profile.business_id,
                Booking.customer_profile_id == profile.id,
                Booking.status == BookingStatus.COMPLETED,
                ~exists().where(CustomerReview.booking_id == Booking.id),
            )
            .order_by(Booking.scheduled_end.desc(), Booking.id.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return ReviewEligibility(eligible=False)
    booking, selected_service = row
    return ReviewEligibility(
        eligible=True,
        booking_id=booking.id,
        booking_reference=booking.reference,
        service_name=selected_service,
        service_date=booking.scheduled_start,
    )


async def customer_review_eligibility(
    session: AsyncSession, identity: VerifiedIdentity
) -> ReviewEligibility:
    profile = await require_customer_profile(session, identity)
    return await _eligibility_for_profile(session, profile)


async def _review_for_booking(
    session: AsyncSession, booking: Booking
) -> PublicReview | None:
    row = (
        await session.execute(
            select(CustomerReview, _service_name_subquery(), Booking.scheduled_start)
            .join(Booking, Booking.id == CustomerReview.booking_id)
            .where(CustomerReview.booking_id == booking.id)
        )
    ).one_or_none()
    return _review_view(*row) if row else None


async def review_eligibility_for_booking(
    session: AsyncSession, booking: Booking
) -> ReviewEligibility:
    existing = await _review_for_booking(session, booking)
    service_name = await session.scalar(
        select(BookingService.service_name)
        .where(BookingService.booking_id == booking.id)
        .order_by(BookingService.created_at, BookingService.id)
        .limit(1)
    )
    return ReviewEligibility(
        eligible=booking.status == BookingStatus.COMPLETED and existing is None,
        booking_id=booking.id,
        booking_reference=booking.reference,
        service_name=service_name,
        service_date=booking.scheduled_start,
        existing_review=existing,
    )


async def submit_customer_review(
    session: AsyncSession,
    identity: VerifiedIdentity,
    *,
    booking_id: uuid.UUID,
    rating: int,
    comment: str | None,
) -> PublicReview:
    profile = await require_customer_profile(session, identity, lock=True)
    booking = (
        await session.scalars(
            select(Booking)
            .where(
                Booking.id == booking_id,
                Booking.business_id == profile.business_id,
                Booking.customer_profile_id == profile.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if booking is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    return await _create_review(
        session,
        booking,
        rating=rating,
        comment=comment,
        customer_profile_id=profile.id,
        guest_device_id_hash=None,
    )


async def _create_review(
    session: AsyncSession,
    booking: Booking,
    *,
    rating: int,
    comment: str | None,
    customer_profile_id: uuid.UUID | None,
    guest_device_id_hash: str | None,
) -> PublicReview:
    if booking.status != BookingStatus.COMPLETED:
        raise ConflictError(
            "REVIEW_NOT_AVAILABLE", "A review is available after the service is completed."
        )
    existing_review_id = await session.scalar(
        select(CustomerReview.id).where(CustomerReview.booking_id == booking.id)
    )
    if existing_review_id:
        raise ConflictError("REVIEW_ALREADY_SUBMITTED", "This booking has already been reviewed.")
    review = CustomerReview(
        business_id=booking.business_id,
        booking_id=booking.id,
        customer_profile_id=customer_profile_id,
        rating=rating,
        comment=comment,
        reviewer_display_name=_public_name(
            booking.customer_first_name, booking.customer_surname
        ),
        status="published",
        published_at=datetime.now(UTC),
        guest_device_id_hash=guest_device_id_hash,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "REVIEW_ALREADY_SUBMITTED", "This booking has already been reviewed."
        ) from exc
    service_name = await session.scalar(
        select(BookingService.service_name)
        .where(BookingService.booking_id == booking.id)
        .order_by(BookingService.created_at, BookingService.id)
        .limit(1)
    )
    return _review_view(review, service_name or "Trifecta service", booking.scheduled_start)


def _next_prompt_after() -> int:
    return secrets.randbelow(3) + 1


async def record_customer_website_open(
    session: AsyncSession, identity: VerifiedIdentity
) -> ReviewPromptOpenResponse:
    profile = await require_customer_profile(session, identity, lock=True)
    eligibility = await _eligibility_for_profile(session, profile)
    if not eligibility.eligible:
        return ReviewPromptOpenResponse(show_prompt=False, eligibility=eligibility)
    state = (
        await session.scalars(
            select(CustomerReviewPromptState)
            .where(CustomerReviewPromptState.customer_profile_id == profile.id)
            .with_for_update()
        )
    ).one_or_none()
    if state is None:
        state = CustomerReviewPromptState(
            business_id=profile.business_id,
            customer_profile_id=profile.id,
            opens_since_last_prompt=0,
            next_prompt_after=_next_prompt_after(),
        )
        session.add(state)
        await session.flush()
    state.opens_since_last_prompt += 1
    show_prompt = state.opens_since_last_prompt >= state.next_prompt_after
    if show_prompt:
        state.opens_since_last_prompt = 0
        state.next_prompt_after = _next_prompt_after()
        state.last_prompted_at = datetime.now(UTC)
    await session.flush()
    return ReviewPromptOpenResponse(show_prompt=show_prompt, eligibility=eligibility)


def _review_token(booking_id: uuid.UUID, device_hash: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": "guest_review",
            "booking_id": str(booking_id),
            "device_hash": device_hash,
            "iat": now,
            "exp": now + REVIEW_TOKEN_TTL,
        },
        get_settings().booking_management_signing_key,
        algorithm="HS256",
    )


def _booking_id_from_review_token(token: str, device_id: uuid.UUID) -> uuid.UUID:
    try:
        claims = jwt.decode(
            token,
            get_settings().booking_management_signing_key,
            algorithms=["HS256"],
            options={"require": ["purpose", "booking_id", "device_hash", "exp"]},
        )
        expected_device_hash = _hash(str(device_id))
        if claims.get("purpose") != "guest_review" or not hmac.compare_digest(
            str(claims.get("device_hash", "")), expected_device_hash
        ):
            raise ValueError
        return uuid.UUID(str(claims["booking_id"]))
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise DomainError(
            "REVIEW_AUTHORIZATION_INVALID",
            "This review link is invalid or expired.",
            status_code=401,
        ) from exc


async def verify_guest_review_access(
    session: AsyncSession,
    *,
    booking_reference: str,
    phone: str,
    device_id: uuid.UUID,
) -> GuestReviewVerificationResponse:
    configuration = await load_default_business(session)
    reference = booking_reference.strip().upper()
    challenge_hash = _hash(reference)
    device_hash = _hash(str(device_id))
    attempt = await _consume_guest_attempt(
        session,
        business_id=configuration.business.id,
        challenge_hash=challenge_hash,
        device_hash=device_hash,
        code="REVIEW_VERIFICATION_RATE_LIMITED",
    )
    booking = (
        await session.scalars(
            select(Booking).where(
                Booking.business_id == configuration.business.id,
                Booking.reference == reference,
            )
        )
    ).one_or_none()
    if booking is None or not hmac.compare_digest(booking.customer_phone, phone):
        raise DomainError(
            "REVIEW_VERIFICATION_FAILED",
            "We could not verify that completed booking.",
            status_code=404,
        )
    eligibility = await review_eligibility_for_booking(session, booking)
    if not eligibility.eligible:
        if eligibility.existing_review is not None:
            raise ConflictError(
                "REVIEW_ALREADY_SUBMITTED", "This booking has already been reviewed."
            )
        raise ConflictError(
            "REVIEW_NOT_AVAILABLE", "A review is available after the service is completed."
        )
    await session.execute(
        delete(GuestReviewVerificationAttempt).where(
            GuestReviewVerificationAttempt.id == attempt.id
        )
    )
    return GuestReviewVerificationResponse(
        review_token=_review_token(booking.id, device_hash),
        eligibility=eligibility,
    )


async def _consume_guest_attempt(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    challenge_hash: str,
    device_hash: str,
    code: str,
) -> GuestReviewVerificationAttempt:
    now = datetime.now(UTC)
    attempt = (
        await session.scalars(
            select(GuestReviewVerificationAttempt)
            .where(
                GuestReviewVerificationAttempt.business_id == business_id,
                GuestReviewVerificationAttempt.challenge_hash == challenge_hash,
                GuestReviewVerificationAttempt.device_id_hash == device_hash,
            )
            .with_for_update()
        )
    ).one_or_none()
    if attempt is None:
        attempt = GuestReviewVerificationAttempt(
            business_id=business_id,
            challenge_hash=challenge_hash,
            device_id_hash=device_hash,
            window_started_at=now,
            attempt_count=0,
        )
        session.add(attempt)
        await session.flush()
    elif now - attempt.window_started_at >= VERIFICATION_WINDOW:
        attempt.window_started_at = now
        attempt.attempt_count = 0
    attempt.attempt_count += 1
    if attempt.attempt_count > MAX_VERIFICATION_ATTEMPTS:
        raise DomainError(
            code,
            "Too many attempts. Please wait before trying again.",
            status_code=429,
        )
    await session.flush()
    return attempt


async def consume_guest_review_submission_attempt(
    session: AsyncSession,
    *,
    authorization_proof: str,
    device_id: uuid.UUID,
) -> uuid.UUID:
    configuration = await load_default_business(session)
    attempt = await _consume_guest_attempt(
        session,
        business_id=configuration.business.id,
        challenge_hash=_hash(f"submission:{authorization_proof}"),
        device_hash=_hash(str(device_id)),
        code="REVIEW_SUBMISSION_RATE_LIMITED",
    )
    return attempt.id


async def clear_guest_review_submission_attempt(
    session: AsyncSession, attempt_id: uuid.UUID
) -> None:
    await session.execute(
        delete(GuestReviewVerificationAttempt).where(
            GuestReviewVerificationAttempt.id == attempt_id
        )
    )


async def submit_guest_review(
    session: AsyncSession,
    *,
    review_token: str,
    device_id: uuid.UUID,
    rating: int,
    comment: str | None,
) -> PublicReview:
    booking_id = _booking_id_from_review_token(review_token, device_id)
    booking = (
        await session.scalars(select(Booking).where(Booking.id == booking_id).with_for_update())
    ).one_or_none()
    if booking is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    return await _create_review(
        session,
        booking,
        rating=rating,
        comment=comment,
        customer_profile_id=booking.customer_profile_id,
        guest_device_id_hash=_hash(str(device_id)),
    )


async def submit_managed_guest_review(
    session: AsyncSession,
    booking: Booking,
    *,
    device_id: uuid.UUID,
    rating: int,
    comment: str | None,
) -> PublicReview:
    return await _create_review(
        session,
        booking,
        rating=rating,
        comment=comment,
        customer_profile_id=booking.customer_profile_id,
        guest_device_id_hash=_hash(str(device_id)),
    )
