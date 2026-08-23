# Architecture

AbdWash is a modular monolith. Next.js serves the customer experience, Expo hosts the independently distributed staff application, and one FastAPI backend owns business operations. Supabase provides PostgreSQL and Auth. This keeps transactions—especially booking and multi-slot acquisition—inside one database boundary and avoids premature network and operational complexity.

## Request flow

Clients authenticate with Supabase Auth when needed and send the access token to FastAPI. Guest-capable booking routes accept no token. FastAPI validates the JWT locally through a cached JWKS set, loads authoritative application/staff context in one joined query, and executes bounded workflow-oriented operations through services and repositories.

Clients do not write business tables through the Supabase Data API. RLS is enabled with no anonymous or authenticated business-data policies. FastAPI's PostgreSQL role remains the business-data access path.

## Modules

- `api` owns HTTP contracts and status codes.
- `auth` verifies Supabase identities and resolves staff authorization.
- `domain` owns scheduling calculations and state-transition rules.
- `services` owns transactional workflows.
- `repositories` contains intentionally bounded database reads.
- `integrations` defines payment and notification provider interfaces.
- `workers` processes durable outbox work independently of API latency.
- `models` and Alembic define the relational schema.

## External work

Authoritative state and its outbox message are committed together. Provider calls occur after commit and never while a booking transaction is open. The shared async HTTP client has bounded connections and timeouts and is reused for application lifetime.

## Future local-first mobile

The mobile app is not offline-capable yet. The server foundation supports a future local operational cache and sync outbox through idempotency keys, client event IDs, append-only job events, authoritative timestamps, version columns, and `409` conflicts. A future sync endpoint should return a bounded operational snapshot rather than require many fine-grained calls.

## Why not microservices

The critical workflows require shared transactions and a small team benefits from one deployable backend. Scale should first come from indexes, pooling, batching, PostgreSQL aggregation, query-count guards, outbox workers, and horizontal API/worker processes. Services can be extracted later only if measured operational boundaries justify it.

