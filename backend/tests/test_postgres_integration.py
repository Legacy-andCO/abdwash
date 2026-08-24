import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.public import router as public_router
from app.auth.dependencies import StaffContext, optional_identity
from app.core.config import Settings
from app.core.database import create_engine, query_count, session_dependency
from app.domain.enums import SlotStatus, StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models import Base
from app.models.entities import (
    AttendanceSession,
    Booking,
    BookingService,
    Business,
    BusinessSettings,
    IdempotencyRecord,
    NotificationOutbox,
    ScheduleResource,
    ScheduleSlot,
    Service,
    SlotHoldGroup,
    StaffProfile,
)
from app.schemas.public import BookingCreate, HoldCreate, HoldResponse
from app.schemas.staff import AttendanceAction, ShiftAssignmentCreate, ShiftCreate
from app.services.bookings import create_booking
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.scheduling import create_hold, hold_token_hash
from app.services.workforce import assign_shift, clock_in, create_shift
from app.workers.notifications import claim_batch

RAW_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _skip_reason() -> str | None:
    if not RAW_TEST_DATABASE_URL:
        return "TEST_DATABASE_URL is not configured for an isolated PostgreSQL database"
    url = make_url(RAW_TEST_DATABASE_URL)
    if url.get_backend_name() != "postgresql":
        return "TEST_DATABASE_URL is not PostgreSQL"
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        return "destructive integration tests are restricted to a local PostgreSQL host"
    if "test" not in (url.database or "").lower():
        return "the isolated PostgreSQL database name must contain 'test'"
    return None


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(_skip_reason() is not None, reason=_skip_reason() or "unavailable"),
]


