"""Booking receivables in integer minor units, shared by all staff reporting."""

from sqlalchemy import case, func, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.entities import Booking, Job, Payment
from app.models.entities import PaymentTransaction as Tx

RECEIPTS = ("cash_payment", "card_payment", "deposit", "charge", "capture", "payment")
RETURNS = ("refund", "reversal", "void")


def ledger_sum(types: tuple[str, ...], status: str = "succeeded") -> ColumnElement[int]:
    return (
        select(func.coalesce(func.sum(Tx.amount_minor), 0))
        .where(Tx.payment_id == Payment.id, Tx.transaction_type.in_(types), Tx.status == status)
        .correlate(Payment)
        .scalar_subquery()
    )


def verified_amount() -> ColumnElement[int]:
    receipts = ledger_sum(RECEIPTS)
    # Historical provider settlements may have only a paid header.
    legacy = case(
        ((Payment.status == "paid") & (receipts == 0), Payment.amount_minor), else_=receipts
    )
    return legacy - ledger_sum(RETURNS)


def pending_amount() -> ColumnElement[int]:
    return ledger_sum(("cash_payment", "card_payment"), "pending")


def adjusted_charge() -> ColumnElement[int]:
    return (
        Payment.amount_minor
        + ledger_sum(("debit_adjustment",))
        - ledger_sum(("credit_adjustment",))
    )


def balance_due() -> ColumnElement[int]:
    return func.greatest(0, adjusted_charge() - verified_amount())


def completed_balance() -> ColumnElement[int]:
    completed = (
        select(Job.id)
        .where(Job.booking_id == Booking.id, Job.status == "completed")
        .correlate(Booking)
        .exists()
    )
    return case((completed & (Booking.status == "completed"), balance_due()), else_=0)
