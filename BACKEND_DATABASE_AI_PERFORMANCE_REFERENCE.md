# CorePOS Backend, Database, and AI Performance Reference

**Audience:** AI engineering agents and backend engineers working on future CorePOS-style systems.

**Scope:** Backend, database, runtime/deployment, and AI Assistant architecture. Client caching is covered in the separate `PERFORMANCE_ARCHITECTURE_REFERENCE.md`.

**Repository state reviewed:** 2026-08-27.

---

## 1. Executive summary

CorePOS did not move from multi-second interactions toward millisecond-scale backend work through one clever query. The main improvement was removing accumulated synchronous orchestration.

An older request could behave like:

~~~text
request
-> serverless startup or new DB connection
-> user query
-> account query
-> branch query
-> branding query
-> monitoring-access query
-> settings query
-> endpoint queries
-> broad ORM loading
-> Python aggregation
-> external provider or push work
-> ancillary persistence
-> commit
-> response
~~~

PostgreSQL statements were often sub-millisecond, yet the complete request took seconds because every serial remote step paid network, pooler, driver, transaction, and serialization overhead.

Observed pre-optimization symptoms included:

- warm DB-backed requests around **1–2+ seconds** despite low PostgreSQL execution time;
- roughly **eight authorization/context queries before endpoint work** on representative mobile monitoring requests;
- roughly **12–13 SELECTs** for a small Dashboard response;
- public-menu responses around **2.7–2.8 seconds** in the observed deployment;
- AI Talk around **20–25 seconds** before useful audio;
- repeated retrieval of the same sales/order data inside one AI request;
- per-ingredient inventory reads during order completion;
- business mutations waiting for push-provider delivery;
- schema/seed/bootstrap work capable of extending serverless cold starts.

After the pass, production report endpoints in the cited environment were observed around:

~~~text
/reports/sales        approximately 18–22 ms
/reports/expenses     approximately 20 ms
/reports/end-of-day   approximately 45 ms
~~~

Those are production observations for one deployment, not universal guarantees. The architecture made common warm endpoints narrow and bounded enough to run in tens of milliseconds when compute, database, load, and geography permit it.

The reusable improvements were:

1. Production-safe request, SQL, connection, phase, and provider instrumentation.
2. A small warm database pool compatible with the Supabase transaction pooler.
3. Production cold-start guards that keep migrations/seeding out of normal startup.
4. Joined authorization graphs and bulk settings/context loading.
5. Purpose-built SQL aggregates for Dashboard and reports.
6. Narrow projections instead of broad ORM graphs.
7. Request-local reuse of AI tool data.
8. Fixed-shape batch inventory deductions with deterministic locks.
9. Composite indexes aligned with real tenant/status/date predicates.
10. Short transaction boundaries around external AI and push-provider work.
11. Event-loop-local reusable HTTP clients and short-lived provider circuits.
12. A durable post-commit notification outbox.
13. Deterministic, validated AI fast paths and progressive voice delivery.

The central principle is:

> Reduce remote round trips and critical-path work before micro-optimizing code. A 0.5 ms query cannot make an endpoint fast if it is surrounded by ten network trips, a new TLS connection, broad serialization, and provider delivery.

---

## 2. Evidence rules

Future agents must label performance evidence correctly.

| Label | Meaning |
|---|---|
| **Production-observed** | Seen in deployed logs or an acceptance flow. |
| **Locally measured** | Timed in the current environment; network and hardware dependent. |
| **Contract-tested** | A test proves query count, reuse, ordering, streaming, or safety—not production latency. |
| **Static evidence** | Code has the intended architecture; its production magnitude remains unmeasured. |
| **Target** | A desired result, explicitly not a measurement. |

For every important flow, measure:

- total request time;
- response-start time;
- cold versus warm process;
- DB connection acquisition/connect time;
- SQL count and cumulative client-observed SQL time;
- transaction/commit time;
- provider attempt duration and TTFB;
- serialization/response completion;
- p50, p95, and p99.

Do not claim “milliseconds” from static code inspection alone.

---

## 3. Request architecture and observability

