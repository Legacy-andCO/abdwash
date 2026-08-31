"""add catalogue invoicing and expense evidence

Revision ID: c18f4a7b2d91
Revises: 8a72c1d4e6f0
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c18f4a7b2d91"
down_revision: str | None = "8a72c1d4e6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CATALOGUE = (
    (
        "Standard Wash",
        "Complete mobile wash for regular vehicle care.",
        7300,
        8600,
        120,
        "single_service",
        True,
        [
            "Exterior Power Wash",
            "Hard Wash",
            "Tires & Rims Clean & Shine",
            "Interior Vacuum",
            "Interior Dusting",
            "Interior Wipe Down",
            "Interior Windows Cleaning",
        ],
    ),
    (
        "Gold Wash",
        "More complete exterior and interior care with finishing touches.",
        9300,
        10500,
        150,
        "single_service",
        True,
        [
            "Exterior Power Wash",
            "Foam Wash",
            "Hard Wash",
            "Tires & Rims Clean & Shine",
            "Underbody Rinse",
            "Interior Vacuum",
            "Interior Dusting",
            "Interior Wipe Down",
            "Interior Windows Cleaning",
            "Dashboard Shine",
            "Protective Plastic Covers for Mat & Steering Wheel",
            "Air Freshener",
        ],
    ),
    (
        "Premium Wash",
        "Premium exterior, engine, wheel and interior care.",
        12500,
        13500,
        180,
        "single_service",
        True,
        [
            "Exterior Power Wash",
            "Foam Wash",
            "Hard Wash",
            "Tires & Rims Clean & Shine",
            "Underbody Rinse",
            "Spray Wax Application",
            "Engine Cleaning & Protection",
            "Wheel Chemical Cleaning",
            "Interior Vacuum",
            "Interior Dusting",
            "Interior Wipe Down",
            "Interior Windows Cleaning",
            "Dashboard Shine",
            "Protective Plastic Covers for Mat, Steering Wheel & Seats",
            "Air Freshener",
        ],
    ),
    (
        "Monthly Package",
        "Once weekly. Monthly package; online entitlement activation is not yet available.",
        26000,
        37000,
        120,
        "monthly_package",
        False,
        [
            "Once weekly",
            "Exterior Power Wash",
            "Hard Wash",
            "Tires & Rims Clean & Shine",
            "Interior Vacuum",
            "Interior Dusting",
            "Interior Wipe Down",
            "Interior Windows Cleaning",
        ],
    ),
    (
        "Interior Deep Cleaning",
        "A complete interior reset for upholstery, leather and difficult stains.",
        35000,
        42000,
        240,
        "single_service",
        True,
        ["Full Interior Deep Cleaning", "Shampooing", "Stain Removal", "Leather Deep Cleaning"],
    ),
    (
        "Exterior Polishing",
        "Exterior polishing, wax and paint enhancement.",
        40000,
        52000,
        240,
        "single_service",
        True,
        ["Full Exterior Polishing", "Wax", "Paint Enhancement"],
    ),
)


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column(
            "included_features", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
    )
    op.add_column(
        "services",
        sa.Column("product_kind", sa.String(24), server_default="single_service", nullable=False),
    )
    op.add_column(
        "services",
        sa.Column(
            "customer_bookable", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )
    op.create_check_constraint(
        "service_product_kind", "services", "product_kind IN ('single_service','monthly_package')"
    )

    financial_columns = (
        sa.Column("legal_name", sa.String(200)),
        sa.Column("trading_name", sa.String(200)),
        sa.Column("billing_address", sa.Text()),
        sa.Column("billing_emirate", sa.String(80)),
        sa.Column(
            "billing_country", sa.String(80), server_default="United Arab Emirates", nullable=False
        ),
        sa.Column("tax_registration_number", sa.String(40)),
        sa.Column("vat_registered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), server_default=sa.text("5.00"), nullable=False),
        sa.Column(
            "prices_include_vat", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("billing_email", sa.String(320)),
        sa.Column("billing_phone", sa.String(40)),
    )
    for column in financial_columns:
        op.add_column("business_settings", column)
    op.create_check_constraint(
        "valid_business_vat_rate", "business_settings", "vat_rate BETWEEN 0 AND 100"
    )
    op.create_check_constraint(
        "vat_registration_requires_trn",
        "business_settings",
        "vat_registered IS FALSE OR tax_registration_number IS NOT NULL",
    )

    op.add_column("bookings", sa.Column("billing_company_name", sa.String(200)))
    op.add_column("bookings", sa.Column("billing_address", sa.Text()))
    op.add_column("bookings", sa.Column("billing_tax_registration_number", sa.String(40)))

    op.create_table(
        "invoice_sequences",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("issue_year", sa.Integer(), nullable=False),
        sa.Column("next_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("issue_year >= 2020", name="valid_invoice_sequence_year"),
        sa.CheckConstraint("next_number > 0", name="positive_invoice_sequence"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id", "issue_year"),
    )
    op.create_table(
        "revenue_invoices",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("payment_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(40), nullable=False),
        sa.Column("document_type", sa.String(24), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supply_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("supplier_snapshot", sa.JSON(), nullable=False),
        sa.Column("customer_snapshot", sa.JSON(), nullable=False),
        sa.Column("line_items", sa.JSON(), nullable=False),
        sa.Column("subtotal_minor", sa.Integer(), nullable=False),
        sa.Column("discount_minor", sa.Integer(), nullable=False),
        sa.Column("vat_amount_minor", sa.Integer(), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False),
        sa.Column("payment_reference", sa.String(255)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "document_type IN ('tax_invoice','invoice')", name="revenue_invoice_document_type"
        ),
        sa.CheckConstraint(
            "subtotal_minor >= 0 AND discount_minor >= 0 "
            "AND vat_amount_minor >= 0 AND total_minor >= 0",
            name="nonnegative_revenue_invoice_totals",
        ),
        sa.CheckConstraint(
            "total_minor = subtotal_minor - discount_minor + vat_amount_minor",
            name="revenue_invoice_total_consistent",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_transaction_id"),
        sa.UniqueConstraint("business_id", "invoice_number", name="uq_revenue_invoice_number"),
    )
    op.create_index("ix_revenue_invoices_booking", "revenue_invoices", ["booking_id", "issued_at"])
    op.create_index(
        "ix_revenue_invoices_business_issued", "revenue_invoices", ["business_id", "issued_at"]
    )

    expense_columns = (
        sa.Column("supplier_tax_registration_number", sa.String(40)),
        sa.Column("supplier_document_number", sa.String(160)),
        sa.Column("net_amount_minor", sa.Integer()),
        sa.Column("vat_amount_minor", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "evidence_status", sa.String(32), server_default="missing_evidence", nullable=False
        ),
    )
    for column in expense_columns:
        op.add_column("expenses", column)
    op.execute("UPDATE expenses SET net_amount_minor = amount_minor")
    op.alter_column("expenses", "net_amount_minor", nullable=False)
    op.execute(
        "UPDATE expenses SET evidence_status = CASE WHEN receipt_object_path IS NULL "
        "THEN 'missing_evidence' ELSE 'complete' END"
    )
    op.create_check_constraint(
        "expense_amount_breakdown",
        "expenses",
        "net_amount_minor >= 0 AND vat_amount_minor >= 0 "
        "AND amount_minor = net_amount_minor + vat_amount_minor",
    )
    op.create_check_constraint(
        "expense_evidence_status",
        "expenses",
        "evidence_status IN ('complete','missing_evidence','not_required')",
    )
    op.create_table(
        "expense_evidence",
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("object_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("client_request_id", sa.String(160), nullable=False),
        sa.Column("uploaded_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_staff_id"], ["staff_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('pending','ready')", name="expense_evidence_upload_status"),
        sa.UniqueConstraint("expense_id", "object_path", name="uq_expense_evidence_object"),
        sa.UniqueConstraint("expense_id", "client_request_id", name="uq_expense_evidence_request"),
    )
    op.create_index("ix_expense_evidence_expense", "expense_evidence", ["expense_id", "created_at"])

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE services SET is_active = false WHERE name IN "
            "('Development Standard Wash','Express Exterior',"
            "'Signature Inside & Out','Premium Detail')"
        )
    )
    import json

    for sort_order, (
        name,
        description,
        car_price,
        suv_price,
        duration,
        kind,
        bookable,
        features,
    ) in enumerate(CATALOGUE, 1):
        params = {
            "name": name,
            "description": description,
            "price": car_price,
            "duration": duration,
            "sort_order": sort_order,
            "features": json.dumps(features),
            "kind": kind,
            "bookable": bookable,
        }
        bind.execute(
            sa.text(
                "INSERT INTO services (id,business_id,name,description,price_minor,"
                "estimated_duration_minutes,included_features,product_kind,"
                "customer_bookable,is_active,mobile_available,shop_available,sort_order) "
                "SELECT gen_random_uuid(), b.id, :name, :description, :price, :duration, "
                "CAST(:features AS json), "
                ":kind, :bookable, true, true, true, :sort_order FROM businesses b "
                "WHERE NOT EXISTS (SELECT 1 FROM services s "
                "WHERE s.business_id=b.id AND s.name=:name)"
            ),
            params,
        )
        bind.execute(
            sa.text(
                "UPDATE services SET description=:description, price_minor=:price, "
                "estimated_duration_minutes=:duration, included_features=CAST(:features AS json), "
                "product_kind=:kind, customer_bookable=:bookable, is_active=true, "
                "mobile_available=true, "
                "sort_order=:sort_order WHERE name=:name"
            ),
            params,
        )
        for vehicle_type in ("sedan", "hatchback", "coupe", "other"):
            bind.execute(
                sa.text(
                    "INSERT INTO service_prices "
                    "(id,business_id,service_id,vehicle_type,price_minor) "
                    "SELECT gen_random_uuid(),s.business_id,s.id,:vehicle_type,:price "
                    "FROM services s WHERE s.name=:name "
                    "ON CONFLICT (service_id,vehicle_type) DO UPDATE "
                    "SET price_minor=EXCLUDED.price_minor"
                ),
                {"name": name, "vehicle_type": vehicle_type, "price": car_price},
            )
        for vehicle_type in ("suv", "pickup", "van"):
            bind.execute(
                sa.text(
                    "INSERT INTO service_prices "
                    "(id,business_id,service_id,vehicle_type,price_minor) "
                    "SELECT gen_random_uuid(),s.business_id,s.id,:vehicle_type,:price "
                    "FROM services s WHERE s.name=:name "
                    "ON CONFLICT (service_id,vehicle_type) DO UPDATE "
                    "SET price_minor=EXCLUDED.price_minor"
                ),
                {"name": name, "vehicle_type": vehicle_type, "price": suv_price},
            )


def downgrade() -> None:
    op.drop_index("ix_expense_evidence_expense", table_name="expense_evidence")
    op.drop_table("expense_evidence")
    op.drop_constraint("expense_evidence_status", "expenses", type_="check")
    op.drop_constraint("expense_amount_breakdown", "expenses", type_="check")
    for name in (
        "evidence_status",
        "vat_amount_minor",
        "net_amount_minor",
        "supplier_document_number",
        "supplier_tax_registration_number",
    ):
        op.drop_column("expenses", name)
    op.drop_index("ix_revenue_invoices_business_issued", table_name="revenue_invoices")
    op.drop_index("ix_revenue_invoices_booking", table_name="revenue_invoices")
    op.drop_table("revenue_invoices")
    op.drop_table("invoice_sequences")
    for name in ("billing_tax_registration_number", "billing_address", "billing_company_name"):
        op.drop_column("bookings", name)
    op.drop_constraint("vat_registration_requires_trn", "business_settings", type_="check")
    op.drop_constraint("valid_business_vat_rate", "business_settings", type_="check")
    for name in (
        "billing_phone",
        "billing_email",
        "prices_include_vat",
        "vat_rate",
        "vat_registered",
        "tax_registration_number",
        "billing_country",
        "billing_emirate",
        "billing_address",
        "trading_name",
        "legal_name",
    ):
        op.drop_column("business_settings", name)
    op.drop_constraint("service_product_kind", "services", type_="check")
    op.drop_column("services", "customer_bookable")
    op.drop_column("services", "product_kind")
    op.drop_column("services", "included_features")
