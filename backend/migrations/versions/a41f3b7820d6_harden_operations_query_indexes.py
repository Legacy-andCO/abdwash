"""Harden Operations V2 query indexes.

Revision ID: a41f3b7820d6
Revises: 96493956784a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a41f3b7820d6"
down_revision: str | None = "96493956784a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_team_memberships_resource_active_staff",
        "team_memberships",
        ["resource_id", "is_active", "staff_profile_id"],
    )
    op.create_index(
        "ix_attendance_staff_clock_in",
        "attendance_sessions",
        ["staff_profile_id", "clock_in_at"],
    )
    op.create_index(
        "ix_booking_services_booking_service",
        "booking_services",
        ["booking_id", "service_id"],
    )
    op.create_index(
        "ix_jobs_business_schedule_status",
        "jobs",
        ["business_id", "scheduled_start", "status"],
    )
    op.create_index(
        "ix_payments_paid_method_date",
        "payments",
        ["status", "method", "paid_at"],
        postgresql_where=sa.text("status = 'paid'"),
    )


def downgrade() -> None:
    op.drop_index("ix_payments_paid_method_date", table_name="payments")
    op.drop_index("ix_jobs_business_schedule_status", table_name="jobs")
    op.drop_index("ix_booking_services_booking_service", table_name="booking_services")
    op.drop_index("ix_attendance_staff_clock_in", table_name="attendance_sessions")
    op.drop_index("ix_team_memberships_resource_active_staff", table_name="team_memberships")
