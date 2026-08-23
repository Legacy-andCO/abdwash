# Deployment notes

## Website

Select `apps/web` as the Vercel Root Directory. Set `NEXT_PUBLIC_API_URL` to the public HTTPS FastAPI origin. Set `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` to a browser key restricted to the production website plus explicitly intended preview/development origins. Set `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` to the production map ID when available. No Supabase, database, Resend, JWT, signing, dispatch, or service-role secret belongs in the web project.

Enable only the Google APIs used by this flow: Maps JavaScript API, Places API (New), and Geocoding API. Apply both Website application restrictions and API restrictions to the browser key. If the key is absent, the form intentionally falls back to written address plus a validated Google Maps share link.

The API must list the exact Vercel production domain and any intended preview domains in `CORS_ORIGINS`. Prefer an explicit stable preview origin rather than `*`; credentials-enabled production CORS must remain bounded.

## Backend

Deploy FastAPI from the existing backend artifact. A persistent host may also run the existing outbox worker; Vercel should use the bounded dispatch endpoint described below and must never start the infinite worker loop inside a request. Use a host geographically close to the Supabase database. API startup must never migrate or seed.

Set a stable, randomly generated `BOOKING_MANAGEMENT_SIGNING_KEY` of at least 32 characters. Rotating it invalidates existing customer management links, so rotate only with an intentional transition plan.

For real booking email, configure backend-only `RESEND_API_KEY`, `EMAIL_FROM`, and `PUBLIC_WEB_URL`. Verify the sender domain in Resend before using a custom sender. The dispatcher derives `/manage#<signed-token>` from `PUBLIC_WEB_URL` at send time. Configure a strong random `OUTBOX_DISPATCH_SECRET`; it is accepted only in `X-Outbox-Dispatch-Secret` on `POST /api/v1/internal/notifications/dispatch`. Missing Resend configuration in production records retries/failure rather than pretending delivery succeeded.

Choose the PostgreSQL endpoint for the compute model. A persistent regional container can use the direct endpoint when IPv6 is available or Supavisor session mode on IPv4-only networks. Serverless/elastic compute should use an appropriate transaction pooler and disable prepared statements when required by that pooler.

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

The scheduler needs only the API URL and dispatch secret; it does not receive database credentials. In the Supabase SQL editor, enable `pg_cron`, `pg_net`, and Vault, then store the values in Vault and schedule a one-minute HTTP call:

```sql
select vault.create_secret(
  'https://YOUR-API-DOMAIN/api/v1/internal/notifications/dispatch',
  'outbox_dispatch_url'
);
select vault.create_secret('YOUR-STRONG-DISPATCH-SECRET', 'outbox_dispatch_secret');

select cron.schedule(
  'abdwash-notification-dispatch',
  '* * * * *',
  $$
  select net.http_post(
    url := (
      select decrypted_secret from vault.decrypted_secrets
      where name = 'outbox_dispatch_url'
    ),
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Outbox-Dispatch-Secret', (
        select decrypted_secret from vault.decrypted_secrets
        where name = 'outbox_dispatch_secret'
      )
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 15000
  );
  $$
);
```

Run this only after the API deployment and secrets are ready. Verify the job in Supabase Cron history and confirm outbox rows transition to `sent`. This repository does not create the Cron job automatically.

## Mobile

The Expo app is independently built and distributed. Only public Supabase/Auth and API base URL configuration may be embedded. Backend/service-role/database credentials must never enter an Expo variable or bundle.

## Release order

1. Back up and verify the intended environment.
2. Apply Alembic migrations only when the release contains a new migration; this improvement pass does not.
3. Run the explicit seed only for initial bootstrap when appropriate.
4. Deploy the API and either its persistent worker or the secured one-shot scheduler near the database.
5. Configure explicit web/mobile API origins and URLs.
6. Deploy/select `apps/web` in Vercel when separately authorized.

No deployment is performed by this foundation task.
