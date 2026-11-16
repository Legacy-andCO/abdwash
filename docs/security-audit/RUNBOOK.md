# Reproduction and release runbook

**Current results and remaining gates:** [STAGING_FINAL.md](STAGING_FINAL.md). The staging chain already reaches bb63439e5750; do not rerun bootstrap or the one-time enrollment script. The temporary operator is retired and its helper refuses to regenerate credentials. Existing synthetic sessions may need normal native sign-in/challenge preparation; that does not authorize a recovery bypass.

Final local runs use the loopback-only database URLs below. For Vitest, set process-local TEMP/TMP to separate writable directories under repository tmp/test-web and tmp/test-mobile; no OS protection needs disabling. The native/API harnesses hard-pin the staging project, pooler host and restricted login, and never read production .env. Secrets remain in ignored tmp/security-staging.json; do not print/commit them. The whole native-provider/password/Storage administrator pipeline is not a replayable public operator endpoint. Full hosted evidence workflows and provider settings need owner-controlled staging credentials/access.

For the mandatory TOTP follow-up, use [FOLLOW-UP.md](FOLLOW-UP.md) and the controlled [recovery procedure](RECOVERY.md). The follow-up source head is `bb63439e5750`; stage that new migration before releasing the MFA-enforced API. Do not overwrite initial audit evidence when collecting follow-up results.

## Safety boundary

Tests must use disposable PostgreSQL databases on loopback, with synthetic data only. The new security suite refuses any URL whose host is not localhost/127.0.0.1/::1 or whose database name lacks `security_boundary_test`. It recreates schemas **only in that explicitly selected test database**. Existing integration tests also drop/recreate their local test tables. Never point either URL at a production/staging/customer database. Do not enable the older opt-in migration tests against an inherited `.env` connection.

This audit created an ignored portable runtime under `tmp/postgres-runtime`, a test cluster under `tmp/security-pg-data`, bound it to **127.0.0.1:55432**, and used `audit_owner` with local-only trust authentication and no real secrets. This is disposable test configuration, not a production recommendation. Its origin/version/hash are recorded in the environment evidence. Do not bind it to an external address.

## Repeat the local verification (PowerShell)

From the repository root, start an equivalent isolated PostgreSQL instance. If using the audit's already initialized portable cluster:

```powershell
& tmp/postgres-runtime/pgsql/bin/pg_ctl.exe -D tmp/security-pg-data -l tmp/security-pg.log -o '-h 127.0.0.1 -p 55432' -w start
# Create these empty databases only if they do not already exist.
& tmp/postgres-runtime/pgsql/bin/createdb.exe -h 127.0.0.1 -p 55432 -U audit_owner trifecta_security_test
& tmp/postgres-runtime/pgsql/bin/createdb.exe -h 127.0.0.1 -p 55432 -U audit_owner trifecta_security_boundary_test
```

The cluster needs synthetic Supabase client roles before applying the older repository migrations:

```sql
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
```

The new migration provisions a NOLOGIN `trifecta_runtime` group itself. No production login password is created or changed. The security fixture creates minimal synthetic `auth.users`/`auth.sessions` tables for session tests; these are not a complete Supabase Auth installation.

```powershell
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'postgresql+asyncpg://audit_owner@127.0.0.1:55432/trifecta_security_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:SECURITY_TEST_DATABASE_URL = 'postgresql+asyncpg://audit_owner@127.0.0.1:55432/trifecta_security_boundary_test'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
Set-Location backend
& .venv/Scripts/python.exe -m pytest -p pytest_asyncio.plugin -q --junitxml=../docs/security-audit/evidence/all-backend-tests.xml
Set-Location ..
npm.cmd run test --workspace=@trifecta/web
npm.cmd run test --workspace=@trifecta/mobile
npm.cmd run typecheck
npm.cmd run lint --workspace=@trifecta/web
npm.cmd run build --workspace=@trifecta/web
```

Windows asyncio/socket operations stalled in the restricted execution sandbox; tests were run in the approved local execution context. This does not require an internet-facing server or production access.

The pre-fix exploit assertions are preserved in `exploits-before.xml` (five failures, three passes) and `team-scope-before.xml` (one demonstrated team-directory failure). Re-running those tests on the hardened source should pass. Do not restore vulnerable code to production to reproduce them.

## Scanners and evidence regeneration

Tool versions used include Bandit 1.9.4, detect-secrets 1.5.0 and pip-audit 2.10.1. npm and pip advisory requests send dependency names/versions to their public services; this transfer was explicitly approved in this audit. Secret scans use offline/no-verification mode, so candidate values are not sent to verification services.

```powershell
& backend/.venv/Scripts/python.exe -m bandit -r backend/app -f json -o docs/security-audit/evidence/bandit-after.json
& backend/.venv/Scripts/python.exe -m ruff check backend/app --select S --output-format json
npm.cmd audit --json
& backend/.venv/Scripts/python.exe -m pip_audit --local --format json
& backend/.venv/Scripts/python.exe backend/scripts/security_history_scan.py
& backend/.venv/Scripts/python.exe backend/scripts/security_inventory.py
& backend/.venv/Scripts/python.exe backend/scripts/security_report_inventory.py
```

