# HostelCare Database Design

**Status:** Revision 2 - proposed, awaiting owner review. No SQLAlchemy models, migrations or schema changes exist for this design yet.
**Target:** PostgreSQL 18, single hostel, SQLAlchemy 2 + Flask-Migrate, runtime role `hostelcare_app`, migration/owner role `hostelcare_owner`.
**Companion docs:** [database-erd.md](database-erd.md) (diagrams), [ADR.md](ADR.md) (decisions), [ARCHITECTURE.md](ARCHITECTURE.md), [TODO.md](TODO.md).

## Revision history

| Rev | Date | Summary |
|-----|------|---------|
| 1 | 2026-11-14 | Initial design: 19 tables, 13 conflicts documented (section 0), assumptions A1-A6, open questions Q1-Q6. |
| 2 | 2026-11-14 | Owner review applied (decisions D1-D8 below): self-service email password reset replaces admin-issued reset; payment attempts separated from verified payments; refund classification removed; complaint reopening; common-area complaints; student reactivation; half-open allocation ranges with locking rules; exact role privileges with column-level grants; DB-backed rate limiting; provider-independent email configuration. Now **20 tables**. |

### Owner decisions applied in Revision 2

| ID | Decision | Where reflected |
|----|----------|-----------------|
| D1 | One `admin` role only, no tiers | 3.1, 3.5 |
| D2 | Rejected students can be reactivated by an administrator; roll numbers stay unique; no duplicate accounts | 3.1, 3.2 |
| D3 | Wardens can reopen closed complaints with a mandatory reason and a history entry | 5.1, 5.5 |
| D4 | Complaints can be rejected during review, before work is accepted; reason mandatory | 5.1, 5.5 |
| D5 | Approved students without an active room can report common-area problems; room complaints need an active room | 5.1 |
| D6 | Full fine payments only initially; extensible to partial payments and refunds later | 7 |
| D7 | Email delivery provider-independent, via configuration | 3.4, ARCHITECTURE.md |
| D8 | Do not hard-delete important business records | 1, 10, 12 |

### Superseded in Revision 2

| Superseded (Rev 1) | Replaced by |
|--------------------|-------------|
| Admin-issued one-time reset code; `password_reset_tokens.purpose`; `users.must_change_password`; ADR-005 temporary credential; ADR-009 | Self-service email reset (30 min, hashed, single-use); admin can only trigger the email. ADR-017. |
| Single `payments` table holding attempts and verified payments; statuses `refund_required`/`refunded`; ADR-015 | `payment_attempts` + `payments` (verified only); late/duplicate captures are `captured_unapplied`, never auto-classified as refunds. ADR-018. |
| `closed` and `rejected` both terminal; question Q3 | Only `rejected` is terminal; `closed -> under_review` reopening. ADR-020. |
| `complaints.room_id NOT NULL`; assumption A3; question Q4 | `location_type` room/common_area. ADR-019. |
| Inclusive allocation ranges `[start, end]` | Half-open `[start, end)`; transfers are same-day safe. ADR-026. |
| Section 12 grant table (table-level only, `DELETE` on tokens) | Section 12: exact ownership, column-level `UPDATE`, sequences, verification queries. ADR-022. |
| Assumption A1 / question Q1, Q2, Q3, Q4, Q5, Q6 (partly) | Answered by D1-D8; remaining items in section 14. |

---

## 0. Inspection summary and conflicts

Reviewed: `backend/` (app factory, `extensions.py` naming convention, `config.py`, `db_cli.py`, tests), `database/setup_postgres.sql`, `docs/*`, `README.md`, and the frontend mock layer (`mockData.js`, `AppContext.jsx`, pages). The frontend mock store is the best statement of what the UI needs; the design covers every workflow it simulates.

| # | Finding | Resolution |
|---|---------|-----------|
| C1 | Approved v0.2: bigint PK + UUID public IDs; brief preferred UUID PKs. | Kept bigint + public ids (ADR-007). |
| C2 | v0.2 scope was complaints only. | Scope extended (ADR-008). |
| C3 | ADR-005 admin temporary credential vs brief's token reset. | **[SUPERSEDED Rev 2]** Self-service email reset only; admin triggers the email (ADR-017). No temporary passwords exist anywhere. |
| C4 | ADR-006 mentions reopening; Rev 1 lifecycle had none. | **[RESOLVED Rev 2, D3]** Reopening added (ADR-020). |
| C5 | TODO listed photo attachments; frontend has none. | No attachments table. |
| C6 | `setup_postgres.sql` comments call the audit table `audit_log`. | Table is `audit_logs`; the comment is documentation only. Script not changed. |
| C7 | `config.py` `HOSTEL_BLOCKS`, `HOSTEL_ROOM_PATTERN`. | Database `blocks`/`rooms` are authoritative; env values are seed/validation hints. |
| C8 | Brief asks for `architecture.md`/`ADR.md`; repo has `ARCHITECTURE.md`, `adr/`. | `architecture.md` is `ARCHITECTURE.md` on Windows (updated in place). `docs/ADR.md` continues numbering after ADR-006. |
| C9 | Mock lets admin start work / mark `Resolved`. | Backend does not expose admin start/complete. `Resolved` maps to `completed`. Frontend alignment is a later phase. |
| C10 | Mock fine `Overdue` and label `issuedBy`. | `overdue` derived; `issued_by` is a FK to the authenticated admin. |
| C11 | Mock staff PIN login. | Real staff use email + password (Argon2id). Duty state not modelled. |
| C12 | Separate mock staff notification list. | One `notifications` table. |
| C13 | README says "Phase 0 only". | Out of scope; tracked in TODO. |
| C14 (new) | `setup_postgres.sql` revokes default privileges and grants no table access, as required. | Confirmed compatible: per-table grants in each migration (section 12). No script change needed. |
| C15 (new) | Mock fine payments store a mock Razorpay order/transaction on the fine itself. | Moved to `payment_attempts` / `payments`. |

---

## 1. Conventions

| Topic | Rule |
|-------|------|
| Primary keys | `id bigint GENERATED ALWAYS AS IDENTITY`. Profile tables use `user_id` as PK (true 1:1). |
| Public identifiers | `public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE` on `users`, `payment_attempts`, `payments`, `notifications`. Complaints and fines use a human `reference_no` (`CMP-2026-00089`, `FIN-2026-00012`), rooms use block code + room number. Internal ids are never exposed by the API. |
| Enumerations | `varchar` + named CHECK, lower_snake_case values; the API maps to display labels. No native enums, no lookup tables for fixed sets. |
| Timestamps | Every instant is `timestamptz` (UTC; `created_at DEFAULT now()`). Mutable tables carry `updated_at` maintained by the application. Calendar facts (`issue_date`, `due_date`, allocation dates) are `date` in `Asia/Kolkata`; a fine is overdue after the end of its due date in IST. Application sets session `TimeZone = 'UTC'`. |
| Money | `numeric(12,2)` INR; Python `Decimal`; never `float`/`money`. Razorpay paise = `int(amount * 100)` only at the gateway boundary, compared exactly. `CHECK (amount > 0)` everywhere. |
| Text | Free text is `text` (or short `varchar(n)`) with `CHECK (btrim(col) <> '')` and an upper length bound. |
| Emails | Trimmed + lower-cased by the app and enforced by `CHECK (email = lower(btrim(email)))`, so plain UNIQUE works (no `citext`). |
| Naming | Existing `NAMING_CONVENTION` in `backend/app/extensions.py`. CHECKs are always explicitly named. |
| Deletes (D8) | **No record in any table is directly deletable by the runtime role (`hostelcare_app` holds zero `DELETE` privileges across all 20 tables).** All FKs are `ON DELETE RESTRICT ON UPDATE NO ACTION`. People are suspended/deactivated, rooms/blocks deactivated, complaints closed/rejected, fines waived/cancelled. Expired `password_reset_tokens` are purged exclusively via a narrowly scoped, parameterless `SECURITY DEFINER` function (`public.purge_expired_password_reset_tokens()`) owned by `hostelcare_owner` (see 3.4 and 12.3). |
| Extension | `btree_gist` only (needed by exclusion constraints). Verified: `trusted = true` in the installed PostgreSQL 18 (`share/extension/btree_gist.control`, version 1.8), so `hostelcare_owner` (database owner, NOSUPERUSER) can run `CREATE EXTENSION`. See 4.4. |
| Append-only tables | `complaint_updates`, `complaint_internal_notes`, `complaint_history`, `fine_history`, `payments`, `payment_events`, `audit_logs`. Runtime role: SELECT + INSERT only. |
| Mandatory reasons | Enforced in the database where the reason lives in the same row (CHECKs on `complaints.rejection_reason`, `fines.resolution_reason`, `fine_disputes.decision_reason`, and on `note` of reason-bearing history actions). |

---

## 2. Table inventory (20 tables)

| # | Module | Table | Purpose |
|---|--------|-------|---------|
| 1 | A Identity | `users` | One login account per person; role and account state |
| 2 | A | `student_profiles` | Student data and registration review (1:1) |
| 3 | A | `staff_profiles` | Staff data (1:1) |
| 4 | A/G | `password_reset_tokens` | Hashed, single-use, 30-minute reset tokens |
| 5 | B Rooms | `blocks` | Hostel blocks |
| 6 | B | `rooms` | Rooms with capacity |
| 7 | B | `room_allocations` | Dated student-to-bed assignments |
| 8 | C Complaints | `complaints` | Complaint and current status |
| 9 | C | `complaint_assignments` | Every staff assignment ever made |
| 10 | C | `complaint_updates` | Staff progress/completion narrative (student-visible) |
| 11 | C | `complaint_internal_notes` | Admin-only notes |
| 12 | C | `complaint_history` | Append-only status/assignment ledger |
| 13 | D Fines | `fines` | A fine issued to a student |
| 14 | D | `fine_disputes` | Student dispute and admin decision |
| 15 | D | `fine_history` | Append-only fine ledger |
| 16 | E Payments | `payment_attempts` | Each gateway checkout attempt (any outcome) |
| 17 | E | `payments` | **Verified** payments only (immutable financial record) |
| 18 | E | `payment_events` | Append-only gateway/webhook/client event log (idempotency) |
| 19 | F | `notifications` | In-app notifications |
| 20 | G | `audit_logs` | Append-only audit trail (also backs rate limiting) |

Added beyond the original brief: `complaint_internal_notes` (Rev 1) and `payment_attempts` (Rev 2, owner request to separate attempts from verified payments). Deliberately absent: roles/permissions, sessions, hostels, violation categories, attachments, refunds, email outbox (ADR-010, ADR-018, ADR-023).

---

## 3. Module A - Identity and authentication

### 3.1 `users`
One account per person; unique email.

