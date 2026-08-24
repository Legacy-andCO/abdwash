# Mobile operations deployment

The Expo app uses the same Supabase Auth project as the customer website. A valid session is admitted only after the API finds an active, same-business `staff_profiles` row. Mobile role visibility is convenience only; every query and mutation is independently scoped by FastAPI.

## Mobile environment

- `EXPO_PUBLIC_API_BASE_URL`
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Never put service-role, database, Resend, dispatch, payment, or Google Routes secrets in Expo variables. Sessions use Expo SecureStore. TanStack Query owns server state and persists only explicitly opted-in read queries (profile, job lists, and recent job detail) in AsyncStorage. Every key includes the authenticated business/staff scope, cached screens show their last-updated time when a refresh fails, and sign-out clears both memory and persisted data. Operational and financial mutations always require an authoritative online response and retain retry-safe client event IDs.

## Backend environment

Set `GOOGLE_ROUTES_API_KEY` only on the API deployment. Enable Google Routes API, restrict the key to that API and the backend deployment's appropriate application/IP controls. Start-trip still enters `en_route` if routing is unavailable.

Apply Alembic through revision `a41f3b7820d6` before deploying the hardened V2 API. This adds the bounded reporting/filtering indexes for jobs, team membership, attendance, booking services, and paid payment-method reporting. All operational tables remain backend-owned with the existing RLS posture.

## Operations V2

- `schedule_resources` remain the source of booking capacity and now act as operational teams.
- Team reassignment locks and moves the booking's reserved slots so availability and operations cannot diverge.
- Employees see direct assignments plus jobs belonging to an active team membership; the API enforces this scope.
- Managers create employee accounts; admins may also create managers. Supabase Admin calls remain server-only.
- Attendance uses server timestamps and a partial unique index prevents multiple open sessions.
- Shifts use the business timezone and `attendance_grace_minutes` policy.
- Leave approval blocks while future direct/team work remains assigned.
- Dashboard and report graph series are aggregated by the backend and bounded before reaching Expo.
- Job navigation uses server-side Today, Upcoming, History, Unassigned and All views with bounded filter/pagination parameters. Job details load a bulk event timeline without per-row queries.
- Attendance overview categorizes scheduled, working, late, clocked-out, not-clocked-in, off-today and approved-leave staff using bulk queries and business-local dates.
- Reports include booked/collected/job trends, service/payment mix, and staff/team performance aggregates.

## Android keyboard and native rebuilds

The app registers `plugins/withAndroidImeInsets.js`. It applies full Android IME bottom insets at the activity content root while preserving insets for React Native safe-area descendants. This is the edge-to-edge fix; forms do not calculate keyboard height in JavaScript.

Because `apps/mobile/android` is checked in, configuration changes must be synchronized before every Android release:

```bash
npx expo prebuild --platform android --no-install --no-clean
cd apps/mobile/android
./gradlew :app:compileReleaseKotlin
```

Use JDK 17 (Android Studio's bundled JBR is suitable). Verify Login, Add/Edit Staff, Profile, Leave, Create/Assign Shift, team membership, and Reschedule on at least one small real Android device with gesture and three-button navigation. A JavaScript-only rebuild is not sufficient when the native activity changes.

## Query cache policy

- Active job/detail and availability: 20 seconds.
- Dashboard, Today jobs and attendance: 30 seconds.
- Teams/staff: 3 minutes.
- Profile and shift definitions: 5 minutes.
- Reports: 2 minutes.

Assignments, lifecycle actions, clock events, shifts, leave and rescheduling update the returned entity and invalidate only related keys. App foreground uses React Query focus handling; pull-to-refresh calls the same query observers. The app has no offline mutation queue.

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
