# Mobile operations deployment

The Expo app uses the same Supabase Auth project as the customer website. A valid session is admitted only after the API finds an active, same-business `staff_profiles` row. Mobile role visibility is convenience only; every query and mutation is independently scoped by FastAPI.

## Mobile environment

- `EXPO_PUBLIC_API_BASE_URL`
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Never put service-role, database, Resend, dispatch, payment, or Google Routes secrets in Expo variables. Sessions use Expo SecureStore. Today lists are cached with a timestamp for read-only offline display; operational and financial mutations require an authoritative online response and retain retry-safe client event IDs.

## Backend environment

Set `GOOGLE_ROUTES_API_KEY` only on the API deployment. Enable Google Routes API, restrict the key to that API and the backend deployment's appropriate application/IP controls. Start-trip still enters `en_route` if routing is unavailable.

Apply Alembic through revision `96493956784a` before deploying the V2 API. The V2 release adds staff phone data, scheduling-resource team memberships, attendance, shifts, shift assignments, leave requests, and team assignment on jobs. All new tables have RLS enabled and remain backend-owned.

## Operations V2

- `schedule_resources` remain the source of booking capacity and now act as operational teams.
- Team reassignment locks and moves the booking's reserved slots so availability and operations cannot diverge.
- Employees see direct assignments plus jobs belonging to an active team membership; the API enforces this scope.
- Managers create employee accounts; admins may also create managers. Supabase Admin calls remain server-only.
- Attendance uses server timestamps and a partial unique index prevents multiple open sessions.
- Shifts use the business timezone and `attendance_grace_minutes` policy.
- Leave approval blocks while future direct/team work remains assigned.
- Dashboard and report graph series are aggregated by the backend and bounded before reaching Expo.

The V2 primary tabs are `Today`, `Jobs`, and `Profile` for employees and add `Team` and `Reports` for managers/admins. Staff, shifts, attendance, leave approvals, and cancellation review are nested workflows rather than extra tabs.

## Notification contract

`trip_started` queues one `driver_en_route` email in the existing durable outbox. Cron, retry, and Resend behavior are unchanged. The operational event is channel-neutral enough for a future WhatsApp renderer, but WhatsApp is intentionally disabled and no undeliverable WhatsApp rows are created.

## Reporting definitions

- Booked sales: sum of booking snapshot totals in the selected scheduled period.
- Collected revenue: payment amounts whose authoritative status is `paid`.
- Outstanding: booked sales less collected revenue.
- Completed washes: completed bookings in the period.
- Average booking value: average booking snapshot total.

The report uses bounded SQL aggregation. History/job lists use offset/limit pagination rather than downloading all records.

## Deferred domains

Inventory, van stock, service photos/checklists, subscriptions, loyalty, corporate credit, expenses, commissions, complaints/rewash, WhatsApp, card/NFC/Tap-to-Pay, background/live GPS, AI assistance, multi-branch management, and a durable offline mutation replay queue remain out of scope.
