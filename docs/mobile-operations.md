# Mobile operations deployment

The Expo app uses the same Supabase Auth project as the customer website. A valid session is admitted only after the API finds an active, same-business `staff_profiles` row. Mobile role visibility is convenience only; every query and mutation is independently scoped by FastAPI.

## Mobile environment

- `EXPO_PUBLIC_API_BASE_URL`
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Never put service-role, database, Resend, dispatch, payment, or Google Routes secrets in Expo variables. Sessions use Expo SecureStore. TanStack Query owns server state and persists only explicitly opted-in read queries (profile, job lists, and recent job detail) in AsyncStorage. Every key includes the authenticated business/staff scope, cached screens show their last-updated time when a refresh fails, and sign-out clears both memory and persisted data. Operational and financial mutations always require an authoritative online response and retain retry-safe client event IDs.

## Backend environment

Set `GOOGLE_ROUTES_API_KEY` only on the API deployment. Enable Google Routes API, restrict the key to that API and the backend deployment's appropriate application/IP controls. Start-trip still enters `en_route` if routing is unavailable.

Apply Alembic through revision `8a72c1d4e6f0` before deploying this operations release. It retains the bounded V2 reporting/filtering indexes and immutable job-consumption snapshots, adds the startup default stock pool plus durable notification deduplication, and adds the two business reminder settings. All operational/customer tables remain backend-owned with RLS enabled and no direct mobile policies.

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
- Services & Pricing is a nested manager/admin workflow reached from Today. It owns mobile-service names/descriptions, active state, canonical vehicle prices, expected duration, add-ons, booking-grid settings, weekday hours, mobile minimum, reward service, and expected-consumables templates. Mobile/Shop controls are hidden from the normal startup editor; compatibility fields remain server-side. On first successful completion, the current service-level template is snapshotted and safely recorded through the existing inventory ledger.

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
- Managed catalogue and booking settings: 1 minute, persisted for three days inside the authenticated business/staff/role scope.
- Manager customer list/detail and loyalty: 1 minute, persisted for two days in the authenticated business/staff/role scope.

Assignments, lifecycle actions, clock events, shifts, leave and rescheduling update the returned entity and invalidate only related keys. App foreground uses React Query focus handling; pull-to-refresh calls the same query observers. The app has no offline mutation queue.

Manager/admin Job Detail shows automatic, manual, or legacy assignment provenance. Its compact assignment sheet can request a fresh automatic choice or select an eligible team. True overlaps are disabled; a turnaround-only warning requires an explicit **Assign anyway** confirmation. Employees can see their assigned work but cannot open reassignment or override controls. The authoritative assignment response immediately patches Job Detail, matching Jobs lists, and Today data; the existing `jobs`/`schedule` sync revisions reconcile related team views without invalidating Finance, Inventory, or Customers.

Completed unpaid Job Detail uses a dedicated cash tender modal. The mobile app calculates display change in integer minor units and submits tender/change with one retained client event ID; FastAPI independently validates the figures, records only the amount due as collected revenue, and returns the authoritative receipt/job.

Managers/admins open Customers from Today. Search is server-side and paginated across normalized name, phone, email, and active vehicle plate within the authenticated tenant. Customer detail uses bounded bulk reads for saved data and booking/job/complaint history. Profile, address, vehicle, and loyalty writes invalidate only scoped customer query families; the `customers` sync revision reconciles changes from job completion, payment, customer web edits, and other devices.

The V2 primary tabs are `Today`, `Jobs`, and `Profile` for employees and add `Team` and `Reports` for managers/admins. Staff, shifts, attendance, leave approvals, cancellation review, Inventory, and Services & Pricing are nested workflows rather than extra tabs.

Inside Jobs, both employees and managers have a `Calendar` view. It is a traditional month grid with at most three compact entries per day and `+N more`; tapping a date opens the chronological agenda and tapping an agenda row opens the existing Job Detail. Managers see all tenant-scoped jobs, while employees retain their existing direct/team assignment scope. Cancelled jobs are hidden and unassigned work is called out visually.

