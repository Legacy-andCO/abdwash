import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    BusinessSettings,
    Expense,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryOperation,
    InventoryStock,
    Job,
    ScheduleResource,
    Service,
    ServiceInventoryTemplate,
    StaffProfile,
    TeamMembership,
)
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemList,
    InventoryItemUpdate,
    InventoryItemView,
    InventoryLocationCreate,
    InventoryLocationSummary,
    InventoryLocationUpdate,
    InventoryLocationView,
    InventoryMovementList,
    InventoryMovementView,
    InventoryOperationView,
    InventoryOverview,
    InventoryQuantityLine,
    InventoryQuantityReportRow,
    InventoryReceiptCreate,
    InventoryStockCountCreate,
    InventoryThresholdUpdate,
    InventoryTransferCreate,
    InventoryUsageCreate,
    InventoryUsageReport,
    InventoryWastageCreate,
    ServiceConsumptionTemplateLine,
    ServiceConsumptionTemplateUpdate,
    StockLine,
    StockList,
    TeamStockSummary,
)

ZERO = Decimal("0.000")
QUANT = Decimal("0.001")
MANAGEMENT_ROLES = {StaffRole.MANAGER, StaffRole.ADMIN}
OUTBOUND_TYPES = {"transfer_out", "usage", "wastage", "adjustment_out"}


def _decimal(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(QUANT)


def stock_status(quantity: Decimal, threshold: Decimal) -> str:
    if quantity <= 0:
        return "out"
    if quantity <= threshold:
        return "low"
    return "normal"


def _request_hash(payload: Any) -> str:
    raw = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _audit(
    session: AsyncSession,
    context: StaffContext,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json={},
        )
    )


def _manager(context: StaffContext) -> None:
    if context.role not in MANAGEMENT_ROLES:
        raise DomainError("INSUFFICIENT_ROLE", "Manager access is required.", status_code=403)


def _item_view(row: Any) -> InventoryItemView:
    item, total_quantity, movement_count = row
    return InventoryItemView(
        id=item.id,
        name=item.name,
        category=item.category,
        code=item.code,
        unit=item.unit,
        is_active=item.is_active,
        default_low_stock_threshold=_decimal(item.default_low_stock_threshold),
        notes=item.notes,
        total_quantity=_decimal(total_quantity),
        has_movements=bool(movement_count),
    )


def _item_statement() -> Any:
    stock_totals = (
        select(
            InventoryStock.inventory_item_id.label("item_id"),
            func.sum(InventoryStock.quantity).label("total_quantity"),
        )
        .group_by(InventoryStock.inventory_item_id)
        .subquery()
    )
    movement_counts = (
        select(
            InventoryMovement.inventory_item_id.label("item_id"),
            func.count(InventoryMovement.id).label("movement_count"),
        )
        .group_by(InventoryMovement.inventory_item_id)
        .subquery()
    )
    return (
        select(
            InventoryItem,
            func.coalesce(stock_totals.c.total_quantity, 0),
            func.coalesce(movement_counts.c.movement_count, 0),
        )
        .select_from(InventoryItem)
        .outerjoin(stock_totals, stock_totals.c.item_id == InventoryItem.id)
        .outerjoin(movement_counts, movement_counts.c.item_id == InventoryItem.id)
    )


async def create_item(
    session: AsyncSession, context: StaffContext, request: InventoryItemCreate
) -> InventoryItemView:
    _manager(context)
    if request.code:
        duplicate = await session.scalar(
            select(InventoryItem.id).where(
                InventoryItem.business_id == context.business_id,
                func.lower(InventoryItem.code) == request.code.strip().lower(),
            )
        )
        if duplicate:
            raise ConflictError("INVENTORY_CODE_EXISTS", "An item already uses this code.")
    item = InventoryItem(
        business_id=context.business_id,
        name=request.name.strip(),
        category=request.category,
        code=request.code.strip() if request.code else None,
        unit=request.unit,
        default_low_stock_threshold=_decimal(request.default_low_stock_threshold),
        notes=request.notes,
    )
    session.add(item)
    await session.flush()
    _audit(session, context, "inventory_item_created", "inventory_item", item.id)
    return InventoryItemView(
        id=item.id,
        name=item.name,
        category=item.category,
        code=item.code,
        unit=item.unit,
        is_active=True,
        default_low_stock_threshold=_decimal(item.default_low_stock_threshold),
        notes=item.notes,
    )


