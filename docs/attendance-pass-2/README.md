# Trifecta Pass 2 · Authentication and attendance

All database work for this pass targets the existing `trifecta-staging` Supabase project `mgfzfgvlrxwyyftwukwf`. The staging API runs the workspace backend and verifies issuer, signature, session revocation, staff status and manager authenticator status against staging.

## Why managers were repeatedly prompted

The backend applied the five-minute TOTP freshness rule to every privileged write, including clocking in and routine job updates. Separately, the app set staff context to null as soon as a renewed access token arrived. That unmounted the staff screens while the context request ran and could reset the current tab. An MFA response from an older request could also arrive after a newer token and open the authenticator screen.

- A manager or admin still needs verified AAL2 and an active verified factor. An explicit list of operational routes accepts an otherwise valid AAL2 session after five minutes. Financial review, account administration, attendance corrections and other privileged changes keep the recent-TOTP check.
- The app uses the Supabase client's persisted session and refresh coordination. Foreground refresh starts on native resume, and refreshed tokens revalidate staff context without unmounting a working screen. Native storage remains Expo SecureStore. The browser uses the existing origin-scoped Supabase session storage.
- The client treats an actionable MFA response from the current token as a challenge. Ordinary permission errors stay with the originating action. A stale unauthorized read can retry once with a rotated token. A rejected current session revalidates staff access. Sign-out revokes the current session and reports a failure if revocation could not be confirmed.

## Attendance records

Employees open **Profile → Attendance history**. Managers and admins open **Team → Attendance → Attendance history** for employee and date filtering. Entries show Abu Dhabi clock-in and clock-out times, status, break and net hours, with expandable correction details. All sessions are assigned to their Abu Dhabi clock-in date, including shifts that end the next day. Missing clock-outs are flagged and excluded from credited daily and period hours. History shows actual attendance rows.

Revision `4c2630a391be` adds optional break minutes and two staff-scoped request identifiers to the existing attendance table. Clock operations preserve server timestamps and serialize on the employee row. Corrections use the same staff lock, reject overlaps, and save both original and corrected values plus the reason and reviewer in existing audit events. The history response returns net daily and period totals across the selected range, independent of page.

## Staging evidence

- The staging revision and all three new database constraints were verified.
- A synthetic employee's simultaneous clock-ins returned one session. Replaying clock-in and clock-out added zero duplicate audit events.
- An admin corrected an overnight 22:00–06:00 record, with a 45-minute break. PostgreSQL and the employee and admin history endpoints agreed on 435 worked minutes. The audit retained the original times. Employee access to another person's records and the correction action was denied.
- The same staging flow reused a verified admin factor, rejected an expired authenticator code, required MFA for the admin and rejected their access token after session sign-out. A separate rolled-back staging test rejected a disabled synthetic profile and an older access token. The Pass 1 payment-history endpoint remained available to the authenticated admin. [Attendance verification](staging-attendance.json)
- Chrome loaded the actual Expo web export against the staging-backed API. The session survived a page reload, offline navigation and reconnect, and a freeze/resume. A real token refresh kept the selected report visible. The manager attendance page exported the selected range to CSV. The employee page showed the same corrected shift in English and Arabic. [Browser verification](browser-verification.json)
- Eight parallel Supabase SDK refresh calls converged on one rotated token through one request to staging Auth. The resulting JWT retained AAL2 and the verified TOTP authentication method. [Concurrent refresh verification](staging-concurrent-refresh.json)
- The Pass 1 staging fixture still has AED 50.00 verified, AED 20.00 handed over and three payment submissions. The financial review step-up stays in effect.
- The automated runs passed 434 backend tests, 194 mobile tests and 230 web tests. The backend run had one skip and excluded the destructive PostgreSQL suites designed for disposable local databases. The hosted staging workflow and migration checks above used the authorized staging database. Ruff, mypy, workspace TypeScript and Expo web export also passed.

[Manager view at 320 px](manager-attendance-en-320.png) · [Employee overnight detail at 430 px](employee-overnight-detail-en-430.png) · [Arabic attendance at 430 px](profile-attendance-ar-430.png)

## Pass 4 acceptance checks

Extended runs were stopped on request on 20 November 2026. Pass 2 acceptance uses the functional, security and regression evidence above. The continuous 60-minute session test moves to Pass 4. Run it on the final application build with the existing staging project. Include routine work, navigation, offline recovery, a restart, background and foreground transitions, and access-token renewal. Record unexpected MFA prompts or session loss and confirm that sensitive actions still require recent MFA.

Native background and restart behavior should be verified on physical iOS and Android devices in Pass 4. The current screenshots and lifecycle evidence come from Chrome. CSV export is available in the staff web app.

