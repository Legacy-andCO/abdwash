# Service consumption and direct job costs

Trifecta treats service templates as **expected standard consumption**, not exact physical usage and not accounting valuation. The feature reduces routine employee administration while leaving physical stock counts and manager review as the reconciliation truth.

## Completion semantics

Automatic consumption runs only on the first successful `in_progress → completed` job transition. Booking, assignment, Start Trip, Arrive, Start Wash, cancellation, payment, and loyalty state do not consume stock. A zero-revenue correction/rewash consumes its configured service template when the physical work completes.

The processor reads every performed `booking_services` row and its current `service_inventory_templates` at completion time. It snapshots service/item names, unit, and expected Decimal quantity per booking-service line. Later template/item/service edits cannot rewrite that history. Historical jobs completed before deployment are deliberately not backfilled.

For a job with service lines `s`, expected quantity for item `i` is:

```text
sum(template[s, i].expected_quantity × booking_service[s].quantity)
```

Per-service lines remain explainable, while repeated items are aggregated before the existing inventory engine locks stock and writes movements.

## Source and stock safety

Source resolution is deterministic:

1. One active location already used by authoritative, job-linked manual usage.
2. One active `van` location linked to the assigned scheduling team.
3. One active `mobile_team` location linked to the assigned team.
4. Shop `main` is reserved as an extension point; the current customer product has no authoritative shop/mobile job mode, so the processor does not fabricate this fallback.
5. Otherwise the source is missing or ambiguous and requires review.

Item/location stock rows use the existing deterministic `(inventory_item_id, location_id)` lock order. Applied usage is `min(recorded_available, expected_remaining)`. Stock therefore never goes below zero. Any unapplied amount is persisted as shortfall with a stable issue code. Missing source, ambiguous source, inactive item, zero stock, and ordinary shortage are business outcomes: the customer job completes and manager attention is created. Infrastructure/database failures are not swallowed.

A discrepancy is not a delayed replay queue. A later stock count already represents physical truth, so marking reviewed or counting stock never replays the old shortfall.

## Manual usage and rollout cutover

Existing positive, job-linked manual `usage` movements recorded before completion cover the standard expected amount for the same item first. Automatic completion deducts only the remaining expected amount. This prevents an in-progress job at deployment from receiving the same standard deduction twice.

Manual usage recorded after completion remains an append-only additional/exception movement. Job Detail reports it separately without altering the expected snapshot. Wastage remains its existing distinct workflow.

## Exactly once and concurrency

The job row is locked by the existing completion transaction. The existing unique `(job_id, client_event_id)` event handles uncertain mobile retries, while `UNIQUE(job_id)` on `job_inventory_consumption_runs` is the database-level invariant. The automatic inventory operation also uses the stable key `service-completion:<job_id>`.

Different jobs may complete concurrently. The shared inventory mutation primitive creates/locks all required stock rows in deterministic order, rereads balances under lock, applies only available stock, and records the rest as shortfall. This prevents lost updates, negative balances, and avoidable multi-item deadlocks.

## Manager and employee behavior

Managers/admins can edit service templates, inspect consumables and direct expenses on Job Detail, open Inventory **Needs review**, launch Stock Count, and mark a discrepancy reviewed with an optional note. Review metadata never changes historical quantities. Employees see a read-only consumption summary and can keep using authorized manual job usage, but cannot edit templates, resolve discrepancies, or see Finance-only direct costs.

## Direct job expenses and Finance

The existing `expenses.related_job_id` relationship is reused. Manager/admin expense creation validates the linked job belongs to the same business; Job Detail loads active linked expenses in one bounded query. Existing void behavior remains authoritative.

Automatic inventory usage creates **no Finance expense**. Stock consumption is not a new cash outflow: the underlying receipt may already have produced one `chemicals_supplies` expense. Reliable cost valuation is unavailable, so Phase 3 reports expected quantities plus explicitly recorded direct expenses and does not invent material cost, FIFO/LIFO, weighted average, COGS, procurement, or supplier records.

## Cache and API behavior

Completion patches authoritative Job Detail, matching job lists, and Today/dashboard state immediately. It then refreshes only reports plus inventory overview, attention, stock, movements, and team-stock families. It does not invalidate Finance, Customers, or Team for automatic usage. A direct-expense response patches the relevant job summary and refreshes only Finance/report/expense dependencies.

Staff endpoints added:

- `GET /api/v1/staff/inventory/consumption/attention`
- `POST /api/v1/staff/inventory/consumption/{run_id}/review`

Customer/public APIs expose no internal inventory data.

## V1 limitations

- One service-level recipe applies to all vehicle types.
- Add-ons do not yet have consumption recipes.
- No material-cost estimate exists without an authoritative cost basis.
- No expected-versus-physical BI/calibration engine.
- No procurement, supplier workflow, or inventory valuation.
- No historical consumption backfill and no automatic reversal/replay.
