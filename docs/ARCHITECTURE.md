# HostelCare Architecture (v0.2 – focused, approved)

**Scope:** one hostel; students, maintenance staff, admins; complaints and maintenance only.

## Style
Modular monolith: one Flask app, one PostgreSQL 18 database, a React SPA. In production the SPA and API are served same-origin behind a reverse proxy (no CORS, simple cookies/CSRF). No Docker, Redis, Celery or microservices.

## Backend (`backend/app/`)
- Application factory (`create_app`), env-based config (`config.py`), extensions (`extensions.py`, with a constraint naming convention for Alembic).
- Modules (added per phase): `auth`, `users`, `rooms`, `complaints`, `audit`; `core` holds health, errors, logging.
- Layering: routes (HTTP only) → services (rules, permissions, transactions) → models. Modules call each other's services, never tables.
- Errors use `{"error": {"code", "message"}}`. Logs are JSON with `X-Request-ID`. Health: `/healthz` (liveness), `/readyz` (DB readiness). Public deployment info: `/api/v1/meta`.
- Configurable placeholders: `HOSTEL_NAME`, `HOSTEL_BLOCKS`, `HOSTEL_ROOM_PATTERN`.

## Frontend (`frontend/src/`)
React + Vite + JavaScript, Tailwind CSS, mobile-first. Feature folders under `src/features` as features arrive. TanStack Query, React Router and React Hook Form + Zod are added when first needed (not in Phase 0). Route guards are UX only; the server enforces permissions.

## Data
SQLAlchemy 2 + Flask-Migrate. Bigint PK, UUID public IDs, `timestamptz`, varchar + CHECK instead of native enums, reviewed migrations. App database `hostelcare`, test database `hostelcare_test`, least-privilege app role (not `postgres`).

## Security (planned, per approved decisions)
Server-side cookie sessions (Flask-Login), Argon2id, CSRF, rate limiting on login/registration, deny-by-default authorization with scoped queries, first admin via CLI.
- **Admin password reset:** an admin triggers a reset; the system generates a temporary one-time credential shown once; the user must change it at next login. Passwords are never viewable by anyone. Self-service reset and email are deferred.
- **Complaint history:** an append-only history records creation, assignment, status changes, resolution and reopening, each with acting user and timestamp.

## Testing
pytest (real PostgreSQL for DB tests, marked `db`), authorization matrix tests, Vitest + RTL, later Playwright. CI: GitHub Actions (ruff, pytest with Postgres 18, ESLint, Prettier, Vitest, build).

## Product decisions
Defaults D1–D20 from the proposal are approved, with the two refinements above. Hosting is undecided.
