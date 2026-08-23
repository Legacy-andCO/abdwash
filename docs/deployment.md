# Deployment notes

## Website

Select `apps/web` as the Vercel Root Directory. It has its own package, Next.js config, environment example, lint/type-check/test/build scripts, and App Router entry point. Set `NEXT_PUBLIC_API_URL` to the public HTTPS FastAPI origin. No Supabase, database, JWT, signing, or service-role secret belongs in the web project.

The API must list the exact Vercel production domain and any intended preview domains in `CORS_ORIGINS`. Prefer an explicit stable preview origin rather than `*`; credentials-enabled production CORS must remain bounded.

## Backend

Deploy FastAPI and the outbox worker as separate processes from the same backend artifact. Use a host geographically close to the Supabase database. Run `alembic upgrade head` as an explicit release step; API startup must never migrate or seed.

Set a stable, randomly generated `BOOKING_MANAGEMENT_SIGNING_KEY` of at least 32 characters. Rotating it invalidates existing customer management links, so rotate only with an intentional transition plan.

Choose the PostgreSQL endpoint for the compute model. A persistent regional container can use the direct endpoint when IPv6 is available or Supavisor session mode on IPv4-only networks. Serverless/elastic compute should use an appropriate transaction pooler and disable prepared statements when required by that pooler.

## Mobile

The Expo app is independently built and distributed. Only public Supabase/Auth and API base URL configuration may be embedded. Backend/service-role/database credentials must never enter an Expo variable or bundle.

## Release order

1. Back up and verify the intended environment.
2. Apply Alembic migrations.
3. Run the explicit seed only for initial bootstrap when appropriate.
4. Deploy API and worker near the database.
5. Configure explicit web/mobile API origins and URLs.
6. Deploy/select `apps/web` in Vercel when separately authorized.

No deployment is performed by this foundation task.
