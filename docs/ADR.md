# Architecture Decision Records (continued)

**Revision 2 (2026-11-14):** owner review applied. ADR-009 and ADR-015 are superseded; ADR-005 (in `adr/0001-initial-decisions.md`, admin temporary credential) is superseded by ADR-017 and is not edited there; ADR-006 (complaint history) is extended by ADR-020; ADR-012, ADR-014 and ADR-016 are amended. New: ADR-017 to ADR-026. Status key: *Proposed* = awaiting owner sign-off, *Accepted* = confirmed by the owner in review.

ADR-001 to ADR-006 are in [adr/0001-initial-decisions.md](adr/0001-initial-decisions.md) and remain in force unless amended below. New records continue the numbering here.

# ADR-007: Identifiers - bigint identity keys with UUID/reference public identifiers

- **Status:** Proposed (confirms the approved v0.2 "Bigint PK, UUID public IDs")
- **Context:** The Phase 3A brief prefers UUID primary keys "if appropriate". The approved architecture already chose bigint keys.
- **Decision:** Every table has `id bigint GENERATED ALWAYS AS IDENTITY`; profile tables use `user_id`. `users`, `payment_attempts`, `payments` and `notifications` also carry `public_id uuid` (`gen_random_uuid()`). Complaints and fines are addressed by human `reference_no` (`CMP-2026-00089`, `FIN-2026-00012`) from sequences, which the frontend already uses. The API never exposes internal ids.
- **Why:** Smaller and faster indexes and joins (many FKs, history tables), sequential insert locality, no ID guessing risk because internal ids are not exposed and every query is principal-scoped. Random UUID PKs would bloat every FK and index for no security gain here.
- **Consequences:** Two identifiers on a few tables. Export/merge across systems is not a goal (single hostel).

# ADR-008: Scope extension - fines, payments, disputes, notifications

- **Status:** Proposed
- **Context:** v0.2 limited scope to complaints and maintenance. The frontend and Phase 3A brief add fines, disputes, Razorpay-ready payments and notifications.
- **Decision:** Add modules D (fines), E (payments), F (notifications) to the schema design. The Razorpay gateway itself is not integrated in this phase.
- **Consequences:** v0.2 "Scope" line in ARCHITECTURE.md is superseded. Roadmap in TODO.md updated.

# ADR-009: One password-reset table for self-service and admin-issued resets

- **Status:** SUPERSEDED by ADR-017 (Rev 2, 2026-11-14). Original text kept for history.
- **Context:** ADR-005 chose admin-initiated reset with a temporary credential and deferred self-service/email. The brief requires secure, single-use, expiring reset tokens.
- **Decision:** `password_reset_tokens` stores only `SHA-256(token)` with `purpose` (`admin_issued` | `self_service`), `expires_at`, `used_at`, `revoked_at`. An admin-issued reset produces a one-time high-entropy code, shown once to the admin, redeemed by the user to choose a new password (so no temporary password is stored in `users`). Redemption is one conditional `UPDATE ... RETURNING`, which makes it atomic and single-use. A partial unique index allows one live token per user and purpose. `must_change_password` remains for the initial password of admin-created staff accounts. Email delivery stays deferred; the schema needs no change when it arrives.
- **Why:** Same security properties for both flows with one mechanism; no reusable or guessable temporary passwords at rest.
- **Consequences:** ADR-005's "temporary credential" becomes "one-time reset code". Owner to confirm.

# ADR-010: Fixed roles in a column; no roles/permissions, sessions or hostel tables

- **Status:** Proposed
- **Decision:** `users.role` (`student|staff|admin`) with a CHECK; authorization is a deny-by-default service-layer matrix with principal-scoped queries. No `roles`, `permissions`, `sessions`, `hostels`, `violation_categories` or `attachments` tables. Session invalidation uses `users.session_version`.
- **Why:** Three immutable roles and one hostel; extra tables add joins and failure modes without capability. Foreign keys to `student_profiles`/`staff_profiles` give the database a structural role guarantee.
- **Consequences:** Adding sub-roles later (e.g. read-only warden) means a new column/check, not a rewrite.

