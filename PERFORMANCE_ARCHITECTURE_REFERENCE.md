# CorePOS Performance Architecture Reference

**Purpose:** This document records the performance architecture and engineering methods used to improve CorePOS, CorePOS Desktop, and CorePOS Mobile Monitor. It is intended to be given to an AI engineering agent before a later project that needs comparable real-world responsiveness without sacrificing correctness, tenant isolation, durability, or business-time semantics.

**Reference state:** Repository state inspected on 2026-08-25.

**Important:** This is a design and implementation reference, not a claim that every deployment will reproduce the same latency. Network geography, serverless cold starts, database size, provider health, device performance, and production configuration still matter. Measure the target system before and after applying these patterns.

---

## 1. Executive summary

The largest CorePOS gains did not come from a single micro-optimization. They came from shortening the complete interaction path.

Older flows often behaved like this:

```text
tap
-> component mounts with empty local state
-> several API requests
-> repeated authorization/context queries
-> broad ORM reads or repeated aggregates
-> external provider work, where applicable
-> ancillary persistence/provider delivery
-> broad client refetch
-> UI finally becomes useful
```

The improved architecture aims for:

```text
tap
-> immediate visual acknowledgement
-> last authorized scoped data appears from memory/device cache
-> fresh cache skips the network
-> stale cache revalidates quietly
-> backend performs narrow, indexed, bounded work
-> authoritative mutation response updates only affected state
-> noncritical work runs after commit/outside the critical path
```

The most important reusable changes were:

1. **Central stale-while-revalidate client caches** on desktop and mobile, with strict account/branch/user/query keys.
2. **Separation of initial loading from background refreshing**, preventing `data -> skeleton -> data` flashes.
3. **Single-flight request deduplication** and resource-specific freshness rather than one universal TTL.
4. **Targeted mutation reconciliation** instead of clearing modules and fetching everything again.
5. **Production-safe request instrumentation** for total time, response-start time, SQL count/time, connection time, phases, and provider attempts.
6. **Warm, bounded database connection reuse** compatible with the Supabase transaction pooler.
7. **Collapsed authorization/context retrieval**, using joined authorization graphs and bulk settings loading.
8. **Purpose-built SQL aggregates** for dashboard, reports, and AI tools instead of loading complete order graphs and aggregating repeatedly in Python.
9. **Fixed-cost batch inventory deductions** instead of ingredient-by-ingredient query loops.
10. **Hot-path composite indexes** aligned with actual tenant, branch, status, and date predicates.
11. **Reusable external HTTP clients and provider circuit state**, avoiding repeated DNS/TLS setup and repeated timeout penalties.
12. **Progressive AI voice delivery**, response-first chat rendering, and history reconciliation outside the first-result path.
13. **Durable notification outbox processing**, so push-provider latency/failure no longer determines whether a business mutation appears successful.
14. **Cold-start controls**, keeping schema creation, seed repair, and bootstrap mutations out of normal production startup.

The general lesson is:

> Optimize the end-to-end orchestration and time to first useful output. A 1 ms SQL query does not make a screen fast if it is surrounded by ten remote round trips, a remount, a broad refetch, and no immediate UI feedback.

---

## 2. Evidence classification

Future agents must distinguish evidence types. Do not present structural improvements as measured production latency unless a trace proves it.

| Label | Meaning |
|---|---|
| **Production-observed** | Seen in production logs or a production acceptance flow. |
| **Locally measured** | Timed in the current repository/environment. Hardware and network caveats apply. |
| **Contract-tested** | A test proves request count, ordering, isolation, streaming, or state behavior—not necessarily production latency. |
| **Static implementation evidence** | The code has the desired architecture, but a production trace is still needed to quantify its benefit. |
| **Target/estimate** | A desired or expected range, explicitly not a measurement. |

Known baseline observations that motivated the work included:

- AI Talk could take approximately **20–25 seconds** before useful audio.
- Warm DB-backed requests could take approximately **1–2+ seconds**, even when PostgreSQL execution itself was sub-millisecond.
- Typical mobile monitoring paths performed roughly **eight context queries before endpoint work**.
- Dashboard used roughly **12–13 SELECTs** for a small response.
- Public menu was observed around **2.7–2.8 seconds** for a small result.
- Desktop inventory mutations could produce **one write plus five GETs**.
- Mobile waiter order actions could produce **one POST plus four GETs**.
- Reports remounted and repeated multiple requests within seconds while briefly displaying a placeholder.
- Order History generated a client-side N+1 pattern for payment summaries.
- Kitchen polling could run at response/RTT speed because response state retriggered the polling effect.

