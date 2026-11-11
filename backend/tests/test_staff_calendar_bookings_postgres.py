import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, time
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.auth.verifier import AuthenticationError, VerifiedIdentity
from app.core.config import Settings
from app.core.database import create_engine, create_session_factory
from app.domain.enums import (
    BookingStatus,
    JobStatus,
    OutboxStatus,
    PaymentStatus,
    SlotStatus,
    StaffRole,
)
from app.main import app
from app.models import Base
from app.models.entities import (
    AuditEvent,
    Booking,
    Business,
    BusinessSettings,
    CustomerProfile,
    Job,
    NotificationOutbox,
    Payment,
    PaymentTransaction,
    ScheduleResource,
    ScheduleSlot,
    Service,
    ServicePrice,
    StaffProfile,
    TeamMembership,
)
from app.repositories.business import DEFAULT_BUSINESS_SLUG
from app.services.policy_acceptance import POLICY_REVISION

URL = os.getenv("TEST_DATABASE_URL")
TEST_URL = make_url(URL) if URL else None
ISOLATED = (
    TEST_URL is not None
    and TEST_URL.get_backend_name() == "postgresql"
    and TEST_URL.host in {"localhost", "127.0.0.1", "::1"}
    and "test" in (TEST_URL.database or "").lower()
)
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.skipif(not ISOLATED, reason="An isolated local TEST_DATABASE_URL is required"),
]
BOOK = "/api/v1/staff/calendar-bookings"
STAFF = "/api/v1/staff"


class TestVerifier:
    __test__ = False

    def __init__(self, tokens):
        self.tokens = tokens

    async def verify(self, token):
        if token not in self.tokens:
            raise AuthenticationError("Invalid test identity")
        return VerifiedIdentity(self.tokens[token], {})


@pytest.fixture(scope="module")
async def foundation() -> AsyncIterator[SimpleNamespace]:
    assert URL is not None
    engine = create_engine(Settings(database_url=URL, app_env="test"))
    sessions = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    tokens = {
        name: uuid.uuid4()
        for name in (
            "employee",
            "coworker",
            "other",
            "foreign",
            "manager",
            "admin",
            "customer",
            "stranger",
        )
    }
    async with sessions() as session, session.begin():
        business = Business(name="Trifecta", slug=DEFAULT_BUSINESS_SLUG)
        foreign_business = Business(name="Other business", slug="foreign-test")
        session.add_all([business, foreign_business])
        await session.flush()
        for tenant in (business, foreign_business):
            session.add(
                BusinessSettings(
                    business_id=tenant.id,
                    timezone="Asia/Dubai",
                    currency_code="AED",
                    opening_time=time(9),
                    closing_time=time(21),
                    default_team_turnaround_minutes=0,
                )
            )
        teams = [
            ScheduleResource(business_id=tenant.id, name=name, resource_type="mobile_team")
            for tenant, name in (
                (business, "Team A"),
                (business, "Team B"),
                (foreign_business, "Team C"),
            )
        ]
        staff = {
            name: StaffProfile(
                business_id=foreign_business.id if name == "foreign" else business.id,
                auth_user_id=tokens[name],
                username=name,
                display_name=name,
                role=StaffRole(name) if name in {"manager", "admin"} else StaffRole.EMPLOYEE,
            )
            for name in ("employee", "coworker", "other", "foreign", "manager", "admin")
        }
        services = [
            Service(
                business_id=business.id,
                name=name,
                price_minor=amount,
                estimated_duration_minutes=minutes,
                customer_bookable=True,
            )
            for name, amount, minutes in (("Test wash", 5000, 120), ("Long test wash", 7000, 180))
        ]
        profile = CustomerProfile(
            business_id=business.id,
            auth_user_id=tokens["customer"],
            first_name="Test",
            surname="Customer",
            phone="+971501234567",
            email="customer@example.com",
        )
        session.add_all([*teams, *staff.values(), *services, profile])
        await session.flush()
        for name, team in zip(
            ("employee", "coworker", "other", "foreign"),
            (teams[0], teams[0], teams[1], teams[2]),
            strict=True,
        ):
            session.add(TeamMembership(resource_id=team.id, staff_profile_id=staff[name].id))
        for service in services:
            session.add(
                ServicePrice(
                    business_id=business.id,
                    service_id=service.id,
                    vehicle_type="sedan",
                    price_minor=service.price_minor,
                )
            )
    saved_state = dict(app.state._state)
    app.state.session_factory = sessions
    app.state.auth_verifier = TestVerifier(tokens)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield SimpleNamespace(
                client=client,
                sessions=sessions,
                business=business.id,
                team_a=teams[0].id,
                team_b=teams[1].id,
                staff=staff,
                profile=profile.id,
                services=services,
            )
    finally:
        app.state._state.clear()
        app.state._state.update(saved_state)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


