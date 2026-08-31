"""add staff password change requirement

Revision ID: 6409bd6c4eec
Revises: f73b2c96a145
Create Date: 2026-08-26 21:28:49.000053
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6409bd6c4eec"
down_revision: str | None = "f73b2c96a145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "staff_profiles",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("staff_profiles", "must_change_password")
