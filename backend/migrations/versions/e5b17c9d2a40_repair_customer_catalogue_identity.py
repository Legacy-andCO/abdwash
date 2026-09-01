"""Repair customer-facing catalogue and loyalty service identity.

Revision ID: e5b17c9d2a40
Revises: d4a9e7c31f26
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b17c9d2a40"
down_revision: str | None = "d4a9e7c31f26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            WITH service_pairs AS (
                SELECT obsolete.business_id,
                       obsolete.id AS obsolete_id,
                       standard.id AS standard_id
                FROM services AS obsolete
                JOIN services AS standard
                  ON standard.business_id = obsolete.business_id
                 AND standard.name = 'Standard Wash'
                WHERE obsolete.name = 'Development Standard Wash'
            )
            UPDATE business_settings AS settings
               SET loyalty_reward_service_id = pairs.standard_id
              FROM service_pairs AS pairs
             WHERE settings.business_id = pairs.business_id
               AND settings.loyalty_reward_service_id = pairs.obsolete_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            WITH service_pairs AS (
                SELECT obsolete.business_id,
                       obsolete.id AS obsolete_id,
                       standard.id AS standard_id
                FROM services AS obsolete
                JOIN services AS standard
                  ON standard.business_id = obsolete.business_id
                 AND standard.name = 'Standard Wash'
                WHERE obsolete.name = 'Development Standard Wash'
            )
            UPDATE loyalty_rewards AS rewards
               SET reward_service_id = pairs.standard_id,
                   reward_service_name = 'Standard Wash'
             FROM service_pairs AS pairs
             WHERE rewards.business_id = pairs.business_id
               AND (
                   rewards.reward_service_id = pairs.obsolete_id
                   OR (
                       rewards.reward_service_id = pairs.standard_id
                       AND rewards.reward_service_name = 'Development Standard Wash'
                   )
               )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE services
               SET included_features = replace(
                   included_features::text,
                   '"Protective Plastic Covers for Mat, Steering Wheel & Seats"',
                   '"Protective Plastic Covers for Mat & Steering Wheel"'
               )::json
             WHERE name = 'Premium Wash'
               AND included_features::jsonb
                   ? 'Protective Plastic Covers for Mat, Steering Wheel & Seats'
               AND NOT included_features::jsonb
                   ? 'Protective Plastic Covers for Mat & Steering Wheel'
            """
        )
    )


def downgrade() -> None:
    # The previous values were obsolete customer data and cannot be restored safely.
    pass
