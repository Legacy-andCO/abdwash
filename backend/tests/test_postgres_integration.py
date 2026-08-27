import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.api.staff as staff_api
from app.api.public import router as public_router
from app.api.staff import router as staff_router
from app.auth.dependencies import StaffContext, optional_identity, staff_context
from app.auth.verifier import AuthenticationError, VerifiedIdentity
from app.core.config import Settings
from app.core.database import create_engine, query_count, session_dependency
from app.domain.enums import JobStatus, SlotStatus, StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models import Base
from app.models.entities import (
    AttendanceSession,
    Booking,
    BookingService,
    Business,
    BusinessSettings,
    BusinessSyncRevision,
    CancellationRequest,
    IdempotencyRecord,
    Job,
    JobChecklistItem,
    JobComplaint,
    JobInspection,
    NotificationOutbox,
    Payment,
    ScheduleResource,
    ScheduleSlot,
    Service,
    SlotHoldGroup,
    StaffProfile,
    TeamMembership,
)
from app.schemas.public import BookingCreate, HoldCreate, HoldResponse
from app.schemas.staff import (
    AttendanceAction,
    JobAction,
    JobChecklistUpdate,
    JobComplaintCreate,
    JobComplaintReview,
    JobInspectionInput,
    JobQualityIssueCreate,
    ShiftAssignmentCreate,
    ShiftCreate,
)
from app.services.bookings import create_booking
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.job_quality import (
    add_issue,
    create_complaint,
    review_complaint,
    save_inspection,
    update_checklist,
)
from app.services.scheduling import create_hold, hold_token_hash
from app.services.staff_operations import transition_job
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


class StubAuthVerifier:
    def __init__(self, identities: dict[str, uuid.UUID]) -> None:
        self.identities = identities

    async def verify(self, token: str) -> VerifiedIdentity:
        user_id = self.identities.get(token)
        if user_id is None:
            raise AuthenticationError("Unknown integration token")
        return VerifiedIdentity(user_id=user_id, claims={"sub": str(user_id)})