async def get_item(
    session: AsyncSession, context: StaffContext, item_id: uuid.UUID
) -> InventoryItemView:
    row = (
        await session.execute(
            _item_statement().where(
                InventoryItem.id == item_id,
                InventoryItem.business_id == context.business_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise DomainError("INVENTORY_ITEM_NOT_FOUND", "Inventory item not found.", status_code=404)
    return _item_view(row)


async def list_items(
    session: AsyncSession,
    context: StaffContext,
    *,
    search: str | None = None,
    category: str | None = None,
    active: bool | None = True,
    offset: int = 0,
    limit: int = 50,
) -> InventoryItemList:
    if context.role not in MANAGEMENT_ROLES and active is None:
        active = True
    statement = (
        _item_statement()
        .where(InventoryItem.business_id == context.business_id)
        .order_by(InventoryItem.name, InventoryItem.id)
    )
    if active is not None:
        statement = statement.where(InventoryItem.is_active.is_(active))
    if category:
        statement = statement.where(InventoryItem.category == category)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                InventoryItem.name.ilike(pattern),
                InventoryItem.code.ilike(pattern),
                InventoryItem.category.ilike(pattern),
            )
        )
    rows = (await session.execute(statement.offset(offset).limit(limit + 1))).all()
    return InventoryItemList(
        items=[_item_view(row) for row in rows[:limit]],
        next_offset=offset + limit if len(rows) > limit else None,
    )


async def update_item(
    session: AsyncSession,
    context: StaffContext,
    item_id: uuid.UUID,
    request: InventoryItemUpdate,
) -> InventoryItemView:
    _manager(context)
    item = await session.scalar(
        select(InventoryItem).where(
            InventoryItem.id == item_id, InventoryItem.business_id == context.business_id
        )
    )
    if item is None:
        raise DomainError("INVENTORY_ITEM_NOT_FOUND", "Inventory item not found.", status_code=404)
    changes = request.model_dump(exclude_unset=True)
    if changes.get("code"):
        duplicate = await session.scalar(
            select(InventoryItem.id).where(
                InventoryItem.business_id == context.business_id,
                InventoryItem.id != item.id,
                func.lower(InventoryItem.code) == changes["code"].strip().lower(),
            )
        )
        if duplicate:
            raise ConflictError("INVENTORY_CODE_EXISTS", "An item already uses this code.")
    if changes.get("unit") and changes["unit"] != item.unit:
        has_movement = await session.scalar(
            select(InventoryMovement.id)
            .where(InventoryMovement.inventory_item_id == item.id)
            .limit(1)
        )
        if has_movement:
            raise ConflictError(
                "INVENTORY_UNIT_IMMUTABLE",
                "The unit cannot change after stock movement has been recorded.",
            )
    for key, value in changes.items():
        if key in {"name", "code"} and isinstance(value, str):
            value = value.strip() or None
        if key == "default_low_stock_threshold" and value is not None:
            value = _decimal(value)
        setattr(item, key, value)
    await session.flush()
    _audit(session, context, "inventory_item_updated", "inventory_item", item.id)
    return await get_item(session, context, item.id)


async def _validate_team(
    session: AsyncSession, context: StaffContext, team_id: uuid.UUID | None
) -> str | None:
    if team_id is None:
        return None
    team_name = await session.scalar(
        select(ScheduleResource.name).where(
            ScheduleResource.id == team_id,
            ScheduleResource.business_id == context.business_id,
            ScheduleResource.resource_type == "mobile_team",
        )
    )
    if team_name is None:
        raise DomainError("TEAM_NOT_FOUND", "Team not found.", status_code=404)
    return team_name


async def create_location(
    session: AsyncSession, context: StaffContext, request: InventoryLocationCreate
) -> InventoryLocationView:
    _manager(context)
    if request.linked_team_id and request.location_type not in {"mobile_team", "van"}:
        raise DomainError(
            "INVALID_TEAM_STOCK_LOCATION",
            "Only mobile-team or van locations may be linked to a team.",
        )
    duplicate = await session.scalar(
        select(InventoryLocation.id).where(
            InventoryLocation.business_id == context.business_id,
            func.lower(InventoryLocation.name) == request.name.strip().lower(),
        )
    )
    if duplicate:
        raise ConflictError("INVENTORY_LOCATION_EXISTS", "A location already uses this name.")
    team_name = await _validate_team(session, context, request.linked_team_id)
    location = InventoryLocation(
        business_id=context.business_id,
        name=request.name.strip(),
        location_type=request.location_type,
        linked_team_id=request.linked_team_id,
    )
    session.add(location)
    await session.flush()
    _audit(session, context, "inventory_location_created", "inventory_location", location.id)
    return InventoryLocationView(
        id=location.id,
        name=location.name,
        location_type=location.location_type,
        linked_team_id=location.linked_team_id,
        linked_team_name=team_name,
        is_active=True,
    )


async def list_locations(
    session: AsyncSession, context: StaffContext, *, active: bool | None = True
) -> list[InventoryLocationView]:
    low_case = case(
        (
            and_(
                InventoryStock.quantity > 0,
                InventoryStock.quantity
                <= func.coalesce(
                    InventoryStock.low_stock_threshold,
                    InventoryItem.default_low_stock_threshold,
                ),
            ),
            1,
        ),
        else_=0,
    )
    out_case = case((InventoryStock.quantity <= 0, 1), else_=0)
    statement = (
        select(
            InventoryLocation,
            ScheduleResource.name,
            func.coalesce(func.sum(low_case), 0),
            func.coalesce(func.sum(out_case), 0),
        )
        .select_from(InventoryLocation)
        .outerjoin(ScheduleResource, ScheduleResource.id == InventoryLocation.linked_team_id)
        .outerjoin(InventoryStock, InventoryStock.location_id == InventoryLocation.id)
        .outerjoin(InventoryItem, InventoryItem.id == InventoryStock.inventory_item_id)
        .where(InventoryLocation.business_id == context.business_id)
        .group_by(InventoryLocation.id, ScheduleResource.name)
        .order_by(InventoryLocation.name)
    )
    if active is not None:
        statement = statement.where(InventoryLocation.is_active.is_(active))
    if context.role not in MANAGEMENT_ROLES:
        statement = statement.where(
            InventoryLocation.linked_team_id.in_(
                select(TeamMembership.resource_id).where(
                    TeamMembership.staff_profile_id == context.staff_id,
                    TeamMembership.is_active.is_(True),
                )
            )
        )
    rows = (await session.execute(statement)).all()
    return [
        InventoryLocationView(
            id=location.id,
            name=location.name,
            location_type=location.location_type,
            linked_team_id=location.linked_team_id,
            linked_team_name=team_name,
            is_active=location.is_active,
            low_stock_count=int(low_count),
            out_of_stock_count=int(out_count),
        )
        for location, team_name, low_count, out_count in rows
    ]


async def update_location(
    session: AsyncSession,
    context: StaffContext,
    location_id: uuid.UUID,
    request: InventoryLocationUpdate,
) -> InventoryLocationView:
    _manager(context)
    location = await session.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == location_id,
            InventoryLocation.business_id == context.business_id,
        )
    )
    if location is None:
        raise DomainError("INVENTORY_LOCATION_NOT_FOUND", "Location not found.", status_code=404)
    changes = request.model_dump(exclude_unset=True)
    next_type = changes.get("location_type", location.location_type)
    next_team = changes.get("linked_team_id", location.linked_team_id)
    if next_team and next_type not in {"mobile_team", "van"}:
        raise DomainError(
            "INVALID_TEAM_STOCK_LOCATION",
            "Only mobile-team or van locations may be linked to a team.",
        )
    if changes.get("name"):
        duplicate = await session.scalar(
            select(InventoryLocation.id).where(
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.id != location.id,
                func.lower(InventoryLocation.name) == changes["name"].strip().lower(),
            )
        )
        if duplicate:
            raise ConflictError("INVENTORY_LOCATION_EXISTS", "A location already uses this name.")
    if "linked_team_id" in changes:
        await _validate_team(session, context, changes["linked_team_id"])
    for key, value in changes.items():
        if key == "name" and value:
            value = value.strip()
        setattr(location, key, value)
    await session.flush()
    _audit(session, context, "inventory_location_updated", "inventory_location", location.id)
    rows = await list_locations(session, context, active=None)
    return next(row for row in rows if row.id == location.id)


