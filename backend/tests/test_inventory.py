import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

import app.services.inventory as inventory
from app.api.staff import router as staff_router
from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Expense,
    InventoryItem,
    InventoryMovement,
    InventoryOperation,
    InventoryStock,
    ServiceInventoryTemplate,
)
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryQuantityLine,
    InventoryReceiptCreate,
    InventoryStockCountCreate,
    InventoryTransferCreate,
    InventoryWastageCreate,
)


def context(role: StaffRole = StaffRole.MANAGER) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=role,
        timezone="Asia/Dubai",
    )


def operation(kind: str = "transfer") -> InventoryOperation:
    return InventoryOperation(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        operation_type=kind,
        client_event_id="inventory-event-123",
        request_hash="a" * 64,
        actor_staff_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
    )


def item(item_id: uuid.UUID, name: str = "Interior Cleaner") -> InventoryItem:
    return InventoryItem(
        id=item_id,
        business_id=uuid.uuid4(),
        name=name,
        category="chemicals",
        unit="liter",
        default_low_stock_threshold=Decimal("3.000"),
    )


def stock(item_id: uuid.UUID, location_id: uuid.UUID, quantity: str) -> InventoryStock:
    return InventoryStock(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        inventory_item_id=item_id,
        location_id=location_id,
        quantity=Decimal(quantity),
    )


def test_catalogue_schema_uses_controlled_categories_units_and_decimal_quantity() -> None:
    value = InventoryItemCreate(
        name="Interior Cleaner",
        category="chemicals",
        unit="liter",
        default_low_stock_threshold="3.125",
    )
    assert value.default_low_stock_threshold == Decimal("3.125")
    with pytest.raises(ValidationError):
        InventoryItemCreate(name="Polisher", category="fixed_asset", unit="machine")


def test_inventory_models_keep_balance_ledger_and_idempotency_invariants() -> None:
    stock_constraints = {constraint.name for constraint in InventoryStock.__table__.constraints}
    operation_constraints = {
        constraint.name for constraint in InventoryOperation.__table__.constraints
    }
    movement_constraints = {
        constraint.name for constraint in InventoryMovement.__table__.constraints
    }
    assert any(
        name and name.endswith("inventory_stock_nonnegative_quantity") for name in stock_constraints
    )
    assert "uq_inventory_stock_item_location" in stock_constraints
    assert "uq_inventory_operation_business_event" in operation_constraints
    assert "uq_inventory_movement_sequence" in movement_constraints
    assert InventoryStock.__table__.c.quantity.type.scale == 3
    assert ServiceInventoryTemplate.__table__.c.expected_quantity.type.scale == 3


def test_stock_status_includes_threshold_boundary_and_zero() -> None:
    assert inventory.stock_status(Decimal("4"), Decimal("3")) == "normal"
    assert inventory.stock_status(Decimal("3"), Decimal("3")) == "low"
    assert inventory.stock_status(Decimal("0"), Decimal("3")) == "out"


def test_location_override_is_used_for_derived_status() -> None:
    row = (
        uuid.uuid4(),
        "Interior Cleaner",
        "CHEM-1",
        "chemicals",
        "liter",
        uuid.uuid4(),
        "Main Shop",
        Decimal("2.800"),
        Decimal("3.000"),
    )
    assert inventory._stock_line(row).status == "low"


def test_batch_lines_are_combined_and_sorted_for_deterministic_locking() -> None:
    first = uuid.UUID("00000000-0000-0000-0000-000000000001")
    second = uuid.UUID("00000000-0000-0000-0000-000000000002")
    result = inventory._combine(
        [
            InventoryQuantityLine(item_id=second, quantity="1.250"),
            InventoryQuantityLine(item_id=first, quantity="2"),
            InventoryQuantityLine(item_id=second, quantity="0.750"),
        ]
    )
    assert result == [(first, Decimal("2.000")), (second, Decimal("2.000"))]


