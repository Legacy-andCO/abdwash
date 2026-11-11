import uuid
from datetime import date as Date
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import (
    EmailStr,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.phones import normalize_phone_number
from app.schemas.public import BookingVehicleCreate, CatalogueResponse, StrictRequest

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class AssistedContact(StrictRequest):
    first_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    surname: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    phone: str = Field(max_length=40)
    email: EmailStr | None = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_phone_number(value)


class AssistedLocation(StrictRequest):
    written_address: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)
    ]
    instructions: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinate_pair(self) -> "AssistedLocation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both coordinates or leave both blank.")
        return self


class AssistedVehicle(BookingVehicleCreate):
    make: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    model: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    plate_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ""

    @model_validator(mode="after")
    def no_account_only_selections(self) -> "AssistedVehicle":
        if self.vehicle_id is not None or self.loyalty_reward_id is not None:
            raise ValueError("Saved vehicles and rewards require customer checkout.")
        return self


class AppointmentOverlap(StrictRequest):
    team_id: uuid.UUID
    confirmed: StrictBool


class StaffBookingCreate(StrictRequest):
    date: Date
    time: time
    contact: AssistedContact
    location: AssistedLocation
    vehicles: list[AssistedVehicle] = Field(min_length=1, max_length=20)
    expected_amount_minor: int = Field(ge=0)
    policy_revision: str = Field(min_length=1, max_length=80)
    policy_delivery: Literal["provided", "email"]
    language: Literal["en", "ar"] = "en"
    overlap: AppointmentOverlap | None = None

    @model_validator(mode="after")
    def validate_confirmation(self) -> "StaffBookingCreate":
        if self.time.tzinfo is not None:
            raise ValueError("Enter a local appointment time.")
        if self.policy_delivery == "email" and not self.contact.email:
            raise ValueError("Enter an email address to send the policies.")
        if self.overlap and not self.overlap.confirmed:
            raise ValueError("Explicitly confirm the overlapping appointment.")
        return self


class StaffBookingCatalogue(CatalogueResponse):
    policy_revision: str
    public_web_url: str | None


class StaffBookingReceipt(StrictRequest):
    id: uuid.UUID
    job_id: uuid.UUID
    reference: str
    scheduled_start: datetime
    scheduled_end: datetime
    total_amount_minor: int
    capacity_exception: bool
