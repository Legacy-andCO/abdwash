import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

import app.services.finance as finance
from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    CashReconciliation,
    Expense,
    ExpenseEvidence,
    PaymentTransaction,
)
from app.schemas.finance import (
    CashReconciliationCreate,
    ExpenseCreate,
    ExpenseEvidenceCreate,
    ExpenseView,
)


def manager_context() -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=StaffRole.MANAGER,
        timezone="Asia/Dubai",
    )


def expense_request(**overrides: object) -> ExpenseCreate:
    values: dict[str, object] = {
        "expense_date": date(2026, 8, 27),
        "category": "fuel",
        "description": "Van fuel",
        "amount_minor": 18_000,
        "payment_method": "company_card",
        "client_event_id": "expense-event-123",
    }
    values.update(overrides)
    return ExpenseCreate(**values)


def test_expense_schema_rejects_zero_and_unknown_categories() -> None:
    with pytest.raises(ValidationError):
        expense_request(amount_minor=0)
    with pytest.raises(ValidationError):
        expense_request(category="invented")


def test_expense_schema_preserves_net_vat_gross_and_evidence_state() -> None:
    request = expense_request(
        amount_minor=10_500,
        vat_amount_minor=500,
        supplier_tax_registration_number="100000000000001",
        supplier_document_number="SUP-42",
        evidence_status="missing_evidence",
    )
    assert request.net_amount_minor == 10_000
    assert request.vat_amount_minor == 500
    with pytest.raises(ValidationError):
        expense_request(amount_minor=10_500, net_amount_minor=10_000, vat_amount_minor=400)


@pytest.mark.asyncio
async def test_internal_expense_voucher_never_masquerades_as_supplier_tax_invoice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = manager_context()
    view = ExpenseView(
        id=uuid.uuid4(),
        expense_date=date(2026, 8, 27),
        category="fuel",
        description="Van fuel",
        amount_minor=10_500,
        currency_code="AED",
        payment_method="company_card",
        paid_by_staff_id=None,
        paid_by_staff_name=None,
        team_id=None,
        team_name=None,
        related_job_id=None,
        related_booking_reference=None,
        supplier_name="Fuel supplier",
        reference_number=None,
        supplier_tax_registration_number="100000000000001",
        supplier_document_number="SUP-42",
        net_amount_minor=10_000,
        vat_amount_minor=500,
        evidence_status="complete",
        notes=None,
        receipt_available=True,
        status="active",
        created_by_staff_id=context.staff_id,
        created_at=datetime.now(UTC),
        voided_at=None,
        void_reason=None,
    )
    monkeypatch.setattr(finance, "get_expense", AsyncMock(return_value=view))
    evidence_result = MagicMock()
    evidence_result.all.return_value = ["supplier-receipt.pdf"]
    session = MagicMock()
    session.scalar = AsyncMock(return_value="Demo Manager")
    session.scalars = AsyncMock(return_value=evidence_result)
    html = await finance.expense_voucher_html(session, context, view.id)
    assert "Internal Expense Voucher" in html
    assert "Not a Tax Invoice" in html
    assert "does not establish VAT recoverability" in html
    assert "supplier-receipt.pdf" in html
    assert "Demo Manager" in html


def test_finance_models_keep_immutable_void_and_idempotency_constraints() -> None:
    expense_constraints = {item.name for item in Expense.__table__.constraints}
    reconciliation_constraints = {item.name for item in CashReconciliation.__table__.constraints}
    assert "uq_expense_business_event" in expense_constraints
    assert any(name and name.endswith("expense_void_state") for name in expense_constraints)
    assert "uq_cash_reconciliation_business_event" in reconciliation_constraints
    assert any(
        name and name.endswith("cash_reconciliation_difference")
        for name in reconciliation_constraints
    )
    assert any(
        name and name.endswith("cash_reconciliation_discrepancy_note")
        for name in reconciliation_constraints
    )
    evidence_constraints = {item.name for item in ExpenseEvidence.__table__.constraints}
    assert "uq_expense_evidence_request" in evidence_constraints
    assert any(
        name and name.endswith("expense_evidence_upload_status") for name in evidence_constraints
    )


