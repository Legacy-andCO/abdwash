"""add operations management v2

Revision ID: 96493956784a
Revises: ebd1ffb1e908
Create Date: 2026-08-24 22:55:11.893550
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "96493956784a"
down_revision: str | None = "ebd1ffb1e908"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_settings",
        sa.Column(
            "attendance_grace_minutes",
            sa.Integer(),
            server_default=sa.text("5"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "nonnegative_attendance_grace",
        "business_settings",
        "attendance_grace_minutes >= 0",
    )
    op.add_column("staff_profiles", sa.Column("phone", sa.String(length=40)))

    op.create_table(
        "team_memberships",
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("staff_profile_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["schedule_resources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"], ["staff_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_id",
            "staff_profile_id",
            name="uq_team_membership_resource_staff",
        ),
    )
    op.create_index(
        "ix_team_memberships_staff_active",
        "team_memberships",
        ["staff_profile_id", "is_active"],
    )

    op.create_table(
        "attendance_sessions",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("staff_profile_id", sa.Uuid(), nullable=False),
        sa.Column("clock_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out_at", sa.DateTime(timezone=True)),
        sa.Column("clock_in_client_timestamp", sa.DateTime(timezone=True)),
        sa.Column("clock_out_client_timestamp", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "clock_out_at IS NULL OR clock_out_at >= clock_in_at",
            name="attendance_chronological",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"], ["staff_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attendance_business_clock_in",
        "attendance_sessions",
        ["business_id", "clock_in_at"],
    )
    op.create_index(
        "uq_attendance_open_staff",
        "attendance_sessions",
        ["staff_profile_id"],
        unique=True,
        postgresql_where=sa.text("clock_out_at IS NULL"),
    )

    op.create_table(
        "shifts",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("end_time > start_time", name="shift_time_order"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_shift_business_name"),
    )

    op.create_table(
        "staff_shift_assignments",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("staff_profile_id", sa.Uuid(), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["schedule_resources.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"], ["staff_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "staff_profile_id", "work_date", name="uq_staff_shift_work_date"
        ),
    )
    op.create_index(
        "ix_shift_assignments_business_date",
        "staff_shift_assignments",
        ["business_id", "work_date"],
    )

    op.create_table(
        "leave_requests",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("staff_profile_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by_staff_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name="leave_date_order"),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="leave_status",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"], ["staff_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_leave_business_status_dates",
        "leave_requests",
        ["business_id", "status", "start_date"],
    )
    op.create_index(
        "ix_leave_staff_dates",
        "leave_requests",
        ["staff_profile_id", "start_date", "end_date"],
    )

    op.add_column("jobs", sa.Column("assigned_resource_id", sa.Uuid()))
    op.create_foreign_key(
        "jobs_assigned_resource_id_schedule_resources",
        "jobs",
        "schedule_resources",
        ["assigned_resource_id"],
        ["id"],
    )
    op.execute(
        "UPDATE jobs SET assigned_resource_id = bookings.resource_id "
        "FROM bookings WHERE jobs.booking_id = bookings.id"
    )
    op.create_index(
        "ix_jobs_resource_schedule",
        "jobs",
        ["assigned_resource_id", "scheduled_start"],
    )

    for table in (
        "team_memberships",
        "attendance_sessions",
        "shifts",
        "staff_shift_assignments",
        "leave_requests",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_jobs_resource_schedule", table_name="jobs")
    op.drop_constraint(
        "jobs_assigned_resource_id_schedule_resources", "jobs", type_="foreignkey"
    )
    op.drop_column("jobs", "assigned_resource_id")
    op.drop_index("ix_leave_staff_dates", table_name="leave_requests")
    op.drop_index("ix_leave_business_status_dates", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index(
        "ix_shift_assignments_business_date", table_name="staff_shift_assignments"
    )
    op.drop_table("staff_shift_assignments")
    op.drop_table("shifts")
    op.drop_index("uq_attendance_open_staff", table_name="attendance_sessions")
    op.drop_index("ix_attendance_business_clock_in", table_name="attendance_sessions")
    op.drop_table("attendance_sessions")
    op.drop_index("ix_team_memberships_staff_active", table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_column("staff_profiles", "phone")
    op.drop_constraint(
        "nonnegative_attendance_grace", "business_settings", type_="check"
    )
    op.drop_column("business_settings", "attendance_grace_minutes")
