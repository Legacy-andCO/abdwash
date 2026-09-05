import uuid
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

import app.services.customers as customer_service
from app.auth.verifier import VerifiedIdentity
from app.domain.enums import BookingStatus, JobStatus
from app.domain.errors import ConflictError
from app.main import app
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    Job,
    JobEvent,
    NotificationOutbox,
    ScheduleSlot,
    SlotHoldGroup,
    Vehicle,
)
from app.schemas.customer import CustomerRescheduleCreate, ManagerRescheduleCreate
from app.schemas.public import BookingVehicleCreate, CustomerContact
from app.services.bookings import _resolve_customer_profile, _save_new_customer_vehicles
from app.services.customers import (
    CustomerScope,
    list_customer_bookings,
    map_customer_status,
    reschedule_customer_booking,
    reschedule_managed_booking,
)
from app.services.scheduling import hold_token_hash
from app.services.smart_scheduling import AssignmentDecision, TeamCandidate


def scalar_result(*, one: object | None = None, all_items: list[object] | None = None) -> MagicMock:
    result = MagicMock()
    result.one.return_value = one
    result.one_or_none.return_value = one
    result.all.return_value = all_items or []
    return result


@pytest.fixture(autouse=True)
def isolate_smart_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    """These service-unit tests isolate reschedule mutation mechanics.

    Smart-scheduler decisions are covered independently; PostgreSQL integration
    tests cover the combined transaction.
    """

    monkeypatch.setattr(customer_service, "lock_schedule_day", AsyncMock())
    monkeypatch.setattr(customer_service, "choose_team_for_booking", AsyncMock())
    monkeypatch.setattr(
        customer_service,
        "policy_for_day",
        AsyncMock(
            return_value=SimpleNamespace(
                opening_time=time(9),
                closing_time=time(21),
                timezone="Asia/Dubai",
            )
        ),
    )


def test_customer_status_mapping_tracks_operational_job_state() -> None:
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.UNASSIGNED).key == "confirmed"
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.ASSIGNED).key == "assigned"
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.EN_ROUTE).key == "en_route"
    arrived = map_customer_status(BookingStatus.CONFIRMED, JobStatus.ARRIVED)
    assert arrived.key == "arrived"
    assert arrived.label == "Driver has arrived"
    assert map_customer_status(BookingStatus.CONFIRMED, "en_route").key == "en_route"
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.IN_PROGRESS).key == "in_progress"
    assert map_customer_status(BookingStatus.COMPLETED, JobStatus.COMPLETED).key == "completed"


def test_customer_status_mapping_prioritizes_cancellation() -> None:
    requested = map_customer_status(BookingStatus.CANCELLATION_REQUESTED, JobStatus.ASSIGNED)
    cancelled = map_customer_status(BookingStatus.CANCELLED, JobStatus.CANCELLED)
    assert requested.key == "cancellation_requested"
    assert cancelled.key == "cancelled"


