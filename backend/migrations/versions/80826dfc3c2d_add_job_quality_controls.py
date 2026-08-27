"""add job quality controls

Revision ID: 80826dfc3c2d
Revises: 6409bd6c4eec
Create Date: 2026-08-27 01:05:30.771973
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "80826dfc3c2d"
down_revision: str | None = "6409bd6c4eec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("services", sa.Column("checklist_template", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE services
        SET checklist_template = CASE name
          WHEN 'Express Exterior' THEN
            json_build_array(
              json_build_object('label', 'Exterior wash', 'required', true),
              json_build_object('label', 'Wheels and tyres', 'required', true),
              json_build_object('label', 'Exterior glass', 'required', true),
              json_build_object('label', 'Hand-finished dry', 'required', true),
              json_build_object('label', 'Final inspection', 'required', true)
            )
          WHEN 'Signature Inside & Out' THEN
            json_build_array(
              json_build_object('label', 'Exterior wash', 'required', true),
              json_build_object('label', 'Wheels and tyres', 'required', true),
              json_build_object('label', 'Exterior and interior glass', 'required', true),
              json_build_object('label', 'Interior vacuum', 'required', true),
              json_build_object('label', 'Dashboard and interior wipe', 'required', true),
              json_build_object('label', 'Final inspection', 'required', true)
            )
          WHEN 'Premium Detail' THEN
            json_build_array(
              json_build_object('label', 'Pre-wash inspection', 'required', true),
              json_build_object(
                'label', 'Exterior wash and decontamination', 'required', true
              ),
              json_build_object('label', 'Wheels and tyres', 'required', true),
              json_build_object(
                'label', 'Exterior and interior glass', 'required', true
              ),
              json_build_object('label', 'Interior vacuum', 'required', true),
              json_build_object('label', 'Detailed interior wipe', 'required', true),
              json_build_object('label', 'Finishing treatment', 'required', true),
              json_build_object('label', 'Final inspection', 'required', true)
            )
          ELSE checklist_template
        END
        WHERE name IN ('Express Exterior', 'Signature Inside & Out', 'Premium Detail')
        """
    )
    op.create_table(
        "job_inspections",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column("damage_category", sa.String(length=40), nullable=True),
        sa.Column("damage_notes", sa.Text(), nullable=True),
        sa.Column("completed_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["completed_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_job_inspections_business_job", "job_inspections", ["business_id", "job_id"])
    op.create_table(
        "job_checklist_items",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("booking_service_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_staff_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["booking_service_id"], ["booking_services.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["completed_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "position", name="uq_job_checklist_position"),
    )
    op.create_index(
        "ix_job_checklist_business_job", "job_checklist_items", ["business_id", "job_id"]
    )
    op.create_table(
        "job_photos",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("client_request_id", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "category IN ('before','after','damage','issue')", name="job_photo_category"
        ),
        sa.CheckConstraint("status IN ('pending','ready')", name="job_photo_status"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
        sa.UniqueConstraint(
            "business_id", "client_request_id", name="uq_job_photo_business_request"
        ),
    )
    op.create_index(
        "ix_job_photos_business_job_status",
        "job_photos",
        ["business_id", "job_id", "status"],
    )
    op.create_table(
        "job_quality_issues",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("photo_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["job_photos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_quality_issues_business_job", "job_quality_issues", ["business_id", "job_id"]
    )
    op.create_table(
        "job_complaints",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("original_job_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_staff_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correction_job_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('open','under_review','resolved','rejected','rewash_approved')",
            name="job_complaint_status",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["correction_job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_profiles.id"]),
        sa.ForeignKeyConstraint(["original_job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_staff_id"], ["staff_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correction_job_id"),
    )
    op.create_index(
        "ix_job_complaints_business_job", "job_complaints", ["business_id", "original_job_id"]
    )
    for table in (
        "job_inspections",
        "job_checklist_items",
        "job_photos",
        "job_quality_issues",
        "job_complaints",
    ):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(
        """
        DO $storage$
        BEGIN
          IF to_regclass('storage.buckets') IS NOT NULL THEN
            INSERT INTO storage.buckets (
              id, name, public, file_size_limit, allowed_mime_types
            ) VALUES (
              'job-quality-photos', 'job-quality-photos', false, 8388608,
              ARRAY['image/jpeg', 'image/png', 'image/webp']
            )
            ON CONFLICT (id) DO UPDATE SET
              public = false,
              file_size_limit = EXCLUDED.file_size_limit,
              allowed_mime_types = EXCLUDED.allowed_mime_types;
          END IF;
        END
        $storage$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_job_complaints_business_job", table_name="job_complaints")
    op.drop_table("job_complaints")
    op.drop_index("ix_job_quality_issues_business_job", table_name="job_quality_issues")
    op.drop_table("job_quality_issues")
    op.drop_index("ix_job_photos_business_job_status", table_name="job_photos")
    op.drop_table("job_photos")
    op.drop_index("ix_job_checklist_business_job", table_name="job_checklist_items")
    op.drop_table("job_checklist_items")
    op.drop_index("ix_job_inspections_business_job", table_name="job_inspections")
    op.drop_table("job_inspections")
    op.drop_column("services", "checklist_template")
