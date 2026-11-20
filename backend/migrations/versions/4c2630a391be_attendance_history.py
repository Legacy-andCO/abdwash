"""Record attendance breaks and durable clock request identifiers."""

from alembic import op

revision = "4c2630a391be"
down_revision = "a19772ea5f12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.attendance_sessions
            ADD COLUMN break_minutes integer,
            ADD COLUMN clock_in_event_id uuid,
            ADD COLUMN clock_out_event_id uuid,
            ADD CONSTRAINT uq_attendance_clock_in_event
                UNIQUE (staff_profile_id, clock_in_event_id),
            ADD CONSTRAINT uq_attendance_clock_out_event
                UNIQUE (staff_profile_id, clock_out_event_id),
            ADD CONSTRAINT ck_attendance_sessions_attendance_valid_break CHECK (
                break_minutes IS NULL OR (
                    break_minutes >= 0 AND clock_out_at IS NOT NULL
                    AND break_minutes * interval '1 minute' <= clock_out_at - clock_in_at
                )
            )
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM public.attendance_sessions
                       WHERE break_minutes IS NOT NULL OR clock_in_event_id IS NOT NULL
                           OR clock_out_event_id IS NOT NULL)
            THEN RAISE EXCEPTION 'Attendance history contains data that requires these columns';
            END IF;
        END $$
    """)
    op.execute("""
        ALTER TABLE public.attendance_sessions
            DROP COLUMN break_minutes,
            DROP COLUMN clock_in_event_id,
            DROP COLUMN clock_out_event_id
    """)
