# Data model

All primary keys are UUIDs, money uses integer minor units plus ISO currency codes, and timestamps are timezone-aware. Mutable high-risk records carry integer versions. JSON is limited to provider/event payload metadata.

## Tables

- `businesses` — business scope and activation state.
- `business_settings` — timezone, currency, legacy default business hours, controlled slot rules, cancellation cutoff, mobile minimum, hold timeout, attendance grace policy, tenant loyalty configuration, and the Phase 2 default team-turnaround foundation.
- `business_operating_hours` — one tenant-owned open/closed and opening/closing window per weekday.
- `customer_profiles` — optional link to a Supabase Auth user plus reusable contact data.
- `customer_addresses` — saved written/map addresses and optional coordinates.
- `staff_profiles` — lowercase staff username, contact details, authoritative role, active state, and Supabase Auth link.
- `vehicles` — reusable customer vehicles.
- `services` — active catalogue identity, expected duration, mobile/shop channel flags, and an optional service-specific checklist template. The legacy base price is retained as a compatibility/minimum summary, not as the booking authority.
- `service_prices` — unique tenant/service/vehicle-type integer-minor-unit price rows used by public catalogue and booking creation.
- `service_addons` — service-owned optional extras with minor-unit price, expected additional duration, channel flags, ordering, and soft lifecycle state.
- `schedule_resources` — teams/vans that can work concurrently.
- `team_memberships` — active many-to-many staff membership of mobile-team scheduling resources.
- `attendance_sessions` — authoritative server clock-in/out timestamps with optional client timestamps.
- `shifts` — reusable same-business shift definitions.
- `staff_shift_assignments` — one staff shift per work date, optionally linked to a mobile team.
- `leave_requests` — staff date-range request and manager/admin review workflow.
- `slot_hold_groups` — one hashed opaque token, expiry, privately reserved team, and trusted operational-duration snapshot for an atomic group of held slots.
- `schedule_slots` — current resource/time occupancy; uniqueness on resource plus start prevents double booking.
- `bookings` — lifecycle, payment summary, schedule, resource, customer/location snapshot, hashed management secret, and concurrency version.
- `booking_vehicles` — immutable booking-time vehicle snapshots.
- `booking_services` — immutable service/list-price, applied discount, charged total, expected-duration, and optional loyalty-reward snapshot per booking vehicle.
- `booking_service_addons` — immutable selected add-on name, charged price, and expected-duration snapshots per booking vehicle.
- `loyalty_events` — tenant/customer-scoped append-only wash-credit, manual-adjustment, and reward lifecycle ledger with source-key deduplication and actor/reason references.
- `loyalty_rewards` — durable configured-service and required-wash snapshots with `available`, `reserved`, and `redeemed` state plus booking/service/job references.
- `jobs` — operational lifecycle, optional primary staff and scheduling-resource team assignment, immutable operational duration, `auto`/`manual`/legacy assignment provenance, authoritative timing, and version.
- `job_events` — append-only event timeline with server/client timestamps, actor, device, metadata, and client-event deduplication.
- `job_inspections` — one lightweight tenant-scoped condition/damage inspection per job with staff attribution.
- `job_checklist_items` — historically stable service-checklist snapshots per job, including required/optional state and completion attribution.
- `job_photos` — private Storage object metadata, category, upload state, actor, and retry-safe client request ID; image bytes and signed URLs are not stored here.
- `job_quality_issues` — categorized job exception notes with an optional same-job ready photo reference.
- `business_settings.default_inventory_location_id` — nullable pointer to the active business stock pool used for routine expected service consumption; runtime validation enforces same-tenant ownership.
- `job_complaints` — lightweight manager complaint workflow linking the original completed job to at most one zero-value correction job.
- `job_inventory_consumption_runs` — one prospective, immutable completion-time inventory outcome per job, including resolved source, linked automatic inventory operation, applied/no-template/needs-review status, and manager review metadata.
- `job_inventory_consumption_lines` — per-booking-service expected-usage snapshots with service/item/unit names, pre-existing manual coverage, automatically applied quantity, truthful shortfall, and stable issue code.
- `inventory_items` — tenant consumable catalogue with controlled unit/category and low-stock default.
- `inventory_locations` — active main/mobile-team/van/other stock sources with at most one active location linked to a team.
- `inventory_stock` — non-negative authoritative Decimal balance for each item/location pair.
- `inventory_operations` — retry-safe inventory command envelope with actor and optional receipt-expense link.
- `inventory_movements` — append-only receipt/transfer/usage/wastage/count audit rows with optional job, expense, source/destination, reference, and receipt unit-cost metadata.
- `service_inventory_templates` — unique service/item expected standard Decimal quantity; the unit remains authoritative on the inventory item.
- `expenses` — active/voidable operational expense ledger with optional same-business team, staff, receipt, and direct-job attribution.
- `cash_reconciliations` / `cash_reconciliation_payments` — auditable staff/team cash handover batches and their active payment membership.
- `business_sync_revisions` — tenant domain revisions used for targeted mobile cache reconciliation.
- `payments` — local payment aggregate/status; no card credentials.
- `payment_transactions` — provider operation/reconciliation history plus staff/client-event attribution and explicit cash tender/change amounts; the applied amount remains the amount due.
- `customer_payment_methods` — gateway customer/payment-method references and safe display metadata only.
- `cancellation_requests` — request/review workflow distinct from booking cancellation state.
- `notification_outbox` — durable provider-independent message work with claiming and retry state.
- `idempotency_records` — scoped key, request hash, safe response, and expiry.
- `audit_events` — security/administrative audit history that does not duplicate operational job events.

Booking snapshots intentionally remain unchanged if reusable customer, vehicle, address, service, vehicle-price, or add-on rows change later. Phase 2 uses the captured service/add-on duration for rescheduling and capacity decisions without rewriting historical work.

Checklist templates are copied into `job_checklist_items` when a booking creates its job. Later catalogue edits do not alter that job's requirements. The quality migration does not fabricate evidence for historical completed jobs; an empty historical snapshot is valid.

Loyalty is ledger-derived rather than a mutable customer counter. One eligible paid booking-service snapshot can create at most one qualifying event. Reward records snapshot the service, normal list price, and earning threshold so later catalogue/settings changes do not rewrite history. The loyalty migration deliberately does not backfill historical jobs.

Expected consumable templates are read at the first successful job completion, not booking time. Repeated items are aggregated only for stock locking/movement efficiency; the line table preserves which booking service contributed each expected quantity. `UNIQUE(job_id)` and the existing job row lock/client-event flow make automatic consumption exactly once. Historical completed jobs are not backfilled, template edits never rewrite completed-job lines, and a review records acknowledgement without changing expected/applied/shortfall history.

`notification_outbox.dedupe_key` is nullable for historical/general messages. New reschedule and completion events set deterministic business-scoped keys protected by a partial unique index, while the raw booking management token remains derived only at dispatch time.
