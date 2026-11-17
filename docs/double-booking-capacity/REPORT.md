# Booking capacity correction — 17 November 2026

No production deployment or production data changes were made.

## Root cause and reproduction

The normal staff booking endpoint and explicit calendar exception shared `POST /api/v1/staff/calendar-bookings` and the same request model. A valid client-supplied `overlap` object switched that normal endpoint into the capacity-exception branch. Existing appointment/team/version checks were present, but the normal endpoint itself did not prohibit exceptions.

This was reproduced against an isolated copy of commit `233a87a`: with both teams occupied, employees, managers and admins each received **201 with `capacity_exception: true`** from the normal endpoint. The new regression expected 422 and failed for all three roles on that baseline. See `before-override-tests.txt`. Those tests pass on the corrected code.

Ordinary requests **without** an overlap payload were already capacity checked under a business/day PostgreSQL advisory lock. I did not reproduce an unflagged capacity bypass in this checkout, and did not inspect or change the deployed production version. The reproduction establishes the shared-endpoint bypass, not the provenance of a particular previously reported booking.

Additional gaps: the staff availability API returned occupied/unavailable entries and relied on client filtering; add-on durations were not accepted by that availability endpoint; the full staff service duration could extend beyond closing even when the grid reservation fit. Vehicle-type changes did not clear the chosen time, and the normal empty state advertised intentional double-booking.

## Changes

- Normal POST accepts `NormalStaffBookingCreate`: overlap must be absent or null. Non-null overlap or unknown override flags return 422 before any mutation.
- Explicit POST is `/api/v1/staff/calendar-bookings/{job_id}/double-book`, with a required confirmed overlap object and a separate idempotency operation. The path appointment must match the payload. The service checks the authenticated tenant/team scope, confirmed original booking, assigned appointment status (matching calendar permission), current version, requested overlap, eligible team, operating hours, holds and hard blocks under the schedule lock. A bare override flag is insufficient.
- Capacity allocation, transaction locking, booking/payment creation, notification outbox and independent original records remain in the existing shared transaction flow. The service rejects exception requests not typed as the dedicated calendar operation.
- Staff availability returns only available times, includes requested add-on durations, and checks the complete operational duration against closing time. Hold creation enforces the same closing boundary.
- The calendar confirmation modal submits only to the explicit endpoint. Normal Book a Wash/Today/Jobs routes submit to the normal endpoint. Availability refreshes on date, service, vehicle count/type changes and periodically while open. A rejected submission clears the selected time, refreshes availability and asks for another available time.
- Empty state is exactly “No available times for this date”, with an Arabic translation.

## Actual verification

Real browser tests used the updated staff web build and modified API served locally against **isolated Supabase staging `mgfzfgvlrxwyyftwukwf`**, real password authentication, fresh MFA for managers/admins, and the existing restricted staging database login. All business records were checked to be synthetic. This was not a hosted deployment or native-device test. No notification worker or external payment provider was enabled.

| Check | Employee | Manager | Admin |
|---|---|---|---|
| Fully occupied 9:00 AM absent from normal form | PASS | PASS | PASS |
| Direct normal request at 9:00 AM | 409 | 409 | 409 |
| Calendar → date → appointment → confirmation → explicit booking | 201 | 201 | 201 |
| Original and extra independently confirmed in database | PASS | PASS | PASS |
| Multi-vehicle concurrent requests with one team left | 201 / 409 | 201 / 409 | 201 / 409 |
| Partially overlapping duration | 409 | 409 | 409 |
| Full duration extending beyond closing | 409 | 409 | 409 |
| Client override flag on normal endpoint | 422 | 422 | 422 |
| Empty state, no time buttons, recalculation after removing vehicles | PASS | PASS | PASS |

The employee test used its assigned team; management tests exercised both eligible staging teams. Browser appointments used 24–26 November 2026; duration/concurrency fixtures used 10–12 March 2038. Stale-selection browser evidence is recorded separately in `staging-stale-results.json`.

Evidence:
- `staging-browser-results.json`: role-by-role browser/API receipts and calendar records.
- `staging-data-results.json`: database confirmation/payment checks and real staging duration/concurrency outcomes.
- `staging-empty-results.json`: no-times and vehicle-change UI checks.
- `staging-stale-results.json`: a competing booking consumes capacity after review; normal submission returns 409, displays the recovery message and removes the occupied time after refetch.
- Role-specific `*-normal.png`, `*-confirmation.png`, `*-empty.png`, `*-stale.png` screenshots.

Regression results: **487 backend tests passed, zero skipped** with PostgreSQL security and migration gates enabled; **194 staff frontend tests passed**; **230 customer frontend tests passed**. Staff TypeScript and mypy on the four changed backend modules passed. Ruff passed for changed application modules and capacity tests. The pre-existing security-test file has unrelated lint findings; its execution passes. The backend suite covers payment preservation, outbox notifications, idempotency, permissions, tenant isolation, rescheduling and cancellation. External payment/email delivery and native hardware were not exercised.

## Reproduction and rollout notes

The new cases live in `backend/tests/test_staff_calendar_bookings_postgres.py`; the restricted-role security regression was updated to use the explicit endpoint. Use an isolated local `TEST_DATABASE_URL` whose database name contains `test`. Full gated runs also need `SECURITY_TEST_DATABASE_URL`, `RUN_POSTGRES_MIGRATION_TESTS=1`, and `DATABASE_URL` pointing to the migrated synthetic security database. Run from `backend` because migration fixtures use its Alembic configuration.

Browser and staging-data scripts are in `scripts/trifecta-verification/capacity-*`. They use the pre-existing ignored `tmp/security-staging.json` credentials, localhost API port 8004 and staff web port 8084. Fixture dates are explicit: choose fresh future dates when repeating mutating tests. They do not provision or deploy an environment.

No schema migration is required. Release the staff client and backend together: older clients can still create normal bookings with `overlap: null`, but their old shared-endpoint double-booking requests will now be rejected. Synthetic verification records remain only in staging for inspection.