def headers(actor="employee", key=None):
    return {"Authorization": f"Bearer {actor}", "Idempotency-Key": str(key or uuid.uuid4())}


def payload(foundation, day, *, time_value="09:00", service=0, email=None, overlap=None):
    item = foundation.services[service]
    return {
        "date": day,
        "time": time_value,
        "contact": {"first_name": "Private Customer", "phone": "+971501234567", "email": email},
        "location": {
            "written_address": "Private service address, Abu Dhabi",
            "instructions": "Gate 2",
        },
        "vehicles": [{"service_id": str(item.id), "vehicle_type": "sedan"}],
        "expected_amount_minor": item.price_minor,
        "policy_revision": POLICY_REVISION,
        "policy_delivery": "email" if email else "provided",
        "language": "en",
        "overlap": overlap,
    }


async def submit(foundation, body, actor="employee", key=None):
    return await foundation.client.post(BOOK, json=body, headers=headers(actor, key))


async def created(foundation, body, actor="employee"):
    response = await submit(foundation, body, actor)
    assert response.status_code == 201, response.text
    return response.json()


async def test_normal_booking_uses_existing_private_customer_and_slot_records(foundation):
    body = payload(foundation, "2036-01-10", email="customer@example.com")
    unauthenticated = await foundation.client.post(
        BOOK, json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert unauthenticated.status_code == 401
    key = uuid.uuid4()
    response = await submit(foundation, body, key=key)
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert (await submit(foundation, body, key=key)).json() == receipt
    assert (
        await submit(foundation, {**body, "expected_amount_minor": 6000}, key=key)
    ).status_code == 409
    assert receipt["scheduled_start"].startswith("2036-01-10T05:00:00")
    assert "customer" not in str(receipt).lower()
    job_id = uuid.UUID(receipt["job_id"])
    async with foundation.sessions() as session:
        booking = await session.get(Booking, uuid.UUID(receipt["id"]))
        job = await session.get(Job, job_id)
        assert booking.latitude is None and booking.longitude is None
        assert booking.written_address == body["location"]["written_address"]
        assert booking.created_by_staff_id == foundation.staff["employee"].id
        assert (
            booking.source == "staff_calendar" and booking.customer_profile_id == foundation.profile
        )
        assert job.assigned_resource_id == foundation.team_a
        payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id))
        assert (payment.status, payment.amount_minor) == (PaymentStatus.UNPAID, 5000)
        events = (
            await session.scalars(select(AuditEvent).where(AuditEvent.entity_id == booking.id))
        ).all()
        assert {event.event_type for event in events} == {
            "staff_calendar_booking_created",
            "booking_policies_provided_by_staff",
        }
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ScheduleSlot)
                .where(ScheduleSlot.booking_id == booking.id)
            )
            == 1
        )
    assert (
        await foundation.client.get(f"{STAFF}/jobs/{job_id}", headers=headers("other"))
    ).status_code == 404
    assert (
        await foundation.client.get(f"{STAFF}/jobs/{job_id}", headers=headers())
    ).status_code == 200
    assert (
        await foundation.client.get(
            f"/api/v1/customer/bookings/{receipt['id']}", headers=headers("customer")
        )
    ).status_code == 200
    assert (
        await foundation.client.get(
            f"/api/v1/customer/bookings/{receipt['id']}", headers=headers("stranger")
        )
    ).status_code == 404
    calendar = await foundation.client.get(
        f"{STAFF}/jobs/calendar?start_date=2036-01-10&end_date=2036-01-10",
        headers=headers(),
    )
    assert calendar.json()["jobs"][0]["can_double_book"] is True
    assert body["location"]["written_address"] not in calendar.text


