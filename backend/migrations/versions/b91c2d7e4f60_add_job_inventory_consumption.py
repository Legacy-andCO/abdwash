"""add immutable job inventory consumption snapshots

Revision ID: b91c2d7e4f60
Revises: e7441de34e33
Create Date: 2026-08-29 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b91c2d7e4f60"
down_revision: str | None = "e7441de34e33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_inventory_consumption_runs",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_location_id", sa.Uuid()),
        sa.Column("inventory_operation_id", sa.Uuid()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_resolution", sa.String(32), nullable=False),
        sa.Column("issue_code", sa.String(64)),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("has_attention", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_staff_id", sa.Uuid()),
        sa.Column("review_note", sa.Text()),
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
        sa.CheckConstraint(
            "status IN ('no_template','applied','needs_review')",
            name="job_inventory_consumption_status",
        ),
        sa.CheckConstraint(
            "source_resolution IN ('explicit_usage','van','mobile_team','shop_main',"
            "'not_required','unresolved','ambiguous')",
            name="job_inventory_source_resolution",
        ),
        sa.CheckConstraint(
            "(reviewed_at IS NULL AND reviewed_by_staff_id IS NULL) OR "
            "(reviewed_at IS NOT NULL AND reviewed_by_staff_id IS NOT NULL)",
            name="job_inventory_review_state",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_location_id"], ["inventory_locations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_operation_id"], ["inventory_operations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_staff_id"], ["staff_profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_job_inventory_consumption_job"),
        sa.UniqueConstraint(
            "inventory_operation_id", name="uq_job_inventory_consumption_operation"
        ),
    )
    op.create_index(
        "ix_job_inventory_runs_business_attention_reviewed",
        "job_inventory_consumption_runs",
        ["business_id", "has_attention", "reviewed_at", "processed_at"],
    )
    op.create_index(
        "ix_job_inventory_runs_source_location",
        "job_inventory_consumption_runs",
        ["source_location_id"],
    )
    op.create_index(
        "ix_job_inventory_runs_reviewed_by",
        "job_inventory_consumption_runs",
        ["reviewed_by_staff_id"],
    )

    op.create_table(
        "job_inventory_consumption_lines",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("booking_service_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid()),
        sa.Column("service_name_snapshot", sa.String(160), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid()),
        sa.Column("item_name_snapshot", sa.String(160), nullable=False),
        sa.Column("unit_snapshot", sa.String(24), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("automatic_applied_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("preexisting_manual_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("shortfall_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("issue_code", sa.String(64)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("expected_quantity > 0", name="job_inventory_line_positive_expected"),
        sa.CheckConstraint(
            "automatic_applied_quantity >= 0 AND preexisting_manual_quantity >= 0 "
            "AND shortfall_quantity >= 0",
            name="job_inventory_line_nonnegative_quantities",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["job_inventory_consumption_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["booking_service_id"], ["booking_services.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "booking_service_id",
            "inventory_item_id",
            name="uq_job_inventory_line_service_item",
        ),
    )
    op.create_index(
        "ix_job_inventory_lines_business_run",
        "job_inventory_consumption_lines",
        ["business_id", "run_id"],
    )
    op.create_index(
        "ix_job_inventory_lines_item",
        "job_inventory_consumption_lines",
        ["inventory_item_id"],
    )
    op.create_index(
        "ix_job_inventory_lines_booking_service",
        "job_inventory_consumption_lines",
        ["booking_service_id"],
    )

    for table in (
        "job_inventory_consumption_runs",
        "job_inventory_consumption_lines",
    ):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_table("job_inventory_consumption_lines")
    op.drop_table("job_inventory_consumption_runs")