After the cache pass, a desktop Reports acceptance flow proved that reopening Reports four seconds later produced **zero additional sales, expense, end-of-day, weekly, or hourly report requests**, while the previously rendered report remained visible. Production logs also showed report endpoints themselves commonly around approximately **18–45 ms** in the cited environment. Treat those endpoint numbers as deployment-specific observations, not universal guarantees.

---

## 3. Old client behavior and why it felt slow

### 3.1 Desktop CorePOS

The old desktop pattern was primarily screen-local:

```text
navigate to screen
-> component mounts
-> local data = empty
-> loading = true
-> placeholder/skeleton renders
-> effect fetches backend
-> data arrives
```

Navigating away often unmounted the screen. Returning destroyed the useful data lifecycle even if the same response had been loaded seconds earlier. Fast backend responses still produced a perceptible flash because the UI rendered an empty state before the request completed.

Additional problems included:

- report values were cleared when refresh began;
- filters, tabs, search, and date selection were component-local;
- identical effects could overlap;
- mutation handlers frequently performed broad follow-up refreshes;
- Order History requested payment information per visible order;
- Kitchen polling depended on response identity and could retrigger immediately.

### 3.2 CorePOS Mobile Monitor

Older mobile screens commonly waited for the backend on each visit:

```text
open tab
-> no usable state
-> skeleton
-> fetch
-> render
```

Problems included:

- screen-local repeated requests;
- no persistent read cache across app restarts;
- cache keys that were not centrally guaranteed to include the complete monitoring scope;
- a generic loading state that could erase useful content during refresh;
- full cache-envelope persistence on the response/render path;
- broad post-mutation refetches;
- app resume behavior that could make screens feel newly mounted;
- waiter menu/table/session resources initially outside the highest-value cached set.

### 3.3 Backend orchestration

The backend was often not slow because SQL computation was intrinsically expensive. It was slow because each user-visible operation accumulated remote and serial work:

- a new database connection/handshake per request in a serverless environment;
- repeated user/account/branding/branch/access/settings lookups;
- complete ORM graphs for data that only needed totals;
- multiple independent report queries and Python aggregation;
- repeated business-data retrieval across related AI tools;
- per-ingredient inventory reads and writes during order completion;
- new external HTTP clients for provider calls;
- long provider waits before fallback;
- DB transactions kept open while waiting on external services;
- history/telemetry/provider delivery on the critical path;
- frontend broad refetches after the authoritative mutation had already succeeded.

---

## 4. Desktop cache architecture

Primary implementation:

- `frontend/src/lib/desktopPerformance.js`
- `frontend/src/lib/useRetainedDesktopState.js`
- `frontend/src/context/AppContext.jsx`
- screen integrations under `frontend/src/screens/`

### 4.1 Architecture

Desktop uses a small purpose-built cache instead of adding a competing dependency:

```text
screen
-> canonical scoped key
-> memory cache lookup
-> optional localStorage lookup
-> render cache immediately
-> if fresh: stop
-> if stale: keep visible and single-flight refresh
-> update memory, persistence, and subscribers
```

The cache contains:

- memory entries for instant navigation;
- selective persistent entries for restart restoration;
- timestamps and schema version;
- retention and size bounds;
- an in-flight promise map for deduplication;
- explicit resource invalidation;
- a separate in-memory retained UI-state map.

### 4.2 Key design

The canonical desktop resource key is equivalent to:

```text
[
  account_id,
  branch_id_or_all,
  user_id,
  role,
  resource,
  canonicalized_query_parameters
]
```

Canonicalization recursively sorts object keys. This prevents logically identical filter objects with different property order from creating separate entries.

Reports additionally include the exact date range and authoritative business date. The design prevents:

- account A data appearing for account B;
- branch A stock appearing for branch B;
- one user's role-sensitive data appearing for another user;
- today's report being reused for last week;
- one filter combination being reused for another.

### 4.3 Desktop freshness policy

| Resource | Freshness window | Reasoning |
|---|---:|---|
| Kitchen | 3 seconds | Highly live operational state. Existing 10-second polling remains authoritative. |
| Tables | 5 seconds | Occupancy/lock state changes frequently. |
| Current orders | 10 seconds | Live, but revisiting immediately should not blank/refetch. |
| Inventory branch stock | 10 seconds | Quantities matter operationally. |
| Attendance/current staff | 15 seconds | Current-state resource. |
| Delivery integrations | 15 seconds | Operational status with moderate volatility. |
| Order History | 15 seconds | Recent orders can still change. |
| Current-period reports | 30 seconds | Current totals change, but not every navigation needs a request. |
| Inventory catalog/bundle | 30 seconds | Catalog is less live than stock. |
| Employees | 30 seconds | Directory changes infrequently; status is separated. |
| Day-off requests | 30 seconds | Actionable but not second-by-second. |
| Notifications | 30 seconds | Avoid duplicate focus/poll requests. |
| Managed tables | 30 seconds | Configuration-like state. |
| Historical reports | 5 minutes | Closed historical ranges rarely change. |
| Menu/catalog | 5 minutes | Mostly static; mutations explicitly invalidate/update. |
| Settings/branding | 5 minutes | Configuration data. |
| Selectable employees | 5 minutes | Directory projection. |