Important files:

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/core/performance.py`
- `backend/app/core/auth.py`
- `backend/app/repositories/`
- `backend/app/services/`
- `backend/app/routes/`

The request structure remains layered:

~~~text
FastAPI route
-> authenticated/authorized business context
-> service rules
-> repository query
-> short transaction
-> response schema
-> optional background/outbox work
~~~

### 3.1 Performance middleware

`PerformanceMiddleware` in `backend/app/core/performance.py` records:

- sanitized request ID;
- HTTP method and FastAPI route template;
- total duration;
- time to response headers;
- first request in process/cold marker;
- process uptime;
- SQL count and cumulative SQL time;
- DB connect count and time;
- named phases;
- provider attempts, outcomes, fallback status, duration, and optional TTFB;
- streamed-response completion.

Responses expose:

~~~text
X-Request-ID
Server-Timing
~~~

The middleware logs route templates, not user-controlled IDs, and deliberately excludes tokens, request bodies, SQL text, raw audio, complete prompts, and tenant business data.

### 3.2 SQLAlchemy instrumentation

Engine events in `backend/app/core/database.py` measure:

- connection establishment;
- successful cursor execution;
- failed cursor execution.

A context variable associates engine events with the active request. This lets an agent distinguish:

~~~text
slow SQL
vs slow connection
vs slow application phase
vs slow external provider
~~~

This distinction prevented wasted work such as adding indexes to already-fast SQL while connection/network orchestration dominated.

---

## 4. Database connection strategy

### 4.1 Problem

A connection-per-request or `NullPool` posture in a serverless environment can repeatedly pay:

~~~text
DNS -> TCP -> TLS -> pooler negotiation -> PostgreSQL protocol setup
~~~

That overhead can be much larger than the query itself.

### 4.2 Current design

Each reused process keeps a deliberately small SQLAlchemy pool. Defaults include:

~~~text
DATABASE_POOL_SIZE=1
DATABASE_POOL_TIMEOUT_SECONDS=5
DATABASE_POOL_RECYCLE_SECONDS=300
DATABASE_POOL_PRE_PING=False
~~~

Overflow is configured separately and remains small.

Reasons:

- one warm connection avoids repeated setup on a reused Vercel/Fluid process;
- small overflow supports limited concurrency;
- a bounded timeout prevents indefinite waits;
- recycle handles stale long-lived connections;
- pre-ping is off by default because it adds a remote round trip to every checkout;
- Supabase's transaction pooler already manages server-side sessions.

For `postgresql+asyncpg`, both caches are disabled:

~~~text
statement_cache_size = 0
prepared_statement_cache_size = 0
~~~

Transaction-mode poolers can move transactions between server connections, so prepared-statement assumptions can be unsafe.

### 4.3 Capacity rule

A future agent must calculate:

~~~text
maximum warm function instances
x (pool_size + possible overflow)
<= database/pooler connection budget
~~~

Do not use a large conventional pool per serverless instance.

### 4.4 Geography

`backend/vercel.json` pins compute to `fra1`. The Supabase region must be verified externally. Co-locate compute and database because every remaining serial query pays network distance even when execution is sub-millisecond.

---

## 5. Cold-start controls

Files:

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/.env.example`

Production startup previously risked performing table creation, seed repair, platform-admin creation, and mobile demo-user bootstrap.

Production now refuses those mutations unless explicitly allowed by:

~~~text
ALLOW_PRODUCTION_STARTUP_MUTATIONS=True
~~~

Normal production should configure:

~~~text
AUTO_CREATE_SCHEMA=False
SEED_ON_STARTUP=False
PLATFORM_ADMIN_BOOTSTRAP_ON_STARTUP=False
MOBILE_DEMO_USERS_BOOTSTRAP_ON_STARTUP=False
ALLOW_PRODUCTION_STARTUP_MUTATIONS=False
~~~

Alembic/deployment jobs own schema changes. A web process should become ready to serve requests, not silently become a migration or seed worker during cold start.

---

## 6. Authorization and monitoring-context collapse

Files:

