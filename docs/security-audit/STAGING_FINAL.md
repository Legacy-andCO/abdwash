# Trifecta — final follow-up assessment

Assessment date: **11 November 2026**. **GO for isolated functional testing with synthetic data. NO-GO for production release.** Complete hosted/browser/device functional sign-off still needs the prerequisites below. This is not a complete-security or ASVS Level 2 compliance claim.

All remote mutations targeted **trifecta-staging `mgfzfgvlrxwyyftwukwf`**, BusinessBoost, Frankfurt. Live ABDWash `cbejmfjycvzdpqbfiskc` was not modified, deployed to, reset or attack-tested. No real charge/refund or customer email was sent. Earlier [REPORT.md](REPORT.md) and [pre-staging follow-up](FOLLOW-UP-PRE-STAGING.md) are historical evidence, not current staging results.

## Executed results

| Check | Final result | Evidence and limits |
|---|---|---|
| Complete backend suite | **PASS — 470 passed, 2 skipped** | [JUnit](follow-up/backend.xml), [log](follow-up/backend.txt). The two opt-in catalogue/review migration scenarios are NOT TESTED in this run. |
| Complete website suite | **PASS — 221 passed** | [Log](follow-up/web.txt). Component/unit tests, not hosted browser sessions. |
| Complete mobile/staff suite | **PASS — 180 passed** | [Log](follow-up/mobile.txt). Does not establish native-device/signing behavior. |
| Workspace TypeScript / application Ruff / scoped mypy | PASS | [TypeScript](follow-up/typescript.txt), [Ruff](follow-up/ruff.txt), [Python types](follow-up/python-types.txt). |
| Native Auth and Storage | **PASS — 67 checks** | [Results](follow-up/staging-native.json), [original executed log](follow-up/staging-native.txt). Actual password/TOTP/challenge/factor restrictions and private Storage requests. |
| Native JWT → FastAPI → restricted staging SQL login | **PASS — 42 assertions** | [Results](follow-up/staging-api.json). Real native tokens/JWKS and database connections; in-process ASGI requests, no authentication mocks. One unconditional schema-field diagnostic was removed from test counts; original raw log retained. |
| Technical MFA recovery sequence | **PASS — 24 checks** | [Results](follow-up/staging-recovery.json). Two synthetic admin identities, suspension, native factor/session operations and three audit events. Independent human approval/identity proof remains NOT TESTED. |
| Final authentication regression | **PASS — 3 checks** | [Results](follow-up/staging-auth-regression.json). Naturally expired native JWT returns 401/ExpiredSignatureError; forged AAL/role claims return 401; naturally aged native TOTP denies a privileged mutation with 403. This supersedes the earlier recovery run's age-window NOT TESTED entry. |
| Remaining API integrations | PASS for stated assertions | [Run](follow-up/staging-remaining.json): 19 PASS and two harness expectation failures. Cancellation correctly returned documented **201**, rather than the harness's expected 200; [separate correction](follow-up/staging-cancellation-correction.json) verifies 201 and replay equality without another cancellation. Complaint isolation/idempotency/rate limiting, invalid parameters, concurrent holds and ten log-only notification deliveries passed. |
| Database client roles | **PASS — 640/640 denials** | [Results](follow-up/staging-role-results.json), [SQL](follow-up/staging-role-probe.sql). 64 tables × two roles × five operations, all 42501. Exception rollback boundaries protected fixtures. Completed checks were not rerun in the final continuation. |
| Migration/catalog integrity | PASS | [Final catalog](follow-up/staging-catalog_final.json), [history](follow-up/staging-migration_history.json), [30-revision manifest](follow-up/staging-migration-manifest.json). Head bb63439e5750; 64 public tables, all RLS; zero invalid indexes/unvalidated constraints. |
| Operator retirement | **PASS — 4 checks plus deployed-source inspection** | [Cleanup](follow-up/staging-operator-cleanup.json), [retired source](follow-up/staging-operator-retired.json). Anonymous, former operator credential and customer requests all receive 410. |
| npm advisories | **FAIL — 10 moderate remain** | [JSON](follow-up/npm-audit.json). Zero high/critical dependency advisories; that does not mean zero high application/configuration risks. |
| Python advisories | PASS within coverage | [JSON](follow-up/pip-audit.json), [log](follow-up/pip-audit.txt). No known vulnerabilities among scanned packages; local application distribution is separately source-audited. |
| Bandit | Reviewed LOW findings | [JSON](follow-up/bandit.json): two B101 invariant assertions; no medium/high finding. |

