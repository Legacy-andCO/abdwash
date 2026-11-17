# Production investigation — 17 November 2026

**A remaining root cause was found in production data and the deployed scheduler. The hosted staging proof is not complete: deploying it is awaiting the user's required approval. No production data or deployments were changed.**

## What is actually deployed

All three live projects resolve to source commit `e8908b869a70e81da44131bffba983d6c4b3c355`:

| Surface | Alias | Deployment ID |
|---|---|---|
| Staff | https://staff.trifecta-wash.com | dpl_4vKDYCVAzAa484QhCq1RU4WqkV9V |
| API | https://abdwash.vercel.app | dpl_4MUu4PP2qmFydsmjKBy1ULD33Sat |
| Customer | https://trifecta-wash.com | dpl_4vhX9U5iWfyXGXUnm5PRx2Eye8V4 |

Vercel's alias/deployment records identify these as production and READY. The live staff JavaScript bundle `/ _expo/static/js/web/index-610a125065634b5ec46e1d169038e6b1.js` (remove the space after `/`) has SHA256 `21fe7f82847b4c5139a63ddef80b95c324ad90c238dc68c3e3039873fb98ef73`. It embeds `https://abdwash.vercel.app` and production Auth `https://cbejmfjycvzdpqbfiskc.supabase.co`, and contains the dedicated `/double-book` path and the latest empty-state text. The live API OpenAPI response identifies `NormalStaffBookingCreate`, with `overlap` restricted to null, and exposes the separate appointment-specific exception endpoint. Production Alembic is `c7e833583da3`.

The earlier endpoint separation fix IS deployed. A missing deployment is not the observed explanation for the remaining shared-person bug. The precise URL/device used by the reporter has been requested; an installed native binary's build cannot be inferred from the hosted web deployment.

## Actual production finding

Read-only database queries show:

- Active team `Mobile Team 1` (`98f6be30-acf2-44e6-942f-a3eb086f2821`) has one active employee.
- Active team `Teams1` (`6783c947-c632-444c-ac80-95cae1bb7d0f`) has the **same sole active employee**, staff ID `53f380f9-2ee5-4f0e-b197-d3c48d299d45`.
- Confirmed booking `AW-A1C46766EA` occupies Mobile Team 1 on **18 November 2026, 09:00–11:00 Asia/Dubai**. Created at `2026-11-17T07:15:06.270462Z`.
- Confirmed booking `AW-B32827E77D` occupies Teams1 at exactly the same time. Created at `2026-11-17T07:45:15.706969Z`, after the latest API deployment became ready. Both jobs remain assigned.
- Both have normal `staff_calendar_booking_created` and policy audit records; neither has a `staff_calendar_capacity_exception` audit event. These are not recorded as explicit overrides.

Thus two distinct team IDs were treated as two independent teams despite representing the same person. This is a backend capacity-model error exposed by real configuration. The original test fixtures used independent members per team and could not detect it.

A separate historical same-team overlap, `AW-3423C15833` / `AW-629C99FC6C`, has an explicit capacity-exception audit on the latter dated 16 November. It is distinct from the normal shared-person bookings above.

## Flow and correction

Normal shortcuts in OperationsShell (including Today/Jobs) render `CalendarBookingSheet` with `overlap=null`. Calendar date/day appointment actions are the sole non-null UI source. Normal requests go to `POST /api/v1/staff/calendar-bookings`; explicit confirmation goes to `POST /api/v1/staff/calendar-bookings/{job_id}/double-book`.

Availability calls `availability_for_date` → eligible teams → `load_capacity_items` → `evaluate_team`. Normal submission calls `book_from_calendar` → `create_hold` → business/day advisory transaction lock → interval evaluation/grid hold → `create_booking` → confirmed Booking + assigned Job. Before this correction, capacity loading filtered by the candidate team IDs and `evaluate_team` compared only work with the same resource ID. Work assigned to the other team was invisible as a staffing conflict. The day lock serialized requests correctly, but serialized the wrong capacity calculation.

The patch in `backend/app/services/smart_scheduling.py` resolves active team memberships within the authenticated business and projects each job/hold/blocked interval onto every candidate team sharing an active person. It includes existing work on currently ineligible teams. This feeds normal staff availability/creation, public/customer holds and confirmation, assignments and rescheduling through the common capacity evaluator. Independent teams continue to offer independent capacity. The existing explicit calendar exception keeps its permission, existing appointment, confirmation, version and hard-block checks.

No production membership was removed, team deactivated, booking cancelled or migration applied. Existing double-booked production records require a separately authorized operational decision.

## Evidence limits and release status

`deployment-and-data-evidence.json` records deployment identities, live API contract and the production configuration/booking references without customer details. `public-artifact.json` records the fetched bundle, origins, hashes and response headers.

The exact deployed source was run with synthetic duplicated team memberships in an isolated database. For employee, manager and admin the regression captured **(occupied time displayed=True, second normal response=201)**. `before-shared-capacity.txt` contains that reproduction. The patched isolated tests check hidden occupied time, normal 409, explicit calendar 201, independently confirmed originals/extras, public hold rejection and concurrent one-success/one-conflict behavior.

These are supporting source-level tests, **not a hosted staging reproduction**. The production read-only findings prove the shared-person configuration and bookings; historical request payloads were not captured and are not invented. No production authenticated browser booking was attempted because the user forbids production writes. No production credentials were requested.

The full patched backend run passed 489 tests and hit one branding check caused by previously committed test transcripts containing immutable filesystem names. The branding test now explicitly excludes those evidence-only directories, as it already does for security audit evidence; the follow-up targeted results are in `after-shared-capacity.txt`.

Hosted staging release details and exact scope are in `STAGING-PLAN.md`; source artifact hashes are in `release-manifest.json`. Separate staging projects will use only the existing synthetic Supabase project. Real hosted employee/manager/admin browser traces, deployment IDs, request paths/payloads/responses and resulting records must still be collected after approval. **Do not consider the issue verified fixed in the hosted application until that gate passes.**
