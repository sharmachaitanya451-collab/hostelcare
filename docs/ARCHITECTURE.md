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


---

# v0.3 addendum - Backend and database architecture (Phase 3A, Revision 2, proposed)

This addendum supersedes the earlier text where they differ (marked below). Full schema: [database-design.md](database-design.md); diagram: [database-erd.md](database-erd.md); decisions: [ADR.md](ADR.md) (ADR-007 to ADR-026).

**Superseded or amended from v0.2:**
- *Scope* ("complaints and maintenance only") is extended to fines, disputes, payments (Razorpay-ready, not integrated) and in-app notifications (ADR-008).
- *Modules* list (`auth`, `users`, `rooms`, `complaints`, `audit`) grows to: `auth`, `users`, `rooms`, `complaints`, `fines`, `payments`, `notifications`, `audit`.
- *Password reset* is self-service email reset with 30-minute expiring hashed tokens, neutral responses, and rate limiting; admin triggers the email but never sees or issues temporary passwords, superseding ADR-005 and ADR-009 (ADR-017). Email delivery is provider-independent via environment configuration (ADR-023).
- *Role model* uses a single `admin` role initially (no admin tiers, ADR-021). Rejected students can be reactivated by an admin (`rejected -> pending`) preserving unique roll numbers and emails without creating duplicate accounts.
- *Complaint lifecycle* supports reopening closed tickets by wardens (`closed -> under_review`) with mandatory reasons and complete history, and pre-acceptance rejection during review (ADR-020). Common-area complaints are supported for approved students without an active room allocation (ADR-019). Private admin notes are strictly isolated in `complaint_internal_notes` (ADR-025).
- *Photo attachments* are not part of this schema (frontend has none).
- `HOSTEL_BLOCKS`/`HOSTEL_ROOM_PATTERN` configuration become seed/validation hints; `blocks` and `rooms` tables are authoritative.

**Data layer**
- PostgreSQL 18, 20 tables, `bigint` identity keys, `public_id uuid` / `reference_no` for API-facing identifiers, `timestamptz` for instants, `numeric(12,2)` INR, varchar + CHECK enums, one extension (`btree_gist`).
- Room allocations use half-open date intervals `[start_date, end_date)` with `btree_gist` exclusion constraints, bed-level capacity enforcement via constraint trigger T1, and row locking (ADR-026).
- Payments cleanly separate `payment_attempts` from immutable `payments` (verified only); browser callbacks are untrusted; idempotent webhook processing is anchored by unique `gateway_event_id`; full payment only in initial release; refunds are explicit future financial operations rather than automatic classifications of late payments (ADR-018, ADR-024).
- Two roles: `hostelcare_owner` runs Alembic and owns schema; `hostelcare_app` has explicit per-table DML grants only (column-level UPDATE on mutable tables, SELECT+INSERT only on append-only history tables, sequence USAGE, **zero `DELETE` privileges on any table**, expired reset tokens purged only via owner-owned `SECURITY DEFINER` function `public.purge_expired_password_reset_tokens()`, zero access to `alembic_version`) (ADR-022).
- Integrity lives in the database: unique/exclusion constraints for duplicate registration, overlapping allocations, bed double-booking, single active complaint assignment, single verified payment per fine, composite FK preventing cross-fine reuse of payment attempts, duplicate webhooks; CHECKs for state/field consistency (including explicit room allocation termination completeness); constraint triggers (T1a/T1b bed within capacity, T2a/T2b bidirectional paid-fine <-> verified-payment invariant, T3 full payment amount and currency match).

**Service layer rules (every module)**
- Routes stay HTTP-only; services own permissions, state machines and transactions. One request = one transaction, writing the entity, its history row, notifications and (for admin actions) the audit row together.
- Authorization is deny-by-default and principal-scoped in queries. Only `users.status = 'active'` can use protected endpoints; `session_version` revokes sessions. Frontend guards are UX only.
- Row locks on the aggregate root (`complaint`, `fine`, `room`, `user`) with a fixed lock order; no network calls while holding locks.
- Passwords: Argon2id only (`argon2-cffi`); accounts awaiting initial password setup use the explicit unusable-password marker `password_hash = '!'`, which authentication unconditionally rejects before Argon2id verification. Reset and payment secrets are never stored in plaintext.

**Payments boundary (design only):** the server creates the gateway order after committing a local `payment_attempts` row, verifies capture by webhook HMAC on the raw body or server-side fetch, and only then records a `payments` row and marks the fine paid. Browser callbacks are advisory.

**Testing to add with implementation:** constraint tests per table (including exclusion/trigger behaviour), authorization matrix tests (student cannot see internal notes, staff only own tasks, pending/rejected users blocked), concurrency tests (parallel allocations, assignments, webhook replays), grant tests (runtime role cannot DELETE, alter immutable columns, or touch `alembic_version`).
