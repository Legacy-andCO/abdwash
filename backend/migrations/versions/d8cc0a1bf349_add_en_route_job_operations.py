"""add en route job operations

Revision ID: d8cc0a1bf349
Revises: 86770d7ef2e1
Create Date: 2026-08-24 16:50:38.030630
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8cc0a1bf349"
down_revision: str | None = "86770d7ef2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("job_status", "jobs", type_="check")
    op.create_check_constraint(
        "job_status",
        "jobs",
        "status IN ('unassigned','assigned','en_route','in_progress','completed','cancelled')",
    )
    op.add_column("jobs", sa.Column("en_route_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("estimated_arrival_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.execute("UPDATE jobs SET status = 'assigned' WHERE status = 'en_route'")
    op.drop_column("jobs", "estimated_arrival_at")
    op.drop_column("jobs", "en_route_at")
    op.drop_constraint("job_status", "jobs", type_="check")
    op.create_check_constraint(
        "job_status",
        "jobs",
        "status IN ('unassigned','assigned','in_progress','completed','cancelled')",
    )
