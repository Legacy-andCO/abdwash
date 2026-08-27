import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    CancellationStatus,
    HoldStatus,
    JobStatus,
    LeaveStatus,
    LoyaltyRewardStatus,
    OutboxStatus,
    PaymentStatus,
    SlotStatus,
    StaffRole,
)
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Business(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class BusinessSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_settings"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Dubai")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AED")
    opening_time: Mapped[time] = mapped_column(Time, nullable=False)
    closing_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    multi_vehicle_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    multi_vehicle_required_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    cancellation_cutoff_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    hold_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    attendance_grace_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default=text("5")
    )
    loyalty_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    loyalty_required_washes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=9, server_default=text("9")
    )
    loyalty_reward_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL")
    )
    __table_args__ = (
        CheckConstraint("slot_duration_minutes > 0", name="positive_slot_duration"),
        CheckConstraint("multi_vehicle_threshold > 0", name="positive_vehicle_threshold"),
        CheckConstraint("multi_vehicle_required_slots > 0", name="positive_required_slots"),
        CheckConstraint("closing_time > opening_time", name="valid_business_hours"),
        CheckConstraint("attendance_grace_minutes >= 0", name="nonnegative_attendance_grace"),
        CheckConstraint("loyalty_required_washes > 0", name="positive_loyalty_required_washes"),
    )


class BusinessSyncRevision(Base):
    __tablename__ = "business_sync_revisions"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    jobs_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    workforce_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    schedule_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    finance_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    customers_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CustomerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_profiles"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    surname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    __table_args__ = (
        Index("ix_customer_profiles_business_email", "business_id", "email"),
        Index("ix_customer_profiles_business_phone", "business_id", "phone"),
    )


class CustomerAddress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_addresses"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    written_address: Mapped[str] = mapped_column(Text, nullable=False)
    location_url: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    location_instructions: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class StaffProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_profiles"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    auth_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=StaffRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    __table_args__ = (
        CheckConstraint("role IN ('employee','manager','admin')", name="staff_role"),
        CheckConstraint("username = lower(username)", name="staff_username_lowercase"),
        Index("uq_staff_profiles_username_ci", func.lower(username), unique=True),
        Index("ix_staff_profiles_business_active", "business_id", "is_active"),
    )


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id"), nullable=False
    )
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    vehicle_type: Mapped[str] = mapped_column(String(80), nullable=False)
    colour: Mapped[str | None] = mapped_column(String(80))
    plate_number: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    __table_args__ = (Index("ix_vehicles_customer_active", "customer_id", "is_active"),)


class Service(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    vehicle_applicability: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    checklist_template: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    __table_args__ = (
        CheckConstraint("price_minor >= 0", name="nonnegative_service_price"),
        Index("ix_services_business_active_sort", "business_id", "is_active", "sort_order"),
    )


class ServiceAddon(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_addons"

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    __table_args__ = (CheckConstraint("price_minor >= 0", name="nonnegative_addon_price"),)


class ScheduleResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_resources"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, default="mobile_team")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    __table_args__ = (UniqueConstraint("business_id", "name"),)


class TeamMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "team_memberships"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_resources.id", ondelete="CASCADE"), nullable=False
    )
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "staff_profile_id",
            name="uq_team_membership_resource_staff",
        ),
        Index("ix_team_memberships_staff_active", "staff_profile_id", "is_active"),
        Index(
            "ix_team_memberships_resource_active_staff",
            "resource_id",
            "is_active",
            "staff_profile_id",
        ),
    )


class AttendanceSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_sessions"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id", ondelete="CASCADE"), nullable=False
    )
    clock_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_in_client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out_client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "clock_out_at IS NULL OR clock_out_at >= clock_in_at",
            name="attendance_chronological",
        ),
        Index("ix_attendance_business_clock_in", "business_id", "clock_in_at"),
        Index("ix_attendance_staff_clock_in", "staff_profile_id", "clock_in_at"),
        Index(
            "uq_attendance_open_staff",
            "staff_profile_id",
            unique=True,
            postgresql_where=text("clock_out_at IS NULL"),
        ),
    )


