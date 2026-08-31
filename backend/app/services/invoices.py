import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.models.entities import (
    Booking,
    BookingService,
    BookingServiceAddon,
    BookingVehicle,
    Business,
    BusinessSettings,
    InvoiceSequence,
    Payment,
    PaymentTransaction,
    RevenueInvoice,
)
from app.schemas.invoices import InvoiceLineView, RevenueInvoiceView


def _vat_portion(total_minor: int, rate: Decimal) -> int:
    if rate <= 0:
        return 0
    return int(
        (Decimal(total_minor) * rate / (Decimal("100") + rate)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


async def _next_invoice_number(session: AsyncSession, *, business_id: uuid.UUID, year: int) -> str:
    await session.execute(
        insert(InvoiceSequence)
        .values(business_id=business_id, issue_year=year, next_number=1)
        .on_conflict_do_nothing(index_elements=["business_id", "issue_year"])
    )
    sequence = (
        await session.scalars(
            select(InvoiceSequence)
            .where(
                InvoiceSequence.business_id == business_id,
                InvoiceSequence.issue_year == year,
            )
            .with_for_update()
        )
    ).one()
    number = sequence.next_number
    sequence.next_number += 1
    return f"TRI-{year}-{number:06d}"


async def issue_revenue_invoice(
    session: AsyncSession,
    *,
    booking: Booking,
    payment: Payment,
    transaction: PaymentTransaction,
) -> RevenueInvoice:
    existing = await session.scalar(
        select(RevenueInvoice).where(RevenueInvoice.payment_transaction_id == transaction.id)
    )
    if existing is not None:
        return existing
    business, settings = (
        await session.execute(
            select(Business, BusinessSettings)
            .join(BusinessSettings, BusinessSettings.business_id == Business.id)
            .where(Business.id == booking.business_id)
        )
    ).one()
    service_rows = (
        await session.execute(
            select(BookingService, BookingVehicle)
            .join(BookingVehicle, BookingVehicle.id == BookingService.booking_vehicle_id)
            .where(BookingService.booking_id == booking.id)
            .order_by(BookingVehicle.position, BookingService.id)
        )
    ).all()
    addon_rows = (
        await session.execute(
            select(BookingServiceAddon, BookingVehicle)
            .join(BookingVehicle, BookingVehicle.id == BookingServiceAddon.booking_vehicle_id)
            .where(BookingServiceAddon.booking_id == booking.id)
            .order_by(BookingVehicle.position, BookingServiceAddon.id)
        )
    ).all()
    lines: list[dict[str, object]] = []
    for service, vehicle in service_rows:
        lines.append(
            {
                "description": service.service_name,
                "quantity": service.quantity,
                "unit_price_minor": service.list_price_minor,
                "discount_minor": service.discount_minor,
                "line_total_minor": service.line_total_minor,
                "vehicle": f"{vehicle.make} {vehicle.model}".strip(),
            }
        )
    for addon, vehicle in addon_rows:
        lines.append(
            {
                "description": addon.addon_name,
                "quantity": 1,
                "unit_price_minor": addon.unit_price_minor,
                "discount_minor": 0,
                "line_total_minor": addon.unit_price_minor,
                "vehicle": f"{vehicle.make} {vehicle.model}".strip(),
            }
        )
    line_gross = sum(cast(int, item["line_total_minor"]) for item in lines)
    if line_gross != transaction.amount_minor:
        raise DomainError(
            "INVOICE_TOTAL_MISMATCH",
            "The payment cannot be invoiced because its immutable booking total does not match.",
            status_code=409,
        )
    vat_minor = (
        _vat_portion(transaction.amount_minor, settings.vat_rate) if settings.vat_registered else 0
    )
    discount_minor = sum(cast(int, item["discount_minor"]) for item in lines)
    subtotal_minor = transaction.amount_minor + discount_minor - vat_minor
    now = datetime.now(UTC)
    local_now = now.astimezone(ZoneInfo(settings.timezone))
    invoice = RevenueInvoice(
        business_id=booking.business_id,
        booking_id=booking.id,
        payment_id=payment.id,
        payment_transaction_id=transaction.id,
        invoice_number=await _next_invoice_number(
            session, business_id=booking.business_id, year=local_now.year
        ),
        document_type="tax_invoice" if settings.vat_registered else "invoice",
        issued_at=now,
        supply_date=local_now.date(),
        currency_code=payment.currency_code,
        supplier_snapshot={
            "legal_name": settings.legal_name or business.name,
            "trading_name": settings.trading_name or business.name,
            "address": settings.billing_address,
            "emirate": settings.billing_emirate,
            "country": settings.billing_country,
            "tax_registration_number": (
                settings.tax_registration_number if settings.vat_registered else None
            ),
            "vat_registered": settings.vat_registered,
            "vat_rate": str(settings.vat_rate),
            "prices_include_vat": settings.prices_include_vat,
            "email": settings.billing_email,
            "phone": settings.billing_phone,
        },
        customer_snapshot={
            "name": f"{booking.customer_first_name} {booking.customer_surname}".strip(),
            "email": booking.customer_email,
            "phone": booking.customer_phone,
            "company_name": booking.billing_company_name,
            "billing_address": booking.billing_address,
            "tax_registration_number": booking.billing_tax_registration_number,
        },
        line_items=lines,
        subtotal_minor=subtotal_minor,
        discount_minor=discount_minor,
        vat_amount_minor=vat_minor,
        total_minor=transaction.amount_minor,
        payment_method=payment.method or "unknown",
        payment_reference=(transaction.provider_transaction_id or payment.provider_payment_id),
    )
    session.add(invoice)
    await session.flush()
    return invoice


def invoice_view(invoice: RevenueInvoice, booking_reference: str) -> RevenueInvoiceView:
    return RevenueInvoiceView(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        document_type=invoice.document_type,
        issued_at=invoice.issued_at,
        supply_date=invoice.supply_date,
        booking_reference=booking_reference,
        currency_code=invoice.currency_code,
        supplier=invoice.supplier_snapshot,
        customer=invoice.customer_snapshot,
        lines=[InvoiceLineView.model_validate(item) for item in invoice.line_items],
        subtotal_minor=invoice.subtotal_minor,
        discount_minor=invoice.discount_minor,
        vat_amount_minor=invoice.vat_amount_minor,
        total_minor=invoice.total_minor,
        payment_method=invoice.payment_method,
        payment_reference=invoice.payment_reference,
    )


async def managed_invoice(
    session: AsyncSession, *, booking_id: uuid.UUID, invoice_id: uuid.UUID
) -> RevenueInvoiceView:
    row = (
        await session.execute(
            select(RevenueInvoice, Booking.reference)
            .join(Booking, Booking.id == RevenueInvoice.booking_id)
            .where(
                RevenueInvoice.id == invoice_id,
                RevenueInvoice.booking_id == booking_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise DomainError("INVOICE_NOT_FOUND", "Invoice not found.", status_code=404)
    return invoice_view(row[0], row[1])
