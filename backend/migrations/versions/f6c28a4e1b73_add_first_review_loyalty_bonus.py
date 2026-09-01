"""Add the one-time first-review loyalty bonus event.

Revision ID: f6c28a4e1b73
Revises: e5b17c9d2a40
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6c28a4e1b73"
down_revision: str | None = "e5b17c9d2a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("loyalty_event_type", "loyalty_events", type_="check")
    op.drop_constraint("loyalty_event_quantity", "loyalty_events", type_="check")
    op.create_check_constraint(
        "loyalty_event_type",
        "loyalty_events",
        "event_type IN ('qualifying_wash','first_review_bonus','manual_credit',"
        "'manual_debit','reward_earned','reward_reserved','reward_released',"
        "'reward_redeemed')",
    )
    op.create_check_constraint(
        "loyalty_event_quantity",
        "loyalty_events",
        "(event_type = 'manual_debit' AND quantity < 0) OR "
        "(event_type IN ('qualifying_wash','first_review_bonus','manual_credit') "
        "AND quantity > 0) OR "
        "(event_type LIKE 'reward_%' AND quantity = 0)",
    )
    op.create_index(
        "uq_loyalty_first_review_bonus_customer",
        "loyalty_events",
        ["business_id", "customer_profile_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'first_review_bonus'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_loyalty_first_review_bonus_customer",
        table_name="loyalty_events",
    )
    op.drop_constraint("loyalty_event_quantity", "loyalty_events", type_="check")
    op.drop_constraint("loyalty_event_type", "loyalty_events", type_="check")
    op.execute("DELETE FROM loyalty_events WHERE event_type = 'first_review_bonus'")
    op.create_check_constraint(
        "loyalty_event_quantity",
        "loyalty_events",
        "(event_type = 'manual_debit' AND quantity < 0) OR "
        "(event_type IN ('qualifying_wash','manual_credit') AND quantity > 0) OR "
        "(event_type LIKE 'reward_%' AND quantity = 0)",
    )
    op.create_check_constraint(
        "loyalty_event_type",
        "loyalty_events",
        "event_type IN ('qualifying_wash','manual_credit','manual_debit',"
        "'reward_earned','reward_reserved','reward_released','reward_redeemed')",
    )