Freshness is intentionally different from retention. A stale value can remain useful for instant display while the system immediately tries to refresh it.

### 4.4 Bounds and versioning

Desktop cache rules:

- schema version: `1`;
- general retention: 24 hours;
- maximum general entries: 80;
- maximum serialized persistent entry: 750 KB;
- report retention: 30 minutes;
- maximum report entries: 12;
- obsolete schema versions and expired entries are pruned.

If persistent storage fails or is full, memory caching still works. A read cache must not make the primary workflow fail.

### 4.5 Initial loading versus refreshing

The central UI invariant is:

```text
no cache + request pending -> initial loader allowed
cache/current data + request pending -> keep data visible, subtle refreshing state
cache/current data + refresh failed -> keep data visible, non-destructive warning
no cache + request failed -> full error state allowed
```

This distinction is more important to perceived speed than changing a 45 ms endpoint to a 25 ms endpoint.

### 4.6 Request deduplication

`runDesktopSingleFlight(key, task)` stores one in-flight promise per exact key. Two components/effects requesting the same resource share one request. The promise is removed after completion so a later legitimate refresh can run.

### 4.7 Retained screen state

`useRetainedDesktopState` preserves useful UI choices without keeping large component trees mounted:

- POS category, search, and order type;
- Reports tab, range, and custom dates;
- Order History filters;
- Inventory, Employees, Settings, and Menu Management tabs;
- delivery integration selection.

Transient or correctness-sensitive state is intentionally not retained, including active cart/payment forms and transaction previews.

### 4.8 Mutation behavior

The improved mutation sequence is:

```text
send mutation
-> receive authoritative response
-> update/upsert affected local entity immediately
-> invalidate or mark only dependent resources stale
-> reconcile quietly
-> preserve unrelated screens and caches
```

Examples:

- order mutations affect current orders, history, kitchen, tables, and related reports;
- table mutations affect tables and managed tables;
- inventory mutations affect inventory catalog/stock and related dashboard/report projections;
- staff mutations affect employees, attendance/status, and selectable employees;
- day-off mutations affect the relevant request keys;
- settings/branding writes replace their cache entry from the authoritative response.

Report caches are marked stale rather than erased. This prevents a successful mutation from turning a visible report into a placeholder.

### 4.9 Logout and scope changes

Cache lookup never acts as authorization. On logout, invalid session, account/branch/role change, or impersonation transition:

- old scoped values are not hydrated into the new screen;
- visible operational state is reset before new-scope hydration;
- the relevant user's persistent cache is removed on logout;
- backend 401/403 behavior remains authoritative.

---

## 5. Mobile Monitor cache architecture

Primary implementation:

- `mobile/src/cache/mobileCacheCore.cjs`
- `mobile/src/cache/mobileCache.js`
- `mobile/src/hooks/useMonitoringRequest.js`
- `mobile/src/context/AuthContext.js`

### 5.1 Architecture

Mobile uses:

```text
memory cache
+ Expo-compatible persistent file cache
+ useMonitoringRequest stale-while-revalidate hook
+ scoped mutation helpers
```

The persistent envelope is stored under the app document directory. Cache hydration runs in parallel with secure session restoration, so previously authorized data can already be in memory when the first screen renders.

The cache is a read-through UX optimization, not an offline transaction database.

### 5.2 Mobile key design

Mobile keys include:

```text
cache version
account ID
branch ID or all
user ID
resource
stable serialized query parameters
```

The selected monitoring context determines account and branch scope. A manager switching monitored restaurants receives a different cache key immediately.

### 5.3 Mobile freshness and retention

| Resource | Freshness | Retention |
|---|---:|---:|
| Dashboard | 20 seconds | 24 hours |
| Reports | 5 minutes | 7 days |
| Daily Summary | 1 minute | 3 days |
| Staff status | 20 seconds | 24 hours |
| Actionable day off | 20 seconds | 24 hours |
| Day-off history | 1 minute | 3 days |
| Inventory items | 45 seconds | 48 hours |
| Inventory movements | 45 seconds | 24 hours |
| Inventory alerts | 30 seconds | 24 hours |
| Waiter orders | 12 seconds | 12 hours |
| Waiter tables | 10 seconds | 12 hours |
| Waiter menu categories | 5 minutes | 3 days |
| Waiter menu items | 1 minute | 48 hours |
| Waiter modifier groups | 5 minutes | 3 days |
| Waiter table session | 8 seconds | 12 hours |