| Column | Type | Null | Default / notes |
|--------|------|------|-----------------|
| id | bigint identity | NO | PK |
| public_id | uuid | NO | `gen_random_uuid()` |
| email | varchar(254) | NO | normalised lower-case |
| full_name | varchar(120) | NO | |
| phone | varchar(20) | YES | |
| designation | varchar(80) | YES | display title for admins ("Chief Warden"); not a permission |
| password_hash | varchar(255) | NO | Argon2id PHC string (`$argon2id$...`), or `'!'` as an explicit unusable-password marker for newly created staff/admin accounts that have not yet set a password |
| role | varchar(10) | NO | `student` / `staff` / `admin` (single admin role, D1) |
| status | varchar(12) | NO | `pending`, `active`, `rejected`, `suspended`, `deactivated` (set by service) |
| password_changed_at | timestamptz | YES | |
| session_version | integer | NO | `1`; bump to revoke all sessions |
| failed_login_count | smallint | NO | `0` |
| locked_until | timestamptz | YES | |
| last_login_at | timestamptz | YES | |
| created_by | bigint | YES | FK users: admin who created a staff/admin account; NULL for self-registered students and the CLI first admin |
| created_at / updated_at | timestamptz | NO | |

- **PK** `id`; **FK** `created_by -> users(id)` RESTRICT.
- **UNIQUE** `public_id`; `email`; `(id, role)` (target of the profile composite FKs).
- **CHECK** `role IN (...)`; `status IN (...)`; `role = 'student' OR status NOT IN ('pending','rejected')`; `email = lower(btrim(email))` and `position('@' in email) > 1`; `btrim(full_name) <> ''`; `password_hash = '!' OR password_hash LIKE '$argon2id$%'`; `failed_login_count >= 0`; `session_version >= 1`.
- **Unusable-password marker (`'!'`) security rules:**
  1. *Purpose:* When an administrator creates a staff or admin account, no temporary password is generated. Instead, `users.password_hash` is initialised to `'!'` (an explicit unusable-password marker that is not a valid Argon2id PHC string) until the user sets their password via the 30-minute reset link.
  2. *Unconditional authentication rejection:* The authentication service **must** explicitly reject any account where `password_hash == '!'` or `not password_hash.startswith('$argon2id$')` before attempting password verification. To prevent timing side-channels, when `password_hash == '!'` (or when the email is unknown), the service still runs a dummy `PasswordHasher.verify()` against a constant precomputed Argon2id hash and returns the standard generic invalid-credentials response.
  3. *Defense in depth:* `argon2-cffi`'s `PasswordHasher.verify(hash, password)` only parses valid `$argon2id$...` PHC strings and raises `InvalidHashError` if passed `'!'`. The `'!'` marker is never compared for string equality against user input, so supplying `"!"` as a password can never authenticate.
- **Indexes** `ix_users_role_status (role, status)`; partial `ix_users_pending (created_at) WHERE role='student' AND status='pending'`.
- **Access rule:** a request reaches a protected endpoint only if `status = 'active'`. `pending`, `rejected`, `suspended`, `deactivated` fail at the session loader. `session_version` mismatch rejects an existing session.
- **Student status transitions (service, admin only except the first):** registration -> `pending`; `pending -> active` (approve); `pending -> rejected` (reason mandatory); **`rejected -> pending` (administrator reactivation, reason mandatory, D2)** then the normal approval; `active <-> suspended`; `active|suspended -> deactivated`. Reactivation reuses the **same account row**, so there is never a second account. Staff/admin: `active <-> suspended`, `-> deactivated`.
- **Duplicate registrations:** UNIQUE `email` and UNIQUE `student_profiles.roll_number` are never released (rejected, suspended and deactivated rows keep them). A second registration with a used email or roll number fails with a generic message ("contact the warden office"); nothing reveals which field matched.

### 3.2 `student_profiles`

| Column | Type | Null | Notes |
|--------|------|------|-------|
| user_id | bigint | NO | PK and FK |
| role | varchar(10) | NO | `'student'` |
| roll_number | varchar(32) | NO | unique, upper-case |
| requested_room_id | bigint | YES | room typed at registration; a preference, **not** an allocation |
| reviewed_by | bigint | YES | admin of the latest decision |
| reviewed_at | timestamptz | YES | |
| review_note | text | YES | latest decision note |
| created_at / updated_at | timestamptz | NO | |

- **FK** `(user_id, role) -> users(id, role)` RESTRICT (with `CHECK role = 'student'` only student users can have a profile); `requested_room_id -> rooms` RESTRICT; `reviewed_by -> users` RESTRICT.
- **UNIQUE** `roll_number`. **CHECK** `roll_number = upper(btrim(roll_number)) AND roll_number ~ '^[A-Z0-9][A-Z0-9/_-]{2,31}$'`; `(reviewed_by IS NULL) = (reviewed_at IS NULL)`; `review_note IS NULL OR btrim(review_note) <> ''`.
- `reviewed_*` hold only the latest decision. **Every decision (approve, reject, reactivate) also appends an `audit_logs` row with the reason**, so the full registration history is preserved (D8) without another table.

### 3.3 `staff_profiles`

| Column | Type | Null | Notes |
|--------|------|------|-------|
| user_id | bigint | NO | PK and FK |
| role | varchar(10) | NO | `'staff'` |
| staff_code | varchar(20) | NO | unique, e.g. `STF-0007` |
| trade | varchar(60) | NO | free text (any trade) |
| shift | varchar(60) | YES | staff may edit |
| created_at / updated_at | timestamptz | NO | |

FK `(user_id, role) -> users(id, role)`; UNIQUE `staff_code`; CHECK `role = 'staff'`, `btrim(trade) <> ''`, `staff_code ~ '^[A-Z0-9-]{3,20}$'`. Staff can change `phone`, `shift` (email with re-authentication); `trade` is admin-only. Staff accounts are created by an admin with an unusable password hash, then the admin triggers the reset email so the staff member sets their own password (no temporary password is issued or emailed).

### 3.4 `password_reset_tokens`
Self-service email reset. An administrator may *trigger* the same email for a user but never sees, issues or emails a password or token.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| user_id | bigint | NO | FK users |
| token_hash | char(64) | NO | hex SHA-256 of the raw token |
| requested_by | bigint | YES | FK users; admin who triggered the email; NULL = requested by the user |
| created_at | timestamptz | NO | `now()` |
| expires_at | timestamptz | NO | `created_at + 30 minutes` |
| used_at | timestamptz | YES | |
| revoked_at | timestamptz | YES | |
| request_ip | inet | YES | |

- **Token:** 32 random bytes from `secrets.token_urlsafe(32)` (256-bit). Only `SHA-256(token)` is stored (high-entropy secret, so a fast hash is correct). The raw token appears only in the emailed link and is never logged, returned by the API, or placed in audit metadata.
- **UNIQUE** `token_hash`. **FK** `user_id`, `requested_by` RESTRICT.
- **CHECK** `token_hash ~ '^[0-9a-f]{64}$'`; `expires_at > created_at AND expires_at <= created_at + interval '30 minutes'` (the 30-minute expiry is a hard database cap); `NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)`.
- **Partial UNIQUE** `uq_prt_one_live (user_id) WHERE used_at IS NULL AND revoked_at IS NULL` - at most one live token per user.
- **Indexes** `ix_prt_user_created (user_id, created_at DESC)`; `ix_prt_ip_created (request_ip, created_at DESC) WHERE request_ip IS NOT NULL`; `ix_prt_expires (expires_at)`.

**Request flow (neutral response, rate limited)**
1. `POST /auth/password-reset/request {email}` always returns the same status, body and (as far as practical) timing, whether or not the account exists; the lookup, token creation and email send happen after the response is prepared (background thread, short SMTP timeout).
2. Rate limit first (below). If the account exists, is `active` and has no token created in the last 60 seconds: in one transaction revoke any live token, insert the new token row, write `audit_logs` (`auth.reset_requested`); after commit send the email. Unknown, non-active or cooling-down accounts do nothing.
3. Admin-triggered: `POST /admin/users/:id/send-password-reset` does the same with `requested_by = admin` and audit `auth.reset_triggered`. The API response says only "email queued"; it never returns the token.

**Redemption (single use, atomic)**
```sql
UPDATE password_reset_tokens SET used_at = now()
WHERE token_hash = :h AND used_at IS NULL AND revoked_at IS NULL AND expires_at > now()
RETURNING user_id;
```
Zero rows -> generic "invalid or expired link". In the **same transaction** on success: set the new Argon2id `password_hash`, `password_changed_at`, bump `session_version` (logs out every session), reset `failed_login_count`/`locked_until`, **revoke every other live token of the user** (`UPDATE ... SET revoked_at = now() WHERE user_id = :u AND used_at IS NULL AND revoked_at IS NULL`), insert `audit_logs` (`auth.reset_redeemed`). A confirmation email is sent after commit.

**Rate limiting (D7-compatible, no Redis, cross-worker, durable)**
- Per account: count rows in `password_reset_tokens` for the user in the last hour (index above).
- Per IP (also covers unknown emails, which create no token row): count `audit_logs` rows with `action = 'auth.reset_requested'` and the same `ip_address` in the window, using `ix_audit_action_ip (action, ip_address, occurred_at DESC)`. Invalid redemption attempts write `auth.reset_invalid` rows counted the same way.
- Proposed defaults (confirmed, U1): 3 requests per account per hour, 10 requests per IP per hour, 10 invalid redemptions per IP per 15 minutes. Once an IP is over its limit the request is answered neutrally and **no further audit row is written** (prevents the limiter being used to flood the table).
- A coarse in-memory per-process limiter (Flask-Limiter) may sit in front as defence in depth, but correctness does not depend on it.

**Expired-token cleanup (no direct `DELETE` privilege for `hostelcare_app`)**
- Because a PostgreSQL table-level `DELETE` grant cannot restrict which rows are deleted, **`hostelcare_app` is granted NO `DELETE` privilege on `password_reset_tokens`** (only `SELECT, INSERT, UPDATE (used_at, revoked_at)`).
- Instead, the migration creates a narrowly scoped, parameterless cleanup function owned by `hostelcare_owner`:
  ```sql
  CREATE OR REPLACE FUNCTION public.purge_expired_password_reset_tokens()
  RETURNS integer
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = public, pg_temp
  AS $$
  DECLARE
    deleted_count integer;
  BEGIN
    DELETE FROM public.password_reset_tokens
    WHERE expires_at < now() - interval '24 hours'
      AND created_at < now() - interval '24 hours';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
  END;
  $$;

  ALTER FUNCTION public.purge_expired_password_reset_tokens() OWNER TO hostelcare_owner;
  REVOKE ALL ON FUNCTION public.purge_expired_password_reset_tokens() FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.purge_expired_password_reset_tokens() TO hostelcare_app;
  ```
