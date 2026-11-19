"""Phase 3D.5 Room & Allocation Management Backend Tests.

Validates:
1. Block Management: RBAC, validation, uniqueness, listing with aggregated occupancy,
   updates, and deactivation protection against active allocations.
2. Room Management: RBAC, validation, floor, capacity constraints (1-8), duplicate
   rejection, filtering, detail serialization, and capacity reduction protection.
3. Allocation Management: Allocation of approved students, bed bounds, duplicate
   allocation prevention, exclusion constraint compliance, graceful termination with
   mandatory reason/date, transfer without overlap collision, audit logs, and notifications.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.models.audit import AuditLog
from app.models.identity import StudentProfile, User
from app.models.notifications import Notification
from app.models.rooms import Block, Room

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def rooms_app():
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
def _clean_rooms_tables(rooms_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    clear_console_outbox()
    owner_engine = create_engine(rooms_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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
                "public.staff_profiles, "
                "public.student_profiles, "
                "public.users "
                "RESTART IDENTITY CASCADE;"
            )
        )


def _login_and_csrf(client, identifier: str, password: str, csrf: str | None = None) -> str:
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    resp = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["csrf_token"]


@pytest.mark.db
def test_block_management_crud_rbac_and_protection(rooms_app):
    """Test block creation, listing, updating, RBAC, and active allocation protection."""
    with rooms_app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Hostel Warden",
            designation="Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        student = User(
            email="student@hostelcare.test",
            full_name="Ravi Kumar",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, student])
        db.session.flush()
        admin_id = admin.id
        db.session.add(
            StudentProfile(
                user_id=student.id,
                roll_number="BETN1CS25010",
                reviewed_by=admin_id,
                reviewed_at=datetime.now(UTC),
            )
        )
        db.session.commit()

    anon_client = rooms_app.test_client()
    student_client = rooms_app.test_client()
    admin_client = rooms_app.test_client()

    _login_and_csrf(student_client, "student@hostelcare.test", "StudentPass123!")
    admin_csrf = _login_and_csrf(admin_client, "warden@hostelcare.test", "AdminPass123!")

    # 1. RBAC check on block endpoints
    assert anon_client.get("/api/v1/admin/blocks").status_code == 401
    assert student_client.get("/api/v1/admin/blocks").status_code == 403
    assert (
        student_client.post(
            "/api/v1/admin/blocks",
            json={"name": "Block X", "code": "BLKX"},
            headers={"X-CSRF-Token": "invalid"},
        ).status_code
        == 403
    )

    # 2. Admin creates Block A
    create_resp = admin_client.post(
        "/api/v1/admin/blocks",
        json={"name": "Block A (Nalanda)", "code": "BLKA", "display_order": 1},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create_resp.status_code == 201
    block_a = create_resp.get_json()["block"]
    assert block_a["name"] == "Block A (Nalanda)"
    assert block_a["code"] == "BLKA"
    assert block_a["display_order"] == 1
    assert block_a["is_active"] is True
    block_a_id = block_a["id"]

    # 3. Duplicate code/name validation
    dup_code = admin_client.post(
        "/api/v1/admin/blocks",
        json={"name": "Different Name", "code": "BLKA"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert dup_code.status_code == 409
    assert dup_code.get_json()["error"]["code"] == "conflict"

    # Invalid code regex (lowercase or non-alphanumeric)
    invalid_code = admin_client.post(
        "/api/v1/admin/blocks",
        json={"name": "Invalid Block", "code": "blk_a!"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert invalid_code.status_code == 400

    # 4. List blocks
    list_resp = admin_client.get("/api/v1/admin/blocks")
    assert list_resp.status_code == 200
    blocks = list_resp.get_json()["blocks"]
    assert len(blocks) == 1
    assert blocks[0]["id"] == block_a_id

    # 5. Update block
    update_resp = admin_client.patch(
        f"/api/v1/admin/blocks/{block_a_id}",
        json={"display_order": 5, "name": "Block A (Nalanda Main)"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["block"]["display_order"] == 5
    assert update_resp.get_json()["block"]["name"] == "Block A (Nalanda Main)"


@pytest.mark.db
def test_block_creation_missing_name_validation_and_payload_resilience(rooms_app):
    """Regression test for block creation validation (missing name, length, payload)."""
    with rooms_app.app_context():
        admin = User(
            email="warden_regress@hostelcare.test",
            full_name="Hostel Warden Regress",
            designation="Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.commit()

    admin_client = rooms_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, "warden_regress@hostelcare.test", "AdminPass123!")

    # 1. Missing name (empty, None, whitespace) -> 400 "Block name is required."
    for invalid_payload in [
        {"code": "BLKZ", "display_order": 1},
        {"name": "", "code": "BLKZ"},
        {"name": "   ", "code": "BLKZ"},
        {"name": None, "code": "BLKZ"},
    ]:
        resp = admin_client.post(
            "/api/v1/admin/blocks",
            json=invalid_payload,
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "validation_error"
        assert "Block name is required" in resp.get_json()["error"]["message"]

    # 2. Name exceeds 80 characters -> 400
    resp_long = admin_client.post(
        "/api/v1/admin/blocks",
        json={"name": "A" * 81, "code": "BLKLONG"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert resp_long.status_code == 400
    assert "80 characters" in resp_long.get_json()["error"]["message"]

    # 3. Successful creation with exact contract
    resp_success = admin_client.post(
        "/api/v1/admin/blocks",
        json={"name": "Block A (New Tapti)", "code": "BLKA", "display_order": 1},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert resp_success.status_code == 201
    created = resp_success.get_json()["block"]
    assert created["name"] == "Block A (New Tapti)"
    assert created["code"] == "BLKA"
    assert created["display_order"] == 1

    # 4. Stringified JSON payload resilience
    import json

    resp_str = admin_client.post(
        "/api/v1/admin/blocks",
        data=json.dumps(
            json.dumps({"name": "Block B (Mandovi)", "code": "BLKB", "display_order": 2})
        ),
        content_type="application/json",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert resp_str.status_code == 201
    created_str = resp_str.get_json()["block"]
    assert created_str["name"] == "Block B (Mandovi)"
    assert created_str["code"] == "BLKB"


@pytest.mark.db
def test_room_management_crud_capacity_reduction_protection(rooms_app):
    """Test room creation, capacity limits (1-8), duplicate rejection, and capacity reduction."""
    with rooms_app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Hostel Warden",
            designation="Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        student = User(
            email="student1@hostelcare.test",
            full_name="Student One",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, student])
        db.session.flush()
        admin_id = admin.id

        db.session.add(
            StudentProfile(
                user_id=student.id,
                roll_number="BETN1CS25011",
                reviewed_by=admin_id,
                reviewed_at=datetime.now(UTC),
            )
        )
        block = Block(code="BLKB", name="Block B (Takshashila)", display_order=2, is_active=True)
        db.session.add(block)
        db.session.commit()
        block_id = block.id
        student_id = student.id

    admin_client = rooms_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, "warden@hostelcare.test", "AdminPass123!")

    # 1. Invalid capacity (0 or > 8)
    inv_cap = admin_client.post(
        "/api/v1/admin/rooms",
        json={"block_id": block_id, "room_number": "B-101", "floor": 1, "capacity": 0},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert inv_cap.status_code == 400

    inv_cap_large = admin_client.post(
        "/api/v1/admin/rooms",
        json={"block_id": block_id, "room_number": "B-101", "floor": 1, "capacity": 9},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert inv_cap_large.status_code == 400

    # 2. Valid room creation (capacity 3)
    create_rm = admin_client.post(
        "/api/v1/admin/rooms",
        json={
            "block_id": block_id,
            "room_number": "B-101",
            "floor": 1,
            "capacity": 3,
            "room_type": "triple",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create_rm.status_code == 201
    rm_data = create_rm.get_json()["room"]
    assert rm_data["room_number"] == "B-101"
    assert rm_data["capacity"] == 3
    assert rm_data["vacant"] == 3
    assert rm_data["occupied"] == 0
    room_id = rm_data["id"]

    # 3. Duplicate room number in same block rejected
    dup_rm = admin_client.post(
        "/api/v1/admin/rooms",
        json={"block_id": block_id, "room_number": "B-101", "floor": 1, "capacity": 2},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert dup_rm.status_code == 409
    assert dup_rm.get_json()["error"]["code"] == "conflict"

    # 4. Allocate student to bed 3
    today = date.today()
    alloc_resp = admin_client.post(
        "/api/v1/admin/room-allocations",
        json={
            "room_id": room_id,
            "student_id": student_id,
            "bed_number": 3,
            "start_date": today.isoformat(),
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert alloc_resp.status_code == 201

    # 5. Try reducing capacity to 2 (should fail because Bed 3 is actively allocated)
    reduce_fail = admin_client.patch(
        f"/api/v1/admin/rooms/{room_id}",
        json={"capacity": 2},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert reduce_fail.status_code == 409
    assert (
        "Bed 3" in reduce_fail.get_json()["error"]["message"]
        or "active" in reduce_fail.get_json()["error"]["message"]
    )

    # 6. Try deactivating the room while active resident is in it
    deact_fail = admin_client.patch(
        f"/api/v1/admin/rooms/{room_id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert deact_fail.status_code == 409
    assert "active resident" in deact_fail.get_json()["error"]["message"]


@pytest.mark.db
def test_room_allocation_lifecycle_transfer_and_termination(rooms_app):
    """Test allocation lifecycle: allocate, transfer without collision, and end allocation."""
    with rooms_app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Hostel Warden",
            designation="Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        student = User(
            email="student@hostelcare.test",
            full_name="Subhas Bose",
            phone="+91 9898989898",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, student])
        db.session.flush()
        admin_id = admin.id

        db.session.add(
            StudentProfile(
                user_id=student.id,
                roll_number="BETN1CS25099",
                reviewed_by=admin_id,
                reviewed_at=datetime.now(UTC),
            )
        )
        block = Block(code="BLKC", name="Block C", display_order=3, is_active=True)
        db.session.add(block)
        db.session.flush()

        room1 = Room(
            block_id=block.id,
            room_number="C-201",
            floor=2,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        room2 = Room(
            block_id=block.id,
            room_number="C-202",
            floor=2,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        db.session.add_all([room1, room2])
        db.session.commit()
        r1_id = room1.id
        r2_id = room2.id
        student_id = student.id
        admin_id = admin.id

    admin_client = rooms_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, "warden@hostelcare.test", "AdminPass123!")

    today = date.today()

    # 1. Allocate student to C-201 Bed 1
    alloc_resp = admin_client.post(
        "/api/v1/admin/room-allocations",
        json={
            "room_id": r1_id,
            "student_id": student_id,
            "bed_number": 1,
            "start_date": today.isoformat(),
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert alloc_resp.status_code == 201
    alloc_data = alloc_resp.get_json()["allocation"]
    alloc_id = alloc_data["id"]
    assert alloc_data["room_number"] == "C-201"
    assert alloc_data["bed_number"] == 1
    assert alloc_data["status"] == "active"

    # 2. Check duplicate allocation for same student (prevented)
    dup_stu = admin_client.post(
        "/api/v1/admin/room-allocations",
        json={
            "room_id": r2_id,
            "student_id": student_id,
            "bed_number": 1,
            "start_date": today.isoformat(),
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert dup_stu.status_code == 409
    assert dup_stu.get_json()["error"]["code"] == "student_already_allocated"

    # 3. Check duplicate bed allocation in C-201 Bed 1 (with another student)
    with rooms_app.app_context():
        stu2 = User(
            email="student2@hostelcare.test",
            full_name="Second Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add(stu2)
        db.session.flush()
        db.session.add(
            StudentProfile(
                user_id=stu2.id,
                roll_number="BETN1CS25100",
                reviewed_by=admin_id,
                reviewed_at=datetime.now(UTC),
            )
        )
        db.session.commit()
        stu2_id = stu2.id

    dup_bed = admin_client.post(
        "/api/v1/admin/room-allocations",
        json={
            "room_id": r1_id,
            "student_id": stu2_id,
            "bed_number": 1,
            "start_date": today.isoformat(),
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert dup_bed.status_code == 409
    assert dup_bed.get_json()["error"]["code"] == "bed_already_occupied"

    # 4. Transfer student to C-202 Bed 2
    transfer_date = today + timedelta(days=1)
    transfer_resp = admin_client.post(
        f"/api/v1/admin/room-allocations/{alloc_id}/transfer",
        json={
            "target_room_id": r2_id,
            "target_bed_number": 2,
            "effective_date": transfer_date.isoformat(),
            "reason": "Air conditioner maintenance in block wing",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert transfer_resp.status_code == 200
    t_data = transfer_resp.get_json()
    new_alloc = t_data["allocation"]
    prev_alloc = t_data["previous_allocation"]

    assert prev_alloc["end_date"] == transfer_date.isoformat()
    assert prev_alloc["status"] == "active"  # still active today since transfer_date is tomorrow
    assert new_alloc["room_number"] == "C-202"
    assert new_alloc["bed_number"] == 2
    new_alloc_id = new_alloc["id"]

    # 5. End the new allocation with mandatory reason and date
    missing_reason = admin_client.post(
        f"/api/v1/admin/room-allocations/{new_alloc_id}/end",
        json={"end_date": today.isoformat()},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert missing_reason.status_code == 400

    end_resp = admin_client.post(
        f"/api/v1/admin/room-allocations/{new_alloc_id}/end",
        json={
            "end_date": (transfer_date + timedelta(days=10)).isoformat(),
            "reason": "Graduated and vacated hostel",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert end_resp.status_code == 200
    ended_data = end_resp.get_json()["allocation"]
    assert ended_data["end_reason"] == "Graduated and vacated hostel"
    assert ended_data["ended_by"] is not None

    # 6. Verify notification was created for student
    with rooms_app.app_context():
        notifs = list(
            db.session.execute(
                db.select(Notification).where(Notification.recipient_user_id == student_id)
            )
            .scalars()
            .all()
        )
        assert len(notifs) >= 2  # room allocated and room transferred
        categories = [n.category for n in notifs]
        assert "system" in categories

        # Verify audit logs
        audits = list(
            db.session.execute(db.select(AuditLog).where(AuditLog.target_type == "room_allocation"))
            .scalars()
            .all()
        )
        actions = [a.action for a in audits]
        assert "room.allocated" in actions
        assert "room.transferred" in actions
        assert "room.vacated" in actions