### 5.4 Persistence performance

The mobile cache deliberately updates memory and notifies the UI before durable persistence. Persistent writes are:

- queued;
- coalesced/debounced by 75 ms;
- bounded to 80 entries;
- bounded to approximately 2.5 MB serialized;
- pruned by retention and least-recent access;
- limited to 12 report queries per scope.

This avoids turning JSON serialization and file I/O into part of time to first useful render.

### 5.5 Hook contract

`useMonitoringRequest` exposes separate states:

```text
data
loading
refreshing
error
refreshError
lastUpdated
isStale
source
refresh()
updateCachedData()
```

Behavior:

- synchronous memory peek can provide data on the first render;
- persistent hydration fills memory before normal screen loading where possible;
- fresh data skips the fetch;
- stale data stays visible while the fetch runs;
- manual refresh forces a request without clearing data;
- resume revalidates stale resources;
- failure applies a retry delay to avoid hammering weak connections;
- 401/403 removes the authorized scope and follows existing logout/access behavior.

### 5.6 Mobile mutation behavior

Mutation helpers provide:

- `updateResourceData(resource, updater)` for authoritative local projection updates;
- `invalidateResources(resources)` for precise revalidation.

Waiter, inventory, staff, day-off, and dashboard dependencies use targeted invalidation instead of an awaited module-wide refresh. Waiter table/order mutations consume authoritative backend responses and update shared cached entities before background reconciliation.

### 5.7 What is not cached as live truth

- generated AI operational answers are not treated as cached current business answers;
- auth tokens remain in secure session storage, not the operational read cache;
- payment outcomes and write queues are not fabricated offline;
- current table/payment state uses short TTLs and explicit invalidation;
- permission loss removes/locks the affected cache.

---

## 6. Backend performance architecture

### 6.1 Instrument first

Primary implementation: `backend/app/core/performance.py`.

CorePOS adds lightweight ASGI request tracing that captures only sanitized metadata:

- safe correlation/request ID;
- route template rather than raw user-controlled IDs;
- total duration;
- time to response start;
- cold-process first-request marker;
- SQL count and cumulative client-observed SQL time;
- database connect count and time;
- named service phases;
- external provider attempts, outcomes, fallback status, duration, and optional TTFB;
- response completion state and process uptime.

Responses expose `X-Request-ID` and `Server-Timing`. Desktop and mobile API clients retain these fields for debugging. Raw SQL, request bodies, tokens, audio, and tenant business data are deliberately excluded.

Reusable principle:

> Capture total time, query count, connection time, provider time, and time to first response separately. Otherwise a fast SQL query can hide a slow connection, or a fast backend can be blamed for a client placeholder flash.

### 6.2 Database connection reuse

Primary implementation: `backend/app/core/database.py`.

The old serverless posture effectively paid connection setup too often. The improved engine keeps a small warm client-side connection pool per reused process while remaining compatible with the Supabase transaction pooler:

- default pool size: 1;
- deliberately small overflow;
- bounded checkout timeout;
- connection recycle;
- `pool_pre_ping` disabled by default to avoid an extra remote round trip on every checkout;
- asyncpg native and SQLAlchemy prepared-statement caches disabled for transaction-pooler compatibility.

Do not blindly replace this with a large conventional pool. In a serverless deployment, many instances multiplied by a large pool can exhaust database connections. Measure concurrency and configure the Supabase pooler and compute runtime together.

### 6.3 Deployment geography

`backend/vercel.json` pins the backend to `fra1`. The database and major providers should be checked for geographic alignment. Repository configuration alone cannot prove the Supabase project region or actual provider routing.

Reusable principle:

> Co-locate compute and database before trying to optimize sub-millisecond SQL. Each serial query pays network latency even when execution time is nearly zero.

### 6.4 Cold-start controls

Primary implementation: `backend/app/main.py` and `backend/app/core/config.py`.

Production startup now guards schema creation, seed work, platform-admin repair, and demo-user repair behind explicit startup-mutation policy. Normal production deployments should use Alembic/deployment jobs and configure:

```text
AUTO_CREATE_SCHEMA=False
SEED_ON_STARTUP=False
PLATFORM_ADMIN_BOOTSTRAP_ON_STARTUP=False
MOBILE_DEMO_USERS_BOOTSTRAP_ON_STARTUP=False
ALLOW_PRODUCTION_STARTUP_MUTATIONS=False
```

This prevents a serverless cold start from quietly becoming a migration/seed/repair job.

### 6.5 Authorization and monitoring-context collapse

Primary implementation:

- `backend/app/repositories/auth_repository.py`
- `backend/app/core/auth.py`
- `backend/app/services/auth_service.py`

The user authorization graph is loaded in one round trip with:

- user;
- active branch constrained to the user's account;
- account;
- branding.

Mobile monitoring access rows eager-load their account and branch. App settings for all allowed accounts are bulk-loaded instead of fetched account-by-account. Request-local `_auth_branch` and validity metadata prevent the service layer from repeating branch lookup while preserving tenant checks.

This improves performance without caching authorization indefinitely. Revocation, account status, branch activity, role, feature entitlement, and monitoring access remain database-authoritative per request.

### 6.6 Dashboard aggregate

Primary implementation:

- `backend/app/repositories/report_repository.py:get_dashboard_snapshot_aggregate`
- `backend/app/services/monitoring_service.py:dashboard_snapshot`

The older Dashboard path assembled a small response through roughly 12–13 SELECTs and broad helper calls. The optimized path returns the core dashboard aggregates in one database round trip using scoped aggregate subqueries/expressions for:

- sales and completed order count;
- average/cash/card metrics;
- inventory low/critical counts;
- table state counts;
- kitchen active/ready counts.

The query remains scoped by account, branch, business-timezone boundaries, status, and active flags. A compatibility fallback remains for lightweight repository adapters used by tests/integrations.

Reusable principle:

> If an endpoint returns ten numbers, do not load hundreds of ORM objects and relationships. Build a narrow, purpose-specific aggregate query with the same authorization and business-time rules.

### 6.7 Report aggregation

Primary implementation:

- `backend/app/repositories/report_repository.py`
- `backend/app/services/report_service.py`

Reports now prefer SQL aggregates:

- order summary aggregate;
- order-type aggregate;
- item sales aggregate;
- category sales aggregate;
- narrow completed-order headers where only timestamps/totals are required.

This avoids loading complete orders and order items repeatedly, reduces serialization, and makes query behavior scale with result groups rather than raw historical rows.

Business-time boundaries remain authoritative. Optimization must never replace branch-local date conversion with server-local `CURRENT_DATE` shortcuts.

### 6.8 AI business-data retrieval reuse

Primary implementation: `backend/app/services/assistant_tool_executor.py`.

The executor keeps request-local caches keyed by:

```text
date_from, date_to, branch_id, business_timezone
```

Related tools reuse:

- sales summary;
- order type mix;
- item sales aggregates;
- broader order metric bundles when needed.

Top and least items share one item aggregate retrieval. The executor explicitly ends tool-read transactions before waiting on an external model.

The cache is request-local, not cross-tenant global state. This is the correct scope for reusing business data during a compound assistant question.

### 6.9 Fixed-cost inventory deductions

Primary implementation:

- `backend/app/repositories/inventory_repository.py:apply_stock_deltas`
- `backend/app/services/order_service.py`

Order completion previously risked per-ingredient reads/locks/updates. The batch path:

1. combines deductions per inventory item;
2. validates account/branch scope;
3. loads and locks required branch-stock rows in deterministic item-ID order;
4. validates availability after locks are acquired;
5. applies all deltas;
6. creates movement rows and flushes as one transactional unit.

Benefits:

- query cost is bounded rather than proportional through repeated service calls;
- deterministic locking lowers deadlock risk;
- concurrency and insufficient-stock correctness remain intact;
- tenant-owned catalog and branch-owned stock remain separate.

### 6.10 Hot-path indexes

Migration: `backend/alembic/versions/20260820_0042_performance_indexes.py`.

Indexes were aligned with common scoped predicates:

| Table | Composite index columns |
|---|---|
| restaurant_tables | branch_id, active, status |
| employees | branch_id, active |
| time_logs | branch_id, clock_in |
| time_logs | branch_id, clock_out |
| orders | branch_id, status, completed_at |
| orders | branch_id, status, created_at |
| orders | branch_id, created_at |
| order_items | order_id |
| order_payments | order_id, status, reversal_status |
| recipe_ingredients | account_id, menu_item_id, active |
| inventory_movements | account_id, branch_id, timestamp |
| expenses | branch_id, date |
| app_settings | account_id, id |
| employee_day_off_requests | account_id, branch_id, status, created_at |

PostgreSQL builds these concurrently to avoid long write locks. A failed concurrent build is detected and repaired on retry rather than silently skipped as if valid.

Do not copy this index list blindly into another product. Derive indexes from actual `WHERE`, `JOIN`, and `ORDER BY` patterns and verify with `EXPLAIN (ANALYZE, BUFFERS)` at representative scale.

### 6.11 External HTTP connection reuse

Primary implementation:

- `backend/app/services/ai/http_client.py`
- `backend/app/services/external_http_client.py`

