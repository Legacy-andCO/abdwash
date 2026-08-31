"""Add scoped sync revisions and repair operational assignments.

Revision ID: c52e9d1a40b7
Revises: a41f3b7820d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c52e9d1a40b7"
down_revision: str | None = "a41f3b7820d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_sync_revisions",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("jobs_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("workforce_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("schedule_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("finance_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id"),
    )
    op.execute(
        "INSERT INTO business_sync_revisions (business_id) "
        "SELECT id FROM businesses ON CONFLICT (business_id) DO NOTHING"
    )
    op.execute("ALTER TABLE business_sync_revisions ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        DO $$
        DECLARE
            repaired_resources bigint;
            repaired_statuses bigint;
        BEGIN
            UPDATE jobs
            SET assigned_resource_id = bookings.resource_id
            FROM bookings
            WHERE jobs.booking_id = bookings.id
              AND jobs.status NOT IN ('completed', 'cancelled')
              AND jobs.assigned_resource_id IS NULL
              AND bookings.resource_id IS NOT NULL;
            GET DIAGNOSTICS repaired_resources = ROW_COUNT;

            UPDATE jobs
            SET status = 'assigned'
            WHERE status = 'unassigned'
              AND (assigned_resource_id IS NOT NULL OR assigned_staff_id IS NOT NULL);
            GET DIAGNOSTICS repaired_statuses = ROW_COUNT;

            RAISE NOTICE 'AbdWash assignment repair: resources=%, statuses=%',
                repaired_resources, repaired_statuses;
        END $$;
        """
    )
    op.create_check_constraint(
        "unassigned_jobs_have_no_assignment",
        "jobs",
        "status <> 'unassigned' OR (assigned_resource_id IS NULL AND assigned_staff_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("unassigned_jobs_have_no_assignment", "jobs", type_="check")
    op.drop_table("business_sync_revisions")
