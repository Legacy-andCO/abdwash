# Mobile operations deployment

The Expo app uses the same Supabase Auth project as the customer website. A valid session is admitted only after the API finds an active, same-business `staff_profiles` row. Mobile role visibility is convenience only; every query and mutation is independently scoped by FastAPI.

## Mobile environment

- `EXPO_PUBLIC_API_BASE_URL`
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Never put service-role, database, Resend, dispatch, payment, or Google Routes secrets in Expo variables. Sessions use Expo SecureStore. Today lists are cached with a timestamp for read-only offline display; operational and financial mutations require an authoritative online response and retain retry-safe client event IDs.

## Backend environment

Set `GOOGLE_ROUTES_API_KEY` only on the API deployment. Enable Google Routes API, restrict the key to that API and the backend deployment's appropriate application/IP controls. Start-trip still enters `en_route` if routing is unavailable.

Apply Alembic revision `d8cc0a1bf349` before deploying the API. Redeploy the web project so `en_route` and `estimated_arrival_at` are displayed to customers.

## Notification contract

`trip_started` queues one `driver_en_route` email in the existing durable outbox. Cron, retry, and Resend behavior are unchanged. The operational event is channel-neutral enough for a future WhatsApp renderer, but WhatsApp is intentionally disabled and no undeliverable WhatsApp rows are created.

## Reporting definitions

- Booked sales: sum of booking snapshot totals in the selected scheduled period.
- Collected revenue: payment amounts whose authoritative status is `paid`.
- Outstanding: booked sales less collected revenue.
- Completed washes: completed bookings in the period.
- Average booking value: average booking snapshot total.

The report uses bounded SQL aggregation. History/job lists use offset/limit pagination rather than downloading all records.

## Deferred hardening

Background/live GPS, WhatsApp delivery, card/NFC/Tap-to-Pay, refunds, a durable offline mutation replay queue, advanced reporting, branch switching, and live employee surveillance remain out of scope.