Long-lived process/event-loop-local `httpx.AsyncClient` instances provide bounded connection pools and keep-alive. They are reused for AI, STT/TTS, receipt/provider, and push operations where integrated.

Clients are keyed by event loop because an async client cannot safely move across loops. Shutdown closes clients through FastAPI lifespan cleanup.

This removes repeated DNS, TCP, and TLS setup from common provider calls while avoiding cross-loop test/runtime bugs.

### 6.12 Provider health and latency budgets

Primary implementation: `backend/app/services/ai/provider_health.py` and provider services.

A short-lived circuit tracks repeated provider failures. The default policy opens after two relevant failures and cools down after 30 seconds. Success resets the state.

This prevents every request from paying the full timeout of a known-unhealthy primary provider while still allowing recovery. It is deliberately not a permanent disable switch.

Provider tracing records attempt outcome, fallback status, duration, and TTFB where available.

### 6.13 Progressive AI response and voice

Primary implementation:

- `backend/app/routes/ai.py`
- `backend/app/services/ai/gemini_client.py`
- `backend/app/services/ai/tts_service.py`
- `mobile/src/api/client.js`
- `mobile/src/utils/aiVoiceStreaming.cjs`
- `mobile/src/screens/AiAssistantScreen.js`

Old voice path:

```text
complete STT
-> complete assistant
-> refetch history
-> complete TTS file
-> base64 JSON transfer
-> write/decode whole file
-> play
```

Improved path:

```text
complete STT
-> assistant POST returns authoritative answer/message IDs
-> render answer immediately
-> reconcile history/thread list in background
-> request streaming TTS
-> backend forwards NDJSON metadata/audio/done events
-> mobile parses arbitrary transport chunks incrementally
-> PCM segmenter emits the first playable segment
-> playback begins while remaining speech arrives
```

Cancellation aborts the stream and stops further dispatch/playback. Complete-file fallback is forbidden after streamed audio has begun, preventing duplicate speech. Invalid or oversized TTS input is rejected before provider work.

The target was to move normal time to first useful audio from approximately 20–25 seconds toward 5–8 seconds, ideally near or below 5 seconds. That remains a target until production traces show the distribution by STT, assistant, provider TTFB, first audio chunk, device buffering, and playback start.

### 6.14 Transaction lifetime

Long external waits should not retain database transactions or stock/staff locks. The optimized patterns explicitly commit or end short allowance/tool-read transactions before provider upload/stream/model waits.

Do not move required durable writes after the response indiscriminately. Chat message durability, payments, stock, attendance, idempotency, and required audit records remain part of the authoritative transaction where necessary.

### 6.15 Notification outbox

Primary implementation:

- `backend/app/services/notification_service.py`
- `backend/app/routes/notification_outbox.py`
- `backend/alembic/versions/20260822_0043_notification_outbox.py`

Old mutation path could wait for Expo push delivery. The improved path:

```text
business mutation
-> write idempotent outbox event in transaction
-> commit source of truth
-> return success
-> background/scheduled dispatcher claims due events
-> provider I/O occurs without the business transaction or locks
-> mark delivered or schedule exponential retry
```

Events use leases so crashed workers become retryable. Poison events are isolated so one failure does not abort the batch. Push failure no longer makes a successful inventory/staff mutation look failed.

### 6.16 Client request correlation

Desktop and mobile clients generate/forward request IDs, retain `Server-Timing`, and only retry safe methods automatically. This allows a user interaction to be traced across client, API, SQL, and provider attempts without risking duplicate financial/inventory mutations.

---

## 7. Before/after architecture matrix

