# State machines

Routes must call centralized transition validation; clients never submit authoritative state.

## Booking

- `pending_payment` → `confirmed` or `cancelled`
- `confirmed` → `cancellation_requested` or `completed`
- `cancellation_requested` → `confirmed` (rejected request) or `cancelled` (approved)
- `cancelled` and `completed` are terminal

## Job

- `unassigned` → `assigned` or `cancelled`
- `assigned` → `unassigned`, `en_route`, or `cancelled`
- `en_route` → `arrived` or `cancelled`
- `arrived` → `in_progress` or `cancelled`
- `in_progress` → `completed` or `cancelled`
- `completed` and `cancelled` are terminal

`started_at` and `completed_at` are authoritative server timestamps. Repeating an already completed action with the same idempotency key returns its original result rather than reopening the job.

Required snapshotted service-checklist items guard only the existing `in_progress → completed` transition. They do not add a lifecycle state. Historical jobs without a snapshot remain valid.

## Complaint and correction

- `open` → `under_review`, `resolved`, `rejected`, or `rewash_approved`
- `under_review` → `resolved`, `rejected`, or `rewash_approved`
- `rewash_approved` → `resolved` when its linked correction job completes
- `resolved` and `rejected` are terminal

A correction is a separate zero-value booking/job that uses the normal schedule and job lifecycle. The original job remains completed.

## Payment

- `unpaid` → `pending` or provider/backend-confirmed `paid`
- `pending` → `paid` or `failed`
- `failed` → `pending`
- `paid` → `refund_pending`
- `refund_pending` → `refunded` or back to `paid` if the refund fails
- `refunded` is terminal

Local/offline state can request a payment operation but cannot authoritatively create `paid`.

For cash, `unpaid → paid` is valid only after a completed job, sufficient tender, exact server-verified change, and a unique client event. The transaction applies the outstanding amount—not the tendered amount—to revenue.

## Loyalty reward

- `available` → `reserved` when an authenticated confirmed booking atomically selects the reward for its snapshotted configured service.
- `reserved` → `available` when that booking's cancellation is approved.
- `reserved` → `redeemed` when the rewarded service completes.
- `redeemed` is terminal.

Qualifying wash events are append-only and source-key deduplicated per booking-service snapshot. Payment and job completion can both invoke the same evaluator; it credits only after both conditions are authoritative. Correction/rewash, guest, zero-value, unpaid, incomplete, and reward-discount lines do not qualify.

## Cancellation

Cancellation request state is `requested` → `approved` or `rejected`. Approval atomically transitions the booking to cancelled, cancels a non-terminal job, releases future reservations, and can queue confirmation/refund work. Rejection restores a confirmed booking lifecycle.