- **Why this cannot delete active or rate-limiting tokens:**
  1. *Active tokens remain untouched:* Live tokens always satisfy `expires_at > now()` (maximum 30-minute lifetime). The hardcoded predicate `expires_at < now() - interval '24 hours'` only matches tokens that have been expired for more than 24 hours.
  2. *Rate-limit window remains intact:* Per-account rate limiting counts `password_reset_tokens` rows with `created_at >= now() - interval '1 hour'`. Because cleanup requires `created_at < now() - interval '24 hours'`, rows inside the 1-hour rate-limit window can never be purged early.
  3. *No caller-supplied parameters:* The function accepts zero arguments, has a fixed `search_path = public, pg_temp`, and is executable only by `hostelcare_owner` and `hostelcare_app` (for the scheduled `flask purge-reset-tokens` CLI task). Even if invoked repeatedly by `hostelcare_app`, it can never delete active tokens.

**Email delivery is provider-independent (D7):** the application talks to a small mailer interface selected by configuration (`MAIL_BACKEND` = `smtp` | `console` | `disabled`, `MAIL_FROM`, `MAIL_SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS`, `APP_BASE_URL` for links), all from environment variables. No provider SDK is baked in; any SMTP relay works, and `console` is used in development/tests. The database stores no email bodies or provider data. No outbox table in the initial release: failures are logged, the user may request again, and the neutral response hides the failure (ADR-023).

### 3.5 Authentication and authorization relationships
- Authentication: `users.email` + Argon2id (`argon2-cffi`, parameters inside the hash, rehash on login when parameters change); server-side cookie sessions with `session_version`; per-account lockout via `failed_login_count`/`locked_until`; per-IP login throttling counted from `audit_logs` (`auth.login_failed`).
- Authorization: `users.role`; deny-by-default service layer; every query principal-scoped. Frontend guards are UX only.
- FKs to `student_profiles(user_id)` / `staff_profiles(user_id)` make non-student complaints/fines/allocations and non-staff assignments structurally impossible.

| Capability | student (active) | staff (active) | admin (active) |
|-----------|------------------|----------------|----------------|
| Register | yes (becomes `pending`) | no | no |
| Approve/reject/reactivate students; create staff; suspend; trigger reset email | no | no | yes |
| Own profile | limited | phone/shift | yes |
| Blocks/rooms/allocations read | own room | none | all |
| Blocks/rooms/allocations write | no | no | yes |
| Submit complaint | yes (room complaint needs an active allocation; common-area does not) | no | no |
| Read complaint | own only; **no internal notes, no assignment instructions** | **only complaints with an open assignment to them** (read); no internal notes | all, incl. internal notes |
| Review, assign/reassign, close, return for rework, reopen, reject | no | no | yes |
| Accept, start, progress, complete | no | only the **current assignee** | no |
| Issue/waive/cancel fine, decide dispute, record manual payment | no | no | yes |
| Read fines / dispute / pay | own only | no | all |
| Read audit logs | no | no | yes |
| Notifications | own | own | own |

---

## 4. Module B - Hostel and room management

One hostel only (no `hostels` table; name from `HOSTEL_NAME`).

### 4.1 `blocks`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| code | varchar(10) | NO | `A`, `B` ... |
| name | varchar(80) | NO | "Block A (Nalanda)" |
| display_order | smallint | NO | `0` |
| is_active | boolean | NO | `true` |
| created_at / updated_at | timestamptz | NO | |

UNIQUE `code`, UNIQUE `name`; CHECK `code ~ '^[A-Z0-9]{1,10}$'`.

### 4.2 `rooms`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| block_id | bigint | NO | FK blocks RESTRICT |
| room_number | varchar(10) | NO | "203" |
| floor | smallint | NO | |
| room_type | varchar(40) | YES | label, e.g. "Double Occupancy" |
| capacity | smallint | NO | number of beds |
| is_active | boolean | NO | `true`; inactive rooms accept no new allocations |
| created_at / updated_at | timestamptz | NO | |

UNIQUE `uq_rooms_block_id_room_number (block_id, room_number)` (A-203 and B-203 can coexist; label = `blocks.code || '-' || room_number`). CHECK `capacity BETWEEN 1 AND 8`, `floor BETWEEN 0 AND 50`, `room_number ~ '^[A-Za-z0-9-]{1,10}$'`. Index `ix_rooms_block_id`.

### 4.3 `room_allocations`
One row per stay. History is preserved by never deleting or rewriting: moving a student ends the old row and inserts a new one.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| room_id | bigint | NO | FK rooms RESTRICT |
| student_user_id | bigint | NO | FK student_profiles(user_id) RESTRICT |
| bed_number | smallint | NO | 1..room capacity |
| start_date | date | NO | first night occupied |
| end_date | date | YES | **move-out date, exclusive** (first day no longer occupied); NULL = still open |
| allocated_by | bigint | NO | FK users (admin) |
| ended_by | bigint | YES | FK users (admin) |
| end_reason | text | YES | |
| created_at | timestamptz | NO | `now()` |

Occupancy is the **half-open range `[start_date, end_date)`** (`end_date` NULL = unbounded).

- **CHECK**
  - `bed_number >= 1`
  - `end_date IS NULL OR end_date >= start_date` (equal dates give an empty range: a same-day correction is preserved but occupies nothing)
  - **Explicit termination completeness (`ck_room_allocations_termination`):**
    ```sql
    CHECK (
      (end_date IS NULL AND ended_by IS NULL AND end_reason IS NULL)
      OR
      (end_date IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL AND btrim(end_reason) <> '')
    )
    ```
    *Truth-table guarantee:* Of the 8 possible NULL/NOT NULL combinations of `(end_date, ended_by, end_reason)`, only `(NULL, NULL, NULL)` (active allocation) and `(NOT NULL, NOT NULL, NOT NULL)` with non-blank `end_reason` (ended allocation) satisfy the constraint. Partial termination states (such as setting `end_date` and `ended_by` while leaving `end_reason` NULL, or vice versa) are rejected.
- **Exclusion constraints (need `btree_gist`):**
  ```sql
  ALTER TABLE room_allocations ADD CONSTRAINT ex_alloc_student_no_overlap
    EXCLUDE USING gist (student_user_id WITH =, daterange(start_date, end_date, '[)') WITH &&);
  ALTER TABLE room_allocations ADD CONSTRAINT ex_alloc_bed_no_overlap
    EXCLUDE USING gist (room_id WITH =, bed_number WITH =, daterange(start_date, end_date, '[)') WITH &&);
  ```
- **Constraint trigger T1** (SECURITY INVOKER, fixed `search_path`), on `room_allocations` INSERT/UPDATE: `SELECT capacity, is_active FROM rooms WHERE id = NEW.room_id FOR SHARE`; require `bed_number <= capacity`, the room active (on INSERT), and the student's `users.status = 'active'` (on INSERT). A companion trigger on `rooms` UPDATE rejects lowering `capacity` (or deactivating is allowed, only new allocations are blocked) below the highest `bed_number` of any allocation with `end_date IS NULL OR end_date > current_date`.
- **Indexes** `ix_alloc_room_open (room_id) WHERE end_date IS NULL`; `ix_alloc_student (student_user_id, start_date DESC)`; the exclusion indexes also serve overlap queries.
- **Definitions:** *open* = `end_date IS NULL`. *Active today* = `start_date <= current_date_IST AND (end_date IS NULL OR end_date > current_date_IST)`. Complaint submission and the "my room" screen use *active today*; occupancy counts use the same predicate.
- **Transfer** (one transaction, order matters because constraints are checked per statement): (1) `UPDATE` old row `SET end_date = D, ended_by, end_reason`; (2) `INSERT` new row with `start_date = D`. The ranges touch but do not overlap, so a same-day transfer is legal and an overlap is impossible.

### 4.4 Verification of room-allocation guarantees (design review result)

| Requirement | Mechanism | Race-safe? |
|-------------|-----------|-----------|
| Bed-level capacity | Each occupant takes a distinct `bed_number`; `bed_number <= capacity` by T1; per-bed no-overlap by `ex_alloc_bed_no_overlap`. Therefore occupants on any date <= capacity. | Yes. Two admins taking the last bed: the second `INSERT` waits on the first's uncommitted index entry, then violates the exclusion constraint -> 409. |
| No overlapping active allocations for one student | `ex_alloc_student_no_overlap` (covers open, past and future-dated rows) | Yes |
| Same bed to two students simultaneously | `ex_alloc_bed_no_overlap` | Yes |
| Capacity reduced while an allocation is inserted | T1 takes `FOR SHARE` on the room row; the rooms `UPDATE` holds an exclusive row lock, so the two serialise, and the later one sees the committed data (READ COMMITTED re-evaluates per statement) | Yes |
| Allocation for a non-active student or inactive room | T1 | Yes |
| Historical correctness / transfers | Rows are never deleted; runtime role may only `UPDATE (end_date, ended_by, end_reason)` (column grant, section 12), so `room_id`, `student_user_id`, `bed_number`, `start_date`, `allocated_by` are immutable | Yes |
| Student leaves (suspended/deactivated) | Service ends the open allocation (`end_date = today`) in the same transaction | Service rule |
| Future-dated allocations | Allowed; the exclusion constraints treat them like any other range | Yes |

**Required extension and permissions.** `btree_gist` is needed only for the two exclusion constraints. The installed PostgreSQL 18 control file declares `trusted = true`, so a non-superuser with `CREATE` on the database can create it; `hostelcare_owner` owns both databases (per `setup_postgres.sql`) and therefore can. The first migration runs `CREATE EXTENSION IF NOT EXISTS btree_gist` as `hostelcare_owner` in each of `hostelcare` and `hostelcare_test`; the extension objects land in `public` and are owned by `hostelcare_owner`. `hostelcare_app` needs **no** privilege on the extension: inserting into a table with an exclusion index does not require access to the operator class. Built-ins only otherwise (`daterange`, `gen_random_uuid()`, `jsonb`, `inet`). Not executed in this phase; the migration test suite must prove it on `hostelcare_test`. If the extension could not be created, the fallback would be a trigger that locks the room row and checks overlaps, which is weaker, so this is a go/no-go item at implementation (section 14, U4).

---

## 5. Module C - Complaint management

### 5.1 `complaints`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| reference_no | varchar(20) | NO | `CMP-2026-00089` via `complaint_ref_seq` default |
| student_user_id | bigint | NO | FK student_profiles; **always from the session, never the request body** |
| location_type | varchar(11) | NO | `room` / `common_area` (D5) |
| room_id | bigint | YES | FK rooms; set by the server from the student's **active-today** allocation; only for `room` |
| block_id | bigint | YES | FK blocks; optional block for a common-area problem |
| location_detail | varchar(150) | YES | free text for common areas ("2nd floor washroom"); required for `common_area` |
| title | varchar(150) | NO | mandatory |
| description | text | NO | mandatory, <= 5000 |
| category | varchar(60) | YES | optional free text (UI suggests the standard list; "Other" allowed) |
| priority | varchar(6) | NO | `low` / `medium` / `high`, default `medium` |
| status | varchar(12) | NO | default `submitted` |
| rejection_reason | text | YES | mandatory when rejected |
| completed_at | timestamptz | YES | set on completion; cleared on rework/reopen |
| closed_at | timestamptz | YES | cleared on reopen |
| version | integer | NO | `1` optimistic-lock counter |
| created_at / updated_at | timestamptz | NO | `created_at` = system submission date |

