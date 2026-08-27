import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import (
    BookingStatus,
    ComplaintStatus,
    HoldStatus,
    JobPhotoStatus,
    JobStatus,
    PaymentStatus,
    SlotStatus,
)
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    Job,
    JobChecklistItem,
    JobComplaint,
    JobEvent,
    JobInspection,
    JobPhoto,
    JobQualityIssue,
    Payment,
    ScheduleSlot,
    Service,
    SlotHoldGroup,
    StaffProfile,
)
from app.schemas.staff import (
    JobChecklistItemView,
    JobChecklistUpdate,
    JobComplaintCreate,
    JobComplaintReview,
    JobComplaintView,
    JobInspectionInput,
    JobInspectionView,
    JobPhotoCreate,
    JobPhotoView,
    JobQualityIssueCreate,
    JobQualityIssueView,
    JobQualityView,
)
from app.services.management_tokens import create_management_token, management_token_hash
from app.services.scheduling import hold_token_hash
from app.services.staff_operations import _job_rows


async def _authorized_job(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[Job, Booking]:
    rows = await _job_rows(
        session,
        context,
        job_id=job_id,
        scope="all" if context.role in {"manager", "admin"} else "my",
        limit=1,
        lock=lock,
    )
    if not rows:
        raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    job, booking, _payment, _staff_name = rows[0]
    return job, booking


def _require_manager(context: StaffContext) -> None:
    if context.role not in {"manager", "admin"}:
        raise DomainError(
            "STAFF_PERMISSION_DENIED",
            "Manager access is required for this action.",
            status_code=403,
        )


async def snapshot_checklist_for_job(
    session: AsyncSession,
    job: Job,
    *,
    allow_historical: bool = False,
) -> None:
    existing = await session.scalar(
        select(func.count(JobChecklistItem.id)).where(JobChecklistItem.job_id == job.id)
    )
    if existing or (
        not allow_historical and job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}
    ):
        return
    rows = (
        await session.execute(
            select(
                BookingService,
                Service.checklist_template,
                BookingVehicle.position,
                BookingVehicle.make,
                BookingVehicle.model,
            )
            .join(Service, Service.id == BookingService.service_id)
            .join(BookingVehicle, BookingVehicle.id == BookingService.booking_vehicle_id)
            .where(BookingService.booking_id == job.booking_id)
            .order_by(BookingVehicle.position, BookingService.created_at, BookingService.id)
        )
    ).all()
    position = 1
    multiple_vehicles = len({row[2] for row in rows}) > 1
    for booking_service, template, vehicle_position, vehicle_make, vehicle_model in rows:
        for configured in template or []:
            label = str(configured.get("label", "")).strip()
            if not label:
                continue
            if multiple_vehicles:
                vehicle = f"{vehicle_make} {vehicle_model}".strip()
                label = f"Vehicle {vehicle_position} · {vehicle} · {label}"
            session.add(
                JobChecklistItem(
                    business_id=job.business_id,
                    job_id=job.id,
                    booking_service_id=booking_service.id,
                    label=label[:160],
                    is_required=bool(configured.get("required", True)),
                    position=position,
                )
            )
            position += 1
    await session.flush()