class Shift(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_shift_business_name"),
        CheckConstraint("end_time > start_time", name="shift_time_order"),
    )


class StaffShiftAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_shift_assignments"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id", ondelete="CASCADE"), nullable=False
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schedule_resources.id"))
    __table_args__ = (
        UniqueConstraint("staff_profile_id", "work_date", name="uq_staff_shift_work_date"),
        Index("ix_shift_assignments_business_date", "business_id", "work_date"),
    )


class LeaveRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id", ondelete="CASCADE"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LeaveStatus.PENDING)
    reviewed_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="leave_date_order"),
        CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')", name="leave_status"
        ),
        Index("ix_leave_business_status_dates", "business_id", "status", "start_date"),
        Index("ix_leave_staff_dates", "staff_profile_id", "start_date", "end_date"),
    )


class SlotHoldGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "slot_hold_groups"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_resources.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=HoldStatus.ACTIVE)
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_slot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('active','consumed','expired','released')", name="hold_status"),
        Index("ix_hold_groups_expiry_status", "status", "expires_at"),
    )


class ScheduleSlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_slots"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_resources.id"), nullable=False
    )
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SlotStatus.FREE)
    hold_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("slot_hold_groups.id"))
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    blocked_reason: Mapped[str | None] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    __table_args__ = (
        UniqueConstraint("resource_id", "slot_start", name="uq_schedule_slot_resource_start"),
        CheckConstraint("status IN ('free','held','reserved','blocked')", name="slot_status"),
        Index("ix_schedule_slots_resource_start_status", "resource_id", "slot_start", "status"),
        Index("ix_schedule_slots_active_hold", "status", "hold_expires_at"),
    )


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    reference: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    customer_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer_profiles.id")
    )
    hold_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("slot_hold_groups.id"), unique=True, nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_resources.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payment_choice: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=PaymentStatus.UNPAID
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="web")
    customer_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_surname: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    written_address: Mapped[str] = mapped_column(Text, nullable=False)
    location_url: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    location_instructions: Mapped[str | None] = mapped_column(Text)
    management_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    __table_args__ = (
        CheckConstraint("vehicle_count > 0", name="positive_booking_vehicle_count"),
        CheckConstraint("total_amount_minor >= 0", name="nonnegative_booking_total"),
        CheckConstraint(
            "status IN ('pending_payment','confirmed','cancellation_requested',"
            "'cancelled','completed')",
            name="booking_status",
        ),
        CheckConstraint(
            "payment_choice IN ('pay_now','pay_after_service')", name="booking_payment_choice"
        ),
        CheckConstraint(
            "payment_status IN ('unpaid','pending','paid','failed','refund_pending','refunded')",
            name="booking_payment_status",
        ),
        Index("ix_bookings_schedule_status", "business_id", "scheduled_start", "status"),
        Index("ix_bookings_customer_history", "customer_profile_id", "created_at"),
    )


class BookingVehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_vehicles"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    vehicle_type: Mapped[str] = mapped_column(String(80), nullable=False)
    colour: Mapped[str | None] = mapped_column(String(80))
    plate_number: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("booking_id", "position"),)


class BookingService(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_services"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    booking_vehicle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_vehicles.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    service_name: Mapped[str] = mapped_column(String(160), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    list_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    discount_type: Mapped[str | None] = mapped_column(String(30))
    loyalty_reward_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loyalty_rewards.id", ondelete="SET NULL")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_booking_service_quantity"),
        CheckConstraint("list_price_minor >= 0", name="nonnegative_booking_service_list_price"),
        CheckConstraint("discount_minor >= 0", name="nonnegative_booking_service_discount"),
        CheckConstraint(
            "discount_minor <= list_price_minor * quantity",
            name="booking_service_discount_within_list_price",
        ),
        CheckConstraint(
            "discount_type IS NULL OR discount_type = 'loyalty_reward'",
            name="booking_service_discount_type",
        ),
        Index("ix_booking_services_booking_service", "booking_id", "service_id"),
    )


