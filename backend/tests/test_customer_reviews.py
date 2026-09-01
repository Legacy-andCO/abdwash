import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus, LoyaltyEventType
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Booking,
    CustomerProfile,
    CustomerReview,
    GuestReviewVerificationAttempt,
    LoyaltyEvent,
)
from app.schemas.reviews import (
    CustomerAccountDelete,
    PublicReview,
    ReviewSubmission,
)
from app.services.reviews import (
    _booking_id_from_review_token,
    _consume_guest_attempt,
    _create_review,
    _next_prompt_after,
    _public_name,
    _review_token,
    hide_customer_review,
    public_review_summary,
    submit_customer_review,
    submit_managed_guest_review,
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
async def test_authenticated_one_star_review_receives_backend_confirmed_bonus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking()
    profile = CustomerProfile(
        id=booking.customer_profile_id,
        business_id=booking.business_id,
        auth_user_id=uuid.uuid4(),
        first_name="Ahmad",
        surname="Hassan",
        email="ahmad@example.com",
        phone="+971501234567",
    )
    scalar_result = MagicMock()
    scalar_result.one_or_none.return_value = booking
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=scalar_result)
    monkeypatch.setattr(
        "app.services.reviews.require_customer_profile",
        AsyncMock(return_value=profile),
    )
    review = PublicReview(
        id=uuid.uuid4(),
        rating=1,
        comment=None,
        reviewer_display_name="Ahmad H.",
        service_name="Standard Wash",
        service_date=booking.scheduled_start,
        published_at=datetime.now(UTC),
    )
    monkeypatch.setattr("app.services.reviews._create_review", AsyncMock(return_value=review))
    award = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.reviews.award_first_review_bonus", award)

    result = await submit_customer_review(
        session,
        VerifiedIdentity(user_id=profile.auth_user_id, claims={}),
        booking_id=booking.id,
        rating=1,
        comment=None,
    )

    assert result.rating == 1
    assert result.first_review_bonus_awarded is True
    award.assert_awaited_once_with(
        session,
        business_id=profile.business_id,
        customer_profile_id=profile.id,
        booking_id=booking.id,
    )


@pytest.mark.asyncio
async def test_guest_review_does_not_award_loyalty_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking()
    review = PublicReview(
        id=uuid.uuid4(),
        rating=5,
        comment=None,
        reviewer_display_name="Guest G.",
        service_name="Standard Wash",
        service_date=booking.scheduled_start,
        published_at=datetime.now(UTC),
    )
    monkeypatch.setattr("app.services.reviews._create_review", AsyncMock(return_value=review))
    award = AsyncMock()
    monkeypatch.setattr("app.services.reviews.award_first_review_bonus", award)

    result = await submit_managed_guest_review(
        MagicMock(spec=AsyncSession),
        booking,
        device_id=uuid.uuid4(),
        rating=5,
        comment=None,
    )

    assert result == review
    award.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_review_does_not_award_bonus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=BookingStatus.CONFIRMED)
    profile = CustomerProfile(
        id=booking.customer_profile_id,
        business_id=booking.business_id,
        auth_user_id=uuid.uuid4(),
        first_name="Ahmad",
        surname="Hassan",
        email="ahmad@example.com",
        phone="+971501234567",
    )
    scalar_result = MagicMock()
    scalar_result.one_or_none.return_value = booking
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=scalar_result)
    monkeypatch.setattr(
        "app.services.reviews.require_customer_profile",
        AsyncMock(return_value=profile),
    )
    award = AsyncMock()
    monkeypatch.setattr("app.services.reviews.award_first_review_bonus", award)

    with pytest.raises(ConflictError):
        await submit_customer_review(
            session,
            VerifiedIdentity(user_id=profile.auth_user_id, claims={}),
            booking_id=booking.id,
            rating=5,
            comment=None,
        )
    award.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_manager_hides_review_without_deleting_booking() -> None:
    booking_id = uuid.uuid4()
    review = CustomerReview(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        booking_id=booking_id,
        customer_profile_id=uuid.uuid4(),
        rating=2,
        comment="Needs improvement",
        reviewer_display_name="Noor A.",
        status="published",
        published_at=datetime.now(UTC),
    )
    bonus = LoyaltyEvent(
        business_id=review.business_id,
        customer_profile_id=review.customer_profile_id,
        event_type=LoyaltyEventType.FIRST_REVIEW_BONUS,
        quantity=1,
        booking_id=booking_id,
        source_key=f"first-review-bonus:{review.customer_profile_id}",
    )
    scalar_result = MagicMock()
    scalar_result.one_or_none.return_value = review
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()

    result = await hide_customer_review(
        session,
        business_id=review.business_id,
        review_id=review.id,
    )

    assert result.status == "hidden"
    assert review.status == "hidden"
    assert review.booking_id == booking_id
    assert bonus.quantity == 1
    session.flush.assert_awaited_once()
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_public_summary_count_and_rating_only_use_published_reviews(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.services.reviews.load_default_business",
        AsyncMock(return_value=SimpleNamespace(business=SimpleNamespace(id=business_id))),
    )
    aggregate_result = MagicMock()
    aggregate_result.one.return_value = (4.5, 2)
    rows_result = MagicMock()
    rows_result.all.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[aggregate_result, rows_result])

    summary = await public_review_summary(session)

    assert summary.average_rating == 4.5
    assert summary.total_count == 2
    for call in session.execute.await_args_list:
        params = call.args[0].compile().params
        assert "published" in params.values()