async def get_job_quality(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    *,
    access_urls: dict[uuid.UUID, str] | None = None,
) -> JobQualityView:
    job, _booking = await _authorized_job(session, context, job_id)
    await snapshot_checklist_for_job(session, job)
    inspection = await session.scalar(
        select(JobInspection).where(
            JobInspection.job_id == job.id,
            JobInspection.business_id == context.business_id,
        )
    )
    checklist = list(
        (
            await session.scalars(
                select(JobChecklistItem)
                .where(
                    JobChecklistItem.job_id == job.id,
                    JobChecklistItem.business_id == context.business_id,
                )
                .order_by(JobChecklistItem.position)
            )
        ).all()
    )
    photos = list(
        (
            await session.scalars(
                select(JobPhoto)
                .where(
                    JobPhoto.job_id == job.id,
                    JobPhoto.business_id == context.business_id,
                    JobPhoto.status == JobPhotoStatus.READY,
                )
                .order_by(JobPhoto.created_at)
            )
        ).all()
    )
    issues = list(
        (
            await session.scalars(
                select(JobQualityIssue)
                .where(
                    JobQualityIssue.job_id == job.id,
                    JobQualityIssue.business_id == context.business_id,
                )
                .order_by(JobQualityIssue.created_at)
            )
        ).all()
    )
    complaints = list(
        (
            await session.scalars(
                select(JobComplaint)
                .where(
                    JobComplaint.original_job_id == job.id,
                    JobComplaint.business_id == context.business_id,
                )
                .order_by(JobComplaint.created_at)
            )
        ).all()
    )
    staff_ids = {
        value
        for value in [
            inspection.completed_by_staff_id if inspection else None,
            *(item.completed_by_staff_id for item in checklist),
            *(item.created_by_staff_id for item in photos),
            *(item.created_by_staff_id for item in issues),
            *(item.created_by_staff_id for item in complaints),
            *(item.reviewed_by_staff_id for item in complaints),
        ]
        if value is not None
    }
    names: dict[uuid.UUID, str] = {}
    if staff_ids:
        name_rows = (
            await session.execute(
                select(StaffProfile.id, StaffProfile.display_name).where(
                    StaffProfile.id.in_(staff_ids),
                    StaffProfile.business_id == context.business_id,
                )
            )
        ).all()
        names = {row[0]: row[1] for row in name_rows}
    required = [item for item in checklist if item.is_required]
    return JobQualityView(
        job_id=job.id,
        inspection=(
            JobInspectionView(
                id=inspection.id,
                condition_notes=inspection.condition_notes,
                damage_category=inspection.damage_category,
                damage_notes=inspection.damage_notes,
                completed_by_staff_id=inspection.completed_by_staff_id,
                completed_by_staff_name=names.get(inspection.completed_by_staff_id, "Staff"),
                completed_at=inspection.completed_at,
            )
            if inspection
            else None
        ),
        checklist=[
            JobChecklistItemView(
                id=item.id,
                label=item.label,
                is_required=item.is_required,
                position=item.position,
                completed_at=item.completed_at,
                completed_by_staff_id=item.completed_by_staff_id,
                completed_by_staff_name=names.get(item.completed_by_staff_id)
                if item.completed_by_staff_id
                else None,
            )
            for item in checklist
        ],
        photos=[
            JobPhotoView(
                id=item.id,
                category=item.category,
                caption=item.caption,
                status=item.status,
                created_by_staff_id=item.created_by_staff_id,
                created_by_staff_name=names.get(item.created_by_staff_id, "Staff"),
                created_at=item.created_at,
                access_url=(access_urls or {}).get(item.id),
            )
            for item in photos
        ],
        issues=[
            JobQualityIssueView(
                id=item.id,
                category=item.category,
                note=item.note,
                photo_id=item.photo_id,
                created_by_staff_id=item.created_by_staff_id,
                created_by_staff_name=names.get(item.created_by_staff_id, "Staff"),
                created_at=item.created_at,
            )
            for item in issues
        ],
        complaints=[
            JobComplaintView(
                id=item.id,
                description=item.description,
                status=item.status,
                review_note=item.review_note,
                created_by_staff_id=item.created_by_staff_id,
                created_by_staff_name=names.get(item.created_by_staff_id, "Staff"),
                created_at=item.created_at,
                reviewed_by_staff_id=item.reviewed_by_staff_id,
                reviewed_by_staff_name=names.get(item.reviewed_by_staff_id)
                if item.reviewed_by_staff_id
                else None,
                reviewed_at=item.reviewed_at,
                correction_job_id=item.correction_job_id,
            )
            for item in complaints
        ],
        required_completed=sum(item.completed_at is not None for item in required),
        required_total=len(required),
        before_photo_count=sum(item.category == "before" for item in photos),
        after_photo_count=sum(item.category == "after" for item in photos),
        issue_count=len(issues),
        can_complete=all(item.completed_at is not None for item in required),
    )


