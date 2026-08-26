"""add arrived job state

Revision ID: f73b2c96a145
Revises: c52e9d1a40b7
Create Date: 2026-08-25 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f73b2c96a145"
down_revision: str | None = "c52e9d1a40b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("arrived_at", sa.DateTime(timezone=True)))
    op.drop_constraint("job_status", "jobs", type_="check")
    op.create_check_constraint(
        "job_status",
        "jobs",
        "status IN ('unassigned','assigned','en_route','arrived',"
        "'in_progress','completed','cancelled')",
    )


def downgrade() -> None:
    # Restore a state accepted by the previous constraint before narrowing it.
    op.execute("UPDATE jobs SET status = 'en_route', arrived_at = NULL WHERE status = 'arrived'")
    op.drop_constraint("job_status", "jobs", type_="check")
    op.create_check_constraint(
        "job_status",
        "jobs",
        "status IN ('unassigned','assigned','en_route','in_progress','completed','cancelled')",
    )
    op.drop_column("jobs", "arrived_at")