- `backend/app/repositories/auth_repository.py`
- `backend/app/core/auth.py`
- `backend/app/services/auth_service.py`

### 6.1 Old cost

Representative requests repeatedly loaded:

~~~text
user
account
branding
branch
monitoring access
monitored account
monitored branch
settings
timezone
entitlements
~~~

Each query was simple but remote and serial.

### 6.2 Joined authorization graph

`AuthRepository._get_user` retrieves in one round trip:

- user;
- active branch constrained to the user's account;
- restaurant account;
- branding.

It attaches request-only metadata:

~~~text
user._auth_branch
user._auth_branch_valid
~~~

These are not persisted ORM fields. Services reuse the authorized branch rather than querying it again.

### 6.3 Monitoring access and settings

Mobile monitoring access rows eager-load their account and branch. App settings for all allowed accounts are loaded through one bulk `IN (...)` query instead of one query per context.

Fallback calls remain for lightweight test/integration repositories, but production follows the eager/bulk path.

### 6.4 Security preserved

The system still verifies per request:

- active user;
- branch/account relationship;
- account status and suspension;
- role and feature entitlements;
- monitoring-access grant;
- selected context membership;
- branch activity;
- business timezone.

The lesson is to collapse and reuse authorization work, not cache authorization indefinitely or skip checks.

---

## 7. Business-time-aware query boundaries

CorePOS uses `backend/app/services/business_clock.py` so Dashboard, reports, AI, orders, staff history, and movement history agree about “today,” “this week,” and “this month.”

Conceptual flow:

~~~text
authorized branch/account IANA timezone
-> logical local start
-> logical local exclusive end
-> convert boundaries to storage/UTC convention
-> indexed predicate: timestamp >= start AND timestamp < end
~~~

This avoids server-local `CURRENT_DATE`, phone timezone, and fixed-offset arithmetic.

A performance change must not replace correct business-time boundaries with a superficially faster but wrong server-time query. Prefer precomputed boundary parameters so the indexed timestamp column does not need an unindexable wrapper.

---

## 8. Dashboard aggregate

Files:

- `backend/app/repositories/report_repository.py`
- `backend/app/services/monitoring_service.py`

The audited Dashboard path used roughly 12–13 SELECTs for a compact response. The optimized repository method `get_dashboard_snapshot_aggregate` returns the main values in one DB round trip:

- sales and completed-order count;
- average order value;
- cash/card totals;
- low/critical inventory counts;
- table counts;
- active/ready kitchen counts.

Inputs include account, branch, business date range, and timezone.

Why this matters:

- SQL aggregates close to the data;
- one remote round trip replaces many serial trips;
- the response is one compact row;
- Python does not instantiate and traverse hundreds of ORM entities;
- JSON serialization stays small.

`MonitoringService` retains a compatibility fallback for repositories without the aggregate loader, but production uses the aggregate path.

Reusable rule:

> If an endpoint returns a dozen numbers, build a purpose-specific aggregate projection. Do not load complete object graphs to count and sum in Python.

---

## 9. Report query architecture

Files:

- `backend/app/repositories/report_repository.py`
- `backend/app/services/report_service.py`

Purpose-built loaders include:

- `get_order_summary_aggregate`;
- `get_order_type_aggregates`;
- `get_item_sales_aggregates`;
- `get_category_sales_aggregates`;
- narrow completed-order headers;
- scoped expense queries.

SQL performs `SUM`, `COUNT`, and `GROUP BY` for totals, payment/order type, item quantity/revenue, and category results.

`ReportService.collect_order_metrics` obtains a summary grouping, order-type grouping, and item grouping. Top and least items rank the same item aggregate result rather than reading order items twice.

Scaling behavior improves because:

- scanned rows are constrained by branch/status/time indexes;
- returned rows scale with groups rather than raw order history;
- Python memory is bounded;
- response payloads remain compact;
- individual endpoints use the narrowest query available.

At representative scale, verify with:

~~~sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
~~~

Check index selection, scanned rows, sort/group memory, and whether timezone predicates remain index-friendly.

---

## 10. Order completion and batched inventory deductions

