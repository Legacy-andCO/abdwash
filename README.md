# Trifecta

Trifecta is a mobile car-care platform. This monorepo contains the production customer website, the independently distributed staff operations app, shared TypeScript concepts, and the authoritative FastAPI/PostgreSQL backend.

The platform is a modular monolith: Supabase provides PostgreSQL and Auth, FastAPI owns all business workflows and authorization, Next.js serves the customer experience, and Expo/React Native serves employees, managers, and admins. Customer-facing and staff-facing interfaces use the Trifecta brand; selected legacy infrastructure identifiers remain stable for deployment compatibility.

### Stable legacy infrastructure identifiers

The product brand is Trifecta, but these deployed identifiers intentionally retain their original spelling. Rename them only through a separately planned infrastructure migration:

- Android namespace/application ID and Kotlin package: `com.abdwash.staff`. Changing it creates a different Android application identity and breaks normal upgrades and app-scoped storage.
- Expo/EAS slug: `abdwash-staff`, plus the existing EAS project ID in `apps/mobile/app.json`. Changing either can disconnect builds and updates from the distributed app.
- Persisted mobile cache/revision keys beginning `abdwash:`. Changing them without a cache migration discards installed-app state.
- Staff synthetic Supabase Auth domain: `staff.abdwash.local`. Changing it would make existing staff identities unreachable through username login.
- Seeded business slug: `abdwash`. It is a database lookup key referenced by existing tenant data.
- Existing Vercel deployment origins under `abdwash.vercel.app` and `abdwash-vdtc.vercel.app`. They remain live deployment addresses until domains/projects are migrated.
- Supabase Cron job `abdwash-notification-dispatch` and Vault names `abdwash_outbox_dispatch_url` / `abdwash_outbox_dispatch_secret`. Renaming them in source alone would duplicate or disconnect the deployed schedule and secrets.
- Existing local/example PostgreSQL database name `abdwash`. It is infrastructure configuration, not customer-visible branding.
- Applied Alembic revision files and their historical repair NOTICE text. Applied migration history is immutable.
- The repository/workspace directory may continue to be named `abdwash`; changing a local checkout path is outside application behavior.

## Current implementation status

### Customer website

- Trifecta visual system with centralized warm-cream, dark-brown, and orange brand tokens.
- Complete English and Arabic customer UI with a persistent language selector, `en-AE`/`ar-AE` presentation, and real LTR/RTL document direction.
- Responsive landing, service catalogue, contact, authentication, booking, account, profile, booking-detail, secure management, and confirmation pages.
- Guest booking and optional Supabase customer authentication; login is never required to book.
- Email/password signup, PKCE email confirmation, session restoration, logout, and authenticated API bearer tokens.
- Real catalogue with server-owned vehicle-type pricing and optional add-ons, timezone-aware availability, atomic temporary holds, idempotent booking submission, and Pay After Service. The booking UI shows the matching vehicle price and add-on total, while the backend independently recalculates every minor-unit amount and enforces any enabled mobile minimum.
- One- or two-vehicle bookings consume one slot; three or more vehicles require two consecutive slots under the current seeded settings.
- International phone entry with UAE as the default and independent E.164 normalization/validation in the browser and backend.
- Google Places search, browser geolocation on explicit user action, reverse geocoding, responsive map preview, map click selection, and a draggable advanced marker.
- A shared singleton Google Maps loader supports hard refresh, client navigation, remounts, delayed readiness, and an accessible manual-address/validated Google Maps-link fallback.
- Authenticated customer profiles with reusable personal information, default/saved service locations, saved vehicles, and booking autofill without mutating historical booking snapshots. Saved vehicles are selected within each booking vehicle slot, so multi-car bookings preserve order, per-car service, and reward allocation while preventing accidental duplicate saved-car selection.
- Trifecta Rewards for authenticated customers: every completed, fully paid normal vehicle service earns one ledger credit; nine credits create one configurable free-service reward. Available rewards can be atomically reserved in booking, released on approved cancellation, and redeemed on completion.
- Customer reward progress, available/redeemed rewards, and concise wash history are visible in the bilingual account profile; eligible rewards can be applied to one matching vehicle/service line without client-controlled pricing.
- Customer account views for upcoming, history, and cancelled bookings; detailed live job status and estimated arrival when available; authorized rescheduling and cancellation requests.
- Secure guest booking management through a signed token held in the URL fragment rather than a public booking ID.
- Retry-safe booking UX preserves entered data and reuses the same idempotency key after uncertain network outcomes.

