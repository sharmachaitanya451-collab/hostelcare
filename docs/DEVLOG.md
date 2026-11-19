# Development Log

## 2026-11-13 – Phase 0 (foundation)
- Architecture v0.2 approved with refinements (admin-initiated reset, full complaint history).
- Verified environment: Node 26.13.1, npm 11.20.0, Python 3.12.10 (`backend\.venv`), Git 2.56.1, PostgreSQL 18.4 (service running). Agent shell has a restricted PATH; full paths are used.
- Scaffolded backend (app factory, config, logging, error envelope, `/healthz`, `/readyz`, `/api/v1/meta`, SQLAlchemy/Migrate wiring, pytest) and frontend (React, Vite, Tailwind, Vitest, ESLint, Prettier).
- Added docs, `.gitignore`, `.editorconfig`, GitHub Actions CI.
- Not done by design: application database/role, auth, complaint features.


## 2026-11-14 - Phase 3A (database architecture and schema design)
- Inspected `backend/`, `database/setup_postgres.sql`, `docs/`, `README.md`, tests and the frontend mock data/context to derive real workflows. `.env` was not opened.
- Produced a design only: 19 tables across identity, rooms, complaints, fines, payments, notifications and audit (one table, `complaint_internal_notes`, added beyond the brief to make admin notes structurally invisible to students).
- Key decisions (ADR-007 to ADR-016): bigint identity keys with UUID/reference public ids; varchar + CHECK enums; `timestamptz` and `numeric(12,2)` INR; exclusion constraints for allocations; append-only history with SELECT+INSERT-only grants; payments verified server-side with idempotent webhooks via unique event id; no RLS, no role tables.
- Documented 13 conflicts between the brief, approved v0.2 docs, the frontend mocks and `config.py` (design doc section 0) with proposed resolutions, plus open questions Q1-Q6 in TODO.md.
- Files: created `docs/database-design.md`, `docs/database-erd.md`, `docs/ADR.md`; appended to `docs/ARCHITECTURE.md`, `docs/TODO.md`, `docs/DEVLOG.md`.
- Not done by design: no SQLAlchemy models, no migrations, no database or role changes, no frontend changes, no commits. Stopped for owner review.


## 2026-11-14 - Phase 3A Revision 2 (design review and revision)
- Processed owner design review decisions D1-D8 and completed all required corrections across the design documentation.
- Replaced admin-issued temporary credential / code reset with self-service email password reset (30-min expiry, SHA-256 hash storage, single-use atomic redemption, neutral anti-enumeration response, database-backed rate limiting via audit logs, admin trigger capability without seeing or generating passwords, ADR-017).
- Separated payment attempts from verified payments into two tables (`payment_attempts` and `payments`, 20 tables total). Verified captures that cannot be applied are flagged `captured_unapplied` rather than auto-classified as refunds; browser callbacks never mark fines paid; idempotent webhooks anchored by `gateway_event_id` (ADR-018, ADR-024).
- Added complaint reopening by wardens (`closed -> under_review`) with mandatory reason and history entry; restricted rejection to pre-acceptance review phase with mandatory reason (ADR-020).
- Supported common-area complaint submissions by approved students without an active room allocation via `location_type = 'room' | 'common_area'` (ADR-019).
- Maintained single `admin` role (no tiers) and enabled student account reactivation (`rejected -> pending`) via administrator control, preserving unique roll numbers and emails to prevent duplicate accounts (ADR-021).
- Switched room allocation occupancy ranges to half-open intervals `[start_date, end_date)` with `btree_gist` exclusion constraints, bed-level capacity enforcement via constraint trigger T1 and room row locking, guaranteeing same-day transfer safety and no overlapping occupancies (ADR-026).
- Abstracted email delivery as provider-independent via environment configuration without database outbox table in initial release (ADR-023).
- Documented exact PostgreSQL ownership and runtime least-privilege permissions: `hostelcare_owner` owns schema and performs migrations; `hostelcare_app` has column-level UPDATE on mutable tables, SELECT+INSERT only on append-only history tables, sequence USAGE, no DELETE except expired reset tokens, zero access to `alembic_version` (ADR-022).
- Updated all 6 deliverables: `docs/database-design.md`, `docs/database-erd.md`, `docs/ADR.md` (ADR-007 to ADR-026), `docs/ARCHITECTURE.md`, `docs/TODO.md`, `docs/DEVLOG.md`.
- No SQLAlchemy models, migrations, database changes, or frontend code were modified; no commits made. Stopped for final review.


