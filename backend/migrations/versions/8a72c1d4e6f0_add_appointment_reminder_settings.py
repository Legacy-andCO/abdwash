"""add appointment reminder settings

Revision ID: 8a72c1d4e6f0
Revises: 61343828bd05
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a72c1d4e6f0"
down_revision: str | None = "61343828bd05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_settings",
        sa.Column(
            "appointment_reminder_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "business_settings",
        sa.Column(
            "appointment_reminder_hours_before",
            sa.Integer(),
            server_default=sa.text("24"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "valid_appointment_reminder_hours",
        "business_settings",
        "appointment_reminder_hours_before BETWEEN 1 AND 168",
    )


def downgrade() -> None:
    op.drop_constraint(
        "valid_appointment_reminder_hours", "business_settings", type_="check"
    )
    op.drop_column("business_settings", "appointment_reminder_hours_before")
    op.drop_column("business_settings", "appointment_reminder_enabled")
