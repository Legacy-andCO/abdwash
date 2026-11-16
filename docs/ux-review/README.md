# Trifecta staff UX review and implementation

16 November 2026 · Existing Expo/React Native manager, admin and employee app · Operate mode

The implementation simplifies the existing interface while retaining Trifecta's cream, brown and orange identity. No deployment was performed. This work does not change backend business rules, authentication, permissions or database schemas. Existing unrelated working-tree changes, including security work, were preserved.

[Open the before-and-after comparison](comparison.html).

## Review method and evidence

The parent reviewed actual local browser interfaces using fresh Chrome contexts with synthetic records and intercepted authentication/API responses. This exercised the production app components and event handlers; it did not authenticate to the live business or write real bookings. Before captures preceded UI edits. Matched captures cover manager Today, employee Today, Jobs, Calendar and booking on a 390×844 phone viewport, plus desktop Today at 1280×900. Final journeys also cover 320×740, 768×1024 and 844×390 viewports.

With the user's permission, two reviewers assessed the work separately:

- **Assessment A, design critique:** 28/40, Good. Evaluated hierarchy, first-time operation, cognitive load, language, error prevention and recovery. Its attendance-placement and customer-search recommendations were implemented afterward.
- **Assessment B, technical/browser audit:** 14/20, Good, before the last targeted contrast and narrow-calendar corrections. Accessibility 2/4; performance 3/4 provisional; responsive 3/4; theming 3/4; implementation integrity 3/4. The performance score is a source/interaction assessment, not a benchmark. Remaining source-only native concerns are unscored.

Assessment A finished before Assessment B's findings entered the synthesis. A inspected source, captured authenticated browser screens and a fresh live login tab. B independently used isolated browser fixtures, measured styles/targets and inspected source. These are expert reviews, not a study with newly recruited employees.

The Impeccable context launcher and detector could not run because engine 0.1.5 was absent and its external cache could not be created. No automated detector pass, clean finding count, injected overlay or canonical critique-storage snapshot is claimed. This report and the captured images provide the local review record. PRODUCT.md and DESIGN.md were absent; the existing implementation and brand tokens supplied the visual context.

## Main problems, in priority order

| Priority | Problem and first-time-user impact | Evidence | Result |
|---|---|---|---|
| P1 | Daily work appeared below secondary tools. Managers first saw Inventory, pricing, complaints, personal cash and a customer-management card. Employees saw inventory and cash before their active appointment. | Before Today screenshots | Daily actions and operational work now lead. |
| P1 | Booking had a hidden entry point: Jobs → Calendar → Book a Wash. Today appointment cards did not open jobs. | Before navigation and source | Book a wash is available directly on Today and Jobs. Today cards open the relevant job. |
| P1 | Small orange-on-light labels and white-on-orange primary buttons failed normal-text AA contrast. | Measured token contrast | Primary buttons use existing burnt orange; secondary buttons use dark text; small labels in the edited surfaces use darker orange. |
| P2 | Seven manager job views were horizontally clipped, making Calendar, History and All difficult to discover. | Before Jobs screenshot | Today, Upcoming and Calendar remain visible; other queues are grouped in More job views. All is labeled All jobs & customer search. |
| P2 | Phone calendar cells used 8px vehicle/team fragments, requiring close reading and truncating names. | Before Calendar screenshot | Phone cells show readable job counts; a selected date opens the full chronological agenda. Wider calendars retain event previews. |
| P2 | Optional make/model/plate, notes, coordinates and three policy links competed with required booking choices. | Before booking screenshot | Optional details and policy documents use labeled disclosure. Service, time, contact, address, policy delivery, review and confirmation remain explicit. |
| P2 | Clock in could be buried after a long schedule after simplification. | Independent design review | Employees who have not clocked in see attendance before job cards. Once clocked in, attendance is below the work list. |
| P2 | Long-form validation reports errors far from affected fields; dialog wrappers lack accessible names. | Independent technical review | Existing announced error and preserved form values verified; field associations/focus and named dialogs remain follow-ups. |
| P1 product gap | The staff interface is English-only apart from existing bilingual booking-policy/overlap content. Arabic customer data alone does not provide an Arabic staff interface. | README, source and browser | Existing Arabic strings and customer data preserved. Full staff localization/RTL remains outstanding. |