## 2026-11-14 - Phase 3A Final Database Design Verification
- Conducted a full technical audit of all 6 documentation files (`docs/database-design.md`, `docs/database-erd.md`, `docs/ADR.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`, `docs/DEVLOG.md`) across all 20 tables, relationships, constraints, security rules, and PostgreSQL permission grants.
- Recorded owner-confirmed operational decisions U1 (password reset rate limits: 3/user/hr, 10/IP/hr, 10 invalid/IP/15 min), U2 (reopen closes previous assignment and transitions `closed -> under_review`), U3 (local `console` default email backend, configurable production backend), and U4 (`btree_gist` verification on `hostelcare_test` during first Phase 3B migration).
- Fixed minor cross-document references (`ADR-007` `public_id` table list to include `payment_attempts`; `database-design.md` U1-U4 numbering alignment).
- Verified trigger execution privileges (`SECURITY INVOKER` with `FOR SHARE` on `rooms`), SQLAlchemy 2 composite/multi-FK requirements, column-level `UPDATE` interactions, and sequence formatting safeguards.
- Status: **READY** for Phase 3B (pending owner sign-off).


## 2026-11-14 - Phase 3A Final Pre-Implementation Corrections
- Applied all 6 final pre-implementation corrections across `docs/database-design.md`, `docs/database-erd.md`, `docs/ADR.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`, and `docs/DEVLOG.md`:
  1. **Room allocation termination constraint:** Replaced `(end_date IS NULL) = (ended_by IS NULL)` with explicit `CHECK ((end_date IS NULL AND ended_by IS NULL AND end_reason IS NULL) OR (end_date IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL AND btrim(end_reason) <> ''))`, verified across all 8 NULL/NOT NULL combinations.
  2. **Password reset token deletion permissions:** Revoked direct `DELETE` on `password_reset_tokens` from `hostelcare_app` (`hostelcare_app` now holds zero `DELETE` privileges across all 20 tables). Defined owner-owned `SECURITY DEFINER` function `public.purge_expired_password_reset_tokens()` (`SET search_path = public, pg_temp`, `REVOKE ALL FROM PUBLIC`, `GRANT EXECUTE TO hostelcare_app`) with a hardcoded `expires_at < now() - interval '24 hours' AND created_at < now() - interval '24 hours'` predicate that can never delete active tokens or tokens inside the 1-hour rate-limit window.
  3. **Password hash marker (`'!'`):** Explicitly documented `CHECK (password_hash = '!' OR password_hash LIKE '$argon2id$%')` where `'!'` is the unusable-password marker for newly created staff/admin accounts prior to first reset redemption, with unconditional authentication rejection before Argon2id verification and constant-time dummy verification.
  4. **Payment processing atomicity & cross-fine attempt isolation:** Added `uq_payment_attempts_id_fine (id, fine_id)` on `payment_attempts` and composite FK `(payment_attempt_id, fine_id) REFERENCES payment_attempts(id, fine_id)` on `payments` so an attempt can never be reused for another fine. Made deferred trigger **T2** bidirectional (`T2a` on `fines`, `T2b` on `payments`), and documented the exact lock order (`fines` -> `payment_attempts`) and statement execution order for attempt creation, webhook verification, and manual payments.
  5. **Trigger and runtime permission verification:** Documented exact `SELECT` and column-level `UPDATE` (`FOR SHARE`) requirements, execution context (`SECURITY INVOKER` for T1a, T1b, T2a, T2b, T3; `SECURITY DEFINER` only for `purge_expired_password_reset_tokens`), `hostelcare_owner` ownership, and fixed `search_path = public, pg_temp`.
- No SQLAlchemy models, migrations, DDL, database changes, or git commits were made. Stopped for final owner approval of Phase 3B.