def _stock_projection() -> Any:
    threshold = func.coalesce(
        InventoryStock.low_stock_threshold, InventoryItem.default_low_stock_threshold
    )
    return (
        select(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.code,
            InventoryItem.category,
            InventoryItem.unit,
            InventoryLocation.id,
            InventoryLocation.name,
            InventoryStock.quantity,
            threshold,
        )
        .select_from(InventoryStock)
        .join(InventoryItem, InventoryItem.id == InventoryStock.inventory_item_id)
        .join(InventoryLocation, InventoryLocation.id == InventoryStock.location_id)
    )


def _stock_line(row: Any) -> StockLine:
    item_id, name, code, category, unit, location_id, location_name, quantity, threshold = row
    normalized_quantity = _decimal(quantity)
    normalized_threshold = _decimal(threshold)
    return StockLine(
        item_id=item_id,
        item_name=name,
        code=code,
        category=category,
        unit=unit,
        location_id=location_id,
        location_name=location_name,
        quantity=normalized_quantity,
        threshold=normalized_threshold,
        status=stock_status(normalized_quantity, normalized_threshold),
    )


async def _employee_location_ids(session: AsyncSession, context: StaffContext) -> set[uuid.UUID]:
    return set(
        (
            await session.scalars(
                select(InventoryLocation.id)
                .join(
                    TeamMembership,
                    TeamMembership.resource_id == InventoryLocation.linked_team_id,
                )
                .where(
                    InventoryLocation.business_id == context.business_id,
                    InventoryLocation.is_active.is_(True),
                    TeamMembership.staff_profile_id == context.staff_id,
                    TeamMembership.is_active.is_(True),
                )
            )
        ).all()
    )