The JavaScript runners first hit EPERM renaming files in an external sandbox temporary directory. Separate writable workspace temporary directories allowed both complete suites to run normally; no OS protection or platform authorization was bypassed. Initial logs are retained as `web-sandbox-blocked.txt` and `mobile-sandbox-blocked.txt`. A backend brand assertion identified a duplicated legacy slug in the staging harness; it now imports DEFAULT_BUSINESS_SLUG, without weakening the assertion. Earlier API attempts also preserve payload/fixture and HTTP-status harness repairs; those are not final application failures or extra passing tests.

## Corrections and confirmed residual vulnerabilities

| ID | Severity / state | Root cause, impact and evidence |
|---|---|---|
| FU-01 | Low availability regression — **FIXED** | A valid freshly refreshed native token sometimes failed with ImmatureSignatureError because issuance was slightly ahead of the API clock. The executed trace observed API 200 before refresh, native refresh 200, immediate verifier failure, then API 401. Only **iat** and native authentication-method timestamps receive at most **five seconds** of tolerance. There is **no blanket JWT leeway**: exp remains strict. Invalid/null/nonfinite/negative or substantially future iat values are rejected. HS256/asymmetric regressions, full suite and subsequent native API checks pass. See [trace](follow-up/staging-clock-failure-observed.json), `test_jwt_issuance_skew.py` and `test_privileged_mfa.py`. |
| FU-02a | High account persistence risk — **API PATH FIXED** | An old employee session could reach Auth Admin password replacement. The isolated pre-fix API test returned 200 with a recording provider adapter: [evidence](follow-up/password-reauth-before.txt). Employee password changes now require native password AMR within five minutes. Old-session denial precedes the provider call; a recent legitimate sign-in still succeeds. Manager/admin mutations retain fresh TOTP. Staff UI explains sign-out/sign-in. This exploit regression did not reset a real password. |
| FU-02b | **High — OPEN, native-provider boundary** | Both synthetic employee and manager AAL1 tokens could replace passwords directly through Supabase `/auth/v1/user`, without another reauthentication step: **two HTTP 200 results**, [evidence](follow-up/staging-password-native.json). Random replacement passwords were saved only in ignored test configuration. This can turn a stolen employee session into persistent account access. Password replacement alone did not demonstrate bypass of manager TOTP. The API fix does **not** close this independent native path. Production's exact setting was not inspected; release is blocked until native current-password protection and compatible client/recovery flows are verified. |
| FU-03 | **Medium — OPEN, transport configuration** | Client → Frankfurt pooler verifies the certificate and hostname using Supabase's public CA. However, PostgreSQL reports **ssl=false** for the actual runtime connection from the pooler: [evidence](follow-up/staging-cancellation-correction.json). The entire path must not be called verified TLS. Provider-internal network exposure/guarantees were not independently inspected. Configure/test SSL enforcement or an approved fully encrypted connection path; never disable client verification. |
| F18 | **Medium — OPEN** | The final staging advisor reports leaked-password protection disabled, as did the earlier production inspection: [advisor](follow-up/staging-advisors_final.json). Owner configuration/plan support remains required. |

No production secrets were rotated. Synthetic passwords/TOTP secrets and the non-owner staging SQL credential remain in ignored configuration; values are not in this report. The temporary operator credential was revoked through endpoint retirement and removed locally.

## MFA implementation and recovery assurance

Managers/admins must use native Supabase TOTP enroll/challenge/verify. The staff app displays the QR locally, challenges existing verified factors on subsequent login and grants no privileged shell at AAL1. Employees/customers retain normal sign-in. SQL staff/business active state and role, not user metadata, determine authority. Promotion immediately applies the stronger gate.

All manager/admin staff routes require native AAL2/TOTP within 24 hours; mutations require verification within five minutes. Refresh preserves the AMR timestamp. Migration bb63439e5750 adds an empty-search-path, runtime-only private helper checking the session's **currently verified, owned TOTP factor**. Native factor removal caused the unchanged AAL2 token to be denied; native global sign-out invalidated API access and refresh-token replay. Native AAL1 could neither remove a verified factor nor enroll its replacement.

[Recovery](RECOVERY.md) uses identity verification and two operators, staff suspension, native Auth Admin session/factor operations, supervised re-enrollment and audit records. The technical drill kept staff suspended until the replacement factor verified; the AAL2 token still received 403 until explicit restoration. It used two **synthetic identities**, not independently verified humans. Human identity proof, social-engineering resistance, independent approval governance and production operation remain NOT TESTED. There is no public password/email-only recovery API or temporary MFA exemption.