- **Statuses:** `submitted`, `under_review`, `assigned`, `accepted`, `in_progress`, `completed`, `closed`, `rejected`. "Returned for rework" and "reopened" are *transitions* recorded in history, not statuses.
- **CHECK**
  - `status IN (...)`; `priority IN ('low','medium','high')`; `location_type IN ('room','common_area')`
  - `btrim(title) <> ''`; `btrim(description) <> ''`
  - `(location_type = 'room' AND room_id IS NOT NULL AND block_id IS NULL AND location_detail IS NULL) OR (location_type = 'common_area' AND room_id IS NULL AND location_detail IS NOT NULL AND btrim(location_detail) <> '')`
  - `(status = 'rejected') = (rejection_reason IS NOT NULL)`; `rejection_reason IS NULL OR btrim(rejection_reason) <> ''`
  - `(status IN ('completed','closed')) = (completed_at IS NOT NULL)`; `(status = 'closed') = (closed_at IS NOT NULL)`
- **Submission rules (service):** the user must be `active`. `location_type = 'room'` requires an active-today allocation and sets `room_id` from it (a student cannot name another room). `location_type = 'common_area'` needs no allocation, so approved students without a room can still report. The client chooses only the type, the detail text, title, description, category and priority.
- **Indexes** `ix_complaints_student (student_user_id, created_at DESC)`; `ix_complaints_queue (status, priority, created_at)`; partial `ix_complaints_room (room_id) WHERE room_id IS NOT NULL`; partial `ix_complaints_block (block_id) WHERE block_id IS NOT NULL`; UNIQUE `reference_no`.
- **State machine** (service, under `SELECT ... FOR UPDATE` on the complaint):

| From | To | Actor | Mandatory | Assignment effect |
|------|----|-------|-----------|-------------------|
| submitted | under_review | admin | | none |
| submitted, under_review | assigned | admin | | new assignment (ends none) |
| submitted, under_review, assigned | rejected (D4) | admin | **reason** | ends the open assignment, if any |
| assigned | accepted | current assignee | | sets `accepted_at` |
| assigned, accepted, in_progress | assigned (reassign) | admin | | ends open row, inserts new row |
| accepted | in_progress | current assignee | | sets `started_at` |
| in_progress | completed | current assignee | **completion note** (`complaint_updates`) | none |
| completed | closed | admin | | none |
| completed | in_progress (rework) | admin | **rework note** | none; same assignee continues |
| closed | under_review (reopen, D3) | admin | **reason** | ends the open assignment (`end_note` = reason); warden re-assigns, optionally to the same person |
| rejected | none (terminal) | | | |

  Rejection is therefore allowed only while work has not been accepted. Progress updates are allowed in `in_progress`. The CHECKs above stop impossible field combinations; the legal moves live in one service-level transition table that is unit-tested.

### 5.2 `complaint_assignments`
Every assignment ever made; the open row (`ended_at IS NULL`) is the **only active assignment**.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| complaint_id | bigint | NO | FK complaints RESTRICT |
| staff_user_id | bigint | NO | FK staff_profiles(user_id) RESTRICT |
| assigned_by | bigint | NO | FK users (admin) |
| assigned_at | timestamptz | NO | `now()` |
| instructions | text | YES | warden dispatch note: staff + admin only, **never students** |
| accepted_at | timestamptz | YES | |
| started_at | timestamptz | YES | |
| ended_at | timestamptz | YES | set on reassignment, rejection or reopen |
| ended_by | bigint | YES | FK users |
| end_note | text | YES | |

- **Database constraint for "one active assignment":** partial unique index `CREATE UNIQUE INDEX uq_assign_one_active ON complaint_assignments (complaint_id) WHERE ended_at IS NULL;`. Two concurrent assign requests cannot both leave an open row; the loser gets a unique violation (409/retry). The service also takes the complaint row lock first.
- **CHECK** `accepted_at IS NULL OR accepted_at >= assigned_at`; `started_at IS NULL OR (accepted_at IS NOT NULL AND started_at >= accepted_at)`; `ended_at IS NULL OR ended_at >= assigned_at`; `(ended_at IS NULL) = (ended_by IS NULL)`.
- **Indexes** `ix_assign_complaint (complaint_id, assigned_at)`; `ix_assign_staff_active (staff_user_id) WHERE ended_at IS NULL` (staff task list).
- Staff may read a complaint **only while they hold its open assignment** (a closed complaint keeps its open assignment until reopened, so finished work stays visible to the staff member who did it). Reassigned or rejected-out staff lose access immediately. Staff writes additionally require the matching state in the table above.
- Runtime role may `UPDATE` only `(accepted_at, started_at, ended_at, ended_by, end_note)`; the assignee, assigner and instructions are immutable once created.

### 5.3 `complaint_updates`
Append-only staff narrative, **student-visible**.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| complaint_id | bigint | NO | FK |
| assignment_id | bigint | NO | FK complaint_assignments |
| author_user_id | bigint | NO | FK users |
| update_type | varchar(12) | NO | `progress` / `completion` |
| body | text | NO | non-blank, <= 4000 |
| created_at | timestamptz | NO | |

CHECK `update_type IN ('progress','completion')`, `btrim(body) <> ''`. Index `(complaint_id, created_at)`. A rework yields a later `completion`; nothing is overwritten.

### 5.4 `complaint_internal_notes`
Admin-only private notes.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| complaint_id | bigint | NO | FK |
| author_user_id | bigint | NO | FK users (admin; service) |
| body | text | NO | non-blank, <= 4000 |
| created_at | timestamptz | NO | |

Append-only; index `(complaint_id, created_at)`.

**Keeping private notes out of student/staff queries** (defence in depth, not one control):
1. *Structural:* separate table. There is no `relationship()`/backref from `Complaint` to the notes model, so lazy loading or serialising a complaint object cannot reach them.
2. *Code boundary:* the notes model and repository live in an admin-only module; student and staff services may not import it (a unit test scans imports and fails the build on a violation).
3. *Explicit output schemas:* student and staff responses are built from explicit field lists (never `to_dict()` of an entity), so `instructions` (staff/admin only) and note content cannot leak by accident.
4. *Never copied:* note text is never placed in `complaint_history.note`, notifications, emails or audit metadata (only the note id/length).
5. *Tests:* seed a unique marker string in a note and assert it is absent from every student and staff endpoint, notification and history response; assert the notes table is queried only by admin routes.

### 5.5 `complaint_history`
Append-only ledger written in the same transaction as the change.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| complaint_id | bigint | NO | FK |
| actor_user_id | bigint | YES | FK users; NULL only for system events |
| action | varchar(24) | NO | see CHECK |
| from_status | varchar(12) | YES | NULL for `submitted` |
| to_status | varchar(12) | NO | |
| note | text | YES | **student-visible** remark; private remarks go to internal notes |
| assignment_id | bigint | YES | FK, for assign/reassign/accept/start and for assignments ended by reject/reopen |
| update_id | bigint | YES | FK complaint_updates (avoids duplicating text) |
| created_at | timestamptz | NO | |

- **CHECK** `action IN ('submitted','review_started','assigned','reassigned','accepted','work_started','progress_updated','completed','returned_for_rework','closed','rejected','reopened')`; both status columns within the status set; **`action NOT IN ('returned_for_rework','rejected','reopened') OR (note IS NOT NULL AND btrim(note) <> '')`** (reasons are mandatory at the database level).
- **Index** `ix_chist_complaint (complaint_id, created_at, id)`.
- A reopen writes one `reopened` row (from `closed` to `under_review`, with the reason) and, in the same transaction, ends the open assignment (its `end_note` repeats the reason). Together with `audit_logs` (`complaint.reopened`) this gives the complete history required by D3.

---

## 6. Module D - Fine management

### 6.1 `fines`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| reference_no | varchar(20) | NO | `FIN-2026-00012` via `fine_ref_seq` |
| student_user_id | bigint | NO | FK student_profiles |
| room_id | bigint | YES | room at issue time (snapshot) |
| category | varchar(80) | YES | optional free text |
| description | text | NO | mandatory incident description, <= 5000 |
| amount_inr | numeric(12,2) | NO | > 0 |
| issue_date | date | NO | |
| due_date | date | NO | |
| issued_by | bigint | NO | FK users; **from the authenticated admin session** |
| status | varchar(10) | NO | `pending` (default), `disputed`, `paid`, `waived`, `cancelled` |
| paid_at | timestamptz | YES | |
| resolved_by | bigint | YES | FK users (waive/cancel) |
| resolved_at | timestamptz | YES | |
| resolution_reason | text | YES | mandatory for waive/cancel |
| version | integer | NO | `1` |
| created_at / updated_at | timestamptz | NO | |

- **CHECK** `status IN (...)`; `amount_inr > 0`; `due_date >= issue_date`; `btrim(description) <> ''`; `(status = 'paid') = (paid_at IS NOT NULL)`; `(status IN ('waived','cancelled')) = (resolution_reason IS NOT NULL AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)`; `resolution_reason IS NULL OR btrim(resolution_reason) <> ''`.
- **Derived:** *overdue* = `status = 'pending' AND due_date < current_date_IST`. A fine paid after its due date is simply `paid` (lateness is visible from `payments.verified_at` vs `due_date`); lateness never triggers any refund logic.
- **Immutability:** `student_user_id`, `amount_inr`, `issue_date`, `issued_by`, `description`, `reference_no` never change after issue; the runtime role's column grant omits them (section 12). Mistakes are fixed by cancel + re-issue.
- **Indexes** `ix_fines_student (student_user_id, created_at DESC)`; `ix_fines_status_due (status, due_date)`; UNIQUE `reference_no`.
- **Transitions:** `pending -> disputed` (student); `disputed -> waived` (dispute approved) or `disputed -> pending` (rejected); `pending -> paid` (only through a verified `payments` row for the full amount); `pending|disputed -> waived|cancelled` (admin, reason). `paid`, `waived`, `cancelled` are terminal. Starting a payment attempt requires `pending`.
- **Constraint triggers:**
  - **T2** (bidirectional deferred constraint triggers `DEFERRABLE INITIALLY DEFERRED`, evaluated at `COMMIT`):
    - **T2a** (on `fines` `AFTER INSERT OR UPDATE OF status`): a fine with `status = 'paid'` must have a corresponding row in `payments` (`EXISTS (SELECT 1 FROM public.payments WHERE fine_id = NEW.id)`).
    - **T2b** (on `payments` `AFTER INSERT`): a verified payment row requires its parent `fines.status = 'paid'` and, when `NEW.payment_attempt_id IS NOT NULL`, its linked `payment_attempts.status = 'succeeded'`. Together, **T2a + T2b** guarantee at commit time that a fine is `paid` if and only if a verified `payments` row exists for it.
  - **T3** (`BEFORE INSERT` on `payment_attempts` and `payments`): acquires `SELECT amount_inr FROM public.fines WHERE id = NEW.fine_id FOR SHARE` and requires `NEW.amount_inr = fines.amount_inr` and `NEW.currency = 'INR'` (the full-payment-only rule of D6, deliberately isolated so supporting partial payments later only requires dropping T3 and `uq_payments_fine`, section 7.4).

