"""Post-Phase-3D stabilization tests:
1. Real room occupancy endpoint (`GET /api/v1/admin/rooms`) with RBAC, empty state,
   active-date filtering, vacant bed calculation, zero-allocation handling, and no N+1 queries.
2. Student room & co-resident serialization (`GET /api/v1/auth/me`, `GET /api/v1/student/profile`)
   for unallocated students, single-occupant rooms, and shared rooms (never inventing sample data).
3. Cross-tab session overwrite simulation, `/api/v1/auth/me` revalidation, genuine 403 vs
   session-switch 403, and real staff creation after admin session synchronization.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, event, text

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def stab_app():
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
def _clean_stab_tables(stab_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    clear_console_outbox()
    owner_engine = create_engine(stab_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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
    clear_console_outbox()


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
def test_admin_rooms_endpoint_empty_rbac_and_active_occupancy_calculation(stab_app):
    """Verify `GET /api/v1/admin/rooms` RBAC, empty state, active-date filter, and vacant beds."""
    with stab_app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Chaitanya Sharma",
            designation="Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        stu1 = User(
            email="mangal@hostelcare.test",
            full_name="Mangal Pandey",
            phone="+91 00000 00001",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="bhagat@hostelcare.test",
            full_name="Bhagat Singh",
            phone="+91 9811122233",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu3 = User(
            email="rajguru@hostelcare.test",
            full_name="Shivaram Rajguru",
            phone="+91 9822233344",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        staff_user = User(
            email="electrician@hostelcare.test",
            full_name="Kishan Lal",
            phone="+91 9833344455",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add_all([admin, stu1, stu2, stu3, staff_user])
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(
                    user_id=stu1.id,
                    roll_number="BETN1CS25002",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                ),
                StudentProfile(
                    user_id=stu2.id,
                    roll_number="BETN1CS25003",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                ),
                StudentProfile(
                    user_id=stu3.id,
                    roll_number="BETN1CS25004",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                ),
                StaffProfile(
                    user_id=staff_user.id,
                    staff_code="STF-0101",
                    trade="Electrician",
                ),
            ]
        )
        db.session.commit()

    anon_client = stab_app.test_client()
    stu_client = stab_app.test_client()
    staff_client = stab_app.test_client()
    admin_client = stab_app.test_client()

    _login_and_csrf(stu_client, "mangal@hostelcare.test", "StudentPass123!")
    _login_and_csrf(staff_client, "electrician@hostelcare.test", "StaffPass123!")
    _login_and_csrf(admin_client, "warden@hostelcare.test", "AdminPass123!")

    # 1. RBAC checks: unauthenticated -> 401, student -> 403, staff -> 403
    assert anon_client.get("/api/v1/admin/rooms").status_code == 401
    stu_denied = stu_client.get("/api/v1/admin/rooms")
    assert stu_denied.status_code == 403
    assert stu_denied.get_json()["error"]["code"] == "forbidden"
    assert staff_client.get("/api/v1/admin/rooms").status_code == 403

    # 2. Empty room occupancy when no rooms exist in DB (never returns sample mock rooms)
    empty_resp = admin_client.get("/api/v1/admin/rooms")
    assert empty_resp.status_code == 200
    assert empty_resp.get_json() == {"rooms": []}

    # 3. Seed blocks, rooms, and active/inactive/future allocations
    today = date.today()
    with stab_app.app_context():
        admin_row = db.session.execute(
            db.select(User).where(User.email == "warden@hostelcare.test")
        ).scalar_one()
        s1_row = db.session.execute(
            db.select(User).where(User.email == "mangal@hostelcare.test")
        ).scalar_one()
        s2_row = db.session.execute(
            db.select(User).where(User.email == "bhagat@hostelcare.test")
        ).scalar_one()
        s3_row = db.session.execute(
            db.select(User).where(User.email == "rajguru@hostelcare.test")
        ).scalar_one()

        block_a = Block(code="BLKA", name="Block A (Nalanda)", display_order=1, is_active=True)
        db.session.add(block_a)
        db.session.flush()

        # Room A-101: capacity 2, 0 active allocations (1 ended yesterday)
        rm_101 = Room(
            block_id=block_a.id,
            room_number="A-101",
            floor=1,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        # Room A-204: capacity 3, 2 active allocations, 1 vacant bed
        rm_204 = Room(
            block_id=block_a.id,
            room_number="A-204",
            floor=2,
            capacity=3,
            room_type="triple",
            is_active=True,
        )
        # Room A-301: capacity 2, 0 active allocations today (1 future allocation)
        rm_301 = Room(
            block_id=block_a.id,
            room_number="A-301",
            floor=3,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        db.session.add_all([rm_101, rm_204, rm_301])
        db.session.flush()

        # Ended allocation in A-101 (end_date == today -> half-open [start, end) not active today)
        db.session.add(
            RoomAllocation(
                room_id=rm_101.id,
                student_user_id=s1_row.id,
                bed_number=1,
                start_date=today - timedelta(days=30),
                end_date=today,
                allocated_by=admin_row.id,
                ended_by=admin_row.id,
                end_reason="Shifted to A-204",
            )
        )
        # Active open-ended allocation in A-204 bed 1 for Mangal Pandey
        db.session.add(
            RoomAllocation(
                room_id=rm_204.id,
                student_user_id=s1_row.id,
                bed_number=1,
                start_date=today,
                end_date=None,
                allocated_by=admin_row.id,
            )
        )
        # Active allocation in A-204 bed 3 for Bhagat Singh (end_date > today)
        db.session.add(
            RoomAllocation(
                room_id=rm_204.id,
                student_user_id=s2_row.id,
                bed_number=3,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
                allocated_by=admin_row.id,
                ended_by=admin_row.id,
                end_reason="Scheduled semester checkout",
            )
        )
        # Future allocation in A-301 bed 1 for Shivaram Rajguru (start_date > today -> not active)
        db.session.add(
            RoomAllocation(
                room_id=rm_301.id,
                student_user_id=s3_row.id,
                bed_number=1,
                start_date=today + timedelta(days=2),
                end_date=None,
                allocated_by=admin_row.id,
            )
        )
        db.session.commit()

    # 4. Verify query count (no N+1) and response payload
    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    with stab_app.app_context():
        event.listen(db.engine, "before_cursor_execute", _count_queries)
        try:
            rooms_resp = admin_client.get("/api/v1/admin/rooms")
        finally:
            event.remove(db.engine, "before_cursor_execute", _count_queries)

    assert rooms_resp.status_code == 200
    # 1 query for session user + 1 for rooms/blocks + 1 for active allocations = 3 queries
    assert query_count <= 4

    rooms_list = rooms_resp.get_json()["rooms"]
    assert len(rooms_list) == 3

    by_no = {r["room_number"]: r for r in rooms_list}

    # Room A-101: 0 active allocations (ended allocation excluded)
    r101 = by_no["A-101"]
    assert r101["block"] == "Block A (Nalanda)"
    assert r101["floor"] == "1st Floor"
    assert r101["capacity"] == 2
    assert r101["occupied"] == 0
    assert r101["vacant_beds"] == 2
    assert r101["residents"] == []
    assert r101["students"] == ["(Vacant Bed)", "(Vacant Bed)"]

    # Room A-204: 2 active allocations (beds 1 and 3), 1 vacant bed (bed 2)
    r204 = by_no["A-204"]
    assert r204["block"] == "Block A (Nalanda)"
    assert r204["floor"] == "2nd Floor"
    assert r204["capacity"] == 3
    assert r204["occupied"] == 2
    assert r204["vacant_beds"] == 1
    assert r204["residents"] == ["Mangal Pandey", "Bhagat Singh"]
    assert r204["students"] == ["Mangal Pandey", "(Vacant Bed)", "Bhagat Singh"]

    # Room A-301: 0 active allocations today (future allocation excluded)
    r301 = by_no["A-301"]
    assert r301["capacity"] == 2
    assert r301["occupied"] == 0
    assert r301["vacant_beds"] == 2
    assert r301["residents"] == []
    assert r301["students"] == ["(Vacant Bed)", "(Vacant Bed)"]

    # Ensure no sample names ever appear
    raw_json_str = str(rooms_list)
    for sample_name in ("Aarav Sharma", "Nikhil Jain", "Rohan Kulkarni", "Siddharth Rao"):
        assert sample_name not in raw_json_str


@pytest.mark.db
def test_student_room_and_roommate_serialization_without_and_with_allocation(stab_app):
    """Verify student `/api/v1/auth/me` and `/api/v1/student/profile` never invent room data."""
    today = date.today()
    with stab_app.app_context():
        admin = User(
            email="warden@hostelcare.test",
            full_name="Chaitanya Sharma",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        stu_unassigned = User(
            email="unassigned@hostelcare.test",
            full_name="Mangal Pandey",
            phone="+91 00000 00001",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_allocated_1 = User(
            email="resident1@hostelcare.test",
            full_name="Chandrashekhar Azad",
            phone="+91 9811100001",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_allocated_2 = User(
            email="resident2@hostelcare.test",
            full_name="Ashfaqulla Khan",
            phone="+91 9811100002",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, stu_unassigned, stu_allocated_1, stu_allocated_2])
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(user_id=stu_unassigned.id, roll_number="BETN1CS25002"),
                StudentProfile(user_id=stu_allocated_1.id, roll_number="BETN1CS25010"),
                StudentProfile(user_id=stu_allocated_2.id, roll_number="BETN1CS25011"),
            ]
        )

        block_b = Block(code="BLKB", name="Block B (Takshashila)", display_order=2, is_active=True)
        db.session.add(block_b)
        db.session.flush()

        room_b105 = Room(
            block_id=block_b.id,
            room_number="B-105",
            floor=1,
            capacity=2,
            is_active=True,
        )
        db.session.add(room_b105)
        db.session.flush()

        # Allocate only stu_allocated_1 first (solo resident in B-105)
        db.session.add(
            RoomAllocation(
                room_id=room_b105.id,
                student_user_id=stu_allocated_1.id,
                bed_number=1,
                start_date=today - timedelta(days=3),
                allocated_by=admin.id,
            )
        )
        db.session.commit()

    # 1. Student without room allocation
    unassigned_client = stab_app.test_client()
    _login_and_csrf(unassigned_client, "unassigned@hostelcare.test", "StudentPass123!")
    me_unassigned = unassigned_client.get("/api/v1/auth/me").get_json()["user"]
    assert me_unassigned["hasActiveRoom"] is False
    assert me_unassigned["room"] == "Unassigned"
    assert me_unassigned["block"] == "Not Assigned"
    assert me_unassigned["floor"] == "Not Assigned"
    assert me_unassigned["bed"] == "Not Assigned"
    assert me_unassigned["roommate"] == "No Roommate Assigned"
    assert me_unassigned["roommateRoll"] is None
    assert "A-203" not in str(me_unassigned)
    assert "Rohan Kulkarni" not in str(me_unassigned)

    # 2. Student with room allocation but no roommate yet
    res1_client = stab_app.test_client()
    _login_and_csrf(res1_client, "resident1@hostelcare.test", "StudentPass123!")
    me_solo = res1_client.get("/api/v1/auth/me").get_json()["user"]
    assert me_solo["hasActiveRoom"] is True
    assert me_solo["room"] == "B-105"
    assert me_solo["block"] == "Block B (Takshashila)"
    assert me_solo["floor"] == "1st Floor"
    assert me_solo["bed"] == "Bed 1"
    assert me_solo["roommate"] == "No Roommate Assigned"
    assert me_solo["roommateRoll"] is None

    # 3. Allocate stu_allocated_2 into Bed 2 of B-105 -> both students now see their real roommate
    with stab_app.app_context():
        admin_row = db.session.execute(
            db.select(User).where(User.email == "warden@hostelcare.test")
        ).scalar_one()
        s2_row = db.session.execute(
            db.select(User).where(User.email == "resident2@hostelcare.test")
        ).scalar_one()
        rm_row = db.session.execute(db.select(Room).where(Room.room_number == "B-105")).scalar_one()
        db.session.add(
            RoomAllocation(
                room_id=rm_row.id,
                student_user_id=s2_row.id,
                bed_number=2,
                start_date=today,
                allocated_by=admin_row.id,
            )
        )
        db.session.commit()

    me_shared = res1_client.get("/api/v1/student/profile").get_json()["user"]
    assert me_shared["hasActiveRoom"] is True
    assert me_shared["room"] == "B-105"
    assert me_shared["roommate"] == "Ashfaqulla Khan"
    assert me_shared["roommateRoll"] == "BETN1CS25011"
    assert me_shared["roommateBed"] == "Bed 2"
    assert me_shared["roommatePhone"] == "+91 9811100002"


@pytest.mark.db
def test_shared_browser_session_switch_and_staff_creation_after_resync(stab_app):
    """Simulate Admin and Student logins sharing a browser cookie jar and verify resync."""
    with stab_app.app_context():
        admin = User(
            email="admin@hostelcare.test",
            full_name="Chaitanya Sharma",
            designation="Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        student = User(
            email="student1@hostelcare.test",
            full_name="Mangal Pandey",
            phone="+91 00000 00001",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, student])
        db.session.flush()
        db.session.add(
            StudentProfile(
                user_id=student.id,
                roll_number="BETN1CS25002",
                reviewed_by=admin.id,
                reviewed_at=datetime.now(UTC),
            )
        )
        db.session.commit()

    # Single test_client represents one browser profile with shared cookies across tabs
    shared_browser = stab_app.test_client()

    # Tab 1: Admin logs in and sees empty staff list
    admin_csrf = _login_and_csrf(shared_browser, "admin@hostelcare.test", "AdminPass123!")
    staff_resp = shared_browser.get("/api/v1/admin/staff")
    assert staff_resp.status_code == 200
    assert staff_resp.get_json() == {"staff": []}

    # Tab 2 (same browser cookie jar): Student logs in, overwriting `hostelcare_session`
    student_csrf = _login_and_csrf(
        shared_browser,
        "student1@hostelcare.test",
        "StudentPass123!",
        csrf=admin_csrf,
    )

    # Tab 1 attempts admin staff action before focus revalidation -> gets 403 forbidden
    denied_post = shared_browser.post(
        "/api/v1/admin/staff",
        headers={"X-CSRF-Token": student_csrf},
        json={
            "fullName": "Ramesh Babu",
            "email": "ramesh@hostelcare.test",
            "phone": "+91 9442188901",
            "trade": "Electrician",
        },
    )
    assert denied_post.status_code == 403
    assert denied_post.get_json()["error"]["code"] == "forbidden"

    # Tab 1 revalidates `/api/v1/auth/me` on focus/403 and discovers the active session is `student`
    me_check = shared_browser.get("/api/v1/auth/me")
    assert me_check.status_code == 200
    assert me_check.get_json()["user"]["role"] == "student"
    assert me_check.get_json()["user"]["rollNumber"] == "BETN1CS25002"

    # Admin signs back in and creates a real staff record
    new_admin_csrf = _login_and_csrf(
        shared_browser,
        "admin@hostelcare.test",
        "AdminPass123!",
        csrf=student_csrf,
    )
    create_staff = shared_browser.post(
        "/api/v1/admin/staff",
        headers={"X-CSRF-Token": new_admin_csrf},
        json={
            "fullName": "Ramesh Babu",
            "email": "ramesh@hostelcare.test",
            "phone": "+91 9442188901",
            "staffCode": "STF-0001",
            "trade": "Electrician",
        },
    )
    assert create_staff.status_code == 201
    created = create_staff.get_json()["staff"]
    assert created["name"] == "Ramesh Babu"
    assert created["staffCode"] == "STF-0001"
    assert created["status"] == "active"
    assert created["display_status"] == "Active"
