# Trifecta Pass 4 release-readiness report

**20 November 2026 · NOT READY FOR PRODUCTION**

## Follow-up on reusing the existing Vercel projects

The revised plan authorizes protected test deployments inside the existing Vercel projects. It supersedes the initial request to create separate projects. The deployment stopped at the isolation preflight. No application was uploaded or deployed and no database, domain, or Vercel setting was changed.

| Existing project | Project ID | Framework and intended source root |
| --- | --- | --- |
| `abdwash` | `prj_7dZRKRKNFRpqXoFlHU1IcKCA0A9U` | FastAPI from `backend` |
| `abdwash-vdtc` | `prj_MNIgizCevSDA1RPoJFD3tHMNZRT9` | Next.js from `apps/web` |
| `trifecta-app` | `prj_48aSnt51DJA0ipRpcUtN8rmG52ZI` | Expo web from `apps/mobile` |

Vercel reports authentication protection for all three projects except on custom domains. Read-only inspection of JavaScript currently served by both public web apps confirmed these bundles use `https://abdwash.vercel.app` and production Supabase `cbejmfjycvzdpqbfiskc`. The backend runtime SQL connection string and effective Preview environment could not be independently verified. Vercel returned HTTP `403` for environment-variable inventory on every project, no authenticated local Vercel CLI was available, and the dashboard automation runtime failed to initialize. Promoting to the public aliases would expose a test candidate on domains outside the reported protection.

| Supabase | Current Alembic revision | Bookings | Payment records | Customer profiles | Auth users | Storage objects |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Production `cbejmfjycvzdpqbfiskc` | `c7e833583da3` | 22 | 22 | 3 | 8 | 4 |
| Staging `mgfzfgvlrxwyyftwukwf` | `d38bf74a923c` | 55 | 55 | 2 | 8 | 3 |

