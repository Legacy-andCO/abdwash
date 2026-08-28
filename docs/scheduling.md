# Scheduling

Scheduling is business-timezone-aware and server-authoritative. Default Trifecta settings are Asia/Dubai, 09:00–21:00, and 120-minute slots. Slot generation therefore exposes 09:00, 11:00, 13:00, 15:00, 17:00, and 19:00; 21:00 is never a start under those settings.

One or two vehicles consume one slot. Three or more consume two consecutive slots. The threshold and required count live in `business_settings`. Availability only advertises a start when the full sequence is available on at least one active resource.

## Atomic acquisition

For each requested resource/start pair, the transaction takes a sorted PostgreSQL transaction-scoped advisory lock. It then inserts the canonical `schedule_slots` row if missing, locks all required rows with `FOR UPDATE`, releases stale holds in-place, and checks the complete set. Only after every row is free does it create one hold group and mark every row held. Any exception rolls back the entire transaction, so a two-slot request cannot leave a partial first slot.

The unique constraint on `(resource_id, slot_start)` is the final database invariant. Different resources may occupy the same wall-clock time.

## Holds and confirmation

Hold tokens use cryptographically secure random bytes. Only SHA-256 hashes are stored. Holds initially expire after ten minutes. Availability treats an expired hold as free immediately; acquisition also marks stale groups expired while holding the slot rows, so correctness does not depend on a cleanup cron.

Pay-after-service booking atomically consumes the hold and changes all rows to reserved. Pay-now booking remains `pending_payment`; its slots remain bounded by the hold expiry until a future provider-confirmation workflow is added. Abandoned pending bookings therefore cannot permanently block the schedule.

Cancellation approval will transition the booking/job and set future reserved slot rows free in the same transaction. The policy function currently permits normal requests through exactly 24 hours before the scheduled start.
