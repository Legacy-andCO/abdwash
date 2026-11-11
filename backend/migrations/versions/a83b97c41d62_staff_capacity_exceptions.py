"""Allow separately reserved slots for confirmed staff overlaps."""

import sqlalchemy as sa
from alembic import op

revision = "a83b97c41d62"
down_revision = "f84d20b7c13a"
branch_labels = None
depends_on = None

INDEX = "uq_schedule_slot_resource_start"


def upgrade() -> None:
    op.add_column(
        "schedule_slots",
        sa.Column("capacity_exception", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.drop_constraint(INDEX, "schedule_slots", type_="unique")
    op.create_index(
        INDEX,
        "schedule_slots",
        ["resource_id", "slot_start"],
        unique=True,
        postgresql_where=sa.text("NOT capacity_exception"),
    )


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM schedule_slots WHERE capacity_exception) THEN
            RAISE EXCEPTION 'Staff overlap records exist. Use a forward migration.';
          END IF;
        END $$;
    """)
    op.drop_index(INDEX, table_name="schedule_slots")
    op.create_unique_constraint(INDEX, "schedule_slots", ["resource_id", "slot_start"])
    op.drop_column("schedule_slots", "capacity_exception")
