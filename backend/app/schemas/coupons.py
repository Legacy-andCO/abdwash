import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.catalogue import is_vehicle_type


class CouponStrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

COUPON_CODE_PATTERN = re.compile(r"^[A-Z0-9]{3,6}$")


def normalize_coupon_code(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Coupon code must be text.")
    normalized = value.upper()
    if not COUPON_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("Coupon codes must contain 3 to 6 letters or numbers.")
    return normalized


class CouponCodeRequest(CouponStrictRequest):
    code: str

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> str:
        return normalize_coupon_code(value)


class CouponCheckoutLine(CouponStrictRequest):
    position: int = Field(ge=1, le=20)
    service_id: uuid.UUID
    vehicle_type: str
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    loyalty_reward_id: uuid.UUID | None = None

    @field_validator("vehicle_type")
    @classmethod
    def canonical_vehicle_type(cls, value: str) -> str:
        if not is_vehicle_type(value):
            raise ValueError("Choose a supported vehicle type.")
        return value


class CouponValidationRequest(CouponCodeRequest):
    lines: list[CouponCheckoutLine] = Field(min_length=1, max_length=20)
    selected_line_position: int | None = Field(default=None, ge=1, le=20)

    @model_validator(mode="after")
    def unique_positions(self) -> "CouponValidationRequest":
        positions = [line.position for line in self.lines]
        if len(positions) != len(set(positions)):
            raise ValueError("Each booking line position must be unique.")
        if self.selected_line_position is not None and self.selected_line_position not in positions:
            raise ValueError("The selected booking line is not present.")
        return self


class CouponEligibleLine(BaseModel):
    position: int
    service_id: uuid.UUID
    service_name: str
    vehicle_type: str
    make: str
    model: str
    list_price_minor: int
    discount_minor: int


class CouponValidationResponse(BaseModel):
    coupon_id: uuid.UUID = Field(exclude=True)
    code: str
    discount_percent: int
    minimum_vehicle_count: int | None
    currency_code: str
    eligible_lines: list[CouponEligibleLine]
    selected_line_position: int | None
    discount_minor: int


class BookingCouponSelection(CouponCodeRequest):
    selected_line_position: int = Field(ge=1, le=20)


class CouponWrite(CouponCodeRequest):
    discount_percent: int = Field(ge=1, le=100)
    minimum_vehicle_count: int | None = Field(default=None, ge=1, le=20)
    service_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    vehicle_types: list[str] = Field(min_length=1, max_length=7)
    is_active: bool = True

    @model_validator(mode="after")
    def unique_eligibility(self) -> "CouponWrite":
        if len(self.service_ids) != len(set(self.service_ids)):
            raise ValueError("Each eligible service can be selected only once.")
        if len(self.vehicle_types) != len(set(self.vehicle_types)):
            raise ValueError("Each eligible vehicle type can be selected only once.")
        if any(not is_vehicle_type(value) for value in self.vehicle_types):
            raise ValueError("Choose only supported vehicle types.")
        return self


class CouponServiceView(BaseModel):
    id: uuid.UUID
    name: str


class CouponView(BaseModel):
    id: uuid.UUID
    code: str
    discount_percent: int
    minimum_vehicle_count: int | None
    is_active: bool
    services: list[CouponServiceView]
    vehicle_types: list[str]
    created_at: datetime
    updated_at: datetime


class CouponList(BaseModel):
    coupons: list[CouponView]


CouponFailureCode = Literal[
    "COUPON_INVALID",
    "COUPON_MINIMUM_VEHICLES",
    "COUPON_SERVICE_INELIGIBLE",
    "COUPON_VEHICLE_INELIGIBLE",
    "COUPON_LOYALTY_CONFLICT",
    "COUPON_LINE_INELIGIBLE",
]
