# Isolated trifecta-staging setup — provisioned and technically verified

**Current state:** the full 30-revision chain is applied through bb63439e5750. All three private buckets, a dedicated non-owner runtime login, two synthetic tenants and eight native identities exist. The temporary operator is disabled and its credential removed. Native TOTP/Storage, 640 role checks and API regressions have completed. See [STAGING_FINAL.md](STAGING_FINAL.md) and [STAGING_DATABASE.md](STAGING_DATABASE.md). Do not repeat bootstrap or re-enable the operator for ordinary functional tests.

**Historical setup notes below:** paused-migration/capacity statements are retained for provenance; the final report supersedes them. Provider password protection, second-leg TLS and hosted/device/integration prerequisites remain open. Functional work must use explicit isolated configuration without loading production .env values.

Authorized target: **BusinessBoost**, organization `wmobhflelxzpffieefuv`, **Frankfurt eu-central-1**. Separate new project named **trifecta-staging**. Never use or branch/restore data from live project `cbejmfjycvzdpqbfiskc`.

The initial creation attempt was rejected by the two-active-Free-project limit. The user subsequently paused another project. A retry successfully created **mgfzfgvlrxwyyftwukwf** on 11 November 2026. The project is healthy. No existing project was paused, deleted or upgraded by the agent and no billing change was made.

## Current approval checkpoint

Nine upgrades have applied through **80826dfc3c2d**. The next upgrade **7d3f2a9c8e41** is paused at the user's explicit request for review before approval. The connector's previous confirmation expired without applying that upgrade.

See [STAGING_MIGRATION_REVIEW.md](STAGING_MIGRATION_REVIEW.md) for exact SQL, its hash, update purposes and verified zero-row staging state. Do not create another project or seed fixtures before the migration chain finishes. Subsequent provisioning remains confined to this staging reference.

## Configuration prepared for review

- `backend/.env.security-staging.example` defines a separate environment. Generate unique project/API/database, management-signing and dispatch credentials. Keep values in an ignored local file/secret manager, never this document or Git. Browser/mobile clients receive only the **new staging publishable key** and staging API URL.
- Apply the **actual Alembic chain** through `bb63439e5750` using a dedicated staging migration connection. Do not stamp a head over an empty schema or copy production tables. Verify the resulting tables, constraints, grants, RLS and private functions, not just the version string.
- Provision a distinct non-owner backend login inheriting `trifecta_runtime`, verify NOBYPASSRLS and no schema ownership/TRUNCATE, and use verified TLS. The migration owner credential must not become the running API credential.
- Create private buckets `job-quality-photos` (8 MiB), `complaint-evidence` (1 MiB), `expense-evidence` (10 MiB), restricting raster MIME types to JPEG/PNG/WebP. Keep direct client listing/reads/writes denied; object-specific grants originate from the scoped API. PDFs remain unfinalized pending a safe scan/CDR path.
- Do not install the production Cron/Vault dispatch schedule, production mail/Maps/payment credentials, production webhooks or customer integrations. APP_ENV=staging now forces log-only application notification delivery **even if provider credentials are accidentally inherited**. Log-only dispatch is not evidence of real email delivery.
- Supabase Auth mail is separate: configure a dedicated test SMTP sink/mail-capture system before email OTP/recovery tests. Never use a real customer address. Use reserved synthetic test identities and native Admin-created confirmed accounts for TOTP-only tests so setup does not send mail.
- Enable native TOTP enrollment and verification. Configure strong password/breach protection where the plan permits, email confirmation, secure password change, short OTP/JWT lifetimes and provider rate limits. Record actual settings/plan limitations rather than assuming production settings were inherited.
- Seed only synthetic customer A/B, two teams and two tenants, employees, two administrators and a manager. Generate test passwords and TOTP secrets at runtime; do not hardcode them or place secrets in evidence. No live customer data export/import is allowed.

## Verification to continue after provisioning

1. Native Auth registration/email confirmation, sign-in and issued-token verification; invalid issuer/audience/signature/expiry and customer/staff role boundaries.
2. Native TOTP QR enrollment, challenge and correct/incorrect/expired/replayed codes; first setup, subsequent login, fresh step-up, concurrent enrollment and verified-factor removal restrictions.
3. API AAL1 denial, role promotion, AAL2 success, stale AMR rejection, logout/ban/session deletion, removed-factor rejection and different-tenant authorization.
4. Lost-device drill with two administrators and restricted audit events per RECOVERY.md; no password/email-only recovery or temporary MFA exemption.
5. Real anon/authenticated/runtime SQL roles and synthetic JWT identities across every application table/RPC; private buckets, wrong object paths, immutable retries, upload content validation and short-lived signed-download expiry.
6. Full customer booking/cancellation, employee explicit overlap, manager reschedule, complaints and log-only outbox regressions. No real charges/refunds or outbound customer notifications.
7. Real browser and native-device enrollment/QR scanning and app logout/signing checks; record PASS/FAIL/NOT TESTED separately. Preserve current local/mock-provider test results without relabeling them as native-provider E2E.

Current staging status: **CREATED**, project `mgfzfgvlrxwyyftwukwf`, healthy in BusinessBoost/Frankfurt. The earlier capacity rejection below is historical; the user freed a slot. Nine migrations are applied through `80826dfc3c2d`. Upgrade `7d3f2a9c8e41` is paused for explicit user approval; see [STAGING_MIGRATION_REVIEW.md](STAGING_MIGRATION_REVIEW.md). No Auth users or customer fixtures have been seeded. Real Supabase MFA/recovery/Storage E2E remains NOT TESTED.

