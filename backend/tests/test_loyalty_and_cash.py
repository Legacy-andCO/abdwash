import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.staff_operations as staff_operations
from app.auth.dependencies import StaffContext
from app.domain.cash import authoritative_cash_change
from app.domain.enums import JobStatus, LoyaltyEventType, PaymentStatus, StaffRole
from app.domain.errors import DomainError
from app.models.entities import (
    Booking,
    BookingService,
    CustomerProfile,
    Job,
    LoyaltyEvent,
    NotificationOutbox,
    Payment,
    PaymentTransaction,
    RevenueInvoice,
)
from app.schemas.staff import CashTenderAction, StaffJob
from app.services.loyalty import (
    award_first_review_bonus,
    is_qualifying_service_line,
    loyalty_progress_from_ledger,
)
from app.services.manager_customers import list_manager_customers


def staff_context(role: StaffRole = StaffRole.EMPLOYEE) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=role,
        timezone="Asia/Dubai",
    )


def test_cash_change_uses_integer_minor_units_and_rejects_underpayment() -> None:
    assert (
        authoritative_cash_change(
            due_minor=8_600,
            tendered_minor=10_000,
            submitted_change_minor=1_400,
        )
        == 1_400
    )
    with pytest.raises(DomainError) as insufficient:
        authoritative_cash_change(
            due_minor=8_600,
            tendered_minor=8_599,
            submitted_change_minor=0,
        )
    assert insufficient.value.code == "CASH_TENDER_INSUFFICIENT"
    with pytest.raises(DomainError) as mismatch:
        authoritative_cash_change(
            due_minor=8_600,
            tendered_minor=10_000,
            submitted_change_minor=1_399,
        )
    assert mismatch.value.details == {"authoritative_change_minor": 1_400}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("customer_email", "expected_notifications"),
    [("customer@example.com", ["payment_received"]), (None, [])],
)
async def test_cash_payment_records_due_tender_and_change_without_inflating_revenue(
    monkeypatch: pytest.MonkeyPatch,
    customer_email: str | None,
    expected_notifications: list[str],
) -> None:
    context = staff_context()
    job = Job(
        id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        business_id=context.business_id,
        status=JobStatus.COMPLETED,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC),
    )
    booking = Booking(
        id=job.booking_id,
        business_id=context.business_id,
        status="completed",
        payment_status=PaymentStatus.UNPAID,
        customer_email=customer_email,
        version=1,
    )
    payment = Payment(
        id=uuid.uuid4(),
        booking_id=booking.id,
        status=PaymentStatus.UNPAID,
        amount_minor=8_600,
        currency_code="AED",
        version=1,
    )
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    monkeypatch.setattr(
        staff_operations,
        "_locked_job",
        AsyncMock(return_value=(job, booking, payment, "Employee")),
    )
    monkeypatch.setattr(staff_operations, "_duplicate_event", AsyncMock(return_value=False))
    monkeypatch.setattr(
        staff_operations,
        "get_job",
        AsyncMock(return_value=StaffJob.model_construct(id=job.id)),
    )
    evaluate = AsyncMock()
    monkeypatch.setattr(staff_operations, "evaluate_loyalty_for_job", evaluate)
    invoice = RevenueInvoice(id=uuid.uuid4(), business_id=context.business_id)
    issue_invoice = AsyncMock(return_value=invoice)
    monkeypatch.setattr(staff_operations, "issue_revenue_invoice", issue_invoice)

    receipt = await staff_operations.record_cash(
        session,
        context,
        job.id,
        CashTenderAction(
            client_event_id="cash-event-123",
            tendered_minor=10_000,
            change_minor=1_400,
        ),
    )

    transaction = next(
        item
        for call in session.add.call_args_list
        if isinstance((item := call.args[0]), PaymentTransaction)
    )
    assert transaction.amount_minor == 8_600
    assert transaction.cash_tendered_minor == 10_000
    assert transaction.cash_change_minor == 1_400
    assert transaction.actor_staff_id == context.staff_id
    assert transaction.client_event_id == "cash-event-123"
    assert payment.status == PaymentStatus.PAID
    assert receipt.amount_applied_minor == 8_600
    assert receipt.change_minor == 1_400
    evaluate.assert_awaited_once()
    issue_invoice.assert_awaited_once()
    payment_notifications = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], NotificationOutbox)
    ]
    assert [item.notification_type for item in payment_notifications] == expected_notifications


@pytest.mark.asyncio
async def test_cash_payment_retry_returns_original_receipt_without_second_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = staff_context()
    job = Job(id=uuid.uuid4(), booking_id=uuid.uuid4(), business_id=context.business_id)
    booking = Booking(id=job.booking_id, business_id=context.business_id)
    payment = Payment(id=uuid.uuid4(), booking_id=booking.id, amount_minor=8_600)
    transaction = PaymentTransaction(
        payment_id=payment.id,
        transaction_type="cash_payment",
        status="succeeded",
        amount_minor=8_600,
        client_event_id="cash-event-123",
        cash_tendered_minor=10_000,
        cash_change_minor=1_400,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=transaction)
    monkeypatch.setattr(
        staff_operations,
        "_locked_job",
        AsyncMock(return_value=(job, booking, payment, "Employee")),
    )
    monkeypatch.setattr(staff_operations, "_duplicate_event", AsyncMock(return_value=True))
    monkeypatch.setattr(
        staff_operations,
        "get_job",
        AsyncMock(return_value=StaffJob.model_construct(id=job.id)),
    )

    receipt = await staff_operations.record_cash(
        session,
        context,
        job.id,
        CashTenderAction(
            client_event_id="cash-event-123",
            tendered_minor=10_000,
            change_minor=1_400,
        ),
    )

    assert receipt.amount_applied_minor == 8_600
    assert receipt.tendered_minor == 10_000
    assert receipt.change_minor == 1_400
    session.add.assert_not_called()