### Staff mobile application

- Production Expo/React Native operations app branded as Trifecta Staff; it is no longer a placeholder scaffold.
- Username/password staff login backed by Supabase Auth. The app converts normalized usernames to internal synthetic staff email identities; legacy staff email login remains temporarily compatible when the entered identifier contains `@`.
- Server-authoritative employee, manager, and admin capabilities. Hiding a mobile control is never the authorization boundary.
- Role-aware navigation:
  - Employees: Today, Jobs, Profile.
  - Managers/admins: Today, Jobs, Team, Reports, Profile.
- Today and paginated Jobs views for today, upcoming, history, unassigned, and all work.
- Server-side, case-insensitive partial customer-name search on Jobs → All with scoped query-cache keys.
- Job detail with customer, vehicle, service, location, payment, assignment, and append-only event timeline information.
- Operational lifecycle: `assigned → en_route → arrived → in_progress → completed`, with explicit cancellation/unassignment paths where permitted.
- Start Trip captures a bounded one-time GPS location, requests a server ETA through Google Routes when configured, queues the customer en-route notification, and still enters `en_route` if routing is unavailable.
- Navigation/call actions, arrival confirmation, active wash timer, completion confirmation, and authoritative cash-payment recording.
- CorePOS-style cash tender records the exact amount due, cash handed over, and change in integer minor units; quick tender amounts and uncertain-retry idempotency are supported without inflating collected revenue.
- Job quality controls on Job Detail: lightweight arrival inspection, categorized private before/after/damage/issue photos, service-specific snapshotted checklists, issue reporting, and a concise completion summary. Required checklist items are enforced by the backend; historical jobs without snapshots remain valid.
- Manager/admin quality review with staff/timestamp attribution, complaint review, and zero-value linked correction/rewash jobs scheduled through the existing availability and hold engine. The original completed job and revenue remain unchanged.
- Deterministic smart scheduling auto-assigns confirmed mobile bookings to eligible teams using immutable duration snapshots, real overlap checks, the configured turnaround buffer, and balanced same-day workload. Manager/admin Auto Assign and manual selection preserve tenant scope; turnaround-only conflicts require explicit override and true overlaps remain forbidden.
- Team and staff management, role hierarchy, team membership, shifts and shift assignments, attendance clock-in/out and overview, leave requests/review, cancellation review, and operational reports.
- Authorized staff password reset with manual or temporary-password flows. Temporary resets force a password change before normal app access; passwords are never stored in application tables or logs.
- Self-service profile editing and password change.
- Manager/admin customer management is reachable from Today and provides tenant-scoped paginated search by name, phone, email, or plate; safe profile, saved-location, saved-vehicle, booking/job history, and audited loyalty controls reuse the existing customer architecture.
- TanStack Query caching, selected AsyncStorage persistence, scope-aware cache keys, last-updated/offline read states, pull-to-refresh, foreground/network synchronization, and revision-based targeted invalidation.
- Online authority for all operational and financial writes. There is intentionally no offline mutation replay queue yet.
- Manager/admin Finance area with authoritative booked-versus-collected reporting, expense ledger/category summaries, operational profit/margin, direct team contribution, and cash handover reconciliation. Employees see only their own collected/awaiting-handover cash summary.
- Manager/admin Inventory area with controlled consumable catalogue, main/shop, mobile-team and named-van stock locations, low/out alerts, bounded search, append-only movement history, batch receiving, atomic transfers, usage, wastage, stock counts, and optional receipt-to-expense recording. Every active tenant is backfilled with an idempotent primary Main Shop when no active main location exists; the mobile forms auto-select a sole location, explain disabled actions, and offer role-aware recovery when none exists. Employees can view their active team stock and record assigned-job usage only.
- First successful job completion snapshots each performed service's current expected-consumables template and records safe, job-linked usage from the assigned team's unambiguous van/mobile-team stock. Recorded shortage, zero stock, inactive items, or an unresolved source never blocks customer completion: stock stops at zero and the immutable shortfall enters the manager Inventory **Needs review** queue.
- Manager Job Detail shows expected, automatically recorded, pre-completion manual, and later additional manual usage. It also exposes existing same-business job-linked Finance expenses as a separate direct-expense section; automatic consumable usage never creates a Finance expense.
- Manager/admin Services & Pricing area for catalogue CRUD, mobile/shop channel flags, activate/deactivate, per-vehicle prices, expected duration, optional add-ons, weekday operating hours, controlled 60/90/120-minute slot settings, cancellation cutoff, mobile minimum, loyalty reward-service selection, and expected-consumables templates. Employees may read operational catalogue/settings data but cannot mutate it.
- Checked-in Android native project with safe-area and edge-to-edge keyboard/IME handling.

