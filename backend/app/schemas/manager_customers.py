import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.phones import normalize_phone_number
from app.schemas.customer import (
    CustomerAddressResponse,
    CustomerProfileResponse,
    CustomerVehicleResponse,
)
from app.schemas.loyalty import LoyaltySummary
from app.schemas.public import NonBlank, StrictRequest


class ManagerCustomerListItem(BaseModel):
    id: uuid.UUID
    first_name: str
    surname: str
    email: EmailStr
    phone: str
    active_vehicle_count: int
    booking_count: int
    latest_booking_at: datetime | None
    available_rewards: int
    loyalty_progress_washes: int
    loyalty_required_washes: int


class ManagerCustomerList(BaseModel):
    customers: list[ManagerCustomerListItem]
    next_offset: int | None


class ManagerCustomerUpdate(StrictRequest):
    first_name: NonBlank = Field(max_length=100)
    surname: NonBlank = Field(max_length=100)
    phone: NonBlank = Field(max_length=40)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> str:
        return normalize_phone_number(value)


class ManagerCustomerBookingVehicle(BaseModel):
    make: str
    model: str
    plate_number: str | None
    service_name: str | None


class ManagerCustomerBooking(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    payment_status: str
    scheduled_start: datetime
    total_amount_minor: int
    currency_code: str
    vehicle_count: int
    job_id: uuid.UUID | None
    job_status: str | None
    complaint_count: int
    vehicles: list[ManagerCustomerBookingVehicle]


class ManagerCustomerDetail(BaseModel):
    profile: CustomerProfileResponse
    addresses: list[CustomerAddressResponse]
    vehicles: list[CustomerVehicleResponse]
    bookings: list[ManagerCustomerBooking]
    bookings_next_offset: int | None
    loyalty: LoyaltySummary
