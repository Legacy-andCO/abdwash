import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.public import StrictRequest


class StaffVehicle(BaseModel):
    make: str
    model: str
    year: int | None
    vehicle_type: str
    colour: str | None
    plate_number: str | None
    notes: str | None
    service_name: str
    amount_minor: int


class JobTimelineEvent(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    event: str
    actor: str | None
    detail: str | None = None


class StaffJob(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    booking_reference: str
    assigned_staff_id: uuid.UUID | None
    assigned_staff_name: str | None
    assigned_team_id: uuid.UUID | None = None
    assigned_team_name: str | None = None
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    en_route_at: datetime | None
    estimated_arrival_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    customer_name: str
    customer_phone: str
    written_address: str
    location_url: str
    latitude: float | None
    longitude: float | None
    location_instructions: str | None
    payment_status: str
    payment_method: str | None
    total_amount_minor: int
    currency_code: str
    vehicles: list[StaffVehicle]
    timeline: list[JobTimelineEvent] = Field(default_factory=list)


class StaffJobList(BaseModel):
    jobs: list[StaffJob]
    next_offset: int | None


class JobInspectionInput(StrictRequest):
    condition_notes: str | None = Field(default=None, max_length=4000)
    damage_category: (
        Literal[
            "scratch",
            "dent",
            "paint_damage",
            "wheel_damage",
            "glass_damage",
            "interior_damage",
            "stain",
            "other",
        ]
        | None
    ) = None
    damage_notes: str | None = Field(default=None, max_length=4000)


class JobInspectionView(BaseModel):
    id: uuid.UUID
    condition_notes: str | None
    damage_category: str | None
    damage_notes: str | None
    completed_by_staff_id: uuid.UUID
    completed_by_staff_name: str
    completed_at: datetime


class JobChecklistUpdateItem(StrictRequest):
    id: uuid.UUID
    completed: bool


class JobChecklistUpdate(StrictRequest):
    items: list[JobChecklistUpdateItem] = Field(min_length=1, max_length=100)
    client_event_id: str = Field(min_length=8, max_length=160)


class JobChecklistItemView(BaseModel):
    id: uuid.UUID
    label: str
    is_required: bool
    position: int
    completed_at: datetime | None
    completed_by_staff_id: uuid.UUID | None
    completed_by_staff_name: str | None


class JobPhotoCreate(StrictRequest):
    category: Literal["before", "after", "damage", "issue"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    caption: str | None = Field(default=None, max_length=500)
    client_request_id: str = Field(min_length=8, max_length=160)


class JobPhotoView(BaseModel):
    id: uuid.UUID
    category: str
    caption: str | None
    status: str
    created_by_staff_id: uuid.UUID
    created_by_staff_name: str
    created_at: datetime
    access_url: str | None = None


class JobPhotoUploadGrant(BaseModel):
    photo: JobPhotoView
    bucket: str
    path: str
    upload_token: str
    max_bytes: int


class JobQualityIssueCreate(StrictRequest):
    category: Literal[
        "pre_existing_damage",
        "incomplete_result",
        "paint_damage",
        "access_problem",
        "customer_request",
        "other",
    ]
    note: str = Field(min_length=2, max_length=4000)
    photo_id: uuid.UUID | None = None


class JobQualityIssueView(BaseModel):
    id: uuid.UUID
    category: str
    note: str
    photo_id: uuid.UUID | None
    created_by_staff_id: uuid.UUID
    created_by_staff_name: str
    created_at: datetime


class JobComplaintCreate(StrictRequest):
    description: str = Field(min_length=2, max_length=4000)


class JobComplaintReview(StrictRequest):
    decision: Literal["under_review", "resolved", "rejected", "approve_rewash"]
    review_note: str | None = Field(default=None, max_length=4000)
    hold_token: str | None = Field(default=None, min_length=20, max_length=300)

    @model_validator(mode="after")
    def require_rewash_hold(self) -> "JobComplaintReview":
        if self.decision == "approve_rewash" and not self.hold_token:
            raise ValueError("A reserved correction appointment is required.")
        if self.decision != "approve_rewash" and self.hold_token:
            raise ValueError("A hold token is valid only when approving a rewash.")
        return self


class JobComplaintView(BaseModel):
    id: uuid.UUID
    description: str
    status: str
    review_note: str | None
    created_by_staff_id: uuid.UUID
    created_by_staff_name: str
    created_at: datetime
    reviewed_by_staff_id: uuid.UUID | None
    reviewed_by_staff_name: str | None
    reviewed_at: datetime | None
    correction_job_id: uuid.UUID | None


class JobQualityView(BaseModel):
    job_id: uuid.UUID
    inspection: JobInspectionView | None
    checklist: list[JobChecklistItemView]
    photos: list[JobPhotoView]
    issues: list[JobQualityIssueView]
    complaints: list[JobComplaintView]
    required_completed: int
    required_total: int
    before_photo_count: int
    after_photo_count: int
    issue_count: int
    can_complete: bool


class SyncState(BaseModel):
    jobs: int = Field(ge=0)
    workforce: int = Field(ge=0)
    schedule: int = Field(ge=0)
    finance: int = Field(ge=0)
    customers: int = Field(default=0, ge=0)


class Coordinates(StrictRequest):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class JobAction(StrictRequest):
    client_event_id: str = Field(min_length=8, max_length=160)
    client_timestamp: datetime | None = None


class CashTenderAction(JobAction):
    tendered_minor: int = Field(ge=0)
    change_minor: int = Field(ge=0)


class CashPaymentResult(BaseModel):
    job: StaffJob
    amount_applied_minor: int
    tendered_minor: int
    change_minor: int


class StartTripAction(JobAction):
    origin: Coordinates | None = None


class AssignmentAction(JobAction):
    staff_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    expected_version: int | None = Field(default=None, ge=1)
    confirm_active_reassignment: bool = False

    @model_validator(mode="after")
    def require_assignment_target(self) -> "AssignmentAction":
        if self.staff_id is None and self.team_id is None:
            raise ValueError("A staff member or team is required.")
        return self


class StaffMember(BaseModel):
    id: uuid.UUID
    display_name: str
    username: str = ""
    phone: str | None = None
    role: str
    is_active: bool = True
    assigned_jobs_today: int
    current_job_reference: str | None
    current_job_status: str | None


class CancellationReview(JobAction):
    decision: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)


class CancellationItem(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    booking_reference: str
    customer_name: str
    reason: str | None
    requested_at: datetime
    scheduled_start: datetime
    payment_status: str
    status: str


class ReportSummary(BaseModel):
    start_date: date
    end_date: date
    bookings: int
    completed_washes: int
    booked_sales_minor: int
    collected_revenue_minor: int
    outstanding_minor: int
    average_booking_value_minor: int
    currency_code: str


class TeamReference(BaseModel):
    id: uuid.UUID
    name: str


class StaffProfileView(BaseModel):
    id: uuid.UUID
    display_name: str
    username: str
    phone: str | None
    role: str
    is_active: bool
    must_change_password: bool = False
    teams: list[TeamReference] = Field(default_factory=list)


class OwnProfileUpdate(StrictRequest):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class StaffAccountCreate(StrictRequest):
    display_name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=3, max_length=32)
    phone: str | None = Field(default=None, max_length=40)
    role: str = Field(pattern="^(employee|manager)$")
    temporary_password: str = Field(min_length=8, max_length=128)


class StaffAccountUpdate(StrictRequest):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    role: str | None = Field(default=None, pattern="^(employee|manager)$")
    is_active: bool | None = None


class TemporaryPasswordUpdate(StrictRequest):
    temporary_password: str = Field(min_length=8, max_length=128)


class StaffPasswordReset(StrictRequest):
    mode: Literal["temporary", "manual"]
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_password_mode(self) -> "StaffPasswordReset":
        if self.mode == "manual" and self.new_password is None:
            raise ValueError("A new password is required for a manual reset.")
        if self.mode == "temporary" and self.new_password is not None:
            raise ValueError("A temporary reset generates its password on the server.")
        return self


class StaffPasswordResetResult(BaseModel):
    must_change_password: bool
    temporary_password: str | None = None


class TeamCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=160)


class TeamUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    is_active: bool | None = None


class TeamMembersUpdate(StrictRequest):
    staff_ids: list[uuid.UUID] = Field(max_length=100)


class TeamSummary(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    member_count: int
    jobs_today: int
    active_job_reference: str | None
    active_job_status: str | None


class TeamDetail(TeamSummary):
    members: list[StaffProfileView]
    jobs: list[StaffJob]


class AttendanceAction(StrictRequest):
    client_timestamp: datetime | None = None


class AttendanceRecord(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str
    clock_in_at: datetime
    clock_out_at: datetime | None
    worked_minutes: int
    late_minutes: int
    status: str


class AttendanceList(BaseModel):
    items: list[AttendanceRecord]
    next_offset: int | None


class AttendanceOverviewItem(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    status: Literal[
        "scheduled",
        "working",
        "late",
        "clocked_out",
        "not_clocked_in",
        "off_today",
        "approved_leave",
    ]
    shift_name: str | None = None
    shift_start: time | None = None
    shift_end: time | None = None
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    worked_minutes: int = 0
    late_minutes: int = 0
    missed_shift: bool = False


class ShiftCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_times(self) -> "ShiftCreate":
        if self.end_time <= self.start_time:
            raise ValueError("Shift end time must be after its start time.")
        return self


class ShiftView(BaseModel):
    id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    is_active: bool


class ShiftAssignmentCreate(StrictRequest):
    staff_id: uuid.UUID
    shift_id: uuid.UUID
    work_date: date
    team_id: uuid.UUID | None = None


class ShiftAssignmentView(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str
    shift_id: uuid.UUID
    shift_name: str
    work_date: date
    start_time: time
    end_time: time
    team_id: uuid.UUID | None
    team_name: str | None


class LeaveCreate(StrictRequest):
    start_date: date
    end_date: date
    reason: str = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self) -> "LeaveCreate":
        if self.end_date < self.start_date:
            raise ValueError("Leave end date must not be before its start date.")
        return self


class LeaveReview(StrictRequest):
    decision: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)


class LeaveView(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str
    start_date: date
    end_date: date
    reason: str
    status: str
    reviewed_at: datetime | None
    review_note: str | None


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: int


class AttentionItem(BaseModel):
    kind: str
    count: int
    label: str


class OperationsDashboard(BaseModel):
    date: date
    currency_code: str
    metrics: list[DashboardMetric]
    attention: list[AttentionItem]
    active_jobs: list[StaffJob]


class ReportPoint(BaseModel):
    date: date
    booked_sales_minor: int
    collected_revenue_minor: int
    jobs: int
    completed: int
    cancelled: int


class PerformanceRow(BaseModel):
    id: uuid.UUID
    name: str
    hours_worked: float
    late_arrivals: int
    jobs_completed: int
    average_wash_minutes: int
    jobs_per_worked_hour: float
    job_value_handled_minor: int


class MixRow(BaseModel):
    key: str
    label: str
    count: int
    amount_minor: int
    percentage: float


class TeamPerformanceRow(BaseModel):
    id: uuid.UUID
    name: str
    completed_jobs: int
    average_wash_minutes: int
    average_operational_minutes: int
    job_value_handled_minor: int
    jobs_per_active_day: float


class ReportV2(BaseModel):
    summary: ReportSummary
    series: list[ReportPoint]
    staff_performance: list[PerformanceRow]
    service_mix: list[MixRow] = Field(default_factory=list)
    payment_mix: list[MixRow] = Field(default_factory=list)
    team_performance: list[TeamPerformanceRow] = Field(default_factory=list)