# ADR-011: No PostgreSQL Row-Level Security (yet)

- **Status:** Proposed
- **Decision:** Do not use RLS. Enforce scoping in services, protect integrity with constraints, and limit damage with table-level grants (no DELETE, append-only history tables).
- **Why:** The app connects as one runtime role; RLS would need per-request `SET LOCAL` identity plumbing and complicates migrations and testing. Revisit if multiple services or direct SQL access appear.

# ADR-012: Append-only history, no hard deletes, restrictive foreign keys

- **Status:** Proposed - AMENDED by ADR-022 (Rev 2): payments is append-only too; UPDATE is column-level; zero DELETE privileges for runtime role
- **Decision:** All FKs are `ON DELETE RESTRICT`. History/ledger tables (`complaint_history`, `complaint_updates`, `complaint_internal_notes`, `fine_history`, `payment_events`, `audit_logs`) grant the runtime role SELECT and INSERT only. Records are retired by status, not deleted. Even expired `password_reset_tokens` are not directly deletable by `hostelcare_app` (`hostelcare_app` holds zero `DELETE` privileges across all 20 tables); they are purged solely via the owner-owned `SECURITY DEFINER` function `public.purge_expired_password_reset_tokens()`.
- **Why:** Auditability and tamper resistance even if the application has a bug or is compromised at the app level.

# ADR-013: Admin-only complaint notes live in a separate table

- **Status:** Proposed
- **Decision:** `complaint_internal_notes` is its own table instead of an `is_internal` flag on a shared comments table.
- **Why:** A forgotten filter cannot leak a note when student/staff queries never touch the table. Authorization tests can assert that only admin services reference it. Notes are never copied into notifications, history notes or non-admin responses.

# ADR-014: Overlap and capacity guarded by exclusion constraints

- **Status:** Proposed - AMENDED by ADR-026 (Rev 2): ranges are half-open and T1 takes a row lock
- **Decision:** `room_allocations` use `EXCLUDE USING gist` on `(student, daterange)` and `(room, bed_number, daterange)` (extension `btree_gist`, a trusted extension created by `hostelcare_owner`). `bed_number <= capacity` is enforced by constraint trigger T1; the service also locks the room row.
- **Why:** Concurrency-proof rules belong in the database. Per-bed exclusivity implies capacity is never exceeded at any date.
- **Alternatives rejected:** application-only counting (race-prone); occupancy counter column (drifts).

# ADR-015: Payments trust only server-side verification; idempotency in the database

- **Status:** SUPERSEDED by ADR-018 (Rev 2, 2026-11-14). Original text kept for history.
- **Decision:** A fine becomes `paid` only through a `payments` row with `status='verified'` (server HMAC / API verification of order id, amount, currency and capture). One verified payment per fine is guaranteed by a partial unique index; constraint trigger T2 rejects `paid` without a verified payment. Webhooks are idempotent through a unique `payment_events.gateway_event_id`; the event row is inserted last, so `payment_events` stays append-only. Amounts are `numeric(12,2)` INR, converted to integer paise only at the gateway boundary. No payment secrets, card data or signatures are stored; stored payloads are allow-listed. Frontend success callbacks are logged and never change state. No network calls while holding row locks.
- **Consequences:** A payment verified after a fine was waived/cancelled becomes `refund_required` for manual handling.

# ADR-016: Status enumerations as varchar + CHECK; overdue is derived

- **Status:** Proposed - AMENDED by ADR-020 (Rev 2): reopening is a transition; only rejected is terminal
- **Decision:** lower_snake_case values with named CHECKs. "Returned for rework" is a transition (`completed -> in_progress`) recorded in history, not a status. Fine `overdue` is computed from `due_date` and status, never stored.
- **Why:** Adding a value is a simple migration; derived state cannot go stale.