async def test_simultaneous_normal_bookings_and_capacity_on_another_team(foundation):
    body = payload(foundation, "2036-01-11")
    attempts = await asyncio.gather(submit(foundation, body), submit(foundation, body, "coworker"))
    assert sorted(result.status_code for result in attempts) == [201, 409]
    normal = await created(foundation, body, actor="other")
    assert normal["capacity_exception"] is False
    assert (await submit(foundation, payload(foundation, "2000-01-01"))).status_code in {400, 409}
    price_changed = await submit(
        foundation, {**body, "date": "2036-01-16", "expected_amount_minor": 1000}
    )
    assert price_changed.json()["code"] == "BOOKING_PRICE_CHANGED"
    mixed_day = "2036-01-17"
    await created(foundation, payload(foundation, mixed_day), actor="other")
    staff, public_hold = await asyncio.gather(
        submit(foundation, payload(foundation, mixed_day)),
        foundation.client.post(
            "/api/v1/public/holds",
            json={
                "date": mixed_day,
                "start_time": "09:00",
                "vehicle_count": 1,
                "service_ids": [str(foundation.services[0].id)],
            },
        ),
    )
    assert sorted((staff.status_code, public_hold.status_code)) == [201, 409]


async def test_overlap_preserves_prepaid_booking_and_manager_reschedules(foundation):
    day = "2036-01-12"
    original = await created(foundation, payload(foundation, day, email="customer@example.com"))
    original_id, original_job_id = uuid.UUID(original["id"]), uuid.UUID(original["job_id"])
    async with foundation.sessions() as session, session.begin():
        booking = await session.get(Booking, original_id)
        payment = await session.scalar(select(Payment).where(Payment.booking_id == original_id))
        payment.status = booking.payment_status = PaymentStatus.PAID
        payment.provider_payment_id = "local-test-deposit"
        transaction = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="payment",
            status="succeeded",
            amount_minor=5000,
        )
        session.add_all(
            [
                transaction,
                AuditEvent(
                    business_id=foundation.business,
                    entity_type="booking",
                    entity_id=original_id,
                    event_type="booking_policies_accepted",
                    metadata_json={"language": "ar"},
                ),
                NotificationOutbox(
                    business_id=foundation.business,
                    booking_id=original_id,
                    channel="email",
                    notification_type="appointment_reminder",
                    recipient="customer@example.com",
                    payload={"scheduled_start": booking.scheduled_start.isoformat()},
                    status=OutboxStatus.PENDING,
                    next_attempt_at=datetime.now(UTC),
                ),
            ]
        )
        await session.flush()
        payment_id, transaction_id = payment.id, transaction.id
    body = payload(
        foundation,
        day,
        email="new@example.com",
        overlap={
            "team_id": str(foundation.team_a),
            "confirmed": True,
        },
    )
    assert (await submit(foundation, body, "other")).status_code == 404
    assert (await submit(foundation, body, "foreign")).status_code == 404
    assert (
        await submit(
            foundation,
            {
                **body,
                "overlap": {**body["overlap"], "confirmed": False},
            },
        )
    ).status_code == 422
    assert (
        await submit(
            foundation,
            {
                **body,
                "replacement": {"job_id": original["job_id"]},
            },
        )
    ).status_code == 422
    key = uuid.uuid4()
    first, retry = await asyncio.gather(
        submit(foundation, body, key=key), submit(foundation, body, key=key)
    )
    assert first.status_code == retry.status_code == 201, first.text
    extra = first.json()
    assert retry.json() == extra and extra["capacity_exception"]
    assert extra["id"] != original["id"]
    assert extra["scheduled_start"] == original["scheduled_start"]
    offset = await created(foundation, {**body, "time": "09:30"})
    assert offset["scheduled_start"] != original["scheduled_start"]
    assert offset["capacity_exception"]
    await created(foundation, payload(foundation, day), actor="other")
    public = await foundation.client.post(
        "/api/v1/public/holds",
        json={
            "date": day,
            "start_time": "09:00",
            "vehicle_count": 1,
            "service_ids": [str(foundation.services[0].id)],
        },
    )
    assert public.status_code == 409
    calendar = await foundation.client.get(
        f"{STAFF}/jobs/calendar?start_date={day}&end_date={day}", headers=headers()
    )
    assert calendar.status_code == 200, calendar.text
    assert {item["job_id"] for item in calendar.json()["jobs"]} >= {
        original["job_id"],
        extra["job_id"],
        offset["job_id"],
    }
    async with foundation.sessions() as session:
        old = await session.get(Booking, original_id)
        old_job = await session.get(Job, original_job_id)
        assert old.status == BookingStatus.CONFIRMED and old.version == 1
        assert old.location_instructions == "Gate 2"
        assert old_job.status == JobStatus.ASSIGNED and old_job.version == 1
        assert (await session.get(Payment, payment_id)).provider_payment_id == "local-test-deposit"
        assert (await session.get(PaymentTransaction, transaction_id)).amount_minor == 5000
        for receipt, exception in ((original, False), (extra, True)):
            booking_id = uuid.UUID(receipt["id"])
            slot = await session.scalar(
                select(ScheduleSlot).where(ScheduleSlot.booking_id == booking_id)
            )
            assert slot.capacity_exception is exception and slot.status == SlotStatus.RESERVED
        notices = set(
            (
                await session.scalars(
                    select(NotificationOutbox.notification_type).where(
                        NotificationOutbox.booking_id == original_id
                    )
                )
            ).all()
        )
        assert notices == {"appointment_reminder", "booking_confirmed"}
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == uuid.UUID(extra["id"]),
                AuditEvent.event_type == "staff_calendar_capacity_exception",
            )
        )
        assert event.actor_auth_user_id and event.occurred_at
        assert event.metadata_json["team_id"] == str(foundation.team_a)
        assert datetime.fromisoformat(event.metadata_json["scheduled_start"]) == (
            datetime.fromisoformat(extra["scheduled_start"])
        )
        assert await session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_id == original_id,
                AuditEvent.event_type == "booking_policies_accepted",
            )
        )
        assert await session.scalar(
            select(NotificationOutbox.id).where(
                NotificationOutbox.booking_id == uuid.UUID(extra["id"]),
                NotificationOutbox.notification_type == "booking_confirmed",
            )
        )

    for actor, receipt, date in (("manager", extra, "2036-01-13"), ("admin", offset, "2036-01-14")):
        endpoint = f"{STAFF}/bookings/{receipt['id']}/reschedule"
        move = {
            "date": date,
            "time": "10:30",
            "team_id": str(foundation.team_b),
            "expected_version": 1,
            "reason": "New appointment agreed by phone",
            "client_event_id": uuid.uuid4().hex,
        }
        assert (
            await foundation.client.post(endpoint, json=move, headers=headers())
        ).status_code == 403
        for _ in range(2):
            result = await foundation.client.post(endpoint, json=move, headers=headers(actor))
            assert result.status_code == 200, result.text
            assert result.json()["booking_id"] == receipt["id"]
            assert result.json()["scheduled_start"].startswith(f"{date}T06:30")
            assert result.json()["assigned_team_id"] == str(foundation.team_b)


