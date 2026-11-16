# Security remediation and follow-up — 11 November 2026

**Current final assessment: [STAGING_FINAL.md](STAGING_FINAL.md).** Staging is at bb63439e5750; native MFA, Storage and 640 role checks completed; the operator is retired. Final suites: **470 backend passed / 2 skipped, 221 website passed, 180 mobile passed**. Native password reauthentication, leaked-password protection and pooler-to-database SSL remain observed failures. Production release is blocked; isolated functional testing may proceed within the final report's limits.

**Historical checkpoint below.** Its paused provisioning, earlier counts and NOT TESTED entries are superseded only where the final report supplies newer evidence. A copy is preserved as FOLLOW-UP-PRE-STAGING.md.

This supplements the initial REPORT.md; its initial snapshots/results remain historical. **Release recommendation: BLOCKED**, pending real provider/device/hosting verification and approved configuration work. No production deployment, migration, factor removal, customer-data mutation or Auth-setting change was performed.

**Staging update:** After the user freed a Free-project slot, `trifecta-staging` was created under BusinessBoost in Frankfurt: `mgfzfgvlrxwyyftwukwf`. Nine migrations are applied through `80826dfc3c2d`; the next upgrade `7d3f2a9c8e41` is paused for explicit user approval. [SQL review and verified empty-state evidence](STAGING_MIGRATION_REVIEW.md). No existing project was paused/deleted by the agent and no billing change was made. Native provider tests remain NOT TESTED; production remains excluded.

## Implemented corrections

- Mandatory Supabase-native TOTP enrollment/challenge UI for privileged staff, including a private enrollment QR code rendered locally with `react-native-svg`. Existing verified factors are challenged instead of re-enrolled. Incorrect/expired codes grant no access. Only abandoned **unverified** enrollments are cleaned up; the app has no verified-factor removal or public recovery API.
- Central backend `staff_context` enforcement for **all manager/admin staff routes**, including context/profile, calendar booking and manager-only operations. Authoritative SQL roles decide who needs MFA. Verified JWT `aal2` and a native `totp` authentication-method claim are required; user metadata cannot supply assurance. No rollout exemption for existing privileged accounts. Employees/customers retain their existing paths; role promotion immediately applies the stronger gate.
- All privileged mutations require TOTP within five minutes. Privileged reads require a TOTP verification within 24 hours. Token refresh does not reset the authentication-method timestamp. Failed mutations are not automatically retried after step-up; the user must resubmit.
- New migration **bb63439e5750** (child of c7e833583da3) adds a private, constrained SECURITY DEFINER boolean function that checks the session's bound factor still belongs to the user and is a verified TOTP. Deployed-mode backend requests use it in addition to the existing active-session check. This closes stale-`aal2` authorization after factor removal. The function grants execution only to the backend runtime group and fixes search_path. It was applied/tested only in the isolated test database. Production must receive the approved migration before this API is released; a missing function fails closed.
- Guest management links expire 30 days after scheduled service completion. Authenticated history remains available through existing ownership-protected APIs. A new fresh-MFA manager-only `POST /api/v1/staff/bookings/{booking_id}/guest-access/revoke` invalidates the stored capability hash and records `guest_access_revoked`. It checks tenant ownership and does not delete the booking. Revocation is permanent for the deterministic guest link: later booking emails/retries may contain an invalid old link; signed-in access/support is the recovery path. A reviewed reissue/versioning feature remains future work.
- Added the controlled, two-person, identity-verified [authenticator recovery procedure](RECOVERY.md), using native Auth Admin factor operations and account/session suspension. No email/password-only bypass or shared recovery secret was added. The production recovery drill remains NOT TESTED.
- Staging now unconditionally suppresses application email delivery, even if a real Resend credential is inherited. Native Auth SMTP is a separate staging configuration and must use a test sink. A regression verifies the application safeguard.

## Actual upgraded database results

Read-only catalog checks found:

| Check | Result | Actual observation |
|---|---|---|
| Applied migration head | PASS | c7e833583da3; matches the **initial audit's** complete head. New follow-up migration bb63439e5750 is intentionally not applied live. |
| RLS | PASS | All 64 public tables have RLS enabled. Existing `backend_only` policies/grants are captured in `follow-up/live-database.json`; local real-role tests continue to exercise all table operations. |
| Anonymous/authenticated privileges | PASS | `SET LOCAL ROLE` inside READ ONLY transactions found **zero** public tables with client SELECT/INSERT/UPDATE/DELETE/TRUNCATE privileges. No application records were selected. An attempted private-function privilege lookup as anon returned schema permission denial. |
| Runtime role attributes | PASS, limited | `trifecta_runtime` is NOLOGIN, non-superuser and NOBYPASSRLS. This is the expected privilege group, not a login credential. |
| Runtime credential adoption | FAIL / High release blocker | The only observed member of this group is **postgres**. No separate backend login inheriting it was found. The migration alone has not established credential separation. Actual hosted DATABASE_URL and TLS connection cannot be verified without hosting access. |
| Existing private session function | PASS catalog/local tests | Empty search_path, execution limited to postgres/runtime; live definition matches expected active, not-banned, verified-user/session checks. Real provider logout/password-reset flows remain NOT TESTED. |
| Job and complaint buckets | PASS metadata | Both are private, with JPEG/PNG/WebP allowlists; limits 8 MiB and 1 MiB respectively. Signed object access against the actual Storage service remains NOT TESTED. |
| Expense bucket | FAIL / release blocker | `expense-evidence` remains absent. |
| Leaked-password protection | FAIL / Medium | Current Supabase advisor still reports disabled. |

