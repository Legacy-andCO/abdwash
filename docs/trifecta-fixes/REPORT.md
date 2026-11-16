# Trifecta targeted corrections — 16 November 2026

Changes are local and reviewable. No deployment or production settings/data changes were made.

## Root causes and changes

- **Grey map:** reproduced on `https://www.trifecta-wash.com/book`. The production Content Security Policy explicitly blocked Google's `blob:` workers. The container had a valid 322 × 218 pixel size at a 390 pixel viewport. Added narrowly scoped `worker-src 'self' blob:`. Replaced `no-referrer` with `strict-origin-when-cross-origin` so Google can validate website restrictions without receiving cross-origin paths or query strings. Empty map IDs now fall back correctly. Maps initialize independently of optional Places/geocoding; authorization failures and stalled rendering show the written-address fallback.
- **Autocomplete:** selecting an address changed search text and triggered another prediction request. Search visibility now follows editing intent; selection, outside pointer interaction, keyboard focus leaving the picker, Escape and clearing dismiss results. Late responses are ignored. Pointer focus is preserved during selection. Place details populate the written address and move/recenter the marker.
- **Manual addresses:** the previous client validation required a Maps link even when the optional map failed. A written address plus access instructions can now continue. Booking submission and review generate an encoded official Google text-search link when needed, without inventing coordinates. Supplied links still receive the existing HTTPS/domain validation; backend validation is unchanged.
- **MFA:** the verified-factor branch already existed, but incomplete factors were automatically deleted/replaced on mount and initialization was not shared across remounts. Initialization now shares an in-flight request per user, prefers existing verified TOTP factors, resumes incomplete factors, and replaces unfinished setup only on an explicit action after rechecking factors. Successful provider challenge/verification must produce AAL2 before the UI gate opens. No existing verified factors were removed. Backend AAL2/freshness enforcement and administrator-mediated recovery remain unchanged.
- **MFA usability:** applied Impeccable's existing-interface hardening guidance. Added a responsive, scrollable safe-area layout, readable title/instructions, 64px high outlined input, numeric/OTP mobile entry, Arabic digit normalization, focus/error states, clear enabled/disabled verification buttons and recovery/sign-out actions. QR screenshots are masked; secrets remain in ignored files.
- **Jobs:** the primary tabs used content-sized wrapping flex items. Today/Upcoming/Calendar now share the entire row equally with centered labels, 48px touch targets and explicit web selected-state semantics. Secondary job views retain their existing layout.

## Verification

- Web: **230 tests passed**; staff/mobile: **187 tests passed**; backend MFA/JWT enforcement: **18 tests passed**.
- Workspace TypeScript checks, web ESLint and the final Next production build passed.
- **Real staging Supabase + local staff UI:** initial manager enrollment exactly once; sign-out/sign-in using the same factor without a QR; existing manager/admin factors; invalid and expired code rejection; employee navigation without a privileged MFA gate. Follow-up SQL confirmed one verified factor per tested account and no incomplete duplicates. The specifically approved temporary synthetic account promotion was restored to employee immediately after testing.
- **Live Google APIs + final local production build:** actual raster/vector tile imagery inspected in screenshots; English Yas Island and Arabic Al Reem Island searches; address population and marker movement; suggestions dismiss after selection/Escape/outside click/clear; written-only addresses advance to scheduling with Google deliberately unavailable. No JavaScript, CSP or Google API errors. A cancelled transparent placeholder image is recorded separately from failed responses.
- Mobile screenshots inspected at 320/360/390 pixels for MFA/Jobs, 320/390 for maps, plus desktop/RTL views. Inputs and tabs fit with no horizontal clipping.
- **41 existing employee/manager/admin browser journeys passed**, including booking review/edit/confirmation, calendar/double-booking, manager rescheduling/version checks, customer tools, inventory, pricing, teams and finance. These use synthetic API fixtures and are separate from the real-provider authentication tests. Two admin full-page preview reloads initially timed out; both passed a focused retry using DOM readiness and a normal preview timeout. Raw results are retained in `regression/`.

## Deployment and configuration boundary

Vercel confirmed project `abdwash-vdtc`, production deployment `https://abdwash-vdtc-9whnnpp4v-legacy-andcos-projects.vercel.app`, commit `388fe55be2e0871e62d3e2430136cdd8a53e097b`. The real public frontend is `https://www.trifecta-wash.com`; the apex redirects there. `abdwash-vdtc.vercel.app` was not used as a staging frontend.

Vercel's environment metadata endpoint still returns **403 projectEnvVars**, even after team access was approved. The served public browser key was verified at runtime: Maps scripts, Places autocomplete/details and map tiles returned successful responses. Google Cloud billing, API restriction rules and dashboard environment values were not directly inspected or changed; no billing/API authorization errors occurred in the corrected runtime checks.

Corrected-build Maps tests use browser-local routing under the real website origin and isolated staging catalogue data. This does not publish code, alter DNS, modify the hosted site or create production bookings. Production will retain its existing behavior until a deployment is separately approved.

Evidence: `production-map-diagnosis.json`, `deployment-verification.json`, `maps-browser-results.json`, `mfa-browser-results.json`, the PNGs in this directory and `regression/`.

References: [Google Maps CSP guidance](https://developers.google.com/maps/documentation/javascript/content-security-policy), [Google key security guidance](https://developers.google.com/maps/api-security-best-practices), [Supabase MFA](https://supabase.com/docs/guides/auth/auth-mfa).