@pytest.mark.asyncio
async def test_expense_evidence_uses_private_server_selected_path() -> None:
    context = manager_context()
    expense = Expense(
        id=uuid.uuid4(),
        business_id=context.business_id,
        status="active",
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[expense, None])
    session.add = MagicMock()
    session.flush = AsyncMock()

    evidence = await finance.prepare_expense_evidence_upload(
        session,
        context,
        expense.id,
        ExpenseEvidenceCreate(
            file_name="supplier invoice.pdf",
            content_type="application/pdf",
            client_request_id="evidence-request-123",
        ),
    )

    assert evidence.object_path.startswith(f"business/{context.business_id}/expenses/{expense.id}/")
    assert evidence.object_path.endswith(".pdf")
    assert "supplier invoice" not in evidence.object_path
    assert evidence.status == "pending"


@pytest.mark.asyncio
async def test_expense_evidence_confirmation_marks_expense_complete() -> None:
    context = manager_context()
    expense = Expense(
        id=uuid.uuid4(),
        business_id=context.business_id,
        evidence_status="missing_evidence",
        receipt_object_path=None,
    )
    evidence = ExpenseEvidence(
        id=uuid.uuid4(),
        expense_id=expense.id,
        object_path="business/example/expenses/example/evidence.pdf",
        file_name="evidence.pdf",
        content_type="application/pdf",
        status="pending",
        client_request_id="evidence-request-123",
        uploaded_by_staff_id=context.staff_id,
    )
    result = MagicMock()
    result.one_or_none.return_value = (evidence, expense)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    view = await finance.confirm_expense_evidence(
        session,
        context,
        expense.id,
        evidence.id,
        object_info={"size": 2_048, "mimetype": "application/pdf"},
        max_bytes=10_485_760,
    )

    assert view.status == "ready"
    assert evidence.size_bytes == 2_048
    assert expense.evidence_status == "complete"
    assert expense.receipt_object_path == evidence.object_path


@pytest.mark.asyncio
async def test_expense_evidence_rejects_invalid_uploaded_object() -> None:
    context = manager_context()
    expense = Expense(id=uuid.uuid4(), business_id=context.business_id)
    evidence = ExpenseEvidence(
        id=uuid.uuid4(),
        expense_id=expense.id,
        object_path="business/example/expenses/example/evidence.pdf",
        file_name="evidence.pdf",
        content_type="application/pdf",
        status="pending",
        client_request_id="evidence-request-123",
        uploaded_by_staff_id=context.staff_id,
    )
    result = MagicMock()
    result.one_or_none.return_value = (evidence, expense)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(DomainError) as raised:
        await finance.confirm_expense_evidence(
            session,
            context,
            expense.id,
            evidence.id,
            object_info={"size": 2_048, "mimetype": "image/png"},
            max_bytes=10_485_760,
        )

    assert raised.value.code == "INVALID_EXPENSE_EVIDENCE"
    assert evidence.status == "pending"


@pytest.mark.asyncio
async def test_expense_create_records_minor_units_and_audit_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = manager_context()
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[None, "AED"])
    session.add = MagicMock()
    session.flush = AsyncMock()
    monkeypatch.setattr(finance, "_validate_expense_ownership", AsyncMock())
    expected = MagicMock()
    monkeypatch.setattr(finance, "get_expense", AsyncMock(return_value=expected))

    result = await finance.create_expense(session, context, expense_request())

    created = next(
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Expense)
    )
    assert created.amount_minor == 18_000
    assert created.created_by_staff_id == context.staff_id
    assert created.business_id == context.business_id
    assert result is expected


@pytest.mark.asyncio
async def test_direct_job_expense_preserves_job_link_and_reuses_finance_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = manager_context()
    job_id = uuid.uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[None, "AED"])
    session.add = MagicMock()
    session.flush = AsyncMock()
    monkeypatch.setattr(finance, "_validate_expense_ownership", AsyncMock())
    monkeypatch.setattr(finance, "get_expense", AsyncMock(return_value=MagicMock()))

    await finance.create_expense(
        session,
        context,
        expense_request(related_job_id=job_id, description="Special leather product"),
    )

    created = next(
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Expense)
    )
    assert created.related_job_id == job_id
    assert created.description == "Special leather product"


