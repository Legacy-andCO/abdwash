# Trifecta performance architecture

## Evidence language

Every number in this document is labelled so a local measurement is never presented as
production fact.

- **Production-observed:** captured from a deployed request or provider log.
- **Locally measured:** executed from the development machine against the configured
  Supabase project on 2026-08-28. Network distance is part of the result.
- **Contract-tested:** enforced by an automated test.
- **Static audit:** derived from code paths and query definitions without runtime timing.
- **Target:** an operating objective that still needs production telemetry to confirm.

## CorePOS reference translation

| CorePOS concept | Trifecta implementation |
| --- | --- |
| tenant | `business_id` on every operational resource |
| branch/location | schedule resource, Main Shop, mobile team, or van inventory location |
| operator context | verified Supabase identity plus one PostgreSQL `StaffContext` projection |
| sale/order | immutable booking snapshot plus job and payment state |
| stock ledger | inventory operation plus append-only inventory movements |
| sync version | `business_sync_revisions`, split by jobs/workforce/schedule/finance/inventory/customers |
| client SWR cache | TanStack Query, role-scoped keys, bounded AsyncStorage persistence |
| provider boundary | one lifespan HTTP client and sanitized attempt metrics |
| outbox | `notification_outbox` with bounded `SKIP LOCKED` claims and retry backoff |

No CorePOS schema, service, Redis tier, AI feature, or offline write queue was copied into
Trifecta. The references informed measurement, ownership, and cache rules only.

## Request lifecycle

```text
mobile/web request
  -> request ID + process age/cold flag
  -> Supabase JWT verification (fresh or stale-safe JWKS)
  -> one narrow staff-context projection when required
  -> bounded service queries / short transaction
  -> response validation and serialization
  -> X-Request-ID + Server-Timing + structured safe log
```

The mutable request metric object crosses Starlette task boundaries without relying on
ContextVar value replacement. It records SQL count/duration, first-SQL start, pool
checkout count/wait, peak checked-out connections, provider attempts/duration/outcomes,
auth time, staff-context time, response-start time, total time, process age, and whether
the process had served a previous request. Route templates are logged instead of raw URLs.
Development responses additionally expose SQL count and duration; production does not.

Provider diagnostics contain only provider, operation, outcome category, and duration.
They never contain JWTs, API keys, headers, customer fields, coordinates, or provider
payloads. Mobile development timing similarly strips query values and UUID path segments.

## Measurement baseline and result

Method: direct service calls through the configured async engine, one new request session
per flow, no writes, no customer fields or identifiers printed. These are **locally
measured**, not Vercel production timings. SQL counts exclude the one-query authenticated
staff-context dependency that an HTTP staff endpoint adds.

| Read flow | Before SQL / total | After SQL / total | Evidence |
| --- | ---: | ---: | --- |
| sync state | 1 / 383 ms | 1 / unchanged contract | locally measured |
| Jobs -> All (50) | 3 / 563 ms | 2 / 483 ms | locally measured + contract-tested ceiling |
| team list | 1 / 382 ms | 1 / unchanged | locally measured |
| attendance overview | 5 / 734 ms | 5 / unchanged | locally measured |
| manager Today dashboard | 9 / 876 ms | 7 / 922 ms sample | locally measured + contract-tested ceiling |
| Reports V2, 30 days | 13 / 1,550 ms | 9 / 1,201 ms | locally measured + contract-tested ceiling |
| Finance, 30 days | 5 / 489 ms | 3 / 378 ms | locally measured + contract-tested ceiling |
| inventory overview | 2 / 436 ms | 2 / unchanged | locally measured + contract-tested ceiling |
| inventory list/location/stock/movement | 1 each / 325-346 ms | 1 each | locally measured/static |
| customer list | 2 / 438 ms | 2 / unchanged | locally measured + contract-tested ceiling |
| staff Job Detail | 4 / 577 ms | 3 expected | locally measured/static projection |
| manager Customer Detail | 11 / 1,313 ms | 9 / 1,140 ms | locally measured |

