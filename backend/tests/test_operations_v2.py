import uuid
from datetime import UTC, date, datetime, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

import app.services.staff_accounts as staff_accounts
from app.auth.dependencies import StaffContext
from app.cli.seed_demo_staff import DEMO_STAFF
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.domain.staff_usernames import normalize_staff_username
from app.models.entities import (
    AttendanceSession,
    BusinessSyncRevision,
    Job,
    LeaveRequest,
    StaffShiftAssignment,
    TeamMembership,
)
from app.schemas.staff import (
    AssignmentAction,
    LeaveCreate,
    ReportV2,
    ShiftCreate,
    StaffPasswordReset,
    StartTripAction,
    SyncState,
)
from app.services.staff_accounts import _managed_profile, _validate_managed_role
from app.services.staff_operations import _job_rows
from app.services.sync_state import get_sync_state
from app.services.workforce import (
    _shift_assignment_view,
    attendance_category,
    attendance_late_minutes,
)


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


def test_start_trip_accepts_explicit_no_eta_fallback_and_valid_origin() -> None:
    fallback = StartTripAction(client_event_id="event-no-eta", origin=None)
    assert fallback.origin is None
    located = StartTripAction(
        client_event_id="event-with-location",
        origin={"latitude": 24.4539, "longitude": 54.3773},
    )
    assert located.origin is not None
    assert located.origin.latitude == 24.4539


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


@pytest.mark.asyncio
async def test_managed_staff_lookup_hides_cross_account_and_invalid_targets() -> None:
    manager = context(StaffRole.MANAGER)
    scalars = MagicMock()
    scalars.one_or_none.return_value = None
    session = MagicMock()
    session.scalars = AsyncMock(return_value=scalars)

    with pytest.raises(DomainError) as error:
        await _managed_profile(session, manager, uuid.uuid4())

    assert error.value.code == "STAFF_NOT_FOUND"
    assert error.value.status_code == 404
    statement = session.scalars.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert manager.business_id in compiled.params.values()


def test_password_reset_schema_separates_manual_and_temporary_secrets() -> None:
    generated_value = str(uuid.uuid4())
    manual = StaffPasswordReset(mode="manual", new_password=generated_value)
    temporary = StaffPasswordReset(mode="temporary")
    assert manual.new_password == generated_value
    assert temporary.new_password is None
    with pytest.raises(ValidationError):
        StaffPasswordReset(mode="manual")
    with pytest.raises(ValidationError):
        StaffPasswordReset(mode="temporary", new_password=str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_shift_assignment_view_uses_unambiguous_scoped_joins() -> None:
    business_id = uuid.uuid4()
    item = StaffShiftAssignment(
        id=uuid.uuid4(),
        business_id=business_id,
        staff_profile_id=uuid.uuid4(),
        shift_id=uuid.uuid4(),
        resource_id=uuid.uuid4(),
        work_date=date(2035, 1, 7),
    )
    result = MagicMock()
    result.one.return_value = (
        "Mohammed Abdo",
        "Morning",
        time(9),
        time(18),
        "Mobile Team 1",
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    view = await _shift_assignment_view(session, item)

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FROM staff_shift_assignments JOIN staff_profiles ON" in sql
    assert "JOIN shifts ON" in sql
    assert "LEFT OUTER JOIN schedule_resources ON" in sql
    assert "schedule_resources.business_id = staff_shift_assignments.business_id" in sql
    assert view.staff_name == "Mohammed Abdo"
    assert view.shift_name == "Morning"
    assert view.team_name == "Mobile Team 1"


@pytest.mark.asyncio
async def test_job_customer_search_is_partial_case_insensitive_and_business_scoped() -> None:
    manager = context(StaffRole.MANAGER)
    result = MagicMock()
    result.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    await _job_rows(
        session,
        manager,
        view="all",
        scope="all",
        search="  Mohammed   Abdo  ",
    )

    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "jobs.business_id" in sql
    assert "bookings.customer_first_name ILIKE" in sql
    assert "bookings.customer_surname ILIKE" in sql
    assert "concat_ws" in sql
    assert "%Mohammed Abdo%" in compiled.params.values()


@pytest.mark.asyncio
async def test_password_reset_modes_never_put_passwords_in_audit_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context(StaffRole.MANAGER)
    profile = MagicMock(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        role=StaffRole.EMPLOYEE,
        must_change_password=False,
    )
    session = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    admin = MagicMock()
    admin.update_staff_user = AsyncMock()
    audit = MagicMock()
    generated_value = str(uuid.uuid4())
    monkeypatch.setattr(staff_accounts, "_managed_profile", AsyncMock(return_value=profile))
    monkeypatch.setattr(staff_accounts, "_audit", audit)
    monkeypatch.setattr(staff_accounts, "bump_sync_revisions", AsyncMock())
    monkeypatch.setattr(staff_accounts.secrets, "token_urlsafe", lambda _size: generated_value)

    temporary = await staff_accounts.reset_staff_password_choice(
        session,
        manager,
        profile.id,
        mode="temporary",
        new_password=None,
        admin=admin,
    )

    assert temporary.temporary_password == generated_value
    assert temporary.must_change_password is True
    assert profile.must_change_password is True
    admin.update_staff_user.assert_awaited_with(
        profile.auth_user_id,
        password=generated_value,
    )
    audit_metadata = audit.call_args.args[-1]
    assert audit_metadata == {"mode": "temporary", "must_change_password": True}

    manual_value = str(uuid.uuid4())
    manual = await staff_accounts.reset_staff_password_choice(
        session,
        manager,
        profile.id,
        mode="manual",
        new_password=manual_value,
        admin=admin,
    )

    assert manual.temporary_password is None
    assert manual.must_change_password is False
    assert profile.must_change_password is False
    admin.update_staff_user.assert_awaited_with(
        profile.auth_user_id,
        password=manual_value,
    )
    assert audit.call_args.args[-1] == {
        "mode": "manual",
        "must_change_password": False,
    }


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
    assignment_checks = {constraint.name for constraint in Job.__table__.constraints}
    assert any(
        name is not None and name.endswith("unassigned_jobs_have_no_assignment")
        for name in assignment_checks
    )


@pytest.mark.asyncio
async def test_sync_state_is_business_scoped_and_returns_current_vector() -> None:
    expected_business = uuid.uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(
        return_value=BusinessSyncRevision(
            business_id=expected_business,
            jobs_revision=4,
            workforce_revision=3,
            schedule_revision=2,
            finance_revision=1,
        )
    )

    state = await get_sync_state(session, expected_business)

    assert state == SyncState(jobs=4, workforce=3, schedule=2, finance=1)
    statement = session.scalar.await_args.args[0]
    assert expected_business.hex in str(
        statement.compile(compile_kwargs={"literal_binds": True})
    )


@pytest.mark.asyncio
async def test_sync_state_starts_with_zero_vector_before_first_write() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)

    assert await get_sync_state(session, uuid.uuid4()) == SyncState(
        jobs=0,
        workforce=0,
        schedule=0,
        finance=0,
    )


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
