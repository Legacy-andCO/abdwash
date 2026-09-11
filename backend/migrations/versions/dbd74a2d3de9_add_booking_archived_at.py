"""add booking archived at

Revision ID: dbd74a2d3de9
Revises: bb30898caab6
Create Date: 2026-09-11 22:23:24.384276
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dbd74a2d3de9"
down_revision: str | None = "bb30898caab6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "archived_at")