The dashboard timing sample increased despite two fewer statements; this is normal network
variance and is why query-count improvement is reported separately from latency. A trivial
connection sample measured cold checkout at 809 ms, warm checkout at 143-191 ms, and the
query/driver leg at 95-142 ms from the development machine. Production Vercel measurements
must determine real compute-to-database distance.

## Client request matrix

Counts below are **static audit** counts when data is stale/absent. A fresh TanStack cache
performs zero resource requests. The shell sync-state check is shown separately because it
is the single foreground invalidation authority.

| # | User flow | Cold/stale application requests | Fresh-cache requests | Notes |
| ---: | --- | ---: | ---: | --- |
| 1 | restore authenticated mobile session | context 1 | context 1 per process restore | Supabase session restoration is separate external auth I/O |
| 2 | enter manager Today | dashboard + attendance + personal cash = 3 | 0 | employee-only Jobs/Shifts no longer mount |
| 3 | enter employee Today | jobs + attendance + shifts + personal cash = 4 | 0 | role-authorized data only |
| 4 | foreground/network sync | sync-state 1, then changed active domains only | sync-state 1 | simultaneous triggers share one promise |
| 5 | Jobs list/tab/filter | 1 | 0 | filter, scope, search, pagination in key |
| 6 | Jobs customer-name search | 1 per debounced term | 0 per fresh term | server-side tenant-scoped search |
| 7 | Job Detail | 1 | 0 | list snapshot remains visible until detail arrives |
| 8 | Job quality detail | 1 plus bounded signed-URL attempts | 0 | provider I/O after DB transaction |
| 9 | job state mutation | 1 write | n/a | patches job/list/dashboard, targeted background refresh only |
| 10 | Team list | 1 | 0 | role-scoped key |
| 11 | Team Detail | 1 | 0 | team ID in key |
| 12 | workforce schedule/attendance/leave view | 1 per visible resource/range | 0 | range in key; hidden screens unmounted |
| 13 | Reports | 1 | 0 | range in key; historical ranges stay fresh longer |
| 14 | Finance screen | overview + expenses + pending + reconciliations = 4 | 0 | parallel, not a waterfall |
| 15 | Inventory initial manager overview | overview + attention + items + locations = 4 | 0 | attention is bounded; hidden stock/movements do not mount |
| 16 | Inventory stock or movements tab | 1 newly visible resource | 0 | active-tab pull refresh only |
| 17 | Customer list/search | 1 per debounced page/term | 0 | account/staff/search/offset scoped |
| 18 | Customer Detail | 1 | 0 | server returns bounded bootstrap/history |
| 19 | public web catalogue consumers | 1 shared promise | 0 for page lifecycle | failures clear promise for retry |
| 20 | authenticated web homepage/account profile | 1 shared profile bootstrap | 0 while fresh | homepage never blocks on loyalty |
| 21 | authenticated web booking-status/account list | 1 shared bookings request | 0 for 20 s | polling refresh preserves cached content |

Availability is intentionally excluded from long-lived persistence: its key includes date,
vehicle count, authoritative service/add-on selections or booking context, and it stays fresh only 20 seconds on mobile. Booking holds,
job actions, inventory movements, cash actions, and other writes are never served from cache.

### Completion-time service consumption

Phase 3 adds only bounded SQL shapes to the completion transaction: one exactly-once run lookup, one joined query for every performed service/template/item, one grouped query for pre-existing job usage, one business-default/active-locations query when automatic usage remains, and the existing inventory operation/item/location/stock-lock primitives. The default location is resolved once per completion, never per item. Repeated service items are aggregated before stock locks, and movement rows are staged together. Job Detail adds one joined consumption-run/line/location query plus one grouped additional-manual-usage query; manager-only direct expenses use one bounded job-ID query. There is no per-service or per-item read loop.