### Backend and platform

- FastAPI modular monolith with versioned public, customer, staff, and internal APIs.
- Async SQLAlchemy/asyncpg with a single lifespan-managed engine, bounded/recycled LIFO pool settings, measured checkout wait, short-lived request sessions, and optional prepared-statement disabling for transaction poolers.
- Evidence-labelled performance architecture with request/query baselines, tenant/role-scoped mobile SWR caching, web single-flight resources, query-count regression ceilings, safe provider timing, and a production verification checklist in [`docs/PERFORMANCE_ARCHITECTURE.md`](docs/PERFORMANCE_ARCHITECTURE.md).
- Supabase JWT verification with issuer, audience, expiry, algorithm, subject, and cryptographic signature validation.
- Resilient JWKS caching retains the last successful key set beyond its freshness TTL. Timeout, network, and provider 5xx refresh failures use a matching stale key; unknown `kid` values force refresh for key rotation; an outage without a usable key returns `503 AUTHENTICATION_SERVICE_UNAVAILABLE` rather than a false `401`. Genuine invalid tokens remain `401`; legacy HS256 verification remains available only when explicitly configured.
- Authoritative staff role, active state, business, and branch/resource scope are loaded from PostgreSQL rather than user-editable JWT metadata.
- Atomic scheduling through advisory locks, row locks, unique resource/start invariants, expiring hold groups, weekday operating hours, and immutable booking/service/vehicle snapshots. Confirmed service and add-on snapshots retain the charged prices and expected durations even after the owner edits the catalogue.
- Customer profile/address/vehicle ownership enforcement and profile provisioning before a customer's first booking.
- Server-side job filters, customer-name search, bounded pagination, bulk relationship loading, database aggregation, and N+1 safeguards.
- Durable notification outbox with `FOR UPDATE SKIP LOCKED`, stale-claim recovery, bounded batches, attempt counts, exponential retry, and provider calls outside database transactions.
- Tenant-scoped job-quality records and private Supabase Storage photo evidence. FastAPI chooses every object path, grants retry-safe signed uploads, verifies uploaded metadata, and issues short-lived signed reads without persisting signed URLs.
- Resend transactional booking-confirmation and driver-en-route email through the existing notification-provider abstraction; development can use the log provider.
- Persistent notification worker for long-lived hosts and an authenticated bounded one-shot dispatcher for serverless deployments.
- Supabase Cron + `pg_net` schedule support for one-minute dispatcher invocation, with URL and secret stored in Supabase Vault.
- Payment abstraction and safe provider-reference schema. Pay Now and real card capture are not implemented; PAN, CVV/CVC, PIN, track data, and other raw card credentials must never enter Trifecta.
- Append-only loyalty events, durable available/reserved/redeemed reward records, reward pricing snapshots, and transaction-level cash tender/change fields preserve auditability and historical financial truth.
- Auditable operational-finance ledger with integer-minor-unit expenses, active/voided correction history, actor attribution, bounded server-side filtering/pagination, and business-timezone aggregates.
- Tenant-scoped inventory ledger with `NUMERIC(14,3)` quantities, authoritative non-negative balances, deterministic row locking, retry-safe operation IDs, team-linked locations, append-only movements, service-consumption templates, immutable per-job consumption runs/lines, manager discrepancy review, RLS, and selective inventory sync revisions.
- Cash reconciliation derives expected liability only from successful cash payment transaction amounts, attributes each payment to its recording staff member, prevents active double reconciliation, records exact/short/over handovers, and preserves void/replacement history. Tender and change never inflate revenue or expected cash.
- Scoped idempotency records, append-only job events with client-event deduplication, optimistic versioning, audit events, and domain-specific sync revisions.
- Structured request telemetry with correlation IDs, route templates, total/auth/staff-context/SQL/application timings, query counts, cold-process state, and sanitized provider/auth diagnostics.
- Explicit CORS origins, backend-only service credentials, no direct browser/mobile access to business tables, and RLS defense in depth.

