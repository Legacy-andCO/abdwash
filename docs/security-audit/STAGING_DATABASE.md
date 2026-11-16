# Staging table-by-table RLS and access-control matrix

Project: `mgfzfgvlrxwyyftwukwf`; head bb63439e5750. Final catalog verifies RLS on all 64 public tables. Each client-role cell summarizes five **executed** SQL permission denials: SELECT, INSERT, UPDATE, DELETE and TRUNCATE. The raw 640 results and rollback-contained probe are linked below.

Runtime policies are intentionally backend-wide: FastAPI must enforce user/team/tenant authorization. These are not per-customer JWT policies. Runtime is a separate NOBYPASSRLS, non-owner login.

| Public table | RLS | anon: S/I/U/D/T | authenticated: S/I/U/D/T | Backend access model |
|---|---|---|---|---|
| alembic_version | PASS | PASS: all denied | PASS: all denied | No grant/policy; migration owner only |
| api_rate_windows | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| attendance_sessions | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| audit_events | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| booking_service_addons | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| booking_services | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| booking_vehicles | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| bookings | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| business_operating_hours | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| business_settings | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| business_sync_revisions | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| businesses | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| cancellation_requests | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| cash_reconciliation_payments | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| cash_reconciliations | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| complaint_rate_windows | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| coupon_service_eligibility | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| coupon_vehicle_eligibility | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| coupons | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_addresses | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_complaints | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_payment_methods | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_profiles | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_review_prompt_states | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| customer_reviews | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| deleted_customer_identities | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| expense_evidence | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| expenses | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| guest_review_verification_attempts | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| idempotency_records | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| inventory_items | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| inventory_locations | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| inventory_movements | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| inventory_operations | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| inventory_stock | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| invoice_sequences | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_checklist_items | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_complaints | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_events | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_inspections | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_inventory_consumption_lines | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_inventory_consumption_runs | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_photos | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| job_quality_issues | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| jobs | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| leave_requests | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| loyalty_events | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| loyalty_rewards | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| notification_outbox | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| payment_transactions | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| payments | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| revenue_invoices | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| schedule_resources | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| schedule_slots | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| service_addons | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| service_inventory_templates | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| service_prices | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| services | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| shifts | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| slot_hold_groups | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| staff_profiles | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| staff_shift_assignments | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| team_memberships | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |
| vehicles | PASS | PASS: all denied | PASS: all denied | backend_only DML; API authorization |

Evidence: [640 raw results](follow-up/staging-role-results.json), [probe SQL](follow-up/staging-role-probe.sql), [final catalog](follow-up/staging-catalog_final.json), [final assessment](STAGING_FINAL.md).

Private app_private helpers have fixed search_path and owner/runtime-only execution. There are no direct-client application data policies to expand. Storage buckets are private and native service tests are documented in the final assessment. Production adoption is a separate unverified/restricted deployment boundary.