These are **static implementation and contract-test evidence**, not production latency. Isolated PostgreSQL concurrency/query execution remains opt-in through `TEST_DATABASE_URL`; production query/latency claims still require post-deployment telemetry.

## Cache ownership and lifecycle

Mobile cache scope is `business_id:staff_id:role`; resource parameters add date range,
team/job/customer/location IDs, filters, search term, and pagination. Cache policy:

| Resource | Freshness | Persistence retention |
| --- | ---: | ---: |
| active job / jobs / dashboard / attendance | 20-30 s | 24 h |
| finance / inventory / customers | 60 s | 2-7 days by resource |
| teams/staff | 3 min | 2 days |
| shifts/profile | 5 min | 3 days |
| historical reports | 5 min | 7 days |
| availability | 20 s | not persisted; 2 min memory GC |

Only successful queries explicitly marked `persist` are dehydrated. Persistence is versioned,
throttled, capped at 80 queries and 2 MB, pruned by per-resource retention, and fails by
removing the oldest query. Logout cancels reads/writes without globally destroying other
account caches; every cache read is scope isolated. A deliberate full clear removes both
the query cache and sync-revision keys.

Initial loading uses pending state only when there is no data. Pull/background refresh uses
refetch state, preserving usable content and showing refresh/error affordances. A changed
sync revision marks only affected scoped families stale and refetches active observers.

## Mutation strategy

- Job mutations replace the authoritative Job Detail and every matching Jobs page, and patch
  manager active-job dashboard state.
- Team/staff/profile/shift/leave mutations patch returned entities where possible, then mark
  only dependent summaries stale.
- Inventory and finance writes invalidate their bounded dependent families because server
  aggregates are authoritative; unrelated workforce/job caches remain intact.
- Uncertain idempotent writes retain their client event ID. There is no offline mutation
  replay queue.
- Manager exact rescheduling performs one bounded authoritative Job reconciliation after a
  timeout. Matching UAE wall-clock date/time is treated as confirmed success; an unconfirmed
  retry reuses the original client event ID and never opens parallel writes from double taps.

## Database and query design

The shared engine uses a bounded QueuePool, LIFO reuse, configurable checkout timeout,
connection recycling, and configurable pre-ping. Session pooling/direct connections may use
prepared statements. Supavisor transaction mode (normally port 6543) must set
`DB_DISABLE_PREPARED_STATEMENTS=true`; current Supabase guidance says transaction mode does
not support prepared statements.

Recommended starting points, subject to the Supabase connection budget:

| Compute | Pool starting point | Prepared statements | Pre-ping |
| --- | --- | --- | --- |
| persistent regional service/direct or session pooler | size 5, overflow 5 | enabled | enabled |
| Vercel/serverless transaction pooler | size 2, overflow 0-1 per warm instance | disabled | validate; normally enabled initially |
| test/local isolated PostgreSQL | size 5, overflow 0 | enabled | enabled |

Never multiply the per-instance maximum by an assumed single Vercel instance. Check the
Supabase Database dashboard connection budget and leave capacity for migrations, dashboard,
cron, and operational access before increasing pool values.

Hot reads use explicit projections, PostgreSQL aggregates, correlated counts, bounded limits,
and batched relationship loads. Jobs now projects staff and team names in its base statement.
Saved addresses and vehicles share one union projection. Loyalty ledger totals share one
aggregate statement. Dashboard, reports, and finance combine independent scalar aggregates
without weakening tenant predicates.

## Index evidence

`EXPLAIN (FORMAT JSON)` was run read-only against the configured database; no `ANALYZE`,
DDL, or customer values were emitted. Results are **locally inspected plans** on a very small
dataset:

