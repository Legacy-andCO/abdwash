"""add operational finance ledger

Revision ID: 63973a3319dd
Revises: 7d3f2a9c8e41
Create Date: 2026-08-28 00:08:56.856806
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "63973a3319dd"
down_revision: str | None = "7d3f2a9c8e41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("paid_by_staff_id", sa.Uuid()),
        sa.Column("team_id", sa.Uuid()),
        sa.Column("related_job_id", sa.Uuid()),
        sa.Column("supplier_name", sa.String(length=200)),
        sa.Column("reference_number", sa.String(length=160)),
        sa.Column("notes", sa.Text()),
        sa.Column("receipt_object_path", sa.String(length=500)),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("client_event_id", sa.String(length=160), nullable=False),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("voided_by_staff_id", sa.Uuid()),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount_minor > 0", name="positive_expense_amount"),
        sa.CheckConstraint("status IN ('active','voided')", name="expense_status"),
        sa.CheckConstraint(
            "category IN ('chemicals_supplies','fuel','vehicle_transport','equipment',"
            "'maintenance_repairs','staff','marketing','rent_utilities',"
            "'software_subscriptions','government_fees','professional_services','miscellaneous')",
            name="expense_category",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND voided_at IS NULL "
            "AND voided_by_staff_id IS NULL AND void_reason IS NULL) OR "
            "(status = 'voided' AND voided_at IS NOT NULL "
            "AND voided_by_staff_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="expense_void_state",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_by_staff_id"], ["staff_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["schedule_resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["voided_by_staff_id"], ["staff_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "client_event_id", name="uq_expense_business_event"),
    )
    op.create_index("ix_expenses_business_date", "expenses", ["business_id", "expense_date", "id"])
    op.create_index(
        "ix_expenses_business_status_date", "expenses", ["business_id", "status", "expense_date"]
    )
    op.create_index(
        "ix_expenses_business_category_date",
        "expenses",
        ["business_id", "category", "expense_date"],
    )
    op.create_index("ix_expenses_paid_by_staff", "expenses", ["paid_by_staff_id"])
    op.create_index("ix_expenses_team", "expenses", ["team_id"])
    op.create_index("ix_expenses_related_job", "expenses", ["related_job_id"])
    op.create_index("ix_expenses_created_by_staff", "expenses", ["created_by_staff_id"])
    op.create_index("ix_expenses_voided_by_staff", "expenses", ["voided_by_staff_id"])

    op.create_table(
        "cash_reconciliations",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid()),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_cash_minor", sa.Integer(), nullable=False),
        sa.Column("declared_cash_minor", sa.Integer(), nullable=False),
        sa.Column("difference_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="confirmed", nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("client_event_id", sa.String(length=160), nullable=False),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_by_staff_id", sa.Uuid()),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("expected_cash_minor >= 0", name="nonnegative_expected_cash"),
        sa.CheckConstraint("declared_cash_minor >= 0", name="nonnegative_declared_cash"),
        sa.CheckConstraint(
            "difference_minor = declared_cash_minor - expected_cash_minor",
            name="cash_reconciliation_difference",
        ),
        sa.CheckConstraint("period_end >= period_start", name="cash_reconciliation_period"),
        sa.CheckConstraint("status IN ('confirmed','voided')", name="cash_reconciliation_status"),
        sa.CheckConstraint(
            "difference_minor = 0 OR note IS NOT NULL", name="cash_reconciliation_discrepancy_note"
        ),
        sa.CheckConstraint(
            "(status = 'confirmed' AND voided_at IS NULL "
            "AND voided_by_staff_id IS NULL AND void_reason IS NULL) OR "
            "(status = 'voided' AND voided_at IS NOT NULL "
            "AND voided_by_staff_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="cash_reconciliation_void_state",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["schedule_resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["voided_by_staff_id"], ["staff_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "client_event_id", name="uq_cash_reconciliation_business_event"
        ),
    )
    op.create_index(
        "ix_cash_reconciliations_business_created",
        "cash_reconciliations",
        ["business_id", "created_at", "id"],
    )
    op.create_index(
        "ix_cash_reconciliations_business_staff_confirmed",
        "cash_reconciliations",
        ["business_id", "staff_id", "confirmed_at"],
    )
    op.create_index("ix_cash_reconciliations_team", "cash_reconciliations", ["team_id"])
    op.create_index("ix_cash_reconciliations_staff", "cash_reconciliations", ["staff_id"])
    op.create_index(
        "ix_cash_reconciliations_created_by",
        "cash_reconciliations",
        ["created_by_staff_id"],
    )
    op.create_index(
        "ix_cash_reconciliations_confirmed_by",
        "cash_reconciliations",
        ["confirmed_by_staff_id"],
    )
    op.create_index(
        "ix_cash_reconciliations_voided_by",
        "cash_reconciliations",
        ["voided_by_staff_id"],
    )

    op.create_table(
        "cash_reconciliation_payments",
        sa.Column("reconciliation_id", sa.Uuid(), nullable=False),
        sa.Column("payment_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["reconciliation_id"], ["cash_reconciliations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cash_reconciliation_payments_reconciliation",
        "cash_reconciliation_payments",
        ["reconciliation_id"],
    )
    op.create_index(
        "ix_cash_reconciliation_payments_transaction",
        "cash_reconciliation_payments",
        ["payment_transaction_id"],
    )
    op.create_index(
        "uq_cash_reconciliation_payment_active",
        "cash_reconciliation_payments",
        ["payment_transaction_id"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
    )
    op.create_index(
        "ix_payment_transactions_cash_collector_date",
        "payment_transactions",
        ["actor_staff_id", "status", "created_at"],
        postgresql_where=sa.text("transaction_type = 'cash_payment' AND status = 'succeeded'"),
    )
    for table in ("expenses", "cash_reconciliations", "cash_reconciliation_payments"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_cash_collector_date", table_name="payment_transactions")
    op.drop_index(
        "uq_cash_reconciliation_payment_active", table_name="cash_reconciliation_payments"
    )
    op.drop_index(
        "ix_cash_reconciliation_payments_transaction",
        table_name="cash_reconciliation_payments",
    )
    op.drop_index(
        "ix_cash_reconciliation_payments_reconciliation", table_name="cash_reconciliation_payments"
    )
    op.drop_table("cash_reconciliation_payments")
    op.drop_index("ix_cash_reconciliations_voided_by", table_name="cash_reconciliations")
    op.drop_index("ix_cash_reconciliations_confirmed_by", table_name="cash_reconciliations")
    op.drop_index("ix_cash_reconciliations_created_by", table_name="cash_reconciliations")
    op.drop_index("ix_cash_reconciliations_staff", table_name="cash_reconciliations")
    op.drop_index("ix_cash_reconciliations_team", table_name="cash_reconciliations")
    op.drop_index(
        "ix_cash_reconciliations_business_staff_confirmed", table_name="cash_reconciliations"
    )
    op.drop_index("ix_cash_reconciliations_business_created", table_name="cash_reconciliations")
    op.drop_table("cash_reconciliations")
    op.drop_index("ix_expenses_voided_by_staff", table_name="expenses")
    op.drop_index("ix_expenses_created_by_staff", table_name="expenses")
    op.drop_index("ix_expenses_related_job", table_name="expenses")
    op.drop_index("ix_expenses_team", table_name="expenses")
    op.drop_index("ix_expenses_paid_by_staff", table_name="expenses")
    op.drop_index("ix_expenses_business_category_date", table_name="expenses")
    op.drop_index("ix_expenses_business_status_date", table_name="expenses")
    op.drop_index("ix_expenses_business_date", table_name="expenses")
    op.drop_table("expenses")
