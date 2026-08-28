"""add service catalogue management

Revision ID: 9d5f551c26e5
Revises: 5e2c8f7a1b4d
Create Date: 2026-08-28 19:17:57.653331
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d5f551c26e5"
down_revision: str | None = "5e2c8f7a1b4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("mobile_available", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "services", sa.Column("shop_available", sa.Boolean(), server_default="true", nullable=False)
    )
    op.execute(
        "UPDATE services SET estimated_duration_minutes = 120 "
        "WHERE estimated_duration_minutes < 15 OR estimated_duration_minutes > 1440"
    )
    op.create_check_constraint(
        "valid_service_duration",
        "services",
        "estimated_duration_minutes BETWEEN 15 AND 1440",
    )

    op.create_table(
        "service_prices",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_type", sa.String(80), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("price_minor >= 0", name="nonnegative_service_vehicle_price"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "vehicle_type", name="uq_service_price_vehicle_type"),
    )
    op.create_index(
        "ix_service_prices_business_service", "service_prices", ["business_id", "service_id"]
    )
    op.execute(
        """
        INSERT INTO service_prices (
            id, business_id, service_id, vehicle_type, price_minor, created_at, updated_at
        )
        SELECT gen_random_uuid(), service.business_id, service.id, vehicle_type.name,
               service.price_minor, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM services service
        CROSS JOIN (VALUES
            ('sedan'), ('suv'), ('hatchback'), ('coupe'), ('pickup'), ('van'), ('other')
        ) AS vehicle_type(name)
        """
    )

    op.add_column("service_addons", sa.Column("business_id", sa.Uuid(), nullable=True))
    op.add_column("service_addons", sa.Column("description", sa.Text()))
    op.add_column(
        "service_addons",
        sa.Column("default_duration_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "service_addons",
        sa.Column("mobile_available", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "service_addons",
        sa.Column("shop_available", sa.Boolean(), server_default="true", nullable=False),
    )
    op.execute(
        "UPDATE service_addons addon SET business_id = service.business_id "
        "FROM services service WHERE service.id = addon.service_id"
    )
    op.alter_column("service_addons", "business_id", nullable=False)
    op.create_foreign_key(
        "fk_service_addons_business_id_businesses",
        "service_addons",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "valid_addon_duration",
        "service_addons",
        "default_duration_minutes BETWEEN 0 AND 1440",
    )
    op.create_index(
        "ix_service_addons_business_service", "service_addons", ["business_id", "service_id"]
    )

    op.add_column(
        "booking_services", sa.Column("expected_duration_minutes", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE booking_services snapshot
        SET expected_duration_minutes = service.estimated_duration_minutes
        FROM services service
        WHERE service.id = snapshot.service_id
        """
    )
    op.execute(
        "UPDATE booking_services SET expected_duration_minutes = 120 "
        "WHERE expected_duration_minutes IS NULL"
    )
    op.alter_column("booking_services", "expected_duration_minutes", nullable=False)
    op.create_check_constraint(
        "valid_booking_service_duration",
        "booking_services",
        "expected_duration_minutes BETWEEN 15 AND 1440",
    )

    op.create_table(
        "booking_service_addons",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("booking_vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("service_addon_id", sa.Uuid(), nullable=False),
        sa.Column("addon_name", sa.String(160), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.Column("expected_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("unit_price_minor >= 0", name="nonnegative_booking_addon_price"),
        sa.CheckConstraint(
            "expected_duration_minutes BETWEEN 0 AND 1440", name="valid_booking_addon_duration"
        ),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["booking_vehicle_id"], ["booking_vehicles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["service_addon_id"], ["service_addons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "booking_vehicle_id", "service_addon_id", name="uq_booking_vehicle_service_addon"
        ),
    )
    op.create_index(
        "ix_booking_service_addons_booking",
        "booking_service_addons",
        ["booking_id", "booking_vehicle_id"],
    )

    op.add_column(
        "business_settings",
        sa.Column("mobile_minimum_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "business_settings",
        sa.Column("mobile_minimum_minor", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "business_settings",
        sa.Column(
            "default_team_turnaround_minutes", sa.Integer(), server_default="60", nullable=False
        ),
    )
    op.create_check_constraint(
        "nonnegative_mobile_minimum", "business_settings", "mobile_minimum_minor >= 0"
    )
    op.create_check_constraint(
        "valid_default_team_turnaround",
        "business_settings",
        "default_team_turnaround_minutes BETWEEN 0 AND 480",
    )

    op.create_table(
        "business_operating_hours",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("opening_time", sa.Time()),
        sa.Column("closing_time", sa.Time()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="valid_operating_hour_weekday"),
        sa.CheckConstraint(
            "(is_open IS FALSE) OR (opening_time IS NOT NULL AND closing_time IS NOT NULL "
            "AND closing_time > opening_time)",
            name="valid_operating_hour_window",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "weekday", name="uq_business_operating_hour_weekday"),
    )
    op.create_index(
        "ix_business_operating_hours_business",
        "business_operating_hours",
        ["business_id", "weekday"],
    )
    op.execute(
        """
        INSERT INTO business_operating_hours (
            id, business_id, weekday, is_open, opening_time, closing_time, created_at, updated_at
        )
        SELECT gen_random_uuid(), settings.business_id, weekday.value, TRUE,
               settings.opening_time, settings.closing_time, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM business_settings settings
        CROSS JOIN generate_series(0, 6) AS weekday(value)
        """
    )

    for table in ("service_prices", "business_operating_hours", "booking_service_addons"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_table("business_operating_hours")
    op.drop_constraint("valid_default_team_turnaround", "business_settings", type_="check")
    op.drop_constraint("nonnegative_mobile_minimum", "business_settings", type_="check")
    op.drop_column("business_settings", "default_team_turnaround_minutes")
    op.drop_column("business_settings", "mobile_minimum_minor")
    op.drop_column("business_settings", "mobile_minimum_enabled")
    op.drop_table("booking_service_addons")
    op.drop_constraint("valid_booking_service_duration", "booking_services", type_="check")
    op.drop_column("booking_services", "expected_duration_minutes")
    op.drop_index("ix_service_addons_business_service", table_name="service_addons")
    op.drop_constraint("valid_addon_duration", "service_addons", type_="check")
    op.drop_constraint(
        "fk_service_addons_business_id_businesses", "service_addons", type_="foreignkey"
    )
    op.drop_column("service_addons", "shop_available")
    op.drop_column("service_addons", "mobile_available")
    op.drop_column("service_addons", "default_duration_minutes")
    op.drop_column("service_addons", "description")
    op.drop_column("service_addons", "business_id")
    op.drop_table("service_prices")
    op.drop_constraint("valid_service_duration", "services", type_="check")
    op.drop_column("services", "shop_available")
    op.drop_column("services", "mobile_available")