Initial c7e833583da3 local migration testing and follow-up full-chain/round-trip tests do not prove backup restorability or production data compatibility for every future migration. Provider-managed Auth tables in local tests contain synthetic minimal rows, not a running Supabase Auth server.

## Verification and evidence

`follow-up/backend.xml` is the canonical complete backend run; `follow-up/backend.txt`, `mobile.txt`, `web.txt` and `typescript.txt` contain actual results. The initial JUnit evidence has not been relabeled as follow-up evidence.

Final local results: **456 backend tests passed, 2 skipped; 179 staff-app tests passed; 221 customer-site tests passed.** Workspace TypeScript, scoped Python mypy, application Ruff and staff web export passed. Bandit retains the same two low-severity invariant assertions. pip-audit reports no known vulnerabilities among scanned packages (the local application distribution is separately source-audited); npm retains 10 moderate, zero high/critical findings. Actual staging/native-provider tests are not included in these pass counts.

| Control / test | Result | Scope / limitation |
|---|---|---|
| AAL1/missing/spoofed assurance | PASS | Real signed local JWT API tests and required-claim unit negatives; context and manager routes deny access. |
| Role change | PASS | A synthetic employee AAL1 session works as employee, then is denied immediately after authoritative promotion to manager. |
| Sensitive-operation freshness | PASS | Old native TOTP AMR timestamp permits bounded read assurance but denies mutations; fresh verification is accepted. |
| Removed factor / stolen old AAL2 token | PASS | Real SQL session-factor binding and actual API request; deleting the synthetic factor denies the unchanged signed token. |
| QR setup, wrong code, subsequent login | PASS with mocked provider | Component tests render decoded QR SVG, reject a provider error without invoking access completion, verify through native challengeAndVerify, and reuse verified factors. **Not a live TOTP enrollment.** |
| Supabase TOTP end to end / recovery drill | NOT TESTED | A dedicated authorized Supabase staging project is needed. No live staff identity was enrolled or modified to simulate staging. |
| Customer/tenant/team isolation, price tampering, SQL injection | PASS | Existing real database/API negative cases rerun, including guest revocation tenant/role controls. |
| Booking concurrency and employee intentional overlap | PASS | Existing isolated PostgreSQL cases rerun; original appointment is preserved and unauthorized actors/teams rejected. |
| Complaints, notifications, file validation | PASS for existing assertions | Synthetic API/service/storage-adapter regressions rerun. Actual provider Storage/Resend delivery, orphan cleanup and malware/CDR remain NOT TESTED. PDFs remain blocked. |
| Guest link expiry/revocation/audit | PASS | Expired capability rejected; active capability works; revoked link rejected; real API authorization/tenant checks and one audit row verified. |
| Staff web production bundle | PASS | Expo export includes the QR renderer; actual Android/iOS binary build, QR scanning and signing still NOT TESTED. Native dependency requires a new native build. |
| Known dependencies | See JSON | Independent pip-audit and npm advisory results preserved; compatible npm fixes attempted without forced SDK changes. No new high/critical advisory was identified in these scans. This is not proof of absence of newly introduced vulnerabilities. |

The final test counts and skip reasons are in the canonical logs/XML. Two older opt-in migration scenarios may remain skipped; their status is NOT TESTED. Native/real provider tests are not counted as passing because mocked calls or builds passed.

## Remaining npm findings

Ten moderate findings remain in Expo/fingerprint/glob/minimatch and TypeScript-ESLint chains. The current direct Expo suggestion is **58.0.23**, a major upgrade from SDK 57, and compatible `npm audit fix --ignore-scripts` does not remove all chains. The initial report's older major-version suggestion was a historical scan result. No forced SDK upgrade or broad incompatible transitive override was made. Before release, perform a coordinated Expo/React Native/native-build upgrade or document time-bounded exposure acceptance for build tooling, with network-isolated builds and no publicly exposed dev servers. Exact packages/ranges/fix suggestions: `follow-up/npm-audit.json`.

