"""Add vehicle-specific consumption rates and snapshot the booked category."""

from alembic import op

revision = "d38bf74a923c"
down_revision = "4c2630a391be"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.service_inventory_templates
            ADD COLUMN vehicle_type varchar(80) NOT NULL DEFAULT 'all',
            DROP CONSTRAINT uq_service_inventory_template_item,
            DROP CONSTRAINT ck_service_inventory_templates_service_inventory_templa_655c,
            ADD CONSTRAINT uq_service_inventory_template_vehicle
                UNIQUE (service_id, inventory_item_id, vehicle_type),
            ADD CONSTRAINT ck_service_inventory_templates_vehicle_type CHECK (
                vehicle_type IN ('all','sedan','suv','hatchback','coupe','pickup','van','other')
            ),
            ADD CONSTRAINT ck_service_inventory_templates_valid_quantity CHECK (
                expected_quantity >= 0 AND expected_quantity <> 'NaN'::numeric
                AND (vehicle_type <> 'all' OR expected_quantity > 0)
            )
    """)
    op.execute("""
        ALTER TABLE public.job_inventory_consumption_lines
            ADD COLUMN vehicle_type_snapshot varchar(80),
            DROP CONSTRAINT ck_job_inventory_consumption_lines_job_inventory_line_p_4c3e,
            ADD CONSTRAINT ck_job_inventory_consumption_lines_expected_quantity CHECK (
                expected_quantity >= 0 AND expected_quantity <> 'NaN'::numeric
            )
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM public.service_inventory_templates WHERE vehicle_type <> 'all')
                OR EXISTS (SELECT 1 FROM public.job_inventory_consumption_lines
                           WHERE vehicle_type_snapshot IS NOT NULL) THEN
                RAISE EXCEPTION 'Downgrade would discard vehicle consumption history or rules';
            END IF;
        END $$
    """)
    op.execute("""
        ALTER TABLE public.job_inventory_consumption_lines
            DROP CONSTRAINT ck_job_inventory_consumption_lines_expected_quantity,
            DROP COLUMN vehicle_type_snapshot,
            ADD CONSTRAINT ck_job_inventory_consumption_lines_job_inventory_line_p_4c3e
                CHECK (expected_quantity > 0)
    """)
    op.execute("""
        ALTER TABLE public.service_inventory_templates
            DROP CONSTRAINT uq_service_inventory_template_vehicle,
            DROP CONSTRAINT ck_service_inventory_templates_vehicle_type,
            DROP CONSTRAINT ck_service_inventory_templates_valid_quantity,
            DROP COLUMN vehicle_type,
            ADD CONSTRAINT uq_service_inventory_template_item
                UNIQUE (service_id, inventory_item_id),
            ADD CONSTRAINT ck_service_inventory_templates_service_inventory_templa_655c
                CHECK (expected_quantity > 0)
    """)
