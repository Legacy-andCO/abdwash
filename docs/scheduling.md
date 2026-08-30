# Scheduling

Scheduling is business-timezone-aware and server-authoritative. Each weekday now has an explicit open/closed window; installations upgraded from the legacy model receive seven open days copied from the former business opening/closing values. Default Trifecta settings are Asia/Dubai, 09:00–21:00, and 120-minute slots. Slot generation therefore exposes 09:00, 11:00, 13:00, 15:00, 17:00, and 19:00; 21:00 is never a start under those settings. A closed weekday returns no availability and cannot acquire a hold.

One or two vehicles consume at least one slot. Three or more consume at least two consecutive slots. The threshold and required count live in `business_settings`. These rules remain the minimum grid reservation; operational team capacity also uses the booking's trusted expected duration.

Managers/admins may configure only the controlled public slot intervals 60, 90, or 120 minutes. Customers continue to book on that grid. Manager Job Detail rescheduling is intentionally more flexible: it offers hourly shortcuts from configured business hours plus a native exact-time picker, and the API evaluates the chosen minute-level interval without snapping it to the public grid. A slot interval controls public start times; it is not assumed to be the job duration. For a new booking the backend sums the current mobile-service duration for every vehicle plus every selected add-on duration. For confirmed/rescheduled work it uses the immutable expected-duration snapshot. One V1 team services all vehicles sequentially. A future catalogue edit therefore affects future selections only, not historical capacity.

## Smart team capacity and ranking

A usable V1 team is a same-business, active `mobile_team` resource with at least one active staff member. A team is excluded when all active members are on approved leave for the requested date. Existing future shift data is not complete enough to treat a missing shift as authoritative unavailability, and current attendance never controls future customer availability.

`assigned`, `en_route`, `arrived`, and `in_progress` jobs block team time. Active, unexpired holds also block it. Completed, cancelled, and unassigned jobs do not. Hard interval overlap is never allowed. Automatic assignment additionally requires the configured `default_team_turnaround_minutes` before and after the proposed job, including the next-job boundary. The final job may end exactly at closing; no artificial post-closing turnaround is required when there is no later job.

Feasible teams are ranked deterministically by: zero same-day jobs, lower job count, fewer assigned operational minutes, greater surrounding idle margin, configured team sort order, creation time, then UUID. No random or continuous rebalancing occurs. `assignment_source` records `auto`, `manual`, or migration-only `legacy`; manual assignments remain sticky across rescheduling when still feasible. Managers may explicitly override a turnaround-only warning, but never a real overlap.

An exact manager reschedule locks only the requested booking and business day. Automatic assignments are reranked for the new interval; manual teams remain selected when feasible. Other bookings are capacity inputs and are never moved or rebalanced. Successful manager reschedules commit one deduplicated `booking_rescheduled` outbox row with the schedule mutation; failed attempts commit neither schedule nor email.

## Operations Calendar

`GET /api/v1/staff/jobs/calendar?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` is the narrow calendar read model. It accepts at most 42 inclusive business-calendar days, uses half-open UTC boundaries derived from the business timezone, excludes cancelled jobs, and preserves employee assignment/team-membership scope. The response contains only job ID, scheduled interval, local date, status, team label, first vehicle label, and first service label. It is one SQL projection backed by `ix_jobs_business_schedule_status`; opening a day or job reuses the existing Job Detail endpoint.

Mobile calendar query keys include operational identity plus the exact start/end range. Cached month data persists and remains visible while it refreshes. Authoritative job mutations invalidate only calendar ranges containing the job or its new business date; sync revisions also reconcile new bookings and changes made by another device.

## Atomic acquisition

Before the final capacity decision or any schedule-slot row lock, capacity-changing operations take a PostgreSQL transaction advisory lock for the business/date (confirmation/reschedule may first lock the specific hold/booking being mutated). Candidate teams and the day's jobs/active holds are then loaded in bounded queries. The selected team's canonical slot rows are acquired in sorted order with the existing per-resource/start advisory locks and `FOR UPDATE`. This startup-scale lock order serializes the final-capacity decision without Redis and prevents two concurrent holds from consuming the same last team.

The unique constraint on `(resource_id, slot_start)` is the final database invariant. Different resources may occupy the same wall-clock time.

## Holds and confirmation

Hold tokens use cryptographically secure random bytes. Only SHA-256 hashes are stored. Holds initially expire after ten minutes. Availability treats an expired hold as free immediately; acquisition also marks stale groups expired while holding the slot rows, so correctness does not depend on a cleanup cron.

Each hold privately reserves one selected team and stores the trusted expected duration. Public availability/hold/booking responses do not expose internal team IDs or names. Pay-after-service booking recalculates duration from authoritative catalogue rows, revalidates the held team while holding the business/day capacity lock, atomically consumes the hold, reserves the grid rows, and creates an auto-assigned job. If capacity changed, the whole booking fails safely and no partial booking remains. Pay-now booking remains `pending_payment`; its slots remain bounded by the hold expiry until a future provider-confirmation workflow is added.

Cancellation approval will transition the booking/job and set future reserved slot rows free in the same transaction. The policy function currently permits normal requests through exactly 24 hours before the scheduled start.
