from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.phones import normalize_phone_number

MAX_EVIDENCE_BYTES = 1024 * 1024
MAX_EVIDENCE_FILES = 2
MAX_ENCODED_BYTES = ((MAX_EVIDENCE_BYTES + 2) // 3) * 4
MAX_COMPLAINT_BODY = MAX_ENCODED_BYTES * MAX_EVIDENCE_FILES + 32768

ComplaintCategory = Literal[
    "service", "damage", "belongings", "booking", "payment", "conduct", "privacy", "other"
]


class ComplaintEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: Annotated[str, StringConstraints(min_length=4, max_length=MAX_ENCODED_BYTES)]


class ComplaintSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    booking_reference: str | None = Field(default=None, max_length=64)
    service_date: date | None = None
    category: ComplaintCategory
    description: str = Field(min_length=10, max_length=4000)
    privacy_acknowledged: StrictBool
    revision: str = Field(min_length=1, max_length=80)
    language: Literal["en", "ar"]
    website: str = Field(default="", max_length=200)
    evidence: list[ComplaintEvidenceInput] = Field(
        default_factory=list, max_length=MAX_EVIDENCE_FILES
    )

    @field_validator("name", "description", "booking_reference", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        if isinstance(value, str):
            return "".join(
                char
                for char in value
                if char in "\n\t" or (char.isprintable() and char not in "\u2028\u2029")
            ).strip()
        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return normalize_phone_number(value) if value else None

    @model_validator(mode="after")
    def validate_submission(self) -> "ComplaintSubmission":
        if not self.email and not self.phone:
            raise ValueError("Provide an email or telephone number.")
        if not self.privacy_acknowledged or self.website:
            raise ValueError("Invalid complaint submission.")
        return self


class ComplaintReceipt(BaseModel):
    reference: str


class ComplaintSummary(ComplaintReceipt):
    category: ComplaintCategory
    created_at: datetime


class ComplaintDetail(ComplaintSummary):
    name: str
    email: str | None
    phone: str | None
    booking_reference: str | None
    service_date: date | None
    description: str
    language: str
    privacy_version: str
    attachment_count: int
    notification_status: str | None


class ComplaintDownload(BaseModel):
    url: str
    expires_in: int
