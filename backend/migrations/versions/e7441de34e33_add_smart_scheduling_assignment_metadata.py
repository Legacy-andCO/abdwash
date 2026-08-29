"""add smart scheduling assignment metadata

Revision ID: e7441de34e33
Revises: 9d5f551c26e5
Create Date: 2026-08-28 22:18:14.379692
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7441de34e33"
down_revision: str | None = "9d5f551c26e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "slot_hold_groups",
        sa.Column(
            "expected_duration_minutes", sa.Integer(), server_default="120", nullable=True
        ),
    )
    op.execute(
        """
        UPDATE slot_hold_groups
        SET expected_duration_minutes = LEAST(
            2880,
            GREATEST(15, CEIL(EXTRACT(EPOCH FROM (slot_end - slot_start)) / 60)::integer)
        )
        """
    )
    op.alter_column("slot_hold_groups", "expected_duration_minutes", nullable=False)
    op.create_check_constraint(
        "valid_hold_expected_duration",
        "slot_hold_groups",
        "expected_duration_minutes BETWEEN 15 AND 2880",
    )
    op.create_index(
        "ix_hold_groups_resource_window_active",
        "slot_hold_groups",
        ["resource_id", "slot_start", "slot_end"],
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column(
        "jobs",
        sa.Column("expected_duration_minutes", sa.Integer(), server_default="120", nullable=True),
    )
    op.add_column("jobs", sa.Column("assignment_source", sa.String(20)))
    op.add_column("jobs", sa.Column("assigned_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("assigned_by_staff_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_jobs_assigned_by_staff_id_staff_profiles",
        "jobs",
        "staff_profiles",
        ["assigned_by_staff_id"],
        ["id"],
    )
    op.create_index("ix_jobs_assigned_by_staff", "jobs", ["assigned_by_staff_id"])
    op.execute(
        """
        UPDATE jobs AS job
        SET expected_duration_minutes = LEAST(
                2880,
                GREATEST(
                    15,
                    CEIL(
                        EXTRACT(EPOCH FROM (job.scheduled_end - job.scheduled_start)) / 60
                    )::integer,
                    COALESCE((
                        SELECT SUM(service.expected_duration_minutes)
                        FROM booking_services AS service
                        WHERE service.booking_id = job.booking_id
                    ), 0) + COALESCE((
                        SELECT SUM(addon.expected_duration_minutes)
                        FROM booking_service_addons AS addon
                        WHERE addon.booking_id = job.booking_id
                    ), 0)
                )
            ),
            assignment_source = CASE
                WHEN job.assigned_resource_id IS NOT NULL OR job.assigned_staff_id IS NOT NULL
                THEN 'legacy'
                ELSE NULL
            END,
            assigned_at = CASE
                WHEN job.assigned_resource_id IS NOT NULL OR job.assigned_staff_id IS NOT NULL
                THEN job.created_at
                ELSE NULL
            END
        """
    )
    op.alter_column("jobs", "expected_duration_minutes", nullable=False)
    op.create_check_constraint(
        "valid_job_expected_duration",
        "jobs",
        "expected_duration_minutes BETWEEN 15 AND 2880",
    )
    op.create_check_constraint(
        "job_assignment_source",
        "jobs",
        "assignment_source IS NULL OR assignment_source IN ('legacy','auto','manual')",
    )


def downgrade() -> None:
    op.drop_constraint("job_assignment_source", "jobs", type_="check")
    op.drop_constraint("valid_job_expected_duration", "jobs", type_="check")
    op.drop_index("ix_jobs_assigned_by_staff", table_name="jobs")
    op.drop_constraint(
        "fk_jobs_assigned_by_staff_id_staff_profiles", "jobs", type_="foreignkey"
    )
    op.drop_column("jobs", "assigned_by_staff_id")
    op.drop_column("jobs", "assigned_at")
    op.drop_column("jobs", "assignment_source")
    op.drop_column("jobs", "expected_duration_minutes")
    op.drop_index("ix_hold_groups_resource_window_active", table_name="slot_hold_groups")
    op.drop_constraint("valid_hold_expected_duration", "slot_hold_groups", type_="check")
    op.drop_column("slot_hold_groups", "expected_duration_minutes")
