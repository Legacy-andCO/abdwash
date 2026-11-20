"""Payment reviews and amount-based physical handover allocations."""

from alembic import op

revision = "a19772ea5f12"
down_revision = "bb63439e5750"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in """ALTER TABLE payment_transactions
 ADD COLUMN reviewed_by_staff_id uuid REFERENCES staff_profiles(id),
 ADD COLUMN reviewed_at timestamptz,
 ADD COLUMN rejection_reason varchar(500),
 ADD COLUMN screenshot bytea,
 ADD CONSTRAINT payment_screenshot_size CHECK (screenshot IS NULL OR
   (transaction_type = 'card_payment' AND octet_length(screenshot) BETWEEN 1 AND 512000));
INSERT INTO payment_transactions(id, payment_id, transaction_type, status, amount_minor,
 created_at, updated_at, provider_metadata)
SELECT gen_random_uuid(), p.id, 'payment', 'succeeded', p.amount_minor,
       coalesce(p.paid_at,p.updated_at), coalesce(p.paid_at,p.updated_at),
       '{"source":"legacy_paid_header"}'::json
FROM payments p WHERE p.status='paid' AND p.amount_minor>0 AND NOT EXISTS (
 SELECT 1 FROM payment_transactions t WHERE t.payment_id=p.id AND t.status='succeeded'
 AND t.transaction_type IN ('cash_payment','card_payment','capture','charge','payment','deposit')
);
ALTER TABLE cash_reconciliation_payments ADD COLUMN allocated_minor integer;
WITH ordered AS (
 SELECT l.id,t.amount_minor,r.declared_cash_minor,
 coalesce(sum(t.amount_minor) OVER (PARTITION BY r.id ORDER BY t.created_at,t.id
 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) AS prior
 FROM cash_reconciliation_payments l JOIN cash_reconciliations r ON r.id=l.reconciliation_id
 JOIN payment_transactions t ON t.id=l.payment_transaction_id
)
UPDATE cash_reconciliation_payments l SET allocated_minor=
 greatest(0,least(o.amount_minor,o.declared_cash_minor-o.prior))
FROM ordered o WHERE o.id=l.id;
ALTER TABLE cash_reconciliation_payments ALTER COLUMN allocated_minor SET NOT NULL,
 ADD CONSTRAINT ck_cash_reconciliation_payments_cash_allocation_nonnegative
 CHECK (allocated_minor >= 0);
DROP INDEX uq_cash_reconciliation_payment_active;""".split(";"):
        if statement.strip():
            op.execute(statement)

    op.execute("""
        CREATE FUNCTION app_private.check_cash_allocation() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        DECLARE held integer; allocated bigint;
        BEGIN
          IF TG_OP = 'UPDATE' AND (NEW.payment_transaction_id <> OLD.payment_transaction_id
              OR NEW.allocated_minor <> OLD.allocated_minor
              OR NEW.reconciliation_id <> OLD.reconciliation_id)
          THEN RAISE EXCEPTION 'Cash allocation is immutable'; END IF;
          IF NOT NEW.active THEN RETURN NEW; END IF;
          SELECT t.amount_minor INTO held FROM public.payment_transactions t
          JOIN public.payments p ON p.id=t.payment_id JOIN public.bookings b ON b.id=p.booking_id
          JOIN public.cash_reconciliations r ON r.id=NEW.reconciliation_id
            AND r.staff_id=t.actor_staff_id AND r.business_id=b.business_id
            AND r.currency_code=p.currency_code AND r.status='confirmed'
          WHERE t.id=NEW.payment_transaction_id AND t.transaction_type='cash_payment'
          FOR UPDATE OF t;
          SELECT coalesce(sum(l.allocated_minor),0) INTO allocated
          FROM public.cash_reconciliation_payments l
          WHERE l.payment_transaction_id=NEW.payment_transaction_id AND l.active AND l.id<>NEW.id;
          IF held IS NULL OR allocated+NEW.allocated_minor>held OR NEW.allocated_minor<=0
          THEN RAISE EXCEPTION 'Allocation exceeds cash held or receipt is ineligible'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER check_cash_allocation BEFORE INSERT OR UPDATE
        ON cash_reconciliation_payments FOR EACH ROW
        EXECUTE FUNCTION app_private.check_cash_allocation()""")
    op.execute("""CREATE FUNCTION app_private.protect_reported_payment() RETURNS trigger
        LANGUAGE plpgsql SET search_path='' AS $$
        BEGIN
          IF OLD.transaction_type IN ('cash_payment','card_payment') AND (
              OLD.status <> 'pending' OR NEW.status NOT IN ('succeeded','rejected')
              OR NEW.reviewed_by_staff_id IS NULL OR NEW.reviewed_at IS NULL
              OR (NEW.status='rejected' AND coalesce(trim(NEW.rejection_reason),'')='')
              OR (to_jsonb(NEW) - ARRAY['status','reviewed_by_staff_id',
                  'reviewed_at','rejection_reason','updated_at'])
              IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','reviewed_by_staff_id',
                  'reviewed_at','rejection_reason','updated_at']))
          THEN RAISE EXCEPTION 'Invalid payment review or modification'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER protect_reported_payment BEFORE UPDATE ON payment_transactions
        FOR EACH ROW EXECUTE FUNCTION app_private.protect_reported_payment()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM payment_transactions WHERE reviewed_at IS NOT NULL
            OR screenshot IS NOT NULL OR (transaction_type IN ('cash_payment','card_payment')
            AND status='pending'))
            OR EXISTS (SELECT 1 FROM cash_reconciliation_payments l JOIN payment_transactions t
                ON t.id=l.payment_transaction_id WHERE l.allocated_minor<>t.amount_minor)
        THEN RAISE EXCEPTION 'Downgrade would discard payment reviews or partial allocations';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER protect_reported_payment ON payment_transactions")
    op.execute("DROP FUNCTION app_private.protect_reported_payment()")
    op.execute("DROP TRIGGER check_cash_allocation ON cash_reconciliation_payments")
    op.execute("DROP FUNCTION app_private.check_cash_allocation()")
    op.execute("""CREATE UNIQUE INDEX uq_cash_reconciliation_payment_active ON
        cash_reconciliation_payments(payment_transaction_id) WHERE active IS TRUE""")
    op.drop_column("cash_reconciliation_payments", "allocated_minor")
    for column in ("screenshot", "rejection_reason", "reviewed_at", "reviewed_by_staff_id"):
        op.drop_column("payment_transactions", column)
