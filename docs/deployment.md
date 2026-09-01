# Deployment notes

## Optional booking email migration (2026-08-31)

Apply Alembic revision `c6c7c3026e63` before deploying the matching API. It changes only
`bookings.customer_email` from required to nullable; authenticated `customer_profiles.email`
remains required and unchanged. Revenue invoices already keep customer contact data in an
immutable JSON snapshot, so no invoice-column migration is needed. No new environment variable
is introduced.

## Catalogue and invoicing migration (2026-08-31)

Before deploying this API phase, apply Alembic revision `c18f4a7b2d91`. It adds catalogue
feature/product metadata, business financial identity, optional booking billing snapshots,
concurrency-safe invoice numbering and immutable revenue invoices, plus expense evidence fields.
The migration activates the approved six-service catalogue and deactivates only the known old
bootstrap catalogue names; historical booking snapshots are not changed or deleted.

After migration, review **Mobile → Services & pricing → Settings → Invoice identity**. Leave VAT
registration disabled unless Trifecta is actually VAT registered and its real TRN and supplier
details have been entered. No new environment variable is required. Redeploy the API and web, then
distribute a new staff mobile build because manager settings and expense forms changed.

## Website

Select `apps/web` as the Vercel Root Directory. Set `NEXT_PUBLIC_API_URL` to the public HTTPS FastAPI origin and set `NEXT_PUBLIC_SITE_URL=https://trifecta-wash.com` (without a trailing path). Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` from the public Supabase project settings. Set `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` to a browser key restricted to the production website plus explicitly intended preview/development origins. Set `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` to the production map ID when available. No database, Resend, JWT, signing, dispatch, SMTP, or service-role secret belongs in the web project.

In **Supabase Dashboard → Authentication → URL Configuration**, configure:

```text
Site URL
https://trifecta-wash.com

Allowed Redirect URLs
https://trifecta-wash.com/auth/confirm
https://trifecta-wash.com/auth/reset-password
http://localhost:3000/auth/confirm
http://localhost:3000/auth/reset-password
```

Add the equivalent `www.trifecta-wash.com` callbacks only if that hostname is intentionally served. Do not use a production wildcard. Passwordless customer access calls `signInWithOtp` with `/auth/confirm` through `emailRedirectTo`; password recovery passes `/auth/reset-password` through `redirectTo`. The browser client retains the existing implicit Supabase flow (`detectSessionInUrl`, persisted sessions, and token refresh). The callback accepts only a local `returnTo` path. A `PASSWORD_RECOVERY` event always replaces the current route with `/auth/reset-password`; ordinary magic-link `SIGNED_IN` events never enter recovery mode.

Keep the **Magic Link** email template as a clickable-link template. For the current implicit browser flow, a minimal safe body is:

```html
<h2>Sign in to Trifecta</h2>
<p><a href="{{ .ConfirmationURL }}">Sign in securely</a></p>
```

Do not replace `{{ .ConfirmationURL }}` with a six-digit OTP-only template or a custom `token_hash` callback unless the application is deliberately migrated to that flow. Keep the recovery template as a recovery link using its Supabase confirmation URL. For security-sensitive Supabase Auth mail sent through Resend, disable click and open tracking on the auth sending domain so link rewriting cannot alter single-use Auth URLs. Prefer a dedicated auth sending subdomain if ordinary transactional booking-email tracking must remain independently configurable.

Supabase Auth emails are separate from booking emails sent by the FastAPI/Resend notification provider. Custom SMTP is already expected for production; keep its credentials only in Supabase Dashboard, never in Vercel web variables or Git. After deployment, send both a real Magic Link and a password recovery link to a non-team test inbox and confirm that each lands on its distinct route.

Enable only the Google APIs used by this flow: Maps JavaScript API, Places API (New), and Geocoding API. Apply both Website application restrictions and API restrictions to the browser key. If the key is absent, the form intentionally falls back to written address plus a validated Google Maps share link.

The API must list the exact Vercel production domain and any intended preview domains in `CORS_ORIGINS`. Prefer an explicit stable preview origin rather than `*`; credentials-enabled production CORS must remain bounded.

## Backend

Deploy FastAPI from the existing backend artifact. A persistent host may also run the existing outbox worker; Vercel should use the bounded dispatch endpoint described below and must never start the infinite worker loop inside a request. Use a host geographically close to the Supabase database. API startup must never migrate or seed.

Set a stable, randomly generated `BOOKING_MANAGEMENT_SIGNING_KEY` of at least 32 characters. Rotating it invalidates existing customer management links, so rotate only with an intentional transition plan.

For Phase 3.2/4, apply Alembic revision `8a72c1d4e6f0` before the matching API. It adds `business_settings.appointment_reminder_enabled` (default `true`) and `appointment_reminder_hours_before` (default `24`, constrained to 1–168). The prior Phase 3.1 migration still supplies the startup default stock pool and durable notification-outbox dedupe index. No new environment variable is required.

For real booking email, configure backend-only `RESEND_API_KEY`, `EMAIL_FROM`, and `PUBLIC_WEB_URL`. Verify the sender domain in Resend before using a custom sender. The dispatcher derives `/manage#<signed-token>` from `PUBLIC_WEB_URL` at send time. Configure a strong random `OUTBOX_DISPATCH_SECRET`; it is accepted only in `X-Outbox-Dispatch-Secret` on `POST /api/v1/internal/notifications/dispatch`. Missing Resend configuration in production records retries/failure rather than pretending delivery succeeded.

