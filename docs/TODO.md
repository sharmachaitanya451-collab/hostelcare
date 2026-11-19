# Outstanding Tasks

## Awaiting owner
- [ ] Approve Phase 0 results
- [ ] Provide PostgreSQL admin access for creating `hostelcare` / `hostelcare_test` and the app role
- [ ] Hostel name, block and room naming, official student list (if any)
- [ ] Production hosting (not blocking until Phase 4)

## Phase 1 – Database and auth
- [ ] Create databases and least-privilege role; set `DATABASE_URL`
- [ ] Initial migration; DB test fixtures (rollback per test)
- [ ] Users, student profiles, rooms; registration with pending status
- [ ] Login/logout, CSRF, rate limiting, Argon2id
- [ ] Admin approval/rejection; `flask create-admin`
- [ ] Admin-initiated reset with temporary one-time credential and forced change

## Phase 2 – Complaints
- [ ] Complaint model, state machine, append-only history
- [ ] Photo attachments (3 x 5 MB)

## Phase 3 – Staff and notifications
- [ ] Assignment, comments, in-app notifications

## Phase 4 – Admin dashboard and deployment
- [ ] Dashboard, CSV export, overdue flag, backups, hosting

## Cross-cutting
- [ ] Confirm Vite/Vitest on Node 26 (non-LTS); CI uses Node 24
- [ ] Add mypy gradually; Playwright E2E


---

# Roadmap update (Phase 3A Revision 2, proposed - pending final sign-off before Phase 3B)

Supersedes the earlier "Phase 1/2/3/4" backend list where they overlap. Frontend phases are complete with mock data and are not repeated.

## Confirmed decisions applied (Revision 2)
- [x] D1: One admin role initially; no admin tiers (ADR-021)
- [x] D2: Rejected students may be reactivated via administrator action (`rejected -> pending`), preserving unique roll numbers and emails (ADR-021)
- [x] D3: Wardens can reopen closed complaints with mandatory reason and history entry (ADR-020)
- [x] D4: Complaints can be rejected during review before work is accepted, with mandatory reason (ADR-020)
- [x] D5: Approved students without active room allocations can report common-area issues; room-specific complaints require active room (ADR-019)
- [x] D6: Full fine payments only in initial release; extensible architecture for partial payments and refunds (ADR-018, ADR-024)
- [x] D7: Email delivery provider-independent through configuration without database outbox table in initial release (ADR-023)
- [x] D8: Important administrative and financial records preserved without hard deletion (ADR-022)

## Confirmed operational decisions (U1-U4 resolved in final verification)
- [x] U1: Password-reset rate limits confirmed: 3 requests/user/hour, 10 requests/IP/hour, 10 invalid attempts/IP/15 min
- [x] U2: Complaint reopen target status confirmed: `closed -> under_review`, closing the previous open assignment and allowing a new assignment
- [x] U3: Email configuration confirmed: local email backend defaults to `console`; production email is configurable via `MAIL_*` environment variables
- [x] U4: Verify execution of `CREATE EXTENSION IF NOT EXISTS btree_gist;` and trusted status by `hostelcare_owner` during the first Phase 3B migration against `hostelcare_test`

## Awaiting owner sign-off (blocking Phase 3B)
- [x] Approve Phase 3A Final Database Design Verification Report to begin Phase 3B (SQLAlchemy Models & Alembic Migrations)

## Phase 3B - Schema implementation (completed)
- [x] SQLAlchemy 2 models per module (20 tables) with explicit naming convention
- [x] Alembic migrations in dependency order (`0001_initial_schema`):
  1. `btree_gist` extension (installed by `hostelcare_owner`)
  2. Identity: `users`, `student_profiles`, `staff_profiles`, `password_reset_tokens`
  3. Rooms: `blocks`, `rooms`, `room_allocations` (with exclusion constraints)
  4. Complaints: `complaints`, `complaint_assignments`, `complaint_updates`, `complaint_internal_notes`, `complaint_history`
  5. Fines & Payments: `fines`, `fine_disputes`, `fine_history`, `payment_attempts`, `payments`, `payment_events`
  6. Notifications & Audit: `notifications`, `audit_logs`
