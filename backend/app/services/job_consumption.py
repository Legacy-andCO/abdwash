import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    BookingService,
    BusinessSettings,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Job,
    JobInventoryConsumptionLine,
    JobInventoryConsumptionRun,
    ServiceInventoryTemplate,
)
from app.schemas.inventory import (
    InventoryAttentionItem,
    InventoryAttentionList,
    JobConsumptionLineView,
    JobConsumptionSummary,
)
from app.services.inventory import apply_available_job_usage

ZERO = Decimal("0.000")
QUANT = Decimal("0.001")
MANAGEMENT_ROLES = {StaffRole.MANAGER, StaffRole.ADMIN}


def _decimal(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANT)


@dataclass
class ConsumptionProcessResult:
    status: str
    expected_lines: int
    attention_lines: int
    created: bool


@dataclass
class _LineDraft:
    booking_service_id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    item_id: uuid.UUID
    item_name: str
    unit: str
    expected: Decimal
    item_active: bool
    manual: Decimal = ZERO
    automatic: Decimal = ZERO
    shortfall: Decimal = ZERO
    issue_code: str | None = None


async def _source_location(
    session: AsyncSession,
    context: StaffContext,
) -> tuple[InventoryLocation | None, str, str | None]:
    rows = (
        await session.execute(
            select(InventoryLocation, BusinessSettings.default_inventory_location_id)
            .select_from(InventoryLocation)
            .join(BusinessSettings, BusinessSettings.business_id == InventoryLocation.business_id)
            .where(
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.is_active.is_(True),
            )
            .order_by(InventoryLocation.created_at, InventoryLocation.id)
        )
    ).all()
    if not rows:
        return None, "unresolved", "SOURCE_LOCATION_MISSING"
    locations = [row[0] for row in rows]
    configured_id = rows[0][1]
    configured = next((item for item in locations if item.id == configured_id), None)
    if configured is not None:
        return configured, "business_default", None
    if len(locations) == 1:
        return locations[0], "single_location", None
    main_locations = [item for item in locations if item.location_type == "main"]
    if len(main_locations) == 1:
        return main_locations[0], "main_default", None
    return None, "ambiguous", "SOURCE_LOCATION_AMBIGUOUS"