@pytest.mark.parametrize(
    ("payment", "source", "amount", "reward", "discount", "expected"),
    [
        ("paid", "web", 8_500, None, None, True),
        ("unpaid", "web", 8_500, None, None, False),
        ("paid", "rewash", 8_500, None, None, False),
        ("paid", "web", 0, None, None, False),
        ("paid", "web", 0, uuid.uuid4(), "loyalty_reward", False),
    ],
)
def test_loyalty_qualification_rules(
    payment: str,
    source: str,
    amount: int,
    reward: uuid.UUID | None,
    discount: str | None,
    expected: bool,
) -> None:
    assert (
        is_qualifying_service_line(
            payment_status=payment,
            booking_source=source,
            line_total_minor=amount,
            loyalty_reward_id=reward,
            discount_type=discount,
        )
        is expected
    )


def test_loyalty_progress_is_ledger_based_and_reward_thresholds_are_snapshots() -> None:
    assert loyalty_progress_from_ledger(8, []) == 8
    assert loyalty_progress_from_ledger(9, [9]) == 0
    assert loyalty_progress_from_ledger(20, [9, 9]) == 2
    assert loyalty_progress_from_ledger(5, [9]) == 0
    assert LoyaltyEvent.__table__.c.source_key.nullable is False
    assert any(
        constraint.name == "uq_loyalty_event_source"
        for constraint in LoyaltyEvent.__table__.constraints
    )
    bonus_index = next(
        index
        for index in LoyaltyEvent.__table__.indexes
        if index.name == "uq_loyalty_first_review_bonus_customer"
    )
    assert bonus_index.unique is True
    assert "first_review_bonus" in str(bonus_index.dialect_options["postgresql"]["where"])


@pytest.mark.asyncio
async def test_first_review_bonus_awards_one_point_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    earn = AsyncMock()
    monkeypatch.setattr("app.services.loyalty._earn_available_rewards", earn)
    business_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    booking_id = uuid.uuid4()

    awarded = await award_first_review_bonus(
        session,
        business_id=business_id,
        customer_profile_id=customer_id,
        booking_id=booking_id,
    )

    assert awarded is True
    event = session.add.call_args.args[0]
    assert event.event_type == LoyaltyEventType.FIRST_REVIEW_BONUS
    assert event.quantity == 1
    assert event.source_key == f"first-review-bonus:{customer_id}"
    earn.assert_awaited_once()

    session.reset_mock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    assert await award_first_review_bonus(
        session,
        business_id=business_id,
        customer_profile_id=customer_id,
        booking_id=uuid.uuid4(),
    ) is False
    session.add.assert_not_called()


def test_released_reward_can_be_reused_without_erasing_historical_booking_snapshot() -> None:
    reward_column = BookingService.__table__.c.loyalty_reward_id
    assert reward_column.unique is not True
    assert all(
        constraint.name != "uq_booking_services_loyalty_reward"
        for constraint in BookingService.__table__.constraints
    )


@pytest.mark.asyncio
async def test_manager_customer_search_is_tenant_scoped_and_matches_plate() -> None:
    context = staff_context(StaffRole.MANAGER)
    result = MagicMock()
    result.all.return_value = []
    session = MagicMock()
    session.scalar = AsyncMock(return_value=9)
    session.execute = AsyncMock(return_value=result)

    response = await list_manager_customers(
        session, context, search="  AD 123  ", offset=0, limit=30
    )

    assert response.customers == []
    statement = session.execute.await_args.args[0]
    compiled_statement = statement.compile()
    compiled = str(compiled_statement).lower()
    assert context.business_id in compiled_statement.params.values()
    assert "vehicles.plate_number" in compiled
    assert "%ad 123%" in compiled_statement.params.values()


@pytest.mark.asyncio
async def test_manager_customer_list_maps_current_loyalty_result_shape() -> None:
    context = staff_context(StaffRole.MANAGER)
    profile = CustomerProfile(
        id=uuid.uuid4(),
        business_id=context.business_id,
        first_name="Mohammed",
        surname="Abdo",
        email="mohammed@example.com",
        phone="+971501234567",
        is_active=True,
    )
    rows = MagicMock()
    rows.all.return_value = [(profile, 2, 12, None, 1, 15, 9)]
    session = MagicMock()
    session.scalar = AsyncMock(return_value=9)
    session.execute = AsyncMock(return_value=rows)

    response = await list_manager_customers(session, context, search=None, offset=0, limit=30)

    customer = response.customers[0]
    assert customer.active_vehicle_count == 2
    assert customer.available_rewards == 1
    assert customer.loyalty_progress_washes == 6
    assert customer.loyalty_required_washes == 9
