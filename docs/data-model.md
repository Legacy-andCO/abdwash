# Data model

All primary keys are UUIDs, money uses integer minor units plus ISO currency codes, and timestamps are timezone-aware. Mutable high-risk records carry integer versions. JSON is limited to provider/event payload metadata.

## Tables

- `businesses` — business scope and activation state.
- `business_settings` — timezone, currency, business hours, slot rules, cancellation cutoff, and hold timeout.
- `customer_profiles` — optional link to a Supabase Auth user plus reusable contact data.
- `customer_addresses` — saved written/map addresses and optional coordinates.
- `staff_profiles` — authoritative employee/manager/admin role and active state linked to Auth.
- `vehicles` — reusable customer vehicles.
- `services` — active catalogue and authoritative minor-unit pricing.
- `service_addons` — future bounded catalogue extensions.
- `schedule_resources` — teams/vans that can work concurrently.
- `slot_hold_groups` — one hashed opaque token and expiry for an atomic group of held slots.
- `schedule_slots` — current resource/time occupancy; uniqueness on resource plus start prevents double booking.
- `bookings` — lifecycle, payment summary, schedule, resource, customer/location snapshot, hashed management secret, and concurrency version.
- `booking_vehicles` — immutable booking-time vehicle snapshots.
- `booking_services` — immutable service name and price snapshots per booking vehicle.
- `jobs` — operational lifecycle, assignment, authoritative start/completion times, and version.
- `job_events` — append-only event timeline with server/client timestamps, actor, device, metadata, and client-event deduplication.
- `payments` — local payment aggregate/status; no card credentials.
- `payment_transactions` — provider operation/reconciliation history and indexed provider reference.
- `customer_payment_methods` — gateway customer/payment-method references and safe display metadata only.
- `cancellation_requests` — request/review workflow distinct from booking cancellation state.
- `notification_outbox` — durable provider-independent message work with claiming and retry state.
- `idempotency_records` — scoped key, request hash, safe response, and expiry.
- `audit_events` — security/administrative audit history that does not duplicate operational job events.

Booking snapshots intentionally remain unchanged if reusable customer, vehicle, address, or service rows change later.