## Required operator settings and approvals

These are proposed changes/checks, not changes made during this follow-up:

1. **Supabase Authentication → MFA:** enable native TOTP enrollment and challenge/verification; do not disable verification. Confirm the project's verified-factor removal and additional enrollment restrictions in a lost-device/stolen-password staging drill. Native Supabase removal requires AAL2 for a verified factor; the application additionally rejects factor-less sessions. Supervise first enrollment for existing privileged staff and verify the account holder through company identity records.
2. **Authentication password security:** enable **Leaked password protection** (plan support may be required); set an appropriate strong minimum password policy, enable **Confirm email**, and verify **Secure password change**/reauthentication settings. Inspect email OTP expiry and Auth rate limits: use a documented short expiry and rate budgets consistent with mail volume; test expired, replayed and incorrect codes. Do not replace provider hashing or disable existing protections. [Provider password guidance](https://supabase.com/docs/guides/auth/password-security).
3. **Authentication sessions/abuse:** review JWT expiry (short-lived; e.g. 15 minutes after compatibility validation), refresh reuse/rotation defaults, maximum/inactivity lifetimes where supported, OTP/email/IP limits, and CAPTCHA/attack protection. Actual values were not readable through the connected tools and are NOT TESTED. Verify logout and password-change invalidation through native Auth in staging.
4. **Database credentials:** provision a dedicated INHERIT login with only membership in `trifecta_runtime`, no ownership/superuser/BYPASSRLS/CREATEROLE, using the secret manager. Point the API to that login; retain owner credentials solely for migrations. Verify actual connection identity and certificate/hostname-validated TLS from the hosting environment. Do not grant the runtime group to anon/authenticated. Stage and approve new migration bb63439e5750 before releasing the API.
5. **Storage:** create private `expense-evidence`, limit to the intended receipt image types/10 MiB budget, keep direct client listing/reads denied. Verify separate identities, wrong paths, immutable upload retries, URL expiry and tenant access against actual staging Storage. Keep PDF completion disabled until reviewed scanning/CDR exists. Configure retention/orphan cleanup explicitly.
6. **Vercel:** team authorization still returns 403. In each actual project/environment review production/preview separation, deployment/fork protection, team least privilege/MFA, server-only secret types, exact public variable names, HTTPS endpoints and CORS origins, source-map exposure, cache/WAF/timeout rules and logs. Do not copy backend service/database/signing secrets into NEXT_PUBLIC/EXPO_PUBLIC variables. No claim is made that hosted variables or deployment permissions passed.
7. **Mobile:** rebuild Android/iOS for the new SVG native dependency. Confirm dedicated release signing and existing-install upgrade compatibility, backup/network flags after prebuild, SecureStore behavior, logout erasure and QR scanning on real devices. Native signing credentials were not inspected or changed.
8. **Operations:** verify backup/PITR coverage and perform a restoration drill on an isolated copy; restrict backup access. Configure alerts for failed MFA bursts, recovery events, privilege changes, dependency regressions, dispatcher failures and elevated error/rate-limit rates. Verify platform log redaction/retention and owner-controlled credential rotation. The application's source controls do not establish those hosting controls.
9. **CSP:** initial compatible CSP still permits inline scripts/styles. Strict nonce/hash rollout and actual browser Maps/auth/callback testing remain open. TLS, HTTPS, CORS and security headers must be checked on the hosted deployment after access is granted; earlier local header evidence is not production evidence.

## ASVS follow-up delta and release recommendation

| ASVS area | Follow-up result |
|---|---|
| V6.3.3 strong authentication | PASS for implemented/local privileged gates; **NOT TESTED as a complete requirement** until real provider/device enrollment, login and recovery drills pass. |
| V7.4 session termination | Existing local PASS retained; new active-factor removal negative adds defense. Actual hosted provider session behavior remains NOT TESTED. |
| V8.3 trusted authorization | Local real-role/object/role-promotion checks PASS; no new frontend-only authorization boundary. |
| V9 token integrity | Existing verifier tests rerun; MFA consumes only signature-verified claims. |
| V13.3 least-privilege secrets | FAIL/incomplete deployment: a dedicated runtime login was not observed and hosting secrets are inaccessible. |
| V3.4 CSP | Existing strict-CSP limitation remains; no complete ASVS PASS claimed. |

The original 253-row matrix remains the historical baseline; this delta does not turn its unexecuted requirements into passes. Release remains blocked by **provider MFA/recovery E2E**, runtime login/TLS adoption, missing expense bucket and actual Storage verification, disabled leaked-password protection, Vercel access/configuration, remaining dependency risk, native signing/device testing, backup/monitoring and strict browser controls. New code can be reviewed and staged; production deployment is not authorized.