The production schema is incompatible with the full Passes 1–3 candidate. Both projects contain state to preserve. The historical encrypted staging finance export is present and matches its recorded SHA-256. It predates Pass 1 and covers finance rows only. A current recoverable backup covering the required database state and separate Storage objects could not be confirmed. [Historical export scope](../finance-pass-1/README.md) · [Supabase backup and Storage coverage](https://supabase.com/docs/guides/platform/backups)

The safe path remains protected Preview deployments in these same projects, with verified Preview-only staging configuration, `APP_ENV=staging`, the restricted staging database login, staging-only Storage credentials and hosted frontend origins. A qualified project operator needs access to verify the Preview bindings and arrange a recoverable staging snapshot before synthetic workflow writes. Existing public aliases and production configuration can stay in place. No new deployment URL or hosted test result was generated in this follow-up. The prior local and staging-backed checks below remain the available results. [Vercel Preview environments](https://vercel.com/docs/deployments/environments)

## Initial Pass 4 assessment

The existing staging database is current. The Vercel account has no verified isolated application deployment for the candidate, so the hosted acceptance gate remains open. Pass 4 verified the local release candidate, tested several live Supabase boundaries, corrected two UI defects and prepared an isolated deployment candidate. Production data and deployments were untouched.

## A. What is running

Supabase confirmed that `trifecta-staging` (`mgfzfgvlrxwyyftwukwf`) is healthy in Frankfurt (`eu-central-1`). Its live `alembic_version` is `d38bf74a923c`, the single local head. Live migration history contains `a19772ea5f12` (payment reviews and cash allocations), `4c2630a391be` (attendance) and `d38bf74a923c` (vehicle inventory). The three private evidence buckets are present.

The Vercel team inventory showed no dedicated Trifecta staging projects. Explicit preview listings and custom-environment listings for all three Trifecta projects returned empty. The live aliases resolved to these `production` deployments on `main`. The common commit is `aeabfdf854c022ae42427608b09f3532a4d655c1`.

| Live surface | Host | Deployment ID |
| --- | --- | --- |
| FastAPI | `abdwash.vercel.app` | `dpl_DTyHUP3RiozkXeVudySdCAqTJDN2` |
| Customer web | `trifecta-wash.com` | `dpl_Fe22tbcK6LmF3gef9aHVJoL49Pm5` |
| Staff web | `staff.trifecta-wash.com` | `dpl_48CVBLzKFTuPeQxZ9XUVcCxxS6db` |

That commit includes the shared-employee scheduler change. The payment, attendance and inventory/photo pass files are working-tree changes on top of it. There are no staging deployment IDs, endpoint bindings or deployed environment variables to attest for this candidate. The acceptance run did not use the live aliases.

The [staging candidate archive](../../tmp/pass4-release/source.zip) includes the updated API, both web apps, shared source and migrations. The [manifest](../../tmp/pass4-release/source-manifest.json) records its base commit and per-file hashes. It contains 339 files and has SHA-256 `25f03a51eedb6fad344d143aff5251f396d6efd8b66307d3451c78d240f27b7a`. The ZIP was checked against the manifest. Local environment files, credentials, test fixtures, signing files and generated builds were excluded. Approval to create protected staging deployments was requested. No staging deployments were created during this run.

## B–E. Feature verification

| Area | Pass 4 evidence | Hosted acceptance still required |
| --- | --- | --- |
| Booking and scheduling | Source inspection confirmed normal and explicit calendar exception entry points and the shared-employee capacity change. Local regressions ran. Earlier staging-backed local browser/API evidence exercised occupied-slot hiding, concurrent `201`/`409`, direct normal override rejection, explicit calendar double-booking, multi-vehicle duration and stale offer recovery. [Capacity results](../double-booking-capacity/REPORT.md) · [Booking lifecycle results](../booking-corrections/REPORT.md) | Run customer registration and sign-in, guest/account and staff bookings, reminders, cancellations, authorized rescheduling/replacement and job completion against the final hosted stack. Repeat one-person/two-team scenarios for employee, manager and admin with short, long and multi-vehicle services. Verify database rows and distinct authorization for the calendar exception. |
| Finance | The local candidate API used real staging Auth and the restricted SQL login. On the retained synthetic completed booking, SQL recorded AED 50.00 charged, AED 20.00 verified cash, AED 30.00 verified card, AED 1.00 rejected, AED 20.00 allocated to handovers and one invoice. Overview, legacy summary and v2 summary each agreed on AED 0.00 outstanding. The employee received `403` for business finance. Prior Pass 1 evidence covers partial payments, review, refunds/adjustments, duplicate requests and cash custody. [Pass 4 SQL/API results](../../tmp/pass4-readonly-results.json) · [Pass 1 verification](../finance-pass-1/README.md) | Replay mutation and concurrency cases with a new synthetic ledger, then reconcile job and history views against SQL. The customer portal currently shows per-booking payment status and invoices. A self-service transaction ledger for partial payments, adjustments and refunds was not verified and is absent from the examined customer views. |
| Auth and attendance | Synthetic employee, manager and admin received `200` on staff context. Manager AAL1 received `403`, TOTP sign-in and refresh worked, and a locally revoked session received `401` on the next API request. Employees could read their attendance and received `403` for another staff member’s history. Prior evidence covers overnight shifts, break minutes, missing clock-outs, correction audit, CSV and browser recovery. [Pass 4 Auth results](../../tmp/pass4-readonly-results.json) · [Pass 2 verification](../attendance-pass-2/README.md) | Retest new MFA enrollment, expiry, disabled accounts, recent MFA on sensitive actions and app restoration after navigation, background and network changes. Exercise clock, break, correction, audit and CSV on the hosted build. Keep continuous 60-minute endurance as a separate uncompleted check. |
| Inventory and photography | Staging has the vehicle consumption schema. Local tests ran. Prior staging-backed inventory evidence covered sedan/SUV/van, service fallbacks, missing and zero rates, manual changes, concurrent completion, and rollback. Prior browser evidence covers multi-select, removal and partial retry using a Storage fixture. [Pass 3 verification](../inventory-photos-pass-3/README.md) | Complete a hosted job with the same inputs and reconcile per-vehicle lines and movements. Use the real private `job-quality-photos` bucket to sign, upload, validate, finalize and read the same synthetic object. Check other-user and unsigned access denial, expired links and an interrupted retry. The staging-only server Storage credential was unavailable to this run. |

## F. Security and external services

- The live staging catalog had **64 public tables with RLS**, zero public table grants to `PUBLIC`, `anon` or `authenticated`, zero invalid public indexes, and zero unvalidated public constraints. The backend runtime login is a non-owner restricted role under the established staging setup. The live catalog confirmed it inherits `trifecta_runtime` and cannot bypass RLS, create databases or roles, or act as superuser. Tenant and job ownership remain enforced by the API for runtime users. Private helpers for session/factor checks and financial guards are present. The intentional deny-all `alembic_version` policy advisory is informational.
- All three evidence buckets are private with JPEG, PNG and WebP allow-lists. Current catalog evidence and prior real Storage checks establish distinct boundaries. The current candidate’s full signed round trip, permissions, overwrite denial and expiry remain unverified. The prior temporary staging operator is documented as retired. [Security follow-up](../security-audit/STAGING_FINAL.md)
- The prior native password-change finding remains a release gate. The backend has password/TOTP freshness checks. The customer client’s authenticated flow currently submits a new password and an optional nonce. Verify the native current-password setting, compatible authenticated changes and recovery separately using a controlled inbox. Staging Security Advisor still reports leaked-password protection disabled. [Supabase password security](https://supabase.com/docs/guides/auth/password-security)
- The real restricted runtime connection used the configured TLS client to the pooler. PostgreSQL returned `ssl=false` for that session’s database leg, independently reproducing the earlier finding. Resolve and recheck the runtime path. Hosted ingress CORS, security headers, TLS, proxy identity/rate limits, audit retention and sensitive log redaction remain acceptance checks. Local API tests cover source-level access restrictions and security middleware. [Runtime connection result](../../tmp/pass4-readonly-results.json) · [Supabase SSL enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement)
- The production npm dependency audit reported **3 moderate** advisories (`@expo/fingerprint`, `glob`, `minimatch`). The full build and test dependency graph reported **9 moderate**, including the TypeScript ESLint chain. Both scans found zero high/critical. `pip-audit` reported zero known advisories for **39 pinned Windows runtime packages**. Resolve and scan the Linux deployment image separately. Bandit found three low-level assertion findings in application code and zero medium/high.
- Staging dispatch uses the log-only notification provider by design. Live Resend booking mail, reminders and cancellation delivery, Supabase Auth SMTP/OTP/reset delivery, bounce handling and real Maps behavior remain unverified. Exercise providers with controlled recipients and synthetic content. The card-payment gateway adapter is a test implementation. Recorded card tenders and a verified ledger do not establish online processing, refunds or webhook readiness. Keep pay-now disabled unless the gateway is implemented and certified.

## G. Performance and reliability

| Booking measurement | Prior baseline | Prior optimized |
| --- | ---: | ---: |
| API mean | 6.84 s | 5.33 s |
| API median | 6.82 s | 5.19 s |
| API p95, nearest rank | 6.94 s | 5.65 s |
| SQL statements per confirmation | 52 | 37 |
| Browser submission through confirmation | Unmeasured | 5.66 s |

Each API column uses three samples from the prior local-API-to-Frankfurt staging comparison. At this sample size the p95 is the largest observed value. A warm profile attributed about 4.22 s to SQL and zero time to notification providers in the request. Pass 4 obtained no comparable hosted booking samples. The 1–2 s target remains unproven. [Raw baseline](../booking-corrections/performance-before.json) · [Raw optimized run](../booking-corrections/performance-after.json) · [Timing profile](../booking-corrections/performance-phase-profile.json)

Staging advisors returned 53 unindexed foreign-key and 49 unused-index information findings. The catalog includes schedule and resource-window indexes, payment ID coverage in the payment-transaction event index, and outbox claim and deduplication indexes. The live Vercel deployment records list `iad1`, while the staging database is in Frankfurt. Use a Frankfurt-area API candidate, confirm runtime region and connection acquisition, then sample ordinary bookings at least 30 times per comparable candidate, with cold and warm cases tracked separately. Record browser submission-to-confirmation, server timing, SQL and pool checkout, and API/request counts for calendar and reporting. Confirm payment and outbox work remains transactional. Profile specific queries before changing an index or pooling. Exercise lost responses and retry keys across booking, payment, handover and completion.

## H. Impeccable UI audit and fixes

Local Chrome inspected the customer homepage and staff sign-in in both languages, and the Arabic customer sign-in and booking error/retry at **320, 390 and 1,280 px**. The 18 observations had zero horizontal overflow and zero page errors. Input labels and language direction were present on the inspected views. Current audit coverage is the observed screens. The Impeccable engine was unavailable, so the audit used its web/native criteria and manual browser inspection. Authenticated calendar, charts, inventory, attendance, photo layouts and modals have earlier fixture or local staging-backed evidence and require final-candidate coverage. Physical keyboard/IME, screen-reader, system picker and camera behavior remain unverified. [Chrome measurements](../../tmp/pass4-browser-results.json) · [Arabic booking error](../../tmp/pass4-customer-book-error-ar-320.png) · [Arabic staff sign-in](../../tmp/pass4-staff-login-ar-320.png)

| Defect | Root cause and correction | Retest |
| --- | --- | --- |
| Small mobile language controls | Tight padding yielded 30 px targets. The customer language switcher now uses at least 44 × 44 px on narrow or touch-first views. | Chrome measured 44 px high in both narrow layouts and found zero horizontal overflow. |
| Quality history followed device locale and time zone | Inspection and issue timestamps used bare `toLocaleString()`. Both now use the staff-language-aware Abu Dhabi formatter shared with other screens. | Staff regression, type check and Expo web export passed. Physical-device rendering remains open. |

ADB listed zero attached Android devices. A local Android virtual-device definition and older APKs were present. No native candidate was installed or exercised, and no iOS device or simulator was available. Generated Android package manifest inspection confirmed a camera permission in the existing build artifacts. Browser screenshots and manifests do not cover camera capture or native upgrade/signing flows.

## I. Regression and release gates

| Check | Pass 4 outcome |
| --- | --- |
| Backend application regression | **448 passed, 1 skipped, 57 PostgreSQL cases deselected.** The gated suites reset disposable schemas or require a dedicated loopback database. Shared staging was not used for those tests. Two failures during the first runnable attempt came from the harness’s TLS override and passed with the default enabled. |
| Customer web | **230 passed**. ESLint, TypeScript, production build and local browser checks passed. |
| Staff and shared | **195 passed** after the regression addition. Workspace TypeScript and the post-fix Expo web export passed. |
| Python static checks | Application Ruff and strict mypy passed. Full-backend Ruff reported **62 findings** in migrations, scripts and tests. |
| Integrated final-candidate hosted acceptance | **Blocked** by the missing verified application deployment and staging Storage credential. |

| Severity | Outstanding launch work |
| --- | --- |
| **Critical** | Obtain approval for the protected staging deployment and verify the exact API, customer and staff artifacts against the existing staging project. Complete hosted acceptance for capacity/concurrency, the financial ledger, attendance, stock deduction and real signed Storage before considering release. |
| **High** | Close the native password-change gap and verify recovery. Establish the runtime TLS path, restricted production role, production migration readiness and server-only credentials. Validate actual email and private Storage integration with controlled recipients and synthetic files. Complete signed Android/iOS candidate install/upgrade, native photo and session tests for supported platforms. Confirm whether the launch requires a customer-facing transaction ledger or online payments and complete them if required. |
| **Medium** | Run the separate session endurance test and hosted benchmark. Triage npm advisories and broad Ruff findings. Verify plan-supported leaked-password protection, staging/production monitoring and alert routing, callback allowlists, and backup/restore drill results. |
| **Low** | Extend responsive and accessibility coverage to additional device widths, text scaling and assistive technology after the core journeys pass. |

### Deployment and rollback plan

1. After the isolation preflight passes, deploy the archived source or a reviewed candidate commit as protected Preview deployments in the three existing Vercel projects. Use `backend`, `apps/web` and `apps/mobile` as project roots and the monorepo lockfile. Record project and deployment IDs, immutable commit or archive hash, region and exact endpoint bindings. Scope configuration to Preview and keep browser bundles limited to the preview API URL and `https://mgfzfgvlrxwyyftwukwf.supabase.co` with a publishable key. Configure the backend with `APP_ENV=staging`, the restricted staging `DATABASE_URL`, `DB_REQUIRE_TLS=true`, exact preview frontend CORS origins, server-only Storage credentials and staging-specific signing/dispatch secrets. Configure staging Auth redirects and a controlled email verification route. Check migrations, private buckets and the recoverable snapshot before serving test traffic. Leave public aliases on the existing deployments.
2. Run hosted acceptance against that exact candidate. Keep the test identities, periods and media synthetic. Save request IDs, candidate identities and sanitized results. Run the destructive regression suites only in an explicitly approved disposable environment later. Confirm production readiness only after blockers close.
3. For a separately approved production release, verify the actual Alembic head, capture a restorable backup and check rollback compatibility, restricted runtime access, configuration, providers and bucket policies. If the head is still `c7e833583da3`, rehearse `bb63439e5750` → `a19772ea5f12` → `4c2630a391be` → `d38bf74a923c` in order. Reconcile existing payment headers and receipt allocations after the finance backfill. Ensure storage, auth, audit and inventory settings are ready. Deploy matching API, customer web, staff web and signed native builds in the approved change window, with booking and finance smoke checks before broader rollout.
4. On a regression, halt rollout and pause affected writes and outbox dispatch if needed. Restore the previously recorded compatible app deployment IDs and verify the schema contract before reopening traffic. The finance downgrade is guarded against records that the previous schema cannot represent. Preserve payment, allocation and stock history, and use a reviewed forward repair or coordinated recovery from the verified backup. Reconcile bookings, balances and cash custody before resuming transactions. [Deployment reference](../deployment.md) · [Migration and reconciliation details](../finance-pass-1/README.md)