def test_customer_routes_require_supabase_authentication() -> None:
    booking_id = uuid.uuid4()
    with TestClient(app) as client:
        assert client.get("/api/v1/customer/context").status_code == 401
        assert client.get("/api/v1/customer/bookings").status_code == 401
        assert client.get(f"/api/v1/customer/bookings/{booking_id}").status_code == 401
        assert client.get("/api/v1/customer/reviews/eligibility").status_code == 401
        response = client.request(
            "DELETE",
            "/api/v1/customer/account",
            json={"confirmation": "DELETE"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_booking_list_uses_named_status_and_eta_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business_id = uuid.uuid4()
    profile = SimpleNamespace(id=uuid.uuid4())
    identity = VerifiedIdentity(user_id=uuid.uuid4(), claims={"email": "noor@example.com"})
    now = datetime.now(UTC)

    def booking(reference: str, status: BookingStatus) -> Booking:
        return Booking(
            id=uuid.uuid4(),
            business_id=business_id,
            reference=reference,
            customer_profile_id=profile.id,
            hold_group_id=uuid.uuid4(),
            resource_id=uuid.uuid4(),
            status=status,
            payment_choice="pay_after_service",
            payment_status="unpaid",
            scheduled_start=now + timedelta(days=1),
            scheduled_end=now + timedelta(days=1, hours=2),
            vehicle_count=1,
            total_amount_minor=5000,
            currency_code="AED",
            source="web",
            customer_first_name="Noor",
            customer_surname="Ali",
            customer_email="noor@example.com",
            customer_phone="+971501234567",
            written_address="Abu Dhabi",
            location_url="https://maps.google.com/x",
            management_token_hash="synthetic-test-hash",  # noqa: S106
            created_at=now,
        )

    en_route_booking = booking("AW-ENROUTE", BookingStatus.CONFIRMED)
    no_job_booking = booking("AW-NOJOB", BookingStatus.CANCELLED)
    eta = now + timedelta(minutes=20)
    rows = [
        SimpleNamespace(
            Booking=en_route_booking,
            job_status=JobStatus.EN_ROUTE,
            estimated_arrival_at=eta,
            extra_future_scalar="safe",
        ),
        SimpleNamespace(
            Booking=no_job_booking,
            job_status=None,
            estimated_arrival_at=None,
            extra_future_scalar="safe",
        ),
    ]
    settings = BusinessSettings(
        business_id=business_id,
        timezone="Asia/Dubai",
        currency_code="AED",
        opening_time=time(9),
        closing_time=time(21),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        cancellation_cutoff_hours=24,
        hold_duration_minutes=10,
    )
    monkeypatch.setattr(
        customer_service,
        "load_customer_scope",
        AsyncMock(return_value=CustomerScope(identity, business_id, profile)),
    )
    session = AsyncMock()
    session.scalars.return_value = scalar_result(one=settings)
    booking_result = MagicMock()
    booking_result.all.return_value = rows
    vehicle_result = MagicMock()
    vehicle_result.all.return_value = []
    session.execute.side_effect = [booking_result, vehicle_result]

    response = await list_customer_bookings(session, identity)

    assert [item.reference for item in response.bookings] == ["AW-ENROUTE", "AW-NOJOB"]
    assert response.bookings[0].status.key == "en_route"
    assert response.bookings[0].estimated_arrival_at == eta
    assert response.bookings[1].status.key == "cancelled"
    assert response.bookings[1].estimated_arrival_at is None
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_authenticated_booking_atomically_provisions_or_updates_profile() -> None:
    profile_id = uuid.uuid4()
    result = MagicMock()
    result.one_or_none.return_value = profile_id
    session = AsyncMock()
    session.scalars.return_value = result
    session.scalar.return_value = None
    identity = VerifiedIdentity(user_id=uuid.uuid4(), claims={"email": "noor@example.com"})
    contact = CustomerContact(
        first_name="Noor",
        surname="Ali",
        email="booking-contact@example.com",
        phone="050 123 4567",
    )

    resolved = await _resolve_customer_profile(
        session,
        identity=identity,
        business_id=uuid.uuid4(),
        contact=contact,
    )

    assert resolved == profile_id
    statement = session.scalars.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (auth_user_id) DO UPDATE" in sql
    assert "noor@example.com" in statement.compile(dialect=postgresql.dialect()).params.values()
    assert contact.phone == "+971501234567"


@pytest.mark.asyncio
async def test_guest_booking_never_claims_profile_by_email() -> None:
    session = AsyncMock()
    contact = CustomerContact(
        first_name="Guest",
        surname="Customer",
        email="shared@example.com",
        phone="+971501234567",
    )
    assert (
        await _resolve_customer_profile(
            session,
            identity=None,
            business_id=uuid.uuid4(),
            contact=contact,
        )
        is None
    )
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticated_booking_saves_new_vehicle_once_by_normalized_plate() -> None:
    customer_id = uuid.uuid4()
    existing = Vehicle(
        id=uuid.uuid4(),
        customer_id=customer_id,
        make="Toyota",
        model="Land Cruiser",
        vehicle_type="suv",
        plate_number="AD 12 345",
        is_active=True,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=customer_id)
    session.scalars = AsyncMock(return_value=scalar_result(all_items=[existing]))
    session.flush = AsyncMock()
    vehicles = [
        BookingVehicleCreate(
            make="Toyota",
            model="Land Cruiser",
            vehicle_type="suv",
            plate_number="ad-12345",
            service_id=uuid.uuid4(),
        )
    ]

    result = await _save_new_customer_vehicles(
        session,
        requested_vehicles=vehicles,
        customer_profile_id=customer_id,
    )

    assert result == {1: existing.id}
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_guest_booking_does_not_save_vehicle_profile_data() -> None:
    session = MagicMock()
    result = await _save_new_customer_vehicles(
        session,
        requested_vehicles=[],
        customer_profile_id=None,
    )
    assert result == {}
    session.scalar.assert_not_called()


def reschedule_records() -> tuple[
    Booking,
    BusinessSettings,
    Job,
    SlotHoldGroup,
    ScheduleSlot,
    ScheduleSlot,
    BookingVehicle,
    BookingService,
    str,
]:
    now = datetime.now(UTC)
    business_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    old_hold_id = uuid.uuid4()
    token = "h" * 40
    booking = Booking(
        id=booking_id,
        business_id=business_id,
        reference="AW-TEST",
        customer_profile_id=uuid.uuid4(),
        hold_group_id=old_hold_id,
        resource_id=uuid.uuid4(),
        status="confirmed",
        payment_choice="pay_after_service",
        payment_status="unpaid",
        scheduled_start=now + timedelta(days=5),
        scheduled_end=now + timedelta(days=5, hours=2),
        vehicle_count=1,
        total_amount_minor=10000,
        currency_code="AED",
        source="web",
        customer_first_name="Noor",
        customer_surname="Ali",
        customer_email="noor@example.com",
        customer_phone="+971501234567",
        written_address="Abu Dhabi",
        location_url="https://maps.google.com/?q=Abu+Dhabi",
        management_token_hash="x" * 64,
        version=1,
        created_at=now,
        updated_at=now,
    )
    settings = BusinessSettings(
        business_id=business_id,
        timezone="Asia/Dubai",
        currency_code="AED",
        opening_time=time(9),
        closing_time=time(21),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        cancellation_cutoff_hours=24,
        hold_duration_minutes=10,
    )
    job = Job(
        id=uuid.uuid4(),
        booking_id=booking_id,
        business_id=business_id,
        status="unassigned",
        scheduled_start=booking.scheduled_start,
        scheduled_end=booking.scheduled_end,
        version=1,
    )
    new_start = datetime.combine(
        (now + timedelta(days=6)).date(),
        time(10),
        ZoneInfo("Asia/Dubai"),
    ).astimezone(UTC)
    hold = SlotHoldGroup(
        id=uuid.uuid4(),
        business_id=business_id,
        resource_id=uuid.uuid4(),
        token_hash=hold_token_hash(token),
        status="active",
        vehicle_count=1,
        required_slot_count=1,
        slot_start=new_start,
        slot_end=new_start + timedelta(hours=2),
        expires_at=now + timedelta(minutes=10),
    )
    old_slot = ScheduleSlot(
        id=uuid.uuid4(),
        business_id=business_id,
        resource_id=booking.resource_id,
        slot_start=booking.scheduled_start,
        slot_end=booking.scheduled_end,
        status="reserved",
        hold_group_id=old_hold_id,
        booking_id=booking_id,
        version=1,
    )
    new_slot = ScheduleSlot(
        id=uuid.uuid4(),
        business_id=business_id,
        resource_id=hold.resource_id,
        slot_start=hold.slot_start,
        slot_end=hold.slot_end,
        status="held",
        hold_group_id=hold.id,
        hold_expires_at=hold.expires_at,
        version=1,
    )
    vehicle = BookingVehicle(
        id=uuid.uuid4(),
        booking_id=booking_id,
        position=1,
        make="Toyota",
        model="Camry",
        vehicle_type="sedan",
    )
    service = BookingService(
        booking_id=booking_id,
        booking_vehicle_id=vehicle.id,
        service_id=uuid.uuid4(),
        service_name="Signature Wash",
        unit_price_minor=10000,
        quantity=1,
        line_total_minor=10000,
    )
    return booking, settings, job, hold, old_slot, new_slot, vehicle, service, token


@pytest.mark.asyncio
async def test_reschedule_atomically_swaps_slots_and_updates_job() -> None:
    booking, settings, job, hold, old_slot, new_slot, vehicle, service, token = reschedule_records()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=settings),
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(one=settings),
            scalar_result(all_items=[service.service_name]),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service, None)]
    job_status_row = MagicMock()
    job_status_row.one_or_none.return_value = (job.status, None)
    session.execute = AsyncMock(side_effect=[vehicle_rows, job_status_row])
    session.flush = AsyncMock()

    response = await reschedule_customer_booking(
        session, booking, CustomerRescheduleCreate(hold_token=token)
    )

    assert old_slot.status == "free"
    assert old_slot.booking_id is None
    assert new_slot.status == "reserved"
    assert new_slot.booking_id == booking.id
    assert booking.scheduled_start == hold.slot_start
    assert job.scheduled_start == hold.slot_start
    assert hold.status == "consumed"
    assert response.scheduled_start == hold.slot_start
    assert any(
        isinstance(call.args[0], JobEvent) and call.args[0].event_type == "booking_rescheduled"
        for call in session.add.call_args_list
    )


