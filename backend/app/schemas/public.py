import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafeBusinessSettings(BaseModel):
    timezone: str
    currency_code: str
    opening_time: time
    closing_time: time
    slot_duration_minutes: int
    multi_vehicle_threshold: int
    multi_vehicle_required_slots: int
    hold_duration_minutes: int
    cancellation_cutoff_hours: int


class ServicePublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price_minor: int
    currency_code: str
    estimated_duration_minutes: int


class CatalogueResponse(BaseModel):
    business_name: str
    settings: SafeBusinessSettings
    services: list[ServicePublic]


class AvailabilityResource(BaseModel):
    resource_id: uuid.UUID
    resource_name: str


class AvailabilitySlot(BaseModel):
    time: time
    starts_at: datetime
    ends_at: datetime
    available: bool
    required_slot_count: int
    resources: list[AvailabilityResource]
    unavailable_reason: str | None = None


class AvailabilityResponse(BaseModel):
    date: date
    timezone: str
    vehicle_count: int
    required_slot_count: int
    slots: list[AvailabilitySlot]


class HoldCreate(StrictRequest):
    date: date
    start_time: time
    vehicle_count: int = Field(ge=1, le=20)
    resource_id: uuid.UUID | None = None


class HoldResponse(BaseModel):
    hold_token: str
    resource_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    expires_at: datetime
    required_slot_count: int


class CustomerContact(StrictRequest):
    first_name: NonBlank = Field(max_length=100)
    surname: NonBlank = Field(max_length=100)
    email: EmailStr
    phone: NonBlank = Field(max_length=40)


class BookingLocation(StrictRequest):
    written_address: NonBlank = Field(max_length=2000)
    location_url: HttpUrl
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    instructions: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def coordinates_together(self) -> "BookingLocation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class BookingVehicleCreate(StrictRequest):
    vehicle_id: uuid.UUID | None = None
    make: NonBlank = Field(max_length=100)
    model: NonBlank = Field(max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2200)
    vehicle_type: NonBlank = Field(max_length=80)
    colour: str | None = Field(default=None, max_length=80)
    plate_number: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    service_id: uuid.UUID


class BookingCreate(StrictRequest):
    hold_token: Annotated[str, StringConstraints(min_length=32, max_length=255)]
    contact: CustomerContact
    location: BookingLocation
    vehicles: list[BookingVehicleCreate] = Field(min_length=1, max_length=20)
    payment_choice: Literal["pay_now", "pay_after_service"]
    source: Literal["web", "mobile", "admin"] = "web"


class BookingVehicleSummary(BaseModel):
    make: str
    model: str
    year: int | None
    vehicle_type: str
    colour: str | None
    plate_number: str | None
    service_name: str
    line_total_minor: int


class BookingResponse(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    payment_choice: str
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    vehicle_count: int
    total_amount_minor: int
    currency_code: str
    resource_id: uuid.UUID
    customer_first_name: str
    customer_surname: str
    written_address: str
    location_url: str
    location_instructions: str | None
    vehicles: list[BookingVehicleSummary]
    management_token: str


class BookingManagementResponse(BaseModel):
    reference: str
    status: str
    payment_choice: str
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    total_amount_minor: int
    currency_code: str
    customer_first_name: str
    customer_surname: str
    written_address: str
    location_url: str
    location_instructions: str | None
    vehicles: list[BookingVehicleSummary]
    cancellation_eligible: bool
    cancellation_cutoff_at: datetime
    cancellation_status: str | None
    timezone: str


class CancellationRequestCreate(StrictRequest):
    reason: str | None = Field(default=None, max_length=2000)


class CancellationRequestResponse(BaseModel):
    id: uuid.UUID
    status: str
    booking: BookingManagementResponse


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
