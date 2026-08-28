# Performance and observability

The canonical implementation, measurement evidence, cache policy, connection guidance,
query ceilings, and deployment checklist are in
[`PERFORMANCE_ARCHITECTURE.md`](PERFORMANCE_ARCHITECTURE.md).

The short version: the API owns one lifespan-managed async engine and one shared HTTP
client; request logs expose safe stage metrics and correlation IDs; operational reads are
bounded and tenant scoped; mobile reads use role-scoped stale-while-revalidate caches;
and provider calls never hold a database transaction open.
