# Browser verification

Run from the repository root. The scripts use the existing Playwright installation (override `PLAYWRIGHT_MODULE` if necessary).

- `staff.cjs`: local Expo preview on port 8083, isolated staging API on port 8002 and existing ignored `tmp/security-staging.json`. Tests use real staging Supabase. Never substitute production credentials. The optional `TEST_INITIAL_ENROLLMENT=1` mode requires separately approved setup of a synthetic manager without a verified factor; it is intentionally not repeatable after that factor is verified. The script does not change roles or remove factors. Enrollment material stays in ignored `tmp/targeted-mfa-enrollment.json`; QR screenshots are masked.
- `maps.cjs`: final Next production build served locally on port 3001 and isolated staging API on port 8002. Browser-local routing renders the corrected source under the real frontend origin, while Google API calls remain real. API reads use staging data. No deployment, hosted configuration change or production booking is performed. This requires a public Maps key authorized for the real frontend origin.

Results and privacy-safe screenshots go to `docs/trifecta-fixes/`. Provider secrets, tokens and passwords must never be included in evidence or committed.