Files:

- `backend/app/services/order_service.py`
- `backend/app/repositories/inventory_repository.py`

An older recipe path could perform load/validate/lock/update/movement work once per ingredient.

The current `apply_stock_deltas` path:

1. combines deductions by inventory item;
2. requires account and branch scope;
3. validates catalog/branch ownership;
4. sorts item IDs deterministically;
5. loads required catalog and branch-stock rows in bounded queries;
6. locks rows in deterministic item-ID order;
7. validates all availability after locks are acquired;
8. applies all deltas;
9. creates movement records;
10. flushes in the caller's transaction.

Benefits:

- fixed-shape query work rather than repeated service round trips;
- lower deadlock risk;
- atomic order completion;
- correct insufficient-stock handling;
- preserved account catalog and branch stock isolation;
- complete movement audit history.

Never make inventory deductions “faster” by moving them outside the order transaction or removing locks.

---

## 11. Composite performance indexes

Migration: `backend/alembic/versions/20260820_0042_performance_indexes.py`.

| Table | Indexed columns | Workload |
|---|---|---|
| restaurant_tables | branch_id, active, status | Table/dashboard state |
| employees | branch_id, active | Staff directory/status |
| time_logs | branch_id, clock_in | Attendance ranges |
| time_logs | branch_id, clock_out | Active/history attendance |
| orders | branch_id, status, completed_at | Sales/report ranges |
| orders | branch_id, status, created_at | Open/kitchen/history |
| orders | branch_id, created_at | Branch order history |
| order_items | order_id | Order-item joins |
| order_payments | order_id, status, reversal_status | Effective payment state |
| recipe_ingredients | account_id, menu_item_id, active | Recipe deduction |
| inventory_movements | account_id, branch_id, timestamp | Movement history |
| expenses | branch_id, date | Expense reports |
| app_settings | account_id, id | Deterministic settings |
| employee_day_off_requests | account_id, branch_id, status, created_at | Day-off queues |

PostgreSQL creates these concurrently to avoid long write locks. The migration detects invalid indexes left by interrupted concurrent builds, drops them, and repairs them on retry.

A future agent must derive indexes from real `WHERE`, `JOIN`, and `ORDER BY` patterns. Do not blindly add indexes: they cost storage and write performance.

---

## 12. Transaction lifetime

FastAPI provides one `AsyncSession` per request. It commits on success, rolls back on failure, and uses `expire_on_commit=False` so authoritative objects do not require immediate reload.

The optimized rules are:

- commit the assistant user's chat message before planner/provider work;
- end tool-read transactions before calling an answer provider;
- commit voice usage/allowance checks before STT/TTS provider I/O;
- commit business mutations before push delivery;
- run outbox provider I/O without source-of-truth locks;
- commit the assistant message before returning its IDs;
- record noncritical AI usage in a separate background session.

These remain synchronous/durable:

- payments and reversals;
- order status/item cancellation;
- stock deductions and movement audit;
- attendance source of truth;
- required chat messages;
- idempotency and required audit records.

The rule is not “background everything.” It is “keep required source-of-truth work synchronous and remove unrelated external waits from its transaction.”

---

## 13. Durable notification outbox

Files:

- `backend/app/services/notification_service.py`
- `backend/app/routes/notification_outbox.py`
- `backend/alembic/versions/20260822_0043_notification_outbox.py`

Old path:

~~~text
business mutation
-> push provider
-> wait
-> provider failure may make success appear failed
~~~

Current path:

~~~text
business mutation
-> enqueue idempotent event in the same transaction
-> commit
-> return success
-> background/scheduler claims due events
-> release DB transaction
-> send provider requests
-> mark delivered or schedule retry
~~~

Reliability properties:

- deterministic event keys;
- processing leases that expire after worker failure;
- no business locks during provider I/O;
- exponential retry;
- poison-event isolation;
- one event failure does not abort the batch;
- push failure never rolls back successful stock/staff state.

This is both faster and safer than calling Expo synchronously or using an undurable fire-and-forget task.

---

## 14. Reusable external HTTP clients

Files:

- `backend/app/services/ai/http_client.py`
- `backend/app/services/external_http_client.py`

Creating an `httpx.AsyncClient` per request repeats DNS, TCP, and TLS work. CorePOS caches clients per asyncio event loop using weak dictionaries.

Production limits include approximately:

~~~text
max_connections = 40
max_keepalive_connections = 16
keepalive_expiry = 30 seconds
~~~

Per-loop storage matters because async clients cannot safely cross event loops. FastAPI lifespan cleanup closes clients.

These clients are reused for assistant providers, STT/TTS, notifications, and integrated external-provider paths. Some specialized image/storage helpers still deserve a separate audit before consolidation.

---

## 15. AI Assistant architecture

The Assistant is a validated planning/retrieval system, not one unrestricted LLM call.

Key files:

- `backend/app/routes/ai.py`
- `backend/app/services/assistant_service.py`
- `backend/app/services/assistant_planner.py`
- `backend/app/services/assistant_planning_fallback.py`
- `backend/app/services/assistant_query_plan.py`
- `backend/app/services/assistant_tool_registry.py`
- `backend/app/services/assistant_permissions.py`
- `backend/app/services/assistant_tool_executor.py`
- `backend/app/services/assistant_context_service.py`
- `backend/app/services/assistant_provider.py`
- `backend/app/services/assistant_response_service.py`
- `backend/app/services/ai/`

### 15.1 Text request pipeline

~~~text
POST /ai/assistant
-> authenticate user
-> resolve authorized account/branch monitoring context
-> enforce entitlement and usage limit
-> get/create chat thread
-> persist user message
-> load bounded history only for an existing thread
-> commit DB transaction
-> deterministic compound/capability/temporal planning
-> semantic/model fallback only if uncertain
-> validate the complete plan
-> enforce tool permissions
-> execute scoped tools
-> deterministic grounded answer when possible
-> otherwise call configured answer provider
-> persist assistant message and metadata
-> commit and return answer/message IDs
-> record noncritical usage telemetry in background
~~~

### 15.2 Bounded history

A new thread skips a history query that can only return the user message just inserted. Existing threads load only the configured recent context limit. Planner fallback receives compact safe context, not an unbounded full conversation.

This keeps latency and prompt size from growing linearly with thread age.

### 15.3 Complete deterministic plan

`AssistantPlanner` resolves:

- question type;
- domain and operation;
- tool names;
- date scope, date confidence, and provenance;
- filters;
- requested metrics;
- branch scope;
- compound subplans;
- route and confidence.

The anchor date comes from the authorized restaurant/branch business clock.

Clear questions stay on the deterministic path and avoid a model-planner network call.

### 15.4 Plan validation

`validate_query_plan` enforces registered capabilities/tools, maximum tool count, filter/date structures, compound limits, and scope coherence.

Recognizing the word “sales” is not a successful plan if “this week” was lost. Temporal cue detection prevents an unresolved explicit period from silently becoming today.

### 15.5 Semantic/model fallback

Only uncertain plans escalate:

~~~text
deterministic uncertain
-> low-cost semantic selection
-> structured provider planner if needed
-> validate domain/operation/date enum/confidence
-> clarification if critical scope remains unresolved
~~~

The model may propose validated concepts like:

~~~json
{
  "domain": "sales.summary",
  "operation": "summary",
  "date_scope": "this_week",
  "confidence": 0.93,
  "date_confidence": 0.96
}
~~~

It cannot invent raw SQL timestamps, tenant scope, or unrestricted tool names.

### 15.6 Permission and scope

Each tool is permission-checked before execution. The executor receives the authorized account, branch, role, and business timezone. The LLM never chooses account or branch scope.

### 15.7 Tool-first fast path

For a clear, non-comparative, non-compound operational question:

~~~text
matched plan
-> execute registered tool
-> construct deterministic grounded answer/cards
-> skip broad context load
-> skip answer-model provider call
~~~

This reduces latency and provider cost for straightforward sales summaries, stock alerts, staff status, day-off counts, and similar questions.

### 15.8 Provider path

