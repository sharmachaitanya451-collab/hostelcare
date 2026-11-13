# ADR-001: Modular monolith, single hostel

- **Status:** Accepted
- **Decision:** One Flask deployable, one PostgreSQL database, one React SPA. No tenancy layer.
- **Why:** Small team and scope; ACID across modules; low operational cost.
- **Consequences:** Multi-hostel support would need a retrofit (accepted). Module boundaries are enforced by convention (service-only cross-module calls).

# ADR-002: Server-side cookie sessions

- **Status:** Accepted
- **Decision:** Flask-Login sessions with HttpOnly, Secure, SameSite=Lax cookies and CSRF tokens; same-origin deployment.
- **Why:** Simpler and safer than JWT + refresh for a same-origin web app; easy revocation.

# ADR-003: Native PostgreSQL 18, no Docker

- **Status:** Accepted
- **Decision:** Local development uses the installed PostgreSQL 18 service (localhost:5432). Separate `hostelcare` and `hostelcare_test` databases with a least-privilege app role.
- **Consequences:** CI uses a postgres:18 service container.

# ADR-004: Minimal Phase 0 dependencies

- **Status:** Accepted
- **Decision:** Add libraries only when first used (e.g. TanStack Query, React Router, Flask-Login, argon2-cffi, marshmallow arrive with features).

# ADR-005: Admin-initiated password reset

- **Status:** Accepted
- **Decision:** Admin triggers a reset; system generates a one-time temporary credential (shown once, stored only hashed, expires); `must_change_password` forces change at next login. Passwords are never viewable. Self-service/email reset deferred.

# ADR-006: Complete complaint history

- **Status:** Accepted
- **Decision:** Append-only `complaint_history` records creation, assignment, status changes, resolution, reopening, with actor and timestamp.