## Improvements implemented

**Daily operations.** Today now has one clear primary action, Book a wash, with View schedule beside it. Employees see their current/next appointment, customer, vehicle, service, address, status and an explicit View job details affordance. Remaining appointments are chronological. Clock in remains immediately discoverable for an unclocked employee. Managers see operational metrics, outstanding work and active jobs before management tools. Attention cards route to the matching unassigned/rescheduling queue or attendance/review area. A direct schedule action clears a previously opened job detail.

**Secondary functions.** Customers, complaints, inventory and services/pricing remain available in Customers & management tools. Employees retain inventory and personal cash access. Team attendance and cash summaries remain accessible without filling the first viewport. Reports and Finance retain their existing destinations, with a contextual hint in management tools.

**Bookings and calendar.** Existing normal and overlap bookings use the same booking sheet and request format. Optional vehicle details, notes/coordinates and policy links are collapsed without losing entered values. Required policy delivery and language choice remain available. An introductory sentence explains the short workflow and payment timing. Before service selection, available times explain the prerequisite. Review and receipt scroll into view; Close is near the form heading. Successful direct bookings invalidate the same scoped jobs/dashboard/calendar/availability queries as calendar bookings. Deliberate double-booking still requires its existing consequence-specific confirmation.

**Readability and interaction.** Status labels are sentence case and use familiar terms such as Scheduled, On the way, Washing and Payment due; server status values are unchanged. Shared controls retain disabled/busy behavior. Tab labels are larger, job-view targets are at least 48px tall, month controls have minimum dimensions, narrow calendars reduce surrounding padding, and disclosures expose expanded state. Web has visible keyboard focus, branded selection/caret colors and a shared system font context for portals. Native styles remain separate from web-only browser styles.

**Job progression.** The existing next operational action appears before quality details. Required checklist enforcement is unchanged. Inspection, photos, issue/complaint handling, assignment, rescheduling, delay notification, customer contact, payment, consumption, expenses and historical information remain present.

Contrast measurements: white on the original primary orange was **3.93:1**; white on the existing darker orange is **5.34:1**. Dark secondary-button text on its peach surface is **13.32:1**. These are measured examples, not certification that every legacy screen meets WCAG AA.

## Before and after screenshots

The [comparison gallery](comparison.html) places matching images side by side. Images contain only synthetic records.

| Screen | Before | After |
|---|---|---|
| Manager Today | [Before](before/manager-today-mobile.png) | [After](after/manager-today-mobile.png) |
| Employee Today | [Before](before/employee-today-mobile.png) | [After](after/employee-today-mobile.png) |
| Jobs | [Before](before/manager-jobs-mobile.png) | [After](after/manager-jobs-mobile.png) |
| Calendar | [Before](before/manager-calendar-mobile.png) | [After](after/manager-calendar-mobile.png) |
| Booking | [Before](before/manager-booking-mobile.png) | [After](after/manager-booking-mobile.png) |
| Manager desktop | [Before](before/manager-today-desktop.png) | [After](after/manager-today-desktop.png) |

Additional screenshots record booking review, success receipt, deliberate-overlap confirmation, rescheduling, job details, management screens, team, reports, Finance and Profile in `after/`.

## Workflow verification

**41/41 role journey checks passed**, across manager, employee and admin. [Raw results](after/journey-results.json).

