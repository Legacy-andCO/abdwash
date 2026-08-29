import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

import app.services.job_quality as job_quality
from app.auth.dependencies import StaffContext
from app.domain.enums import HoldStatus, JobPhotoStatus, JobStatus, SlotStatus, StaffRole
from app.domain.errors import ConflictError, DomainError
from app.integrations.supabase_storage import SupabaseStorageAdminClient
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    Job,
    JobChecklistItem,
    JobInspection,
    JobPhoto,
    Payment,
)
from app.schemas.staff import JobComplaintCreate, JobInspectionInput, JobPhotoCreate
from app.services.job_quality import (
    create_complaint,
    ensure_completion_quality,
    get_job_quality,
    save_inspection,
    snapshot_checklist_for_job,
)


def context(role: StaffRole = StaffRole.EMPLOYEE) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=role,
        timezone="Asia/Dubai",
    )


@pytest.mark.asyncio
async def test_authorized_job_accepts_current_five_column_job_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = context()
    booking = Booking(id=uuid.uuid4(), business_id=employee.business_id)
    job = Job(
        id=uuid.uuid4(),
        booking_id=booking.id,
        business_id=employee.business_id,
        status=JobStatus.ARRIVED,
    )
    payment = Payment(id=uuid.uuid4(), booking_id=booking.id)
    monkeypatch.setattr(
        job_quality,
        "_job_rows",
        AsyncMock(return_value=[(job, booking, payment, "Employee", "Team One")]),
    )

    authorized_job, authorized_booking = await job_quality._authorized_job(
        MagicMock(), employee, job.id
    )

    assert authorized_job is job
    assert authorized_booking is booking


@pytest.mark.asyncio
async def test_quality_without_existing_record_or_photos_returns_empty_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = context()
    booking = Booking(id=uuid.uuid4(), business_id=employee.business_id)
    job = Job(
        id=uuid.uuid4(),
        booking_id=booking.id,
        business_id=employee.business_id,
        status=JobStatus.ARRIVED,
    )
    monkeypatch.setattr(
        job_quality,
        "_authorized_job",
        AsyncMock(return_value=(job, booking)),
    )
    monkeypatch.setattr(job_quality, "snapshot_checklist_for_job", AsyncMock())
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    empty = MagicMock()
    empty.all.return_value = []
    session.scalars = AsyncMock(return_value=empty)

    result = await get_job_quality(session, employee, job.id)

    assert result.inspection is None
    assert result.photos == []
    assert result.checklist == []
    assert result.issues == []


@pytest.mark.asyncio
async def test_authorized_employee_can_save_inspection_for_operational_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = context()
    booking = Booking(id=uuid.uuid4())
    job = Job(
        id=uuid.uuid4(),
        booking_id=booking.id,
        business_id=employee.business_id,
        status=JobStatus.ARRIVED,
    )
    monkeypatch.setattr(
        job_quality,
        "_authorized_job",
        AsyncMock(return_value=(job, booking)),
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()

    await save_inspection(
        session,
        employee,
        job.id,
        JobInspectionInput(
            condition_notes="Clean overall",
            damage_category="scratch",
            damage_notes="Front-left door",
        ),
    )

    inspection = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], JobInspection)
    )
    assert inspection.business_id == employee.business_id
    assert inspection.job_id == job.id
    assert inspection.completed_by_staff_id == employee.staff_id
    assert inspection.damage_category == "scratch"


