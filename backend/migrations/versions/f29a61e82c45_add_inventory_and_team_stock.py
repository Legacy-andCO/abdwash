"""add inventory and team stock

Revision ID: f29a61e82c45
Revises: 63973a3319dd
Create Date: 2026-08-28 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f29a61e82c45"
down_revision: str | None = "63973a3319dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ITEM_CATEGORIES = (
    "chemicals",
    "cleaning_products",
    "microfibers_towels",
    "brushes",
    "pads",
    "bottles_sprayers",
    "ppe",
    "disposable_consumables",
    "equipment_consumables",
    "other",
)
UNITS = ("piece", "liter", "milliliter", "kilogram", "gram", "meter", "roll", "box", "pack")


def values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "business_sync_revisions",
        sa.Column("inventory_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.create_table(
        "inventory_items",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("code", sa.String(80)),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "default_low_stock_threshold",
            sa.Numeric(14, 3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            f"category IN ({values(ITEM_CATEGORIES)})", name="inventory_item_category"
        ),
        sa.CheckConstraint(f"unit IN ({values(UNITS)})", name="inventory_item_unit"),
        sa.CheckConstraint(
            "default_low_stock_threshold >= 0", name="inventory_item_nonnegative_threshold"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_items_business_active_name",
        "inventory_items",
        ["business_id", "is_active", "name"],
    )
    op.create_index(
        "ix_inventory_items_business_category", "inventory_items", ["business_id", "category"]
    )
    op.create_index(
        "uq_inventory_items_business_code_ci",
        "inventory_items",
        ["business_id", sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )

    op.create_table(
        "inventory_locations",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("location_type", sa.String(24), nullable=False),
        sa.Column("linked_team_id", sa.Uuid()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "location_type IN ('main','mobile_team','van','other')",
            name="inventory_location_type",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_team_id"], ["schedule_resources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_inventory_location_business_name"),
    )
    op.create_index(
        "ix_inventory_locations_business_active",
        "inventory_locations",
        ["business_id", "is_active", "location_type"],
    )
    op.create_index("ix_inventory_locations_linked_team", "inventory_locations", ["linked_team_id"])
    op.create_index(
        "uq_inventory_locations_active_team",
        "inventory_locations",
        ["linked_team_id"],
        unique=True,
        postgresql_where=sa.text("linked_team_id IS NOT NULL AND is_active IS TRUE"),
    )

    op.create_table(
        "inventory_stock",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("low_stock_threshold", sa.Numeric(14, 3)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity >= 0", name="inventory_stock_nonnegative_quantity"),
        sa.CheckConstraint(
            "low_stock_threshold IS NULL OR low_stock_threshold >= 0",
            name="inventory_stock_nonnegative_threshold",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "inventory_item_id", "location_id", name="uq_inventory_stock_item_location"
        ),
    )
    op.create_index(
        "ix_inventory_stock_business_location",
        "inventory_stock",
        ["business_id", "location_id"],
    )
    op.create_index(
        "ix_inventory_stock_business_item",
        "inventory_stock",
        ["business_id", "inventory_item_id"],
    )

    op.create_table(
        "inventory_operations",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(30), nullable=False),
        sa.Column("client_event_id", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_staff_id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "operation_type IN ('opening_balance','receipt','transfer','usage','wastage',"
            "'stock_count','return')",
            name="inventory_operation_type",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "client_event_id", name="uq_inventory_operation_business_event"
        ),
    )
    op.create_index("ix_inventory_operations_actor", "inventory_operations", ["actor_staff_id"])
    op.create_index("ix_inventory_operations_expense", "inventory_operations", ["expense_id"])

    op.create_table(
        "inventory_movements",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("from_location_id", sa.Uuid()),
        sa.Column("to_location_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("expense_id", sa.Uuid()),
        sa.Column("actor_staff_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("reference_number", sa.String(160)),
        sa.Column("unit_cost_minor", sa.Integer()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="inventory_movement_positive_quantity"),
        sa.CheckConstraint(
            "movement_type IN ('opening_balance','receipt','transfer_out','transfer_in','usage',"
            "'wastage','adjustment_in','adjustment_out','return')",
            name="inventory_movement_type",
        ),
        sa.CheckConstraint(
            "unit_cost_minor IS NULL OR unit_cost_minor >= 0",
            name="inventory_movement_nonnegative_cost",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operation_id"], ["inventory_operations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_location_id"], ["inventory_locations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["to_location_id"], ["inventory_locations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_staff_id"], ["staff_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", "sequence", name="uq_inventory_movement_sequence"),
    )
    op.create_index(
        "ix_inventory_movements_business_created",
        "inventory_movements",
        ["business_id", "created_at", "id"],
    )
    op.create_index(
        "ix_inventory_movements_business_item_created",
        "inventory_movements",
        ["business_id", "inventory_item_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_movements_business_location_created",
        "inventory_movements",
        ["business_id", "location_id", "created_at"],
    )
    for name, columns in (
        ("ix_inventory_movements_operation", ["operation_id"]),
        ("ix_inventory_movements_job_created", ["job_id", "created_at"]),
        ("ix_inventory_movements_actor", ["actor_staff_id"]),
        ("ix_inventory_movements_from_location", ["from_location_id"]),
        ("ix_inventory_movements_to_location", ["to_location_id"]),
        ("ix_inventory_movements_expense", ["expense_id"]),
    ):
        op.create_index(name, "inventory_movements", columns)

    op.create_table(
        "service_inventory_templates",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "expected_quantity > 0", name="service_inventory_template_positive_quantity"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_id", "inventory_item_id", name="uq_service_inventory_template_item"
        ),
    )
    op.create_index(
        "ix_service_inventory_templates_business",
        "service_inventory_templates",
        ["business_id"],
    )
    op.create_index(
        "ix_service_inventory_templates_item",
        "service_inventory_templates",
        ["inventory_item_id"],
    )

    tables = (
        "inventory_items",
        "inventory_locations",
        "inventory_stock",
        "inventory_operations",
        "inventory_movements",
        "service_inventory_templates",
    )
    for table in tables:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_table("service_inventory_templates")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_operations")
    op.drop_table("inventory_stock")
    op.drop_table("inventory_locations")
    op.drop_table("inventory_items")
    op.drop_column("business_sync_revisions", "inventory_revision")