def test_transfer_schema_rejects_same_source_and_destination() -> None:
    location_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        InventoryTransferCreate(
            from_location_id=location_id,
            to_location_id=location_id,
            lines=[{"item_id": uuid.uuid4(), "quantity": "1"}],
            client_event_id="transfer-event-123",
        )


def test_wastage_and_stock_count_require_a_reason() -> None:
    with pytest.raises(ValidationError):
        InventoryWastageCreate(
            location_id=uuid.uuid4(),
            lines=[{"item_id": uuid.uuid4(), "quantity": "1"}],
            reason="",
            client_event_id="wastage-event-123",
        )
    with pytest.raises(ValidationError):
        InventoryStockCountCreate(
            location_id=uuid.uuid4(),
            lines=[{"item_id": uuid.uuid4(), "counted_quantity": "1"}],
            reason="",
            client_event_id="count-event-123",
        )


@pytest.mark.asyncio
async def test_linked_team_requires_team_or_van_location_type() -> None:
    with pytest.raises(DomainError) as raised:
        await inventory.create_location(
            MagicMock(),
            context(),
            inventory.InventoryLocationCreate(
                name="Invalid Main",
                location_type="main",
                linked_team_id=uuid.uuid4(),
            ),
        )
    assert raised.value.code == "INVALID_TEAM_STOCK_LOCATION"


@pytest.mark.asyncio
async def test_item_unit_is_immutable_after_first_movement() -> None:
    manager = context()
    current = item(uuid.uuid4())
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[current, uuid.uuid4()])
    with pytest.raises(ConflictError) as raised:
        await inventory.update_item(
            session,
            manager,
            current.id,
            inventory.InventoryItemUpdate(unit="piece"),
        )
    assert raised.value.code == "INVENTORY_UNIT_IMMUTABLE"


@pytest.mark.asyncio
async def test_manager_cannot_link_usage_to_cross_business_job() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    with pytest.raises(DomainError) as raised:
        await inventory._authorize_usage(
            session,
            context(),
            uuid.uuid4(),
            uuid.uuid4(),
        )
    assert raised.value.code == "JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_transfer_rejects_insufficient_stock_before_any_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    item_id, source, destination = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source_stock = stock(item_id, source, "2")
    destination_stock = stock(item_id, destination, "0")
    monkeypatch.setattr(inventory, "_operation", AsyncMock(return_value=(operation(), True)))
    monkeypatch.setattr(inventory, "_items", AsyncMock(return_value={item_id: item(item_id)}))
    monkeypatch.setattr(inventory, "_locations", AsyncMock())
    monkeypatch.setattr(
        inventory,
        "_lock_stock",
        AsyncMock(
            return_value={
                (item_id, source): source_stock,
                (item_id, destination): destination_stock,
            }
        ),
    )
    session = MagicMock()
    session.add_all = MagicMock()
    with pytest.raises(ConflictError) as raised:
        await inventory.transfer_stock(
            session,
            manager,
            InventoryTransferCreate(
                from_location_id=source,
                to_location_id=destination,
                lines=[{"item_id": item_id, "quantity": "4"}],
                client_event_id="transfer-event-123",
            ),
        )
    assert raised.value.code == "INSUFFICIENT_STOCK"
    assert source_stock.quantity == Decimal("2")
    assert destination_stock.quantity == Decimal("0")
    session.add_all.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_writes_balanced_in_out_movements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    item_id, source, destination = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source_stock = stock(item_id, source, "20")
    destination_stock = stock(item_id, destination, "0")
    current_operation = operation()
    monkeypatch.setattr(inventory, "_operation", AsyncMock(return_value=(current_operation, True)))
    monkeypatch.setattr(inventory, "_items", AsyncMock(return_value={item_id: item(item_id)}))
    monkeypatch.setattr(inventory, "_locations", AsyncMock())
    monkeypatch.setattr(
        inventory,
        "_lock_stock",
        AsyncMock(
            return_value={
                (item_id, source): source_stock,
                (item_id, destination): destination_stock,
            }
        ),
    )
    expected = MagicMock()
    monkeypatch.setattr(inventory, "_operation_view", AsyncMock(return_value=expected))
    session = MagicMock()
    session.add_all = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    result, created = await inventory.transfer_stock(
        session,
        manager,
        InventoryTransferCreate(
            from_location_id=source,
            to_location_id=destination,
            lines=[{"item_id": item_id, "quantity": "5"}],
            client_event_id="transfer-event-123",
        ),
    )
    movements = session.add_all.call_args.args[0]
    assert [movement.movement_type for movement in movements] == ["transfer_out", "transfer_in"]
    assert source_stock.quantity == Decimal("15.000")
    assert destination_stock.quantity == Decimal("5.000")
    assert created is True
    assert result is expected