Resend HTTP 4xx/5xx responses are provider rejections even when Cron and the dispatcher are healthy. Inspect the notification's bounded `last_error` and the sanitized `notification_retry` log fields for the provider status/code/message. A Resend onboarding sender can be restricted to the account's approved test recipient; use a verified production sending domain and an allowed recipient policy before general customer delivery. Never copy the API key, recipient, or full provider response into logs or support notes.

Choose the PostgreSQL endpoint for the compute model. A persistent regional container can use the direct endpoint when IPv6 is available or Supavisor session mode on IPv4-only networks. Serverless/elastic compute should use an appropriate transaction pooler and disable prepared statements when required by that pooler. Configure `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS`, and `DB_POOL_PRE_PING` against the Supabase connection budget. For a Vercel transaction-pooler deployment, start conservatively (for example size 2 and overflow 0-1 per warm instance), set `DB_DISABLE_PREPARED_STATEMENTS=true`, then adjust only from checkout/connection telemetry. See [`PERFORMANCE_ARCHITECTURE.md`](PERFORMANCE_ARCHITECTURE.md).

## Private job-quality photo storage

Apply Alembic revision `80826dfc3c2d` before deploying the matching API. When the target is Supabase and `storage.buckets` is available, the migration idempotently creates or updates a private bucket named `job-quality-photos` with an 8 MiB object limit and JPEG, PNG, and WebP MIME allow-list. The migration never creates a public read policy; all access is mediated by FastAPI using the backend-only Supabase service-role key.

Configure these backend values (defaults are shown only where safe):

```text
JOB_PHOTO_BUCKET=job-quality-photos
JOB_PHOTO_SIGNED_URL_SECONDS=300
JOB_PHOTO_MAX_BYTES=8388608
```

If the migration runs against a PostgreSQL target without Supabase's `storage` schema, it safely skips bucket creation. Before enabling photo uploads in the Supabase project, manually create the same **private** bucket in **Storage → New bucket**, then set the size and MIME restrictions above. Do not add anonymous/public object policies. The mobile bundle needs no Storage service credential; it uploads only with a short-lived backend-issued token.

This release adds Expo Image Picker and Image Manipulator plus Android camera/media permission configuration. Run `npx expo prebuild --platform android --no-install --no-clean`, verify the generated manifest, and distribute a new APK/AAB. An OTA JavaScript update alone is insufficient for first adoption of the native modules/permissions.

## Supabase Cron notification dispatch

The Vercel-compatible path is bounded and returns after at most `OUTBOX_BATCH_SIZE` records:

```text
Supabase Cron
      ↓ POST + X-Outbox-Dispatch-Secret
FastAPI /api/v1/internal/notifications/dispatch
      ↓ claim bounded batch with FOR UPDATE SKIP LOCKED
Resend
      ↓
mark sent or schedule exponential retry
```

The scheduler needs only the API URL and dispatch secret; it does not receive database credentials. The setup SQL is [`supabase/notification_dispatch_cron.sql`](../supabase/notification_dispatch_cron.sql). It idempotently enables `pg_cron`, `pg_net`, and Vault and upserts one job named `abdwash-notification-dispatch` on `* * * * *`. The job is intentionally dormant until both Vault values exist.

### Store or rotate the Vault values

Prefer **Supabase Dashboard → Vault** and create these exact names:

```text
abdwash_outbox_dispatch_url
abdwash_outbox_dispatch_secret
```

The URL must be the deployed internal dispatch endpoint. The secret must exactly match the API project's backend-only `OUTBOX_DISPATCH_SECRET`. To create or update them through the SQL editor instead, replace only the bracketed placeholders before running this block. Never commit or paste its completed form into logs or tickets.