async def save_inspection(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    payload: JobInspectionInput,
) -> None:
    job, booking = await _authorized_job(session, context, job_id, lock=True)
    if job.status not in {JobStatus.ARRIVED, JobStatus.IN_PROGRESS}:
        raise ConflictError(
            "INSPECTION_NOT_AVAILABLE",
            "Vehicle inspection is available after arrival and during the wash.",
        )
    inspection = await session.scalar(
        select(JobInspection).where(JobInspection.job_id == job.id).with_for_update()
    )
    now = datetime.now(UTC)
    if inspection is None:
        inspection = JobInspection(
            business_id=context.business_id,
            job_id=job.id,
            completed_by_staff_id=context.staff_id,
        )
        session.add(inspection)
    inspection.condition_notes = payload.condition_notes
    inspection.damage_category = payload.damage_category
    inspection.damage_notes = payload.damage_notes
    inspection.completed_by_staff_id = context.staff_id
    inspection.completed_at = now
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="inspection_completed",
            metadata_json={
                "damage_recorded": bool(payload.damage_category or payload.damage_notes)
            },
        )
    )
    await session.flush()


async def update_checklist(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    payload: JobChecklistUpdate,
) -> None:
    job, booking = await _authorized_job(session, context, job_id, lock=True)
    if job.status != JobStatus.IN_PROGRESS:
        raise ConflictError(
            "CHECKLIST_NOT_AVAILABLE",
            "Start the wash before updating its checklist.",
        )
    if await session.scalar(
        select(JobEvent.id).where(
            JobEvent.job_id == job.id,
            JobEvent.client_event_id == payload.client_event_id,
        )
    ):
        return
    await snapshot_checklist_for_job(session, job)
    ids = {item.id for item in payload.items}
    rows = list(
        (
            await session.scalars(
                select(JobChecklistItem)
                .where(
                    JobChecklistItem.id.in_(ids),
                    JobChecklistItem.job_id == job.id,
                    JobChecklistItem.business_id == context.business_id,
                )
                .with_for_update()
            )
        ).all()
    )
    if {item.id for item in rows} != ids:
        raise DomainError("CHECKLIST_ITEM_NOT_FOUND", "Checklist item not found.", status_code=404)
    updates = {item.id: item.completed for item in payload.items}
    now = datetime.now(UTC)
    for item in rows:
        item.completed_at = now if updates[item.id] else None
        item.completed_by_staff_id = context.staff_id if updates[item.id] else None
    all_rows = list(
        (
            await session.scalars(select(JobChecklistItem).where(JobChecklistItem.job_id == job.id))
        ).all()
    )
    required_complete = all(item.completed_at is not None for item in all_rows if item.is_required)
    completion_already_recorded = False
    if required_complete:
        completion_already_recorded = bool(
            await session.scalar(
                select(JobEvent.id).where(
                    JobEvent.job_id == job.id,
                    JobEvent.event_type == "checklist_completed",
                )
            )
        )
    if required_complete and not completion_already_recorded:
        session.add(
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                actor_staff_id=context.staff_id,
                event_type="checklist_completed",
                client_event_id=payload.client_event_id,
                metadata_json={
                    "completed": sum(item.completed_at is not None for item in all_rows),
                    "total": len(all_rows),
                },
            )
        )
    await session.flush()


async def ensure_completion_quality(session: AsyncSession, job_id: uuid.UUID) -> None:
    incomplete = await session.scalar(
        select(func.count(JobChecklistItem.id)).where(
            JobChecklistItem.job_id == job_id,
            JobChecklistItem.is_required.is_(True),
            JobChecklistItem.completed_at.is_(None),
        )
    )
    if incomplete:
        raise ConflictError(
            "SERVICE_CHECKLIST_INCOMPLETE",
            "Complete all required service checklist items before finishing the job.",
        )


