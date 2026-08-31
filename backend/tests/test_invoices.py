import uuid
from datetime import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.invoices as invoices
from app.integrations.notifications.resend import render_email
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    Business,
    BusinessSettings,
    Payment,
    PaymentTransaction,
    RevenueInvoice,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("customer_email", ["customer@example.com", None])
async def test_successful_payment_creates_immutable_non_vat_invoice_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    customer_email: str | None,
) -> None:
    business_id = uuid.uuid4()
    booking_id = uuid.uuid4()
    payment = Payment(
        id=uuid.uuid4(),
        booking_id=booking_id,
        status="paid",
        method="cash",
        amount_minor=8_600,
        currency_code="AED",
    )
    transaction = PaymentTransaction(
        id=uuid.uuid4(),
        payment_id=payment.id,
        transaction_type="cash_payment",
        status="succeeded",
        amount_minor=8_600,
    )
    booking = Booking(
        id=booking_id,
        business_id=business_id,
        reference="AW-TEST",
        customer_first_name="Aisha",
        customer_surname="Ali",
        customer_email=customer_email,
        customer_phone="+971501234567",
    )
    vehicle = BookingVehicle(
        id=uuid.uuid4(), booking_id=booking_id, position=1, make="Toyota", model="RAV4"
    )
    service = BookingService(
        booking_id=booking_id,
        booking_vehicle_id=vehicle.id,
        service_id=uuid.uuid4(),
        service_name="Standard Wash",
        unit_price_minor=8_600,
        list_price_minor=9_600,
        discount_minor=1_000,
        quantity=1,
        line_total_minor=8_600,
    )
    settings = BusinessSettings(
        business_id=business_id,
        timezone="Asia/Dubai",
        currency_code="AED",
        opening_time=time(8),
        closing_time=time(18),
        legal_name="Trifecta Auto Care LLC",
        billing_country="United Arab Emirates",
        vat_registered=False,
        vat_rate=Decimal("5.00"),
        prices_include_vat=True,
    )
    business = Business(id=business_id, name="Trifecta", slug="trifecta")
    business_result = MagicMock()
    business_result.one.return_value = (business, settings)
    services_result = MagicMock()
    services_result.all.return_value = [(service, vehicle)]
    addons_result = MagicMock()
    addons_result.all.return_value = []
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock(side_effect=[business_result, services_result, addons_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    monkeypatch.setattr(invoices, "_next_invoice_number", AsyncMock(return_value="TRI-2026-000001"))

    invoice = await invoices.issue_revenue_invoice(
        session, booking=booking, payment=payment, transaction=transaction
    )

    assert invoice.document_type == "invoice"
    assert invoice.invoice_number == "TRI-2026-000001"
    assert invoice.total_minor == 8_600
    assert invoice.subtotal_minor == 9_600
    assert invoice.discount_minor == 1_000
    assert invoice.vat_amount_minor == 0
    assert invoice.line_items[0]["description"] == "Standard Wash"
    assert invoice.customer_snapshot["email"] == customer_email
    assert invoice.payment_transaction_id == transaction.id


def test_vat_registered_invoice_uses_inclusive_vat_portion() -> None:
    assert invoices._vat_portion(10_500, Decimal("5.00")) == 500


def test_invoice_model_enforces_unique_number_transaction_and_consistent_total() -> None:
    constraint_names = {item.name for item in RevenueInvoice.__table__.constraints}
    assert "uq_revenue_invoice_number" in constraint_names
    assert any(
        name and name.endswith("revenue_invoice_total_consistent")
        for name in constraint_names
    )
    assert RevenueInvoice.__table__.c.payment_transaction_id.unique is True


def test_payment_received_email_contains_invoice_action() -> None:
    subject, html = render_email(
        "payment_received",
        {
            "booking_reference": "AW-TEST",
            "customer_first_name": "Aisha",
            "invoice_number": "TRI-2026-000001",
            "currency_code": "AED",
            "amount_paid_minor": 8_600,
            "payment_method": "cash",
            "invoice_url": "https://example.test/invoice?invoice=id#token",
        },
    )
    assert "Payment received" in subject
    assert "TRI-2026-000001" in html
    assert "View invoice" in html