## Important current limitations

- Pay Now, saved-card creation, payment-provider capture, refunds through a real gateway, NFC, and Tap-to-Pay are not implemented.
- The mobile app is English-only in this phase; English/Arabic localization applies to the customer website.
- Cached mobile reads are available offline, but operational writes require connectivity and an authoritative server response.
- Background/live employee tracking, durable offline mutation replay, WhatsApp, subscriptions, corporate credit, commissions, AI assistance, and multi-branch management remain deferred.
- Supplier catalogues, purchase orders, supplier pricing, inventory valuation/COGS, fleet management, vehicle-specific/add-on recipe matrices, and fixed-asset/equipment tracking are not implemented. Standard service templates now drive prospective completion-time stock usage, but remain operational estimates rather than physical or accounting truth. Vans are currently named stock locations rather than fleet records.
- Customer availability and atomic holds now reflect real active-team capacity. One booking uses one team; service/add-on minutes are summed across its vehicles with the existing one-slot/two-slot rule retained as a conservative minimum. Team identities remain private in public APIs. GPS, traffic, route scoring, geographic clustering, and continuous schedule optimization remain intentionally deferred.
- Expense receipt uploads and full accounting functions such as a general ledger, tax filing, payroll, bank feeds, and arbitrary cost allocation remain deferred. Current profit is explicitly operational profit: collected revenue minus active recorded expenses.
- Google Maps/Places and routing depend on correctly enabled APIs, billing, map ID, and restricted browser/backend keys. Manual address entry remains available when Maps is unavailable.

## Repository structure

- `apps/web` — Next.js App Router customer website; use this as the Vercel web root.
- `apps/mobile` — Expo/React Native staff application plus checked-in Android project.
- `packages/shared` — intentionally small shared TypeScript concepts. Prefer generated OpenAPI types for future API-contract expansion.
- `backend` — FastAPI application, SQLAlchemy models, Alembic migrations, integrations, CLI seeders, worker, and tests.
- `supabase` — idempotent Supabase operational SQL, currently including notification dispatch scheduling.
- `docs` — architecture, data model, deployment, mobile operations, performance, scheduling, security, and state-machine detail.

## Core workflows

### Booking

```text
catalogue
→ customer/contact/location/vehicles
→ real availability
→ atomic temporary hold
→ review and Pay After Service
→ idempotent booking confirmation
→ durable confirmation email
→ customer account or signed management link
```

Booking states are:

```text
pending_payment → confirmed → cancellation_requested → cancelled
                            ↘ completed
```

Cancellation rejection restores `confirmed`; `cancelled` and `completed` are terminal.

### Staff job execution

```text
unassigned → assigned → en_route → arrived → in_progress → completed
```

Applicable non-terminal states can transition to `cancelled`; an assigned job can be unassigned by an authorized workflow. The backend owns transition validation and authoritative timestamps.

### Notification delivery

```text
booking/job transaction
→ notification_outbox
→ persistent worker OR secured bounded dispatcher
→ Resend/log provider
→ sent or exponential retry
```

### Mobile synchronization

```text
app foreground / connectivity restored / periodic check
→ fetch domain revision counters
→ invalidate only changed scoped query families
→ refresh active views
```

### Operational finance

```text
successful cash payment transaction (recording staff is accountable collector)
→ unreconciled cash queue
→ manager confirms declared handover
→ exact / short / over reconciliation with immutable payment links
→ void with reason and create replacement if correction is required
```

```text
booked booking snapshots + successful payment transactions + active expense ledger
→ bounded server-side aggregates
→ Reports / Finance overview, expense mix, cash status, and direct team contribution
```

General expenses are not arbitrarily allocated to services, teams, or employees. Direct team contribution includes only expenses explicitly linked to that team.

### Job quality and correction

