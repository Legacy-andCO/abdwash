"""make booking customer email optional

Revision ID: c6c7c3026e63
Revises: c18f4a7b2d91
Create Date: 2026-08-31 16:21:17.441911
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6c7c3026e63"
down_revision: str | None = "c18f4a7b2d91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "bookings",
        "customer_email",
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM bookings WHERE customer_email IS NULL) THEN
                    RAISE EXCEPTION 'Cannot restore bookings.customer_email NOT NULL '
                        'while null snapshots exist';
                END IF;
            END
            $$
            """
        )
    )
    op.alter_column(
        "bookings",
        "customer_email",
        existing_type=sa.String(length=320),
        nullable=False,
    )