@pytest.mark.asyncio
async def test_unauthorized_job_is_hidden_instead_of_leaking_quality_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(job_quality, "_job_rows", AsyncMock(return_value=[]))

    with pytest.raises(DomainError) as error:
        await job_quality._authorized_job(MagicMock(), context(), uuid.uuid4())

    assert error.value.code == "JOB_NOT_FOUND"
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_employee_cannot_create_manager_only_complaint() -> None:
    employee = context()

    with pytest.raises(DomainError) as error:
        await create_complaint(
            MagicMock(),
            employee,
            uuid.uuid4(),
            JobComplaintCreate(description="Missed rear bumper"),
        )

    assert error.value.code == "STAFF_PERMISSION_DENIED"
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_rewash_clones_snapshots_without_changing_original_or_adding_revenue() -> None:
    manager = context(StaffRole.MANAGER)
    now = datetime.now(UTC)
    original = Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        business_id=manager.business_id,
        status=JobStatus.COMPLETED,
    )
    original_booking = Booking(
        id=original.booking_id,
        business_id=manager.business_id,
        customer_profile_id=None,
        payment_choice="pay_after_service",
        currency_code="AED",
        vehicle_count=1,
        customer_first_name="Amina",
        customer_surname="Khan",
        customer_email="amina@example.com",
        customer_phone="+971500000000",
        written_address="Yas Island",
        location_url="https://www.google.com/maps/search/?api=1&query=24,54",
        latitude=24,
        longitude=54,
        location_instructions="Visitor entrance",
    )
    old_vehicle = BookingVehicle(
        id=uuid.uuid4(),
        booking_id=original_booking.id,
        position=1,
        make="Toyota",
        model="Land Cruiser",
        vehicle_type="suv",
        plate_number="A 12345",
    )
    old_service = BookingService(
        id=uuid.uuid4(),
        booking_id=original_booking.id,
        booking_vehicle_id=old_vehicle.id,
        service_id=uuid.uuid4(),
        service_name="Premium Detail",
        unit_price_minor=25000,
        quantity=1,
        line_total_minor=25000,
    )
    hold = SimpleNamespace(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        status=HoldStatus.ACTIVE,
        expires_at=now + timedelta(minutes=5),
        vehicle_count=1,
        required_slot_count=1,
        resource_id=uuid.uuid4(),
        slot_start=now + timedelta(days=1),
        slot_end=now + timedelta(days=1, hours=2),
        consumed_at=None,
    )
    slot = SimpleNamespace(
        status=SlotStatus.HELD,
        hold_expires_at=hold.expires_at,
        booking_id=None,
        hold_group_id=hold.id,
        version=1,
    )
    original_checklist = SimpleNamespace(label="Final inspection", is_required=True, position=1)
    complaint = SimpleNamespace(id=uuid.uuid4())
    scalar_results = []
    for values in ([slot], [old_vehicle], [old_service], [original_checklist]):
        scalar_result = MagicMock()
        scalar_result.all.return_value = values
        scalar_results.append(scalar_result)
    added: list[object] = []

    def capture(item: object) -> None:
        if hasattr(item, "id") and item.id is None:
            item.id = uuid.uuid4()
        added.append(item)

    session = MagicMock()
    session.scalar = AsyncMock(return_value=hold)
    session.scalars = AsyncMock(side_effect=scalar_results)
    session.add = MagicMock(side_effect=capture)
    session.flush = AsyncMock()

    correction = await job_quality._create_correction_job(
        session,
        manager,
        original,
        original_booking,
        complaint,
        "valid-hold-token",
    )

    correction_booking = next(
        item for item in added if isinstance(item, Booking) and item is not original_booking
    )
    correction_payment = next(item for item in added if isinstance(item, Payment))
    correction_service = next(
        item for item in added if isinstance(item, BookingService) and item is not old_service
    )
    assert original.status == JobStatus.COMPLETED
    assert correction.status == JobStatus.ASSIGNED
    assert correction_booking.source == "rewash"
    assert correction_booking.total_amount_minor == 0
    assert correction_payment.amount_minor == 0
    assert correction_service.line_total_minor == 0
    assert correction_service.service_name == "Correction · Premium Detail"


@pytest.mark.asyncio
async def test_service_checklist_is_snapshotted_for_the_job() -> None:
    booking_service = BookingService(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        service_name="Premium Detail",
        unit_price_minor=1,
        quantity=1,
        line_total_minor=1,
    )
    second_service = BookingService(
        id=uuid.uuid4(),
        booking_id=booking_service.booking_id,
        service_id=uuid.uuid4(),
        service_name="Express Exterior",
        unit_price_minor=1,
        quantity=1,
        line_total_minor=1,
    )
    job = Job(
        id=uuid.uuid4(),
        booking_id=booking_service.booking_id,
        business_id=uuid.uuid4(),
        status=JobStatus.ASSIGNED,
    )
    result = MagicMock()
    result.all.return_value = [
        (
            booking_service,
            [
                {"label": "Inspect exterior", "required": True},
                {"label": "Final quality check", "required": False},
            ],
            1,
            "Toyota",
            "Land Cruiser",
        ),
        (
            second_service,
            [{"label": "Exterior wash", "required": True}],
            2,
            "Nissan",
            "Patrol",
        ),
    ]
    session = MagicMock()
    session.scalar = AsyncMock(return_value=0)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()

    await snapshot_checklist_for_job(session, job)

    added = [call.args[0] for call in session.add.call_args_list]
    assert [(item.label, item.is_required, item.position) for item in added] == [
        ("Vehicle 1 · Toyota Land Cruiser · Inspect exterior", True, 1),
        ("Vehicle 1 · Toyota Land Cruiser · Final quality check", False, 2),
        ("Vehicle 2 · Nissan Patrol · Exterior wash", True, 3),
    ]
    assert [item.booking_service_id for item in added] == [
        booking_service.id,
        booking_service.id,
        second_service.id,
    ]