```text
arrived → inspection + before/damage evidence
in_progress → service checklist + after/issue evidence
required checklist complete → completed
manager complaint → resolve/reject OR approve scheduled zero-value rewash
rewash follows the normal job lifecycle → complaint resolved
```

### Inventory

```text
catalogue item + main/team/van location
→ opening balance or receipt
→ authoritative InventoryStock row
→ append-only InventoryMovement audit
→ transfer / confirmed job usage / wastage / physical-count adjustment
→ inventory revision invalidates only affected mobile inventory reads
```

A receipt can optionally create one linked `chemicals_supplies` expense in the same transaction. Retries reuse the original inventory operation and never create duplicate stock or expense. Receipt costs are operational metadata only: FIFO, weighted-average valuation, COGS, and accounting journals are intentionally outside this phase.

On the first successful `in_progress → completed` transition, current service templates become an immutable job-consumption snapshot. Repeated items are aggregated before deterministic stock locks; applied usage is capped at recorded availability and any difference is retained for manager review. Existing job-linked manual usage recorded before completion satisfies the expected amount first, preventing rollout double deduction. Later manual usage remains a separate additional-usage movement. See [`docs/service-consumption.md`](docs/service-consumption.md).

## Requirements

- Node.js 22 or newer.
- npm 11 or newer.
- Python 3.13.
- PostgreSQL 15+ for migrations and integration tests.
- JDK 17 for the Android compile/release check.
- The intended Supabase project for shared environments. Confirm the project reference before applying migrations or seeds.

## Install and run

Install JavaScript workspaces from the repository root:

```bash
npm install
npm run web
```

Run the Expo app separately:

```bash
npm run mobile
```

Prepare and run the backend:

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
python -m pip install -e ".[dev]"
# Copy .env.example to .env and supply local values.
uvicorn app.main:app --reload
```

Health endpoints:

- `GET /health` — process liveness.
- `GET /ready` — database readiness.
- Application routes are under `/api/v1`.

## Environment configuration

Copy the relevant `.env.example` file and never commit real values.

### Customer web (`apps/web`)

| Variable                          | Purpose                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `NEXT_PUBLIC_API_URL`             | Public FastAPI origin.                                             |
| `NEXT_PUBLIC_SITE_URL`            | Canonical web origin used for Supabase confirmation redirects.     |
| `NEXT_PUBLIC_SUPABASE_URL`        | Public Supabase project URL.                                       |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY`   | Public/anonymous browser Auth key; never use the service-role key. |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Browser-restricted Maps/Places/Geocoding key.                      |
| `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID`  | Production map ID for advanced markers; optional locally.          |

Without Google Maps configuration, written address and validated Google Maps-link entry remain usable.

### Staff mobile (`apps/mobile`)

| Variable                               | Purpose                      |
| -------------------------------------- | ---------------------------- |
| `EXPO_PUBLIC_API_BASE_URL`             | Public FastAPI origin.       |
| `EXPO_PUBLIC_SUPABASE_URL`             | Public Supabase project URL. |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Public mobile Auth key.      |

Only public values belong in `EXPO_PUBLIC_*`. Never embed a service-role, database, Resend, dispatch, payment, or Google Routes secret.

### Backend (`backend`)

