"""startup inventory and notification dedupe

Revision ID: 61343828bd05
Revises: b91c2d7e4f60
Create Date: 2026-08-29 19:49:24.626348
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "61343828bd05"
down_revision: str | None = "b91c2d7e4f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "job_inventory_source_resolution",
        "job_inventory_consumption_runs",
        type_="check",
    )
    op.create_check_constraint(
        "job_inventory_source_resolution",
        "job_inventory_consumption_runs",
        "source_resolution IN ('explicit_usage','van','mobile_team','shop_main',"
        "'business_default','single_location','main_default','not_required',"
        "'unresolved','ambiguous')",
    )
    op.add_column(
        "business_settings",
        sa.Column("default_inventory_location_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_business_settings_default_inventory_location",
        "business_settings",
        "inventory_locations",
        ["default_inventory_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_business_settings_default_inventory_location",
        "business_settings",
        ["default_inventory_location_id"],
    )
    op.execute(
        """
        UPDATE business_settings AS settings
        SET default_inventory_location_id = candidates.location_id
        FROM (
          SELECT business_id, min(id::text)::uuid AS location_id
          FROM inventory_locations
          WHERE is_active IS TRUE
          GROUP BY business_id
          HAVING count(*) = 1
        ) AS candidates
        WHERE candidates.business_id = settings.business_id
          AND settings.default_inventory_location_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE business_settings AS settings
        SET default_inventory_location_id = candidates.location_id
        FROM (
          SELECT business_id, min(id::text)::uuid AS location_id
          FROM inventory_locations
          WHERE is_active IS TRUE AND location_type = 'main'
          GROUP BY business_id
          HAVING count(*) = 1
        ) AS candidates
        WHERE candidates.business_id = settings.business_id
          AND settings.default_inventory_location_id IS NULL
        """
    )

    op.add_column(
        "notification_outbox",
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "uq_notification_outbox_business_dedupe",
        "notification_outbox",
        ["business_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notification_outbox_business_dedupe",
        table_name="notification_outbox",
    )
    op.drop_column("notification_outbox", "dedupe_key")
    op.drop_index(
        "ix_business_settings_default_inventory_location",
        table_name="business_settings",
    )
    op.drop_constraint(
        "fk_business_settings_default_inventory_location",
        "business_settings",
        type_="foreignkey",
    )
    op.drop_column("business_settings", "default_inventory_location_id")
    op.drop_constraint(
        "job_inventory_source_resolution",
        "job_inventory_consumption_runs",
        type_="check",
    )
    op.create_check_constraint(
        "job_inventory_source_resolution",
        "job_inventory_consumption_runs",
        "source_resolution IN ('explicit_usage','van','mobile_team','shop_main',"
        "'not_required','unresolved','ambiguous')",
    )