@pytest.mark.asyncio
async def test_direct_job_expense_rejects_cross_tenant_job() -> None:
    context = manager_context()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(DomainError) as raised:
        await finance._validate_expense_ownership(
            session,
            context,
            expense_request(related_job_id=uuid.uuid4()),
        )

    assert raised.value.code == "JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_expense_retry_reuses_authoritative_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = manager_context()
    original_id = uuid.uuid4()
    expected = MagicMock()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=original_id)
    session.add = MagicMock()
    get_expense = AsyncMock(return_value=expected)
    monkeypatch.setattr(finance, "get_expense", get_expense)

    result = await finance.create_expense(session, context, expense_request())

    assert result is expected
    get_expense.assert_awaited_once_with(session, context, original_id)
    session.add.assert_not_called()


def test_pending_cash_query_filters_authoritative_successful_cash_transactions() -> None:
    statement = finance._pending_base(manager_context())
    sql = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "payment_transactions.transaction_type = 'cash_payment'" in sql
    assert "payment_transactions.status = 'succeeded'" in sql
    assert "cash_reconciliation_payments.active IS true" in sql
    assert "bookings.business_id" in sql


def reconciliation_rows(context: StaffContext, amount: int = 8_600) -> list[tuple[object, ...]]:
    transaction = PaymentTransaction(
        id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        transaction_type="cash_payment",
        status="succeeded",
        amount_minor=amount,
        cash_tendered_minor=10_000,
        cash_change_minor=10_000 - amount,
        actor_staff_id=context.staff_id,
    )
    return [
        (
            transaction,
            "AW-TEST",
            uuid.uuid4(),
            "Demo Employee",
            uuid.uuid4(),
            "Mobile Team 1",
            "AED",
        )
    ]


@pytest.mark.asyncio
async def test_cash_reconciliation_uses_transaction_amount_not_cash_tender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = manager_context()
    rows = reconciliation_rows(context)
    execute_result = MagicMock()
    execute_result.all.return_value = rows
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[None, 0])
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    expected = MagicMock()
    monkeypatch.setattr(finance, "_reconciliation_view", AsyncMock(return_value=expected))

    result = await finance.create_reconciliation(
        session,
        context,
        CashReconciliationCreate(
            staff_id=context.staff_id,
            payment_transaction_ids=[rows[0][0].id],
            declared_cash_minor=8_600,
            client_event_id="handover-event-123",
        ),
    )

    created = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], CashReconciliation)
    )
    assert created.expected_cash_minor == 8_600
    assert created.declared_cash_minor == 8_600
    assert created.difference_minor == 0
    assert result is expected


@pytest.mark.asyncio
async def test_cash_reconciliation_difference_requires_note() -> None:
    context = manager_context()
    rows = reconciliation_rows(context)
    execute_result = MagicMock()
    execute_result.all.return_value = rows
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[None, 0])
    session.execute = AsyncMock(return_value=execute_result)

    with pytest.raises(DomainError) as raised:
        await finance.create_reconciliation(
            session,
            context,
            CashReconciliationCreate(
                staff_id=context.staff_id,
                payment_transaction_ids=[rows[0][0].id],
                declared_cash_minor=8_000,
                client_event_id="handover-event-124",
            ),
        )
    assert raised.value.code == "CASH_DISCREPANCY_NOTE_REQUIRED"


@pytest.mark.asyncio
async def test_cash_transaction_cannot_be_reconciled_when_no_longer_pending() -> None:
    context = manager_context()
    execute_result = MagicMock()
    execute_result.all.return_value = []
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    with pytest.raises(ConflictError):
        await finance.create_reconciliation(
            session,
            context,
            CashReconciliationCreate(
                staff_id=context.staff_id,
                payment_transaction_ids=[uuid.uuid4()],
                declared_cash_minor=8_600,
                client_event_id="handover-event-125",
            ),
        )


def test_business_timezone_range_is_half_open() -> None:
    start, end = finance._bounds(date(2026, 8, 27), date(2026, 8, 27), "Asia/Dubai")
    assert start == datetime(2026, 8, 26, 20, tzinfo=UTC)
    assert end == datetime(2026, 8, 27, 20, tzinfo=UTC)


def test_finance_migration_enables_rls_and_active_payment_uniqueness() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "63973a3319dd_add_operational_finance_ledger.py"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert '"expenses"' in migration
    assert '"cash_reconciliations"' in migration
    assert '"cash_reconciliation_payments"' in migration
    assert "uq_cash_reconciliation_payment_active" in migration