class LoyaltyReward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_rewards"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False
    )
    reward_service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    reward_service_name: Mapped[str] = mapped_column(String(160), nullable=False)
    reward_list_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    required_washes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LoyaltyRewardStatus.AVAILABLE
    )
    reserved_booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    reserved_booking_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_services.id"), unique=True
    )
    redeemed_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"))
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('available','reserved','redeemed')", name="loyalty_reward_status"
        ),
        CheckConstraint("reward_list_price_minor >= 0", name="nonnegative_reward_list_price"),
        CheckConstraint("required_washes > 0", name="positive_reward_required_washes"),
        Index(
            "ix_loyalty_rewards_business_customer_status",
            "business_id",
            "customer_profile_id",
            "status",
        ),
    )


class LoyaltyEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_events"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    booking_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("booking_vehicles.id"))
    reward_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loyalty_rewards.id"))
    actor_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('qualifying_wash','manual_credit','manual_debit',"
            "'reward_earned','reward_reserved','reward_released','reward_redeemed')",
            name="loyalty_event_type",
        ),
        CheckConstraint(
            "(event_type = 'manual_debit' AND quantity < 0) OR "
            "(event_type IN ('qualifying_wash','manual_credit') AND quantity > 0) OR "
            "(event_type LIKE 'reward_%' AND quantity = 0)",
            name="loyalty_event_quantity",
        ),
        UniqueConstraint("business_id", "source_key", name="uq_loyalty_event_source"),
        Index(
            "ix_loyalty_events_business_customer_created",
            "business_id",
            "customer_profile_id",
            "created_at",
        ),
    )


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id"), unique=True, nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    assigned_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedule_resources.id")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=JobStatus.UNASSIGNED)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('unassigned','assigned','en_route','arrived',"
            "'in_progress','completed','cancelled')",
            name="job_status",
        ),
        CheckConstraint(
            "status <> 'unassigned' OR "
            "(assigned_resource_id IS NULL AND assigned_staff_id IS NULL)",
            name="unassigned_jobs_have_no_assignment",
        ),
        Index("ix_jobs_staff_status_schedule", "assigned_staff_id", "status", "scheduled_start"),
        Index("ix_jobs_business_status", "business_id", "status"),
        Index(
            "ix_jobs_business_schedule_status",
            "business_id",
            "scheduled_start",
            "status",
        ),
        Index("ix_jobs_resource_schedule", "assigned_resource_id", "scheduled_start"),
    )


class JobEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_events"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    actor_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    server_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device_id: Mapped[str | None] = mapped_column(String(160))
    client_event_id: Mapped[str | None] = mapped_column(String(160))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("job_id", "client_event_id"),
        Index("ix_job_events_job_timestamp", "job_id", "server_timestamp"),
    )


class JobInspection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_inspections"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    condition_notes: Mapped[str | None] = mapped_column(Text)
    damage_category: Mapped[str | None] = mapped_column(String(40))
    damage_notes: Mapped[str | None] = mapped_column(Text)
    completed_by_staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id"), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    __table_args__ = (Index("ix_job_inspections_business_job", "business_id", "job_id"),)


class JobChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_checklist_items"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    booking_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_services.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    __table_args__ = (
        UniqueConstraint("job_id", "position", name="uq_job_checklist_position"),
        Index("ix_job_checklist_business_job", "business_id", "job_id"),
    )


class JobPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_photos"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by_staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id"), nullable=False
    )
    client_request_id: Mapped[str] = mapped_column(String(160), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "category IN ('before','after','damage','issue')", name="job_photo_category"
        ),
        CheckConstraint("status IN ('pending','ready')", name="job_photo_status"),
        UniqueConstraint("business_id", "client_request_id", name="uq_job_photo_business_request"),
        Index("ix_job_photos_business_job_status", "business_id", "job_id", "status"),
    )


class JobQualityIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_quality_issues"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    photo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_photos.id", ondelete="SET NULL")
    )
    created_by_staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id"), nullable=False
    )
    __table_args__ = (Index("ix_job_quality_issues_business_job", "business_id", "job_id"),)


class JobComplaint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_complaints"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    original_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    review_note: Mapped[str | None] = mapped_column(Text)
    created_by_staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_profiles.id"), nullable=False
    )
    reviewed_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correction_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), unique=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','under_review','resolved','rejected','rewash_approved')",
            name="job_complaint_status",
        ),
        Index("ix_job_complaints_business_job", "business_id", "original_job_id"),
    )


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=PaymentStatus.UNPAID)
    method: Mapped[str | None] = mapped_column(String(40))
    provider: Mapped[str | None] = mapped_column(String(80))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('unpaid','pending','paid','failed','refund_pending','refunded')",
            name="payment_status",
        ),
        CheckConstraint("amount_minor >= 0", name="nonnegative_payment_amount"),
        Index("ix_payments_booking", "booking_id"),
        Index(
            "ix_payments_paid_method_date",
            "status",
            "method",
            "paid_at",
            postgresql_where=text("status = 'paid'"),
        ),
        Index("ix_payments_provider_id", "provider", "provider_payment_id"),
    )


class PaymentTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_transactions"

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    client_event_id: Mapped[str | None] = mapped_column(String(160))
    cash_tendered_minor: Mapped[int | None] = mapped_column(Integer)
    cash_change_minor: Mapped[int | None] = mapped_column(Integer)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "(cash_tendered_minor IS NULL AND cash_change_minor IS NULL) OR "
            "(cash_tendered_minor IS NOT NULL AND cash_change_minor IS NOT NULL)",
            name="cash_tender_fields_together",
        ),
        CheckConstraint(
            "cash_tendered_minor IS NULL OR cash_tendered_minor >= amount_minor",
            name="cash_tender_covers_payment",
        ),
        CheckConstraint(
            "cash_change_minor IS NULL OR cash_change_minor >= 0",
            name="nonnegative_cash_change",
        ),
        CheckConstraint(
            "cash_tendered_minor IS NULL OR cash_change_minor = cash_tendered_minor - amount_minor",
            name="cash_change_matches_tender",
        ),
        UniqueConstraint("payment_id", "client_event_id", name="uq_payment_transaction_event"),
        Index("ix_payment_transactions_provider_id", "provider_transaction_id"),
    )


class CustomerPaymentMethod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_payment_methods"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_payment_method_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    card_brand: Mapped[str | None] = mapped_column(String(40))
    last_four: Mapped[str | None] = mapped_column(String(4))
    expiry_month: Mapped[int | None] = mapped_column(Integer)
    expiry_year: Mapped[int | None] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class CancellationRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cancellation_requests"

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    requester_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CancellationStatus.REQUESTED
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_profiles.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','approved','rejected')", name="cancellation_status"
        ),
        Index("ix_cancellations_status_created", "status", "created_at"),
    )


class NotificationOutbox(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_outbox"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=OutboxStatus.PENDING)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(160))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','sent','retry','failed')", name="outbox_status"
        ),
        CheckConstraint("channel IN ('email','whatsapp','push')", name="notification_channel"),
        Index("ix_notification_outbox_claim", "status", "next_attempt_at"),
        CheckConstraint("attempt_count >= 0", name="nonnegative_outbox_attempts"),
    )


class IdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "idempotency_records"

    scope: Mapped[str] = mapped_column(String(160), nullable=False)
    operation: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "scope", "operation", "idempotency_key", name="uq_idempotency_scope_operation_key"
        ),
        Index("ix_idempotency_expiry", "expires_at"),
    )


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    actor_auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    __table_args__ = (Index("ix_audit_business_occurred", "business_id", "occurred_at"),)