## 2026-11-14 - Phase 3B (SQLAlchemy models and Alembic migrations)
- Implemented all 20 approved PostgreSQL tables as modular SQLAlchemy 2 models under `backend/app/models/` (`identity.py`, `rooms.py`, `complaints.py`, `complaint_internal_notes.py`, `fines.py`, `payments.py`, `notifications.py`, `audit.py`, `sequences.py`, `__init__.py`), keeping `ComplaintInternalNote` in a dedicated module with no relationship or backref on `Complaint`.
- Created the Alembic migration environment (`backend/migrations/env.py`, `alembic.ini`, `script.py.mako`) and initial schema migration `0001_initial_schema` (`backend/migrations/versions/20261114_0001_initial_schema.py`), connecting via `MIGRATION_DATABASE_URI` (`hostelcare_owner`) and revoking all privileges on `public.alembic_version` from `PUBLIC` and `hostelcare_app`.
- Installed `btree_gist`, 3 reference sequences (`complaint_ref_seq`, `fine_ref_seq`, `receipt_seq`), all 20 tables with composite FKs, partial unique indexes, CHECK constraints, and GiST exclusion constraints, plus triggers T1a/T1b, deferred constraint triggers T2a/T2b, trigger T3, `public.purge_expired_password_reset_tokens()`, and exact least-privilege table/column-level grants for `hostelcare_app` (zero `DELETE` privileges on all 20 tables).
- Verified full migration apply (`upgrade head`), rollback (`downgrade base`), and reapply (`upgrade head`) on `hostelcare_test` first, followed by upgrading `hostelcare`.
- Added comprehensive Phase 3B integration test suite (`backend/tests/test_schema_phase3b.py`); all 20 backend pytest tests and Ruff lint checks pass. No frontend files or Git commits modified; stopped for Phase 3C approval.


## 2026-11-14 - Phase 3C (authentication, identity & role-based access control)
- Implemented complete authentication, identity lifecycle, and role-based access control across the Flask backend (`backend/app/auth/`, `backend/app/audit/`, `backend/app/core/mailer.py`) and React frontend (`frontend/src/`).
- **Security & Session Architecture:** Argon2id password hashing via `argon2-cffi`; explicit rejection of the unusable password marker `'!'` before Argon2 verification with constant-time dummy verification; HTTP-only cookie sessions (`SameSite=Lax`, `Secure` in production, `HttpOnly=True`) bound to `user.public_id` and `user.session_version`; request-time verification of `session_version` and `status == 'active'`; CSRF double-submit protection (`X-CSRF-Token` header + `hc_csrf_token` cookie) and `Origin` header validation on state-changing requests.
- **Student Registration & Approval Lifecycle:** Implemented `POST /api/v1/auth/register` (`status='pending'`, neutral duplicate email/roll number `409` handling, privilege-escalation rejection), `GET /api/v1/admin/students`, `GET /api/v1/admin/students/pending`, `POST /api/v1/admin/students/{id}/approve` (`pending -> active`), `POST /api/v1/admin/students/{id}/reject` (`pending -> rejected`, mandatory reason), and `POST /api/v1/admin/students/{id}/reactivate` (`rejected -> pending`, mandatory reason, reuses existing account row preserving unique email and roll number).
- **Staff Provisioning & Management:** Implemented `POST /api/v1/admin/staff` (creates `staff` account with `password_hash='!'` and emails a 30-minute single-use password setup link without generating or displaying temporary passwords), `GET /api/v1/admin/staff`, `GET /api/v1/admin/staff/{id}`, `PATCH /api/v1/admin/staff/{id}`, `POST /api/v1/admin/staff/{id}/deactivate` (revokes active sessions via `session_version` increment and revokes open reset tokens), and `GET/PATCH /api/v1/staff/profile` (staff can update own `phone`/`shift`, never `trade` or `role`).
- **Password Reset & Setup:** Implemented `POST /api/v1/auth/forgot-password` (neutral anti-enumeration response), `POST /api/v1/auth/reset-password` (256-bit `secrets.token_urlsafe(32)` token, SHA-256 hash lookup, 30-min expiry, atomic single-use `UPDATE ... RETURNING`, `session_version` bump), `POST /api/v1/admin/users/{id}/send-password-reset`, provider-independent email delivery (`console` in dev/test, `smtp` in prod), and CLI commands `flask create-admin` and `flask purge-reset-tokens`.
- **Audit Logging & Rate Limiting:** Implemented append-only `audit_logs` service with automatic redaction of sensitive keys (`password`, `token`, `hash`, `secret`, `cookie`, `csrf`) and database-backed rate limiting for login failures, account lockouts, and password reset requests/redemptions.
- **Frontend Integration & Verification:** Created `frontend/src/lib/api.js` and connected `AppContext.jsx`, `RequireRole.jsx`, `LoginPage.jsx`, `StaffLoginPage.jsx`, `RegisterPage.jsx`, `ForgotPasswordPage.jsx`, `ResetPasswordPage.jsx`, `RegistrationApprovalsPage.jsx`, `AdminStudentsPage.jsx`, `AdminStaffPage.jsx`, and `StaffProfilePage.jsx` to the real backend APIs, removing mock login fallbacks and demo user switching. Verified all 27 backend pytest tests, Ruff lint checks, 25 frontend Vitest tests, ESLint, and Vite production build pass.


