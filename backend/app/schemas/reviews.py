import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.phones import normalize_phone_number
from app.schemas.public import NonBlank, StrictRequest


class ReviewSubmission(StrictRequest):
    booking_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class GuestReviewVerification(StrictRequest):
    booking_reference: NonBlank = Field(max_length=20)
    phone: NonBlank = Field(max_length=40)
    device_id: uuid.UUID

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> str:
        return normalize_phone_number(value)


class GuestReviewSubmission(StrictRequest):
    review_token: str | None = Field(default=None, min_length=40, max_length=1000)
    device_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class PublicReview(BaseModel):
    id: uuid.UUID
    rating: int
    comment: str | None
    reviewer_display_name: str
    service_name: str
    service_date: datetime
    published_at: datetime
    verified: bool = True


class PublicReviewSummary(BaseModel):
    average_rating: float | None
    total_count: int
    featured_reviews: list[PublicReview]


class PublicReviewList(BaseModel):
    average_rating: float | None
    total_count: int
    reviews: list[PublicReview]


class ReviewEligibility(BaseModel):
    eligible: bool
    booking_id: uuid.UUID | None = None
    booking_reference: str | None = None
    service_name: str | None = None
    service_date: datetime | None = None
    existing_review: PublicReview | None = None


class ReviewPromptOpenResponse(BaseModel):
    show_prompt: bool
    eligibility: ReviewEligibility


class GuestReviewVerificationResponse(BaseModel):
    review_token: str
    eligibility: ReviewEligibility


class CustomerAccountDelete(StrictRequest):
    confirmation: str = Field(min_length=6, max_length=6)

    @field_validator("confirmation")
    @classmethod
    def require_confirmation(cls, value: str) -> str:
        if value != "DELETE":
            raise ValueError("Type DELETE to confirm account deletion.")
        return value