# ADR-017: Self-service email password reset (supersedes ADR-005 and ADR-009)

- **Status:** Accepted (confirmed by owner in review)
- **Context:** ADR-005 selected admin-issued temporary passwords, and ADR-009 proposed admin-issued one-time codes. The owner required a self-service email reset architecture: cryptographically secure random token, store only its hash, 30-minute expiry, single-use redemption, neutral responses to prevent account enumeration, rate limiting, and invalidation of existing tokens upon redemption. Administrators may trigger reset emails but must never issue or email temporary passwords.
- **Decision:** Implement self-service email password reset using `password_reset_tokens`. Generate 256-bit random tokens (`secrets.token_urlsafe(32)`) and store only `SHA-256(token)`. Tokens expire in exactly 30 minutes (`CHECK expires_at <= created_at + interval '30 minutes'`). Redemption is single-use and atomic via a conditional SQL `UPDATE ... WHERE token_hash = :h AND used_at IS NULL AND revoked_at IS NULL AND expires_at > now() RETURNING user_id`. Upon redemption, all other active tokens for that user are revoked, `session_version` is incremented (revoking all existing sessions), and `password_hash` is updated with Argon2id. Newly created staff and admin accounts that have not yet established a password start with the unusable-password marker `password_hash = '!'` (`CHECK (password_hash = '!' OR password_hash LIKE '$argon2id$%')`); the authentication service unconditionally rejects `'!'` before Argon2id verification (performing a dummy Argon2id verification for constant-time rejection) so the marker can never bypass authentication. Requests respond with neutral messaging regardless of account existence. Rate limiting is enforced using database records (recent tokens per user and `audit_logs` per IP). Administrators can invoke a trigger endpoint that sends the standard reset email to the user (`requested_by = admin_id`), but administrators never see or generate passwords or tokens. Expired tokens are cleaned up via `public.purge_expired_password_reset_tokens()` (`SECURITY DEFINER`, owned by `hostelcare_owner`, `SET search_path = public, pg_temp`), which deletes only rows with `expires_at < now() - interval '24 hours' AND created_at < now() - interval '24 hours'`, ensuring `hostelcare_app` holds zero `DELETE` privileges and active or rate-limiting tokens can never be deleted.
- **Consequences:** Eliminates temporary password generation and runtime `DELETE` privileges entirely. Requires email delivery integration (abstracted per ADR-023).

# ADR-018: Separate payment attempts from verified payments and explicit refund architecture (supersedes ADR-015)

- **Status:** Accepted (confirmed by owner in review)
- **Context:** ADR-015 stored attempts and verified payments in a single table and auto-classified late/unapplied captures as refunds (`refund_required`). The owner required separating payment attempts from verified payments, never trusting browser callbacks, idempotent webhook processing, only verified payments marking fines paid, and keeping refunds as explicit future financial operations rather than automatic classifications of late payments.
- **Decision:** Split into two tables: `payment_attempts` (mutable state: `created`, `processing`, `succeeded`, `captured_unapplied`, `failed`, `cancelled`) and `payments` (immutable, verified payments only; runtime has SELECT and INSERT only). A composite foreign key `(payment_attempt_id, fine_id) REFERENCES payment_attempts (id, fine_id)` on `payments` (backed by `UNIQUE (id, fine_id)` on `payment_attempts`) and `UNIQUE (payment_attempt_id)` prevent any payment attempt from being reused for another fine or another payment. A fine transitions to `paid` if and only if a corresponding row in `payments` is created in the same transaction following server-side verification (HMAC verification of raw webhook payload or server-to-server gateway API verification), enforced at `COMMIT` by bidirectional deferred constraint triggers **T2a** (on `fines`) and **T2b** (on `payments`). Browser callbacks are logged for observability (`source = 'client_callback'`) but never change payment or fine state. Webhook idempotency is anchored by a unique constraint on `payment_events.gateway_event_id` and state-based transitions under fixed-order locks (`fines` `FOR UPDATE` -> `payment_attempts` `FOR UPDATE`). Payments captured after a fine is no longer pending or already paid are marked `captured_unapplied` in `payment_attempts` and logged for administrative investigation; they are not automatically labelled as refunds. Late payments (after `due_date`) for pending fines are accepted as valid payments.
- **Consequences:** Clean separation of volatile gateway interaction from immutable accounting records. The schema easily supports future refund tracking via a dedicated table without altering historical payments.

