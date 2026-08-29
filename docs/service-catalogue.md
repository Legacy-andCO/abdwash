# Service catalogue and Phase 1 business configuration

Phase 1 implemented the immediate owner/manager controls described in `STARTUP_PRODUCT_DIRECTION.md`. Phase 2 now consumes duration/capacity settings, and Phase 3 consumes the existing service-level expected-consumables templates without adding procurement or inventory accounting.

## Implemented now

- One backend-authoritative service catalogue shared by the public website, booking creation, and manager/admin mobile management.
- Canonical vehicle types: sedan, SUV, hatchback, coupe, pickup, van, and other.
- Unique normalized integer-minor-unit price per service and vehicle type.
- Service name, description, expected duration, mobile/shop flags, active/inactive state, and sort order.
- Service-owned optional add-ons with price, expected extra duration, channel flags, and active/inactive state.
- Customer booking selection of add-ons and server recalculation of vehicle price, add-ons, loyalty discount, and mobile minimum.
- Immutable booking snapshots for selected service price/duration and add-on name/price/duration.
- Explicit open/closed and opening/closing values for every weekday.
- Controlled 60/90/120-minute slot setting, current cancellation cutoff, optional mobile minimum, and loyalty reward-service selection.
- Manager/admin mobile UI and audited backend writes. Employee reads remain allowed where operationally useful, while writes are rejected by the existing role dependency.
- Tenant-scoped cache keys and schedule/inventory revision invalidation.

Public catalogue serialization uses two bounded database round trips: one business/settings configuration read and one joined service/price/add-on read. Booking creation bulk-loads services, price rows, and selected add-ons; it does not query once per vehicle or add-on.

## Prepared foundations

- Confirmed booking services store `expected_duration_minutes`.
- Selected add-ons store their expected additional duration.
- `default_team_turnaround_minutes` defaults to 60.
- Existing `service_inventory_templates` can be edited from the manager mobile surface.

These values were durable inputs in Phase 1. Current behavior uses duration snapshots for scheduling and reads the current expected-consumables template at first successful completion, then stores an immutable job snapshot and updates recorded team stock safely.

## Explicitly deferred

- Traffic/GPS-aware scheduling or continuous route optimization.
- Vehicle-specific or add-on consumable recipe matrices.
- Advanced expected-versus-physical analytics and automatic calibration.
- Pickup/drop-off or shop-mode customer workflows; the current customer booking product is mobile-service only, so no dead pickup configuration was added.
- Supplier management, purchase orders, inventory valuation/COGS, route optimization, commissions, subscriptions, corporate contracts, AI recommendations, or multi-branch policy inheritance.

## APIs

Public:

- `GET /api/v1/public/catalogue`
- Existing availability, hold, and booking routes consume the new authoritative data.

Staff:

- `GET /api/v1/staff/catalogue`
- `POST /api/v1/staff/catalogue/services`
- `PATCH /api/v1/staff/catalogue/services/{service_id}`
- `POST /api/v1/staff/catalogue/services/{service_id}/addons`
- `PATCH /api/v1/staff/catalogue/addons/{addon_id}`
- `GET /api/v1/staff/business-settings`
- `PATCH /api/v1/staff/business-settings`
- Existing `GET/PUT /api/v1/staff/inventory/services/{service_id}/template`

## Safe deployment

1. Back up and confirm the intended Supabase/PostgreSQL project.
2. Run `alembic upgrade 9d5f551c26e5` from `backend`.
3. Deploy the API.
4. Deploy the customer web.
5. Publish the mobile update.
6. In Services & Pricing, verify every active mobile service has prices for every customer-selectable vehicle type and review the backfilled weekday hours before changing availability rules.

No new environment variable is required. The new public-schema tables have RLS enabled and grants revoked from `anon` and `authenticated`; FastAPI remains the only business-data write path, consistent with current Supabase guidance on combining grants and RLS for exposed schemas.
