"""Add loyalty ledger, reward reservations, and cash tender accounting.

Revision ID: 7d3f2a9c8e41
Revises: 80826dfc3c2d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d3f2a9c8e41"
down_revision: str | None = "80826dfc3c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_settings",
        sa.Column("loyalty_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "business_settings",
        sa.Column("loyalty_required_washes", sa.Integer(), server_default="9", nullable=False),
    )
    op.add_column(
        "business_settings", sa.Column("loyalty_reward_service_id", sa.Uuid(), nullable=True)
    )
    op.create_check_constraint(
        "positive_loyalty_required_washes",
        "business_settings",
        "loyalty_required_washes > 0",
    )
    op.create_foreign_key(
        "fk_business_settings_loyalty_reward_service",
        "business_settings",
        "services",
        ["loyalty_reward_service_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # A deterministic backfill is safe only where one active service exists. Businesses
    # with multiple services must explicitly choose the reward service after deployment.
    op.execute(
        """
        UPDATE business_settings AS settings
        SET loyalty_reward_service_id = candidate.service_id
        FROM (
            SELECT business_id, min(id::text)::uuid AS service_id
            FROM services
            WHERE is_active IS TRUE
            GROUP BY business_id
            HAVING count(*) = 1
        ) AS candidate
        WHERE settings.business_id = candidate.business_id
          AND settings.loyalty_reward_service_id IS NULL
        """
    )

    op.add_column(
        "business_sync_revisions",
        sa.Column("customers_revision", sa.BigInteger(), server_default="0", nullable=False),
    )

    op.create_table(
        "loyalty_rewards",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("customer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("reward_service_id", sa.Uuid(), nullable=False),
        sa.Column("reward_service_name", sa.String(length=160), nullable=False),
        sa.Column("reward_list_price_minor", sa.Integer(), nullable=False),
        sa.Column("required_washes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reserved_booking_id", sa.Uuid(), nullable=True),
        sa.Column("reserved_booking_service_id", sa.Uuid(), nullable=True),
        sa.Column("redeemed_job_id", sa.Uuid(), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('available','reserved','redeemed')", name="loyalty_reward_status"
        ),
        sa.CheckConstraint("reward_list_price_minor >= 0", name="nonnegative_reward_list_price"),
        sa.CheckConstraint("required_washes > 0", name="positive_reward_required_washes"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_profile_id"], ["customer_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reward_service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["reserved_booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["reserved_booking_service_id"], ["booking_services.id"]),
        sa.ForeignKeyConstraint(["redeemed_job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reserved_booking_service_id"),
    )
    op.create_index(
        "ix_loyalty_rewards_business_customer_status",
        "loyalty_rewards",
        ["business_id", "customer_profile_id", "status"],
    )

    op.add_column("booking_services", sa.Column("list_price_minor", sa.Integer(), nullable=True))
    op.execute("UPDATE booking_services SET list_price_minor = unit_price_minor")
    op.alter_column("booking_services", "list_price_minor", nullable=False)
    op.add_column(
        "booking_services",
        sa.Column("discount_minor", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "booking_services", sa.Column("discount_type", sa.String(length=30), nullable=True)
    )
    op.add_column("booking_services", sa.Column("loyalty_reward_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        "nonnegative_booking_service_list_price", "booking_services", "list_price_minor >= 0"
    )
    op.create_check_constraint(
        "nonnegative_booking_service_discount", "booking_services", "discount_minor >= 0"
    )
    op.create_check_constraint(
        "booking_service_discount_within_list_price",
        "booking_services",
        "discount_minor <= list_price_minor * quantity",
    )
    op.create_check_constraint(
        "booking_service_discount_type",
        "booking_services",
        "discount_type IS NULL OR discount_type = 'loyalty_reward'",
    )
    op.create_foreign_key(
        "fk_booking_services_loyalty_reward",
        "booking_services",
        "loyalty_rewards",
        ["loyalty_reward_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "loyalty_events",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("customer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("booking_vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("reward_id", sa.Uuid(), nullable=True),
        sa.Column("actor_staff_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('qualifying_wash','manual_credit','manual_debit',"
            "'reward_earned','reward_reserved','reward_released','reward_redeemed')",
            name="loyalty_event_type",
        ),
        sa.CheckConstraint(
            "(event_type = 'manual_debit' AND quantity < 0) OR "
            "(event_type IN ('qualifying_wash','manual_credit') AND quantity > 0) OR "
            "(event_type LIKE 'reward_%' AND quantity = 0)",
            name="loyalty_event_quantity",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_profile_id"], ["customer_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["booking_vehicle_id"], ["booking_vehicles.id"]),
        sa.ForeignKeyConstraint(["reward_id"], ["loyalty_rewards.id"]),
        sa.ForeignKeyConstraint(["actor_staff_id"], ["staff_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "source_key", name="uq_loyalty_event_source"),
    )
    op.create_index(
        "ix_loyalty_events_business_customer_created",
        "loyalty_events",
        ["business_id", "customer_profile_id", "created_at"],
    )

    op.add_column("payment_transactions", sa.Column("actor_staff_id", sa.Uuid(), nullable=True))
    op.add_column(
        "payment_transactions", sa.Column("client_event_id", sa.String(length=160), nullable=True)
    )
    op.create_foreign_key(
        "fk_payment_transactions_actor_staff",
        "payment_transactions",
        "staff_profiles",
        ["actor_staff_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_payment_transaction_event",
        "payment_transactions",
        ["payment_id", "client_event_id"],
    )
    op.add_column(
        "payment_transactions", sa.Column("cash_tendered_minor", sa.Integer(), nullable=True)
    )
    op.add_column(
        "payment_transactions", sa.Column("cash_change_minor", sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        "cash_tender_fields_together",
        "payment_transactions",
        "(cash_tendered_minor IS NULL AND cash_change_minor IS NULL) OR "
        "(cash_tendered_minor IS NOT NULL AND cash_change_minor IS NOT NULL)",
    )
    op.create_check_constraint(
        "cash_tender_covers_payment",
        "payment_transactions",
        "cash_tendered_minor IS NULL OR cash_tendered_minor >= amount_minor",
    )
    op.create_check_constraint(
        "nonnegative_cash_change",
        "payment_transactions",
        "cash_change_minor IS NULL OR cash_change_minor >= 0",
    )
    op.create_check_constraint(
        "cash_change_matches_tender",
        "payment_transactions",
        "cash_tendered_minor IS NULL OR cash_change_minor = cash_tendered_minor - amount_minor",
    )

    op.create_index(
        "ix_customer_profiles_business_name_search",
        "customer_profiles",
        ["business_id", sa.text("lower(first_name)"), sa.text("lower(surname)")],
    )
    op.create_index(
        "ix_vehicles_customer_plate_search",
        "vehicles",
        ["customer_id", sa.text("lower(plate_number)")],
    )
    for table in ("loyalty_rewards", "loyalty_events"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_vehicles_customer_plate_search", table_name="vehicles")
    op.drop_index("ix_customer_profiles_business_name_search", table_name="customer_profiles")
    for name in (
        "cash_change_matches_tender",
        "nonnegative_cash_change",
        "cash_tender_covers_payment",
        "cash_tender_fields_together",
    ):
        op.drop_constraint(name, "payment_transactions", type_="check")
    op.drop_column("payment_transactions", "cash_change_minor")
    op.drop_column("payment_transactions", "cash_tendered_minor")
    op.drop_constraint("uq_payment_transaction_event", "payment_transactions", type_="unique")
    op.drop_constraint(
        "fk_payment_transactions_actor_staff", "payment_transactions", type_="foreignkey"
    )
    op.drop_column("payment_transactions", "client_event_id")
    op.drop_column("payment_transactions", "actor_staff_id")
    op.drop_index("ix_loyalty_events_business_customer_created", table_name="loyalty_events")
    op.drop_table("loyalty_events")
    op.drop_constraint("fk_booking_services_loyalty_reward", "booking_services", type_="foreignkey")
    for name in (
        "booking_service_discount_type",
        "booking_service_discount_within_list_price",
        "nonnegative_booking_service_discount",
        "nonnegative_booking_service_list_price",
    ):
        op.drop_constraint(name, "booking_services", type_="check")
    op.drop_column("booking_services", "loyalty_reward_id")
    op.drop_column("booking_services", "discount_type")
    op.drop_column("booking_services", "discount_minor")
    op.drop_column("booking_services", "list_price_minor")
    op.drop_index("ix_loyalty_rewards_business_customer_status", table_name="loyalty_rewards")
    op.drop_table("loyalty_rewards")
    op.drop_column("business_sync_revisions", "customers_revision")
    op.drop_constraint(
        "fk_business_settings_loyalty_reward_service", "business_settings", type_="foreignkey"
    )
    op.drop_constraint("positive_loyalty_required_washes", "business_settings", type_="check")
    op.drop_column("business_settings", "loyalty_reward_service_id")
    op.drop_column("business_settings", "loyalty_required_washes")
    op.drop_column("business_settings", "loyalty_enabled")
