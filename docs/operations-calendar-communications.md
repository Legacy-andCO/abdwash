# Operations Calendar and customer communications

## Calendar flow

The mobile Jobs → Calendar view requests one bounded 1–42 day projection. The API converts business-local day boundaries to UTC, applies tenant and staff/team scope in SQL, excludes cancelled jobs, and returns only calendar fields. The month cache key is:

```text
calendar / business:staff:role / start-date / end-date
```

Persisted data remains visible during refresh. Job status/assignment/reschedule changes invalidate only relevant month ranges, while the existing `jobs` and `schedule` sync revisions reconcile changes from bookings and other devices. The existing `(business_id, scheduled_start, status)` job index supports this projection; no additional speculative calendar index was added.

For production measurement, compare a cold and immediate repeated month request in Vercel logs. Record `total_ms`, `sql_query_count`, and response bytes. The expected contract is one SQL query for the calendar endpoint, at most 42 days per response, and no N+1 queries. Mobile fresh-cache navigation should render without waiting for a request; stale-cache navigation keeps data visible during one background refresh.

## Communication event matrix

| Event | Trigger | Dedupe basis | Customer email |
| --- | --- | --- | --- |
| Booking confirmation | Confirmed booking transaction | Booking ID | Confirmation and secure manage link |
| Appointment reminder | Bounded dispatcher reaches configured lead time | Booking ID + current scheduled timestamp | Current date/time and manage link |
| Team en route | Start Trip transaction | Job ID | ETA when available |
| Team arrived | Arrived transaction | Job ID | Arrival update |
| Delay update | Explicit manager action | Job ID + client event ID | Selected delay; schedule unchanged |
| Rescheduled | Successful manager reschedule | Reschedule event ID | New appointment time |
| Service completed | Complete transaction | Job ID | Completion summary |
| Payment pending | Completed job remains unpaid and has no customer payment-link flow | Job ID | Pending notice; no dead Pay button |
| Cancellation requested | Customer request | Cancellation request ID | Request acknowledgement |
| Cancellation approved | Manager approval transaction | Booking ID | Cancellation confirmation |

All messages use `notification_outbox`. Provider calls remain outside database transactions, retry with the existing exponential policy, and are claimed with `FOR UPDATE SKIP LOCKED`. Reschedule/cancel/complete deletes any unsent reminder, while dispatch rechecks status and scheduled time before sending. The management token is derived only at dispatch and is never stored in the outbox or shown in communication history.

Communication history is manager-only and exposes only a safe label, Queued/Sent/Failed state, timestamps, and delay minutes. It does not expose recipient addresses, payloads, provider errors, or tokens. `Sent` means provider acceptance; inbox delivery/open telemetry is not implemented.

Emails currently use the established English transactional template system. Customer language preference is not stored authoritatively, so Arabic email templates are intentionally deferred rather than inferred incorrectly. SMS and WhatsApp are not implemented.