## 2026-11-14 - Phase 3D (complete complaint & maintenance management system)
- Implemented the full database-backed complaint, maintenance task, and notification vertical slice across the Flask backend (`backend/app/complaints/`, `backend/app/notifications/`, `backend/app/auth/service.py`) and React frontend (`frontend/src/`).
- **Student Complaint Submission & Visibility:** Implemented `POST /api/v1/student/complaints`, `GET /api/v1/student/complaints`, `GET /api/v1/student/complaints/{id}`, and `GET /api/v1/blocks`. Enforced active-today `RoomAllocation` verification (`start_date <= today AND (end_date IS NULL OR end_date > today)`) for `location_type='room'` (deriving `room_id` strictly from the active allocation and ignoring client-spoofed room fields) while allowing approved students with or without an active room allocation to submit `location_type='common_area'` complaints with mandatory `location_detail` (D5/ADR-019). Preserved unrestricted free-text descriptions (`<= 5000` chars) and optional categories (`<= 60` chars), formatted sequence references via `complaint_ref_seq` (`CMP-YYYY-00001`), and enforced strict student ownership (`WHERE student_user_id = g.current_user.id`).
- **Admin/Warden Complaint Lifecycle:** Implemented `GET /api/v1/admin/complaints` (filtering by `status`, `priority`, `category`, `assigned_staff`, `block`, `date`/`date_from`/`date_to`, and keyword search `q`), `GET /api/v1/admin/complaints/{id}`, `PATCH /api/v1/admin/complaints/{id}` (priority/category updates and `submitted -> under_review`), `POST .../assign`, `POST .../reassign` (closes previous open assignment with `ended_at`, `ended_by`, `end_note` and flushes before inserting the new open assignment to satisfy `uq_complaint_assignments_one_open`), `POST .../internal-notes`, `POST .../close` (`completed -> closed`), `POST .../return-for-rework` (`completed -> in_progress` with mandatory reason and `completed_at = None`), `POST .../reject` (`submitted | under_review | assigned -> rejected` pre-acceptance only with mandatory reason, D4/ADR-020), and `POST .../reopen` (`closed -> under_review` with mandatory reason, clearing `completed_at`/`closed_at` and closing any open assignment, D3/ADR-020).
- **Staff Task Execution & Strict Ownership:** Implemented `GET /api/v1/staff/tasks`, `GET /api/v1/staff/tasks/{id}`, `POST /api/v1/staff/tasks/{id}/accept` (`assigned -> accepted`), `POST /api/v1/staff/tasks/{id}/start` (`accepted -> in_progress` with optional initial note), `POST /api/v1/staff/tasks/{id}/updates` (`ComplaintUpdate(update_type='progress')`), and `POST /api/v1/staff/tasks/{id}/complete` (`in_progress -> completed` with mandatory completion note recorded as `ComplaintUpdate(update_type='completion')`). Enforced active-assignment ownership (`staff_user_id == g.current_user.id AND ended_at IS NULL`) and row-level `FOR UPDATE` locking on all state transitions.
- **Structural Privacy & Notifications:** Enforced structural module isolation so `ComplaintInternalNote` (`app.models.complaint_internal_notes`) is imported exclusively in `backend/app/complaints/admin_service.py` and never in student or staff services or serializers. Implemented `GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`, and `POST /api/v1/notifications/read-all`, creating in-app notifications, `complaint_history`, and `audit_logs` atomically within each lifecycle transaction.
- **Frontend Integration & Verification:** Connected Student, Admin, and Staff portals (`AppContext.jsx`, `SubmitComplaintPage.jsx`, `StudentComplaintsPage.jsx`, `ComplaintDetailPage.jsx`, `StudentNotificationsPage.jsx`, `AdminComplaintsPage.jsx`, `AdminComplaintDetailPage.jsx`, `StaffDashboardPage.jsx`, `StaffTasksPage.jsx`, `StaffTaskDetailPage.jsx`, `StaffNotificationsPage.jsx`) to the backend APIs and removed mock complaint/notification runtime state. Verified all 32 backend pytest tests, Ruff lint checks, 27 frontend Vitest tests, ESLint, and Vite production build pass.