- [x] Sequences created and granted: `complaint_ref_seq`, `fine_ref_seq`, `receipt_seq` (`GRANT USAGE`)
- [x] Constraint triggers and maintenance functions (owned by `hostelcare_owner`, fixed `search_path = public, pg_temp`):
  - T1a & T1b (`SECURITY INVOKER`): Room bed capacity validation (`FOR SHARE` on `rooms`), active status check, and capacity reduction guard (`room_allocations`, `rooms`)
  - T2a & T2b (`SECURITY INVOKER`, `DEFERRABLE INITIALLY DEFERRED`): Bidirectional invariant that `fines.status = 'paid'` iff a `payments` row exists (and linked `payment_attempts.status = 'succeeded'`)
  - T3 (`SECURITY INVOKER`): Payment attempt and verified payment `amount_inr` and `currency` match `fines.amount_inr` (`FOR SHARE` on `fines`)
  - `public.purge_expired_password_reset_tokens()` (`SECURITY DEFINER`, zero parameters, `REVOKE ALL FROM PUBLIC`, `GRANT EXECUTE TO hostelcare_app`): Purges only tokens with `expires_at < now() - interval '24 hours' AND created_at < now() - interval '24 hours'`
- [x] Each table migration carries explicit least-privilege grants to `hostelcare_app` (column-level UPDATE, SELECT+INSERT on append-only tables, **zero `DELETE` privileges on all 20 tables**, no table ownership or DDL)
- [x] Migration environment revokes all privileges on `alembic_version` from `PUBLIC` and `hostelcare_app`
- [x] Schema test suite on `hostelcare_test`:
  - Every CHECK (including all 8 NULL combinations of `room_allocations` termination fields and `'!'` vs `$argon2id$` on `users.password_hash`), UNIQUE, composite FK (`(payment_attempt_id, fine_id)`), and exclusion constraint verified
  - Constraint triggers T1a/T1b, T2a/T2b, T3 and `purge_expired_password_reset_tokens()` verified under `hostelcare_app` and concurrency
  - Behavioral permission tests confirming `hostelcare_app` cannot perform DDL, cannot `DELETE` from any table (including `password_reset_tokens`), cannot update audit/history tables, and cannot access `alembic_version`

## Phase 3C - Authentication, identity & role-based access control (completed)
- [x] Argon2id hashing (`argon2-cffi`), login/logout, `/api/v1/auth/me`, CSRF (`X-CSRF-Token` + `hc_csrf_token`), `Origin` validation, and HTTP-only cookie session management with `session_version`
- [x] Self-service & admin-triggered password reset service (256-bit token generation, SHA-256 storage, provider-independent `console`/`smtp` email dispatch, atomic single-use `UPDATE ... RETURNING` redemption, previous token revocation, `session_version` bump)
- [x] Student registration (`status='pending'`), admin approval (`pending -> active`), rejection (`pending -> rejected`), and controlled reactivation (`rejected -> pending`) on the existing account row; `flask create-admin` and `flask purge-reset-tokens` CLI commands; admin staff provisioning with unusable password marker `'!'`, update, and deactivation
- [x] Reusable `@login_required` and `@require_role(...)` decorators enforcing active status and strict role isolation (`student`, `staff`, `admin`)
- [x] Append-only `audit_logs` service with sensitive-field sanitization and database-backed rate limiting (per-IP & per-user login and password-reset rate limits + account lockout)
- [x] React frontend connected to real backend authentication, registration, password reset, student approval/rejection/reactivation, and staff provisioning APIs (removing mock login fallbacks and demo user switching)

