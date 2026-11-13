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