Manager Job Detail can queue a 15, 30, 45, or 60 minute customer delay email without changing the scheduled time. It also shows safe communication history from the existing outbox. `Sent` means the email provider accepted the request, not proof that the recipient opened or received it. Services & Pricing → Settings contains the single appointment-reminder enable switch and lead-time field.

## Job quality controls

Job Detail loads one scoped quality record for jobs at `arrived`, `in_progress`, or `completed`. Workers can record a lightweight inspection after arrival; create compressed before, after, damage, and issue evidence; complete a fast-tap service checklist; and attach an optional ready photo to an issue. The backend blocks `in_progress → completed` only when a snapshotted required checklist item remains incomplete. Old completed jobs with no snapshot continue to load and remain valid.

Camera and media-library permissions are requested only when the worker chooses the corresponding action. Images are resized to a maximum width of 1600 pixels and encoded as JPEG before upload. A preview can be removed before upload; a failed upload retains the preview and its client request ID, so retry reuses the same pending metadata/object path. Quality writes are disabled when the device is known offline, while previously persisted quality reads remain available.

The quality authorization path consumes the shared five-column job projection through its named/explicit row adapter. No record, empty checklist, and no photos are valid states. A failed quality refresh is isolated from Job Detail and leaves cached quality visible with a retry action; per-photo signed-read failures yield unavailable evidence rather than a failed job record.

Managers/admins can review inspections, evidence, checklist attribution, issues, and complaints from the same authorized Job Detail. Complaint outcomes are under review, resolved, rejected, or a scheduled complimentary rewash. A rewash consumes a normal scheduling hold, creates a linked zero-value booking/job, preserves the original completed job, and resolves the complaint when the correction job completes.

## Completion-time consumables and direct expenses

Normal completion remains one employee action. The returned Job Detail is patched immediately with its immutable consumables summary. Expected usage resolves one business default/sole/obvious-main stock pool and deducts immediately. Only a real shortage, inactive item, or ambiguous/missing startup setup creates a manager-only Inventory **Needs review** item; it never blocks the completed customer workflow. Managers receive issue-specific actions and can mark historical discrepancies reviewed immediately. Stock Count is optional physical reconciliation, not a normal wash step. Employees see a read-only summary and retain existing assigned-job manual usage for unusual/additional materials.

Manager/admin Job Detail also shows active expenses explicitly linked to that job and can create one through the existing Finance mutation. These cash/business costs remain separate from expected quantities. Automatic inventory usage does not post a second Finance expense.

## Notification contract

`trip_started` queues one `driver_en_route` email. A successful manager reschedule queues one `booking_rescheduled` email, and the first successful completion queues one `job_completed` email in the same authoritative transaction as job/inventory state. The completion dispatcher renders the reserved schedule, actual `started_at → completed_at` duration, and authoritative settled amount or **Pending**. A nullable dedupe key plus unique business/key index prevents duplicate new events. Cron, retry, and Resend behavior are unchanged; provider calls remain outside job transactions. WhatsApp remains disabled.

## Reporting definitions

- Booked sales: sum of booking snapshot totals in the selected scheduled period.
- Collected revenue: payment amounts whose authoritative status is `paid`.
- Outstanding: booked sales less collected revenue.
- Completed washes: completed bookings in the period.
- Average booking value: average booking snapshot total.

The report uses bounded SQL aggregation. History/job lists use offset/limit pagination rather than downloading all records.

## Deferred domains

Supplier/procurement workflows, inventory valuation/COGS, vehicle-specific/add-on consumable recipes, fleet records beyond named stock locations, subscriptions, corporate credit, commissions, WhatsApp, card/NFC/Tap-to-Pay, background/live GPS, AI assistance, multi-branch management, historical consumption/loyalty backfill, and a durable offline mutation replay queue remain out of scope.
