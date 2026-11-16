**Trifecta booking corrections — verification report (17 November 2026)**

Implemented in this checkout. Production data, hosting, environment variables and deployments were not changed. Browser verification used the local staff frontend and API connected exclusively to the isolated Supabase staging project, with synthetic accounts and records. Existing verified MFA factors were retained.

**Root causes and changes**

- The ordinary booking path already contained capacity locks. The weak boundary was the exception payload: it identified a team and confirmation flag without binding the exception to the appointment the user selected. Explicit overlap now requires that appointment's ID, current version, team and occupied time. Normal booking keeps its capacity checks and rejects competing requests. No ordinary-form bypass control was added.
- The overlap confirmation used a native alert. It now uses a branded, accessible confirmation modal showing team, date and time, with Go back and Confirm double-booking. Its hidden content no longer formats an empty time and crashes the normal form.
- Staff screens contained hardcoded English and bilingual copy without an application-wide language preference. They now use a persisted EN/AR preference, the existing translation/interpolation infrastructure, a staff catalogue, translated dates/statuses/errors and RTL layout. Customer-entered names and addresses retain their original text. Translation coverage and interpolation tests protect the catalogue.
- Booking confirmation repeated hold/capacity reads within the same locked transaction. Server-created reservations are now reused only inside that exact transaction; public holds retain full validation. Eligibility queries and capacity reads were consolidated. Authorization, pricing checks, locks, audit writes and durable outbox insertion remain.
- Direct manager/admin cancellation was missing. Job details now provide reason → review → confirmation. The backend enforces role, fresh AAL2, scope, eligibility, version and idempotency. It cancels the booking/job, releases capacity and rewards, removes pending reminders and retains financial/history records. A valid customer email queues one cancellation message; otherwise a persistent manual-notification event is recorded. No automatic refund is issued.
- The mixed revenue/jobs chart now has separate Revenue and Job Activity charts, with currency/count axes, legends, date grouping and accessible values. Existing filters and calculations remain. Mixed-currency report periods are rejected rather than silently summed. Scheduled represents all bookings on the appointment date; completed/cancelled are explicitly labelled subsets.

**Verification**

| Check | Result |
| --- | --- |
| Full backend suite, including local Postgres booking tests | 462 passed; 16 gated cases then run separately below |
| Dedicated Postgres security and migration suites | 18 passed (includes the 16 gated cases) |
| Staff tests | 194 passed |
| Customer web tests | 230 passed |
| Staff/customer TypeScript; staff web export; application Ruff; changed application mypy | Passed |
| Real staging ordinary concurrency | One 201; competing request 409 NO_TEAM_CAPACITY |
| Real staging cancellation permissions | Employee and manager AAL1 both denied with 403 |
| Browser flows | Normal booking, deliberate overlap, Go back, Arabic RTL, manager cancellation and both charts passed |
| Mobile/desktop inspection | Chrome at 320, 390 and 1280 pixels; no JavaScript errors |
| Cancellation worker | One captured message; retry skipped; no pending reminders; payment/audit preserved |
| Report accuracy | AED 150 booked, AED 50 collected; 3 scheduled, 1 completed, 1 cancelled matched API and rendered chart values |

The broader lint command also found pre-existing lint issues in the legacy security test harness; application lint and the new/updated booking tests pass. Native iOS/Android hardware was not tested.

**Measured performance and remaining limits**

Three comparable API samples averaged **6,839.50 ms before → 5,332.78 ms after (22.0% faster)**, with **52 → 37 SQL queries**. Actual browser submission-to-confirmation measured **5,658 ms**, with one POST and immediate disabled/loading feedback. Confirmation followed backend commit; refresh requests were not awaited.

A separate warm request measured 5,153 ms: hold/capacity creation 1,315 ms (11 queries), booking persistence 1,413 ms (12 queries), and the booking transaction 4,236 ms. These phases overlap. Notification-provider time inside booking was zero: delivery already used the outbox and was not the seven-second bottleneck. Database round trips to remote staging dominate.

**The 1–2 second target is not achieved.** These are local-API-to-remote-staging measurements, not hosted preview or production timings. Browser before-change timing was not captured; the before/after comparison is the API measurement. No artificial delay or premature success message was introduced. No deployment was performed.

Evidence: [timings](performance-summary.json), [phase profile](performance-phase-profile.json), [browser flows](browser-results.json), [final chart/modal checks](final-browser-results.json), [staging concurrency/security](staging-concurrency-security.json), [database/worker proof](staging-data-proof.json), [redacted cancellation email](cancellation-email.html).

Screenshots: [320px confirmation](double-book-modal-final-en-320.png), [390px confirmation](double-book-modal-final-en-390.png), [desktop revenue](revenue-en-1280.png), [mobile revenue](revenue-en-390.png). Older captures in this folder record defects found during verification; the `final` confirmation captures show the corrected opaque modal.