# ADR-019: Support for common-area complaints without active room allocations

- **Status:** Accepted (confirmed by owner in review)
- **Context:** Previously, `complaints.room_id` was non-nullable, requiring all complaints to be tied to a student's allocated room. The owner decided that approved students without active room allocations must be able to report common-area issues, while room-specific complaints still require an active room allocation.
- **Decision:** Introduce `location_type` (`room` or `common_area`) on `complaints`. For `location_type = 'room'`, `room_id` is mandatory and automatically populated from the student's active allocation, while `block_id` and `location_detail` must be NULL. For `location_type = 'common_area'`, `room_id` must be NULL, `location_detail` is mandatory free text (e.g., "Library reading room 2nd floor"), and `block_id` is optional. Enforce this via a CHECK constraint: `(location_type = 'room' AND room_id IS NOT NULL AND block_id IS NULL AND location_detail IS NULL) OR (location_type = 'common_area' AND room_id IS NULL AND location_detail IS NOT NULL AND btrim(location_detail) <> '')`.
- **Consequences:** Non-allocated, approved students can report facility issues across campus while preventing room misattribution for room-specific complaints.

# ADR-020: Reopening closed complaints and pre-acceptance rejection lifecycle (extends ADR-006 and amends ADR-016)

- **Status:** Accepted (confirmed by owner in review)
- **Context:** ADR-006 mentioned reopening, but the initial v0.3 lifecycle treated `closed` and `rejected` as terminal. The owner decided that wardens must be able to reopen closed complaints with a mandatory reason and complete history entry, and that complaints can be rejected during review before work is accepted, with a mandatory reason.
- **Decision:** Add a transition from `closed` to `under_review` (action: `reopened`) initiated by an administrator with a mandatory reason. In the database, `action IN ('returned_for_rework','rejected','reopened')` requires a non-empty `note` in `complaint_history`. When reopened, any previously open assignment is formally ended with `end_note` set to the reopen reason, allowing the warden to reassign the complaint to any technician (or the previous one). For rejection, allow transitions to `rejected` from `submitted`, `under_review`, and `assigned` (before the technician accepts the assignment). Once an assignment is `accepted`, rejection is disallowed; the work must proceed or be returned for rework by the warden after completion. Rejection requires `rejection_reason` in `complaints` and a corresponding `complaint_history` record.
- **Consequences:** Wardens can handle recurring issues on closed tickets while preserving full auditability. Technicians are protected from arbitrary ticket cancellations once on-site work is accepted.

# ADR-021: Single administrator role and student account reactivation

- **Status:** Accepted (confirmed by owner in review)
- **Context:** Initial design questioned whether admin tiers (e.g., super admin vs. junior warden) were required, and how rejected student registrations should be handled. The owner confirmed using one admin role initially, and allowing rejected students to be reactivated through an administrator-controlled process while preserving unique roll numbers and preventing duplicate accounts.
- **Decision:** Keep `users.role` as a single `admin` value with no sub-tiers; titles like "Chief Warden" or "Hostel Supervisor" are stored purely as display strings in `users.designation`. For rejected students, do not delete the user account or release the unique constraints on `users.email` and `student_profiles.roll_number`. Instead, allow administrators to transition `users.status` from `rejected` back to `pending` with a mandatory reason recorded in `audit_logs`. The reactivated student then re-enters the standard approval queue without creating a second account or orphaned records.
- **Consequences:** Simple RBAC model. Guaranteed preservation of unique student identity and immunity to duplicate registration fraud.