## Phase 3D - Complete complaint & maintenance management system (completed)
- [x] Student complaint APIs (`POST /api/v1/student/complaints`, `GET /api/v1/student/complaints`, `GET /api/v1/student/complaints/{id}`) with `location_type = 'room' | 'common_area'`, active-room validation via `room_allocations` (`start_date <= today AND (end_date IS NULL OR end_date > today)`), free-text `description` (`<= 5000` chars), optional `category` (`<= 60` chars), server-generated `reference_no` (`CMP-YYYY-00001`), and strict student ownership (`WHERE student_user_id = g.current_user.id`)
- [x] Admin/warden complaint management APIs (`GET /api/v1/admin/complaints`, `GET /api/v1/admin/complaints/{id}`, `PATCH /api/v1/admin/complaints/{id}`, `POST .../assign`, `POST .../reassign`, `POST .../internal-notes`, `POST .../close`, `POST .../return-for-rework`, `POST .../reject`, `POST .../reopen`) with row-level `FOR UPDATE` locking, single-open-assignment invariant enforcement (`ended_at`, `ended_by`, `end_note` + `db.session.flush()`), pre-acceptance rejection rule (D4/ADR-020), and warden reopening (`closed -> under_review`, D3/ADR-020)
- [x] Staff task execution APIs (`GET /api/v1/staff/tasks`, `GET /api/v1/staff/tasks/{id}`, `POST /api/v1/staff/tasks/{id}/accept`, `POST /api/v1/staff/tasks/{id}/start`, `POST /api/v1/staff/tasks/{id}/updates`, `POST /api/v1/staff/tasks/{id}/complete`) with strict active-assignment ownership (`staff_user_id == g.current_user.id AND ended_at IS NULL`) and mandatory completion note
- [x] Structural isolation of `complaint_internal_notes` (`ComplaintInternalNote` imported only in `backend/app/complaints/admin_service.py`) verified by automated AST inspection and API response assertions
- [x] In-app notifications (`GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications/read-all`) and append-only `complaint_history` + `audit_logs` created atomically inside each lifecycle transaction
- [x] React frontend connected across Student, Admin, and Staff complaint, task, and notification pages (`AppContext.jsx`, `SubmitComplaintPage.jsx`, `StudentComplaintsPage.jsx`, `ComplaintDetailPage.jsx`, `StudentNotificationsPage.jsx`, `AdminComplaintsPage.jsx`, `AdminComplaintDetailPage.jsx`, `StaffDashboardPage.jsx`, `StaffTasksPage.jsx`, `StaffTaskDetailPage.jsx`, `StaffNotificationsPage.jsx`)

## Phase 3D.5 - Global Data Integrity & Room Management (completed)
- [x] Complete mock-data audit and cleanup: removed sample fine records (`initialFines` -> `[]`), empty fine directories now render clean non-crashing states without demo data
- [x] Admin Block Management APIs (`GET /api/v1/admin/blocks`, `POST /api/v1/admin/blocks`, `PATCH /api/v1/admin/blocks/<block_id>`) with uppercase code validation, name validation, and safe deactivation protection
- [x] Admin Room Management APIs (`GET /api/v1/admin/rooms`, `POST /api/v1/admin/rooms`, `GET /api/v1/admin/rooms/<room_id>`, `PATCH /api/v1/admin/rooms/<room_id>`) with capacity bounds (1-8), duplicate room number prevention per block, and active allocation capacity reduction protection
- [x] Student Room Allocation Management APIs (`GET /api/v1/admin/room-allocations`, `POST /api/v1/admin/room-allocations`, `POST /api/v1/admin/room-allocations/<id>/end`, `POST /api/v1/admin/room-allocations/<id>/transfer`) with row locking (`FOR UPDATE`), bed availability enforcement, audit logging, and system notifications
- [x] Comprehensive Admin Room & Occupancy frontend interface (`AdminRoomsPage.jsx`) with 3 tabs (Rooms & Occupancy Map, Hostel Blocks, Resident Allocations) and modal dialogues (Add/Edit Block, Add/Edit Room, Allocate Resident, Transfer Resident, End Allocation Checkout)
- [x] Data consistency: Unallocated students display "Not Assigned" cleanly across `StudentProfilePage` and `AdminStudentsPage` without sample room numbers

## Phase 3E - Fines, disputes and payments
- [ ] Blocks, rooms, and allocations services with concurrency row locking, transfer handling, and validation
- [ ] Fine issuance, written dispute submission, dispute decision (approve/reject), waive, cancel, and manual payment records
- [ ] Razorpay order creation, raw-body HMAC webhook verification, idempotent event processing (behind config flag)
- [ ] Frontend integration of real backend API replacing mock context (separate, explicit task)

## Housekeeping
- [ ] README still says "Phase 0 only" (stale; update after Phase 3B)
- [ ] Align frontend mock workflows with server rules when integrating backend API
