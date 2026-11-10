"""Add customer complaints and protect policy audit records."""

import sqlalchemy as sa
from alembic import op

revision = "ed0f361bae21"
down_revision = "dbd74a2d3de9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_complaints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("reference", sa.String(36), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(20)),
        sa.Column("booking_reference", sa.String(64)),
        sa.Column("service_date", sa.Date()),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("privacy_version", sa.String(120), nullable=False),
        sa.Column("attachment_paths", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="contact_required"),
    )
    op.create_index(
        "ix_customer_complaints_business_created",
        "customer_complaints",
        ["business_id", "created_at", "id"],
    )
    op.create_table(
        "complaint_rate_windows",
        sa.Column("scope", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_complaint_rate_windows_window_start", "complaint_rate_windows", ["window_start"]
    )
    op.execute("ALTER TABLE customer_complaints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE complaint_rate_windows ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_booking_policy_acceptance
          ON audit_events (entity_id)
          WHERE event_type = 'booking_policies_accepted' AND entity_type = 'booking';
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_booking_policy_audit() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
          IF OLD.event_type IN ('booking_policies_accepted', 'booking_policies_provided_by_staff')
             OR (TG_OP = 'UPDATE' AND NEW.event_type IN
                 ('booking_policies_accepted', 'booking_policies_provided_by_staff')) THEN
            RAISE EXCEPTION 'Booking policy audit entries are append-only';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER booking_policy_audit_append_only
          BEFORE UPDATE OR DELETE ON audit_events
          FOR EACH ROW EXECUTE FUNCTION protect_booking_policy_audit();
        """
    )
    op.execute(
        """
        DO $storage$
        BEGIN
          IF to_regclass('storage.buckets') IS NOT NULL THEN
            INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
            VALUES ('complaint-evidence', 'complaint-evidence', false, 1048576,
                    ARRAY['image/jpeg', 'image/png', 'image/webp'])
            ON CONFLICT (id) DO UPDATE SET public = false,
              file_size_limit = EXCLUDED.file_size_limit,
              allowed_mime_types = EXCLUDED.allowed_mime_types;
            CREATE POLICY complaint_evidence_server_only ON storage.objects
              AS RESTRICTIVE FOR ALL TO anon, authenticated
              USING (bucket_id <> 'complaint-evidence')
              WITH CHECK (bucket_id <> 'complaint-evidence');
          END IF;
        END
        $storage$;
        """
    )


def downgrade() -> None:
    # A populated intake must be archived according to the approved retention process first.
    op.execute(
        """
        DO $guard$
        BEGIN
          IF EXISTS (SELECT FROM customer_complaints) OR EXISTS (
            SELECT FROM audit_events WHERE event_type IN
              ('booking_policies_accepted', 'booking_policies_provided_by_staff')
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade after policy acceptance or complaint intake';
          END IF;
        END
        $guard$;
        """
    )
    op.execute("DROP TRIGGER booking_policy_audit_append_only ON audit_events")
    op.execute("DROP FUNCTION protect_booking_policy_audit()")
    op.drop_index("uq_booking_policy_acceptance", table_name="audit_events")
    op.drop_table("complaint_rate_windows")
    op.drop_table("customer_complaints")
    op.execute(
        """
        DO $storage$
        BEGIN
          IF to_regclass('storage.objects') IS NOT NULL THEN
            DROP POLICY IF EXISTS complaint_evidence_server_only ON storage.objects;
          END IF;
        END
        $storage$;
        """
    )