@pytest.fixture(scope="module")
async def database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    assert RAW_TEST_DATABASE_URL is not None
    url = RAW_TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_engine(
        Settings(app_env="test", database_url=url, db_pool_size=5, db_max_overflow=0)
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session, session.begin():
        business = Business(name="AbdWash", slug="abdwash")
        session.add(business)
        await session.flush()
        session.add(
            BusinessSettings(
                business_id=business.id,
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
        )
        session.add(
            ScheduleResource(
                business_id=business.id,
                name="Mobile Team 1",
                resource_type="mobile_team",
                sort_order=1,
            )
        )
        session.add(
            Service(
                business_id=business.id,
                name="Integration Wash",
                price_minor=12500,
                estimated_duration_minutes=120,
                sort_order=1,
            )
        )
    yield factory
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _attempt_hold(
    factory: async_sessionmaker[AsyncSession], request: HoldCreate
) -> HoldResponse:
    async with factory() as session, session.begin():
        return await create_hold(session, request)


@pytest.mark.asyncio
async def test_concurrent_slot_acquisition_allows_one_winner(
    database: async_sessionmaker[AsyncSession],
) -> None:
    request = HoldCreate(date=date(2035, 1, 2), start_time=time(9), vehicle_count=1)
    results = await asyncio.gather(
        _attempt_hold(database, request), _attempt_hold(database, request), return_exceptions=True
    )
    assert sum(isinstance(result, HoldResponse) for result in results) == 1
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    async with database() as session:
        active = list(
            (
                await session.scalars(
                    select(ScheduleSlot).where(ScheduleSlot.status == SlotStatus.HELD)
                )
            ).all()
        )
    assert len(active) == 1


@pytest.mark.asyncio
async def test_multi_slot_failure_leaves_no_partial_hold(
    database: async_sessionmaker[AsyncSession],
) -> None:
    day = date(2035, 1, 3)
    await _attempt_hold(database, HoldCreate(date=day, start_time=time(15), vehicle_count=1))
    with pytest.raises(ConflictError, match="consecutive"):
        await _attempt_hold(database, HoldCreate(date=day, start_time=time(13), vehicle_count=3))
    async with database() as session:
        slots = list(
            (
                await session.scalars(
                    select(ScheduleSlot).where(
                        ScheduleSlot.slot_start >= datetime(2035, 1, 3, 9, tzinfo=UTC),
                        ScheduleSlot.slot_start < datetime(2035, 1, 3, 11, tzinfo=UTC),
                    )
                )
            ).all()
        )
    assert all(slot.status == SlotStatus.FREE for slot in slots)


@pytest.mark.asyncio
async def test_expired_hold_is_reclaimed_and_booking_snapshots_price(
    database: async_sessionmaker[AsyncSession],
) -> None:
    first = await _attempt_hold(
        database, HoldCreate(date=date(2035, 1, 4), start_time=time(11), vehicle_count=1)
    )
    async with database() as session, session.begin():
        group = (
            await session.scalars(
                select(SlotHoldGroup).where(
                    SlotHoldGroup.token_hash == hold_token_hash(first.hold_token)
                )
            )
        ).first()
        assert group is not None
        group.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        slots = list(
            (
                await session.scalars(
                    select(ScheduleSlot).where(ScheduleSlot.hold_group_id == group.id)
                )
            ).all()
        )
        for slot in slots:
            slot.hold_expires_at = group.expires_at
    replacement = await _attempt_hold(
        database, HoldCreate(date=date(2035, 1, 4), start_time=time(11), vehicle_count=1)
    )
    assert replacement.hold_token != first.hold_token

    async with database() as session:
        service_id = (await session.scalars(select(Service.id))).one()
    booking_request = BookingCreate.model_validate(
        {
            "hold_token": replacement.hold_token,
            "contact": {
                "first_name": "Amina",
                "surname": "Khan",
                "email": "amina@example.com",
                "phone": "+971500000000",
            },
            "location": {
                "written_address": "Dubai Marina",
                "location_url": "https://maps.google.com/?q=Dubai",
            },
            "vehicles": [
                {
                    "make": "Toyota",
                    "model": "Camry",
                    "vehicle_type": "sedan",
                    "service_id": service_id,
                }
            ],
            "payment_choice": "pay_after_service",
        }
    )
    async with database() as session, session.begin():
        response = await create_booking(session, booking_request, None)
    assert response.total_amount_minor == 12500
    assert response.status == "confirmed"
    async with database() as session:
        booking = await session.get(Booking, response.id)
        snapshot = (
            await session.scalars(
                select(BookingService).where(BookingService.booking_id == response.id)
            )
        ).one()
        outbox = (
            await session.scalars(
                select(NotificationOutbox).where(NotificationOutbox.booking_id == response.id)
            )
        ).one()
    assert booking is not None
    assert booking.customer_first_name == "Amina"
    assert booking.customer_phone == "+971500000000"
    assert snapshot.service_name == "Integration Wash"
    assert snapshot.unit_price_minor == 12500
    assert outbox.recipient == "amina@example.com"
    assert outbox.notification_type == "booking_confirmed"
    assert outbox.payload == {"booking_reference": response.reference}
    assert "management_token" not in outbox.payload

    first_claim = await claim_batch(database, worker_id="worker-a", batch_size=10)
    duplicate_claim = await claim_batch(database, worker_id="worker-b", batch_size=10)
    assert first_claim == [outbox.id]
    assert duplicate_claim == []


@pytest.mark.asyncio
async def test_idempotency_retry_and_conflicting_reuse(
    database: async_sessionmaker[AsyncSession],
) -> None:
    payload_hash = canonical_request_hash({"vehicle_count": 1})
    resource_id = uuid.uuid4()
    async with database() as session, session.begin():
        assert (
            await find_idempotent_response(
                session,
                scope="public",
                operation="test",
                key="same-network-request",
                request_hash=payload_hash,
            )
            is None
        )
        store_idempotent_response(
            session,
            scope="public",
            operation="test",
            key="same-network-request",
            request_hash=payload_hash,
            response_status=201,
            response_json={"id": str(resource_id)},
            resource_id=resource_id,
        )
    async with database() as session, session.begin():
        existing = await find_idempotent_response(
            session,
            scope="public",
            operation="test",
            key="same-network-request",
            request_hash=payload_hash,
        )
        assert existing is not None
        assert existing.response_json == {"id": str(resource_id)}
    async with database() as session, session.begin():
        with pytest.raises(ConflictError):
            await find_idempotent_response(
                session,
                scope="public",
                operation="test",
                key="same-network-request",
                request_hash=canonical_request_hash({"vehicle_count": 2}),
            )


async def _staff_context(factory: async_sessionmaker[AsyncSession], *, suffix: str) -> StaffContext:
    async with factory() as session, session.begin():
        business = (await session.scalars(select(Business))).one()
        profile = StaffProfile(
            business_id=business.id,
            auth_user_id=uuid.uuid4(),
            username=f"integration-{suffix}-{uuid.uuid4().hex[:8]}",
            display_name=f"Integration {suffix}",
            role=StaffRole.MANAGER,
            is_active=True,
        )
        session.add(profile)
        await session.flush()
        return StaffContext(
            auth_user_id=profile.auth_user_id,
            staff_id=profile.id,
            business_id=business.id,
            business_name=business.name,
            role=StaffRole.MANAGER,
            timezone="Asia/Dubai",
        )


@pytest.mark.asyncio
async def test_concurrent_clock_in_returns_one_open_session(
    database: async_sessionmaker[AsyncSession],
) -> None:
    context = await _staff_context(database, suffix="attendance")

    async def attempt() -> uuid.UUID:
        async with database() as session, session.begin():
            record = await clock_in(session, context, AttendanceAction())
            return record.id

    results = await asyncio.gather(attempt(), attempt())
    assert results[0] == results[1]
    async with database() as session:
        open_sessions = list(
            (
                await session.scalars(
                    select(AttendanceSession).where(
                        AttendanceSession.staff_profile_id == context.staff_id,
                        AttendanceSession.clock_out_at.is_(None),
                    )
                )
            ).all()
        )
    assert len(open_sessions) == 1


@pytest.mark.asyncio
async def test_shift_creation_assignment_and_duplicate_conflict(
    database: async_sessionmaker[AsyncSession],
) -> None:
    context = await _staff_context(database, suffix="shift")
    async with database() as session, session.begin():
        shift = await create_shift(
            session,
            context,
            ShiftCreate(
                name=f"Morning {uuid.uuid4().hex[:6]}", start_time=time(9), end_time=time(18)
            ),
        )
    request = ShiftAssignmentCreate(
        staff_id=context.staff_id,
        shift_id=shift.id,
        work_date=date(2035, 1, 7),
    )
    async with database() as session, session.begin():
        assigned = await assign_shift(session, context, request)
    assert assigned.staff_id == context.staff_id
    with pytest.raises(ConflictError, match="already has a shift"):
        async with database() as session, session.begin():
            await assign_shift(session, context, request)


@pytest.mark.asyncio
async def test_public_api_guest_booking_and_query_count_guard(
    database: async_sessionmaker[AsyncSession],
) -> None:
    test_app = FastAPI()
    test_app.include_router(public_router)

    async def sessions() -> AsyncIterator[AsyncSession]:
        async with database() as session:
            yield session

    test_app.dependency_overrides[session_dependency] = sessions
    test_app.dependency_overrides[optional_identity] = lambda: None

    @test_app.exception_handler(DomainError)
    async def error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code})

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        query_count.set(0)
        catalogue = await client.get("/api/v1/public/catalogue")
        assert catalogue.status_code == 200
        assert query_count.get() <= 2
        service_id = catalogue.json()["services"][0]["id"]
        query_count.set(0)
        availability = await client.get(
            "/api/v1/public/availability", params={"date": "2035-01-05", "vehicle_count": 1}
        )
        assert availability.status_code == 200
        assert query_count.get() <= 3
        assert [slot["time"] for slot in availability.json()["slots"]] == [
            "09:00:00",
            "11:00:00",
            "13:00:00",
            "15:00:00",
            "17:00:00",
            "19:00:00",
        ]
        query_count.set(0)
        hold = await client.post(
            "/api/v1/public/holds",
            json={"date": "2035-01-05", "start_time": "09:00:00", "vehicle_count": 1},
        )
        assert hold.status_code == 201
        assert query_count.get() <= 8
        payload = {
            "hold_token": hold.json()["hold_token"],
            "contact": {
                "first_name": "Guest",
                "surname": "Customer",
                "email": "guest@example.com",
                "phone": "+971500000001",
            },
            "location": {
                "written_address": "Business Bay",
                "location_url": "https://maps.google.com/?q=Business+Bay",
            },
            "vehicles": [
                {
                    "make": "Nissan",
                    "model": "Patrol",
                    "vehicle_type": "suv",
                    "service_id": service_id,
                }
            ],
            "payment_choice": "pay_now",
        }
        query_count.set(0)
        booking = await client.post(
            "/api/v1/public/bookings",
            json=payload,
            headers={"Idempotency-Key": "api-integration-booking-1"},
        )
        assert booking.status_code == 201
        assert query_count.get() <= 15
        assert booking.json()["status"] == "pending_payment"
        assert booking.json()["payment_status"] == "pending"
        retried = await client.post(
            "/api/v1/public/bookings",
            json=payload,
            headers={"Idempotency-Key": "api-integration-booking-1"},
        )
        assert retried.status_code == 201
        assert retried.json() == booking.json()
        management_token = booking.json()["management_token"]
        managed = await client.get(
            "/api/v1/public/bookings/manage",
            headers={"X-Booking-Management-Token": management_token},
        )
        assert managed.status_code == 200
        assert managed.json()["reference"] == booking.json()["reference"]
        assert managed.json()["cancellation_eligible"] is False

    async with database() as session:
        idempotency_record = (
            await session.scalars(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.operation == "create_booking",
                    IdempotencyRecord.idempotency_key == "api-integration-booking-1",
                )
            )
        ).one()
        assert "management_token" not in idempotency_record.response_json