| Area | Older behavior | Improved behavior | Evidence |
|---|---|---|---|
| Desktop Reports revisit | Empty local state, placeholder, 3–5 requests | Cached report immediately; fresh revisit makes 0 requests | Production-observed problem; desktop acceptance/contract-tested fix |
| Desktop major screens | Screen remount discarded data | Central scoped memory/persistent cache and retained UI state | Static + contract-tested |
| Mobile screen revisit | Skeleton and repeated fetch | Memory/device cache first, then quiet revalidation | Static + contract-tested |
| Cache persistence | Unbounded/ad hoc patterns | Versioned, size/entry/retention bounded, pruned | Contract-tested |
| Duplicate requests | Overlapping effects could duplicate | One in-flight promise per exact scoped key | Contract-tested |
| Refresh failure | Error/empty state could replace data | Last successful data remains visible | Contract-tested |
| Kitchen polling | Response-driven loop possible | Stable interval, no overlap, unmount cleanup | Contract-tested |
| Order History payments | Per-order N+1 requests | Batched summary request/cache | Contract-tested |
| Dashboard backend | Roughly 12–13 SELECTs | Purpose-built one-round-trip aggregate path | Baseline observed; new path static/contract-tested |
| Auth context | Roughly eight preliminary queries | Joined user/account/branding/branch, eager access rows, bulk settings | Baseline observed; new path static/contract-tested |
| Reports/AI metrics | Broad ORM loads/repeated retrieval | Narrow SQL aggregates and request-local reuse | Static + contract-tested |
| Order completion inventory | Per-ingredient work | Fixed-cost batch load/lock/update | Static + service tests |
| DB connection | Frequent remote setup | Small warm pool compatible with transaction pooler | Static; production timing required |
| External HTTP | New clients/repeated handshakes | Event-loop-local keep-alive clients | Contract-tested |
| Provider fallback | Repeated slow-primary timeout | Short-lived circuit and attempt telemetry | Contract-tested |
| AI answer display | History reconciliation could gate answer | POST answer/IDs rendered first; reconciliation backgrounded | Contract-tested |
| AI voice | Whole-file generation/transfer before play | Progressive provider/backend/mobile stream and segmented playback | Contract-tested; production latency required |
| Push notifications | Provider delivery could block mutation | Durable post-commit outbox with retry | Contract-tested |
| Production startup | Schema/seed/repair could run on cold start | Explicit startup mutation guard | Static + configuration review |

---

## 8. Tests and current verification evidence

Focused verification rerun on 2026-08-25:

```text
Backend performance + notification outbox: 15 passed
Mobile cache + waiter + AI streaming contracts: 14 passed
Desktop performance/cache unit suite: 17 passed
```

The tests prove contracts such as:

- safe request correlation and `Server-Timing`;
- provider circuit open/reset behavior;
- event-loop-safe HTTP client reuse;
- progressive NDJSON audio forwarding and parsing;
- cancellation and fallback gating;
- answer rendering before history reconciliation;
- assistant aggregate sharing;
- outbox idempotency, post-commit provider work, poison-event isolation, and retry;
- cache tenant/branch/user/filter isolation;
- fresh revisit with no fetch;
- stale data remaining visible;
- refresh failure preservation;
- single-flight request deduplication;
- scoped invalidation;
- cache pruning/versioning;
- waiter authoritative mutation updates;
- Kitchen polling cadence contract;
- Order History payment batching;
- Reports fresh revisit returning before report requests.

These are behavioral tests, not load tests. A future project still needs production percentile measurements.

---

## 9. Reusable engineering playbook for a future AI agent

### Phase 1: establish the baseline

1. Map the full user interaction, not just the endpoint.
2. Record time to first visual/audio feedback separately from completion time.
3. Count HTTP requests, SQL queries, DB connects, provider attempts, and post-mutation refetches.
4. Separate cold and warm measurements.
5. Label all findings by evidence quality.
6. Capture representative production data volumes and network geography.

Recommended baseline table:

| Flow | TTF useful output | Total | HTTP count | SQL count/time | DB connect time | Provider time/TTFB | Cache state |
|---|---:|---:|---:|---:|---:|---:|---|

### Phase 2: fix perceived-speed lifecycle

1. Find screens that unmount and recreate empty state.
2. Create one central query/cache abstraction.
3. Design the complete scope key before caching anything.
4. Return cached data synchronously from memory where possible.
5. Distinguish `initialLoading` from `refreshing` and `refreshError`.
6. Add resource-specific stale times and separate retention.
7. Dedupe identical in-flight requests.
8. Persist only appropriate bounded read data.
9. Hydrate alongside session restoration.
10. Ensure 401/403 and scope changes remove or lock cached data.

### Phase 3: reduce request amplification

For each mutation, create a dependency map:

```text
mutation
-> authoritative entities returned
-> local cache entries updated
-> dependent resources marked stale
-> optional background reconciliation
```

Do not use `refreshEverything()` unless the mutation genuinely changes everything.

### Phase 4: reduce database/network orchestration

1. Instrument query and connection time.
2. Collapse repeated authorization graph loads without weakening checks.
3. Bulk-load repeated settings/context rows.
4. Replace broad ORM loading with narrow projections/aggregates.
5. Reuse results inside one request/compound operation.
6. Batch repeated row operations with deterministic locking.
7. Add indexes matching real scoped predicates.
8. Reuse safe database and HTTP connections.
9. End transactions before long external waits.
10. Keep ancillary provider work outside the source-of-truth critical path using a durable outbox where needed.

### Phase 5: progressive delivery

1. Identify useful partial output.
2. Ensure streaming reaches the client; provider streaming followed by backend buffering is not progressive delivery.
3. Define first playable/renderable thresholds.
4. Support cancellation across client, network, backend, and provider.
5. Prevent fallback from duplicating already-delivered output.
6. Reconcile durable history in the background only after authoritative IDs/content are visible.