async def prepare_photo_upload(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    payload: JobPhotoCreate,
) -> JobPhoto:
    job, _booking = await _authorized_job(session, context, job_id)
    existing = await session.scalar(
        select(JobPhoto).where(
            JobPhoto.business_id == context.business_id,
            JobPhoto.client_request_id == payload.client_request_id,
        )
    )
    if existing:
        if (
            existing.job_id != job.id
            or existing.category != payload.category
            or existing.content_type != payload.content_type
        ):
            raise ConflictError("PHOTO_REQUEST_REUSED", "That photo request was already used.")
        return existing
    if payload.category in {"before", "damage", "issue"} and job.status not in {
        JobStatus.ARRIVED,
        JobStatus.IN_PROGRESS,
    }:
        raise ConflictError(
            "PHOTO_NOT_AVAILABLE",
            "Before, damage, and issue photos are available after arrival.",
        )
    if payload.category == "after" and job.status != JobStatus.IN_PROGRESS:
        raise ConflictError("PHOTO_NOT_AVAILABLE", "After photos are available during the wash.")
    photo_id = uuid.uuid4()
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[payload.content_type]
    path = f"business/{context.business_id}/jobs/{job.id}/{payload.category}/{photo_id}.{extension}"
    photo = JobPhoto(
        id=photo_id,
        business_id=context.business_id,
        job_id=job.id,
        category=payload.category,
        storage_path=path,
        content_type=payload.content_type,
        caption=payload.caption,
        status=JobPhotoStatus.PENDING,
        created_by_staff_id=context.staff_id,
        client_request_id=payload.client_request_id,
    )
    session.add(photo)
    await session.flush()
    return photo


async def load_pending_photo(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    photo_id: uuid.UUID,
) -> JobPhoto:
    await _authorized_job(session, context, job_id)
    photo = await session.scalar(
        select(JobPhoto).where(
            JobPhoto.id == photo_id,
            JobPhoto.job_id == job_id,
            JobPhoto.business_id == context.business_id,
        )
    )
    if photo is None:
        raise DomainError("JOB_PHOTO_NOT_FOUND", "Photo not found.", status_code=404)
    return photo


async def confirm_photo(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    photo_id: uuid.UUID,
    *,
    object_info: dict[str, Any],
    max_bytes: int,
) -> None:
    job, booking = await _authorized_job(session, context, job_id, lock=True)
    photo = await session.scalar(
        select(JobPhoto)
        .where(
            JobPhoto.id == photo_id,
            JobPhoto.job_id == job.id,
            JobPhoto.business_id == context.business_id,
        )
        .with_for_update()
    )
    if photo is None:
        raise DomainError("JOB_PHOTO_NOT_FOUND", "Photo not found.", status_code=404)
    if photo.status == JobPhotoStatus.READY:
        return
    size = int(object_info.get("size") or object_info.get("metadata", {}).get("size") or 0)
    mimetype = str(
        object_info.get("mimetype")
        or object_info.get("metadata", {}).get("mimetype")
        or photo.content_type
    )
    if size <= 0 or size > max_bytes or mimetype != photo.content_type:
        raise DomainError("INVALID_JOB_PHOTO", "Uploaded photo is invalid.")
    photo.status = JobPhotoStatus.READY
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type=f"{photo.category}_photo_added",
            metadata_json={"photo_id": str(photo.id)},
        )
    )
    await session.flush()


async def add_issue(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    payload: JobQualityIssueCreate,
) -> None:
    job, booking = await _authorized_job(session, context, job_id)
    if job.status not in {JobStatus.ARRIVED, JobStatus.IN_PROGRESS}:
        raise ConflictError("ISSUE_NOT_AVAILABLE", "Issues can be reported after arrival.")
    if payload.photo_id and not await session.scalar(
        select(JobPhoto.id).where(
            JobPhoto.id == payload.photo_id,
            JobPhoto.job_id == job.id,
            JobPhoto.business_id == context.business_id,
            JobPhoto.status == JobPhotoStatus.READY,
        )
    ):
        raise DomainError("JOB_PHOTO_NOT_FOUND", "Issue photo not found.", status_code=404)
    session.add(
        JobQualityIssue(
            business_id=context.business_id,
            job_id=job.id,
            category=payload.category,
            note=payload.note,
            photo_id=payload.photo_id,
            created_by_staff_id=context.staff_id,
        )
    )
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="quality_issue_reported",
            metadata_json={"category": payload.category},
        )
    )
    await session.flush()


