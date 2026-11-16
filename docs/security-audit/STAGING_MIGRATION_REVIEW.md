# Staging migration approval review — 11 November 2026

**Executed after explicit approval:** 7d3f2a9c8e41 matched the reviewed checksum before execution and applied only to staging. The full chain now reaches bb63439e5750; [history](follow-up/staging-migration_history.json) and [manifest](follow-up/staging-migration-manifest.json) record the result. The review below is historical, not a request to rerun the migration.

Target: **trifecta-staging**, project `mgfzfgvlrxwyyftwukwf`, BusinessBoost, Frankfurt.
Production `cbejmfjycvzdpqbfiskc` is excluded. Every provisioning migration call in this session has used the staging project ID; no production mutations have been submitted.

## Verified state before approval

Read-only queries against staging returned:
- Alembic head `80826dfc3c2d`: nine upgrades applied in order.
- 35 public tables; businesses, customers, bookings, jobs, payments, Auth users and Storage objects all have **zero rows**.
- business_settings, services, booking_services, business_sync_revisions, payment_transactions and vehicles all have **zero rows**.
- loyalty_rewards and loyalty_events do not exist yet.
- Pending upgrade `7d3f2a9c8e41` has **not** applied. The connector returned an expired confirmation; the subsequent catalog queries confirm its predecessor remains current.

## Exact pending SQL

See [staging-pending-7d3f2a9c8e41.sql](follow-up/staging-pending-7d3f2a9c8e41.sql).
SHA-256 (UTF-8, LF, no trailing newline): `b67068f2ba7c6b0e23027ba1919a2555d15f61b3b2ac6cc2967f1ffd0440ce9f`.

| Operation | Objects/data | Purpose / impact |
|---|---|---|
| DROP / DELETE / TRUNCATE | **None** | No table, column, index, constraint, row, schema or database is removed by this upgrade. |
| UPDATE | business_settings.loyalty_reward_service_id | Fill an unset reward service only when that business has exactly one active service. Currently zero rows qualify. |
| UPDATE | booking_services.list_price_minor | Backfill a newly added field from existing unit_price_minor, before setting NOT NULL. Does not change unit prices, totals or payment state. Currently zero rows qualify. |
| UPDATE | alembic_version.version_num | Advance the existing checkpoint from 80826dfc3c2d to 7d3f2a9c8e41 after the upgrade. This is expected migration bookkeeping. A predecessor assertion rejects a different head. |
| CREATE | loyalty_rewards, loyalty_events and their indexes | Add loyalty reservations/ledger; enable RLS on both. |
| ALTER / ADD | business_settings, business_sync_revisions, booking_services, payment_transactions | Add loyalty configuration, customer revision counter, discount/list-price metadata, cash tender/change and actor/idempotency fields, checks, foreign keys and uniqueness. |
| CREATE INDEX | customer_profiles, vehicles | Add customer-name and plate search indexes; preserves records. |
| ON DELETE CASCADE / SET NULL clauses | New foreign-key definitions | Future parent-deletion behavior only; these are **not DELETE statements** and delete nothing during this upgrade. |

Only the **upgrade()** SQL is submitted. Destructive **downgrade()** functions visible in the Python source are not executed or included. Existing repository migration files are not rewritten. Applied Supabase migration-history entries are retained; alembic_version intentionally stores the current head rather than an append-only history.

Assessment: expected and compatible for this newly created empty staging database. No required synthetic fixtures have been seeded yet, so none can be overwritten. Existing tables are preserved. Provider approval remains required for the connector operation; the user additionally explicitly requested a pause until approval.

## Later migrations (separate from this pending approval)

The remaining chain has no DROP TABLE, DROP COLUMN, TRUNCATE or executable DELETE statements in its rendered upgrades. It does include expected data backfills/catalogue updates, replacement CHECK constraints, replacing the schedule-slot unique constraint with the capacity-exception index, and tightening grants/RLS. These are not covered by the specific pending-upgrade approval above; inspect applicable approval requests before submission. In particular, catalogue migration c18f4a7b2d91 updates prices/service descriptions by name and would overwrite matching fixtures if those were seeded prematurely. **Finish the chain before seeding any synthetic data.**

## Renderer verification and limits

The real Alembic upgrade modules are rendered with the application's Base.metadata naming convention, literal parameters and a PostgreSQL dialect with no DBAPI percent escaping. No schema snapshot was stamped. Early attempts exposed a missing naming convention and doubled percent signs in the renderer; each failed upgrade rolled back and its version checkpoint stayed unchanged. The renderer was corrected, unchanged previously applied SQL was compared, then the next upgrade proceeded. These were bootstrap-renderer defects, not evidence that the application's online migration chain failed. Native Auth, MFA, Storage/API tests and full staging hardening remain incomplete.

