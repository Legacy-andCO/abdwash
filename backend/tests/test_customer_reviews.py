import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import BookingStatus
from app.domain.errors import ConflictError, DomainError
from app.models.entities import Booking, CustomerReview, GuestReviewVerificationAttempt
from app.schemas.reviews import (
    CustomerAccountDelete,
    ReviewSubmission,
)
from app.services.reviews import (
    _booking_id_from_review_token,
    _consume_guest_attempt,
    _create_review,
    _next_prompt_after,
    _public_name,
    _review_token,
)


def _booking(*, status: str = BookingStatus.COMPLETED) -> Booking:
    now = datetime.now(UTC)
    return Booking(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        reference=f"AW-{uuid.uuid4().hex[:8].upper()}",
        customer_profile_id=uuid.uuid4(),
        hold_group_id=uuid.uuid4(),
        resource_id=uuid.uuid4(),
        status=status,
        payment_choice="pay_after_service",
        payment_status="unpaid",
        scheduled_start=now - timedelta(hours=2),
        scheduled_end=now,
        vehicle_count=1,
        total_amount_minor=7_300,
        currency_code="AED",
        source="web",
        customer_first_name="Ahmad",
        customer_surname="Hassan",
        customer_email="private@example.com",
        customer_phone="+971501234567",
        written_address="Private address",
        location_url="https://www.google.com/maps",
        management_token_hash="x" * 64,
        created_at=now - timedelta(days=1),
    )


def test_review_schema_requires_valid_rating_and_limits_plain_comment() -> None:
    assert ReviewSubmission(
        booking_id=uuid.uuid4(), rating=5, comment="  Excellent service  "
    ).comment == "Excellent service"
    assert ReviewSubmission(booking_id=uuid.uuid4(), rating=4, comment="  ").comment is None
    for rating in (0, 6):
        with pytest.raises(ValidationError):
            ReviewSubmission(booking_id=uuid.uuid4(), rating=rating)
    with pytest.raises(ValidationError):
        ReviewSubmission(booking_id=uuid.uuid4(), rating=5, comment="x" * 1001)


def test_account_deletion_requires_deliberate_phrase() -> None:
    assert CustomerAccountDelete(confirmation="DELETE").confirmation == "DELETE"
    with pytest.raises(ValidationError):
        CustomerAccountDelete(confirmation="delete")


def test_public_reviewer_name_is_abbreviated() -> None:
    assert _public_name("Ahmad", "Hassan") == "Ahmad H."
    assert "Hassan" not in _public_name("Ahmad", "Hassan")


def test_prompt_threshold_is_always_between_one_and_three() -> None:
    assert {_next_prompt_after() for _ in range(100)} <= {1, 2, 3}


def test_guest_review_token_is_bound_to_device_and_booking() -> None:
    booking_id = uuid.uuid4()
    device_id = uuid.uuid4()
    token = _review_token(booking_id, hashlib.sha256(str(device_id).encode()).hexdigest())
    assert _booking_id_from_review_token(token, device_id) == booking_id
    with pytest.raises(DomainError) as raised:
        _booking_id_from_review_token(token, uuid.uuid4())
    assert raised.value.code == "REVIEW_AUTHORIZATION_INVALID"


def test_device_id_alone_is_not_guest_review_authorization() -> None:
    with pytest.raises(DomainError):
        _booking_id_from_review_token("not-a-review-token", uuid.uuid4())


@pytest.mark.asyncio
async def test_guest_review_submission_attempts_are_rate_limited() -> None:
    business_id = uuid.uuid4()
    attempt = GuestReviewVerificationAttempt(
        business_id=business_id,
        challenge_hash="a" * 64,
        device_id_hash="b" * 64,
        window_started_at=datetime.now(UTC),
        attempt_count=5,
    )
    scalar_result = MagicMock()
    scalar_result.one_or_none.return_value = attempt
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()

    with pytest.raises(DomainError) as raised:
        await _consume_guest_attempt(
            session,
            business_id=business_id,
            challenge_hash=attempt.challenge_hash,
            device_hash=attempt.device_id_hash,
            code="REVIEW_SUBMISSION_RATE_LIMITED",
        )

    assert raised.value.code == "REVIEW_SUBMISSION_RATE_LIMITED"
    assert raised.value.status_code == 429


@pytest.mark.asyncio
async def test_completed_booking_creates_public_safe_review() -> None:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[None, "Standard Wash"])
    session.flush = AsyncMock()

    def assign_id(review: CustomerReview) -> None:
        review.id = uuid.uuid4()

    session.add.side_effect = assign_id
    booking = _booking()
    result = await _create_review(
        session,
        booking,
        rating=5,
        comment="Excellent",
        customer_profile_id=booking.customer_profile_id,
        guest_device_id_hash=None,
    )

    assert result.rating == 5
    assert result.reviewer_display_name == "Ahmad H."
    assert result.service_name == "Standard Wash"
    assert set(result.model_dump()) == {
        "id",
        "rating",
        "comment",
        "reviewer_display_name",
        "service_name",
        "service_date",
        "published_at",
        "verified",
    }


@pytest.mark.asyncio
async def test_incomplete_or_duplicate_booking_cannot_be_reviewed() -> None:
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    with pytest.raises(ConflictError) as incomplete:
        await _create_review(
            session,
            _booking(status=BookingStatus.CONFIRMED),
            rating=5,
            comment=None,
            customer_profile_id=None,
            guest_device_id_hash=None,
        )
    assert incomplete.value.code == "REVIEW_NOT_AVAILABLE"

    session.scalar = AsyncMock(return_value=uuid.uuid4())
    with pytest.raises(ConflictError) as duplicate:
        await _create_review(
            session,
            _booking(),
            rating=5,
            comment=None,
            customer_profile_id=None,
            guest_device_id_hash=None,
        )
    assert duplicate.value.code == "REVIEW_ALREADY_SUBMITTED"