# ADR-022: Exact least-privilege PostgreSQL ownership and permissions (amends ADR-012)

- **Status:** Accepted (confirmed by owner in review)
- **Context:** The database architecture must strictly enforce separation of duties between schema ownership (migration role) and runtime data access (application role), preventing DDL, table ownership, migration table access, arbitrary row deletion, and history tampering by the application.
- **Decision:**
  - `hostelcare_owner` owns the databases, the `public` schema, all tables, sequences, functions, and extensions. It runs migrations via `MIGRATION_DATABASE_URL`.
  - `hostelcare_app` has `CONNECT` on the database and `USAGE` on the `public` schema; `CREATE` on `public` is revoked. It has no default privileges on future objects.
  - Runtime permissions are granted explicitly per table in each table's migration.
  - Mutable business tables (`users`, `student_profiles`, `staff_profiles`, `blocks`, `rooms`, `room_allocations`, `complaints`, `complaint_assignments`, `fines`, `fine_disputes`, `payment_attempts`, `notifications`) and `password_reset_tokens` receive SELECT, INSERT, and **column-specific UPDATE** grants (excluding primary keys, public UUIDs, created_at, reference numbers, and actor foreign keys). **Zero `DELETE` and zero `TRUNCATE` privileges are granted to `hostelcare_app` on any of the 20 tables.**
  - Ephemeral expired rows in `password_reset_tokens` are cleaned up solely via `public.purge_expired_password_reset_tokens()` (`SECURITY DEFINER`, owned by `hostelcare_owner`, `SET search_path = public, pg_temp`, `REVOKE ALL FROM PUBLIC`, `GRANT EXECUTE TO hostelcare_app`), which takes zero parameters and deletes only rows satisfying `expires_at < now() - interval '24 hours' AND created_at < now() - interval '24 hours'`.
  - Append-only tables (`complaint_updates`, `complaint_internal_notes`, `complaint_history`, `fine_history`, `payments`, `payment_events`, `audit_logs`) receive **SELECT and INSERT only**. No UPDATE, DELETE, or TRUNCATE.
  - Trigger functions **T1a**, **T1b**, **T2a**, **T2b**, and **T3** are owned by `hostelcare_owner`, run as **`SECURITY INVOKER`** with `SET search_path = public, pg_temp` (`REVOKE ALL FROM PUBLIC`), and require only the `SELECT` and existing mutable-table column-level `UPDATE` privileges (`rooms` for T1a `FOR SHARE`; `fines` for T3 `FOR SHARE`) already held by `hostelcare_app`.
  - Reference sequences (`complaint_ref_seq`, `fine_ref_seq`, `receipt_seq`) receive `USAGE` only.
  - `alembic_version` has all privileges revoked from `PUBLIC` and `hostelcare_app`; the application role holds zero privileges (not even SELECT).
- **Consequences:** Even a complete application SQL injection vulnerability cannot alter schema, read migration metadata, delete active rows, truncate tables, or rewrite audit trails and financial ledgers.

# ADR-023: Provider-independent email delivery architecture

- **Status:** Accepted (confirmed by owner in review)
- **Context:** The system requires sending password reset emails and notification summaries, but must not be locked into a specific commercial email provider.
- **Decision:** Abstract email delivery behind an application mailer interface configured entirely via standard environment variables (`MAIL_BACKEND`, `MAIL_FROM`, `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT`, `MAIL_SMTP_USERNAME`, `MAIL_SMTP_PASSWORD`, `MAIL_USE_TLS`). Supported backends include standard SMTP and console (for development/testing). No third-party proprietary SDKs (SendGrid, AWS SES, Resend) are embedded in the database schema or core code. In the initial release, email dispatch is synchronous/background-thread without a database outbox table. If email delivery fails, the error is logged; password reset endpoints maintain neutral responses to prevent leaking delivery status.
- **Consequences:** The application can be deployed on any hosting environment with any standard SMTP server or relay without modifying schema or code.