async def create_complaint(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    payload: JobComplaintCreate,
) -> JobComplaint:
    _require_manager(context)
    job, booking = await _authorized_job(session, context, job_id)
    if job.status != JobStatus.COMPLETED:
        raise ConflictError("COMPLAINT_NOT_AVAILABLE", "Complaints are recorded on completed jobs.")
    complaint = JobComplaint(
        business_id=context.business_id,
        original_job_id=job.id,
        description=payload.description,
        status=ComplaintStatus.OPEN,
        created_by_staff_id=context.staff_id,
    )
    session.add(complaint)
    session.add(
        JobEvent(
            job_id=job.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="complaint_opened",
            metadata_json={},
        )
    )
    await session.flush()
    return complaint


async def review_complaint(
    session: AsyncSession,
    context: StaffContext,
    job_id: uuid.UUID,
    complaint_id: uuid.UUID,
    payload: JobComplaintReview,
) -> JobComplaint:
    _require_manager(context)
    original_job, original_booking = await _authorized_job(session, context, job_id, lock=True)
    complaint = await session.scalar(
        select(JobComplaint)
        .where(
            JobComplaint.id == complaint_id,
            JobComplaint.original_job_id == original_job.id,
            JobComplaint.business_id == context.business_id,
        )
        .with_for_update()
    )
    if complaint is None:
        raise DomainError("COMPLAINT_NOT_FOUND", "Complaint not found.", status_code=404)
    if complaint.status in {ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED}:
        raise ConflictError("COMPLAINT_ALREADY_CLOSED", "The complaint is already closed.")
    now = datetime.now(UTC)
    complaint.review_note = payload.review_note
    complaint.reviewed_by_staff_id = context.staff_id
    complaint.reviewed_at = now
    if payload.decision == "approve_rewash":
        if complaint.correction_job_id:
            return complaint
        correction_job = await _create_correction_job(
            session,
            context,
            original_job,
            original_booking,
            complaint,
            payload.hold_token or "",
        )
        complaint.status = ComplaintStatus.REWASH_APPROVED
        complaint.correction_job_id = correction_job.id
        event_type = "rewash_approved"
    else:
        complaint.status = ComplaintStatus(payload.decision)
        event_type = f"complaint_{payload.decision}"
    session.add(
        JobEvent(
            job_id=original_job.id,
            booking_id=original_booking.id,
            actor_staff_id=context.staff_id,
            event_type=event_type,
            metadata_json={"complaint_id": str(complaint.id)},
        )
    )
    if payload.decision == "approve_rewash":
        session.add(
            JobEvent(
                job_id=original_job.id,
                booking_id=original_booking.id,
                actor_staff_id=context.staff_id,
                event_type="rewash_scheduled",
                metadata_json={
                    "complaint_id": str(complaint.id),
                    "correction_job_id": str(complaint.correction_job_id),
                },
            )
        )
    await session.flush()
    return complaint