## 2026-11-15 - Phase 3D.5 (global data integrity & room management)
- **Part A — Mock Data Audit & Cleanup:** Audited all frontend directories and contexts. Removed demo fine records (`initialFines` import removed; `fines` initialized to empty array `[]` in `AppContext.jsx`) so no mock fines appear across any portal. Ensured fine and violation pages (`AdminFinesPage`, `StudentFinesPage`, `AdminFineDisputesPage`, `AdminViolationsPage`, `StudentFineHistoryPage`) display clean, meaningful empty states noting Phase 3E activation without errors or crashes.
- **Part B — Admin Block Management:** Implemented `GET /api/v1/admin/blocks`, `POST /api/v1/admin/blocks`, and `PATCH /api/v1/admin/blocks/<block_id>` with admin role enforcement, block code validation (1-10 uppercase alphanumeric), name validation, and safe deactivation protection (preventing deactivation when active room allocations exist in the block).
- **Part C — Admin Room Management:** Implemented `GET /api/v1/admin/rooms`, `POST /api/v1/admin/rooms`, `GET /api/v1/admin/rooms/<room_identifier>`, and `PATCH /api/v1/admin/rooms/<room_identifier>` supporting filtering by `block_id`, `floor`, and `is_active`. Enforced capacity bounds (1-8 beds), unique room numbers per block, active block verification, and capacity reduction protection (rejecting capacity decrease below occupied bed count or highest occupied bed number).
- **Part D — Student Room Allocation Management:** Implemented `GET /api/v1/admin/room-allocations`, `POST /api/v1/admin/room-allocations`, `POST /api/v1/admin/room-allocations/<allocation_id>/end`, and `POST /api/v1/admin/room-allocations/<allocation_id>/transfer`. Enforced single active allocation per student, one occupant per bed within capacity, row locking (`FOR UPDATE` on room and student), half-open interval overlap prevention, atomic transfer (ending previous allocation and creating new allocation on effective date), mandatory checkout reasons (`>= 3` chars), system notifications, and audit logging.
- **Part E — Frontend Room Management Interface:** Expanded `AdminRoomsPage.jsx` into a comprehensive 3-tab management workspace ("Rooms & Occupancy Map", "Hostel Blocks", "Resident Allocations") with search/filters, bed-slot visualization, quick allocation actions, and full modals (Add Block, Edit Block, Add Room, Edit Room, Allocate Student, Transfer Resident, End Allocation Checkout).
- **Part F — Global Data Consistency:** Updated `StudentProfilePage.jsx` and `AdminStudentsPage.jsx` so unallocated residents cleanly display "Not Assigned" without fake room numbers.
- **Part G — Verification & Quality Assurance:** Added backend test suite (`backend/tests/test_rooms_phase3d5.py`) with 3 comprehensive tests; added frontend Vitest tests in `frontend/src/App.test.jsx`. Verified:
  - Backend tests: 47/47 pytest passed in 25.64s.
  - Backend linter: Ruff passed with zero errors.
  - Frontend tests: 33/33 Vitest passed in 3.85s.
  - Frontend linter: ESLint passed with zero errors.


