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
from app.schemas.staff import AssignmentAction, LeaveCreate, ShiftCreate
from app.services.staff_accounts import _validate_managed_role
from app.services.workforce import attendance_late_minutes


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
    assert attendance_late_minutes(
        clock_in, date(2026, 8, 24), time(9), "Asia/Dubai", 5
    ) == 3
    assert attendance_late_minutes(
        clock_in, date(2026, 8, 24), None, "Asia/Dubai", 5
    ) == 0


def test_operations_models_have_ownership_and_conflict_indexes() -> None:
    team_unique = {
        constraint.name for constraint in TeamMembership.__table__.constraints
    }
    shift_unique = {
        constraint.name for constraint in StaffShiftAssignment.__table__.constraints
    }
    attendance_indexes = {index.name for index in AttendanceSession.__table__.indexes}
    leave_indexes = {index.name for index in LeaveRequest.__table__.indexes}
    job_indexes = {index.name for index in Job.__table__.indexes}
    assert "uq_team_membership_resource_staff" in team_unique
    assert "uq_staff_shift_work_date" in shift_unique
    assert "uq_attendance_open_staff" in attendance_indexes
    assert "ix_leave_business_status_dates" in leave_indexes
    assert "ix_jobs_resource_schedule" in job_indexes