@pytest.mark.asyncio
async def test_expired_reschedule_hold_keeps_original_booking_unchanged() -> None:
    booking, settings, job, hold, old_slot, _new_slot, _vehicle, _service, token = (
        reschedule_records()
    )
    original_start = booking.scheduled_start
    hold.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session = MagicMock()
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=settings),
            scalar_result(one=job),
            scalar_result(one=hold),
        ]
    )

    with pytest.raises(ConflictError, match="expired"):
        await reschedule_customer_booking(
            session, booking, CustomerRescheduleCreate(hold_token=token)
        )

    assert booking.scheduled_start == original_start
    assert old_slot.status == "reserved"


@pytest.mark.asyncio
async def test_overdue_customer_reschedule_remains_restricted() -> None:
    booking, settings, job, _hold, _old_slot, _new_slot, _vehicle, _service, token = (
        reschedule_records()
    )
    booking.scheduled_start = datetime.now(UTC) - timedelta(hours=1)
    booking.scheduled_end = datetime.now(UTC) + timedelta(hours=1)
    job.scheduled_start = booking.scheduled_start
    job.scheduled_end = booking.scheduled_end
    job.status = JobStatus.ASSIGNED
    session = MagicMock()
    session.scalars = AsyncMock(
        side_effect=[scalar_result(one=settings), scalar_result(one=job)]
    )

    with pytest.raises(ConflictError) as error:
        await reschedule_customer_booking(
            session, booking, CustomerRescheduleCreate(hold_token=token)
        )

    assert error.value.code == "RESCHEDULE_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_active_manager_reschedule_requires_explicit_confirmation() -> None:
    booking, _settings, job, _hold, _old_slot, _new_slot, _vehicle, _service, token = (
        reschedule_records()
    )
    job.status = JobStatus.IN_PROGRESS
    session = MagicMock()
    session.scalars = AsyncMock(side_effect=[scalar_result(one=job)])

    with pytest.raises(ConflictError) as error:
        await reschedule_managed_booking(
            session,
            booking,
            CustomerRescheduleCreate(hold_token=token),
            actor_staff_id=uuid.uuid4(),
            confirm_active_reschedule=False,
        )

    assert error.value.code == "ACTIVE_RESCHEDULE_CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_confirmed_active_manager_reschedule_resets_operational_state() -> None:
    booking, settings, job, hold, old_slot, new_slot, vehicle, service, token = (
        reschedule_records()
    )
    job.status = JobStatus.IN_PROGRESS
    job.en_route_at = datetime.now(UTC)
    job.estimated_arrival_at = datetime.now(UTC)
    job.started_at = datetime.now(UTC)
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(one=settings),
            scalar_result(all_items=[service.service_name]),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service, None)]
    job_status_row = MagicMock()
    job_status_row.one_or_none.return_value = (JobStatus.ASSIGNED, None)
    session.execute = AsyncMock(side_effect=[vehicle_rows, job_status_row])
    session.flush = AsyncMock()

    await reschedule_managed_booking(
        session,
        booking,
        CustomerRescheduleCreate(hold_token=token),
        actor_staff_id=uuid.uuid4(),
        confirm_active_reschedule=True,
    )

    assert job.status == JobStatus.ASSIGNED
    assert job.en_route_at is None
    assert job.estimated_arrival_at is None
    assert job.started_at is None
    assert job.assigned_resource_id == hold.resource_id
    event = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], JobEvent)
    )
    assert event.metadata_json["source"] == "staff_override"
    assert event.metadata_json["active_state_reset"] is True