async def _create_correction_job(
    session: AsyncSession,
    context: StaffContext,
    original_job: Job,
    original_booking: Booking,
    complaint: JobComplaint,
    hold_token: str,
) -> Job:
    now = datetime.now(UTC)
    hold = await session.scalar(
        select(SlotHoldGroup)
        .where(SlotHoldGroup.token_hash == hold_token_hash(hold_token))
        .with_for_update()
    )
    if hold is None or hold.business_id != context.business_id:
        raise DomainError("INVALID_HOLD", "The correction hold is invalid.")
    if hold.status != HoldStatus.ACTIVE or hold.expires_at <= now:
        raise ConflictError("HOLD_EXPIRED", "The correction hold has expired.")
    if hold.vehicle_count != original_booking.vehicle_count:
        raise ConflictError(
            "HOLD_VEHICLE_COUNT_MISMATCH",
            "The correction hold is for a different vehicle count.",
        )
    slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(ScheduleSlot.hold_group_id == hold.id)
                .order_by(ScheduleSlot.id)
                .with_for_update()
            )
        ).all()
    )
    if len(slots) != hold.required_slot_count or any(
        slot.status != SlotStatus.HELD
        or slot.hold_expires_at is None
        or slot.hold_expires_at <= now
        for slot in slots
    ):
        raise ConflictError("HOLD_EXPIRED", "The correction hold is no longer valid.")
    new_booking_id = uuid.uuid4()
    token = create_management_token(new_booking_id)
    booking = Booking(
        id=new_booking_id,
        business_id=context.business_id,
        reference=f"RW-{secrets.token_hex(5).upper()}",
        customer_profile_id=original_booking.customer_profile_id,
        hold_group_id=hold.id,
        resource_id=hold.resource_id,
        status=BookingStatus.CONFIRMED,
        payment_choice=original_booking.payment_choice,
        payment_status=PaymentStatus.PAID,
        scheduled_start=hold.slot_start,
        scheduled_end=hold.slot_end,
        vehicle_count=original_booking.vehicle_count,
        total_amount_minor=0,
        currency_code=original_booking.currency_code,
        source="rewash",
        customer_first_name=original_booking.customer_first_name,
        customer_surname=original_booking.customer_surname,
        customer_email=original_booking.customer_email,
        customer_phone=original_booking.customer_phone,
        written_address=original_booking.written_address,
        location_url=original_booking.location_url,
        latitude=original_booking.latitude,
        longitude=original_booking.longitude,
        location_instructions=original_booking.location_instructions,
        management_token_hash=management_token_hash(token),
    )
    session.add(booking)
    await session.flush()
    vehicles = list(
        (
            await session.scalars(
                select(BookingVehicle)
                .where(BookingVehicle.booking_id == original_booking.id)
                .order_by(BookingVehicle.position)
            )
        ).all()
    )
    services = list(
        (
            await session.scalars(
                select(BookingService).where(BookingService.booking_id == original_booking.id)
            )
        ).all()
    )
    service_by_vehicle = {item.booking_vehicle_id: item for item in services}
    for old_vehicle in vehicles:
        new_vehicle = BookingVehicle(
            booking_id=booking.id,
            vehicle_id=old_vehicle.vehicle_id,
            position=old_vehicle.position,
            make=old_vehicle.make,
            model=old_vehicle.model,
            year=old_vehicle.year,
            vehicle_type=old_vehicle.vehicle_type,
            colour=old_vehicle.colour,
            plate_number=old_vehicle.plate_number,
            notes=old_vehicle.notes,
        )
        session.add(new_vehicle)
        await session.flush()
        old_service = service_by_vehicle[old_vehicle.id]
        session.add(
            BookingService(
                booking_id=booking.id,
                booking_vehicle_id=new_vehicle.id,
                service_id=old_service.service_id,
                service_name=f"Correction · {old_service.service_name}",
                unit_price_minor=0,
                list_price_minor=0,
                discount_minor=0,
                quantity=1,
                line_total_minor=0,
            )
        )
    session.add(
        Payment(
            booking_id=booking.id,
            status=PaymentStatus.PAID,
            method="complimentary_rewash",
            amount_minor=0,
            currency_code=booking.currency_code,
            paid_at=now,
        )
    )
    correction = Job(
        booking_id=booking.id,
        business_id=context.business_id,
        assigned_resource_id=hold.resource_id,
        status=JobStatus.ASSIGNED,
        scheduled_start=hold.slot_start,
        scheduled_end=hold.slot_end,
    )
    session.add(correction)
    await session.flush()
    original_items = list(
        (
            await session.scalars(
                select(JobChecklistItem)
                .where(JobChecklistItem.job_id == original_job.id)
                .order_by(JobChecklistItem.position)
            )
        ).all()
    )
    for item in original_items:
        session.add(
            JobChecklistItem(
                business_id=context.business_id,
                job_id=correction.id,
                label=item.label,
                is_required=item.is_required,
                position=item.position,
            )
        )
    if not original_items:
        await snapshot_checklist_for_job(session, correction, allow_historical=True)
    hold.status = HoldStatus.CONSUMED
    hold.consumed_at = now
    for slot in slots:
        slot.status = SlotStatus.RESERVED
        slot.booking_id = booking.id
        slot.hold_expires_at = None
        slot.version += 1
    session.add(
        JobEvent(
            job_id=correction.id,
            booking_id=booking.id,
            actor_staff_id=context.staff_id,
            event_type="rewash_scheduled",
            metadata_json={
                "original_job_id": str(original_job.id),
                "complaint_id": str(complaint.id),
            },
        )
    )
    await session.flush()
    return correction
