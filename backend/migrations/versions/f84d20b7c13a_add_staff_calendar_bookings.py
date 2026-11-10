"""Support staff-created bookings and displaced appointments."""

import sqlalchemy as sa
from alembic import op

revision = "f84d20b7c13a"
down_revision = "ed0f361bae21"
branch_labels = None
depends_on = None

BOOKING_STATES = "'pending_payment','confirmed','cancellation_requested','cancelled','completed'"
JOB_STATES = "'unassigned','assigned','en_route','arrived','in_progress','completed','cancelled'"


def _replace_constraints(*, include_displaced: bool) -> None:
    suffix = ",'rescheduling_required'" if include_displaced else ""
    for table, name, states in (
        ("bookings", "ck_bookings_booking_status", BOOKING_STATES),
        ("jobs", "ck_jobs_job_status", JOB_STATES),
    ):
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"status IN ({states}{suffix})")


def upgrade() -> None:
    op.add_column("bookings", sa.Column("created_by_staff_id", sa.Uuid()))
    op.create_foreign_key(
        op.f("fk_bookings_created_by_staff_id_staff_profiles"),
        "bookings",
        "staff_profiles",
        ["created_by_staff_id"],
        ["id"],
    )
    op.add_column(
        "bookings",
        sa.Column(
            "reschedule_payment_review_required",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    _replace_constraints(include_displaced=True)


def downgrade() -> None:
    op.execute(
        """
        DO $guard$
        BEGIN
          IF EXISTS (SELECT FROM bookings WHERE status = 'rescheduling_required'
                     OR created_by_staff_id IS NOT NULL OR reschedule_payment_review_required)
             OR EXISTS (SELECT FROM jobs WHERE status = 'rescheduling_required') THEN
            RAISE EXCEPTION 'Resolve and archive staff calendar records before downgrading';
          END IF;
        END
        $guard$;
        """
    )
    _replace_constraints(include_displaced=False)
    op.drop_column("bookings", "reschedule_payment_review_required")
    op.drop_column("bookings", "created_by_staff_id")