- customer history used `ix_bookings_schedule_status` (estimated one row, cost 2.36);
- inventory stock used `ix_inventory_stock_business_item` (three rows, cost 4.45);
- Jobs joined small tables with sequential scans and booking PK lookup (one row, cost 3.64);
- outbox claim used a small sequential scan (two rows, cost 1.09).

The existing schema already has indexes for business/schedule/status Jobs, staff/status/job
schedule, customer booking history, inventory business/location and business/item, outbox
claim, booking-service joins, and active team membership. Small-table sequential scans are
not evidence of a missing index. No performance migration was created. Re-evaluate with
production-scale statistics and `EXPLAIN (ANALYZE, BUFFERS)` in a safe staging clone before
adding an index; watch customer history ordering and outbox claim selectivity as data grows.

## Query-count regression ceilings

The isolated PostgreSQL suite enforces service ceilings of: sync 1, Jobs list 2, dashboard 7,
Reports V2 9, Finance 3, inventory overview 2, inventory items 1, and customer list 2.
Public catalogue/availability/hold/booking ceilings remain in place. Staff HTTP endpoints add
one staff-context query. The integration suite refuses remote/destructive database targets and
runs only when `TEST_DATABASE_URL` names a local PostgreSQL database containing `test`.

Smart availability loads eligible teams, active membership/leave signals, relevant blocking jobs,
active holds, and grid-slot occupancy in bounded date-scoped queries. It does not query once per
slot or once per team. A business/day advisory transaction lock serializes hold, confirmation,
reschedule, and manager-assignment capacity writes before deterministic per-slot row locking.

## Web resource reuse

Catalogue uses one page-lifecycle promise. Customer profile/loyalty/bookflow uses one
user-keyed 60-second single-flight resource. Customer booking status and Account Bookings use
one user-keyed 20-second single-flight resource; explicit polling forces refresh while cached
content remains rendered. Guest home does not fetch private resources. Availability and holds
remain live because their correctness window is short.

## Provider and transaction boundaries

The lifespan HTTP client has bounded connections and connect/read/write/pool timeouts and is
reused by JWKS, Supabase Admin/Storage, Google Routes, and Resend adapters. Provider attempts
are counted and categorized. JWKS retains stale verified keys during transient refresh failure;
unknown signing keys still force rotation refresh. Job-photo signed URL calls, Google ETA, and
notification delivery happen outside long database transactions. Notification providers never
mark success before the provider confirms it.

## Deployment checklist

1. Keep API compute geographically close to the Supabase region; verify the actual Vercel
   function region rather than assuming it.
2. Choose direct/session versus transaction pooler deliberately. For transaction mode set
   `DB_DISABLE_PREPARED_STATEMENTS=true` and use a small per-instance pool.
3. Configure `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`,
   `DB_POOL_RECYCLE_SECONDS`, and `DB_POOL_PRE_PING` from the connection budget.
4. Deploy the API and inspect `http_request` plus `provider_attempt` events. Confirm warm
   checkout, auth, staff-context, SQL, provider, and response-start distributions.
5. Deploy web/mobile clients and verify fresh navigation performs zero resource requests,
   stale navigation preserves content, and foreground sync does one revision request.
6. Alert on pool timeout/503, rising checkout wait, SQL-count ceiling drift, provider timeout,
   and p95/p99 route latency. Never alert from or store raw tokens/payloads.

## Known limitations and targets

- The database is currently one Alembic revision behind repository head (`f29a61e82c45`
  deployed versus `5e2c8f7a1b4d` repository head) as observed read-only on 2026-08-28. This is
  an existing deployment-state issue, not a performance migration.
- No production Vercel timing export or load-test traffic was available. Production p50/p95/p99,
  cold-start rate, and connection-budget headroom remain **targets to verify**.
- **Target:** warm staff context under 150 ms and ordinary warm reads under 500 ms when compute
  and database are co-located; reports may be slower but should remain bounded and cached.
- No offline mutation queue, Redis, materialized report pipeline, or AI feature was introduced.
