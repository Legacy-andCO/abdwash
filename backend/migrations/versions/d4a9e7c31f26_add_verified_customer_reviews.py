"""add verified customer reviews and account-deletion guard

Revision ID: d4a9e7c31f26
Revises: c6c7c3026e63
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a9e7c31f26"
down_revision: str | None = "c6c7c3026e63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deleted_customer_identities",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("auth_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auth_user_id", name="uq_deleted_customer_identity_auth_user"),
    )
    op.create_table(
        "customer_reviews",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("customer_profile_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="published", nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("guest_device_id_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="customer_review_rating"),
        sa.CheckConstraint("status IN ('published','hidden')", name="customer_review_status"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_profile_id"], ["customer_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", name="uq_customer_reviews_booking"),
    )
    op.create_index(
        "ix_customer_reviews_business_status_published",
        "customer_reviews",
        ["business_id", "status", "published_at"],
    )
    op.create_index(
        "ix_customer_reviews_customer_profile",
        "customer_reviews",
        ["customer_profile_id"],
    )
    op.create_index(
        "ix_customer_reviews_business_rating",
        "customer_reviews",
        ["business_id", "rating"],
    )
    op.create_table(
        "customer_review_prompt_states",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("customer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("opens_since_last_prompt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_prompt_after", sa.Integer(), nullable=False),
        sa.Column("last_prompted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("opens_since_last_prompt >= 0", name="nonnegative_review_prompt_opens"),
        sa.CheckConstraint("next_prompt_after BETWEEN 1 AND 3", name="review_prompt_threshold"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_profile_id"], ["customer_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_profile_id", name="uq_customer_review_prompt_customer"
        ),
    )
    op.create_index(
        "ix_review_prompt_business_customer",
        "customer_review_prompt_states",
        ["business_id", "customer_profile_id"],
    )
    op.create_table(
        "guest_review_verification_attempts",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("challenge_hash", sa.String(length=64), nullable=False),
        sa.Column("device_id_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("attempt_count >= 0", name="nonnegative_guest_review_attempts"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "challenge_hash",
            "device_id_hash",
            name="uq_guest_review_verification_challenge_device",
        ),
    )
    op.create_index(
        "ix_guest_review_attempt_window",
        "guest_review_verification_attempts",
        ["business_id", "window_started_at"],
    )
    for table in (
        "deleted_customer_identities",
        "customer_reviews",
        "customer_review_prompt_states",
        "guest_review_verification_attempts",
    ):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_guest_review_attempt_window", table_name="guest_review_verification_attempts")
    op.drop_table("guest_review_verification_attempts")
    op.drop_index("ix_review_prompt_business_customer", table_name="customer_review_prompt_states")
    op.drop_table("customer_review_prompt_states")
    op.drop_index("ix_customer_reviews_business_rating", table_name="customer_reviews")
    op.drop_index("ix_customer_reviews_customer_profile", table_name="customer_reviews")
    op.drop_index("ix_customer_reviews_business_status_published", table_name="customer_reviews")
    op.drop_table("customer_reviews")
    op.drop_table("deleted_customer_identities")
