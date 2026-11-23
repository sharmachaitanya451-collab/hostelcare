"""Phase 3D integration tests: Complete Complaint & Maintenance Management System.

Covers:
1. Student room complaint submission (requires active RoomAllocation) & free-text/custom category.
2. Student common-area complaint submission without active room allocation (D5 / ADR-019).
3. Student ownership isolation (cannot view another student's complaint).
4. Admin complaint listing, filtering (status, priority, category, staff, block, date, search),
   and safe PATCH rules (rejecting arbitrary status mutations).
5. Admin assign and reassign workflows, including previous staff access revocation.
6. Staff task ownership, accept, start, progress updates, and completion with mandatory note.
7. Invalid status transition rejections across student, staff, and admin roles.
8. Admin return-for-rework (`completed -> in_progress`, clearing `completed_at`) and re-completion.
9. Admin close (`completed -> closed`) and reopen (`closed -> under_review` with mandatory reason,
   clearing `completed_at`/`closed_at` and ending open assignment per D3 / ADR-020).
10. Pre-acceptance rejection (`submitted | under_review | assigned -> rejected` with mandatory
    reason per D4 / ADR-020) and post-acceptance rejection prevention.
11. Strict privacy & module isolation for `complaint_internal_notes` (admin-only visibility,
    never exposed to students/staff or leaked into history/notifications/audit metadata).
12. In-app notifications creation, listing, single mark-read ownership check, and mark-all-read.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, select, text

from app import create_app
from app.auth.security import hash_password
from app.extensions import db
from app.models.audit import AuditLog
from app.models.complaints import Complaint, ComplaintAssignment, ComplaintHistory
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def phase3d_app():
    """Create a testing Flask app and ensure `hostelcare_test` is migrated to head."""
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture(autouse=True)
def _clean_phase3d_tables(phase3d_app):
    """Truncate relevant tables between tests using `hostelcare_owner`."""
    owner_engine = create_engine(phase3d_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
                "public.complaint_history, "
                "public.complaint_internal_notes, "
                "public.complaint_updates, "
                "public.complaint_assignments, "
                "public.complaints, "
                "public.room_allocations, "
                "public.rooms, "
                "public.blocks, "
                "public.password_reset_tokens, "
                "public.student_profiles, "
                "public.staff_profiles, "
                "public.users "
                "RESTART IDENTITY CASCADE"
            )
        )
    owner_engine.dispose()
    yield


def _seed_complaint_actors(app) -> dict[str, str]:
    """Seed admin, two students (with/without room), two active staff, and one inactive staff."""
    with app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.flush()

        block_a = Block(
            code="BLKA",
            name="Aryabhatta Block",
            is_active=True,
        )
        db.session.add(block_a)
        db.session.flush()

        room_204 = Room(
            block_id=block_a.id,
            room_number="A-204",
            floor=2,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        db.session.add(room_204)
        db.session.flush()

        # Student 1: Active student WITH active room allocation (A-204)
        stu1 = User(
            email="aarav@hostelcare.test",
            full_name="Aarav Sharma",
            phone="+91 98234 56789",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add(stu1)
        db.session.flush()
        db.session.add(
            StudentProfile(
                user_id=stu1.id,
                roll_number="2026CSB1042",
                reviewed_by=admin.id,
                reviewed_at=datetime.now(UTC),
                review_note="Approved",
            )
        )
        db.session.flush()
        db.session.add(
            RoomAllocation(
                student_user_id=stu1.id,
                room_id=room_204.id,
                bed_number=2,
                start_date=date.today() - timedelta(days=10),
                allocated_by=admin.id,
            )
        )

        # Student 2: Active student WITHOUT an active room allocation
        stu2 = User(
            email="meera@hostelcare.test",
            full_name="Meera Krishnan",
            phone="+91 97654 12098",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add(stu2)
        db.session.flush()
        db.session.add(
            StudentProfile(
                user_id=stu2.id,
                roll_number="2026ECE1089",
                reviewed_by=admin.id,
                reviewed_at=datetime.now(UTC),
                review_note="Approved awaiting room",
            )
        )

        # Staff 1: Active Electrician
        stf1 = User(
            email="ramesh@hostelcare.test",
            full_name="Ramesh Babu",
            phone="+91 98111 22334",
            designation="Senior Electrician",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add(stf1)
        db.session.flush()
        db.session.add(
            StaffProfile(
                user_id=stf1.id,
                staff_code="STF-0001",
                trade="Electrician",
                shift="Morning (08:00 AM - 04:00 PM)",
            )
        )

        # Staff 2: Active Plumber
        stf2 = User(
            email="santosh@hostelcare.test",
            full_name="Santosh Kumar",
            phone="+91 98222 33445",
            designation="Plumbing Technician",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add(stf2)
        db.session.flush()
        db.session.add(
            StaffProfile(
                user_id=stf2.id,
                staff_code="STF-0002",
                trade="Plumber",
                shift="General (09:00 AM - 05:30 PM)",
            )
        )

        # Staff 3: Inactive / Deactivated Carpenter
        stf3 = User(
            email="inactive.staff@hostelcare.test",
            full_name="Mahesh Yadav",
            phone="+91 98333 44556",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="deactivated",
        )
        db.session.add(stf3)
        db.session.flush()
        db.session.add(
            StaffProfile(
                user_id=stf3.id,
                staff_code="STF-0003",
                trade="Carpenter",
            )
        )

        db.session.commit()
        return {
            "admin_id": str(admin.public_id),
            "stu1_id": str(stu1.public_id),
            "stu2_id": str(stu2.public_id),
            "stf1_id": str(stf1.public_id),
            "stf2_id": str(stf2.public_id),
            "stf3_id": str(stf3.public_id),
            "block_id": str(block_a.id),
            "block_code": block_a.code,
        }


def _login_and_headers(client, identifier: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()
    csrf = resp.get_json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def test_structural_module_isolation_for_internal_notes():
    """Verify student_service, staff_service, and serializers never import ComplaintInternalNote."""
    complaints_dir = Path(__file__).resolve().parent.parent / "app" / "complaints"
    for filename in ("serializers.py", "student_service.py", "staff_service.py"):
        source = (complaints_dir / filename).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "complaint_internal_notes" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "complaint_internal_notes" not in mod
                for alias in node.names:
                    assert alias.name != "ComplaintInternalNote"


@pytest.mark.db
def test_student_room_and_common_area_complaint_submission_and_ownership(phase3d_app):
    """Verify room complaint, common-area complaint without room, validation, and ownership."""
    actors = _seed_complaint_actors(phase3d_app)
    stu1_client = phase3d_app.test_client()
    stu2_client = phase3d_app.test_client()

    stu1_headers = _login_and_headers(stu1_client, "aarav@hostelcare.test", "StudentPass123!")
    stu2_headers = _login_and_headers(stu2_client, "meera@hostelcare.test", "StudentPass123!")

    # 1. Verify /api/v1/auth/me exposes active room for stu1 and hasActiveRoom=False for stu2
    me1 = stu1_client.get("/api/v1/auth/me").get_json()["user"]
    assert me1["hasActiveRoom"] is True
    assert me1["room"] == "A-204"
    assert me1["block"] == "Aryabhatta Block"

    me2 = stu2_client.get("/api/v1/auth/me").get_json()["user"]
    assert me2["hasActiveRoom"] is False
    assert me2["room"] == "Unassigned"

    # 2. Student 1 submits a room complaint with free-text description and omitted category
    create1 = stu1_client.post(
        "/api/v1/student/complaints",
        headers=stu1_headers,
        json={
            "title": "Ceiling fan regulator sparking and buzzing",
            "description": (
                "Every time the fan is set to speed 3, sparks come out of the switchboard."
            ),
            "priority": "high",
            "location_type": "room",
            # Attempt to spoof student_user_id/room_id -> must be ignored and derived from session
            "student_user_id": actors["stu2_id"],
            "room_id": 99999,
        },
    )
    assert create1.status_code == 201, create1.get_json()
    comp1 = create1.get_json()["complaint"]
    assert comp1["reference_no"].startswith("CMP-")
    assert comp1["status"] == "submitted"
    assert comp1["priority"] == "high"
    assert comp1["location_type"] == "room"
    assert comp1["room"] == "A-204"
    assert comp1["studentId"] == actors["stu1_id"]
    assert "internalNotes" not in comp1
    assert "internal_notes" not in comp1
    assert len(comp1["history"]) == 1
    assert comp1["history"][0]["action"] == "submitted"

    # 3. Student 2 (no active room allocation) tries to submit a room complaint -> rejected (400)
    bad_room_comp = stu2_client.post(
        "/api/v1/student/complaints",
        headers=stu2_headers,
        json={
            "title": "Room window latch broken",
            "description": "Window latch does not close.",
            "priority": "low",
            "location_type": "room",
        },
    )
    assert bad_room_comp.status_code == 400
    assert bad_room_comp.get_json()["error"]["code"] == "active_room_required"

    # 4. Student 2 submits a common-area complaint without location_detail -> rejected (400)
    missing_loc = stu2_client.post(
        "/api/v1/student/complaints",
        headers=stu2_headers,
        json={
            "title": "Water cooler leaking in corridor",
            "description": "Water pooling near the 2nd floor staircase.",
            "priority": "medium",
            "location_type": "common_area",
        },
    )
    assert missing_loc.status_code == 400
    assert missing_loc.get_json()["error"]["code"] == "validation_error"

    # 5. Student 2 submits a valid common-area complaint (D5 / ADR-019)
    create2 = stu2_client.post(
        "/api/v1/student/complaints",
        headers=stu2_headers,
        json={
            "title": "Water cooler leaking in corridor",
            "category": "Plumbing",
            "description": (
                "Water pooling near the 2nd floor staircase outside Aryabhatta reading hall."
            ),
            "priority": "medium",
            "location_type": "common_area",
            "location_detail": "2nd Floor Corridor near Reading Hall",
            "block_code": "BLKA",
        },
    )
    assert create2.status_code == 201, create2.get_json()
    comp2 = create2.get_json()["complaint"]
    assert comp2["location_type"] == "common_area"
    assert comp2["room_id"] is None
    assert comp2["location_detail"] == "2nd Floor Corridor near Reading Hall"
    assert comp2["block"] == "Aryabhatta Block"

    # 6. Ownership isolation: Student 2 cannot view Student 1's complaint
    forbidden_resp = stu2_client.get(f"/api/v1/student/complaints/{comp1['reference_no']}")
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.get_json()["error"]["code"] == "forbidden"

    # Student 1's list only contains comp1; Student 2's list only contains comp2
    list1 = stu1_client.get("/api/v1/student/complaints").get_json()["complaints"]
    assert [c["reference_no"] for c in list1] == [comp1["reference_no"]]

    list2 = stu2_client.get("/api/v1/student/complaints").get_json()["complaints"]
    assert [c["reference_no"] for c in list2] == [comp2["reference_no"]]


@pytest.mark.db
def test_complete_complaint_lifecycle_rework_reopen_reassign_and_privacy(phase3d_app):
    """Verify full end-to-end complaint lifecycle across Student, Admin, and Staff roles."""
    actors = _seed_complaint_actors(phase3d_app)
    stu_client = phase3d_app.test_client()
    admin_client = phase3d_app.test_client()
    stf1_client = phase3d_app.test_client()
    stf2_client = phase3d_app.test_client()

    stu_headers = _login_and_headers(stu_client, "aarav@hostelcare.test", "StudentPass123!")
    admin_headers = _login_and_headers(admin_client, "warden@hostelcare.test", "AdminPass123!")
    stf1_headers = _login_and_headers(stf1_client, "ramesh@hostelcare.test", "StaffPass123!")
    stf2_headers = _login_and_headers(stf2_client, "santosh@hostelcare.test", "StaffPass123!")

    # 1. Student submits complaint -> status = 'submitted'
    sub_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=stu_headers,
        json={
            "title": "Ceiling fan speed regulator sparking",
            "category": "Electrical",
            "description": "Regulator sparks when turned past level 2 in room A-204.",
            "priority": "high",
            "location_type": "room",
        },
    )
    assert sub_resp.status_code == 201
    ref_no = sub_resp.get_json()["complaint"]["reference_no"]

    # 2. Admin tries arbitrary status change via PATCH -> rejected (409)
    bad_patch = admin_client.patch(
        f"/api/v1/admin/complaints/{ref_no}",
        headers=admin_headers,
        json={"status": "closed"},
    )
    assert bad_patch.status_code == 409
    assert bad_patch.get_json()["error"]["code"] == "invalid_transition"

    # 3. Admin marks complaint under_review via PATCH -> status = 'under_review'
    rev_resp = admin_client.patch(
        f"/api/v1/admin/complaints/{ref_no}",
        headers=admin_headers,
        json={"status": "under_review", "note": "Warden reviewing electrical hazard."},
    )
    assert rev_resp.status_code == 200
    assert rev_resp.get_json()["complaint"]["status"] == "under_review"

    # 4. Admin adds a private internal note -> visible ONLY to admin
    note_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/internal-notes",
        headers=admin_headers,
        json={"body": "CONFIDENTIAL WARDEN NOTE: Check if whole wing wiring needs replacement."},
    )
    assert note_resp.status_code == 201
    admin_comp = note_resp.get_json()["complaint"]
    assert len(admin_comp["internalNotes"]) == 1
    assert "CONFIDENTIAL WARDEN NOTE" in admin_comp["internalNotes"][0]["body"]

    # Verify student view NEVER contains internal notes
    stu_view = stu_client.get(f"/api/v1/student/complaints/{ref_no}").get_json()["complaint"]
    assert "internalNotes" not in stu_view
    assert "internal_notes" not in stu_view
    assert "CONFIDENTIAL WARDEN NOTE" not in str(stu_view)

    # 5. Admin tries to assign to inactive staff member -> rejected (400)
    inactive_assign = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/assign",
        headers=admin_headers,
        json={"staff_id": actors["stf3_id"], "instructions": "Inspect room"},
    )
    assert inactive_assign.status_code == 400
    assert inactive_assign.get_json()["error"]["code"] == "staff_inactive"

    # 6. Admin assigns to Staff 1 (Ramesh Babu) -> status = 'assigned'
    assign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/assign",
        headers=admin_headers,
        json={
            "staff_id": actors["stf1_id"],
            "instructions": "Isolate MCB before opening the regulator box.",
        },
    )
    assert assign_resp.status_code == 200
    assert assign_resp.get_json()["complaint"]["status"] == "assigned"
    assert assign_resp.get_json()["complaint"]["assignedStaff"] == "Ramesh Babu"

    # Staff 1 can view the task (and never sees internalNotes), while Staff 2 gets 403
    stf1_view = stf1_client.get(f"/api/v1/staff/tasks/{ref_no}")
    assert stf1_view.status_code == 200
    stf1_task = stf1_view.get_json()["task"]
    assert stf1_task["instructions"] == "Isolate MCB before opening the regulator box."
    assert "internalNotes" not in stf1_task
    assert "internal_notes" not in stf1_task
    assert "CONFIDENTIAL WARDEN NOTE" not in str(stf1_task)

    stf2_denied = stf2_client.get(f"/api/v1/staff/tasks/{ref_no}")
    assert stf2_denied.status_code == 403

    # 7. Admin reassigns from Staff 1 to Staff 2 -> previous assignment closed, Staff 1 loses access
    reassign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reassign",
        headers=admin_headers,
        json={
            "staff_id": actors["stf2_id"],
            "instructions": "Ramesh is at Block C; please handle urgent inspection.",
            "reason": "Shift balancing",
        },
    )
    assert reassign_resp.status_code == 200
    reassigned_comp = reassign_resp.get_json()["complaint"]
    assert reassigned_comp["assignedStaff"] == "Santosh Kumar"
    assert len(reassigned_comp["previousAssignments"]) == 1
    assert reassigned_comp["previousAssignments"][0]["staffName"] == "Ramesh Babu"

    # Staff 1 immediately loses access (403) and cannot accept or view the task
    assert stf1_client.get(f"/api/v1/staff/tasks/{ref_no}").status_code == 403
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/accept",
            headers=stf1_headers,
        ).status_code
        == 403
    )
    assert stf1_client.get("/api/v1/staff/tasks").get_json()["tasks"] == []

    # 8. Staff 2 tries to start work before accepting -> rejected (409)
    premature_start = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/start",
        headers=stf2_headers,
        json={},
    )
    assert premature_start.status_code == 409

    # 9. Staff 2 accepts assignment -> status = 'accepted'
    acc_resp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/accept",
        headers=stf2_headers,
    )
    assert acc_resp.status_code == 200
    assert acc_resp.get_json()["task"]["status"] == "accepted"

    # Once accepted, admin can no longer reject the complaint (D4 / ADR-020)
    late_reject = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reject",
        headers=admin_headers,
        json={"reason": "Too late to reject after acceptance"},
    )
    assert late_reject.status_code == 409

    # 10. Staff 2 starts work -> status = 'in_progress'
    start_resp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/start",
        headers=stf2_headers,
        json={"note": "Opened switchboard and testing regulator capacitor."},
    )
    assert start_resp.status_code == 200
    assert start_resp.get_json()["task"]["status"] == "in_progress"

    # 11. Staff 2 posts a student-visible progress update
    upd_resp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/updates",
        headers=stf2_headers,
        json={"body": "Obtained new modular step regulator from hostel maintenance store."},
    )
    assert upd_resp.status_code == 201
    assert len(upd_resp.get_json()["task"]["updates"]) == 2

    # 12. Staff 2 tries to complete without a completion note -> rejected (400)
    empty_comp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/complete",
        headers=stf2_headers,
        json={"note": "   "},
    )
    assert empty_comp.status_code == 400

    # 13. Staff 2 completes work with mandatory completion note -> status = 'completed'
    comp_resp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/complete",
        headers=stf2_headers,
        json={"note": "Replaced faulty regulator and verified speeds 1-5 without sparking."},
    )
    assert comp_resp.status_code == 200
    completed_task = comp_resp.get_json()["task"]
    assert completed_task["status"] == "completed"
    assert completed_task["completed_at"] is not None
    assert (
        completed_task["completionNote"]
        == "Replaced faulty regulator and verified speeds 1-5 without sparking."
    )

    # 14. Admin returns for rework without a reason -> rejected (400)
    empty_rework = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/return-for-rework",
        headers=admin_headers,
        json={"reason": ""},
    )
    assert empty_rework.status_code == 400

    # 15. Admin returns for rework with mandatory reason -> 'in_progress', completed_at = None
    rework_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/return-for-rework",
        headers=admin_headers,
        json={"reason": "Please also secure the loose faceplate screws on the switchboard."},
    )
    assert rework_resp.status_code == 200
    reworked_comp = rework_resp.get_json()["complaint"]
    assert reworked_comp["status"] == "in_progress"
    assert reworked_comp["completed_at"] is None
    assert (
        reworked_comp["reworkNote"]
        == "Please also secure the loose faceplate screws on the switchboard."
    )

    # 16. Staff 2 completes work again -> status = 'completed'
    recomp_resp = stf2_client.post(
        f"/api/v1/staff/tasks/{ref_no}/complete",
        headers=stf2_headers,
        json={"note": "Secured faceplate with new brass machine screws and re-verified."},
    )
    assert recomp_resp.status_code == 200
    assert recomp_resp.get_json()["task"]["status"] == "completed"

    # 17. Admin closes the completed complaint -> status = 'closed'
    close_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/close",
        headers=admin_headers,
        json={"note": "Warden inspected room A-204; work is satisfactory."},
    )
    assert close_resp.status_code == 200
    closed_comp = close_resp.get_json()["complaint"]
    assert closed_comp["status"] == "closed"
    assert closed_comp["completed_at"] is not None
    assert closed_comp["closed_at"] is not None

    # 18. Admin reopens the closed complaint (D3 / ADR-020) -> requires mandatory reason
    empty_reopen = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reopen",
        headers=admin_headers,
        json={"reason": "  "},
    )
    assert empty_reopen.status_code == 400

    reopen_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reopen",
        headers=admin_headers,
        json={"reason": "Student reported intermittent humming returned after 2 hours."},
    )
    assert reopen_resp.status_code == 200
    reopened_comp = reopen_resp.get_json()["complaint"]
    assert reopened_comp["status"] == "under_review"
    assert reopened_comp["completed_at"] is None
    assert reopened_comp["closed_at"] is None
    assert reopened_comp["assignedStaff"] is None
    assert len(reopened_comp["previousAssignments"]) == 2

    # 19. Verify complete history and audit trail in PostgreSQL
    with phase3d_app.app_context():
        comp_row = db.session.execute(
            select(Complaint).where(Complaint.reference_no == ref_no)
        ).scalar_one()
        hist_actions = list(
            db.session.execute(
                select(ComplaintHistory.action)
                .where(ComplaintHistory.complaint_id == comp_row.id)
                .order_by(ComplaintHistory.id.asc())
            )
            .scalars()
            .all()
        )
        assert hist_actions == [
            "submitted",
            "review_started",
            "assigned",
            "reassigned",
            "accepted",
            "work_started",
            "progress_updated",
            "completed",
            "returned_for_rework",
            "completed",
            "closed",
            "reopened",
        ]

        # Verify audit logs recorded internal_note_added WITHOUT leaking the private note text
        audit_rows = list(
            db.session.execute(
                select(AuditLog).where(AuditLog.target_id == ref_no).order_by(AuditLog.id.asc())
            )
            .scalars()
            .all()
        )
        audit_actions = [a.action for a in audit_rows]
        assert "complaint.internal_note_added" in audit_actions
        assert "complaint.reopened" in audit_actions
        for a in audit_rows:
            assert "CONFIDENTIAL WARDEN NOTE" not in str(a.metadata_json)


@pytest.mark.db
def test_pre_acceptance_rejection_and_notifications_isolation(phase3d_app):
    """Verify pre-acceptance complaint rejection, admin filters, and notification ownership."""
    actors = _seed_complaint_actors(phase3d_app)
    stu_client = phase3d_app.test_client()
    admin_client = phase3d_app.test_client()
    stf1_client = phase3d_app.test_client()

    stu_headers = _login_and_headers(stu_client, "aarav@hostelcare.test", "StudentPass123!")
    admin_headers = _login_and_headers(admin_client, "warden@hostelcare.test", "AdminPass123!")
    stf1_headers = _login_and_headers(stf1_client, "ramesh@hostelcare.test", "StaffPass123!")

    # Student submits complaint
    sub_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=stu_headers,
        json={
            "title": "Duplicate request for balcony bulb",
            "category": "Electrical",
            "description": "Duplicate submission of earlier request.",
            "priority": "low",
            "location_type": "room",
        },
    )
    ref_no = sub_resp.get_json()["complaint"]["reference_no"]

    # Admin assigns to Staff 1 (status = 'assigned', pre-acceptance)
    admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/assign",
        headers=admin_headers,
        json={"staff_id": actors["stf1_id"], "instructions": "Check bulb"},
    )

    # Reject without reason -> 400
    no_reason = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reject",
        headers=admin_headers,
        json={"reason": ""},
    )
    assert no_reason.status_code == 400

    # Reject with reason while status is 'assigned' (pre-acceptance) -> 200, ends open assignment
    rej_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reject",
        headers=admin_headers,
        json={"reason": "Duplicate of existing maintenance ticket."},
    )
    assert rej_resp.status_code == 200
    rej_comp = rej_resp.get_json()["complaint"]
    assert rej_comp["status"] == "rejected"
    assert rej_comp["rejection_reason"] == "Duplicate of existing maintenance ticket."
    assert rej_comp["assignedStaff"] is None

    # Verify open assignment was closed in DB
    with phase3d_app.app_context():
        open_assigns = list(
            db.session.execute(
                select(ComplaintAssignment).where(ComplaintAssignment.ended_at.is_(None))
            )
            .scalars()
            .all()
        )
        assert open_assigns == []

    # Test Admin filtering (status=rejected, priority=low, q=balcony)
    filtered = admin_client.get(
        "/api/v1/admin/complaints?status=rejected&priority=low&q=balcony"
    ).get_json()["complaints"]
    assert len(filtered) == 1
    assert filtered[0]["reference_no"] == ref_no

    # Test Notifications listing & strict ownership
    stu_notifs_resp = stu_client.get("/api/v1/notifications").get_json()
    stu_notifs = stu_notifs_resp["notifications"]
    assert len(stu_notifs) >= 3  # submitted, assigned, rejected
    assert stu_notifs_resp["unread_count"] >= 3

    stf_notifs = stf1_client.get("/api/v1/notifications").get_json()["notifications"]
    assert len(stf_notifs) >= 2  # assigned, rejected

    # Staff 1 cannot mark Student 1's notification as read -> 403 Forbidden
    stu_notif_id = stu_notifs[0]["id"]
    cross_read = stf1_client.post(
        f"/api/v1/notifications/{stu_notif_id}/read",
        headers=stf1_headers,
    )
    assert cross_read.status_code == 403

    # Student 1 marks a single notification as read -> 200
    read_one = stu_client.post(
        f"/api/v1/notifications/{stu_notif_id}/read",
        headers=stu_headers,
    )
    assert read_one.status_code == 200
    assert read_one.get_json()["notification"]["read"] is True

    # Student 1 marks all remaining notifications as read -> 200
    read_all = stu_client.post("/api/v1/notifications/read-all", headers=stu_headers)
    assert read_all.status_code == 200
    assert stu_client.get("/api/v1/notifications").get_json()["unread_count"] == 0

    # Staff 1's notifications remain unread!
    assert stf1_client.get("/api/v1/notifications").get_json()["unread_count"] >= 2
    with phase3d_app.app_context():
        unread_rows = list(
            db.session.execute(select(Notification).where(Notification.read_at.is_(None)))
            .scalars()
            .all()
        )
        assert len(unread_rows) >= 2


@pytest.mark.db
def test_concurrent_duplicate_transitions_and_rbac_enforcement(phase3d_app):
    """Verify duplicate/concurrent transition guards and strict RBAC across complaint endpoints."""
    actors = _seed_complaint_actors(phase3d_app)
    stu_client = phase3d_app.test_client()
    admin_client = phase3d_app.test_client()
    stf1_client = phase3d_app.test_client()

    stu_headers = _login_and_headers(stu_client, "aarav@hostelcare.test", "StudentPass123!")
    admin_headers = _login_and_headers(admin_client, "warden@hostelcare.test", "AdminPass123!")
    stf1_headers = _login_and_headers(stf1_client, "ramesh@hostelcare.test", "StaffPass123!")

    # Student creates complaint
    sub = stu_client.post(
        "/api/v1/student/complaints",
        headers=stu_headers,
        json={
            "title": "Study table drawer stuck",
            "category": "Furniture",
            "description": "Right side drawer rail is bent.",
            "priority": "medium",
            "location_type": "room",
        },
    ).get_json()["complaint"]
    ref_no = sub["reference_no"]

    # RBAC: Student cannot access admin or staff endpoints
    assert stu_client.get("/api/v1/admin/complaints").status_code == 403
    assert stu_client.get("/api/v1/staff/tasks").status_code == 403
    assert (
        stu_client.post(
            f"/api/v1/admin/complaints/{ref_no}/close",
            headers=stu_headers,
        ).status_code
        == 403
    )

    # RBAC: Staff cannot access admin or student complaint endpoints
    assert stf1_client.get("/api/v1/admin/complaints").status_code == 403
    assert stf1_client.get("/api/v1/student/complaints").status_code == 403
    assert (
        stf1_client.post(
            f"/api/v1/admin/complaints/{ref_no}/close",
            headers=stf1_headers,
        ).status_code
        == 403
    )
    assert (
        stf1_client.post(
            f"/api/v1/admin/complaints/{ref_no}/reject",
            headers=stf1_headers,
            json={"reason": "Staff trying to reject"},
        ).status_code
        == 403
    )

    # Admin assigns to Staff 1 -> 200
    assert (
        admin_client.post(
            f"/api/v1/admin/complaints/{ref_no}/assign",
            headers=admin_headers,
            json={"staff_id": actors["stf1_id"], "instructions": "Inspect drawer rail"},
        ).status_code
        == 200
    )

    # Duplicate initial assign while already 'assigned' -> 409
    dup_assign = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/assign",
        headers=admin_headers,
        json={"staff_id": actors["stf2_id"], "instructions": "Second assign"},
    )
    assert dup_assign.status_code == 409

    # Reassigning to the same staff member -> 400
    same_staff = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reassign",
        headers=admin_headers,
        json={"staff_id": actors["stf1_id"], "instructions": "Same staff"},
    )
    assert same_staff.status_code == 400
    assert same_staff.get_json()["error"]["code"] == "same_staff"

    # Staff 1 accepts -> 200, second accept -> 409
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/accept",
            headers=stf1_headers,
        ).status_code
        == 200
    )
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/accept",
            headers=stf1_headers,
        ).status_code
        == 409
    )

    # Staff 1 starts -> 200, second start -> 409
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/start",
            headers=stf1_headers,
            json={},
        ).status_code
        == 200
    )
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/start",
            headers=stf1_headers,
            json={},
        ).status_code
        == 409
    )

    # Admin cannot close while 'in_progress' -> 409
    assert (
        admin_client.post(
            f"/api/v1/admin/complaints/{ref_no}/close",
            headers=admin_headers,
        ).status_code
        == 409
    )

    # Staff 1 completes -> 200, second complete -> 409
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/complete",
            headers=stf1_headers,
            json={"note": "Drawer channel lubricated and aligned."},
        ).status_code
        == 200
    )
    assert (
        stf1_client.post(
            f"/api/v1/staff/tasks/{ref_no}/complete",
            headers=stf1_headers,
            json={"note": "Duplicate completion"},
        ).status_code
        == 409
    )


@pytest.mark.db
def test_student_complaint_ownership_idor_and_roommate_isolation(phase3d_app):
    """Verify strict student ownership, IDOR defense (ref & numeric ID), and roommate isolation."""
    actors = _seed_complaint_actors(phase3d_app)

    # Allocate Student B (Rohan Verma) into Bed 1 of the EXACT SAME room (A-204) as Student A
    with phase3d_app.app_context():
        admin_user = db.session.execute(
            select(User).where(User.email == "warden@hostelcare.test")
        ).scalar_one()
        room_204 = db.session.execute(select(Room).where(Room.room_number == "A-204")).scalar_one()
        stu_b = User(
            email="rohan.verma@hostelcare.test",
            full_name="Rohan Verma",
            phone="+91 98123 45670",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add(stu_b)
        db.session.flush()
        db.session.add(
            StudentProfile(
                user_id=stu_b.id,
                roll_number="2026CSB1043",
                reviewed_by=admin_user.id,
                reviewed_at=datetime.now(UTC),
                review_note="Approved roommate",
            )
        )
        db.session.add(
            RoomAllocation(
                student_user_id=stu_b.id,
                room_id=room_204.id,
                bed_number=1,
                start_date=date.today() - timedelta(days=5),
                allocated_by=admin_user.id,
            )
        )
        db.session.commit()
        stu_b_public_id = str(stu_b.public_id)

    stu_a_client = phase3d_app.test_client()
    stu_b_client = phase3d_app.test_client()
    admin_client = phase3d_app.test_client()
    stf1_client = phase3d_app.test_client()

    stu_a_headers = _login_and_headers(stu_a_client, "aarav@hostelcare.test", "StudentPass123!")
    stu_b_headers = _login_and_headers(
        stu_b_client, "rohan.verma@hostelcare.test", "StudentPass123!"
    )
    admin_headers = _login_and_headers(admin_client, "warden@hostelcare.test", "AdminPass123!")
    stf1_headers = _login_and_headers(stf1_client, "ramesh@hostelcare.test", "StaffPass123!")

    # Student A & roommate Student B each create a room complaint in A-204
    sub_a = stu_a_client.post(
        "/api/v1/student/complaints",
        headers=stu_a_headers,
        json={
            "title": "Desk lamp socket sparking on Bed 2",
            "category": "Electrical",
            "description": "Secret A detail: desk outlet near window sparks.",
            "priority": "high",
            "location_type": "room",
        },
    )
    assert sub_a.status_code == 201
    ref_a = sub_a.get_json()["complaint"]["reference_no"]

    sub_b = stu_b_client.post(
        "/api/v1/student/complaints",
        headers=stu_b_headers,
        json={
            "title": "Wardrobe hinge broken on Bed 1",
            "category": "Furniture",
            "description": "Secret B detail: private locker door hinge snapped.",
            "priority": "medium",
            "location_type": "room",
        },
    )
    assert sub_b.status_code == 201
    ref_b = sub_b.get_json()["complaint"]["reference_no"]

    # Admin assigns both to Staff 1 & logs confidential warden internal notes on both
    for ref, note_text in (
        (ref_a, "CONFIDENTIAL WARDEN NOTE A: Check breaker panel logs."),
        (ref_b, "CONFIDENTIAL WARDEN NOTE B: Student B reported prior damage."),
    ):
        assert (
            admin_client.post(
                f"/api/v1/admin/complaints/{ref}/assign",
                headers=admin_headers,
                json={"staff_id": actors["stf1_id"], "instructions": f"Staff dispatch {ref}"},
            ).status_code
            == 200
        )
        assert (
            admin_client.post(
                f"/api/v1/admin/complaints/{ref}/internal-notes",
                headers=admin_headers,
                json={"note": note_text},
            ).status_code
            == 201
        )
        assert (
            stf1_client.post(
                f"/api/v1/staff/tasks/{ref}/accept",
                headers=stf1_headers,
            ).status_code
            == 200
        )
        assert (
            stf1_client.post(
                f"/api/v1/staff/tasks/{ref}/start",
                headers=stf1_headers,
                json={"note": f"Work started on {ref}"},
            ).status_code
            == 200
        )
        assert (
            stf1_client.post(
                f"/api/v1/staff/tasks/{ref}/updates",
                headers=stf1_headers,
                json={"body": f"Progress update visible only to owner of {ref}"},
            ).status_code
            == 201
        )

    # Fetch internal integer primary keys & baseline state for B
    with phase3d_app.app_context():
        comp_a_row = db.session.execute(
            select(Complaint).where(Complaint.reference_no == ref_a)
        ).scalar_one()
        comp_b_row = db.session.execute(
            select(Complaint).where(Complaint.reference_no == ref_b)
        ).scalar_one()
        id_a = comp_a_row.id
        id_b = comp_b_row.id
        b_hist_count_before = len(
            db.session.execute(
                select(ComplaintHistory).where(ComplaintHistory.complaint_id == id_b)
            )
            .scalars()
            .all()
        )
        b_status_before = comp_b_row.status

    # 1. Student A can list & view A's complaint (by ref_no and numeric id)
    list_a = stu_a_client.get(
        f"/api/v1/student/complaints?student_id={stu_b_public_id}"
        f"&roll_number=2026CSB1043&room=A-204"
    )
    assert list_a.status_code == 200
    a_refs = [c["reference_no"] for c in list_a.get_json()["complaints"]]
    assert a_refs == [ref_a]

    for ident in (ref_a, str(id_a)):
        detail_a = stu_a_client.get(f"/api/v1/student/complaints/{ident}")
        assert detail_a.status_code == 200
        body_a = detail_a.get_json()["complaint"]
        assert body_a["reference_no"] == ref_a
        assert "internal_notes" not in body_a
        assert "internalNotes" not in body_a
        assert "instructions" not in body_a
        assert "assignmentNotes" not in body_a
        assert "CONFIDENTIAL WARDEN NOTE A" not in str(detail_a.get_json())

    # 2. Student B can list & view B's complaint (by ref_no and numeric id)
    list_b = stu_b_client.get("/api/v1/student/complaints")
    assert list_b.status_code == 200
    assert [c["reference_no"] for c in list_b.get_json()["complaints"]] == [ref_b]
    for ident in (ref_b, str(id_b)):
        detail_b = stu_b_client.get(f"/api/v1/student/complaints/{ident}")
        assert detail_b.status_code == 200
        assert detail_b.get_json()["complaint"]["reference_no"] == ref_b
        assert "CONFIDENTIAL WARDEN NOTE B" not in str(detail_b.get_json())

    # 3 & 4 & 5 & 9. Roommates A and B cannot view each other's complaints (ref or numeric id)
    for ident_b in (ref_b, str(id_b)):
        resp = stu_a_client.get(f"/api/v1/student/complaints/{ident_b}")
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "forbidden"
        assert "Secret B detail" not in str(resp.get_json())
        assert "complaint" not in resp.get_json()

    for ident_a in (ref_a, str(id_a)):
        resp = stu_b_client.get(f"/api/v1/student/complaints/{ident_a}")
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "forbidden"
        assert "Secret A detail" not in str(resp.get_json())

    # Non-existent identifier returns 404
    assert stu_a_client.get("/api/v1/student/complaints/CMP-2099-99999").status_code == 404
    assert stu_a_client.get("/api/v1/student/complaints/999999").status_code == 404

    # 6. Student A cannot post updates, modify, or reopen B's complaint (nor call staff/admin)
    unauthorized_mutations = [
        stu_a_client.patch(
            f"/api/v1/student/complaints/{ref_b}",
            headers=stu_a_headers,
            json={"priority": "low", "title": "Tampered"},
        ),
        stu_a_client.patch(
            f"/api/v1/student/complaints/{id_b}",
            headers=stu_a_headers,
            json={"priority": "low"},
        ),
        stu_a_client.post(
            f"/api/v1/student/complaints/{ref_b}/updates",
            headers=stu_a_headers,
            json={"body": "Unauthorized student update"},
        ),
        stu_a_client.post(
            f"/api/v1/student/complaints/{ref_b}/reopen",
            headers=stu_a_headers,
            json={"reason": "Unauthorized reopen"},
        ),
        stu_a_client.post(
            f"/api/v1/staff/tasks/{ref_b}/updates",
            headers=stu_a_headers,
            json={"body": "Staff update attempt by student"},
        ),
        stu_a_client.patch(
            f"/api/v1/admin/complaints/{ref_b}",
            headers=stu_a_headers,
            json={"priority": "low"},
        ),
        stu_a_client.post(
            f"/api/v1/admin/complaints/{ref_b}/reopen",
            headers=stu_a_headers,
            json={"reason": "Admin reopen attempt by student"},
        ),
    ]
    for res in unauthorized_mutations:
        assert res.status_code == 403

    # Verify DB record for B was untouched
    with phase3d_app.app_context():
        b_after = db.session.execute(select(Complaint).where(Complaint.id == id_b)).scalar_one()
        b_hist_count_after = len(
            db.session.execute(
                select(ComplaintHistory).where(ComplaintHistory.complaint_id == id_b)
            )
            .scalars()
            .all()
        )
        assert b_after.status == b_status_before
        assert b_after.title == "Wardrobe hinge broken on Bed 1"
        assert b_hist_count_after == b_hist_count_before

    # 7 & 8. History & updates isolation + no internal notes in history/updates
    hist_a = stu_a_client.get(f"/api/v1/student/complaints/{ref_a}/history")
    assert hist_a.status_code == 200
    assert len(hist_a.get_json()["history"]) >= 1
    assert "CONFIDENTIAL WARDEN NOTE A" not in str(hist_a.get_json())

    upds_a = stu_a_client.get(f"/api/v1/student/complaints/{ref_a}/updates")
    assert upds_a.status_code == 200
    assert len(upds_a.get_json()["updates"]) >= 1
    assert "CONFIDENTIAL WARDEN NOTE A" not in str(upds_a.get_json())

    for ident_b in (ref_b, str(id_b)):
        assert stu_a_client.get(f"/api/v1/student/complaints/{ident_b}/history").status_code == 403
        assert stu_a_client.get(f"/api/v1/student/complaints/{ident_b}/updates").status_code == 403

    # 9. Notifications remain strictly isolated between roommates in A-204
    notifs_a_str = str(stu_a_client.get("/api/v1/notifications").get_json()["notifications"])
    notifs_b_str = str(stu_b_client.get("/api/v1/notifications").get_json()["notifications"])
    assert ref_a in notifs_a_str
    assert ref_b not in notifs_a_str
    assert ref_b in notifs_b_str
    assert ref_a not in notifs_b_str

    # Regression check: Staff & Admin retain their full authorized access
    staff_task_a = stf1_client.get(f"/api/v1/staff/tasks/{ref_a}")
    assert staff_task_a.status_code == 200
    assert staff_task_a.get_json()["task"]["instructions"] == f"Staff dispatch {ref_a}"
    assert "CONFIDENTIAL WARDEN NOTE A" not in str(staff_task_a.get_json())

    admin_comp_b = admin_client.get(f"/api/v1/admin/complaints/{ref_b}")
    assert admin_comp_b.status_code == 200
    assert len(admin_comp_b.get_json()["complaint"]["internalNotes"]) == 1


@pytest.mark.db
def test_internal_notes_excluded_from_public_complaint_history(phase3d_app):
    """Verify warden notes, dispatch instructions, and review remarks never leak
    into student/staff history.
    """
    actors = _seed_complaint_actors(phase3d_app)
    stu_client = phase3d_app.test_client()
    admin_client = phase3d_app.test_client()
    stf1_client = phase3d_app.test_client()
    stf2_client = phase3d_app.test_client()

    stu_headers = _login_and_headers(stu_client, "aarav@hostelcare.test", "StudentPass123!")
    admin_headers = _login_and_headers(admin_client, "warden@hostelcare.test", "AdminPass123!")
    _login_and_headers(stf1_client, "ramesh@hostelcare.test", "StaffPass123!")
    _login_and_headers(stf2_client, "santosh@hostelcare.test", "StaffPass123!")

    # 1. Student submits complaint
    sub_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=stu_headers,
        json={
            "title": "Switchboard humming loudly",
            "category": "Electrical",
            "description": "Loud hum from switchboard near study desk.",
            "priority": "high",
            "location_type": "room",
        },
    )
    assert sub_resp.status_code == 201
    ref_no = sub_resp.get_json()["complaint"]["reference_no"]

    # 2. Administrative review with private remark
    rev_resp = admin_client.patch(
        f"/api/v1/admin/complaints/{ref_no}",
        headers=admin_headers,
        json={
            "action": "start_review",
            "note": "PRIVATE REVIEW REMARK: Check if student overloaded socket.",
        },
    )
    assert rev_resp.status_code == 200

    # Student history hides private review remark while preserving public review_started event
    stu_comp = stu_client.get(f"/api/v1/student/complaints/{ref_no}").get_json()["complaint"]
    assert "PRIVATE REVIEW REMARK" not in str(stu_comp)
    review_events = [h for h in stu_comp["history"] if h["action_code"] == "review_started"]
    assert len(review_events) == 1
    assert (
        review_events[0]["note"]
        == "Complaint acknowledged by warden and placed under administrative review."
    )

    # Admin still sees the preserved review remark in admin history
    adm_comp = admin_client.get(f"/api/v1/admin/complaints/{ref_no}").get_json()["complaint"]
    adm_review = [h for h in adm_comp["history"] if h["action_code"] == "review_started"]
    assert "PRIVATE REVIEW REMARK" in adm_review[0]["note"]

    # 3. Assignment with confidential instructions
    assign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/assign",
        headers=admin_headers,
        json={
            "staff_id": actors["stf1_id"],
            "instructions": "Fix it as soon as possible - private dispatch instruction",
        },
    )
    assert assign_resp.status_code == 200

    # Student detail & history do not contain instructions or Warden Note
    stu_comp = stu_client.get(f"/api/v1/student/complaints/{ref_no}").get_json()["complaint"]
    stu_hist = stu_client.get(f"/api/v1/student/complaints/{ref_no}/history").get_json()["history"]
    assert "Fix it as soon as possible" not in str(stu_comp)
    assert "Warden Note:" not in str(stu_comp)
    assert "Fix it as soon as possible" not in str(stu_hist)
    assign_events = [h for h in stu_hist if h["action_code"] == "assigned"]
    assert len(assign_events) == 1
    assert assign_events[0]["note"] == "Assigned to Ramesh Babu (Electrician)."

    # Assigned staff receives dispatch instructions on task detail, but NOT in public history
    stf1_task = stf1_client.get(f"/api/v1/staff/tasks/{ref_no}").get_json()["task"]
    assert stf1_task["instructions"] == "Fix it as soon as possible - private dispatch instruction"
    assert "Fix it as soon as possible" not in str(stf1_task["history"])
    assert "PRIVATE REVIEW REMARK" not in str(stf1_task["history"])
    stf1_assign_events = [h for h in stf1_task["history"] if h["action_code"] == "assigned"]
    assert stf1_assign_events[0]["note"] == "Assigned to Ramesh Babu (Electrician)."

    # 4. Reassignment with confidential instructions
    reassign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{ref_no}/reassign",
        headers=admin_headers,
        json={
            "staff_id": actors["stf2_id"],
            "instructions": "SECRET REASSIGNMENT INSTRUCTION: Inspect main breaker.",
        },
    )
    assert reassign_resp.status_code == 200

    # Student and Staff history hide reassignment instructions while preserving public event
    stu_hist_after = stu_client.get(f"/api/v1/student/complaints/{ref_no}/history").get_json()[
        "history"
    ]
    assert "SECRET REASSIGNMENT INSTRUCTION" not in str(stu_hist_after)
    reassign_events = [h for h in stu_hist_after if h["action_code"] == "reassigned"]
    assert len(reassign_events) == 1
    assert reassign_events[0]["note"] == "Reassigned from Ramesh Babu to Santosh Kumar (Plumber)."

    stf2_task = stf2_client.get(f"/api/v1/staff/tasks/{ref_no}").get_json()["task"]
    assert stf2_task["instructions"] == "SECRET REASSIGNMENT INSTRUCTION: Inspect main breaker."
    assert "SECRET REASSIGNMENT INSTRUCTION" not in str(stf2_task["history"])
    stf2_reassign_events = [h for h in stf2_task["history"] if h["action_code"] == "reassigned"]
    assert (
        stf2_reassign_events[0]["note"] == "Reassigned from Ramesh Babu to Santosh Kumar (Plumber)."
    )

    # 5. Legacy historical records containing Warden Note: and Instructions: suffixes
    with phase3d_app.app_context():
        admin_user = db.session.execute(
            select(User).where(User.public_id == actors["admin_id"])
        ).scalar_one()
        comp_row = db.session.execute(
            select(Complaint).where(Complaint.reference_no == ref_no)
        ).scalar_one()
        legacy_assign = ComplaintHistory(
            complaint_id=comp_row.id,
            actor_user_id=admin_user.id,
            action="assigned",
            from_status="under_review",
            to_status="assigned",
            note="Assigned to Ramesh Babu (Electrician). Warden Note: Legacy secret note",
        )
        legacy_reassign = ComplaintHistory(
            complaint_id=comp_row.id,
            actor_user_id=admin_user.id,
            action="reassigned",
            from_status="assigned",
            to_status="assigned",
            note=(
                "Reassigned from Ramesh Babu to Santosh Kumar (Plumber). "
                "Instructions: Legacy secret instruction"
            ),
        )
        db.session.add_all([legacy_assign, legacy_reassign])
        db.session.commit()
        legacy_assign_id = legacy_assign.id
        legacy_reassign_id = legacy_reassign.id

    # Both student and staff serializers hide legacy suffixes while preserving public text
    stu_legacy_hist = stu_client.get(f"/api/v1/student/complaints/{ref_no}/history").get_json()[
        "history"
    ]
    assert "Legacy secret note" not in str(stu_legacy_hist)
    assert "Legacy secret instruction" not in str(stu_legacy_hist)
    assert "Warden Note:" not in str(stu_legacy_hist)

    legacy_assign_out = next(h for h in stu_legacy_hist if h["id"] == legacy_assign_id)
    legacy_reassign_out = next(h for h in stu_legacy_hist if h["id"] == legacy_reassign_id)
    assert legacy_assign_out["note"] == "Assigned to Ramesh Babu (Electrician)."
    assert legacy_reassign_out["note"] == "Reassigned from Ramesh Babu to Santosh Kumar (Plumber)."

    stf2_legacy_task = stf2_client.get(f"/api/v1/staff/tasks/{ref_no}").get_json()["task"]
    assert "Legacy secret note" not in str(stf2_legacy_task["history"])
    assert "Legacy secret instruction" not in str(stf2_legacy_task["history"])

    # Database records remain untouched
    with phase3d_app.app_context():
        db_assign = db.session.get(ComplaintHistory, legacy_assign_id)
        db_reassign = db.session.get(ComplaintHistory, legacy_reassign_id)
        assert "Warden Note: Legacy secret note" in db_assign.note
        assert "Instructions: Legacy secret instruction" in db_reassign.note
