import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.job_consumption as consumption
from app.auth.dependencies import StaffContext
from app.domain.enums import JobStatus, StaffRole
from app.domain.errors import DomainError
from app.models.entities import (
    Expense,
    InventoryLocation,
    InventoryOperation,
    Job,
    JobInventoryConsumptionLine,
    JobInventoryConsumptionRun,
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


def job(manager: StaffContext) -> Job:
    return Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        business_id=manager.business_id,
        assigned_resource_id=uuid.uuid4(),
        status=JobStatus.IN_PROGRESS,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC),
    )


def result(rows: list[tuple[object, ...]]) -> MagicMock:
    value = MagicMock()
    value.all.return_value = rows
    return value


def template_row(
    *,
    service_id: uuid.UUID,
    item_id: uuid.UUID,
    expected: str = "50",
    active: bool = True,
    booking_service_id: uuid.UUID | None = None,
    service_name: str = "Standard Wash",
) -> tuple[object, ...]:
    return (
        booking_service_id or uuid.uuid4(),
        service_id,
        service_name,
        1,
        item_id,
        Decimal(expected),
        "Car Shampoo",
        "milliliter",
        active,
    )


@pytest.mark.asyncio
async def test_normal_completion_snapshots_and_applies_expected_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    service_id, item_id, location_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[result([template_row(service_id=service_id, item_id=item_id)]), result([])]
    )
    location = InventoryLocation(
        id=location_id,
        business_id=manager.business_id,
        name="Team Van",
        location_type="van",
        linked_team_id=current_job.assigned_resource_id,
        is_active=True,
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [location]
    session.scalars = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    operation = InventoryOperation(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        operation_type="usage",
        client_event_id=f"service-completion:{current_job.id}",
        request_hash="a" * 64,
        actor_staff_id=manager.staff_id,
    )
    apply = AsyncMock(return_value=(operation, {item_id: Decimal("50.000")}))
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(
        session, manager, current_job
    )

    run = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], JobInventoryConsumptionRun)
    )
    line = session.add_all.call_args.args[0][0]
    assert processed.status == "applied"
    assert processed.attention_lines == 0
    assert run.source_location_id == location_id
    assert run.inventory_operation_id == operation.id
    assert isinstance(line, JobInventoryConsumptionLine)
    assert line.expected_quantity == Decimal("50.000")
    assert line.automatic_applied_quantity == Decimal("50.000")
    assert line.shortfall_quantity == Decimal("0.000")
    assert not any(
        isinstance(call.args[0], Expense) for call in session.add.call_args_list
    )


@pytest.mark.asyncio
async def test_insufficient_stock_is_partial_and_never_blocks_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    service_id, item_id = uuid.uuid4(), uuid.uuid4()
    location = InventoryLocation(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        name="Team Stock",
        location_type="mobile_team",
        linked_team_id=current_job.assigned_resource_id,
        is_active=True,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[result([template_row(service_id=service_id, item_id=item_id)]), result([])]
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [location]
    session.scalars = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    operation = MagicMock(id=uuid.uuid4())
    monkeypatch.setattr(
        consumption,
        "apply_available_job_usage",
        AsyncMock(return_value=(operation, {item_id: Decimal("20.000")})),
    )

    processed = await consumption.process_job_consumption(session, manager, current_job)

    run = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], JobInventoryConsumptionRun)
    )
    line = session.add_all.call_args.args[0][0]
    assert processed.status == "needs_review"
    assert run.has_attention is True
    assert line.automatic_applied_quantity == Decimal("20.000")
    assert line.shortfall_quantity == Decimal("30.000")
    assert line.issue_code == "INSUFFICIENT_RECORDED_STOCK"


@pytest.mark.asyncio
async def test_missing_location_records_attention_without_fabricated_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    item_id = uuid.uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[
            result([template_row(service_id=uuid.uuid4(), item_id=item_id)]),
            result([]),
        ]
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = []
    session.scalars = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    apply = AsyncMock()
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, current_job)

    line = session.add_all.call_args.args[0][0]
    assert processed.status == "needs_review"
    assert line.issue_code == "SOURCE_LOCATION_MISSING"
    assert line.shortfall_quantity == Decimal("50.000")
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_preexisting_manual_usage_prevents_cutover_double_deduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    item_id = uuid.uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[
            result([template_row(service_id=uuid.uuid4(), item_id=item_id)]),
            result([(item_id, uuid.uuid4(), Decimal("50"))]),
        ]
    )
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    apply = AsyncMock()
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, current_job)

    line = session.add_all.call_args.args[0][0]
    assert processed.status == "applied"
    assert line.preexisting_manual_quantity == Decimal("50.000")
    assert line.automatic_applied_quantity == Decimal("0.000")
    assert line.shortfall_quantity == Decimal("0.000")
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_without_template_records_no_template_run() -> None:
    manager = context()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=result([]))
    session.add = MagicMock()
    session.flush = AsyncMock()

    processed = await consumption.process_job_consumption(session, manager, job(manager))

    run = session.add.call_args.args[0]
    assert processed.status == "no_template"
    assert run.status == "no_template"
    assert run.has_attention is False