@pytest.mark.asyncio
async def test_combined_receipt_creates_exactly_one_linked_expense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    item_id, location_id = uuid.uuid4(), uuid.uuid4()
    target = stock(item_id, location_id, "0")
    current_operation = operation("receipt")
    monkeypatch.setattr(inventory, "_operation", AsyncMock(return_value=(current_operation, True)))
    monkeypatch.setattr(inventory, "_items", AsyncMock(return_value={item_id: item(item_id)}))
    monkeypatch.setattr(inventory, "_locations", AsyncMock())
    monkeypatch.setattr(
        inventory, "_lock_stock", AsyncMock(return_value={(item_id, location_id): target})
    )
    monkeypatch.setattr(inventory, "_operation_view", AsyncMock(return_value=MagicMock()))
    session = MagicMock()
    session.scalar = AsyncMock(return_value="AED")
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    result, created, finance_created = await inventory.receive_stock(
        session,
        manager,
        InventoryReceiptCreate(
            location_id=location_id,
            lines=[{"item_id": item_id, "quantity": "20"}],
            record_as_expense=True,
            expense_amount_minor=36_000,
            expense_payment_method="company_card",
            client_event_id="receipt-event-123",
        ),
    )
    expenses = [
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Expense)
    ]
    assert len(expenses) == 1
    assert expenses[0].category == "chemicals_supplies"
    assert expenses[0].amount_minor == 36_000
    assert current_operation.expense_id == expenses[0].id
    assert target.quantity == Decimal("20.000")
    assert created and finance_created and result is not None


@pytest.mark.asyncio
async def test_receipt_retry_returns_original_without_stock_or_expense_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_operation = operation("receipt")
    current_operation.expense_id = uuid.uuid4()
    monkeypatch.setattr(inventory, "_operation", AsyncMock(return_value=(current_operation, False)))
    expected = MagicMock()
    monkeypatch.setattr(inventory, "_operation_view", AsyncMock(return_value=expected))
    session = MagicMock()
    session.add = MagicMock()
    result, created, finance_created = await inventory.receive_stock(
        session,
        context(),
        InventoryReceiptCreate(
            location_id=uuid.uuid4(),
            lines=[{"item_id": uuid.uuid4(), "quantity": "20"}],
            record_as_expense=True,
            expense_amount_minor=36_000,
            expense_payment_method="company_card",
            client_event_id="receipt-event-123",
        ),
    )
    assert result is expected
    assert not created and not finance_created
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_stock_count_records_only_compensating_adjustments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    location_id = uuid.uuid4()
    lower_item, higher_item = uuid.uuid4(), uuid.uuid4()
    lower_stock = stock(lower_item, location_id, "4.250")
    higher_stock = stock(higher_item, location_id, "5.000")
    current_operation = operation("stock_count")
    monkeypatch.setattr(
        inventory, "_operation", AsyncMock(return_value=(current_operation, True))
    )
    monkeypatch.setattr(
        inventory,
        "_items",
        AsyncMock(return_value={lower_item: item(lower_item), higher_item: item(higher_item)}),
    )
    monkeypatch.setattr(inventory, "_locations", AsyncMock())
    monkeypatch.setattr(
        inventory,
        "_lock_stock",
        AsyncMock(
            return_value={
                (lower_item, location_id): lower_stock,
                (higher_item, location_id): higher_stock,
            }
        ),
    )
    monkeypatch.setattr(inventory, "_operation_view", AsyncMock(return_value=MagicMock()))
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    _, created = await inventory.record_stock_count(
        session,
        manager,
        InventoryStockCountCreate(
            location_id=location_id,
            lines=[
                {"item_id": lower_item, "counted_quantity": "4.000"},
                {"item_id": higher_item, "counted_quantity": "6.000"},
            ],
            reason="Physical stock count",
            client_event_id="count-event-123",
        ),
    )
    movements = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], InventoryMovement)
    ]
    assert {movement.movement_type for movement in movements} == {
        "adjustment_in",
        "adjustment_out",
    }
    assert {movement.quantity for movement in movements} == {
        Decimal("0.250"),
        Decimal("1.000"),
    }
    assert lower_stock.quantity == Decimal("4.000")
    assert higher_stock.quantity == Decimal("6.000")
    assert created is True