```sql
do $vault_setup$
declare
  dispatch_url_id uuid;
  dispatch_secret_id uuid;
begin
  select id into dispatch_url_id from vault.secrets
  where name = 'abdwash_outbox_dispatch_url';

  if dispatch_url_id is null then
    perform vault.create_secret(
      'https://abdwash.vercel.app/api/v1/internal/notifications/dispatch',
      'abdwash_outbox_dispatch_url',
      'Trifecta bounded notification dispatcher URL'
    );
  else
    perform vault.update_secret(
      dispatch_url_id,
      'https://abdwash.vercel.app/api/v1/internal/notifications/dispatch',
      'abdwash_outbox_dispatch_url',
      'Trifecta bounded notification dispatcher URL'
    );
  end if;

  select id into dispatch_secret_id from vault.secrets
  where name = 'abdwash_outbox_dispatch_secret';

  if dispatch_secret_id is null then
    perform vault.create_secret(
      '<OUTBOX_DISPATCH_SECRET>',
      'abdwash_outbox_dispatch_secret',
      'Trifecta bounded notification dispatcher secret'
    );
  else
    perform vault.update_secret(
      dispatch_secret_id,
      '<OUTBOX_DISPATCH_SECRET>',
      'abdwash_outbox_dispatch_secret',
      'Trifecta bounded notification dispatcher secret'
    );
  end if;
end
$vault_setup$;
```

### Install or update the schedule

Run the committed setup file in the Supabase SQL editor. Calling `cron.schedule` again with the same job name updates that job, so repeated setup does not create duplicates. Confirm there is exactly one active job:

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'abdwash-notification-dispatch';

select count(*) as matching_jobs
from cron.job
where jobname = 'abdwash-notification-dispatch';
```

The expected count is `1`, schedule is `* * * * *`, and `active` is `true`.

### Inspect execution and HTTP results

Cron records whether the SQL command ran; `pg_net` separately records the asynchronous HTTP response. Inspect both without selecting request headers or Vault values:

```sql
select runid, jobid, status, return_message, start_time, end_time
from cron.job_run_details
where jobid = (
  select jobid from cron.job
  where jobname = 'abdwash-notification-dispatch'
)
order by start_time desc
limit 20;

select id as request_id, status_code, timed_out, error_msg, created
from net._http_response
order by created desc
limit 20;
```

A healthy minute has a succeeded cron run and an HTTP `200` response. Each bounded invocation first queues due appointment reminders and then claims the normal outbox batch. A minute with no due or pending notifications is also successful; the endpoint returns zero scheduled/claimed work.

### Manual and end-to-end verification

First confirm the endpoint still rejects an invalid secret:

```bash
curl --fail-with-body -X POST \
  https://abdwash.vercel.app/api/v1/internal/notifications/dispatch \
  -H "Content-Type: application/json" \
  -H "X-Outbox-Dispatch-Secret: deliberately-invalid" \
  -d '{}'
```

Expect HTTP `401`. For a valid manual smoke test, keep the secret in the shell environment rather than command history:

```bash
curl --fail-with-body -X POST \
  https://abdwash.vercel.app/api/v1/internal/notifications/dispatch \
  -H "Content-Type: application/json" \
  -H "X-Outbox-Dispatch-Secret: ${OUTBOX_DISPATCH_SECRET}" \
  -d '{}'