async def list_stock(
    session: AsyncSession,
    context: StaffContext,
    *,
    location_id: uuid.UUID | None = None,
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> StockList:
    statement = _stock_projection().where(
        InventoryStock.business_id == context.business_id,
        InventoryItem.is_active.is_(True),
        InventoryLocation.is_active.is_(True),
    )
    if context.role not in MANAGEMENT_ROLES:
        allowed = await _employee_location_ids(session, context)
        statement = statement.where(InventoryStock.location_id.in_(allowed or {uuid.UUID(int=0)}))
    if location_id:
        statement = statement.where(InventoryStock.location_id == location_id)
    if category:
        statement = statement.where(InventoryItem.category == category)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                InventoryItem.name.ilike(pattern),
                InventoryItem.code.ilike(pattern),
                InventoryItem.category.ilike(pattern),
            )
        )
    threshold = func.coalesce(
        InventoryStock.low_stock_threshold, InventoryItem.default_low_stock_threshold
    )
    if status == "out":
        statement = statement.where(InventoryStock.quantity <= 0)
    elif status == "low":
        statement = statement.where(
            InventoryStock.quantity > 0, InventoryStock.quantity <= threshold
        )
    elif status == "normal":
        statement = statement.where(InventoryStock.quantity > threshold)
    rows = (
        await session.execute(
            statement.order_by(InventoryItem.name, InventoryLocation.name)
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()
    return StockList(
        items=[_stock_line(row) for row in rows[:limit]],
        next_offset=offset + limit if len(rows) > limit else None,
    )


async def inventory_overview(session: AsyncSession, context: StaffContext) -> InventoryOverview:
    _manager(context)
    active_item_count = int(
        await session.scalar(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.business_id == context.business_id,
                InventoryItem.is_active.is_(True),
            )
        )
        or 0
    )
    threshold = func.coalesce(
        InventoryStock.low_stock_threshold, InventoryItem.default_low_stock_threshold
    )
    low_case = case(
        (and_(InventoryStock.quantity > 0, InventoryStock.quantity <= threshold), 1), else_=0
    )
    out_case = case((InventoryStock.quantity <= 0, 1), else_=0)
    rows = (
        await session.execute(
            select(
                InventoryLocation.id,
                InventoryLocation.name,
                InventoryLocation.location_type,
                func.coalesce(func.sum(low_case), 0),
                func.coalesce(func.sum(out_case), 0),
            )
            .select_from(InventoryLocation)
            .outerjoin(InventoryStock, InventoryStock.location_id == InventoryLocation.id)
            .outerjoin(InventoryItem, InventoryItem.id == InventoryStock.inventory_item_id)
            .where(
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.is_active.is_(True),
            )
            .group_by(InventoryLocation.id)
            .order_by(InventoryLocation.name)
        )
    ).all()
    locations = [
        InventoryLocationSummary(
            location_id=row[0],
            location_name=row[1],
            location_type=row[2],
            low_stock_count=int(row[3]),
            out_of_stock_count=int(row[4]),
        )
        for row in rows
    ]
    return InventoryOverview(
        active_item_count=active_item_count,
        low_stock_count=sum(row.low_stock_count for row in locations),
        out_of_stock_count=sum(row.out_of_stock_count for row in locations),
        locations=locations,
    )


def _combine(lines: Iterable[InventoryQuantityLine]) -> list[tuple[uuid.UUID, Decimal]]:
    totals: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for line in lines:
        totals[line.item_id] += _decimal(line.quantity)
    return sorted(totals.items(), key=lambda pair: pair[0].hex)


async def _items(
    session: AsyncSession, context: StaffContext, item_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, InventoryItem]:
    rows = (
        await session.scalars(
            select(InventoryItem).where(
                InventoryItem.business_id == context.business_id,
                InventoryItem.id.in_(item_ids),
                InventoryItem.is_active.is_(True),
            )
        )
    ).all()
    result = {item.id: item for item in rows}
    if len(result) != len(set(item_ids)):
        raise DomainError(
            "INVENTORY_ITEM_NOT_FOUND",
            "One or more inventory items are unavailable.",
            status_code=404,
        )
    return result


async def _locations(
    session: AsyncSession, context: StaffContext, location_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, InventoryLocation]:
    rows = (
        await session.scalars(
            select(InventoryLocation).where(
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.id.in_(location_ids),
                InventoryLocation.is_active.is_(True),
            )
        )
    ).all()
    result = {location.id: location for location in rows}
    if len(result) != len(set(location_ids)):
        raise DomainError(
            "INVENTORY_LOCATION_NOT_FOUND",
            "One or more locations are unavailable.",
            status_code=404,
        )
    return result


async def _lock_stock(
    session: AsyncSession,
    context: StaffContext,
    keys: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> dict[tuple[uuid.UUID, uuid.UUID], InventoryStock]:
    ordered = sorted(set(keys), key=lambda key: (key[0].hex, key[1].hex))
    if not ordered:
        return {}
    await session.execute(
        insert(InventoryStock)
        .values(
            [
                {
                    "business_id": context.business_id,
                    "inventory_item_id": item_id,
                    "location_id": location_id,
                    "quantity": ZERO,
                }
                for item_id, location_id in ordered
            ]
        )
        .on_conflict_do_nothing(index_elements=["inventory_item_id", "location_id"])
    )
    rows = (
        await session.scalars(
            select(InventoryStock)
            .where(
                InventoryStock.business_id == context.business_id,
                or_(
                    *[
                        and_(
                            InventoryStock.inventory_item_id == item_id,
                            InventoryStock.location_id == location_id,
                        )
                        for item_id, location_id in ordered
                    ]
                ),
            )
            .order_by(InventoryStock.inventory_item_id, InventoryStock.location_id)
            .with_for_update()
        )
    ).all()
    result = {(row.inventory_item_id, row.location_id): row for row in rows}
    if len(result) != len(ordered):
        raise DomainError("INVENTORY_LOCK_FAILED", "Stock could not be locked.", status_code=409)
    return result


async def _operation(
    session: AsyncSession,
    context: StaffContext,
    operation_type: str,
    client_event_id: str,
    request_hash: str,
) -> tuple[InventoryOperation, bool]:
    created_id = await session.scalar(
        insert(InventoryOperation)
        .values(
            business_id=context.business_id,
            operation_type=operation_type,
            client_event_id=client_event_id,
            request_hash=request_hash,
            actor_staff_id=context.staff_id,
        )
        .on_conflict_do_nothing(
            index_elements=[InventoryOperation.business_id, InventoryOperation.client_event_id]
        )
        .returning(InventoryOperation.id)
    )
    operation = await session.scalar(
        select(InventoryOperation).where(
            InventoryOperation.id == created_id
            if created_id is not None
            else and_(
                InventoryOperation.business_id == context.business_id,
                InventoryOperation.client_event_id == client_event_id,
            )
        )
    )
    if operation is None:
        raise DomainError(
            "INVENTORY_OPERATION_UNAVAILABLE",
            "The inventory operation could not be loaded.",
            status_code=409,
        )
    if created_id is None:
        if operation.request_hash != request_hash:
            raise ConflictError(
                "IDEMPOTENCY_KEY_REUSED",
                "This client event ID was already used for a different inventory request.",
            )
        return operation, False
    return operation, True


async def _operation_view(
    session: AsyncSession, operation: InventoryOperation
) -> InventoryOperationView:
    count = int(
        await session.scalar(
            select(func.count(InventoryMovement.id)).where(
                InventoryMovement.operation_id == operation.id
            )
        )
        or 0
    )
    return InventoryOperationView(
        id=operation.id,
        operation_type=operation.operation_type,
        client_event_id=operation.client_event_id,
        expense_id=operation.expense_id,
        movement_count=count,
        created_at=operation.created_at,
    )


async def receive_stock(
    session: AsyncSession, context: StaffContext, request: InventoryReceiptCreate
) -> tuple[InventoryOperationView, bool, bool]:
    _manager(context)
    digest = _request_hash(request)
    operation, created = await _operation(
        session,
        context,
        "opening_balance" if request.opening_balance else "receipt",
        request.client_event_id,
        digest,
    )
    if not created:
        return await _operation_view(session, operation), False, False
    combined = _combine(request.lines)
    await _items(session, context, [item_id for item_id, _ in combined])
    await _locations(session, context, [request.location_id])
    stocks = await _lock_stock(
        session, context, [(item_id, request.location_id) for item_id, _ in combined]
    )
    expense: Expense | None = None
    if request.record_as_expense:
        currency = await session.scalar(
            select(BusinessSettings.currency_code).where(
                BusinessSettings.business_id == context.business_id
            )
        )
        expense = Expense(
            business_id=context.business_id,
            expense_date=datetime.now(ZoneInfo(context.timezone)).date(),
            category="chemicals_supplies",
            description=f"Inventory receipt: {request.reference_number or 'stock received'}",
            amount_minor=request.expense_amount_minor,
            currency_code=currency or "AED",
            payment_method=(request.expense_payment_method or "other").strip().lower(),
            supplier_name=request.supplier_name,
            reference_number=request.reference_number,
            notes=request.notes,
            status="active",
            client_event_id=f"inventory:{request.client_event_id}",
            created_by_staff_id=context.staff_id,
        )
        session.add(expense)
        await session.flush()
        operation.expense_id = expense.id
    per_item_cost = {line.item_id: line.unit_cost_minor for line in request.lines}
    movements: list[InventoryMovement] = []
    for sequence, (item_id, quantity) in enumerate(combined):
        stocks[(item_id, request.location_id)].quantity += quantity
        movements.append(
            InventoryMovement(
                business_id=context.business_id,
                operation_id=operation.id,
                sequence=sequence,
                inventory_item_id=item_id,
                location_id=request.location_id,
                movement_type="opening_balance" if request.opening_balance else "receipt",
                quantity=quantity,
                to_location_id=request.location_id,
                expense_id=expense.id if expense else None,
                actor_staff_id=context.staff_id,
                reason=request.notes,
                reference_number=request.reference_number,
                unit_cost_minor=per_item_cost.get(item_id),
            )
        )
    session.add_all(movements)
    await session.flush()
    _audit(session, context, "inventory_stock_received", "inventory_operation", operation.id)
    return await _operation_view(session, operation), True, expense is not None


async def transfer_stock(
    session: AsyncSession, context: StaffContext, request: InventoryTransferCreate
) -> tuple[InventoryOperationView, bool]:
    _manager(context)
    operation, created = await _operation(
        session, context, "transfer", request.client_event_id, _request_hash(request)
    )
    if not created:
        return await _operation_view(session, operation), False
    combined = _combine(request.lines)
    items = await _items(session, context, [item_id for item_id, _ in combined])
    await _locations(session, context, [request.from_location_id, request.to_location_id])
    keys = [
        key
        for item_id, _ in combined
        for key in (
            (item_id, request.from_location_id),
            (item_id, request.to_location_id),
        )
    ]
    stocks = await _lock_stock(session, context, keys)
    for item_id, quantity in combined:
        available = _decimal(stocks[(item_id, request.from_location_id)].quantity)
        if available < quantity:
            raise ConflictError(
                "INSUFFICIENT_STOCK",
                f"{items[item_id].name} has only {available} {items[item_id].unit} available.",
                {"item_id": str(item_id), "available": str(available)},
            )
    movements: list[InventoryMovement] = []
    sequence = 0
    for item_id, quantity in combined:
        stocks[(item_id, request.from_location_id)].quantity -= quantity
        stocks[(item_id, request.to_location_id)].quantity += quantity
        for movement_type, location_id in (
            ("transfer_out", request.from_location_id),
            ("transfer_in", request.to_location_id),
        ):
            movements.append(
                InventoryMovement(
                    business_id=context.business_id,
                    operation_id=operation.id,
                    sequence=sequence,
                    inventory_item_id=item_id,
                    location_id=location_id,
                    movement_type=movement_type,
                    quantity=quantity,
                    from_location_id=request.from_location_id,
                    to_location_id=request.to_location_id,
                    actor_staff_id=context.staff_id,
                    reason=request.notes,
                )
            )
            sequence += 1
    session.add_all(movements)
    await session.flush()
    _audit(session, context, "inventory_stock_transferred", "inventory_operation", operation.id)
    return await _operation_view(session, operation), True


async def _authorize_usage(
    session: AsyncSession,
    context: StaffContext,
    location_id: uuid.UUID,
    job_id: uuid.UUID | None,
) -> None:
    job: Job | None = None
    if job_id is not None:
        job = await session.scalar(
            select(Job).where(
                Job.id == job_id,
                Job.business_id == context.business_id,
            )
        )
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "Job not found.", status_code=404)
    if context.role in MANAGEMENT_ROLES:
        return
    allowed = await _employee_location_ids(session, context)
    if location_id not in allowed:
        raise DomainError(
            "INVENTORY_LOCATION_FORBIDDEN", "This team stock is not available.", status_code=403
        )
    if job_id is None:
        raise DomainError(
            "JOB_REQUIRED", "Employees may only record stock against a job.", status_code=403
        )
    assert job is not None
    team_ids = await session.scalars(
        select(TeamMembership.resource_id).where(
            TeamMembership.staff_profile_id == context.staff_id,
            TeamMembership.is_active.is_(True),
        )
    )
    if job.assigned_staff_id != context.staff_id and job.assigned_resource_id not in set(
        team_ids.all()
    ):
        raise DomainError("JOB_NOT_FOUND", "Assigned job not found.", status_code=404)


async def _consume(
    session: AsyncSession,
    context: StaffContext,
    *,
    operation_type: str,
    movement_type: str,
    location_id: uuid.UUID,
    lines: Sequence[InventoryQuantityLine],
    reason: str | None,
    client_event_id: str,
    request_hash: str,
    job_id: uuid.UUID | None = None,
) -> tuple[InventoryOperationView, bool]:
    operation, created = await _operation(
        session, context, operation_type, client_event_id, request_hash
    )
    if not created:
        return await _operation_view(session, operation), False
    combined = _combine(lines)
    items = await _items(session, context, [item_id for item_id, _ in combined])
    await _locations(session, context, [location_id])
    stocks = await _lock_stock(
        session, context, [(item_id, location_id) for item_id, _ in combined]
    )
    for item_id, quantity in combined:
        available = _decimal(stocks[(item_id, location_id)].quantity)
        if available < quantity:
            raise ConflictError(
                "INSUFFICIENT_STOCK",
                f"{items[item_id].name} has only {available} {items[item_id].unit} available.",
                {"item_id": str(item_id), "available": str(available)},
            )
    for sequence, (item_id, quantity) in enumerate(combined):
        stocks[(item_id, location_id)].quantity -= quantity
        session.add(
            InventoryMovement(
                business_id=context.business_id,
                operation_id=operation.id,
                sequence=sequence,
                inventory_item_id=item_id,
                location_id=location_id,
                movement_type=movement_type,
                quantity=quantity,
                from_location_id=location_id,
                job_id=job_id,
                actor_staff_id=context.staff_id,
                reason=reason,
            )
        )
    await session.flush()
    _audit(
        session,
        context,
        f"inventory_{operation_type}_recorded",
        "inventory_operation",
        operation.id,
    )
    return await _operation_view(session, operation), True


async def record_usage(
    session: AsyncSession, context: StaffContext, request: InventoryUsageCreate
) -> tuple[InventoryOperationView, bool]:
    await _authorize_usage(session, context, request.location_id, request.job_id)
    return await _consume(
        session,
        context,
        operation_type="usage",
        movement_type="usage",
        location_id=request.location_id,
        lines=request.lines,
        reason=request.notes,
        client_event_id=request.client_event_id,
        request_hash=_request_hash(request),
        job_id=request.job_id,
    )


async def record_wastage(
    session: AsyncSession, context: StaffContext, request: InventoryWastageCreate
) -> tuple[InventoryOperationView, bool]:
    _manager(context)
    return await _consume(
        session,
        context,
        operation_type="wastage",
        movement_type="wastage",
        location_id=request.location_id,
        lines=request.lines,
        reason=request.reason,
        client_event_id=request.client_event_id,
        request_hash=_request_hash(request),
    )


async def record_stock_count(
    session: AsyncSession, context: StaffContext, request: InventoryStockCountCreate
) -> tuple[InventoryOperationView, bool]:
    _manager(context)
    operation, created = await _operation(
        session, context, "stock_count", request.client_event_id, _request_hash(request)
    )
    if not created:
        return await _operation_view(session, operation), False
    counted: dict[uuid.UUID, Decimal] = {}
    for line in request.lines:
        if line.item_id in counted:
            raise DomainError("DUPLICATE_STOCK_COUNT_ITEM", "Each item may be counted once.")
        counted[line.item_id] = _decimal(line.counted_quantity)
    await _items(session, context, list(counted))
    await _locations(session, context, [request.location_id])
    stocks = await _lock_stock(
        session,
        context,
        [(item_id, request.location_id) for item_id in sorted(counted, key=lambda x: x.hex)],
    )
    sequence = 0
    for item_id in sorted(counted, key=lambda value: value.hex):
        stock = stocks[(item_id, request.location_id)]
        current = _decimal(stock.quantity)
        difference = counted[item_id] - current
        if difference == 0:
            continue
        stock.quantity = counted[item_id]
        session.add(
            InventoryMovement(
                business_id=context.business_id,
                operation_id=operation.id,
                sequence=sequence,
                inventory_item_id=item_id,
                location_id=request.location_id,
                movement_type="adjustment_in" if difference > 0 else "adjustment_out",
                quantity=abs(difference),
                from_location_id=request.location_id if difference < 0 else None,
                to_location_id=request.location_id if difference > 0 else None,
                actor_staff_id=context.staff_id,
                reason=request.reason,
            )
        )
        sequence += 1
    await session.flush()
    _audit(session, context, "inventory_stock_counted", "inventory_operation", operation.id)
    return await _operation_view(session, operation), True


async def update_threshold(
    session: AsyncSession,
    context: StaffContext,
    location_id: uuid.UUID,
    item_id: uuid.UUID,
    request: InventoryThresholdUpdate,
) -> StockLine:
    _manager(context)
    await _items(session, context, [item_id])
    await _locations(session, context, [location_id])
    stock = (await _lock_stock(session, context, [(item_id, location_id)]))[(item_id, location_id)]
    stock.low_stock_threshold = (
        _decimal(request.low_stock_threshold) if request.low_stock_threshold is not None else None
    )
    await session.flush()
    _audit(session, context, "inventory_threshold_updated", "inventory_stock", stock.id)
    row = (
        await session.execute(
            _stock_projection().where(
                InventoryStock.inventory_item_id == item_id,
                InventoryStock.location_id == location_id,
                InventoryStock.business_id == context.business_id,
            )
        )
    ).one()
    return _stock_line(row)


async def list_movements(
    session: AsyncSession,
    context: StaffContext,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    item_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    movement_type: str | None = None,
    team_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> InventoryMovementList:
    FromLocation = aliased(InventoryLocation)
    ToLocation = aliased(InventoryLocation)
    statement = (
        select(
            InventoryMovement,
            InventoryItem.name,
            InventoryItem.unit,
            InventoryLocation.name,
            FromLocation.name,
            ToLocation.name,
            Booking.reference,
            StaffProfile.display_name,
        )
        .select_from(InventoryMovement)
        .join(InventoryItem, InventoryItem.id == InventoryMovement.inventory_item_id)
        .join(InventoryLocation, InventoryLocation.id == InventoryMovement.location_id)
        .outerjoin(FromLocation, FromLocation.id == InventoryMovement.from_location_id)
        .outerjoin(ToLocation, ToLocation.id == InventoryMovement.to_location_id)
        .outerjoin(Job, Job.id == InventoryMovement.job_id)
        .outerjoin(Booking, Booking.id == Job.booking_id)
        .join(StaffProfile, StaffProfile.id == InventoryMovement.actor_staff_id)
        .where(InventoryMovement.business_id == context.business_id)
        .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
    )
    if context.role not in MANAGEMENT_ROLES:
        allowed = await _employee_location_ids(session, context)
        statement = statement.where(
            InventoryMovement.location_id.in_(allowed or {uuid.UUID(int=0)})
        )
    if start_at:
        statement = statement.where(InventoryMovement.created_at >= start_at)
    if end_at:
        statement = statement.where(InventoryMovement.created_at < end_at)
    if item_id:
        statement = statement.where(InventoryMovement.inventory_item_id == item_id)
    if location_id:
        statement = statement.where(InventoryMovement.location_id == location_id)
    if movement_type:
        statement = statement.where(InventoryMovement.movement_type == movement_type)
    if team_id:
        statement = statement.where(InventoryLocation.linked_team_id == team_id)
    if job_id:
        statement = statement.where(InventoryMovement.job_id == job_id)
    if actor_id:
        statement = statement.where(InventoryMovement.actor_staff_id == actor_id)
    rows = (await session.execute(statement.offset(offset).limit(limit + 1))).all()
    views: list[InventoryMovementView] = []
    for movement, name, unit, location, from_name, to_name, booking_ref, actor_name in rows[:limit]:
        quantity = _decimal(movement.quantity)
        views.append(
            InventoryMovementView(
                id=movement.id,
                operation_id=movement.operation_id,
                item_id=movement.inventory_item_id,
                item_name=name,
                unit=unit,
                movement_type=movement.movement_type,
                quantity=quantity,
                signed_quantity=-quantity if movement.movement_type in OUTBOUND_TYPES else quantity,
                location_id=movement.location_id,
                location_name=location,
                from_location_id=movement.from_location_id,
                from_location_name=from_name,
                to_location_id=movement.to_location_id,
                to_location_name=to_name,
                job_id=movement.job_id,
                booking_reference=booking_ref,
                expense_id=movement.expense_id,
                actor_staff_id=movement.actor_staff_id,
                actor_name=actor_name,
                reason=movement.reason,
                reference_number=movement.reference_number,
                created_at=movement.created_at,
            )
        )
    return InventoryMovementList(
        items=views, next_offset=offset + limit if len(rows) > limit else None
    )


async def usage_report(
    session: AsyncSession,
    context: StaffContext,
    start_at: datetime,
    end_at: datetime,
) -> InventoryUsageReport:
    _manager(context)
    if end_at <= start_at:
        raise DomainError("INVALID_REPORT_RANGE", "Report end must be after its start.")
    rows = (
        await session.execute(
            select(
                InventoryMovement.movement_type,
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.unit,
                func.sum(InventoryMovement.quantity),
            )
            .select_from(InventoryMovement)
            .join(InventoryItem, InventoryItem.id == InventoryMovement.inventory_item_id)
            .where(
                InventoryMovement.business_id == context.business_id,
                InventoryMovement.created_at >= start_at,
                InventoryMovement.created_at < end_at,
                InventoryMovement.movement_type.in_(("usage", "wastage")),
            )
            .group_by(
                InventoryMovement.movement_type,
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.unit,
            )
            .order_by(InventoryMovement.movement_type, InventoryItem.name)
        )
    ).all()
    grouped: dict[str, list[InventoryQuantityReportRow]] = {"usage": [], "wastage": []}
    for movement_type, item_id, name, unit, quantity in rows:
        grouped[movement_type].append(
            InventoryQuantityReportRow(
                item_id=item_id,
                item_name=name,
                unit=unit,
                quantity=_decimal(quantity),
            )
        )
    return InventoryUsageReport(
        start_at=start_at,
        end_at=end_at,
        usage=grouped["usage"],
        wastage=grouped["wastage"],
    )


async def team_stock_summary(
    session: AsyncSession, context: StaffContext, team_id: uuid.UUID
) -> TeamStockSummary:
    await _validate_team(session, context, team_id)
    if context.role not in MANAGEMENT_ROLES:
        membership = await session.scalar(
            select(TeamMembership.id).where(
                TeamMembership.resource_id == team_id,
                TeamMembership.staff_profile_id == context.staff_id,
                TeamMembership.is_active.is_(True),
            )
        )
        if membership is None:
            raise DomainError(
                "TEAM_STOCK_FORBIDDEN", "Team stock is not available.", status_code=403
            )
    location = (
        await session.execute(
            select(InventoryLocation.id, InventoryLocation.name).where(
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.linked_team_id == team_id,
                InventoryLocation.is_active.is_(True),
            )
        )
    ).one_or_none()
    if location is None:
        return TeamStockSummary(
            team_id=team_id,
            location_id=None,
            location_name=None,
            item_count=0,
            low_stock_count=0,
            out_of_stock_count=0,
            items=[],
        )
    stock = await list_stock(session, context, location_id=location.id, limit=8)
    return TeamStockSummary(
        team_id=team_id,
        location_id=location.id,
        location_name=location.name,
        item_count=len(stock.items),
        low_stock_count=sum(item.status == "low" for item in stock.items),
        out_of_stock_count=sum(item.status == "out" for item in stock.items),
        items=stock.items,
    )


async def get_service_template(
    session: AsyncSession, context: StaffContext, service_id: uuid.UUID
) -> list[ServiceConsumptionTemplateLine]:
    service = await session.scalar(
        select(Service.id).where(
            Service.id == service_id, Service.business_id == context.business_id
        )
    )
    if service is None:
        raise DomainError("SERVICE_NOT_FOUND", "Service not found.", status_code=404)
    rows = (
        await session.execute(
            select(
                ServiceInventoryTemplate.inventory_item_id,
                InventoryItem.name,
                InventoryItem.unit,
                ServiceInventoryTemplate.expected_quantity,
            )
            .join(InventoryItem, InventoryItem.id == ServiceInventoryTemplate.inventory_item_id)
            .where(
                ServiceInventoryTemplate.business_id == context.business_id,
                ServiceInventoryTemplate.service_id == service_id,
                InventoryItem.is_active.is_(True),
            )
            .order_by(InventoryItem.name)
        )
    ).all()
    return [
        ServiceConsumptionTemplateLine(
            item_id=row[0], item_name=row[1], unit=row[2], expected_quantity=_decimal(row[3])
        )
        for row in rows
    ]


async def update_service_template(
    session: AsyncSession,
    context: StaffContext,
    service_id: uuid.UUID,
    request: ServiceConsumptionTemplateUpdate,
) -> list[ServiceConsumptionTemplateLine]:
    _manager(context)
    service = await session.scalar(
        select(Service.id).where(
            Service.id == service_id, Service.business_id == context.business_id
        )
    )
    if service is None:
        raise DomainError("SERVICE_NOT_FOUND", "Service not found.", status_code=404)
    item_ids = [line.item_id for line in request.lines]
    if len(set(item_ids)) != len(item_ids):
        raise DomainError("DUPLICATE_TEMPLATE_ITEM", "Each template item must be unique.")
    await _items(session, context, item_ids)
    await session.execute(
        delete(ServiceInventoryTemplate).where(
            ServiceInventoryTemplate.business_id == context.business_id,
            ServiceInventoryTemplate.service_id == service_id,
        )
    )
    session.add_all(
        [
            ServiceInventoryTemplate(
                business_id=context.business_id,
                service_id=service_id,
                inventory_item_id=line.item_id,
                expected_quantity=_decimal(line.expected_quantity),
            )
            for line in request.lines
        ]
    )
    await session.flush()
    _audit(session, context, "service_inventory_template_updated", "service", service_id)
    return await get_service_template(session, context, service_id)