### 6.2 `fine_disputes`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| fine_id | bigint | NO | FK fines |
| raised_by | bigint | NO | FK student_profiles; must equal the fine's student (service) |
| reason | text | NO | written dispute, <= 4000 |
| status | varchar(10) | NO | `open` / `approved` / `rejected` |
| decided_by | bigint | YES | FK users (admin) |
| decided_at | timestamptz | YES | |
| decision_reason | text | YES | mandatory for approve and reject |
| created_at | timestamptz | NO | |

UNIQUE `uq_fine_disputes_fine_id (fine_id)` (one dispute per fine, A2). CHECK `status IN (...)`; `btrim(reason) <> ''`; `(status = 'open') = (decided_by IS NULL AND decided_at IS NULL AND decision_reason IS NULL)`; `decision_reason IS NULL OR btrim(decision_reason) <> ''`. Approve -> fine `waived` using the decision reason; reject -> fine back to `pending` (matches the mock).

### 6.3 `fine_history`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| fine_id | bigint | NO | FK |
| actor_user_id | bigint | YES | NULL for gateway-driven events |
| action | varchar(24) | NO | `issued`, `dispute_submitted`, `dispute_approved`, `dispute_rejected`, `payment_attempted`, `payment_verified`, `manual_payment_recorded`, `payment_needs_review`, `waived`, `cancelled` |
| from_status / to_status | varchar(10) | YES / NO | |
| note | text | YES | student-visible |
| payment_id | bigint | YES | FK payments |
| payment_attempt_id | bigint | YES | FK payment_attempts |
| dispute_id | bigint | YES | FK fine_disputes |
| created_at | timestamptz | NO | |

CHECK on `action`; `action NOT IN ('dispute_approved','dispute_rejected','waived','cancelled') OR (note IS NOT NULL AND btrim(note) <> '')`. Index `(fine_id, created_at, id)`.

---

## 7. Module E - Payments (Razorpay-ready, not integrated)

Rev 2 separates **attempts** (what the student tried, any outcome, mutable status) from **payments** (money confirmed by the server, immutable). A fine is `paid` only if a `payments` row exists for it.

### 7.1 `payment_attempts`
One row per gateway checkout (one Razorpay order).

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| public_id | uuid | NO | `gen_random_uuid()`; also the gateway `receipt` |
| fine_id | bigint | NO | FK fines RESTRICT |
| initiated_by | bigint | NO | FK users (the student) |
| amount_inr | numeric(12,2) | NO | equals the fine amount (T3) |
| currency | char(3) | NO | `'INR'` |
| gateway_order_id | varchar(64) | YES | Razorpay `order_...`; NULL until the order exists |
| gateway_payment_id | varchar(64) | YES | Razorpay `pay_...` of the captured payment |
| payment_method | varchar(20) | YES | `upi`, `card`, `netbanking`, `wallet`, `other` as reported |
| status | varchar(18) | NO | `created`, `processing`, `succeeded`, `captured_unapplied`, `failed`, `cancelled` |
| verified_at | timestamptz | YES | when the server verified a capture |
| failure_code | varchar(60) | YES | |
| failure_reason | varchar(255) | YES | |
| created_at / updated_at | timestamptz | NO | |

- **Statuses:** `created` (row exists) -> `processing` (gateway reports an attempt) -> `succeeded` (verified capture applied: a `payments` row exists) | `failed` | `cancelled` (superseded, or the fine was waived/cancelled/disputed). `captured_unapplied` = the server verified a real capture that could **not** be applied to the fine (fine no longer `pending`, or already paid by another attempt). It is a neutral "needs admin attention" state, **not** a refund classification (D6, ADR-018).
- **UNIQUE** `public_id`; **`uq_payment_attempts_id_fine (id, fine_id)`** (target of the composite FK from `payments` so an attempt can never be linked to a payment for a different fine); partial UNIQUE `gateway_order_id WHERE NOT NULL`; partial UNIQUE `gateway_payment_id WHERE NOT NULL`.
- **Partial UNIQUE** `uq_attempt_one_open (fine_id) WHERE status IN ('created','processing')` - one open attempt per fine (double clicks cannot create parallel orders). Starting a new attempt first cancels stale open ones in the same transaction.
- **CHECK** `status IN (...)`; `amount_inr > 0`; `currency = 'INR'`; `(status IN ('succeeded','captured_unapplied')) = (verified_at IS NOT NULL)`; `status NOT IN ('succeeded','captured_unapplied') OR (gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL)`.
- **Indexes** `ix_attempts_fine (fine_id, created_at)`; `ix_attempts_status_open (status) WHERE status IN ('created','processing')`.
- A cancelled or failed attempt can still become `succeeded`/`captured_unapplied` if the gateway later proves a capture for its order (the money is real regardless of our local label).

### 7.2 `payments`
Verified payments only. Immutable financial record (SELECT + INSERT only).

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| public_id | uuid | NO | `gen_random_uuid()` |
| fine_id | bigint | NO | FK fines RESTRICT |
| payment_attempt_id | bigint | YES | Composite FK `(payment_attempt_id, fine_id) -> payment_attempts(id, fine_id)` RESTRICT; NULL for manual records |
| channel | varchar(10) | NO | `razorpay` / `manual` |
| amount_inr | numeric(12,2) | NO | > 0; equals the fine amount (T3) |
| currency | char(3) | NO | `'INR'` |
| gateway_order_id | varchar(64) | YES | |
| gateway_payment_id | varchar(64) | YES | |
| payment_method | varchar(20) | YES | `upi`, `card`, `netbanking`, `wallet`, `cash`, `bank_transfer`, `other` |
| verification_method | varchar(14) | NO | `webhook`, `api_fetch`, `manual_entry` |
| verified_at | timestamptz | NO | |
| receipt_number | varchar(24) | NO | `RCP-2026-00841` via `receipt_seq` default |
| recorded_by | bigint | YES | FK users; admin for manual records |
| manual_reference | varchar(120) | YES | receipt/transaction note |
| created_at | timestamptz | NO | `now()` |

- **FK** `fine_id -> fines(id)` RESTRICT; **composite FK** `fk_payments_attempt_fine (payment_attempt_id, fine_id) -> payment_attempts(id, fine_id) MATCH SIMPLE ON DELETE RESTRICT` (guarantees that a `payment_attempt` created for one fine can **never** be reused or attached to a `payments` row for another fine); `recorded_by -> users(id)` RESTRICT.
- **UNIQUE** `public_id`; `receipt_number`; **`uq_payments_fine (fine_id)`** (full payments only: one payment per fine); **`uq_payments_attempt (payment_attempt_id) WHERE payment_attempt_id IS NOT NULL`** (an attempt can produce at most one payment); partial `gateway_payment_id WHERE NOT NULL`.
- **CHECK**
  - `channel IN ('razorpay','manual')`; `amount_inr > 0`; `currency = 'INR'`
  - `channel <> 'razorpay' OR (payment_attempt_id IS NOT NULL AND gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL AND verification_method IN ('webhook','api_fetch') AND recorded_by IS NULL)`
  - `channel <> 'manual' OR (payment_attempt_id IS NULL AND gateway_order_id IS NULL AND gateway_payment_id IS NULL AND verification_method = 'manual_entry' AND recorded_by IS NOT NULL AND manual_reference IS NOT NULL AND btrim(manual_reference) <> '')`
- **Index** `ix_payments_verified_at (verified_at)`.
- **No secrets stored anywhere in the payment tables:** no card/UPI data, no gateway key secret, webhook secret or signature values; `gateway_*` ids are references, not credentials. Keys live in environment variables only.

### 7.3 `payment_events`
Append-only log of everything the gateway or browser told us; the idempotency anchor.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| payment_attempt_id | bigint | YES | FK payment_attempts; NULL for events about an unknown order |
| source | varchar(16) | NO | `webhook`, `client_callback`, `server_verify`, `system`, `admin` |
| event_type | varchar(60) | NO | e.g. `payment.captured`, `order.paid`, `payment.failed` |
| gateway_event_id | varchar(100) | YES | Razorpay `X-Razorpay-Event-Id` |
| signature_valid | boolean | YES | HMAC result where applicable |
| outcome | varchar(14) | NO | `applied`, `duplicate`, `ignored`, `rejected`, `error`, `needs_review` |
| payload | jsonb | NO | sanitised allow-list (ids, status, amount, method); no contact/email/VPA/card fields |
| created_at | timestamptz | NO | |

Partial UNIQUE `uq_payment_events_gateway_event (gateway_event_id) WHERE gateway_event_id IS NOT NULL`; CHECK `source`/`outcome` lists, `jsonb_typeof(payload) = 'object'`; index `(payment_attempt_id, created_at)`.

### 7.4 Payment rules, atomicity, lock order and transaction order

**Never trust the browser.** The checkout success callback only triggers a server-side check (and is logged as `source = 'client_callback'`, changing nothing). A fine becomes `paid` only through server-verified evidence: (a) a webhook whose HMAC over the **raw body** validates, or (b) a server-to-server fetch of the order/payment from Razorpay. A checkout signature alone is never sufficient (it may trigger (b)).

**Atomicity & invariant guarantees (verified across service + database constraints):**
1. *Verified payment insertion and fine status update happen in one transaction:* Both the `INSERT INTO payments` and `UPDATE fines SET status = 'paid'` execute in the same database transaction.
2. *Failed transactions leave no partially paid fine:* Any exception, constraint violation, or trigger failure rolls back the entire transaction. At `COMMIT`, deferred constraint triggers **T2a** (on `fines`) and **T2b** (on `payments`) enforce the bidirectional invariant: `fines.status = 'paid'` iff a row in `payments` exists for that `fine_id` (and for gateway payments, its `payment_attempts.status = 'succeeded'`).
3. *Duplicate webhook events cannot create duplicate payment records:* Prevented by four layers: (i) fixed-order row locks (`fines` `FOR UPDATE` -> `payment_attempts` `FOR UPDATE`); (ii) state idempotency check (`payment_attempts.status IN ('succeeded','captured_unapplied')` exits without inserting `payments`); (iii) `uq_payments_fine (fine_id)`, `uq_payments_attempt (payment_attempt_id)`, and `uq_payments_gateway_payment (gateway_payment_id)`; and (iv) `uq_payment_events_gateway_event (gateway_event_id)`.
4. *A payment attempt cannot be reused for another fine:* `payment_attempts.fine_id` is `NOT NULL` and excluded from `hostelcare_app`'s column-level `UPDATE` grant. `payments` enforces the composite foreign key `(payment_attempt_id, fine_id) REFERENCES payment_attempts (id, fine_id)` plus `uq_payments_attempt (payment_attempt_id)`.
5. *A fine cannot be marked paid without a valid verified payment:* Enforced at `COMMIT` by deferred trigger **T2a** on `fines`.
6. *Exact amount and currency match the original fine:* Enforced at the gateway boundary (`gateway_currency == 'INR'` and `gateway_amount_paise == int(fine.amount_inr * 100)`) and at the database level on every `INSERT` into `payment_attempts` and `payments` by `CHECK (currency = 'INR' AND amount_inr > 0)` and trigger **T3** (`NEW.amount_inr = fines.amount_inr` under `FOR SHARE` on `fines`).