| Variable                                                     | Purpose                                                                                            |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `APP_ENV`                                                    | `development`, `test`, `staging`, or `production`.                                                 |
| `DATABASE_URL`                                               | Async PostgreSQL/Supavisor connection URL.                                                         |
| `CORS_ORIGINS`                                               | Explicit allowed customer-web origins.                                                             |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS` | Bounded connection-pool capacity and checkout timeout.                                              |
| `DB_POOL_RECYCLE_SECONDS`, `DB_POOL_PRE_PING`                | Connection lifetime and liveness policy; tune for the selected host/pooler.                         |
| `DB_DISABLE_PREPARED_STATEMENTS`                             | Enable for transaction-mode poolers that do not support prepared-statement caches.                 |
| `SUPABASE_URL`                                               | Supabase project/Auth issuer and JWKS base URL.                                                    |
| `SUPABASE_JWT_AUDIENCE`                                      | Expected access-token audience.                                                                    |
| `SUPABASE_JWT_SECRET`                                        | Optional backend-only legacy HS256 fallback.                                                       |
| `JWKS_CACHE_TTL_SECONDS`                                     | JWKS freshness interval; default 600 seconds. Last-good keys are retained for safe stale fallback. |
| `SUPABASE_SERVICE_ROLE_KEY`                                  | Backend-only Supabase Admin access for staff provisioning/password operations and demo seeding.    |
| `DEMO_STAFF_PASSWORD`                                        | Backend-only shared demo password used only by the explicit demo seed.                             |
| `BOOKING_MANAGEMENT_SIGNING_KEY`                             | Stable backend HMAC key, at least 32 characters. Rotation invalidates existing management links.   |
| `RESEND_API_KEY`, `EMAIL_FROM`, `PUBLIC_WEB_URL`             | Transactional email and secure management-link configuration.                                      |
| `OUTBOX_DISPATCH_SECRET`                                     | Secret header value for the bounded notification dispatcher.                                       |
| `GOOGLE_ROUTES_API_KEY`                                      | Backend-restricted Routes API key for staff trip ETA.                                              |
| `JOB_PHOTO_BUCKET`                                           | Private Supabase Storage bucket for job evidence; defaults to `job-quality-photos`.                |
| `JOB_PHOTO_SIGNED_URL_SECONDS`                               | Short-lived staff photo access grant lifetime; defaults to 300 seconds.                            |
| `JOB_PHOTO_MAX_BYTES`                                        | Server-enforced uploaded object size limit; defaults to 8 MiB.                                     |
| `OUTBOX_POLL_SECONDS`, `OUTBOX_BATCH_SIZE`                   | Persistent worker cadence and bounded batch size.                                                  |
| `LOG_LEVEL`                                                  | Structured application log level.                                                                  |

Production secrets must not use `NEXT_PUBLIC_*` or `EXPO_PUBLIC_*` names.

## Database migrations and seed data

Migrations and seeds never run during API startup. Use an isolated local database while developing; back up and confirm the target before touching a shared Supabase database.

```bash
cd backend
alembic heads
alembic upgrade head
python -m app.cli.seed
```

The current Alembic head is `b91c2d7e4f60`. The migration chain includes the foundation schema, en-route/arrived job states, case-insensitive staff usernames, Operations V2 workforce features, query indexes, sync revisions/assignment repair, forced password-change state, tenant-scoped job-quality controls with a private photo bucket, loyalty ledger/reward state, customer sync revision, booking discount snapshots, auditable cash tender fields, the operational finance ledger, tenant-scoped inventory catalogue/location/balance/operation/movement/service-template tables, Phase 1 normalized service pricing/operating-hour/booking-duration snapshots, Phase 2 hold/job operational-duration plus assignment-source metadata, and prospective immutable job-consumption runs/lines with manager review state.

`python -m app.cli.seed` is idempotent and creates the Trifecta business, business settings, seven weekday-hour rows, Main Shop inventory location, Mobile Team 1, and the initial customer-facing service catalogue with canonical vehicle prices. Once a service exists, rerunning the seed does not overwrite owner-managed commercial fields.

Demo staff provisioning is a separate idempotent command:

```bash
cd backend
python -m app.cli.seed_demo_staff
```

It requires `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `DEMO_STAFF_PASSWORD`. It creates or updates the current demo usernames:

- Manager: `manager`
- Employee: `employee`

The password is read only from `DEMO_STAFF_PASSWORD` and is never printed. Staff usernames are normalized to lowercase and mapped internally to Supabase Auth identities; customers continue using normal email/password authentication.

## Notification worker and Supabase Cron

Long-lived hosts can run the persistent worker:

```bash
cd backend
python -m app.workers.notifications
```

Vercel/serverless production should invoke:

```text
POST /api/v1/internal/notifications/dispatch
X-Outbox-Dispatch-Secret: <backend-only secret>
Content-Type: application/json

{}
```

The committed `supabase/notification_dispatch_cron.sql` idempotently enables `pg_cron`, `pg_net`, and Vault and schedules `abdwash-notification-dispatch` every minute. Store these values separately in Supabase Vault:

- `abdwash_outbox_dispatch_url`
- `abdwash_outbox_dispatch_secret`

See [deployment](docs/deployment.md) for installation, verification, rotation, history inspection, and disable/remove commands.

