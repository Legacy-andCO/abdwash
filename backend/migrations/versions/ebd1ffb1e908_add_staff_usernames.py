"""add staff usernames

Revision ID: ebd1ffb1e908
Revises: d8cc0a1bf349
Create Date: 2026-08-24 22:16:38.887823
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ebd1ffb1e908"
down_revision: str | None = "d8cc0a1bf349"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("staff_profiles", sa.Column("username", sa.String(length=80)))
    op.execute(
        "UPDATE staff_profiles "
        "SET username = 'staff-' || lower(auth_user_id::text) "
        "WHERE username IS NULL"
    )
    op.alter_column("staff_profiles", "username", nullable=False)
    op.create_check_constraint(
        "staff_username_lowercase", "staff_profiles", "username = lower(username)"
    )
    op.create_index(
        "uq_staff_profiles_username_ci",
        "staff_profiles",
        [sa.text("lower(username)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_staff_profiles_username_ci", table_name="staff_profiles")
    op.drop_constraint("staff_username_lowercase", "staff_profiles", type_="check")
    op.drop_column("staff_profiles", "username")