async def test_overlap_requires_existing_appointment_and_preserves_hard_blocks(foundation):
    day = "2036-01-15"
    body = payload(
        foundation,
        day,
        overlap={
            "team_id": str(foundation.team_a),
            "confirmed": True,
        },
    )
    assert (await submit(foundation, body)).json()["code"] == "NO_APPOINTMENT_OVERLAP"
    await created(foundation, payload(foundation, day))
    async with foundation.sessions() as session, session.begin():
        session.add(
            ScheduleSlot(
                business_id=foundation.business,
                resource_id=foundation.team_a,
                slot_start=datetime(2036, 1, 15, 5, 30, tzinfo=UTC),
                slot_end=datetime(2036, 1, 15, 7, tzinfo=UTC),
                status=SlotStatus.BLOCKED,
            )
        )
    assert (await submit(foundation, body)).json()["code"] == "TEAM_TIME_CONFLICT"


async def test_manager_cannot_override_a_blocked_interval_with_off_grid_start(foundation):
    original = await created(foundation, payload(foundation, "2036-01-19"))
    async with foundation.sessions() as session, session.begin():
        session.add(
            ScheduleSlot(
                business_id=foundation.business,
                resource_id=foundation.team_b,
                slot_start=datetime(2036, 1, 20, 5, tzinfo=UTC),
                slot_end=datetime(2036, 1, 20, 7, tzinfo=UTC),
                status=SlotStatus.BLOCKED,
            )
        )
    endpoint = f"{STAFF}/bookings/{original['id']}"
    options = await foundation.client.get(
        f"{endpoint}/reschedule-options?date=2036-01-20&time=09:30", headers=headers("manager")
    )
    assert {row["team_id"]: row["status"] for row in options.json()}[
        str(foundation.team_b)
    ] == "time_conflict"
    response = await foundation.client.post(
        f"{endpoint}/reschedule",
        json={
            "date": "2036-01-20",
            "time": "09:30",
            "team_id": str(foundation.team_b),
            "reason": "Check that a hard block cannot be overridden",
            "expected_version": 1,
            "override_turnaround": True,
            "client_event_id": uuid.uuid4().hex,
        },
        headers=headers("manager"),
    )
    assert response.status_code == 409 and response.json()["code"] == "TEAM_TIME_CONFLICT"