@pytest.mark.asyncio
async def test_employee_cannot_use_unrelated_team_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    employee = context(StaffRole.EMPLOYEE)
    monkeypatch.setattr(inventory, "_employee_location_ids", AsyncMock(return_value=set()))
    with pytest.raises(DomainError) as raised:
        await inventory._authorize_usage(MagicMock(), employee, uuid.uuid4(), None)
    assert raised.value.code == "INVENTORY_LOCATION_FORBIDDEN"


def test_stock_query_is_narrow_tenant_scoped_and_server_filterable() -> None:
    statement = inventory._stock_projection().where(
        InventoryStock.business_id == context().business_id
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "inventory_stock.business_id" in sql
    assert "inventory_items.name" in sql
    assert "inventory_locations.name" in sql
    assert "SELECT inventory_stock" not in sql


def test_migration_enables_rls_revokes_direct_mobile_access_and_indexes_predicates() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "f29a61e82c45_add_inventory_and_team_stock.py"
    ).read_text(encoding="utf-8")
    for table in (
        "inventory_items",
        "inventory_locations",
        "inventory_stock",
        "inventory_operations",
        "inventory_movements",
        "service_inventory_templates",
    ):
        assert table in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE" in migration
    assert "uq_inventory_operation_business_event" in migration
    assert "uq_inventory_locations_active_team" in migration
    assert "ix_inventory_movements_business_item_created" in migration


def test_movement_ledger_has_no_edit_or_delete_route() -> None:
    movement_routes = [
        route
        for route in staff_router.routes
        if getattr(route, "path", "") == "/api/v1/staff/inventory/movements"
    ]
    assert len(movement_routes) == 1
    assert movement_routes[0].methods == {"GET"}


def test_main_shop_backfill_is_tenant_scoped_and_idempotent() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "5e2c8f7a1b4d_provision_main_shop_and_rebrand.py"
    ).read_text(encoding="utf-8")
    assert "FROM businesses business" in migration
    assert "main_location.business_id = business.id" in migration
    assert "main_location.location_type = 'main'" in migration
    assert "main_location.is_active IS TRUE" in migration
    assert "AND NOT EXISTS" in migration
    assert "WHERE slug = 'abdwash'" in migration
    assert "SET name = 'Trifecta'" in migration


def test_seed_provisions_main_shop_without_replacing_existing_main_location() -> None:
    seed = (Path(__file__).parents[1] / "app" / "cli" / "seed.py").read_text(
        encoding="utf-8"
    )
    assert 'InventoryLocation.location_type == "main"' in seed
    assert "if not main_locations:" in seed
    assert "len(main_locations) == 1" in seed
    assert "business_settings.default_inventory_location_id" in seed
    assert '"Main Shop"' in seed
