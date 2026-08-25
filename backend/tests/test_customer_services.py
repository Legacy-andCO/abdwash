import uuid
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
    ScheduleSlot,
    SlotHoldGroup,
)
from app.schemas.customer import CustomerRescheduleCreate
from app.schemas.public import CustomerContact
from app.services.bookings import _resolve_customer_profile
from app.services.customers import (
    CustomerScope,
    list_customer_bookings,
    map_customer_status,
    reschedule_customer_booking,
    reschedule_managed_booking,
)
from app.services.scheduling import hold_token_hash


def scalar_result(*, one: object | None = None, all_items: list[object] | None = None) -> MagicMock:
    result = MagicMock()
    result.one.return_value = one
    result.one_or_none.return_value = one
    result.all.return_value = all_items or []
    return result


def test_customer_status_mapping_tracks_operational_job_state() -> None:
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.UNASSIGNED).key == "confirmed"
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.ASSIGNED).key == "assigned"
    assert map_customer_status(BookingStatus.CONFIRMED, JobStatus.EN_ROUTE).key == "en_route"
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
    identity = VerifiedIdentity(user_id=uuid.uuid4(), claims={"email": "noor@example.com"})
    contact = CustomerContact(
        first_name="Noor",
        surname="Ali",
        email="noor@example.com",
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
    new_start = now + timedelta(days=6)
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
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=settings),
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service)]
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
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service)]
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
    session.scalars = AsyncMock(
        side_effect=[
            scalar_result(one=job),
            scalar_result(one=hold),
            scalar_result(all_items=[old_slot, new_slot]),
            scalar_result(one=settings),
            scalar_result(one=None),
        ]
    )
    vehicle_rows = MagicMock()
    vehicle_rows.all.return_value = [(vehicle, service)]
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
