# AbdWash

AbdWash is a mobile car-care platform. This monorepo contains the production-ready customer booking website, a placeholder staff mobile app, shared TypeScript concepts, and the authoritative FastAPI/PostgreSQL backend.

The customer guest booking and cancellation-request journeys are implemented. The staff interface, online payment gateway, and production notification provider remain future work.

## Repository structure

- `apps/web` — Next.js App Router customer application; valid standalone Vercel root.
- `apps/mobile` — Expo/React Native staff application scaffold.
- `packages/shared` — small, stable TypeScript concepts. Future API types should be generated from FastAPI OpenAPI rather than duplicated manually.
- `backend` — FastAPI application, SQLAlchemy models, Alembic migration, worker, seed command, and tests.
- `docs` — architecture and operational decisions.

## Requirements

- Node.js 22 or newer and npm 11 or newer.
- Python 3.13.
- PostgreSQL 15+ for migrations and integration tests.
- The existing AbdWash Supabase project for the shared environment. Do not create another project.

## JavaScript applications

```bash
npm install
npm run lint
npm run typecheck
npm run build
npm run web
npm run mobile
```

Copy each app's `.env.example` to `.env.local` or the environment mechanism appropriate to the host. The web application needs only `NEXT_PUBLIC_API_URL`. Never expose a database, signing, JWT, or service-role secret.

## Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
copy .env.example .env  # use cp on macOS/Linux
uvicorn app.main:app --reload
```

Liveness is `GET /health`; database readiness is `GET /ready`. Versioned routes are under `/api/v1`.

## Database migrations and seed

Set `DATABASE_URL` to an isolated local PostgreSQL database while developing. For the shared Supabase database, confirm the project reference and environment before applying anything.

```bash
cd backend
alembic heads
alembic upgrade head
python -m app.cli.seed
```

Migrations and seed data never run during API startup. `python -m app.cli.seed` is idempotent and explicitly creates AbdWash, its settings, `Mobile Team 1`, and three customer-facing services. It deactivates the old bootstrap-only development service if present.

Run the notification worker separately:

```bash
cd backend
python -m app.workers.notifications
```

## Tests and checks

```bash
cd backend
pytest
ruff check .
mypy app
alembic heads
alembic upgrade head --sql
```

Frontend checks run from the repository root:

```bash
npm test --workspace=@abdwash/web
npm run lint --workspace=@abdwash/web
npm run typecheck --workspace=@abdwash/web
npm run build --workspace=@abdwash/web
```

Real scheduling concurrency tests require `TEST_DATABASE_URL` pointing to a **local**, isolated PostgreSQL database whose name contains `test`. The suite deliberately refuses to run destructive tests against Supabase or any remote host.

## Environment variables

Backend configuration is documented in `backend/.env.example`. Important values include `DATABASE_URL`, `SUPABASE_URL`, JWT/JWKS configuration, `BOOKING_MANAGEMENT_SIGNING_KEY`, explicit `CORS_ORIGINS`, bounded database pool settings, log level, and worker settings. `SUPABASE_SERVICE_ROLE_KEY` is optional backend-only configuration and is not required for normal SQL operations.

See [architecture](docs/architecture.md), [data model](docs/data-model.md), [scheduling](docs/scheduling.md), [state machines](docs/state-machines.md), [performance](docs/performance.md), [security](docs/security.md), and [deployment](docs/deployment.md).