@pytest.mark.asyncio
async def test_overdue_assigned_job_can_be_rescheduled_by_manager() -> None:
    booking, settings, job, hold, old_slot, new_slot, vehicle, service, token = (
        reschedule_records()
    )
    booking.scheduled_start = datetime.now(UTC) - timedelta(hours=2)
    booking.scheduled_end = datetime.now(UTC) - timedelta(minutes=1)
    job.scheduled_start = booking.scheduled_start
    job.scheduled_end = booking.scheduled_end
    old_slot.slot_start = booking.scheduled_start
    old_slot.slot_end = booking.scheduled_end
    job.status = JobStatus.ASSIGNED
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(one=settings),
            scalar_result(all_items=[service.service_name]),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service, None)]
    job_status_row = MagicMock()
    job_status_row.one_or_none.return_value = (JobStatus.ASSIGNED, None)
    session.execute = AsyncMock(side_effect=[vehicle_rows, job_status_row])
    session.flush = AsyncMock()

    response = await reschedule_managed_booking(
        session,
        booking,
        CustomerRescheduleCreate(hold_token=token),
        actor_staff_id=uuid.uuid4(),
        confirm_active_reschedule=False,
    )

    assert response.scheduled_start == hold.slot_start
    assert job.assigned_resource_id == hold.resource_id


