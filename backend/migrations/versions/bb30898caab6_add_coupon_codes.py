"""Add business-scoped coupon codes and booking-line snapshots.

Revision ID: bb30898caab6
Revises: f6c28a4e1b73
Create Date: 2026-09-04 13:58:30.691153
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bb30898caab6"
down_revision: str | None = "f6c28a4e1b73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("minimum_vehicle_count", sa.Integer(), nullable=True),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("code ~ '^[A-Z0-9]{3,6}$'", name="coupon_code_format"),
        sa.CheckConstraint(
            "discount_percent BETWEEN 1 AND 100", name="coupon_discount_percent"
        ),
        sa.CheckConstraint(
            "minimum_vehicle_count IS NULL OR minimum_vehicle_count >= 1",
            name="coupon_minimum_vehicle_count",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_staff_id"], ["staff_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_coupon_business_code"),
    )
    op.create_index("ix_coupons_business_active", "coupons", ["business_id", "is_active"])
    op.create_table(
        "coupon_service_eligibility",
        sa.Column("coupon_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("coupon_id", "service_id"),
    )
    op.create_index(
        "ix_coupon_service_eligibility_service",
        "coupon_service_eligibility",
        ["service_id"],
    )
    op.create_table(
        "coupon_vehicle_eligibility",
        sa.Column("coupon_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_type", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "vehicle_type IN ('sedan','suv','hatchback','coupe','pickup','van','other')",
            name="coupon_vehicle_type",
        ),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("coupon_id", "vehicle_type"),
    )
    for table in ("coupons", "coupon_service_eligibility", "coupon_vehicle_eligibility"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM anon, authenticated')

    op.add_column("booking_services", sa.Column("coupon_id", sa.Uuid(), nullable=True))
    op.add_column(
        "booking_services", sa.Column("coupon_code_snapshot", sa.String(length=6), nullable=True)
    )
    op.add_column(
        "booking_services", sa.Column("discount_percent_snapshot", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_booking_services_coupon_id",
        "booking_services",
        "coupons",
        ["coupon_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_booking_services_coupon", "booking_services", ["coupon_id"])
    op.drop_constraint("booking_service_discount_type", "booking_services", type_="check")
    op.create_check_constraint(
        "booking_service_discount_type",
        "booking_services",
        "discount_type IS NULL OR discount_type IN ('loyalty_reward','coupon')",
    )
    op.create_check_constraint(
        "booking_service_discount_source",
        "booking_services",
        "(discount_type IS NULL AND loyalty_reward_id IS NULL AND coupon_id IS NULL "
        "AND coupon_code_snapshot IS NULL AND discount_percent_snapshot IS NULL) OR "
        "(discount_type = 'loyalty_reward' AND loyalty_reward_id IS NOT NULL "
        "AND coupon_id IS NULL AND coupon_code_snapshot IS NULL "
        "AND discount_percent_snapshot IS NULL) OR "
        "(discount_type = 'coupon' AND loyalty_reward_id IS NULL "
        "AND coupon_code_snapshot IS NOT NULL "
        "AND discount_percent_snapshot BETWEEN 1 AND 100)",
    )
    op.create_index(
        "uq_booking_services_booking_coupon",
        "booking_services",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("discount_type = 'coupon'"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_booking_services_booking_coupon")
    op.drop_constraint("booking_service_discount_source", "booking_services", type_="check")
    op.execute(
        "UPDATE booking_services SET discount_type = NULL "
        "WHERE discount_type = 'coupon'"
    )
    op.drop_constraint("booking_service_discount_type", "booking_services", type_="check")
    op.create_check_constraint(
        "booking_service_discount_type",
        "booking_services",
        "discount_type IS NULL OR discount_type = 'loyalty_reward'",
    )
    op.drop_index("ix_booking_services_coupon", table_name="booking_services")
    op.drop_constraint("fk_booking_services_coupon_id", "booking_services", type_="foreignkey")
    op.drop_column("booking_services", "discount_percent_snapshot")
    op.drop_column("booking_services", "coupon_code_snapshot")
    op.drop_column("booking_services", "coupon_id")
    op.drop_table("coupon_vehicle_eligibility")
    op.drop_index(
        "ix_coupon_service_eligibility_service", table_name="coupon_service_eligibility"
    )
    op.drop_table("coupon_service_eligibility")
    op.drop_index("ix_coupons_business_active", table_name="coupons")
    op.drop_table("coupons")
