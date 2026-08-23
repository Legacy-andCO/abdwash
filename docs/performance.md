# Performance and observability

One async SQLAlchemy engine is created for the FastAPI lifespan. Its bounded asyncpg pool defaults to five persistent connections plus five overflow connections and is configurable per host. Sessions are short-lived and always returned to that shared pool.

Request logs are structured JSON and include correlation ID, method, route, status, total duration, SQL statement count, and cumulative SQL duration. Development/test responses expose query-count/timing headers to aid regression tests; production responses do not. Provider adapters should log bounded duration and result category without payload secrets.

Implemented workflow reads use joined or batched `IN` queries. Booking services are loaded in one batch, saved vehicles are validated in one batch, and staff/business/settings context is joined. No relationship has implicit lazy loading enabled. Future lists must use bounded pagination and joined/batch loading, while reports should aggregate in PostgreSQL.

The integration suite sets coarse query ceilings for catalogue, availability, hold, and booking calls. These ceilings are intentionally broad enough for safe ORM changes while catching a change from a few statements to N+1 behavior.

The backend should be hosted geographically close to the Supabase region. Runtime connection choice depends on the host: direct or session pooling suits long-lived containers; transaction pooling suits serverless workloads. Set `DB_DISABLE_PREPARED_STATEMENTS=true` for transaction-mode poolers so SQLAlchemy and asyncpg do not use unsupported prepared-statement caches.