# ADR-024: Full fine payments in initial release with extensible architecture for partial payments and refunds

- **Status:** Accepted (confirmed by owner in review)
- **Context:** The owner confirmed supporting full fine payments only in the initial release, while ensuring the architecture is easily extensible for partial payments and refunds later.
- **Decision:**
  - Enforce full payment in the initial release by: (1) unique constraint `uq_payments_fine` on `payments(fine_id)`, allowing at most one payment per fine; (2) constraint trigger T3 verifying that `payment_attempts.amount_inr` and `payments.amount_inr` exactly equal `fines.amount_inr`.
  - To support partial payments in the future, schema changes are strictly additive: drop `uq_payments_fine`, drop trigger T3, add `partially_paid` to `fines.status`, and calculate remaining balance as `fines.amount_inr - SUM(payments.amount_inr)`. The `payments` and `payment_attempts` tables require no structural refactoring.
  - For future refunds, a dedicated `refunds` table referencing `payments(id)` can be added without modifying the immutable `payments` ledger.
- **Consequences:** Simple and reliable initial payment verification logic with zero breaking changes when partial payments or refunds are introduced in subsequent phases.

# ADR-025: Structural isolation of private administrative complaint notes

- **Status:** Accepted (confirmed by owner in review)
- **Context:** Internal administrative notes must never be accessible or exposed to students or maintenance staff under any circumstance.
- **Decision:** Maintain `complaint_internal_notes` as an independent table rather than a boolean column (`is_internal`) on a shared comments table. Restrict the application repository and service layer so that student and staff endpoints and serializers have no foreign key relationships or query paths to `complaint_internal_notes`. Enforce this architectural boundary through automated architectural unit tests. Furthermore, ensure internal note text is never mirrored in notifications, audit log metadata, or public complaint history.
- **Consequences:** Eliminates the risk of accidental information disclosure caused by an omitted `WHERE is_internal = false` clause in student or staff queries.

# ADR-026: Half-open date ranges for room allocations and concurrency controls (amends ADR-014)

- **Status:** Accepted (confirmed by owner in review)
- **Context:** Room allocations must guarantee capacity at bed level, prevent overlapping allocations for the same student or bed, and correctly handle transfers on the same day.
- **Decision:** Define room occupancy using the half-open date interval `[start_date, end_date)`, where `start_date` is the first day of occupancy and `end_date` is the exclusive move-out date (NULL indicates an ongoing allocation). Enforce termination completeness via an explicit CHECK constraint:
  `CHECK ((end_date IS NULL AND ended_by IS NULL AND end_reason IS NULL) OR (end_date IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL AND btrim(end_reason) <> ''))`
  so an active allocation has all three columns NULL and an ended allocation has all three columns NOT NULL. Enforce overlap prevention via `btree_gist` exclusion constraints:
  `EXCLUDE USING gist (student_user_id WITH =, daterange(start_date, end_date, '[)') WITH &&)`
  `EXCLUDE USING gist (room_id WITH =, bed_number WITH =, daterange(start_date, end_date, '[)') WITH &&)`
  Transfers are executed within a single transaction by setting `end_date = transfer_date`, `ended_by`, and `end_reason` on the old allocation and inserting a new allocation with `start_date = transfer_date`. Because `[..., D)` and `[D, ...)` do not intersect, same-day room transfers succeed cleanly without violating exclusion constraints. Bed-level capacity is verified via constraint trigger T1 acquiring a `FOR SHARE` lock on the room row.
- **Consequences:** Eliminates boundary edge-case bugs and partial termination states in room scheduling and guarantees zero double-booking at the database level under concurrent operations.
