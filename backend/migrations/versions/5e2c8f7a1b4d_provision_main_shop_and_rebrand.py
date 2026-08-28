"""provision main shop inventory location and Trifecta business name

Revision ID: 5e2c8f7a1b4d
Revises: f29a61e82c45
Create Date: 2026-08-28 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5e2c8f7a1b4d"
down_revision: str | None = "f29a61e82c45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO inventory_locations (
            id,
            business_id,
            name,
            location_type,
            linked_team_id,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            business.id,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM inventory_locations named_location
                    WHERE named_location.business_id = business.id
                      AND lower(named_location.name) = lower('Main Shop')
                ) THEN 'Main Shop (Primary)'
                ELSE 'Main Shop'
            END,
            'main',
            NULL,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM businesses business
        WHERE business.is_active IS TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM inventory_locations main_location
              WHERE main_location.business_id = business.id
                AND main_location.location_type = 'main'
                AND main_location.is_active IS TRUE
          )
        """
    )
    op.execute(
        """
        UPDATE businesses
        SET name = 'Trifecta', updated_at = CURRENT_TIMESTAMP
        WHERE slug = 'abdwash'
          AND lower(name) IN ('abdwash', 'abd wash', 'adb wash')
        """
    )


def downgrade() -> None:
    # This migration provisions operational data. It is intentionally not deleted
    # during downgrade because stock may subsequently reference the location.
    pass