**Expected lock order (deadlock-free):**
Always acquire row locks in parent-to-child order: **`fines` (`FOR UPDATE` or `FOR SHARE`) -> `payment_attempts` (`FOR UPDATE`)**. Never lock `payments` or `payment_events` (both are append-only `SELECT, INSERT` tables). Never perform external HTTP/gateway calls while holding database row locks.

**Expected transaction statement order:**
- **Flow A — Initiate payment attempt (student):**
  1. *Tx 1:* `SELECT ... FROM fines WHERE id = :fine_id FOR UPDATE;` (require `status = 'pending'`).
  2. `UPDATE payment_attempts SET status = 'cancelled', updated_at = now() WHERE fine_id = :fine_id AND status IN ('created','processing');`
  3. `INSERT INTO payment_attempts (fine_id, initiated_by, amount_inr, currency, status) VALUES (:fine_id, :student_id, :fine_amount, 'INR', 'created');` (Trigger **T3** verifies `amount_inr = fines.amount_inr`; `uq_attempt_one_open` ensures single open attempt).
  4. `INSERT INTO fine_history (fine_id, actor_user_id, action, from_status, to_status, payment_attempt_id) ...;`
  5. `COMMIT;` (releases locks before network I/O).
  6. *Outside transaction:* Call Razorpay Orders API with `receipt = attempt.public_id`, `amount = int(amount_inr * 100)`, `currency = 'INR'`.
  7. *Tx 2:* `UPDATE payment_attempts SET gateway_order_id = :order_id, updated_at = now() WHERE id = :attempt_id;` `COMMIT;`
- **Flow B — Idempotent webhook / server-side verification (one atomic transaction):**
  1. Validate the HMAC over the **raw request body** before opening the business transaction; if invalid, write a `payment_events` row (`outcome = 'rejected'`, `signature_valid = false`) in a standalone short transaction and return HTTP 400.
  2. Resolve `attempt_id` and `fine_id` by `gateway_order_id` (`SELECT id, fine_id FROM payment_attempts WHERE gateway_order_id = :order_id`); if unknown, write `payment_events` (`outcome = 'ignored'`) and return HTTP 200.
  3. **Lock 1:** `SELECT id, status, amount_inr, version FROM fines WHERE id = :fine_id FOR UPDATE;`
  4. **Lock 2:** `SELECT id, fine_id, status, amount_inr, currency FROM payment_attempts WHERE id = :attempt_id FOR UPDATE;`
  5. Verify gateway payload: captured state, `currency == 'INR'`, and `amount_paise == int(fines.amount_inr * 100)`.
  6. **State-based idempotency:** If `payment_attempts.status IN ('succeeded','captured_unapplied')`, insert `payment_events` (`outcome = 'duplicate'` or `'ignored'`) and `COMMIT` (or if `gateway_event_id` already exists in `payment_events`, the unique index violation rolls back cleanly and returns HTTP 200).
  7. **Apply in exact statement order:**
     - *Case 1 (`fines.status = 'pending'` and no existing payment):*
       (a) `INSERT INTO payments (fine_id, payment_attempt_id, channel, amount_inr, currency, gateway_order_id, gateway_payment_id, payment_method, verification_method, verified_at) ...;` (checked immediately by composite FK, `uq_payments_fine`, `uq_payments_attempt`, and Trigger **T3**).
       (b) `UPDATE payment_attempts SET status = 'succeeded', gateway_payment_id = :pay_id, payment_method = :method, verified_at = :ts, updated_at = now() WHERE id = :attempt_id;`
       (c) `UPDATE fines SET status = 'paid', paid_at = :ts, version = version + 1, updated_at = now() WHERE id = :fine_id;`
       (d) `INSERT INTO fine_history (..., action = 'payment_verified', from_status = 'pending', to_status = 'paid', payment_id = :pay_row_id, payment_attempt_id = :attempt_id);`
       (e) `INSERT INTO notifications ...;`
       (f) `INSERT INTO audit_logs (action = 'payment.verified', ...);`
       (g) `INSERT INTO payment_events (..., gateway_event_id = :evt_id, outcome = 'applied');`
     - *Case 2 (fine is no longer `pending` — e.g. waived, cancelled, disputed, or already paid by another attempt):*
       (a) `UPDATE payment_attempts SET status = 'captured_unapplied', gateway_payment_id = :pay_id, payment_method = :method, verified_at = :ts, updated_at = now() WHERE id = :attempt_id;`
       (b) `INSERT INTO fine_history (..., action = 'payment_needs_review', from_status = fines.status, to_status = fines.status, payment_attempt_id = :attempt_id);`
       (c) `INSERT INTO notifications` (to admins);
       (d) `INSERT INTO audit_logs (action = 'payment.needs_review', ...);`
       (e) `INSERT INTO payment_events (..., gateway_event_id = :evt_id, outcome = 'needs_review');`
       (**Nothing is classified as a refund automatically.**)
  8. `COMMIT;` — Deferred triggers **T2a** and **T2b** fire at commit and confirm `fines.status = 'paid'`, `payments` row existence, and `payment_attempts.status = 'succeeded'`.
- **Flow C — Manual/offline payment (admin, one atomic transaction):**
  1. **Lock 1:** `SELECT id, status, amount_inr, version FROM fines WHERE id = :fine_id FOR UPDATE;` (require `pending`, or `disputed` with explicit admin note).
  2. **Lock 2:** `UPDATE payment_attempts SET status = 'cancelled', updated_at = now() WHERE fine_id = :fine_id AND status IN ('created','processing');`
  3. `INSERT INTO payments (fine_id, payment_attempt_id, channel, amount_inr, currency, payment_method, verification_method, verified_at, recorded_by, manual_reference) VALUES (:fine_id, NULL, 'manual', :fine_amount, 'INR', :method, 'manual_entry', now(), :admin_id, :ref);` (Trigger **T3** verifies exact amount and currency).
  4. `UPDATE fines SET status = 'paid', paid_at = now(), version = version + 1, updated_at = now() WHERE id = :fine_id;`
  5. `INSERT INTO fine_history (..., action = 'manual_payment_recorded', from_status = :old_status, to_status = 'paid', payment_id = :pay_row_id);`
  6. `INSERT INTO notifications ...;`
  7. `INSERT INTO audit_logs (action = 'payment.manual_recorded', ...);`
  8. `COMMIT;` — Deferred triggers **T2a** and **T2b** verify the committed state.

**Waive/cancel/dispute while an attempt is open:** open attempts become `cancelled` locally; if the gateway later proves a capture, step 5 yields `captured_unapplied`. No network call is ever made while holding row locks (create the attempt row, commit, call Razorpay, then update it).

**Late payment:** paying after `due_date` is an ordinary successful payment; no refund state exists for it.

**Future extension (not built, architecture stays open - D6):**
- *Partial payments:* drop `uq_payments_fine` and T3; add `fines.status = 'partially_paid'` and compute the balance as `amount_inr - SUM(payments.amount_inr)`; drop the "amount equals fine" check in the attempt creation service. `payment_attempts` and `payment_events` need no change.
- *Refunds:* add a `refunds` table (`payment_id` FK, `amount_inr`, `reason`, `status`, `gateway_refund_id`, `requested_by`, audit) and resolve `captured_unapplied` attempts through it. Payments stay immutable; a refund is a new row, never an edit.

---

## 8. Module F - Notifications

### 8.1 `notifications`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| public_id | uuid | NO | `gen_random_uuid()` |
| recipient_user_id | bigint | NO | FK users |
| category | varchar(14) | NO | `complaint`, `fine`, `dispute`, `payment`, `registration`, `system` |
| event_type | varchar(40) | NO | e.g. `complaint_assigned`, `complaint_progress`, `rework_requested`, `complaint_reopened`, `fine_issued`, `dispute_decided`, `account_approved`, `account_rejected`, `account_reactivated`, `payment_verified`, `payment_needs_review` |
| title | varchar(150) | NO | |
| message | text | NO | <= 1000; **never contains internal notes** |
| entity_type | varchar(20) | YES | `complaint`, `fine`, `payment`, `student` |
| entity_ref | varchar(40) | YES | `reference_no` for deep links (no polymorphic FK) |
| read_at | timestamptz | YES | NULL = unread |
| created_at | timestamptz | NO | |

CHECK `category IN (...)`, `btrim(title) <> ''`, `(entity_type IS NULL) = (entity_ref IS NULL)`. Indexes `ix_notif_recipient (recipient_user_id, created_at DESC)`; partial `ix_notif_unread (recipient_user_id) WHERE read_at IS NULL`. Created in the same transaction as the triggering event. Read/mark-read are always `WHERE recipient_user_id = :me`; runtime role may `UPDATE (read_at)` only. Notifications are in-app only; the optional email channel uses the provider-independent mailer (3.4) and is not stored.

---

## 9. Module G - Audit and security

### 9.1 `audit_logs`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| id | bigint identity | NO | PK |
| occurred_at | timestamptz | NO | `now()` |
| actor_user_id | bigint | YES | FK users; NULL for unauthenticated/system events |
| actor_role | varchar(10) | YES | snapshot |
| action | varchar(60) | NO | dotted catalogue |
| target_type | varchar(30) | YES | `user`, `complaint`, `fine`, `payment_attempt`, `payment`, `room_allocation`, ... |
| target_id | varchar(40) | YES | reference_no, public_id or id as text |
| metadata | jsonb | NO | `{}`; allow-listed non-secret details |
| request_id | varchar(64) | YES | matches the existing `X-Request-ID` |
| ip_address | inet | YES | |

