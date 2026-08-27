import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.domain.phones import normalize_phone_number
from app.schemas.loyalty import LoyaltySummary
from app.schemas.public import (
    BookingLocation,
    BookingVehicleSummary,
    NonBlank,
    StrictRequest,
)


class CustomerProfileResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    surname: str
    email: EmailStr
    phone: str


class CustomerContextResponse(BaseModel):
    profile: CustomerProfileResponse | None
    booking_count: int


class CustomerProfileUpdate(StrictRequest):
    first_name: NonBlank = Field(max_length=100)
    surname: NonBlank = Field(max_length=100)
    phone: NonBlank = Field(max_length=40)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> str:
        return normalize_phone_number(value)


class CustomerAddressWrite(BookingLocation):
    label: NonBlank = Field(max_length=80)
    is_default: bool = False


class CustomerAddressResponse(BaseModel):
    id: uuid.UUID
    label: str
    written_address: str
    location_url: str
    latitude: float | None
    longitude: float | None
    location_instructions: str | None
    is_default: bool


class CustomerVehicleWrite(StrictRequest):
    make: NonBlank = Field(max_length=100)
    model: NonBlank = Field(max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2200)
    vehicle_type: NonBlank = Field(max_length=80)
    colour: str | None = Field(default=None, max_length=80)
    plate_number: NonBlank = Field(max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


class CustomerVehicleResponse(BaseModel):
    id: uuid.UUID
    make: str
    model: str
    year: int | None
    vehicle_type: str
    colour: str | None
    plate_number: str | None
    notes: str | None


class CustomerProfileBootstrap(BaseModel):
    authenticated_email: EmailStr
    profile: CustomerProfileResponse | None
    addresses: list[CustomerAddressResponse]
    vehicles: list[CustomerVehicleResponse]
    loyalty: LoyaltySummary | None = None


class CustomerBookingStatus(BaseModel):
    key: str
    label: str
    stage: int
    job_status: str | None


class CustomerBookingSummary(BaseModel):
    id: uuid.UUID
    reference: str
    status: CustomerBookingStatus
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    vehicle_count: int
    total_amount_minor: int
    currency_code: str
    written_address: str
    vehicles: list[BookingVehicleSummary]
    created_at: datetime
    cancellation_eligible: bool
    reschedule_eligible: bool
    estimated_arrival_at: datetime | None = None
    category: str


class CustomerBookingListResponse(BaseModel):
    bookings: list[CustomerBookingSummary]


class CustomerBookingDetail(CustomerBookingSummary):
    payment_choice: str
    payment_status: str
    location_url: str
    location_instructions: str | None
    latitude: float | None
    longitude: float | None
    cancellation_cutoff_at: datetime
    cancellation_status: str | None
    timezone: str


class CustomerBookingActionResponse(BaseModel):
    booking: CustomerBookingDetail


class CustomerCancellationCreate(StrictRequest):
    reason: str | None = Field(default=None, max_length=2000)


class CustomerRescheduleCreate(StrictRequest):
    hold_token: Annotated[str, StringConstraints(min_length=32, max_length=255)]


class ManagerRescheduleCreate(CustomerRescheduleCreate):
    confirm_active_reschedule: bool = False