Nuanced questions can load bounded business context and call the answer provider. Provider input contains validated plan, authorized scope, requested ranges, tool results, safe context, language/money guidance, and a grounding rule forbidding invented facts.

If the provider fails, the backend can return a structured response from available tool data instead of losing the successful retrieval.

### 15.9 Request-local data reuse

`AssistantToolExecutor` caches data only for the current request using keys such as:

~~~text
(date_from, date_to, branch_id, business_timezone)
~~~

It reuses:

- order summary aggregate;
- order-type aggregate;
- item-sales aggregate;
- broader metrics only when specialized loaders are unavailable.

For example:

~~~text
sales summary + top items + least items
-> one summary aggregate
-> one order-type aggregate
-> one item aggregate
~~~

Top and least rank the same rows. Request-local scope prevents cross-tenant leakage or persistent stale AI facts.

### 15.10 Compound requests

Compound planning creates a bounded number of validated subplans. Results retain subplan ID, status, tools, result, duration, and safe failure type. Compatible retrieval can be reused; one failing subplan does not authorize fabricated data.

### 15.11 AI transaction and persistence flow

The route commits the user message before long planning/provider work. Tool-read transactions end before answer-provider I/O. The assistant message is committed before returning authoritative IDs.

Usage telemetry is noncritical and runs after the response via a separate session. This shortens the result path without sacrificing chat durability.

### 15.12 AI timing

The service records:

~~~text
intent detection
planning fallback
tool execution
context fetch
provider
total
~~~

The route additionally records:

~~~text
auth/context
chat history
answer
assistant-message save
total
~~~

Combined with request SQL/connect/provider tracing, this identifies whether the planner, tool SQL, provider, connection, or persistence is slow.

---

## 16. Provider resilience

Files:

- `backend/app/services/assistant_provider.py`
- `backend/app/services/ai/provider_health.py`
- `backend/app/services/ai/http_client.py`

Assistant, STT, and TTS attempts use bounded timeout configuration, commonly seven seconds by default.

A short-lived circuit breaker:

- opens after a configurable threshold, default two failures;
- cools down after a short interval, default 30 seconds;
- resets on success;
- avoids making every request rediscover the same unhealthy primary through a full timeout.

Provider telemetry records workflow, provider, duration, outcome, fallback status, and TTFB where available. It does not need prompt/audio content.

---

## 17. Progressive AI voice

Backend files:

- `backend/app/routes/ai.py`
- `backend/app/services/ai/stt_service.py`
- `backend/app/services/ai/tts_service.py`
- `backend/app/services/ai/gemini_client.py`
- `backend/app/services/assistant_voice_limits.py`

Client transport files are relevant because a backend stream must reach playback:

- `mobile/src/api/client.js`
- `mobile/src/utils/aiVoiceStreaming.cjs`
- `mobile/src/screens/AiAssistantScreen.js`

### 17.1 Old path

~~~text
recording complete
-> full upload
-> complete STT
-> complete assistant
-> history refetch
-> complete TTS generation
-> base64 JSON response
-> complete transfer/write/decode
-> playback
~~~

### 17.2 Current path

~~~text
STT
-> assistant POST returns answer and message IDs
-> text renders immediately
-> history reconciles in background
-> POST /ai/tts/stream
-> provider begins stream
-> backend forwards metadata/audio/done NDJSON events
-> client parses transport chunks incrementally
-> PCM segmenter emits first playable fragment
-> playback begins while remaining audio arrives
~~~

`POST /ai/tts/stream` uses a FastAPI `StreamingResponse` with no-transform/no-store semantics. The backend forwards real provider chunks rather than buffering the entire response.

Cancellation aborts network/provider consumption and prevents later playback. Complete-file fallback is forbidden after streamed audio begins, avoiding duplicate speech. Oversized input is rejected before provider work.

The voice usage gate stores content-free usage and commits before STT/TTS provider I/O so provider backpressure does not occupy a DB transaction.

Targets:

~~~text
old first useful audio: approximately 20–25 seconds
initial production goal: approximately 5–8 seconds
ideal normal case: <= 5 seconds
~~~