The detect-secrets run used a process-scoped Git safe-directory exception (the checkout has different Windows ownership), not a global Git configuration change. Its JSON contains hashed candidates, never raw secrets. The history scanner records only type, path, line, blob and disposition; 27 binary/large objects are explicitly excluded.

An independent offline Python check can use the downloaded public database ZIP without sending an inventory:

```powershell
& backend/.venv/Scripts/python.exe backend/scripts/security_python_audit.py tmp/pypa-advisory-database.zip docs/security-audit/evidence/python-advisories-after.json
```

It is a limited PyPA range comparison, not a replacement claim for pip-audit. Preserve the source/hash and retrieval date. `requirements-security.txt` provides the audited runtime constraints; build and scan a separate resolved lock/image for the actual deployment OS.

## Review groups

| Group | Principal files | Evidence |
|---|---|---|
| Identity/session/HTTP boundary | `auth/*`, `core/config.py`, `main.py`, `core/http_security.py` | pre-fix exploit file, authentication tests, final suite |
| Database and abuse controls | migration `c7e833583da3`, `api_rate_limits.py`, rate model, `idempotency.py` | role matrix, session/rate/rollback/idempotency tests |
| Ownership and operational permissions | `workforce.py`, customer profile upsert, staff account creation | team-scope before/after, customer/tenant tests |
| Files/evidence | storage adapter, image validator, complaint validation, completion routes, immutable upload retry | forged image/MIME and signed-grant tests |
| Browser/mobile/deployment | redirect helper, headers, memory-only cache, native defaults/signing plugin | Vitest, types, production build/header smoke; native runtime untested |
| Dependencies and audit artifacts | manifests/lockfile/runtime constraints, scripts and this directory | npm/pip/offline/static/secret outputs |

Existing test fixtures were repaired where the audit exposed obsolete assumptions: loop scopes, missing service price rows, renamed team/member values, invoice/payment/checklist contracts, consumed-hold behavior and outdated Arabic copy. The API was not weakened to satisfy those assertions. All changes remain local and uncommitted for review.

## Production release gate (separate authorization required)

1. Provision an isolated Supabase staging project, with no copied customer records. Set exact Auth callbacks, explicit HTTPS origins, strong keys and `APP_ENV=staging`.
2. Apply the entire Alembic chain through `c7e833583da3`; verify the private session function is created on real Auth tables. Test session removal, password change, suspension, bans, unverified email and token replay through the actual provider.
3. Create a separate secret-managed backend login inheriting `trifecta_runtime`. Do not grant that group to anon/authenticated. Verify it is neither table owner nor BYPASSRLS/superuser, cannot TRUNCATE/alter schema/read Auth secrets, and can execute only the required private session function.
4. Confirm the actual PostgREST exposed schemas and direct client denials, including all current tables/views/functions. Enforce future migrations with explicit RLS and matching runtime grants/policies; the new default-privilege changes do not automatically secure an arbitrary future schema design.
5. Set `DB_REQUIRE_TLS=true`; exercise the actual database hostname and certificate chain. Configure ingress proxy trust deliberately: application limits use ASGI client addresses, never raw forwarding headers. Confirm the platform supplies the intended peer address and cannot be spoofed.
6. Create/verify private complaint/job/expense buckets, MIME/size limits and object-specific access. Test unauthorized paths and signed URL expiry using synthetic accounts and files. Keep PDF finalization blocked until scan/CDR is implemented.
7. Implement/enforce privileged MFA and verify recovery/reauthentication. Enable appropriate provider password/breach protection, OTP/reset/email limits, anti-enumeration and abuse controls. Verify the active 24-hour cancellation policy.
8. Complete browser/device/WAF/backup/retention/processor and financial gates in REPORT.md. Verify final artifacts and dependency findings for the exact host image. Do not treat this local scan as production verification.
9. For Android, provide `TRIFECTA_RELEASE_STORE_FILE`, `TRIFECTA_RELEASE_STORE_PASSWORD`, `TRIFECTA_RELEASE_KEY_ALIAS`, and `TRIFECTA_RELEASE_KEY_PASSWORD` through protected build credentials. Re-run Expo prebuild and inspect the generated defaults. Verify existing-package signing compatibility before distribution; no key was generated/rotated by this audit.
10. Only after review, backup/restore validation and a separately authorized release may production migrations or deployments be considered. Run a quiet synthetic smoke test there only within that authorization.

Stop the audit's local services after verification:

```powershell
& tmp/postgres-runtime/pgsql/bin/pg_ctl.exe -D tmp/security-pg-data -m fast -w stop
```

The audit left production unchanged. The local server was stopped at handoff; retained test artifacts/runtime files are ignored under `tmp/` for reproducibility.