### Phase 6: prove the result

Minimum proof:

- fresh revisit request count;
- stale revisit behavior;
- simultaneous-request deduplication;
- tenant/branch/user/filter isolation;
- mutation request count;
- query count and plan at representative scale;
- p50/p95/p99 total latency;
- cold versus warm latency;
- time to response start;
- AI provider TTFB and time to first audio;
- refresh/offline/provider failure behavior;
- concurrency and authorization regression tests.

---

## 10. Non-negotiable invariants

Performance work must preserve:

1. **Tenant isolation:** every query and cache entry has sufficient account/branch scope.
2. **User/role isolation:** role-sensitive cached views cannot cross users or contexts.
3. **Authorization authority:** cache never grants access; backend access failures invalidate/lock data.
4. **Business timezone:** today/week/month boundaries remain restaurant/branch authoritative.
5. **Financial correctness:** no fabricated payment/report results.
6. **Inventory concurrency:** batch optimization retains locks, validation, and atomicity.
7. **Idempotency:** retries must not duplicate writes or notifications.
8. **Durability:** noncritical work may move off-path; source-of-truth writes may not be silently lost.
9. **Logical dates:** day-off and other calendar dates must not shift through timestamp conversion.
10. **Bounded storage:** no unbounded report history or serialized cache growth.

---

## 11. Anti-patterns to avoid

Do not:

- optimize only endpoint execution while the client still renders a placeholder;
- use a global cache key such as `inventory:list`;
- use one TTL for every resource;
- clear data at the start of every refresh;
- persist every API response forever;
- globally clear all caches after normal mutations;
- make stale data an authorization mechanism;
- cache generated AI operational answers as current truth;
- add `useMemo` or indexes indiscriminately without evidence;
- parallelize queries on one `AsyncSession` with unsafe concurrent use;
- create a large DB pool per serverless instance;
- enable `pool_pre_ping` without measuring its remote round-trip cost;
- break transaction-pooler compatibility with prepared statements;
- keep DB transactions open during long STT/LLM/TTS/provider waits;
- call provider APIs before committing a successful business mutation;
- claim streaming when the backend or client buffers the whole result;
- optimistically modify financial totals that the backend has not confirmed;
- use server/device local time for business-day filtering;
- treat contract tests as production latency benchmarks.

---

## 12. Remaining limitations and future measurement work

The current architecture is substantially better, but the following still require production verification or future work:

- Obtain p50/p95/p99 traces for representative endpoints and user flows.
- Confirm Vercel compute, Supabase, and provider region alignment in deployed infrastructure.
- Quantify cold-start frequency and first-request import/startup cost.
- Measure database pool wait under real concurrent restaurant traffic.
- Run `EXPLAIN (ANALYZE, BUFFERS)` using production-scale anonymized data.
- Measure public-menu latency, payload size, and image/CDN behavior after deployment.
- Measure AI voice phases from recording stop through first audible frame on physical Android devices.
- Track cache hit ratio, hydration duration, cache-envelope size, and revalidation failure rate.
- Watch mobile full-envelope persistence as cache usage grows; shard only if measurements justify it.
- Review remaining one-off `httpx.AsyncClient` usages in image-storage/Supabase helpers before generalizing reuse.
- Continue monitoring short-TTL live resources such as kitchen, tables, orders, and stock.
- Keep platform-admin/support data conservative because it is sensitive and frequently authoritative.
- Address existing datetime deprecation warnings separately without changing logical date semantics during unrelated performance work.

---

## 13. Agent handoff checklist

Before an AI agent starts a similar project, provide this document and require it to answer:

- What is the measured slow user flow?
- What is time to first useful output versus completion?
- How many client requests and SQL queries occur?
- Which work is serial but independent?
- What cache already exists?
- What is the complete tenant/branch/user/filter key?
- What data is safe to display stale?
- What is the resource-specific stale time and retention?
- Which mutation response is authoritative?
- Which exact cache keys depend on that mutation?
- Which writes/provider calls are required before response?
- Which work can move to an outbox/background phase?
- What locks/idempotency/auth/timezone invariants must remain?
- What tests prove isolation, deduplication, failure behavior, and concurrency?
- What production traces will prove the latency improvement?

The desired final interaction should be evaluated against this model:

```text
User action
-> acknowledgement within one frame where possible
-> cached or optimistic-but-safe useful state
-> one deduplicated authoritative request
-> narrow indexed backend work
-> immediate authoritative client update
-> quiet targeted reconciliation
-> durable noncritical follow-up outside the first-result path
```

That is the core performance approach that made CorePOS feel faster and made the backend do materially less unnecessary work.