```

For the Cron proof, create a booking with the approved Resend test recipient, confirm its outbox row is initially `pending`, and do not call the endpoint manually. After the next minute, confirm it becomes `sent`, then verify the Resend event and test inbox. Existing dispatcher retry/backoff behavior remains authoritative when delivery fails.

### Disable or remove the schedule

Temporarily disable it without deleting history:

```sql
select cron.alter_job(
  job_id := (
    select jobid from cron.job
    where jobname = 'abdwash-notification-dispatch'
  ),
  active := false
);
```

Remove it while preserving existing run-history rows:

```sql
select cron.unschedule('abdwash-notification-dispatch');
```

## Mobile

The Expo app is independently built and distributed. Only public Supabase/Auth and API base URL configuration may be embedded. Backend/service-role/database credentials must never enter an Expo variable or bundle.

For the Phase 1 catalogue release, apply Alembic revision `9d5f551c26e5` before deploying the matching API. It backfills canonical vehicle prices from each existing service's legacy base price, copies legacy business hours into seven weekday rows, and snapshots existing booking-service durations without changing booking history. Then deploy the customer web and publish the updated Expo JavaScript bundle/native release through the normal mobile channel. No new environment variable is required, and this phase adds no native dependency.

For the Phase 2 smart-scheduling release, apply Alembic revision `e7441de34e33` after `9d5f551c26e5` and before deploying the matching API. It backfills hold/job operational minutes conservatively from existing scheduled intervals and immutable booking-service/add-on snapshots, labels existing assigned jobs as `legacy`, and does not reassign historical or future work. Deploy the web client with the API so availability sends trusted catalogue selections and no longer consumes public team IDs. Publish the mobile JavaScript update through the proven Expo release channel; if OTA delivery is not configured for the installed app, issue a new APK/app bundle. No new environment variable or native dependency is introduced.

For Operations V2 hardening, upgrade the API database through Alembic revision `a41f3b7820d6`, deploy the API, then create a new Android binary. The checked-in Android project must be regenerated with `npx expo prebuild --platform android --no-install --no-clean` so `withAndroidImeInsets.js` stays synchronized with `MainActivity.kt`. Build with JDK 17 and perform the real-device keyboard matrix in `docs/mobile-operations.md`; an OTA JavaScript update cannot deliver the native IME listener.

For Operations V2, apply Alembic revision `96493956784a`, deploy the API, then run `python -m app.cli.seed_demo_staff` with backend-only `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, and `DEMO_STAFF_PASSWORD`. The demo usernames are `manager` and `employee`; the shared password value is never printed. Rebuild the native app because V2 adds the Expo Haptics module.

## Release order

1. Back up and verify the intended environment.
2. Apply Alembic through revision `e7441de34e33` before deploying this release. It performs no historical loyalty-credit backfill or team reassignment and preserves existing booking snapshots.
3. Run the explicit seed only for initial bootstrap when appropriate.
4. Deploy the API and either its persistent worker or the secured one-shot scheduler near the database.
5. Configure explicit web/mobile API origins and URLs.
6. Deploy/select `apps/web` in Vercel when separately authorized.

After the API is live, open manager mobile Customers → Loyalty settings and select the intended active reward service. The migration populates `loyalty_reward_service_id` only for businesses with exactly one active service; it deliberately does not infer a service by name. No new environment variable is required for loyalty or cash tender.

No deployment is performed by this foundation task.

## Services, pricing, invoices, and expense evidence release

Apply Alembic revision `c18f4a7b2d91` before deploying the matching API. The migration adds the
approved six-service catalogue and vehicle-type prices, immutable revenue invoice/sequence tables,
optional booking billing snapshots, VAT-aware business identity fields, and expense evidence fields.
It preserves historical booking/service/payment snapshots.

Create a **private** Supabase Storage bucket named `expense-evidence` (or set the backend-only
`EXPENSE_EVIDENCE_BUCKET` to another private bucket name). Set `EXPENSE_EVIDENCE_MAX_BYTES` if the
10 MiB default is unsuitable. Do not make the bucket public and do not expose the service-role key
to web or mobile applications.

Release order for this phase:

1. Back up the production database and apply `alembic upgrade c18f4a7b2d91`.
2. Create or verify the private expense-evidence Storage bucket.
3. Deploy the API, then the web project.
4. Publish the mobile JavaScript/application update for the catalogue/settings/expense form changes.
5. Configure the legal supplier identity and VAT status in manager Services & pricing settings before
   relying on Tax Invoice output. Never enable VAT status without the business's real TRN.

## Customer account and verified reviews release

Apply Alembic revision `d4a9e7c31f26` after `c6c7c3026e63` and before deploying the matching API.
It adds verified reviews, account-level prompt cadence, bounded guest verification state, and deleted-
identity tombstones. The release does not rewrite historical booking, invoice, payment, loyalty, or
notification data.

The API project must already have backend-only `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for
real Supabase Auth identity deletion. Do not expose the service-role key to `NEXT_PUBLIC_*`, Expo,
logs, or client bundles. No new environment variable is introduced. Deploy in this order:

1. Back up the production database and run `alembic upgrade d4a9e7c31f26`.
2. Confirm `alembic current` returns `d4a9e7c31f26` and `alembic heads` shows one head.
3. Deploy the FastAPI backend.
4. Deploy the Next.js web project.
5. Smoke-test Magic Link sent state, password sign-up, onboarding skip, authenticated and guest
   completed-booking reviews, `/reviews`, and deliberate self-account deletion with a disposable
   customer identity.

No mobile source or native dependency changes are part of this release; no APK rebuild is required.