Existing privileged accounts require supervised first enrollment. AAL1 has no privileged API window, but an attacker already holding the first-factor credential before first enrollment remains an operational enrollment risk. Actual authenticator-app QR scanning, multi-device UI behavior, native builds/signing and lost-device UX are NOT TESTED; API enrollment and component mocks do not establish them.

## Database and Storage boundaries

The approved 7d3f2a9c8e41 SQL matched the reviewed SHA-256 **b67068f2ba7c6b0e23027ba1919a2555d15f61b3b2ac6cc2967f1ffd0440ce9f** before execution (UTF-8/LF/no trailing newline). Thirty real Alembic upgrades ran in order. The final fifteen were one transaction with an empty-application/zero-Auth-user guard and predecessor assertions. Sixteen Supabase history entries therefore represent thirty upgrades, not a stamp over a snapshot. No completed migration was repeated in the final continuation.

| Boundary | Result / interpretation |
|---|---|
| All 64 public tables | RLS enabled; client table access denied. alembic_version intentionally has no policy. See the [table-by-table matrix](STAGING_DATABASE.md). |
| anon/authenticated | All 640 real SQL denials pass; separate native customer Data API requests also return 403. |
| Runtime | trifecta_staging_api is LOGIN/INHERIT, non-owner, non-superuser, NOBYPASSRLS, NOCREATEDB and NOCREATEROLE. Cannot assume postgres, read auth.users or read migration state. |
| Tenant isolation | Runtime DML policies deliberately allow business rows across tenants. **FastAPI is the tenant/object boundary**, not per-customer database RLS. Executed native API cases deny other customers, teams and tenants. |
| Private helpers | Constrained SECURITY DEFINER booleans, fixed search_path, execution limited to owner/runtime. Actual session/factor behavior verified. |
| Integrity / synthetic inventory | Two tenants, two customers, six staff, eight native Auth users; no customer import; zero invalid public indexes/unvalidated constraints. |
| Private buckets | job-quality-photos: 8 MiB; complaint-evidence: 1 MiB; expense-evidence: 10 MiB. All private, JPEG/PNG/WebP allowlists. |
| Actual Storage service | Immutable signed uploads succeed and reject overwrite even with requested upsert; direct reads/listing denied/empty for anon and separate customers; signed downloads work, expired/wrong-path URLs fail; active SVG MIME rejected. |
| Complete hosted API → Storage adapter → finalizer | **NOT TESTED as full E2E.** Native service requests and local decoder/ownership/size/frame regressions pass. The local API never received a persistent service-role key. Full complaint-photo/job/expense upload/finalize/download still needs owner-controlled staging credentials and hosting. PDF completion stays blocked pending reviewed scanning/CDR. |
| Transport | Verified client → pooler TLS; **FAIL** on observed pooler → database SSL. |

The advisor's alembic_version deny-all INFO is intentional. Its leaked-password WARN is unresolved, not dismissed because other tests passed.

## Disposition of original findings

| Findings | Current disposition |
|---|---|
| F01 | Compatible dependency updates retained; ten moderate npm chains remain. Coordinated Expo/native SDK upgrade or documented time-limited risk acceptance is required; do not force a scanner's major-version suggestion blindly. |
| F02–F04 | Team directory, immutable evidence and resource-limit fixes retained. Native team/Storage negatives and staging complaint/concurrent-hold limits pass. Full finalizer and distributed ingress/proxy/WAF remain untested. |
| F05–F08 | Session revocation, validation disclosure, required JWT claims and JWKS amplification fixes pass regressions. Native revocation/expiry/factor removal add real provider evidence; FU-01 fixes the clock regression. |
| F09–F10 | Source CORS/key/TLS enforcement passes. Production adoption remains unverified; FU-03 exposes the staging second-leg transport gap. |
| F11–F13 | Redirect/cache/signing source controls retained. Hosted browser callbacks, physical-device storage and signed native release/install upgrade remain NOT TESTED. |
| F14–F16 | Incomplete online payments fail closed; idempotency, inactive-profile and forced-password-change regressions pass. FU-02 adds the credential-boundary finding. Real card provider/webhook/refund tests are NOT APPLICABLE to the currently unwired integration. |
| F17 | Native MFA and API enforcement implemented and technically verified in staging. Supervised rollout, native UX and human recovery remain open. Production has not received the new code/migration. |
| F18 | Leaked-password protection remains OPEN. |
| F19 | Staging chain and all buckets fixed. Last production metadata was c7e833583da3 with expense-evidence absent; new factor helper and dedicated runtime-login adoption remain **High production release blockers**. |
| F20 | Staging real client-role denials pass; earlier upgraded production read-only grant checks denied clients. Actual production owner-credential replacement remains unverified. |

