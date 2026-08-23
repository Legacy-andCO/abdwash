# State machines

Routes must call centralized transition validation; clients never submit authoritative state.

## Booking

- `pending_payment` → `confirmed` or `cancelled`
- `confirmed` → `cancellation_requested` or `completed`
- `cancellation_requested` → `confirmed` (rejected request) or `cancelled` (approved)
- `cancelled` and `completed` are terminal

## Job

- `unassigned` → `assigned` or `cancelled`
- `assigned` → `unassigned`, `in_progress`, or `cancelled`
- `in_progress` → `completed` or `cancelled`
- `completed` and `cancelled` are terminal

`started_at` and `completed_at` are authoritative server timestamps. Repeating an already completed action with the same idempotency key returns its original result rather than reopening the job.

## Payment

- `unpaid` → `pending` or provider/backend-confirmed `paid`
- `pending` → `paid` or `failed`
- `failed` → `pending`
- `paid` → `refund_pending`
- `refund_pending` → `refunded` or back to `paid` if the refund fails
- `refunded` is terminal

Local/offline state can request a payment operation but cannot authoritatively create `paid`.

## Cancellation

Cancellation request state is `requested` → `approved` or `rejected`. Approval atomically transitions the booking to cancelled, cancels a non-terminal job, releases future reservations, and can queue confirmation/refund work. Rejection restores a confirmed booking lifecycle.

