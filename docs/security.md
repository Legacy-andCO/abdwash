# Security posture

- Supabase Auth is the identity provider; FastAPI stores no passwords.
- Asymmetric access tokens are verified against cached project JWKS with issuer, audience, expiry, algorithm, and subject validation. Legacy HS256 fallback requires an explicit backend-only secret and should be avoided where project signing keys are available.
- Staff role and active state come from `staff_profiles`, not user-editable JWT metadata or client input.
- Public request schemas forbid unknown fields and exclude prices, status, paid state, role, and other server-owned fields.
- Every exposed business table has RLS enabled and no anonymous/authenticated business-data policy. Clients perform business operations through FastAPI.
- CORS origins are explicit. Credentialed production CORS never uses `*`.
- Hold tokens are random and booking-management links are signed with a backend-only HMAC key; only hashes are stored. Idempotency records contain safe responses and deterministically re-derive management links rather than persisting raw tokens.
- The management secret stays in a browser URL fragment, which is not sent in HTTP requests, and reaches FastAPI only through a dedicated header. It is never part of a server route or idempotency record. The booking reference alone cannot open or cancel a booking.
- Card PAN, CVV, magnetic-stripe data, and raw payment credentials are not represented in the schema. Saved methods contain provider references and safe display metadata only.
- Cash tender/change is accepted only through the authenticated staff API, revalidated against the locked authoritative amount due, and deduplicated per payment/client event. Tendered cash is never treated as revenue beyond the applied balance.
- Loyalty rewards are tenant/customer-owned rows locked during booking reservation. Customer identities cannot select another customer's reward, employees cannot access manager customer search/adjustment routes, and manual loyalty changes require an attributed manager/admin actor plus reason.
- A future Pay Now flow must collect cards in the payment provider's hosted/tokenized UI. Trifecta may store only the provider customer/payment-method IDs plus brand, last four digits, expiry, and default status; PAN, CVV/CVC, track data, and PIN must never enter the API, database, logs, browser storage, booking payloads, or payment metadata.
- Logs mask notification recipients and never include authorization headers, connection URLs, secrets, raw management/hold tokens, or provider credentials.
- Job photos are private operational data. FastAPI derives `business/{business_id}/jobs/{job_id}/...` paths from the authenticated tenant/job, stores only stable paths, verifies uploaded size/MIME metadata, and issues short-lived signed reads. Signed photo URLs and upload tokens must never be logged.
- Booking-confirmation outbox rows contain only the booking reference and foreign key. The dispatcher re-derives the signed management token in memory and places it in the email URL fragment; it is never persisted in the outbox or structured logs.
- The bounded notification endpoint requires a backend-only dispatch secret and compares it in constant time. Google Maps browser credentials are intentionally public but must be restricted to approved HTTPS referrers and only the Maps JavaScript, Places API (New), and Geocoding APIs.
- Public booking/hold endpoints are isolated behind versioned routers and can receive a gateway or middleware rate limiter later without changing domain services. Deployment should add per-IP and per-idempotency-key limits at the trusted ingress.

Rotate any credential that has appeared in chat, logs, source, or another non-secret channel before production use.