Guest links retain 30-day-after-service expiry and tenant-scoped fresh-MFA revocation/auditing. Local regressions pass. Deterministic link revocation is permanent; old queued emails may carry invalid links and signed-in/support access is the recovery path. Production retention/reissue/key-rotation policy remains a manual review item.

## Operator retirement

The only staging function slug now serves static **410 operator_permanently_disabled**. Deployed version 4 has **no imports, secret reads, Auth Admin calls, Storage grants or data access**. The old random operator credential authorizes nothing and was removed from ignored configuration. The preparation helper refuses to regenerate a retired operator. Canonical endpoint checks and deployed-source/function-inventory inspection found no remaining privileged test endpoint.

Supabase's built-in service-role key was never returned to clients or this report; no unrelated project-key rotation was needed. The restricted runtime login and synthetic account credentials remain for authorized functional work and are not operator recovery credentials. Keep ignored configuration private.

## Manual configuration and unexecuted checks

1. **Native credential protection — High blocker:** Authentication → Email provider / Password security → **Require current password when changing password**. Prepare compatible normal password-change clients using native `current_password`, and verify legitimate forgot-password/recovery flows separately. Existing web updateUser calls send only a new password; do not enable a breaking setting blindly. Retain API fresh-password/TOTP checks on Admin paths. Retest stolen AAL1 credential replacement. [Native guidance](https://supabase.com/docs/guides/auth/password-security).
2. **Transport — Medium blocker:** Database → Settings → SSL Configuration → **Enforce SSL on incoming connections**. Supabase documents both shared-pooler legs and a possible database restart. Review the change, then verify certificate/hostname checks and actual PostgreSQL ssl=true. If unavailable, use an owner-approved supported encrypted path. No certificate bypass, paid add-on purchase or unavailable dashboard operation was attempted. [SSL guidance](https://supabase.com/docs/guides/platform/ssl-enforcement).
3. **Password/OTP controls:** configure strong minimum length and plan-supported leaked-password protection; Supabase documents Pro-or-higher support. A paid upgrade needs actual owner price approval. Native confirmation, SMTP, email OTP/reset expiry/replay, anti-enumeration, CAPTCHA and full Auth rate-limit/session policies remain NOT TESTED. No test SMTP sink exists; never run these using customer addresses.
4. **Production adoption — High blocker:** separately approved bb63439e5750 migration/private expense bucket; dedicated non-owner backend login; verified actual hosted connection identity/TLS and server-only secret scopes. Production remains untouched.
5. **Hosting:** Vercel team access returned 403. Production/preview environment separation, deployment/team privileges, HTTPS/CORS/CSP/headers/cache/WAF/source maps, proxies and logs remain NOT TESTED on hosting. No scope bypass was attempted. A separate staging API/frontend URL, callback configuration and owner-managed server credentials are prerequisites for hosted functional testing.
6. **Native/integrations:** QR scanning, subsequent-login/step-up/lost-device UX, SecureStore/logout forensics, Android/iOS signing/build/install upgrades, Maps and full evidence finalization remain NOT TESTED. New SVG dependency needs a native rebuild. Test sink/provider delivery, retention/orphan cleanup, backup/PITR restoration, monitoring/redaction/retention and secret-rotation drills remain open. The ten worker deliveries here were log-only, not Resend deliveries.
7. **Browser controls:** compatible CSP still permits inline scripts/styles. Strict nonce/hash rollout and real browser integration testing remain open.

## ASVS assurance and functional-test recommendation

[ASVS.md](ASVS.md) remains the conservative historical 253-row L1/L2 baseline; no unexecuted requirement has been relabeled PASS. This follow-up adds real MFA/session/authorization/token evidence but has observed native password, leaked-password and transport FAILs. Human recovery, hosting and device requirements remain unverified. Bearer-path cookie flags/classic ambient-cookie CSRF and unwired card-provider checks are NOT APPLICABLE only to those identified paths.

Proceed with isolated synthetic functional testing of permitted workflows, with external email/payment delivery disabled and the operator retired. A **complete hosted/browser/device sign-off is still gated** by the prerequisites above. Use explicit staging settings, never an inherited production .env. Stable ignored management-signing/dispatch values are now retained; guest links from earlier ephemeral probe runs are historical fixtures and cannot establish deployment compatibility.

**Production recommendation: NO-GO.** No production deployment approval is requested or implied. Scanner counts and passing regressions support only their stated evidence, not a claim that the system is completely secure.