- **CHECK** `jsonb_typeof(metadata) = 'object'`; `btrim(action) <> ''`; `(target_type IS NULL) = (target_id IS NULL)`.
- **Indexes** `ix_audit_occurred (occurred_at DESC)`; `ix_audit_actor (actor_user_id, occurred_at DESC)`; `ix_audit_target (target_type, target_id)`; `ix_audit_action_ip (action, ip_address, occurred_at DESC) WHERE ip_address IS NOT NULL` (rate limiting).
- **Never** in `metadata`: passwords, hashes, reset tokens, payment secrets, full webhook payloads, note text, email addresses of unauthenticated requesters.
- **Catalogue (initial):** `auth.login_failed`, `auth.login_locked`, `auth.password_changed`, `auth.reset_requested`, `auth.reset_triggered`, `auth.reset_redeemed`, `auth.reset_invalid`, `student.registered`, `student.approved`, `student.rejected`, `student.reactivated`, `user.suspended`, `user.reactivated`, `staff.created`, `staff.updated`, `room.created`, `room.updated`, `allocation.created`, `allocation.ended`, `complaint.assigned`, `complaint.reassigned`, `complaint.closed`, `complaint.returned`, `complaint.rejected`, `complaint.reopened`, `complaint.internal_note_added`, `fine.issued`, `fine.waived`, `fine.cancelled`, `dispute.approved`, `dispute.rejected`, `payment.manual_recorded`, `payment.verified`, `payment.needs_review`.
- **Atomicity:** admin-action audit rows are inserted in the same transaction as the action (failure rolls the action back). Events that must survive rollback (failed login, invalid reset token, rejected webhook signature) use their own short transaction.
- **Audit vs history:** per-entity ledgers (`complaint_history`, `fine_history`) are rendered to users; `audit_logs` is the admin-only cross-system trail. Admin actions legitimately write both.

---

## 10. Relationships

**One-to-one:** `users`-`student_profiles` (PK = FK, composite FK to role); `users`-`staff_profiles`; `fines`-`fine_disputes` (UNIQUE `fine_id`); `fines`-`payments` (UNIQUE `fine_id`, full payments only); `payment_attempts`-`payments` (UNIQUE, optional).

**One-to-many:** `blocks`->`rooms`; `rooms`->`room_allocations`; `student_profiles`->`room_allocations`; `student_profiles`->`complaints`; `rooms`->`complaints` (room complaints); `blocks`->`complaints` (common-area complaints); `complaints`->`complaint_assignments`/`updates`/`internal_notes`/`history`; `staff_profiles`->`complaint_assignments`; `complaint_assignments`->`complaint_updates`; `student_profiles`->`fines`; `fines`->`fine_history`/`payment_attempts`; `payment_attempts`->`payment_events`; `users`->`password_reset_tokens`/`notifications`/`audit_logs` and every `*_by`/`actor_user_id` column.

**Many-to-many (through payload-carrying tables):** students <-> rooms via `room_allocations`; complaints <-> staff via `complaint_assignments`.

**Delete/update behaviour:** every FK is `ON DELETE RESTRICT ON UPDATE NO ACTION`; primary keys are immutable. Retiring = status/flag change. The runtime role has no DELETE privilege on business tables (section 12).

---

## 11. Transactions, concurrency and history

| Operation | Rows written atomically | Locks / guard |
|-----------|-------------------------|---------------|
| Registration | users, student_profiles, audit, admin notifications | UNIQUE email/roll number -> generic 409 |
| Approve / reject / reactivate student | users.status, student_profiles review fields, optional allocation, notification, audit (with reason) | `FOR UPDATE` user; require expected current status |
| Allocate / transfer / end | update old allocation then insert new, audit | `FOR UPDATE` room (+ student); exclusion constraints + T1 backstop |
| Submit complaint | complaints, history, admin notifications | location rules; student and room from session |
| Review / assign / reassign | complaint status, end old assignment, insert new, history, notifications, audit | `FOR UPDATE` complaint; `uq_assign_one_active` |
| Accept / start / progress / complete | assignment timestamps, status, update, history, notifications | `FOR UPDATE` complaint; actor = open assignee |
| Close / rework / reject / reopen | status, end assignment (reject, reopen), history (reason), notifications, audit | `FOR UPDATE` complaint; transition table |
| Issue fine | fines, history, notification, audit | `issued_by` from session |
| Dispute / decide | dispute, fine status, history, notification, audit | `FOR UPDATE` fine; UNIQUE dispute |
| Waive / cancel | fine, history, open attempts -> cancelled, audit | `FOR UPDATE` fine then attempts |
| Start payment attempt | cancel stale attempts, insert attempt (`created`) -> commit -> gateway order -> update | `FOR UPDATE` fine; `uq_attempt_one_open`; no network under lock |
| Webhook / verify | payments, attempt, fine, history, notification, audit, payment_events | HMAC; fine then attempt lock; state idempotency; unique event id; `uq_payments_fine` |
| Manual payment | payments, fine, history, audit | fine lock; `uq_payments_fine` |
| Reset request / redeem | token row (+ revoke others), users, audit | conditional `UPDATE ... RETURNING`; `uq_prt_one_live` |

**Concurrency summary:** constraints decide races (duplicate registration, allocation overlap, bed double-booking, two active assignments, two payments for a fine, duplicate webhook, two live reset tokens); `FOR UPDATE` on the aggregate root serialises transitions; fixed lock order (room -> allocation; complaint -> assignment; fine -> attempt; user -> profile); `version` columns allow stale-edit rejection; READ COMMITTED throughout, no SERIALIZABLE or advisory locks; a deadlock/serialization error is retried once.

**History preservation:** reassignment adds and closes rows; transfers add rows; completion notes are rows; reopening and rework are history rows; payment attempts, events and payments are rows; registration decisions append to `audit_logs`. History and financial tables carry no UPDATE/DELETE grants; business records are retired, never deleted (D8).

---

## 12. PostgreSQL ownership and privileges (exact)

Matches `database/setup_postgres.sql` (already executed): both roles `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT`, no memberships; `hostelcare_owner` owns the `hostelcare` and `hostelcare_test` databases and their `public` schema; `PUBLIC` has no database or schema privileges (so also no `TEMP`); `hostelcare_app` has `CONNECT` and schema `USAGE` only, `CREATE` on `public` revoked; default privileges for tables and sequences revoked. The script needs no change. Grants below are issued **by each table's own migration**.

### 12.1 Ownership and role capabilities

| Capability | `hostelcare_owner` (migrations; `MIGRATION_DATABASE_URL`) | `hostelcare_app` (runtime; `DATABASE_URL`) |
|-----------|-----------------------------------------------------------|---------------------------------------------|
| Owns tables, sequences, indexes, constraints, triggers, trigger functions, extension | **yes** (migrations always run connected as this role, never via a superuser) | **no** - owns nothing |
| `CREATE`/`ALTER`/`DROP` tables, columns, constraints, indexes, triggers, functions, extensions | yes | **no** (not owner; `CREATE` on schema revoked; `CREATE EXTENSION` impossible) |
| `TRUNCATE`, `REFERENCES`, `TRIGGER` on tables | owner | **never granted** |
| Run Alembic / read or write `alembic_version` | yes (owns it) | **no privilege at all**, not even `SELECT` |
| `DELETE` | owner | **never granted on any table** (expired reset tokens are purged via owner-owned `SECURITY DEFINER` function `public.purge_expired_password_reset_tokens()`) |
| Create temporary tables | yes (owner) | no (`TEMP` not granted) |
| Bypass RLS / superuser / create roles | no | no |

The runtime application never receives the owner's credentials; the owner URL exists only for the migration command and the DB verification CLI.

### 12.2 Table privileges for `hostelcare_app`

`I` = INSERT (all columns), `S` = SELECT. `UPDATE` is **column-level**, so immutable facts cannot be rewritten even by an application bug. SQLAlchemy only emits changed columns in an `UPDATE`, which fits; tests must prove the real statements succeed.

| Table | Privileges |
|-------|-----------|
| `users` | S, I, UPDATE (email, full_name, phone, designation, password_hash, status, password_changed_at, session_version, failed_login_count, locked_until, last_login_at, updated_at) - not `id`, `public_id`, `role`, `created_by`, `created_at` |
| `student_profiles` | S, I, UPDATE (roll_number, requested_room_id, reviewed_by, reviewed_at, review_note, updated_at) |
| `staff_profiles` | S, I, UPDATE (trade, shift, updated_at) |
| `password_reset_tokens` | S, I, UPDATE (used_at, revoked_at) - **no DELETE** (cleanup is performed only via `public.purge_expired_password_reset_tokens()`) |
| `blocks` | S, I, UPDATE (name, display_order, is_active, updated_at) |
| `rooms` | S, I, UPDATE (floor, room_type, capacity, is_active, updated_at) |
| `room_allocations` | S, I, UPDATE (end_date, ended_by, end_reason) |
| `complaints` | S, I, UPDATE (category, priority, status, rejection_reason, completed_at, closed_at, version, updated_at) - not student, location, title, description, reference_no |
| `complaint_assignments` | S, I, UPDATE (accepted_at, started_at, ended_at, ended_by, end_note) |
| `fines` | S, I, UPDATE (status, paid_at, resolved_by, resolved_at, resolution_reason, version, updated_at) - not student, amount, dates, issuer, description, reference_no |
| `fine_disputes` | S, I, UPDATE (status, decided_by, decided_at, decision_reason) |
| `payment_attempts` | S, I, UPDATE (gateway_order_id, gateway_payment_id, payment_method, status, verified_at, failure_code, failure_reason, updated_at) |
| `notifications` | S, I, UPDATE (read_at) |
| **Append-only:** `complaint_updates`, `complaint_internal_notes`, `complaint_history`, `fine_history`, `payments`, `payment_events`, `audit_logs` | **S, I only** - no UPDATE, no DELETE, no TRUNCATE (`REVOKE ALL ... FROM hostelcare_app; GRANT SELECT, INSERT ...`, the pattern the setup script prescribes for audit tables) |

No other privilege (zero `DELETE` across all 20 tables, zero `TRUNCATE`/`REFERENCES`/`TRIGGER`) is granted on any table. Identity-column sequences need no grant.

### 12.3 Sequences, triggers, functions and extension (exact runtime privilege verification)

- **Custom sequences:** `complaint_ref_seq`, `fine_ref_seq`, `receipt_seq` are used by column defaults, so `GRANT USAGE ON SEQUENCE ... TO hostelcare_app` (not `SELECT`/`UPDATE`). Owned by `hostelcare_owner`.
- **Extension `btree_gist`:** created and owned by `hostelcare_owner`; no grant to `hostelcare_app` is required (4.4).
- **Trigger & function execution and permission verification under `hostelcare_app`:**

