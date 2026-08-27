import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.public import StrictRequest


class LoyaltyRewardService(BaseModel):
    id: uuid.UUID
    name: str


class LoyaltyRewardView(BaseModel):
    id: uuid.UUID
    service: LoyaltyRewardService
    list_price_minor: int
    status: str
    created_at: datetime
    reserved_at: datetime | None
    redeemed_at: datetime | None


class LoyaltyHistoryItem(BaseModel):
    id: uuid.UUID
    event_type: str
    quantity: int
    reason: str | None
    booking_reference: str | None
    vehicle_label: str | None
    created_at: datetime


class LoyaltySummary(BaseModel):
    enabled: bool
    configured: bool
    required_washes: int
    progress_washes: int
    washes_remaining: int
    lifetime_qualifying_washes: int
    available_rewards: int
    reserved_rewards: int
    redeemed_rewards: int
    reward_service: LoyaltyRewardService | None
    rewards: list[LoyaltyRewardView] = Field(default_factory=list)
    history: list[LoyaltyHistoryItem] = Field(default_factory=list)


class LoyaltySettingsView(BaseModel):
    enabled: bool
    required_washes: int
    reward_service: LoyaltyRewardService | None


class LoyaltySettingsUpdate(StrictRequest):
    enabled: bool
    required_washes: int = Field(ge=1, le=100)
    reward_service_id: uuid.UUID | None


class LoyaltyAdjustment(StrictRequest):
    direction: Literal["credit", "debit"]
    washes: int = Field(ge=1, le=100)
    reason: str = Field(min_length=2, max_length=1000)
    client_event_id: str = Field(min_length=8, max_length=160)
