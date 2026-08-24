import uuid
from datetime import UTC, date, datetime, time

import pytest
from pydantic import ValidationError

from app.auth.dependencies import StaffContext
from app.cli.seed_demo_staff import DEMO_STAFF
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.domain.staff_usernames import normalize_staff_username
from app.models.entities import (
    AttendanceSession,
    Job,
    LeaveRequest,
    StaffShiftAssignment,
    TeamMembership,
)
from app.schemas.staff import AssignmentAction, LeaveCreate, ReportV2, ShiftCreate
from app.services.staff_accounts import _validate_managed_role
from app.services.workforce import attendance_category, attendance_late_minutes


def context(role: StaffRole) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="AbdWash",
        role=role,
        timezone="Asia/Dubai",
    )


def test_demo_accounts_use_simple_usernames_and_expected_roles() -> None:
    assert [(item.username, item.role) for item in DEMO_STAFF] == [
        ("manager", StaffRole.MANAGER),
        ("employee", StaffRole.EMPLOYEE),
    ]


def test_username_rules_allow_normal_names_and_bound_length() -> None:
    assert normalize_staff_username(" Wash-Team_Lead ") == "wash-team_lead"
    assert len(normalize_staff_username("a" * 32)) == 32
    with pytest.raises(DomainError):
        normalize_staff_username("a" * 33)


def test_assignment_requires_team_or_staff_and_supports_each() -> None:
    with pytest.raises(ValidationError):
        AssignmentAction(client_event_id="event-1234")
    team_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    assert AssignmentAction(client_event_id="event-team", team_id=team_id).team_id == team_id
    assert AssignmentAction(client_event_id="event-staff", staff_id=staff_id).staff_id == staff_id


def test_shift_and_leave_ranges_are_validated() -> None:
    with pytest.raises(ValidationError):
        ShiftCreate(name="Invalid", start_time=time(18), end_time=time(9))
    with pytest.raises(ValidationError):
        LeaveCreate(start_date=date(2026, 8, 25), end_date=date(2026, 8, 24), reason="Trip")


def test_manager_can_only_manage_employees() -> None:
    _validate_managed_role(context(StaffRole.MANAGER), StaffRole.EMPLOYEE)
    with pytest.raises(DomainError) as error:
        _validate_managed_role(context(StaffRole.MANAGER), StaffRole.MANAGER)
    assert error.value.code == "ROLE_MANAGEMENT_FORBIDDEN"


def test_admin_can_manage_manager_but_not_create_admin() -> None:
    _validate_managed_role(context(StaffRole.ADMIN), StaffRole.MANAGER)
    with pytest.raises(DomainError) as error:
        _validate_managed_role(context(StaffRole.ADMIN), StaffRole.ADMIN)
    assert error.value.code == "ADMIN_CREATION_FORBIDDEN"


def test_attendance_lateness_uses_business_timezone_and_grace() -> None:
    clock_in = datetime(2026, 8, 24, 5, 8, tzinfo=UTC)  # 09:08 in the UAE.
    assert attendance_late_minutes(clock_in, date(2026, 8, 24), time(9), "Asia/Dubai", 5) == 3
    assert attendance_late_minutes(clock_in, date(2026, 8, 24), None, "Asia/Dubai", 5) == 0


def test_operations_models_have_ownership_and_conflict_indexes() -> None:
    team_unique = {constraint.name for constraint in TeamMembership.__table__.constraints}
    shift_unique = {constraint.name for constraint in StaffShiftAssignment.__table__.constraints}
    attendance_indexes = {index.name for index in AttendanceSession.__table__.indexes}
    leave_indexes = {index.name for index in LeaveRequest.__table__.indexes}
    job_indexes = {index.name for index in Job.__table__.indexes}
    assert "uq_team_membership_resource_staff" in team_unique
    assert "uq_staff_shift_work_date" in shift_unique
    assert "uq_attendance_open_staff" in attendance_indexes
    assert "ix_leave_business_status_dates" in leave_indexes
    assert "ix_jobs_resource_schedule" in job_indexes
    assert "ix_jobs_business_schedule_status" in job_indexes


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                "has_open_session": True,
                "has_closed_session": False,
                "late_minutes": 0,
                "has_shift": True,
                "shift_started": True,
                "on_approved_leave": False,
                "shift_ended": False,
            },
            ("working", False),
        ),
        (
            {
                "has_open_session": True,
                "has_closed_session": False,
                "late_minutes": 8,
                "has_shift": True,
                "shift_started": True,
                "on_approved_leave": False,
                "shift_ended": False,
            },
            ("late", False),
        ),
        (
            {
                "has_open_session": False,
                "has_closed_session": True,
                "late_minutes": 8,
                "has_shift": True,
                "shift_started": True,
                "on_approved_leave": False,
                "shift_ended": True,
            },
            ("clocked_out", False),
        ),
        (
            {
                "has_open_session": False,
                "has_closed_session": False,
                "late_minutes": 0,
                "has_shift": True,
                "shift_started": True,
                "on_approved_leave": True,
                "shift_ended": True,
            },
            ("approved_leave", False),
        ),
        (
            {
                "has_open_session": False,
                "has_closed_session": False,
                "late_minutes": 0,
                "has_shift": False,
                "shift_started": False,
                "on_approved_leave": False,
                "shift_ended": True,
            },
            ("off_today", False),
        ),
        (
            {
                "has_open_session": False,
                "has_closed_session": False,
                "late_minutes": 0,
                "has_shift": True,
                "shift_started": True,
                "on_approved_leave": False,
                "shift_ended": True,
            },
            ("not_clocked_in", True),
        ),
        (
            {
                "has_open_session": False,
                "has_closed_session": False,
                "late_minutes": 0,
                "has_shift": True,
                "shift_started": False,
                "on_approved_leave": False,
                "shift_ended": False,
            },
            ("scheduled", False),
        ),
    ],
)
def test_attendance_categories_and_missed_shift_precedence(
    values: dict[str, object], expected: tuple[str, bool]
) -> None:
    assert attendance_category(**values) == expected  # type: ignore[arg-type]


def test_report_v2_supports_service_payment_and_team_aggregates() -> None:
    report = ReportV2.model_validate(
        {
            "summary": {
                "start_date": "2026-08-25",
                "end_date": "2026-08-25",
                "bookings": 1,
                "completed_washes": 1,
                "booked_sales_minor": 10000,
                "collected_revenue_minor": 10000,
                "outstanding_minor": 0,
                "average_booking_value_minor": 10000,
                "currency_code": "AED",
            },
            "series": [],
            "staff_performance": [],
            "service_mix": [
                {
                    "key": "service",
                    "label": "Wash",
                    "count": 1,
                    "amount_minor": 10000,
                    "percentage": 100,
                }
            ],
            "payment_mix": [
                {
                    "key": "cash",
                    "label": "Cash",
                    "count": 1,
                    "amount_minor": 10000,
                    "percentage": 100,
                }
            ],
            "team_performance": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Mobile Team 1",
                    "completed_jobs": 1,
                    "average_wash_minutes": 60,
                    "average_operational_minutes": 90,
                    "job_value_handled_minor": 10000,
                    "jobs_per_active_day": 1,
                }
            ],
        }
    )
    assert report.service_mix[0].percentage == 100
    assert report.payment_mix[0].key == "cash"
    assert report.team_performance[0].completed_jobs == 1