## 2026-11-15 - Fix Block Creation Validation Error & Double-Serialization Bug
- **Root Cause Analysis:** In `frontend/src/context/AppContext.jsx`, `addBlock` passed `body: JSON.stringify(data)`. Because `frontend/src/lib/api.js`'s `apiRequest` unconditionally executed `JSON.stringify(body)`, the payload was doubly JSON-encoded into a JSON string (`"\"{\\\"name\\\": ...}\""`). Flask's `request.get_json(silent=True)` parsed this into a Python `str` instead of a `dict`, causing `_json_body()` to return `{}`. In turn, `create_block` found `data.get("name")` was `None` and raised 400 "Block name is required.".
- **Fix Applied:**
  1. Updated `frontend/src/context/AppContext.jsx` methods (`addBlock`, `updateBlock`, `addRoom`, `updateRoom`, `allocateRoom`, `endAllocation`, `transferAllocation`) to pass `body: data` directly as an object, matching all other API calls.
  2. Updated `frontend/src/lib/api.js` to serialize `body` only when `typeof body !== 'string'` (`typeof body === 'string' ? body : JSON.stringify(body)`), preventing double serialization.
  3. Hardened `backend/app/rooms/routes.py` `_json_body()` to parse stringified JSON payloads if received, and updated `backend/app/rooms/service.py` to support field aliases (`name`/`block_name`/`blockName`, `code`/`block_code`/`blockCode`, `display_order`/`displayOrder`).
  4. Updated `frontend/src/pages/admin/AdminRoomsPage.jsx` Add Block modal to display field-specific validation errors beside inputs, preserve form inputs upon validation failure, prevent duplicate submissions (`if (submitting) return` and button disabled state), and refresh blocks and room occupancy data via `fetchBlocks()` and `fetchRooms()` on success.
- **Verification:**
  - Backend pytest: Added `test_block_creation_missing_name_validation_and_payload_resilience` in `test_rooms_phase3d5.py` (48/48 passed).
  - Backend linter: Ruff passed with 0 errors.
  - Frontend Vitest: Added `validates missing block name, preserves form input on failure, and creates block successfully` in `App.test.jsx` (34/34 passed).
  - Frontend linter: ESLint passed with 0 errors.


## 2026-11-15 - Staff Email Editing and Password Setup Workflow
- **Staff Email Editing:**
  - Added Email Address field to the Edit Staff modal in `frontend/src/pages/admin/AdminStaffPage.jsx`, prepopulated with the staff member's current email.
  - Implemented client-side and server-side email format validation and normalization (lowercase, trim).
  - Enforced global email uniqueness across `users.email` (returns HTTP 409 conflict when duplicate).
  - Updated `backend/app/auth/service.py` (`update_staff_account`) to record `staff.email_updated` audit log containing the admin actor, staff user ID, staff code, old email, and new email (never passwords or tokens).
  - Preserved staff account ID, role, status, staffCode, and task history across email updates without creating duplicate users or profiles.
- **Password Setup Workflow:**
  - Provided an explicit "Send Password Setup Link" action button directly inside the Edit Staff modal and as a quick-action trigger in the post-update notification banner.
  - Uses existing `POST /api/v1/admin/users/<id>/send-password-reset` with single-use 30-minute token dispatched via configured mailer (console output in development).
- **Verification:**
  - Backend pytest: Added `test_staff_email_editing_validation_audit_and_password_setup_workflow` in `backend/tests/test_auth_phase3c.py` (49/49 passed in 25.91s).
  - Backend linter: Ruff passed with zero errors.
  - Frontend Vitest: Added `allows admin to edit staff email with validation and dispatch password setup link` in `frontend/src/App.test.jsx` (35/35 passed in 4.29s).
  - Frontend linter: ESLint passed with zero errors.