## Tests and quality checks

Backend:

```bash
cd backend
pytest
ruff check .
mypy app
alembic heads
alembic upgrade head --sql
```

PostgreSQL concurrency/integration tests require `TEST_DATABASE_URL` pointing to an isolated local database whose name contains `test`. The suite refuses destructive execution against Supabase or another remote host.

Customer web:

```bash
npm test --workspace=@trifecta/web
npm run lint --workspace=@trifecta/web
npm run typecheck --workspace=@trifecta/web
npm run build --workspace=@trifecta/web
```

Staff mobile:

```bash
npm test --workspace=@trifecta/mobile
npm run typecheck --workspace=@trifecta/mobile
```

Android compile check after native/configuration changes:

```bash
npx expo prebuild --platform android --no-install --no-clean
cd apps/mobile/android
# Windows
gradlew.bat :app:compileReleaseKotlin
# macOS/Linux
# ./gradlew :app:compileReleaseKotlin
```

Repository whitespace check:

```bash
git diff --check
```

## Deployment summary

### Web

- Use `apps/web` as the Vercel Root Directory.
- Configure the public web environment variables above.
- Configure the exact production and intentionally supported preview origins in backend `CORS_ORIGINS`.
- Configure Supabase Auth Site URL and `/auth/confirm` redirect allow-list entries.
- Restrict the Google browser key by approved HTTP referrers and only Maps JavaScript API, Places API (New), and Geocoding API.

### Backend

- Apply pending Alembic migrations before deploying code that depends on them.
- After applying `7d3f2a9c8e41`, use the manager mobile Loyalty settings surface to confirm the enabled state, nine-wash threshold, and active reward service. The migration chooses an initial reward service only when exactly one active service exists; it never guesses by service name and never grants historical credits.
- Deploy FastAPI near the Supabase database and choose direct/session/transaction pooling appropriate to the compute model.
- Configure all backend-only secrets and a stable management signing key.
- Configure Resend and either a persistent worker or the authenticated Supabase Cron dispatcher.
- Configure backend Supabase service-role access for signed private job-photo operations. The quality migration creates or updates the private `job-quality-photos` bucket when the Supabase `storage` schema is available; otherwise create the bucket manually with the documented size/MIME restrictions before enabling uploads.
- Never run migrations, seeds, or an infinite worker loop during a Vercel request.

### Mobile

- Configure only public Expo variables.
- Regenerate/synchronize the checked-in Android project after native dependency or plugin changes.
- Build and distribute a new native binary when native code/configuration changes; JavaScript-only changes may follow the project's normal Expo release path.

## Security invariants

- Supabase Auth is the identity provider; FastAPI stores no passwords.
- Service-role, database, Resend, signing, dispatch, and routing secrets remain server-side.
- Staff authorization comes from active, tenant-scoped database profiles—not client claims or user-editable metadata.
- Customer and staff ownership/role checks are enforced by FastAPI on every protected workflow.
- Job evidence stays in a private Storage bucket. Clients receive only backend-scoped signed upload tokens and short-lived signed read URLs; stable paths, not signed URLs, are stored in PostgreSQL.
- Access tokens, passwords, raw management/hold tokens, notification recipients, and provider credentials are not logged.
- JWT verification never bypasses signature or claims validation; stale JWKS fallback uses only the last successfully parsed key matching the token's `kid`.
- Public request schemas exclude server-owned prices, roles, paid state, and lifecycle state.
- Booking management tokens are signed, kept in URL fragments, and never persisted raw in the notification outbox.
- Notification dispatch uses constant-time secret comparison and bounded batches.
- Business tables are backend-owned; browser and mobile clients do not write them through the Supabase Data API.
- Card PAN, CVV/CVC, PIN, track data, and raw payment credentials are never stored or sent through Trifecta.

## Further documentation

- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Deployment](docs/deployment.md)
- [Mobile operations](docs/mobile-operations.md)
- [Performance and observability](docs/performance.md)
- [Scheduling](docs/scheduling.md)
- [Service catalogue and Phase 1 business configuration](docs/service-catalogue.md)
- [Startup product direction](docs/STARTUP_PRODUCT_DIRECTION.md)
- [Security](docs/security.md)
- [State machines](docs/state-machines.md)