async def process_job_consumption(
    session: AsyncSession,
    context: StaffContext,
    job: Job,
) -> ConsumptionProcessResult:
    existing = await session.scalar(
        select(JobInventoryConsumptionRun).where(
            JobInventoryConsumptionRun.business_id == context.business_id,
            JobInventoryConsumptionRun.job_id == job.id,
        )
    )
    if existing is not None:
        counts = (
            await session.execute(
                select(
                    func.count(JobInventoryConsumptionLine.id),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    (
                                        JobInventoryConsumptionLine.issue_code.is_not(None)
                                        | (JobInventoryConsumptionLine.shortfall_quantity > ZERO)
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(JobInventoryConsumptionLine.run_id == existing.id)
            )
        ).one()
        return ConsumptionProcessResult(existing.status, int(counts[0]), int(counts[1]), False)

    template_rows = (
        await session.execute(
            select(
                BookingService.id,
                BookingService.service_id,
                BookingService.service_name,
                BookingService.quantity,
                ServiceInventoryTemplate.inventory_item_id,
                ServiceInventoryTemplate.expected_quantity,
                InventoryItem.name,
                InventoryItem.unit,
                InventoryItem.is_active,
            )
            .select_from(BookingService)
            .join(
                ServiceInventoryTemplate,
                (ServiceInventoryTemplate.service_id == BookingService.service_id)
                & (ServiceInventoryTemplate.business_id == context.business_id),
            )
            .join(
                InventoryItem,
                (InventoryItem.id == ServiceInventoryTemplate.inventory_item_id)
                & (InventoryItem.business_id == context.business_id),
            )
            .where(
                BookingService.booking_id == job.booking_id,
                ServiceInventoryTemplate.business_id == context.business_id,
            )
            .order_by(BookingService.id, ServiceInventoryTemplate.inventory_item_id)
        )
    ).all()
    if not template_rows:
        run = JobInventoryConsumptionRun(
            business_id=context.business_id,
            job_id=job.id,
            status="no_template",
            source_resolution="not_required",
            has_attention=False,
            processed_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        return ConsumptionProcessResult("no_template", 0, 0, True)

    drafts = [
        _LineDraft(
            booking_service_id=row[0],
            service_id=row[1],
            service_name=row[2],
            item_id=row[4],
            item_name=row[6],
            unit=row[7],
            expected=_decimal(row[5]) * int(row[3]),
            item_active=bool(row[8]),
        )
        for row in template_rows
    ]
    manual_rows = (
        await session.execute(
            select(
                InventoryMovement.inventory_item_id,
                InventoryMovement.location_id,
                func.sum(InventoryMovement.quantity),
            )
            .where(
                InventoryMovement.business_id == context.business_id,
                InventoryMovement.job_id == job.id,
                InventoryMovement.movement_type == "usage",
            )
            .group_by(InventoryMovement.inventory_item_id, InventoryMovement.location_id)
        )
    ).all()
    manual_by_item: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for item_id, _location_id, quantity in manual_rows:
        manual_by_item[item_id] += _decimal(quantity)

    remaining_manual = dict(manual_by_item)
    automatic_needed: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for draft in drafts:
        available_manual = remaining_manual.get(draft.item_id, ZERO)
        draft.manual = min(draft.expected, available_manual)
        remaining_manual[draft.item_id] = max(ZERO, available_manual - draft.manual)
        if not draft.item_active:
            draft.issue_code = "INVENTORY_ITEM_INACTIVE"
            draft.shortfall = draft.expected - draft.manual
            continue
        automatic_needed[draft.item_id] += draft.expected - draft.manual

    automatic_needed = {
        item_id: quantity for item_id, quantity in automatic_needed.items() if quantity > ZERO
    }
    source: InventoryLocation | None = None
    source_resolution = "not_required"
    source_issue: str | None = None
    if automatic_needed:
        source, source_resolution, source_issue = await _source_location(session, context)

    operation_id: uuid.UUID | None = None
    applied_by_item: dict[uuid.UUID, Decimal] = {}
    if source is not None and automatic_needed:
        operation, applied_by_item = await apply_available_job_usage(
            session,
            context,
            location_id=source.id,
            job_id=job.id,
            quantities=automatic_needed,
        )
        operation_id = operation.id

    remaining_applied = dict(applied_by_item)
    for draft in drafts:
        if draft.issue_code is not None:
            continue
        need = draft.expected - draft.manual
        if need <= ZERO:
            continue
        if source_issue is not None:
            draft.issue_code = source_issue
            draft.shortfall = need
            continue
        available_applied = remaining_applied.get(draft.item_id, ZERO)
        draft.automatic = min(need, available_applied)
        remaining_applied[draft.item_id] = max(ZERO, available_applied - draft.automatic)
        draft.shortfall = need - draft.automatic
        if draft.shortfall > ZERO:
            draft.issue_code = "INSUFFICIENT_RECORDED_STOCK"

    has_attention = any(draft.issue_code is not None for draft in drafts)
    run = JobInventoryConsumptionRun(
        business_id=context.business_id,
        job_id=job.id,
        source_location_id=source.id if source else None,
        inventory_operation_id=operation_id,
        status="needs_review" if has_attention else "applied",
        source_resolution=source_resolution,
        issue_code=(source_issue or next((d.issue_code for d in drafts if d.issue_code), None)),
        processed_at=datetime.now(UTC),
        has_attention=has_attention,
    )
    session.add(run)
    await session.flush()
    session.add_all(
        [
            JobInventoryConsumptionLine(
                business_id=context.business_id,
                run_id=run.id,
                booking_service_id=draft.booking_service_id,
                service_id=draft.service_id,
                service_name_snapshot=draft.service_name,
                inventory_item_id=draft.item_id,
                item_name_snapshot=draft.item_name,
                unit_snapshot=draft.unit,
                expected_quantity=draft.expected,
                automatic_applied_quantity=draft.automatic,
                preexisting_manual_quantity=draft.manual,
                shortfall_quantity=draft.shortfall,
                issue_code=draft.issue_code,
            )
            for draft in drafts
        ]
    )
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type="job_inventory_consumption_processed",
            entity_type="job",
            entity_id=job.id,
            metadata_json={
                "status": run.status,
                "expected_lines": len(drafts),
                "attention_lines": sum(d.issue_code is not None for d in drafts),
            },
        )
    )
    await session.flush()
    return ConsumptionProcessResult(
        run.status,
        len(drafts),
        sum(d.issue_code is not None for d in drafts),
        True,
    )


async def consumption_summaries(
    session: AsyncSession,
    context: StaffContext,
    job_ids: list[uuid.UUID],
) -> dict[uuid.UUID, JobConsumptionSummary]:
    if not job_ids:
        return {}
    rows = (
        await session.execute(
            select(
                JobInventoryConsumptionRun,
                JobInventoryConsumptionLine,
                InventoryLocation.name,
            )
            .select_from(JobInventoryConsumptionRun)
            .outerjoin(
                JobInventoryConsumptionLine,
                JobInventoryConsumptionLine.run_id == JobInventoryConsumptionRun.id,
            )
            .outerjoin(
                InventoryLocation,
                InventoryLocation.id == JobInventoryConsumptionRun.source_location_id,
            )
            .where(
                JobInventoryConsumptionRun.business_id == context.business_id,
                JobInventoryConsumptionRun.job_id.in_(job_ids),
            )
            .order_by(
                JobInventoryConsumptionRun.processed_at,
                JobInventoryConsumptionLine.created_at,
            )
        )
    ).all()
    manual_rows = (
        await session.execute(
            select(
                InventoryMovement.job_id,
                InventoryMovement.inventory_item_id,
                func.sum(InventoryMovement.quantity),
            )
            .outerjoin(
                JobInventoryConsumptionRun,
                JobInventoryConsumptionRun.inventory_operation_id == InventoryMovement.operation_id,
            )
            .where(
                InventoryMovement.business_id == context.business_id,
                InventoryMovement.job_id.in_(job_ids),
                InventoryMovement.movement_type == "usage",
                JobInventoryConsumptionRun.id.is_(None),
            )
            .group_by(InventoryMovement.job_id, InventoryMovement.inventory_item_id)
        )
    ).all()
    manual_totals = {(job_id, item_id): _decimal(total) for job_id, item_id, total in manual_rows}
    grouped: dict[uuid.UUID, tuple[JobInventoryConsumptionRun, str | None, list[Any]]] = {}
    for run, line, location_name in rows:
        grouped.setdefault(run.job_id, (run, location_name, []))[2].append(line)

    result: dict[uuid.UUID, JobConsumptionSummary] = {}
    for job_id, (run, location_name, raw_lines) in grouped.items():
        lines = [line for line in raw_lines if line is not None]
        preexisting_by_item: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
        for line in lines:
            if line.inventory_item_id is not None:
                preexisting_by_item[line.inventory_item_id] += _decimal(
                    line.preexisting_manual_quantity
                )
        extra_by_item = {
            item_id: max(
                ZERO,
                manual_totals.get((job_id, item_id), ZERO) - preexisting_quantity,
            )
            for item_id, preexisting_quantity in preexisting_by_item.items()
        }
        consumed_extra: set[uuid.UUID] = set()
        views: list[JobConsumptionLineView] = []
        for line in lines:
            additional = ZERO
            if line.inventory_item_id is not None and line.inventory_item_id not in consumed_extra:
                additional = extra_by_item.get(line.inventory_item_id, ZERO)
                consumed_extra.add(line.inventory_item_id)
            views.append(
                JobConsumptionLineView(
                    id=line.id,
                    booking_service_id=line.booking_service_id,
                    service_id=line.service_id,
                    service_name=line.service_name_snapshot,
                    item_id=line.inventory_item_id,
                    item_name=line.item_name_snapshot,
                    unit=line.unit_snapshot,
                    expected_quantity=_decimal(line.expected_quantity),
                    automatic_applied_quantity=_decimal(line.automatic_applied_quantity),
                    preexisting_manual_quantity=_decimal(line.preexisting_manual_quantity),
                    additional_manual_quantity=additional,
                    shortfall_quantity=_decimal(line.shortfall_quantity),
                    issue_code=line.issue_code,
                )
            )
        result[job_id] = JobConsumptionSummary(
            id=run.id,
            status=run.status,
            source_location_id=run.source_location_id,
            source_location_name=location_name,
            source_resolution=run.source_resolution,
            issue_code=run.issue_code,
            processed_at=run.processed_at,
            expected_lines=len(views),
            attention_lines=sum(line.issue_code is not None for line in lines),
            has_attention=run.has_attention,
            reviewed_at=run.reviewed_at,
            review_note=run.review_note,
            lines=views,
        )
    return result


async def list_attention(
    session: AsyncSession,
    context: StaffContext,
    *,
    offset: int = 0,
    limit: int = 50,
) -> InventoryAttentionList:
    if context.role not in MANAGEMENT_ROLES:
        raise DomainError("INSUFFICIENT_ROLE", "Manager access is required.", status_code=403)
    attention_case = case(
        (
            (JobInventoryConsumptionLine.issue_code.is_not(None))
            | (JobInventoryConsumptionLine.shortfall_quantity > ZERO),
            1,
        ),
        else_=0,
    )
    rows = (
        await session.execute(
            select(
                JobInventoryConsumptionRun,
                Job.id,
                Booking.reference,
                Booking.customer_first_name,
                Booking.customer_surname,
                InventoryLocation.name,
                func.coalesce(func.sum(attention_case), 0),
            )
            .select_from(JobInventoryConsumptionRun)
            .join(Job, Job.id == JobInventoryConsumptionRun.job_id)
            .join(Booking, Booking.id == Job.booking_id)
            .outerjoin(
                JobInventoryConsumptionLine,
                JobInventoryConsumptionLine.run_id == JobInventoryConsumptionRun.id,
            )
            .outerjoin(
                InventoryLocation,
                InventoryLocation.id == JobInventoryConsumptionRun.source_location_id,
            )
            .where(
                JobInventoryConsumptionRun.business_id == context.business_id,
                JobInventoryConsumptionRun.has_attention.is_(True),
                JobInventoryConsumptionRun.reviewed_at.is_(None),
            )
            .group_by(
                JobInventoryConsumptionRun.id,
                Job.id,
                Booking.reference,
                Booking.customer_first_name,
                Booking.customer_surname,
                InventoryLocation.name,
            )
            .order_by(JobInventoryConsumptionRun.processed_at.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()
    return InventoryAttentionList(
        items=[
            InventoryAttentionItem(
                id=run.id,
                job_id=job_id,
                booking_reference=reference,
                customer_name=f"{first_name} {surname}",
                source_location_name=location_name,
                issue_code=run.issue_code,
                processed_at=run.processed_at,
                attention_lines=int(attention_lines),
            )
            for (
                run,
                job_id,
                reference,
                first_name,
                surname,
                location_name,
                attention_lines,
            ) in rows[:limit]
        ],
        next_offset=offset + limit if len(rows) > limit else None,
    )


async def review_consumption(
    session: AsyncSession,
    context: StaffContext,
    run_id: uuid.UUID,
    note: str | None,
) -> JobConsumptionSummary:
    if context.role not in MANAGEMENT_ROLES:
        raise DomainError("INSUFFICIENT_ROLE", "Manager access is required.", status_code=403)
    run = await session.scalar(
        select(JobInventoryConsumptionRun)
        .where(
            JobInventoryConsumptionRun.id == run_id,
            JobInventoryConsumptionRun.business_id == context.business_id,
        )
        .with_for_update()
    )
    if run is None:
        raise DomainError(
            "INVENTORY_CONSUMPTION_NOT_FOUND",
            "Inventory consumption review was not found.",
            status_code=404,
        )
    if run.reviewed_at is None:
        run.reviewed_at = datetime.now(UTC)
        run.reviewed_by_staff_id = context.staff_id
        run.review_note = note.strip() if note and note.strip() else None
        session.add(
            AuditEvent(
                business_id=context.business_id,
                actor_auth_user_id=context.auth_user_id,
                event_type="job_inventory_consumption_reviewed",
                entity_type="job_inventory_consumption",
                entity_id=run.id,
                metadata_json={},
            )
        )
        await session.flush()
    return (await consumption_summaries(session, context, [run.job_id]))[run.job_id]