class StubSupabaseAdmin:
    def __init__(self, created_user_id: uuid.UUID) -> None:
        self.created_user_id = created_user_id

    async def create_staff_user(self, username: str, password: str) -> uuid.UUID:
        assert username
        assert len(password) >= 8
        return self.created_user_id

    async def update_staff_user(
        self,
        user_id: uuid.UUID,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        assert user_id
        assert username is not None or password is not None


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
                checklist_template=[
                    {"label": "Exterior wash", "required": True},
                    {"label": "Final inspection", "required": True},
                ],
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
                "instructions": "Meet at the main entrance",
            },
            "vehicles": [
                {
                    "make": "Toyota",
                    "model": "Camry",
                    "vehicle_type": "sedan",
                    "plate_number": "A 12345",
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
async def test_shift_creation_assignment_and_modification(
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
        team = ScheduleResource(
            business_id=context.business_id,
            name=f"Shift Team {uuid.uuid4().hex[:6]}",
            resource_type="mobile_team",
            is_active=True,
        )
        session.add(team)
        await session.flush()
    invalid_membership = ShiftAssignmentCreate(
        staff_id=context.staff_id,
        shift_id=shift.id,
        work_date=date(2035, 1, 6),
        team_id=team.id,
    )
    with pytest.raises(ConflictError) as membership_error:
        async with database() as session, session.begin():
            await assign_shift(session, context, invalid_membership)
    assert membership_error.value.code == "STAFF_NOT_ON_TEAM"
    async with database() as session, session.begin():
        session.add(
            TeamMembership(
                resource_id=team.id,
                staff_profile_id=context.staff_id,
                is_active=True,
            )
        )
    request = ShiftAssignmentCreate(
        staff_id=context.staff_id,
        shift_id=shift.id,
        work_date=date(2035, 1, 7),
        team_id=team.id,
    )
    async with database() as session, session.begin():
        assigned = await assign_shift(session, context, request)
    assert assigned.staff_id == context.staff_id
    async with database() as session, session.begin():
        later_shift = await create_shift(
            session,
            context,
            ShiftCreate(
                name=f"Later {uuid.uuid4().hex[:6]}",
                start_time=time(10),
                end_time=time(19),
            ),
        )
        modified = await assign_shift(
            session,
            context,
            request.model_copy(update={"shift_id": later_shift.id}),
        )
    assert modified.id == assigned.id
    assert modified.shift_id == later_shift.id
    assert modified.shift_name == later_shift.name


@pytest.mark.asyncio
async def test_job_quality_completion_and_zero_value_rewash_workflow(
    database: async_sessionmaker[AsyncSession],
) -> None:
    context = await _staff_context(database, suffix="quality")
    hold = await _attempt_hold(
        database,
        HoldCreate(date=date(2035, 6, 1), start_time=time(9), vehicle_count=1),
    )
    async with database() as session:
        service_id = (await session.scalars(select(Service.id))).one()
    request = BookingCreate.model_validate(
        {
            "hold_token": hold.hold_token,
            "contact": {
                "first_name": "Quality",
                "surname": "Customer",
                "email": "quality@example.com",
                "phone": "+971500000099",
            },
            "location": {
                "written_address": "Yas Island, Abu Dhabi",
                "location_url": "https://maps.google.com/?q=Yas+Island",
                "instructions": "Visitor entrance",
            },
            "vehicles": [
                {
                    "make": "Toyota",
                    "model": "Land Cruiser",
                    "vehicle_type": "suv",
                    "plate_number": "Q 100",
                    "service_id": service_id,
                }
            ],
            "payment_choice": "pay_after_service",
        }
    )
    async with database() as session, session.begin():
        created = await create_booking(session, request, None)
        job = (await session.scalars(select(Job).where(Job.booking_id == created.id))).one()
        job.status = JobStatus.IN_PROGRESS
        job.started_at = datetime.now(UTC)
        job_id = job.id

    async with database() as session, session.begin():
        await save_inspection(
            session,
            context,
            job_id,
            JobInspectionInput(
                condition_notes="Condition checked",
                damage_category="scratch",
                damage_notes="Front-left door",
            ),
        )
        await add_issue(
            session,
            context,
            job_id,
            JobQualityIssueCreate(
                category="customer_request",
                note="Customer requested extra attention on rear glass.",
            ),
        )

    with pytest.raises(ConflictError) as incomplete_error:
        async with database() as session, session.begin():
            await transition_job(
                session,
                context,
                job_id,
                JobAction(client_event_id="quality-incomplete"),
                JobStatus.COMPLETED,
            )
    assert incomplete_error.value.code == "SERVICE_CHECKLIST_INCOMPLETE"

    async with database() as session, session.begin():
        checklist = list(
            (
                await session.scalars(
                    select(JobChecklistItem)
                    .where(JobChecklistItem.job_id == job_id)
                    .order_by(JobChecklistItem.position)
                )
            ).all()
        )
        await update_checklist(
            session,
            context,
            job_id,
            JobChecklistUpdate(
                client_event_id="quality-checklist-complete",
                items=[{"id": item.id, "completed": True} for item in checklist],
            ),
        )
        completed = await transition_job(
            session,
            context,
            job_id,
            JobAction(client_event_id="quality-job-complete"),
            JobStatus.COMPLETED,
        )
        complaint = await create_complaint(
            session,
            context,
            job_id,
            JobComplaintCreate(description="Missed area on rear bumper."),
        )
    assert completed.status == JobStatus.COMPLETED

    correction_hold = await _attempt_hold(
        database,
        HoldCreate(date=date(2035, 6, 2), start_time=time(11), vehicle_count=1),
    )
    async with database() as session, session.begin():
        reviewed = await review_complaint(
            session,
            context,
            job_id,
            complaint.id,
            JobComplaintReview(
                decision="approve_rewash",
                review_note="Complimentary correction approved.",
                hold_token=correction_hold.hold_token,
            ),
        )
        correction_job_id = reviewed.correction_job_id
    assert correction_job_id is not None

    async with database() as session, session.begin():
        original = await session.get(Job, job_id)
        correction = await session.get(Job, correction_job_id)
        assert original is not None and original.status == JobStatus.COMPLETED
        assert correction is not None
        correction_booking = await session.get(Booking, correction.booking_id)
        correction_payment = (
            await session.scalars(
                select(Payment).where(Payment.booking_id == correction.booking_id)
            )
        ).one()
        assert correction_booking is not None
        assert correction_booking.source == "rewash"
        assert correction_booking.total_amount_minor == 0
        assert correction_payment.amount_minor == 0
        correction.status = JobStatus.IN_PROGRESS
        correction.started_at = datetime.now(UTC)

    async with database() as session, session.begin():
        correction_checklist = list(
            (
                await session.scalars(
                    select(JobChecklistItem).where(
                        JobChecklistItem.job_id == correction_job_id
                    )
                )
            ).all()
        )
        await update_checklist(
            session,
            context,
            correction_job_id,
            JobChecklistUpdate(
                client_event_id="rewash-checklist-complete",
                items=[
                    {"id": item.id, "completed": True}
                    for item in correction_checklist
                ],
            ),
        )
        await transition_job(
            session,
            context,
            correction_job_id,
            JobAction(client_event_id="rewash-job-complete"),
            JobStatus.COMPLETED,
        )

    async with database() as session:
        resolved = await session.get(JobComplaint, complaint.id)
        inspection = (
            await session.scalars(
                select(JobInspection).where(JobInspection.job_id == job_id)
            )
        ).one()
    assert resolved is not None and resolved.status == "resolved"
    assert inspection.damage_category == "scratch"


@pytest.mark.asyncio
async def test_staff_write_workflow_uses_real_context_dependency_without_leaking_transaction(
    database: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_auth_id = uuid.uuid4()
    employee_auth_id = uuid.uuid4()
    async with database() as session, session.begin():
        business = (await session.scalars(select(Business))).one()
        manager = StaffProfile(
            business_id=business.id,
            auth_user_id=manager_auth_id,
            username=f"workflow-manager-{uuid.uuid4().hex[:6]}",
            display_name="Workflow Manager",
            role=StaffRole.MANAGER,
            is_active=True,
        )
        session.add(manager)

    initial_hold = await _attempt_hold(
        database,
        HoldCreate(date=date(2035, 2, 1), start_time=time(9), vehicle_count=1),
    )
    async with database() as session:
        service_id = (await session.scalars(select(Service.id))).one()
    booking_request = BookingCreate.model_validate(
        {
            "hold_token": initial_hold.hold_token,
            "contact": {
                "first_name": "Write",
                "surname": "Workflow",
                "email": "write-workflow@example.com",
                "phone": "+971500000002",
            },
            "location": {
                "written_address": "Yas Island, Abu Dhabi",
                "location_url": "https://maps.google.com/?q=Yas+Island",
                "instructions": "Use the visitor parking entrance",
            },
            "vehicles": [
                {
                    "make": "Toyota",
                    "model": "Land Cruiser",
                    "vehicle_type": "suv",
                    "plate_number": "B 67890",
                    "service_id": service_id,
                }
            ],
            "payment_choice": "pay_after_service",
        }
    )
    async with database() as session, session.begin():
        booking = await create_booking(session, booking_request, None)
    async with database() as session:
        job_id = (await session.scalars(select(Job.id).where(Job.booking_id == booking.id))).one()

    cancellation_hold = await _attempt_hold(
        database,
        HoldCreate(date=date(2035, 2, 3), start_time=time(13), vehicle_count=1),
    )
    cancellation_booking_request = booking_request.model_copy(
        update={"hold_token": cancellation_hold.hold_token}
    )
    async with database() as session, session.begin():
        cancellation_booking = await create_booking(session, cancellation_booking_request, None)
        rejected_cancellation = CancellationRequest(
            booking_id=cancellation_booking.id,
            requester_type="customer",
            reason="Reject this integration request",
            status="requested",
            requested_at=datetime.now(UTC),
        )
        approved_cancellation = CancellationRequest(
            booking_id=cancellation_booking.id,
            requester_type="customer",
            reason="Approve this integration request",
            status="requested",
            requested_at=datetime.now(UTC),
        )
        session.add_all([rejected_cancellation, approved_cancellation])
        await session.flush()
        rejected_cancellation_id = rejected_cancellation.id
        approved_cancellation_id = approved_cancellation.id

    test_app = FastAPI()
    test_app.include_router(staff_router)

    async def sessions() -> AsyncIterator[AsyncSession]:
        async with database() as session:
            yield session

    test_app.dependency_overrides[session_dependency] = sessions
    test_app.state.auth_verifier = StubAuthVerifier(
        {"manager-token": manager_auth_id, "employee-token": employee_auth_id}
    )
    test_app.state.http_client = httpx.AsyncClient()
    monkeypatch.setattr(staff_api, "_admin", lambda _request: StubSupabaseAdmin(employee_auth_id))
    monkeypatch.setattr(
        staff_api,
        "get_settings",
        lambda: SimpleNamespace(google_routes_api_key=None),
    )

    @test_app.exception_handler(DomainError)
    async def error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @test_app.get("/_staff-transaction-state")
    async def transaction_state(
        session: Annotated[AsyncSession, Depends(session_dependency)],
        _context: Annotated[StaffContext, Depends(staff_context)],
    ) -> dict[str, bool]:
        return {"in_transaction": session.in_transaction()}

    manager_headers = {"Authorization": "Bearer manager-token"}
    employee_headers = {"Authorization": "Bearer employee-token"}
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        context_response = await client.get("/api/v1/staff/context", headers=manager_headers)
        assert context_response.status_code == 200
        transaction_response = await client.get(
            "/_staff-transaction-state", headers=manager_headers
        )
        assert transaction_response.json() == {"in_transaction": False}

        employee_response = await client.post(
            "/api/v1/staff/users",
            headers=manager_headers,
            json={
                "display_name": "Workflow Employee",
                "username": f"workflow-employee-{uuid.uuid4().hex[:6]}",
                "phone": "+971501234567",
                "role": "employee",
                "temporary_password": "Integration-Only-123!",
            },
        )
        assert employee_response.status_code == 201, employee_response.text
        employee_id = employee_response.json()["id"]

        updated_employee = await client.patch(
            f"/api/v1/staff/users/{employee_id}",
            headers=manager_headers,
            json={"display_name": "Workflow Employee Updated"},
        )
        assert updated_employee.status_code == 200, updated_employee.text
        assert updated_employee.json()["display_name"] == "Workflow Employee Updated"
        deactivated_employee = await client.patch(
            f"/api/v1/staff/users/{employee_id}",
            headers=manager_headers,
            json={"is_active": False},
        )
        assert deactivated_employee.status_code == 200, deactivated_employee.text
        assert deactivated_employee.json()["is_active"] is False
        reactivated_employee = await client.patch(
            f"/api/v1/staff/users/{employee_id}",
            headers=manager_headers,
            json={"is_active": True},
        )
        assert reactivated_employee.status_code == 200, reactivated_employee.text
        temporary_password = await client.post(
            f"/api/v1/staff/users/{employee_id}/password",
            headers=manager_headers,
            json={"mode": "temporary"},
        )
        assert temporary_password.status_code == 200, temporary_password.text
        assert temporary_password.json()["must_change_password"] is True
        assert len(temporary_password.json()["temporary_password"]) >= 8
        forced_change = await client.get(
            "/api/v1/staff/jobs",
            headers=employee_headers,
            params={"view": "today", "scope": "my"},
        )
        assert forced_change.status_code == 403, forced_change.text
        assert forced_change.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
        employee_password_change = await client.patch(
            "/api/v1/staff/profile",
            headers=employee_headers,
            json={"password": "Employee-Replacement-123!"},
        )
        assert employee_password_change.status_code == 200, employee_password_change.text
        assert employee_password_change.json()["must_change_password"] is False

        manual_password = await client.post(
            f"/api/v1/staff/users/{employee_id}/password",
            headers=manager_headers,
            json={"mode": "manual", "new_password": "Manager-Selected-123!"},
        )
        assert manual_password.status_code == 200, manual_password.text
        assert manual_password.json() == {
            "must_change_password": False,
            "temporary_password": None,
        }

        team_response = await client.post(
            "/api/v1/staff/teams",
            headers=manager_headers,
            json={"name": f"Workflow Team {uuid.uuid4().hex[:6]}"},
        )
        assert team_response.status_code == 201, team_response.text
        team_id = team_response.json()["id"]

        renamed_team = await client.patch(
            f"/api/v1/staff/teams/{team_id}",
            headers=manager_headers,
            json={"name": f"Renamed Workflow Team {uuid.uuid4().hex[:6]}"},
        )
        assert renamed_team.status_code == 200, renamed_team.text

        members_response = await client.put(
            f"/api/v1/staff/teams/{team_id}/members",
            headers=manager_headers,
            json={"staff_ids": [employee_id]},
        )
        assert members_response.status_code == 200, members_response.text
        assert [member["id"] for member in members_response.json()["members"]] == [employee_id]
        removed_response = await client.put(
            f"/api/v1/staff/teams/{team_id}/members",
            headers=manager_headers,
            json={"staff_ids": []},
        )
        assert removed_response.status_code == 200
        restored_response = await client.put(
            f"/api/v1/staff/teams/{team_id}/members",
            headers=manager_headers,
            json={"staff_ids": [employee_id]},
        )
        assert restored_response.status_code == 200
        deactivated_team = await client.patch(
            f"/api/v1/staff/teams/{team_id}",
            headers=manager_headers,
            json={"is_active": False},
        )
        assert deactivated_team.status_code == 200, deactivated_team.text
        assert deactivated_team.json()["is_active"] is False
        reactivated_team = await client.patch(
            f"/api/v1/staff/teams/{team_id}",
            headers=manager_headers,
            json={"is_active": True},
        )
        assert reactivated_team.status_code == 200, reactivated_team.text

        shift_response = await client.post(
            "/api/v1/staff/shifts",
            headers=manager_headers,
            json={
                "name": f"Workflow Morning {uuid.uuid4().hex[:6]}",
                "start_time": "09:00:00",
                "end_time": "18:00:00",
            },
        )
        assert shift_response.status_code == 201, shift_response.text
        assignment_response = await client.put(
            "/api/v1/staff/shift-assignments",
            headers=manager_headers,
            json={
                "staff_id": employee_id,
                "shift_id": shift_response.json()["id"],
                "work_date": "2035-02-05",
                "team_id": team_id,
            },
        )
        assert assignment_response.status_code == 200, assignment_response.text

        leave_response = await client.post(
            "/api/v1/staff/leave",
            headers=employee_headers,
            json={
                "start_date": "2035-03-01",
                "end_date": "2035-03-01",
                "reason": "Integration workflow",
            },
        )
        assert leave_response.status_code == 201, leave_response.text
        review_response = await client.post(
            f"/api/v1/staff/leave/{leave_response.json()['id']}/review",
            headers=manager_headers,
            json={"decision": "approved"},
        )
        assert review_response.status_code == 200, review_response.text

        second_leave_response = await client.post(
            "/api/v1/staff/leave",
            headers=employee_headers,
            json={
                "start_date": "2035-03-02",
                "end_date": "2035-03-02",
                "reason": "Rejected integration workflow",
            },
        )
        assert second_leave_response.status_code == 201, second_leave_response.text
        rejected_leave_response = await client.post(
            f"/api/v1/staff/leave/{second_leave_response.json()['id']}/review",
            headers=manager_headers,
            json={"decision": "rejected"},
        )
        assert rejected_leave_response.status_code == 200, rejected_leave_response.text

        manager_profile = await client.patch(
            "/api/v1/staff/profile",
            headers=manager_headers,
            json={"display_name": "Workflow Manager Updated"},
        )
        assert manager_profile.status_code == 200, manager_profile.text

        employee_profile = await client.patch(
            "/api/v1/staff/profile",
            headers=employee_headers,
            json={
                "display_name": "Workflow Employee Self Updated",
            },
        )
        assert employee_profile.status_code == 200, employee_profile.text

        clock_in_response = await client.post(
            "/api/v1/staff/attendance/clock-in",
            headers=employee_headers,
            json={},
        )
        assert clock_in_response.status_code == 200, clock_in_response.text
        clock_out_response = await client.post(
            "/api/v1/staff/attendance/clock-out",
            headers=employee_headers,
            json={},
        )
        assert clock_out_response.status_code == 200, clock_out_response.text
        assert clock_out_response.json()["clock_out_at"] is not None

        job_assignment_response = await client.patch(
            f"/api/v1/staff/jobs/{job_id}/assignment",
            headers=manager_headers,
            json={"team_id": team_id, "client_event_id": str(uuid.uuid4())},
        )
        assert job_assignment_response.status_code == 200, job_assignment_response.text
        assert job_assignment_response.json()["assigned_team_id"] == team_id
        assert job_assignment_response.json()["assigned_team_name"] == "Mobile Team 2"

        for customer_search in ("Write", "workflow", "wri"):
            searched_jobs = await client.get(
                "/api/v1/staff/jobs",
                headers=manager_headers,
                params={
                    "view": "all",
                    "scope": "all",
                    "search": customer_search,
                },
            )
            assert searched_jobs.status_code == 200, searched_jobs.text
            assert job_id in {
                uuid.UUID(item["id"]) for item in searched_jobs.json()["jobs"]
            }
        unrelated_search = await client.get(
            "/api/v1/staff/jobs",
            headers=manager_headers,
            params={"view": "all", "scope": "all", "search": "NoSuchCustomer"},
        )
        assert unrelated_search.status_code == 200, unrelated_search.text
        assert job_id not in {
            uuid.UUID(item["id"]) for item in unrelated_search.json()["jobs"]
        }

        unassigned_jobs = await client.get(
            "/api/v1/staff/jobs",
            headers=manager_headers,
            params={"view": "unassigned", "scope": "all"},
        )
        assert job_id not in {
            uuid.UUID(item["id"]) for item in unassigned_jobs.json()["jobs"]
        }

        reassignment_response = await client.patch(
            f"/api/v1/staff/jobs/{job_id}/assignment",
            headers=manager_headers,
            json={"staff_id": employee_id, "client_event_id": str(uuid.uuid4())},
        )
        assert reassignment_response.status_code == 200, reassignment_response.text
        assert reassignment_response.json()["assigned_staff_id"] == employee_id
        assert (
            reassignment_response.json()["assigned_staff_name"]
            == "Workflow Employee Updated"
        )

        employee_jobs = await client.get(
            "/api/v1/staff/jobs",
            headers=employee_headers,
            params={"view": "all", "scope": "my"},
        )
        assert employee_jobs.status_code == 200, employee_jobs.text
        assert job_id in {uuid.UUID(item["id"]) for item in employee_jobs.json()["jobs"]}

        replacement_hold = await _attempt_hold(
            database,
            HoldCreate(date=date(2035, 2, 2), start_time=time(11), vehicle_count=1),
        )
        reschedule_response = await client.post(
            f"/api/v1/staff/bookings/{booking.id}/reschedule",
            headers=manager_headers,
            json={"hold_token": replacement_hold.hold_token},
        )
        assert reschedule_response.status_code == 200, reschedule_response.text
        assert reschedule_response.json()["scheduled_start"].startswith("2035-02-02")
        assert reschedule_response.json()["assigned_team_id"] is not None
        assert reschedule_response.json()["assigned_team_name"] == "Mobile Team 1"

        trip_event_id = str(uuid.uuid4())
        start_trip_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/start-trip",
            headers=employee_headers,
            json={
                "client_event_id": trip_event_id,
                "origin": {"latitude": 24.4539, "longitude": 54.3773},
            },
        )
        assert start_trip_response.status_code == 200, start_trip_response.text
        assert start_trip_response.json()["status"] == "en_route"
        duplicate_trip_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/start-trip",
            headers=employee_headers,
            json={"client_event_id": trip_event_id, "origin": None},
        )
        assert duplicate_trip_response.status_code == 200, duplicate_trip_response.text
        async with database() as session:
            trip_notifications = (
                await session.scalars(
                    select(NotificationOutbox).where(
                        NotificationOutbox.booking_id == booking.id,
                        NotificationOutbox.notification_type == "driver_en_route",
                    )
                )
            ).all()
        assert len(trip_notifications) == 1
        arrive_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/arrive",
            headers=employee_headers,
            json={"client_event_id": str(uuid.uuid4())},
        )
        assert arrive_response.status_code == 200, arrive_response.text
        assert arrive_response.json()["status"] == "arrived"
        assert arrive_response.json()["arrived_at"] is not None
        start_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/start",
            headers=employee_headers,
            json={"client_event_id": str(uuid.uuid4())},
        )
        assert start_response.status_code == 200, start_response.text
        assert start_response.json()["status"] == "in_progress"
        complete_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/complete",
            headers=employee_headers,
            json={"client_event_id": str(uuid.uuid4())},
        )
        assert complete_response.status_code == 200, complete_response.text
        assert complete_response.json()["status"] == "completed"
        cash_response = await client.post(
            f"/api/v1/staff/jobs/{job_id}/cash-payment",
            headers=employee_headers,
            json={"client_event_id": str(uuid.uuid4())},
        )
        assert cash_response.status_code == 200, cash_response.text
        assert cash_response.json()["payment_status"] == "paid"

        rejected_response = await client.post(
            f"/api/v1/staff/cancellations/{rejected_cancellation_id}/review",
            headers=manager_headers,
            json={
                "decision": "rejected",
                "client_event_id": str(uuid.uuid4()),
            },
        )
        assert rejected_response.status_code == 200, rejected_response.text
        assert rejected_response.json()["status"] == "rejected"
        approved_response = await client.post(
            f"/api/v1/staff/cancellations/{approved_cancellation_id}/review",
            headers=manager_headers,
            json={
                "decision": "approved",
                "client_event_id": str(uuid.uuid4()),
            },
        )
        assert approved_response.status_code == 200, approved_response.text
        assert approved_response.json()["status"] == "approved"
        sync_response = await client.get(
            "/api/v1/staff/sync-state", headers=manager_headers
        )
        assert sync_response.status_code == 200, sync_response.text
        assert sync_response.json()["jobs"] > 0
        assert sync_response.json()["workforce"] > 0
        assert sync_response.json()["schedule"] > 0
        assert sync_response.json()["finance"] > 0

    await test_app.state.http_client.aclose()


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
                "instructions": "Meet by the lobby",
            },
            "vehicles": [
                {
                    "make": "Nissan",
                    "model": "Patrol",
                    "vehicle_type": "suv",
                    "plate_number": "C 24680",
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
        booking_business_id = await session.scalar(
            select(Booking.business_id).where(
                Booking.id == idempotency_record.resource_id
            )
        )
        assert booking_business_id is not None
        revision = (
            await session.scalars(
                select(BusinessSyncRevision).where(
                    BusinessSyncRevision.business_id == booking_business_id
                )
            )
        ).one()
        assert revision.jobs_revision == 1
        assert revision.schedule_revision == 1
        assert revision.finance_revision == 1