@pytest.mark.asyncio
async def test_employee_cannot_review_consumption_attention() -> None:
    with pytest.raises(DomainError) as raised:
        await consumption.review_consumption(
            MagicMock(), context(StaffRole.EMPLOYEE), uuid.uuid4(), None
        )
    assert raised.value.code == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_multiple_service_lines_preserve_history_and_batch_shared_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    item_id = uuid.uuid4()
    location = InventoryLocation(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        name="Assigned Van",
        location_type="van",
        linked_team_id=current_job.assigned_resource_id,
        is_active=True,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[
            result(
                [
                    template_row(
                        service_id=uuid.uuid4(),
                        item_id=item_id,
                        expected="50",
                        service_name="Standard Wash",
                    ),
                    template_row(
                        service_id=uuid.uuid4(),
                        item_id=item_id,
                        expected="30",
                        service_name="Executive Wash",
                    ),
                ]
            ),
            result([]),
        ]
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [location]
    session.scalars = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    apply = AsyncMock(
        return_value=(MagicMock(id=uuid.uuid4()), {item_id: Decimal("80.000")})
    )
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, current_job)

    assert processed.status == "applied"
    assert apply.await_args.kwargs["quantities"] == {item_id: Decimal("80.000")}
    lines = session.add_all.call_args.args[0]
    assert [line.service_name_snapshot for line in lines] == [
        "Standard Wash",
        "Executive Wash",
    ]
    assert [line.automatic_applied_quantity for line in lines] == [
        Decimal("50.000"),
        Decimal("30.000"),
    ]


@pytest.mark.asyncio
async def test_inactive_template_item_is_snapshotted_for_review_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[
            result(
                [
                    template_row(
                        service_id=uuid.uuid4(), item_id=uuid.uuid4(), active=False
                    )
                ]
            ),
            result([]),
        ]
    )
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    apply = AsyncMock()
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, job(manager))

    line = session.add_all.call_args.args[0][0]
    assert processed.status == "needs_review"
    assert line.issue_code == "INVENTORY_ITEM_INACTIVE"
    assert line.shortfall_quantity == Decimal("50.000")
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_team_sources_do_not_select_or_deduct_random_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    locations = [
        InventoryLocation(
            id=uuid.uuid4(),
            business_id=manager.business_id,
            name=f"Van {index}",
            location_type="van",
            linked_team_id=current_job.assigned_resource_id,
            is_active=True,
        )
        for index in range(2)
    ]
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[
            result([template_row(service_id=uuid.uuid4(), item_id=uuid.uuid4())]),
            result([]),
        ]
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = locations
    session.scalars = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    apply = AsyncMock()
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, current_job)

    line = session.add_all.call_args.args[0][0]
    assert processed.status == "needs_review"
    assert line.issue_code == "SOURCE_LOCATION_AMBIGUOUS"
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_run_is_exactly_once_and_does_not_reload_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = context()
    current_job = job(manager)
    run = JobInventoryConsumptionRun(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        job_id=current_job.id,
        status="applied",
        source_resolution="van",
        has_attention=False,
        processed_at=datetime.now(UTC),
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=run)
    session.execute = AsyncMock(return_value=MagicMock(one=MagicMock(return_value=(2, 0))))
    apply = AsyncMock()
    monkeypatch.setattr(consumption, "apply_available_job_usage", apply)

    processed = await consumption.process_job_consumption(session, manager, current_job)

    assert processed == consumption.ConsumptionProcessResult("applied", 2, 0, False)
    assert session.execute.await_count == 1
    apply.assert_not_awaited()


def test_consumption_migration_is_forward_only_private_and_not_a_backfill() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "b91c2d7e4f60_add_job_inventory_consumption.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "e7441de34e33"' in migration
    assert "uq_job_inventory_consumption_job" in migration
    assert "job_inventory_line_nonnegative_quantities" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL" in migration
    assert "INSERT INTO" not in migration.upper()


@pytest.mark.asyncio
async def test_job_summary_separates_manual_usage_beyond_expected_snapshot() -> None:
    manager = context()
    job_id, item_id, booking_service_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    run = JobInventoryConsumptionRun(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        job_id=job_id,
        status="applied",
        source_resolution="explicit_usage",
        has_attention=False,
        processed_at=datetime.now(UTC),
    )
    line = JobInventoryConsumptionLine(
        id=uuid.uuid4(),
        business_id=manager.business_id,
        run_id=run.id,
        booking_service_id=booking_service_id,
        service_id=uuid.uuid4(),
        service_name_snapshot="Standard Wash",
        inventory_item_id=item_id,
        item_name_snapshot="Car Shampoo",
        unit_snapshot="milliliter",
        expected_quantity=Decimal("50"),
        automatic_applied_quantity=Decimal("0"),
        preexisting_manual_quantity=Decimal("50"),
        shortfall_quantity=Decimal("0"),
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result([(run, line, "Team Van")]),
            result([(job_id, item_id, Decimal("70"))]),
        ]
    )

    summary = (await consumption.consumption_summaries(session, manager, [job_id]))[
        job_id
    ]

    assert summary.lines[0].preexisting_manual_quantity == Decimal("50.000")
    assert summary.lines[0].automatic_applied_quantity == Decimal("0.000")
    assert summary.lines[0].additional_manual_quantity == Decimal("20.000")