@pytest.mark.asyncio
async def test_historical_completed_job_without_snapshot_remains_viewable() -> None:
    job = Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        status=JobStatus.COMPLETED,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=0)
    session.execute = AsyncMock()
    session.flush = AsyncMock()

    await snapshot_checklist_for_job(session, job)
    await ensure_completion_quality(session, job.id)

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_required_checklist_blocks_completion_but_empty_snapshot_does_not() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[2, 0])

    with pytest.raises(ConflictError) as error:
        await ensure_completion_quality(session, uuid.uuid4())
    assert error.value.code == "SERVICE_CHECKLIST_INCOMPLETE"

    await ensure_completion_quality(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_photo_upload_request_is_retry_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = context()
    job = Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        business_id=employee.business_id,
        status=JobStatus.ARRIVED,
    )
    existing = JobPhoto(
        id=uuid.uuid4(),
        business_id=employee.business_id,
        job_id=job.id,
        category="before",
        storage_path=f"business/{employee.business_id}/jobs/{job.id}/before/photo.jpg",
        content_type="image/jpeg",
        status=JobPhotoStatus.PENDING,
        created_by_staff_id=employee.staff_id,
        client_request_id="photo-request-123",
    )
    monkeypatch.setattr(
        job_quality,
        "_authorized_job",
        AsyncMock(return_value=(job, MagicMock())),
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=existing)
    session.flush = AsyncMock()

    result = await job_quality.prepare_photo_upload(
        session,
        employee,
        job.id,
        JobPhotoCreate(
            category="before",
            content_type="image/jpeg",
            client_request_id="photo-request-123",
        ),
    )

    assert result is existing
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_private_storage_adapter_uses_signed_upload_and_download_urls() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/upload/sign/" in request.url.path:
            return httpx.Response(200, json={"url": "/signed/upload?token=upload-token"})
        if "/object/info/" in request.url.path:
            return httpx.Response(200, json={"size": 1024, "mimetype": "image/jpeg"})
        return httpx.Response(200, json={"signedURL": "/object/sign/job?token=view-token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        storage = SupabaseStorageAdminClient(
            client,
            supabase_url="https://example.supabase.co",
            service_role_key="server-only-test-key",
            bucket="job-quality-photos",
        )
        assert await storage.create_signed_upload("business/1/jobs/2/before/photo.jpg") == (
            "upload-token"
        )
        assert await storage.object_info("business/1/jobs/2/before/photo.jpg") == {
            "size": 1024,
            "mimetype": "image/jpeg",
        }
        signed = await storage.create_signed_download("business/1/jobs/2/before/photo.jpg", 300)

    assert signed == ("https://example.supabase.co/storage/v1/object/sign/job?token=view-token")
    assert all(
        request.headers["authorization"] == "Bearer server-only-test-key" for request in seen
    )
    assert all("server-only-test-key" not in str(request.url) for request in seen)
    assert seen[0].content == b'{"upsert":true}'


@pytest.mark.asyncio
async def test_private_storage_network_failure_is_temporary_unavailable() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("storage timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        storage = SupabaseStorageAdminClient(
            client,
            supabase_url="https://example.supabase.co",
            service_role_key="server-only-test-key",
            bucket="job-quality-photos",
        )
        with pytest.raises(DomainError) as error:
            await storage.create_signed_upload("business/1/jobs/2/before/photo.jpg")

    assert error.value.code == "JOB_PHOTO_STORAGE_UNAVAILABLE"
    assert error.value.status_code == 503


def test_quality_models_enforce_job_scoped_constraints() -> None:
    checklist_constraints = {
        constraint.name for constraint in JobChecklistItem.__table__.constraints
    }
    photo_constraints = {constraint.name for constraint in JobPhoto.__table__.constraints}
    assert "uq_job_checklist_position" in checklist_constraints
    assert "uq_job_photo_business_request" in photo_constraints
    assert "ck_job_photos_job_photo_category" in photo_constraints
    assert "ck_job_photos_job_photo_status" in photo_constraints
