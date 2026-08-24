import uuid
from datetime import date, datetime, time

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


class StaffJobList(BaseModel):
    jobs: list[StaffJob]
    next_offset: int | None


class Coordinates(StrictRequest):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class JobAction(StrictRequest):
    client_event_id: str = Field(min_length=8, max_length=160)
    client_timestamp: datetime | None = None


class StartTripAction(JobAction):
    origin: Coordinates


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


class ReportV2(BaseModel):
    summary: ReportSummary
    series: list[ReportPoint]
    staff_performance: list[PerformanceRow]