@pytest.mark.asyncio
async def test_manager_exact_minute_reschedule_updates_only_requested_booking_and_queues_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking, settings, job, _hold, old_slot, _new_slot, _vehicle, _service, _token = (
        reschedule_records()
    )
    team = TeamCandidate(
        id=uuid.uuid4(),
        name="Team One",
        sort_order=1,
        created_at=datetime.now(UTC),
    )
    decision = AssignmentDecision(
        team=team,
        candidate_count=1,
        feasible_count=1,
        same_day_job_count=0,
        assigned_minutes=0,
        assignment_source="auto",
        reason="Available",
    )
    selected_date = (datetime.now(UTC) + timedelta(days=7)).date()
    request = ManagerRescheduleCreate(
        date=selected_date,
        time=time(10, 37),
        client_event_id="manager-reschedule-exact-1",
    )
    new_slot = ScheduleSlot(
        id=uuid.uuid4(),
        business_id=booking.business_id,
        resource_id=team.id,
        slot_start=datetime.combine(selected_date, time(10, 37), tzinfo=UTC),
        slot_end=datetime.combine(selected_date, time(12, 37), tzinfo=UTC),
        status="free",
        version=1,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=job),
            scalar_result(one=settings),
            scalar_result(all_items=[old_slot]),
        ]
    )
    session.flush = AsyncMock()
    monkeypatch.setattr(
        customer_service,
        "choose_team_for_booking",
        AsyncMock(return_value=decision),
    )
    monkeypatch.setattr(
        customer_service,
        "_lock_slot_sequence",
        AsyncMock(return_value=[new_slot]),
    )
    monkeypatch.setattr(
        customer_service,
        "customer_booking_detail_for_record",
        AsyncMock(return_value=SimpleNamespace(scheduled_start=new_slot.slot_start)),
    )

    await reschedule_managed_booking(
        session,
        booking,
        request,
        actor_staff_id=uuid.uuid4(),
        confirm_active_reschedule=False,
    )

    assert booking.scheduled_start == datetime.combine(
        selected_date,
        time(6, 37),
        tzinfo=UTC,
    )
    assert job.scheduled_start == booking.scheduled_start
    assert job.assigned_resource_id == team.id
    assert old_slot.status == "free"
    assert new_slot.status == "reserved"
    notifications = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], NotificationOutbox)
    ]
    assert len(notifications) == 1
    assert notifications[0].notification_type == "booking_rescheduled"
    assert notifications[0].recipient == booking.customer_email
    assert notifications[0].dedupe_key is not None


@pytest.mark.asyncio
async def test_failed_exact_reschedule_does_not_queue_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking, settings, job, _hold, _old_slot, _new_slot, _vehicle, _service, _token = (
        reschedule_records()
    )
    selected_date = (datetime.now(UTC) + timedelta(days=7)).date()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(
        side_effect=[scalar_result(one=job), scalar_result(one=settings)]
    )
    monkeypatch.setattr(
        customer_service,
        "choose_team_for_booking",
        AsyncMock(side_effect=ConflictError("NO_TEAM_CAPACITY", "No team available.")),
    )

    with pytest.raises(ConflictError):
        await reschedule_managed_booking(
            session,
            booking,
            ManagerRescheduleCreate(
                date=selected_date,
                time=time(11, 23),
                client_event_id="manager-reschedule-failed-1",
            ),
            actor_staff_id=uuid.uuid4(),
            confirm_active_reschedule=False,
        )

    assert not any(
        isinstance(call.args[0], NotificationOutbox)
        for call in session.add.call_args_list
    )