| Trigger / Function | Attached Table & Event | Owner & Security Context | Fixed `search_path` | Queries Executed Inside Function | Required `hostelcare_app` Privileges (and Why Satisfied Without Broad Grants) |
|--------------------|------------------------|--------------------------|---------------------|----------------------------------|-------------------------------------------------------------------------------|
| **T1a** (`fn_check_room_allocation`) | `room_allocations` `BEFORE INSERT OR UPDATE OF room_id, bed_number, start_date, end_date` | `hostelcare_owner`, **`SECURITY INVOKER`** (`REVOKE ALL FROM PUBLIC`) | `SET search_path = public, pg_temp` | 1. `SELECT capacity, is_active FROM public.rooms WHERE id = NEW.room_id FOR SHARE;`<br>2. (On `INSERT`): `SELECT status FROM public.users WHERE id = NEW.student_user_id;` | **SELECT:** `SELECT` on `rooms` and `users`.<br>**Row-lock UPDATE:** PostgreSQL requires `UPDATE` privilege on at least one column of `rooms` to execute `SELECT ... FOR SHARE`. `hostelcare_app` already holds column-level `UPDATE (floor, room_type, capacity, is_active, updated_at)` on `rooms` (Section 12.2). No extra grant needed. |
| **T1b** (`fn_check_room_capacity_reduction`) | `rooms` `BEFORE UPDATE OF capacity` | `hostelcare_owner`, **`SECURITY INVOKER`** (`REVOKE ALL FROM PUBLIC`) | `SET search_path = public, pg_temp` | When `NEW.capacity < OLD.capacity`:<br>`SELECT max(bed_number) FROM public.room_allocations WHERE room_id = NEW.id AND (end_date IS NULL OR end_date > (now() AT TIME ZONE 'Asia/Kolkata')::date);` | **SELECT:** `SELECT` on `room_allocations`.<br>**Row-lock UPDATE:** None needed on `room_allocations`; the `UPDATE` on `rooms` already holds an exclusive row lock on the `rooms` row, which serialises against T1a's `FOR SHARE` lock on `rooms`. |
| **T2a** (`fn_check_fine_paid_has_payment`) | `fines` `CONSTRAINT TRIGGER AFTER INSERT OR UPDATE OF status DEFERRABLE INITIALLY DEFERRED` | `hostelcare_owner`, **`SECURITY INVOKER`** (`REVOKE ALL FROM PUBLIC`) | `SET search_path = public, pg_temp` | When `NEW.status = 'paid'`:<br>`PERFORM 1 FROM public.payments WHERE fine_id = NEW.id;` | **SELECT:** `SELECT` on `payments` (already granted).<br>**Row-lock UPDATE:** None (`payments` is append-only and is not locked with `FOR SHARE`; concurrency is already serialised by `FOR UPDATE` on `fines` and `uq_payments_fine`). |
| **T2b** (`fn_check_payment_fine_state`) | `payments` `CONSTRAINT TRIGGER AFTER INSERT DEFERRABLE INITIALLY DEFERRED` | `hostelcare_owner`, **`SECURITY INVOKER`** (`REVOKE ALL FROM PUBLIC`) | `SET search_path = public, pg_temp` | 1. `SELECT status FROM public.fines WHERE id = NEW.fine_id;` (must be `'paid'`)<br>2. When `NEW.payment_attempt_id IS NOT NULL`: `SELECT status FROM public.payment_attempts WHERE id = NEW.payment_attempt_id;` (must be `'succeeded'`) | **SELECT:** `SELECT` on `fines` and `payment_attempts` (already granted).<br>**Row-lock UPDATE:** None needed inside the deferred check because the enclosing transaction already holds `FOR UPDATE` on `fines` (and `payment_attempts`). |
| **T3** (`fn_check_payment_amount_matches_fine`) | `payment_attempts` `BEFORE INSERT` & `payments` `BEFORE INSERT` | `hostelcare_owner`, **`SECURITY INVOKER`** (`REVOKE ALL FROM PUBLIC`) | `SET search_path = public, pg_temp` | `SELECT amount_inr FROM public.fines WHERE id = NEW.fine_id FOR SHARE;`<br>Verifies `NEW.amount_inr = fines.amount_inr` and `NEW.currency = 'INR'`. | **SELECT:** `SELECT` on `fines`.<br>**Row-lock UPDATE:** PostgreSQL requires `UPDATE` privilege on at least one column of `fines` for `SELECT ... FOR SHARE`. `hostelcare_app` already holds column-level `UPDATE (status, paid_at, resolved_by, resolved_at, resolution_reason, version, updated_at)` on `fines` while `fines.amount_inr` remains strictly non-updatable. |
| **`purge_expired_password_reset_tokens()`** | Standalone maintenance function (not a trigger) | `hostelcare_owner`, **`SECURITY DEFINER`** (`REVOKE ALL FROM PUBLIC; GRANT EXECUTE TO hostelcare_app`) | `SET search_path = public, pg_temp` | `DELETE FROM public.password_reset_tokens WHERE expires_at < now() - interval '24 hours' AND created_at < now() - interval '24 hours';` | **`SECURITY DEFINER` required** specifically so `hostelcare_app` holds **zero `DELETE` privileges** on `password_reset_tokens`. Takes zero parameters and hardcodes a >24-hour post-expiry predicate so active tokens and 1-hour rate-limit rows can never be deleted. |

### 12.4 `alembic_version`
Alembic creates it as `hostelcare_owner`. Because no default privileges exist, the runtime role never receives access automatically; the migration environment additionally runs `REVOKE ALL ON alembic_version FROM PUBLIC, hostelcare_app` after Alembic creates it (idempotent), and a test asserts the result.

### 12.5 Verification queries (run as `hostelcare_owner` in tests, each expected result stated)
```sql
-- 1. Nothing in public is owned by the runtime role (expect 0 rows)
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) <> 'hostelcare_owner';

-- 2. Runtime role cannot create objects or touch alembic_version (expect all false)
SELECT has_schema_privilege('hostelcare_app','public','CREATE'),
       has_table_privilege('hostelcare_app','alembic_version','SELECT'),
       has_table_privilege('hostelcare_app','alembic_version','INSERT');

-- 3. Append-only tables: no UPDATE/DELETE/TRUNCATE for the runtime role (expect 0 rows)
SELECT t, p FROM unnest(ARRAY['complaint_updates','complaint_internal_notes','complaint_history',
  'fine_history','payments','payment_events','audit_logs']) t,
  unnest(ARRAY['UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p
WHERE has_table_privilege('hostelcare_app', t, p);

-- 4. Immutable columns are not updatable (expect all false)
SELECT has_column_privilege('hostelcare_app','fines','amount_inr','UPDATE'),
       has_column_privilege('hostelcare_app','users','role','UPDATE'),
       has_column_privilege('hostelcare_app','room_allocations','bed_number','UPDATE'),
       has_column_privilege('hostelcare_app','complaints','student_user_id','UPDATE');

-- 5. Zero tables may be deleted from by the runtime role (expect 0 rows)
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND has_table_privilege('hostelcare_app', c.oid, 'DELETE');

-- 6. Sequences: USAGE only (expect the three reference sequences; no UPDATE)
SELECT c.relname, has_sequence_privilege('hostelcare_app', c.oid, 'USAGE') AS usage,
       has_sequence_privilege('hostelcare_app', c.oid, 'UPDATE') AS upd
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S' AND c.relname IN ('complaint_ref_seq','fine_ref_seq','receipt_seq');

-- 7. Functions: owned by hostelcare_owner, EXECUTE revoked from PUBLIC (expect 0 rows where public_exec is true)
SELECT p.proname, pg_get_userbyid(p.proowner) AS owner, p.prosecdef,
       has_function_privilege('public', p.oid, 'EXECUTE') AS public_exec
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname IN (
  'fn_check_room_allocation', 'fn_check_room_capacity_reduction',
  'fn_check_fine_paid_has_payment', 'fn_check_payment_fine_state',
  'fn_check_payment_amount_matches_fine', 'purge_expired_password_reset_tokens'
);
```
Behavioural tests connect as `hostelcare_app` and assert that `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, `TRUNCATE`, `UPDATE audit_logs`, `DELETE FROM complaints`, `DELETE FROM password_reset_tokens`, and `SELECT * FROM alembic_version` all fail with permission errors, while `SELECT public.purge_expired_password_reset_tokens()` removes only tokens with `expires_at < now() - interval '24 hours'` and leaves active and recent tokens untouched.

Row-Level Security remains unused (ADR-011).

---

## 13. Frontend-to-database mapping (for later phases)

| Frontend concept | Database |
|------------------|----------|
| student `status` pending/active/Rejected | `users.status` (`rejected` reactivates through `pending`) |
| `rollNumber`, `room` at registration | `student_profiles.roll_number`, `requested_room_id` |
| `rooms[].students`, `occupied` | derived from `room_allocations` (active today) |
| complaint form (room only) | `location_type`; common-area option added later in the UI |
| complaint `status` labels | snake_case; `Resolved` -> `completed` |
| `assignedStaff*`, `previousAssignments` | `complaint_assignments` |
| `internalNotes` | `complaint_internal_notes` |
| complaint `history[]` | `complaint_history` + `complaint_updates` |
| fine `Overdue` | derived |
| fine `dispute`, `history[]` | `fine_disputes`, `fine_history` |
| fine `payment` (mock Razorpay ids, receipt) | `payment_attempts` + `payments` |
| staff and student notification lists | `notifications` |
| `auditLogs` | `audit_logs` |
| staff `Active / On Duty` | `users.status` |

---

## 14. Assumptions and resolved operational decisions

Assumptions retained: A2 one dispute per fine (rejected is final); A5 login by email (roll number optional, service-level); A6 a fine is paid once, in full; A8 student reactivation is `rejected -> pending` followed by normal approval (two admin steps, both audited); A9 a verified capture for a fine that is no longer `pending` becomes `captured_unapplied`, notifies admins, and waits for manual handling; A11 staff and admin accounts start with an unusable password hash (`!`) and get their first password through the 30-minute reset email.
Resolved by the owner: A1 (one admin role), A3 (replaced by D5), A4 (confirmed, D4).

Confirmed operational defaults (U1-U4 resolved in final verification):
- **U1 (Rate limits, confirms A10):** Password reset rate limits are 3 requests per user per hour; 10 requests per IP per hour; 10 invalid redemption attempts per IP per 15 minutes (counted via `password_reset_tokens` and `audit_logs`).
- **U2 (Complaint reopen assignment behaviour, confirms A7):** On complaint reopening (`closed -> under_review`), close the previous open assignment (`ended_at = now()`, `ended_by = admin_id`, `end_note = reopen_reason`) and allow a new assignment to be created.
- **U3 (Email backend configuration):** Local development/test email backend defaults to `console` (`MAIL_BACKEND=console`). Production email is configurable via `MAIL_*` environment variables (`MAIL_BACKEND=smtp`).
- **U4 (`btree_gist` verification):** Verify `btree_gist` installation (`CREATE EXTENSION IF NOT EXISTS btree_gist;`) and trusted extension status as `hostelcare_owner` during the first Phase 3B migration against `hostelcare_test`.

See [TODO.md](TODO.md) for the Phase 3B implementation checklist.