These remain targets until physical-device production traces measure recording stop, upload, STT, assistant, TTS TTFB, first chunk, first playable buffer, and playback start.

---

## 18. Why the gains compound

| Layer | Older cost | Current approach |
|---|---|---|
| DB connection | Frequent remote setup | Small warm transaction-pooler-compatible pool |
| Authorization | Several serial reads | Joined user graph, eager access graph, bulk settings |
| Dashboard | Roughly 12–13 SELECTs | One aggregate round trip |
| Reports | Broad entity loading | Narrow indexed SQL aggregates |
| AI retrieval | Context/tool duplicate work | Tool-first path and request-local reuse |
| Inventory deduction | Per-ingredient calls | Batched deterministic locks/updates |
| Indexing | Hot predicates incompletely matched | Scoped composite indexes |
| Provider clients | Repeated DNS/TCP/TLS | Reused keep-alive clients |
| Provider failure | Repeated full timeout | Short circuit and attempt budgets |
| Transactions | Open during external waits | DB phase ends before provider I/O |
| Push | Provider blocked mutation | Durable post-commit outbox |
| Startup | Seed/schema work possible | Production startup guard |
| Diagnostics | Total time opaque | SQL/connect/phase/provider timing |

Conceptually:

~~~text
Old:
many serial remote DB calls
+ connection establishment
+ broad serialization
+ provider/ancillary work
= seconds

Current:
warm connection
+ one to a few narrow indexed DB round trips
+ compact serialization
+ noncritical work outside response
= tens of milliseconds for suitable warm non-provider endpoints
~~~

AI remains provider-dependent, but deterministic operational paths can avoid an answer-model call, and voice no longer waits for a complete audio file.

---

## 19. Verification

Important tests include:

- `backend/tests/test_performance_critical_paths.py`
- `backend/tests/test_notification_outbox.py`
- business-time, service, assistant, inventory, report, auth, and concurrency tests under `backend/tests/`.

Focused verification rerun while preparing this reference:

~~~text
python -m pytest tests/test_performance_critical_paths.py tests/test_notification_outbox.py -q
15 passed
~~~

The focused contracts prove:

- safe correlation and timing headers;
- SQL count/time capture;
- provider attempt tracing;
- provider circuit open/reset;
- HTTP client reuse within, but not across, event loops;
- progressive TTS event forwarding;
- voice input bounded before provider work;
- voice usage commit before provider work;
- assistant aggregate sharing;
- outbox idempotency and post-commit provider work;
- poison-event isolation and retry.

These tests prove architecture, not production percentile latency.

---

## 20. Production measurement procedure

For every critical route/AI flow:

1. send a stable `X-Request-ID`;
2. capture `Server-Timing` and client total;
3. locate the matching `request_performance` log;
4. record cold/warm state and process uptime;
5. record SQL count/time and DB connect time;
6. record phases and provider attempts;
7. run enough samples for p50/p95/p99;
8. use representative data volume and concurrency;
9. test timezone boundaries;
10. compare before/after in the same region/configuration.

Recommended table:

| Flow | Cold/warm | p50 | p95 | p99 | SQL count | SQL ms | Connect ms | Response start | Provider TTFB | Total |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

For queries, use `EXPLAIN (ANALYZE, BUFFERS)`. For writes, test concurrent order completion, stock adjustment, payments, attendance, and idempotent retry.

---

## 21. Non-negotiable constraints

Performance work must preserve:

1. Tenant and branch isolation.
2. Account-owned inventory catalog and branch-owned stock.
3. Revocation, suspension, role, entitlement, and context checks.
4. Restaurant/branch business timezone.
5. Financial/payment correctness.
6. Inventory locks, availability validation, audit movements, and atomicity.
7. Idempotency for retries and outbox events.
8. Required source-of-truth durability.
9. Logical date semantics.
10. AI grounding and registered tools.
11. Bounded AI question/history/tool/compound/voice work.
12. Honest failure and clarification behavior.

---

## 22. Anti-patterns

Do not:

- optimize 1 ms SQL while ignoring a 500 ms connection;
- use large DB pools per serverless instance;
- enable pre-ping without measuring its extra trip;
- enable incompatible prepared-statement caching through a transaction pooler;
- run concurrent queries unsafely on one `AsyncSession`;
- load ORM graphs to compute simple counts/sums;
- aggregate years of history in Python;
- issue one query per row or ingredient;
- add indexes without real predicates and query plans;
- wrap indexed timestamps in avoidable functions;
- cache authorization indefinitely;
- weaken tenant filters for speed;
- use server time for restaurant reports;
- keep transactions open during LLM/STT/TTS/push waits;
- call push providers before business commit;
- send every assistant question to a model planner;
- let models invent timestamps, tenant scope, or raw SQL;
- fetch the same business data in context and tools;
- accept intent while losing requested date/filter scope;
- call provider output “streaming” if the backend buffers it;
- move required payment/inventory/chat durability into unreliable background work;
- report target latency as measured latency.

---

## 23. Playbook for the next AI agent

1. Trace startup, connection, auth, service, SQL, transaction, provider, persistence, and response.
2. Establish cold/warm baselines and p50/p95/p99.
3. Add safe SQL/connect/phase/provider instrumentation.
4. Verify compute/database geography.
5. Use a bounded pool compatible with the actual pooler/runtime.
6. Collapse authorization into a narrow joined graph and bulk context query.
7. Replace broad ORM reads with purpose-built aggregates/projections.
8. Reuse compatible results inside one request.
9. Batch repeated writes with deterministic locks.
10. Add only indexes supported by real query plans.
11. End transactions before unrelated external I/O.
12. Use durable outbox processing for post-commit provider work.
13. Reuse bounded HTTP clients and implement short provider circuits.
14. Give AI deterministic validated fast paths before model fallback.
15. Stream useful output end to end with cancellation.
16. Run security, timezone, concurrency, durability, and latency verification.

---

## 24. Deployment requirements and remaining limitations

Required deployment considerations:

- apply `20260820_0042_performance_indexes.py`;
- apply `20260822_0043_notification_outbox.py`;
- deploy backend code;
- configure the authenticated outbox scheduler;
- disable production startup schema/seed/bootstrap mutations;
- verify Vercel and Supabase region alignment;
- monitor DB pool capacity.

Remaining measurement work:

- continuous endpoint p50/p95/p99;
- production DB checkout/connect timing;
- cold-start frequency/import cost;
- production-scale query plans;
- public-menu payload/image/CDN profiling;
- physical Android AI first-audio traces;
- provider circuit-open rate;
- outbox backlog and oldest retry age;
- DB pool wait under concurrency;
- remaining one-off external HTTP clients.

---

## 25. Short handoff instruction

Give the next AI agent this instruction:

~~~text
Read BACKEND_DATABASE_AI_PERFORMANCE_REFERENCE.md completely before changing code.

Measure the full cold and warm request path. Preserve tenant/branch isolation, business timezone, financial correctness, inventory locking, idempotency, and required durability.

Prefer fewer remote round trips, joined authorization context, narrow SQL aggregates, request-local result reuse, deterministic batch locking, transaction-pooler-compatible connection reuse, short transaction boundaries, durable outbox processing, reusable provider clients, and validated deterministic AI fast paths.

Do not claim improvement from static code alone. Report total latency, response start, SQL count/time, DB connect time, provider attempts/TTFB, and p50/p95/p99 before and after.
~~~

The standard to reproduce is:

~~~text
warm ordinary request
-> already-authorized narrow context
-> minimal indexed SQL round trips
-> compact response
-> no noncritical provider work
-> millisecond/tens-of-milliseconds backend work when deployment conditions permit
~~~

For AI:

~~~text
validated deterministic plan when possible
-> scoped shared tool retrieval
-> grounded answer immediately
-> provider only when needed
-> durable assistant message
-> noncritical telemetry later
-> progressive audio instead of whole-file waiting
~~~

That combined architecture—not a single database trick—is how CorePOS moved from multi-second orchestration toward millisecond-scale backend behavior.



