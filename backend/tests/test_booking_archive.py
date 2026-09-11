import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from unittest.mock import AsyncMock

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.api.staff import router
from app.auth.dependencies import StaffContext, staff_context
from app.core.database import session_dependency
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.models import Base
from app.models.entities import Booking, Job, JobEvent, Payment
from app.services.staff_operations import (
    _job_rows,
    list_job_calendar,
    list_jobs,
    set_booking_archived,
)
from app.services.workforce import operations_dashboard


class AsyncFacade:
    """Execute real ORM queries against an isolated in-memory SQL database."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    async def flush(self):
        self.session.flush()

    @asynccontextmanager
    async def begin(self):
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


@pytest.fixture
def data():
    engine = create_engine("sqlite://")
    names = [
        "bookings",
        "jobs",
        "payments",
        "job_events",
        "booking_vehicles",
        "booking_services",
        "staff_profiles",
        "schedule_resources",
        "team_memberships",
        "leave_requests",
        "cancellation_requests",
        "business_sync_revisions",
    ]
    for name in names:
        Base.metadata.tables[name].create(engine)
    with engine.connect() as connection:
        connection.connection.create_function(
            "concat_ws",
            -1,
            lambda *args: " ".join(str(x) for x in args[1:] if x),
        )
    with Session(engine, expire_on_commit=False) as session:
        context = StaffContext(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "Test", StaffRole.MANAGER, "UTC"
        )
        start = datetime(2026, 9, 11, 12, tzinfo=UTC)
        booking = Booking(
            business_id=context.business_id,
            reference="ARCHIVE-TEST",
            hold_group_id=uuid.uuid4(),
            resource_id=uuid.uuid4(),
            status="completed",
            payment_choice="pay_after_service",
            payment_status="paid",
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
            vehicle_count=1,
            total_amount_minor=10000,
            currency_code="AED",
            customer_first_name="Test",
            customer_surname="Customer",
            customer_phone="+971500000000",
            written_address="Test",
            location_url="https://example.com",
            management_token_hash=uuid.uuid4().hex,
        )
        session.add(booking)
        session.flush()
        job = Job(
            booking_id=booking.id,
            business_id=context.business_id,
            status="completed",
            assigned_staff_id=context.staff_id,
            scheduled_start=start,
            scheduled_end=booking.scheduled_end,
        )
        session.add(job)
        session.flush()
        session.add_all(
            [
                Payment(
                    booking_id=booking.id,
                    status="paid",
                    method="cash",
                    amount_minor=10000,
                    currency_code="AED",
                ),
                JobEvent(
                    job_id=job.id,
                    booking_id=booking.id,
                    event_type="job_completed",
                    metadata_json={"history": "preserved"},
                ),
            ]
        )
        session.commit()
        yield AsyncFacade(session), context, booking, job
    engine.dispose()


@pytest.mark.parametrize("role", [StaffRole.MANAGER, StaffRole.ADMIN])
@pytest.mark.parametrize("status", ["completed", "cancelled"])
async def test_archive_filters_preserves_history_and_unarchives(data, monkeypatch, role, status):
    db, context, booking, job = data
    context = replace(context, role=role)
    booking.status = job.status = status
    db.session.commit()
    monkeypatch.setattr("app.services.workforce.attendance_overview", AsyncMock(return_value=[]))
    before = {
        table: db.session.execute(select(Base.metadata.tables[table])).all()
        for table in ("jobs", "payments", "job_events")
    }
    day = date(2026, 9, 11)
    assert len((await list_jobs(db, context, scope="all")).jobs) == 1
    assert (await operations_dashboard(db, context, day=day)).metrics[2].value == 1
    assert len((await list_job_calendar(db, context, start_date=day, end_date=day)).jobs) == (
        status != "cancelled"
    )
    await set_booking_archived(db, context, booking.id, archived=True)
    first_archived = booking.archived_at
    await set_booking_archived(db, context, booking.id, archived=True)
    assert booking.archived_at == first_archived
    db.session.commit()
    assert (await list_jobs(db, context, scope="all")).jobs == []
    assert (await list_jobs(db, replace(context, role=StaffRole.EMPLOYEE))).jobs == []
    assert (await list_job_calendar(db, context, start_date=day, end_date=day)).jobs == []
    assert (await operations_dashboard(db, context, day=day)).metrics[2].value == 0
    assert len((await list_jobs(db, context, scope="all", include_archived=True)).jobs) == 1
    assert len(await _job_rows(db, context, job_id=job.id, scope="all")) == 1
    assert db.session.get(Booking, booking.id) is not None
    for table, rows in before.items():
        assert db.session.execute(select(Base.metadata.tables[table])).all() == rows
    await set_booking_archived(db, context, booking.id, archived=False)
    db.session.commit()
    assert booking.archived_at is None
    assert len((await list_jobs(db, context, scope="all")).jobs) == 1
    assert (await operations_dashboard(db, context, day=day)).metrics[2].value == 1


async def test_rejects_employee_cross_business_and_active_booking(data):
    db, context, booking, _job = data
    for archived in (True, False):
        with pytest.raises(DomainError) as error:
            await set_booking_archived(
                db, replace(context, role=StaffRole.EMPLOYEE), booking.id, archived=archived
            )
        assert error.value.status_code == 403
    with pytest.raises(DomainError) as error:
        await list_jobs(db, replace(context, role=StaffRole.EMPLOYEE), include_archived=True)
    assert error.value.status_code == 403
    with pytest.raises(DomainError) as error:
        await set_booking_archived(
            db, replace(context, business_id=uuid.uuid4()), booking.id, archived=True
        )
    assert error.value.status_code == 404
    booking.status = "confirmed"
    with pytest.raises(DomainError) as error:
        await set_booking_archived(db, context, booking.id, archived=True)
    assert error.value.status_code == 409
    assert booking.archived_at is None


@pytest.mark.parametrize(
    "role,expected", [(StaffRole.MANAGER, 200), (StaffRole.ADMIN, 200), (StaffRole.EMPLOYEE, 403)]
)
async def test_endpoint_permissions_and_unarchive(data, role, expected):
    db, context, booking, _job = data
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[staff_context] = lambda: replace(context, role=role)
    app.dependency_overrides[session_dependency] = lambda: db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for archived in (True, False):
            response = await client.patch(
                f"/api/v1/staff/bookings/{booking.id}/archive", json={"archived": archived}
            )
            assert response.status_code == expected, response.text
            if expected == 200:
                assert bool(response.json()["archived_at"]) is archived


def test_migration_preserves_existing_booking_and_is_reversible():
    migration = import_module("migrations.versions.dbd74a2d3de9_add_booking_archived_at")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE bookings (id TEXT PRIMARY KEY)"))
        connection.execute(text("INSERT INTO bookings (id) VALUES ('existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(text("SELECT id, archived_at FROM bookings")).one() == (
                "existing",
                None,
            )
            migration.downgrade()
            assert connection.execute(text("SELECT id FROM bookings")).scalar_one() == "existing"
    engine.dispose()