| Journey | Result |
|---|---|
| Discover booking from Today | One direct tap, compared with the previous three-action Jobs → Calendar → Book route. |
| Create normal booking | Select service/type/time; enter customer/address; record policy delivery; review; edit without losing fields; confirm; see receipt. Passed for all three roles. |
| Intentionally double-book occupied time | Open date agenda; choose occupied job; complete booking; review; verify no submission before explicit confirmation; confirm with `overlap.confirmed=true`. Passed for all three roles. |
| Open job from Today | Correct job request and next action; return to Today; View schedule returns to the list rather than the old job. Passed for all roles. |
| Manager/admin reschedule | Select exact time and team/auto-assignment; provide reason; confirm; submit original expected version. Passed. |
| Find outstanding work | Attention entry opens the appropriate queue. Passed. |
| Management navigation | Customers, complaints, inventory, services, team/staff/shifts/attendance, Reports/Finance and Profile remain reachable. Passed. |
| Role visibility | Employee retains Today, Jobs and Profile, without manager tools. Passed. |
| Responsive and keyboard | Tested phone, narrow phone, tablet, desktop and landscape; Today document did not overflow; Enter activates disclosures and expanded state is exposed. Passed. |
| Runtime diagnostics | No uncaught page errors or unknown fixture endpoints in the completed role journeys. |

**5/5 lifecycle and recovery checks passed.** [Raw results](after/state-results.json).

- Employee Start trip → arrival confirmation → Start wash → completion confirmation → cash received → visible Payment complete acknowledgment. AED 100 tender against AED 70 due submitted AED 30 change.
- Unclocked employee sees Clock in before job cards.
- Empty jobs explain where assignments appear and how to create a booking.
- Invalid booking review raises an announced alert and retains entered customer details.
- Jobs load failure exposes Try again.

**Repository validation:** mobile TypeScript check passed; all **180 tests in 42 files passed**; production Expo web export passed. Existing MFA/capability/security tests remain in that suite. No backend tests were rerun because backend code was not changed. UI fixtures do not validate real JWT/MFA challenges, database permissions, concurrent capacity decisions, real cash accounting or notification delivery.

## Remaining issues and recommended work

1. **Staff Arabic/RTL localization:** add a staff locale system and complete translations, mirrored navigation/layout, bidi-safe customer/time rows and Arabic screen-reader checks. Customer website localization was outside these edits and remains intact. Current bilingual policy/overlap content was preserved and an Arabic customer name was exercised in booking.
2. **Inline form guidance:** mark required/invalid fields, associate errors and move focus to the first invalid field. Also protect a partially entered booking from accidental dismissal. Current form-level alerts and safe retry behavior remain.
3. **Named dialogs and full assistive-technology testing:** booking already traps focus and closes with Escape; associate its dialog with its heading. Complete real NVDA/TalkBack/VoiceOver journeys and a broader contrast review of legacy management screens.
4. **Native verification:** Pixel_6a is configured, but its Android 37 system-image directory is missing. Emulator launch failed before boot. No native screenshots, native gesture/IME/dark-mode/large-font evidence or Android regression pass is claimed. Restore the system image and verify the shared implementation on a device. Tablet navigation adaptation and a full dark appearance remain existing product limitations.
5. **Human first-time-user validation:** observe a new employee starting a shift and making a first booking, and a manager responding to a customer call. This pass verified discoverability and technical completion by an expert acting without a tutorial; it did not measure a real novice success rate or completion time.
6. **Further density improvements:** wide layouts remain vertically stretched. Inventory, Finance and service-configuration forms retain their domain complexity; this pass verified their access and preserved their workflows rather than rebuilding each specialized form.

Recommended sequence: `$impeccable harden` for field/dialog semantics, `$impeccable adapt` for full localization and native size classes, then `$impeccable polish` after real-device and novice-user validation. No production deployment has been performed.

## Reproduce the browser checks

Start `npm.cmd run web --workspace=@trifecta/mobile -- --port 8082 --offline`, then run `node scripts/ux-review/journeys.cjs` and `node scripts/ux-review/states.cjs`. `capture.cjs after` refreshes matching screenshots. The scripts use the installed Chrome browser and bundled Playwright path; `PLAYWRIGHT_MODULE` can point to another local Playwright installation. Browser contexts intercept external traffic, use synthetic authentication and API fixtures, and abort unrelated external requests. Test screenshots therefore verify client behavior only.

Review-only servers and browsers were stopped at handoff. The Impeccable engine installation and Android system image were not changed.

Questions skipped: the user already authorized implementation and explicitly approved the two reviewers; remaining gaps are documented above.
