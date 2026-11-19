"""Phase 4.1 Admin Dashboard Foundation & KPI Engine PostgreSQL Integration Tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth.security import hash_password
from app.extensions import db
from app.models.complaint_internal_notes import ComplaintInternalNote
from app.models.complaints import Complaint, ComplaintAssignment
from app.models.fines import Fine, FineDispute
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.payments import Payment, PaymentAttempt, PaymentEvent
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")
_IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(scope="module")
def analytics_app():
    """Create testing Flask app and ensure `hostelcare_test` is migrated to head."""
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture(autouse=True)
def _clean_analytics_tables(analytics_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    owner_engine = create_engine(analytics_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
                "public.payment_events, "
                "public.payments, "
                "public.payment_attempts, "
                "public.fine_history, "
                "public.fine_disputes, "
                "public.fines, "
                "public.complaint_attachments, "
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


def _login(client, identifier: str, password: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()


def _seed_base_users(app) -> dict[str, int]:
    with app.app_context():
        admin = User(
            email="warden.p41@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        staff_user = User(
            email="tech.p41@hostelcare.test",
            full_name="Ramesh Kumar",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        stu1 = User(
            email="stu1.p41@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="stu2.p41@hostelcare.test",
            full_name="Priya Patel",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="pending",
        )
        stu3 = User(
            email="stu3.p41@hostelcare.test",
            full_name="Rohan Das",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="rejected",
        )
        db.session.add_all([admin, staff_user, stu1, stu2, stu3])
        db.session.flush()

        db.session.add(
            StaffProfile(
                user_id=staff_user.id,
                role="staff",
                staff_code="STF-4101",
                trade="Electrical",
            )
        )
        db.session.add_all(
            [
                StudentProfile(user_id=stu1.id, role="student", roll_number="2026CSB4101"),
                StudentProfile(user_id=stu2.id, role="student", roll_number="2026CSB4102"),
                StudentProfile(user_id=stu3.id, role="student", roll_number="2026CSB4103"),
            ]
        )
        db.session.commit()
        return {
            "admin_id": admin.id,
            "staff_id": staff_user.id,
            "stu1_id": stu1.id,
            "stu2_id": stu2.id,
            "stu3_id": stu3.id,
        }


def test_analytics_overview_rbac_enforced(analytics_app):
    ids = _seed_base_users(analytics_app)
    assert ids["admin_id"] > 0

    unauth_client = analytics_app.test_client()
    assert unauth_client.get("/api/v1/admin/analytics/overview").status_code == 401

    stu_client = analytics_app.test_client()
    _login(stu_client, "stu1.p41@hostelcare.test", "StudentPass123!")
    assert stu_client.get("/api/v1/admin/analytics/overview").status_code == 403

    staff_client = analytics_app.test_client()
    _login(staff_client, "tech.p41@hostelcare.test", "StaffPass123!")
    assert staff_client.get("/api/v1/admin/analytics/overview").status_code == 403

    admin_client = analytics_app.test_client()
    _login(admin_client, "warden.p41@hostelcare.test", "AdminPass123!")
    resp = admin_client.get("/api/v1/admin/analytics/overview")
    assert resp.status_code == 200


def test_analytics_overview_empty_database_and_zero_capacity(analytics_app):
    with analytics_app.app_context():
        admin = User(
            email="warden.empty@hostelcare.test",
            full_name="Empty Admin",
            designation="Chief Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        # Add active block with zero rooms and an inactive room to verify zero-capacity handling
        blk = Block(code="Z", name="Block Z", display_order=1, is_active=True)
        db.session.add(blk)
        db.session.flush()
        db.session.add(
            Room(
                block_id=blk.id,
                room_number="Z-101",
                floor=1,
                room_type="double",
                capacity=2,
                is_active=False,
            )
        )
        db.session.commit()

    client = analytics_app.test_client()
    _login(client, "warden.empty@hostelcare.test", "AdminPass123!")
    resp = client.get("/api/v1/admin/analytics/overview")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["complaints"]["total"] == 0
    assert data["complaints"]["unassigned"] == 0
    assert data["complaints"]["resolved"] == 0
    assert data["approvals"]["pendingCount"] == 0
    assert data["approvals"]["totalStudents"] == 0
    assert data["occupancy"]["totalCapacity"] == 0
    assert data["occupancy"]["occupiedBeds"] == 0
    assert data["occupancy"]["vacantBeds"] == 0
    assert data["occupancy"]["occupancyRate"] == 0.0
    assert data["residents"]["activeCount"] == 0
    assert data["finances"]["leviedAmount"] == 0.0
    assert data["finances"]["collectedAmount"] == 0.0
    assert data["finances"]["outstandingAmount"] == 0.0
    assert data["finances"]["pendingDisputesCount"] == 0
    assert data["recentActivity"] == []


def test_analytics_overview_kpis_complaints_occupancy_finances_and_privacy(analytics_app):
    ids = _seed_base_users(analytics_app)
    today_ist = datetime.now(_IST).date()
    yesterday_ist = today_ist - timedelta(days=1)
    old_date = today_ist - timedelta(days=45)
    now_utc = datetime.now(UTC)

    with analytics_app.app_context():
        # Blocks & Rooms
        blk_a = Block(code="A", name="Block A - Aryabhatta", display_order=1, is_active=True)
        blk_b = Block(code="B", name="Block B - Bhaskara", display_order=2, is_active=True)
        blk_inactive = Block(code="X", name="Inactive Block", display_order=9, is_active=False)
        db.session.add_all([blk_a, blk_b, blk_inactive])
        db.session.flush()

        rm_a1 = Room(block_id=blk_a.id, room_number="A-101", floor=1, capacity=2, is_active=True)
        rm_a2 = Room(block_id=blk_a.id, room_number="A-102", floor=1, capacity=2, is_active=True)
        rm_b1 = Room(block_id=blk_b.id, room_number="B-201", floor=2, capacity=3, is_active=True)
        rm_inactive = Room(
            block_id=blk_a.id, room_number="A-999", floor=9, capacity=4, is_active=False
        )
        rm_in_inactive_blk = Room(
            block_id=blk_inactive.id, room_number="X-101", floor=1, capacity=4, is_active=True
        )
        db.session.add_all([rm_a1, rm_a2, rm_b1, rm_inactive, rm_in_inactive_blk])
        db.session.flush()

        # Create two additional active students for room allocations
        stu_act2 = User(
            email="stu_act2.p41@hostelcare.test",
            full_name="Active Resident 2",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_act3 = User(
            email="stu_act3.p41@hostelcare.test",
            full_name="Active Resident 3",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([stu_act2, stu_act3])
        db.session.flush()
        db.session.add_all(
            [
                StudentProfile(user_id=stu_act2.id, role="student", roll_number="2026CSB4192"),
                StudentProfile(user_id=stu_act3.id, role="student", roll_number="2026CSB4193"),
            ]
        )
        db.session.flush()

        # Allocations: 1 active today, 1 past ended before today, 1 starting tomorrow
        db.session.add_all(
            [
                RoomAllocation(
                    room_id=rm_a1.id,
                    student_user_id=ids["stu1_id"],
                    bed_number=1,
                    start_date=today_ist - timedelta(days=10),
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
                RoomAllocation(
                    room_id=rm_a1.id,
                    student_user_id=stu_act2.id,
                    bed_number=2,
                    start_date=today_ist - timedelta(days=20),
                    end_date=today_ist,  # half-open [start, end) -> NOT active today!
                    allocated_by=ids["admin_id"],
                    ended_by=ids["admin_id"],
                    end_reason="Completed checkout",
                ),
                RoomAllocation(
                    room_id=rm_b1.id,
                    student_user_id=stu_act3.id,
                    bed_number=1,
                    start_date=today_ist + timedelta(days=1),  # future -> NOT active today!
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
            ]
        )

        # Complaints across all 8 statuses within the 30d window + 1 old complaint outside 30d
        def _make_complaint(status, title, created_dt, priority="medium", room_id=rm_a1.id):
            comp = Complaint(
                student_user_id=ids["stu1_id"],
                location_type="room",
                room_id=room_id,
                title=title,
                description=f"Details for {title}",
                category="Electrical",
                priority=priority,
                status=status,
                rejection_reason="Duplicate ticket" if status == "rejected" else None,
                completed_at=created_dt if status in ("completed", "closed") else None,
                closed_at=created_dt if status == "closed" else None,
                created_at=created_dt,
                updated_at=created_dt,
            )
            return comp

        c_sub = _make_complaint(
            "submitted", "Fan switch broken", now_utc - timedelta(hours=1), "high"
        )
        c_rev = _make_complaint("under_review", "Light flickering", now_utc - timedelta(hours=2))
        c_asg = _make_complaint("assigned", "Socket loose", now_utc - timedelta(hours=3))
        c_acc = _make_complaint("accepted", "AC remote missing", now_utc - timedelta(hours=4))
        c_prg = _make_complaint("in_progress", "MCB tripping", now_utc - timedelta(hours=5), "high")
        c_cmp = _make_complaint("completed", "Tube light replaced", now_utc - timedelta(hours=6))
        c_cls = _make_complaint("closed", "Switchboard fixed", now_utc - timedelta(days=2))
        c_rej = _make_complaint("rejected", "Invalid report", now_utc - timedelta(days=3))
        c_old = _make_complaint(
            "submitted",
            "Very old ticket",
            datetime.combine(old_date, datetime.min.time(), tzinfo=_IST),
        )
        db.session.add_all([c_sub, c_rev, c_asg, c_acc, c_prg, c_cmp, c_cls, c_rej, c_old])
        db.session.flush()

        # Open assignments for assigned, accepted, in_progress; ended assignment for rejected
        for comp in (c_asg, c_acc, c_prg):
            db.session.add(
                ComplaintAssignment(
                    complaint_id=comp.id,
                    staff_user_id=ids["staff_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=comp.created_at,
                )
            )
        db.session.add(
            ComplaintAssignment(
                complaint_id=c_rej.id,
                staff_user_id=ids["staff_id"],
                assigned_by=ids["admin_id"],
                assigned_at=c_rej.created_at,
                ended_at=c_rej.created_at,
                ended_by=ids["admin_id"],
                end_note="Rejected",
            )
        )
        # Private admin internal note on latest complaint (must NEVER leak to overview response)
        db.session.add(
            ComplaintInternalNote(
                complaint_id=c_sub.id,
                author_user_id=ids["admin_id"],
                body="SECRET_INTERNAL_WARDEN_NOTE",
            )
        )

        # Fines & Payments
        # 1. Paid fine issued inside window, verified inside window, with 2 attempts & 2 events
        f_paid = Fine(
            student_user_id=ids["stu1_id"],
            room_id=rm_a1.id,
            category="Property Damage",
            description="Broken window pane",
            amount_inr=Decimal("1200.00"),
            issue_date=yesterday_ist,
            due_date=today_ist + timedelta(days=7),
            issued_by=ids["admin_id"],
            status="paid",
            paid_at=now_utc - timedelta(hours=2),
        )
        # 2. Pending fine issued inside window (with failed attempt -> must NOT count as collected!)
        f_pending = Fine(
            student_user_id=ids["stu1_id"],
            room_id=rm_a1.id,
            category="Late Curfew",
            description="Curfew violation",
            amount_inr=Decimal("500.00"),
            issue_date=today_ist,
            due_date=today_ist + timedelta(days=5),
            issued_by=ids["admin_id"],
            status="pending",
        )
        # 3. Disputed fine issued BEFORE window (still contributes to live outstanding balance!)
        f_disputed_old = Fine(
            student_user_id=ids["stu1_id"],
            room_id=rm_a1.id,
            category="Noise Violation",
            description="Old disputed fine",
            amount_inr=Decimal("800.00"),
            issue_date=old_date,
            due_date=old_date + timedelta(days=7),
            issued_by=ids["admin_id"],
            status="disputed",
        )
        # 4. Waived fine issued & resolved inside window
        f_waived = Fine(
            student_user_id=ids["stu1_id"],
            room_id=rm_a1.id,
            category="Disciplinary",
            description="Waived penalty",
            amount_inr=Decimal("300.00"),
            issue_date=yesterday_ist,
            due_date=today_ist + timedelta(days=7),
            issued_by=ids["admin_id"],
            status="waived",
            resolved_by=ids["admin_id"],
            resolved_at=now_utc - timedelta(hours=4),
            resolution_reason="First warning waived",
        )
        # 5. Cancelled fine issued & resolved inside window
        f_cancelled = Fine(
            student_user_id=ids["stu1_id"],
            room_id=rm_a1.id,
            category="Clerical Error",
            description="Duplicate fine",
            amount_inr=Decimal("450.00"),
            issue_date=today_ist,
            due_date=today_ist + timedelta(days=7),
            issued_by=ids["admin_id"],
            status="cancelled",
            resolved_by=ids["admin_id"],
            resolved_at=now_utc - timedelta(hours=1),
            resolution_reason="Issued in error",
        )
        db.session.add_all([f_paid, f_pending, f_disputed_old, f_waived, f_cancelled])
        db.session.flush()

        db.session.add(
            FineDispute(
                fine_id=f_disputed_old.id,
                raised_by=ids["stu1_id"],
                reason="I was not in hostel on that date.",
                status="open",
            )
        )

        # Attempts & verified Payment on f_paid (1 failed attempt + 1 succeeded attempt + 2 events)
        att_fail_paid = PaymentAttempt(
            fine_id=f_paid.id,
            initiated_by=ids["stu1_id"],
            amount_inr=Decimal("1200.00"),
            gateway_order_id="order_fail_1",
            status="failed",
            failure_code="BAD_REQUEST",
            failure_reason="Insufficient funds",
        )
        att_succ_paid = PaymentAttempt(
            fine_id=f_paid.id,
            initiated_by=ids["stu1_id"],
            amount_inr=Decimal("1200.00"),
            gateway_order_id="order_succ_1",
            gateway_payment_id="pay_succ_1",
            payment_method="upi",
            status="succeeded",
            verified_at=now_utc - timedelta(hours=2),
        )
        # Failed & processing attempts on f_pending (must NEVER count as revenue!)
        att_fail_pend = PaymentAttempt(
            fine_id=f_pending.id,
            initiated_by=ids["stu1_id"],
            amount_inr=Decimal("500.00"),
            gateway_order_id="order_fail_2",
            status="failed",
            failure_reason="User cancelled",
        )
        db.session.add_all([att_fail_paid, att_succ_paid, att_fail_pend])
        db.session.flush()

        db.session.add(
            Payment(
                fine_id=f_paid.id,
                payment_attempt_id=att_succ_paid.id,
                channel="razorpay",
                amount_inr=Decimal("1200.00"),
                gateway_order_id="order_succ_1",
                gateway_payment_id="pay_succ_1",
                payment_method="upi",
                verification_method="webhook",
                verified_at=now_utc - timedelta(hours=2),
            )
        )
        db.session.add_all(
            [
                PaymentEvent(
                    payment_attempt_id=att_succ_paid.id,
                    source="webhook",
                    event_type="payment.captured",
                    gateway_event_id="evt_1",
                    signature_valid=True,
                    outcome="applied",
                ),
                PaymentEvent(
                    payment_attempt_id=att_succ_paid.id,
                    source="webhook",
                    event_type="order.paid",
                    gateway_event_id="evt_2",
                    signature_valid=True,
                    outcome="duplicate",
                ),
            ]
        )
        db.session.commit()

    client = analytics_app.test_client()
    _login(client, "warden.p41@hostelcare.test", "AdminPass123!")
    resp = client.get("/api/v1/admin/analytics/overview?preset=30d")
    assert resp.status_code == 200
    data = resp.get_json()

    # Complaints (8 inside 30d window, c_old excluded)
    comp = data["complaints"]
    assert comp["total"] == 8
    assert comp["newSubmissions"] == 1
    assert comp["underReview"] == 1
    assert comp["assigned"] == 1
    assert comp["accepted"] == 1
    assert comp["inProgress"] == 1
    assert comp["completed"] == 1
    assert comp["closed"] == 1
    assert comp["rejected"] == 1
    assert comp["resolved"] == 2
    assert comp["unassigned"] == 2  # c_sub + c_rev (c_rej is terminal, not unassigned)

    # Approvals
    appr = data["approvals"]
    assert appr["pendingCount"] == 1
    assert appr["approvedCount"] == 3
    assert appr["rejectedCount"] == 1
    assert appr["totalStudents"] == 5

    # Occupancy as of today (active rooms: A-101 cap 2, A-102 cap 2, B-201 cap 3 -> total 7)
    occ = data["occupancy"]
    assert occ["totalCapacity"] == 7
    assert occ["occupiedBeds"] == 1
    assert occ["vacantBeds"] == 6
    assert occ["occupancyRate"] == 14.3
    assert occ["activeRoomsCount"] == 3
    assert len(occ["blocks"]) == 2
    assert occ["blocks"][0]["code"] == "A"
    assert occ["blocks"][0]["totalCapacity"] == 4
    assert occ["blocks"][0]["occupiedBeds"] == 1
    assert occ["blocks"][1]["code"] == "B"
    assert occ["blocks"][1]["totalCapacity"] == 3
    assert occ["blocks"][1]["occupiedBeds"] == 0
    assert data["residents"]["activeCount"] == 1

    # Historical occupancy as of yesterday_ist (stu2's checkout allocation was still active)
    hist_from = (yesterday_ist - timedelta(days=2)).isoformat()
    hist_to = yesterday_ist.isoformat()
    hist_resp = client.get(
        f"/api/v1/admin/analytics/overview?preset=custom&date_from={hist_from}&date_to={hist_to}"
    )
    assert hist_resp.status_code == 200
    hist_payload = hist_resp.get_json()
    hist_occ = hist_payload["occupancy"]
    assert hist_occ["occupiedBeds"] == 2
    assert hist_occ["vacantBeds"] == 5
    assert hist_payload["residents"]["activeCount"] == 2

    # Finances (30d window)
    fin = data["finances"]
    # Levied in window: 1200 + 500 + 300 + 450 = 2450 (f_disputed_old issued 45d ago excluded)
    assert fin["leviedAmountInr"] == "2450.00"
    assert fin["leviedCount"] == 4
    # Collected verified only, no double-count from 2 attempts/2 events: 1200.00
    assert fin["collectedAmountInr"] == "1200.00"
    assert fin["collectedCount"] == 1
    # Outstanding live: f_pending (500) + f_disputed_old (800) = 1300.00
    assert fin["outstandingAmountInr"] == "1300.00"
    assert fin["outstandingCount"] == 2
    assert fin["waivedAmountInr"] == "300.00"
    assert fin["waivedCount"] == 1
    assert fin["cancelledAmountInr"] == "450.00"
    assert fin["cancelledCount"] == 1
    assert fin["pendingDisputesCount"] == 1

    # Recent activity: limited to 5, ordered newest-first, no student PII or internal notes
    recent = data["recentActivity"]
    assert len(recent) == 5
    assert recent[0]["title"] == "Fan switch broken"
    assert recent[0]["priority"] == "High"
    assert recent[0]["status"] == "Submitted"
    assert recent[0]["assignedStaff"] is None
    assert recent[2]["assignedStaff"] == "Ramesh Kumar"
    payload_text = str(data)
    assert "SECRET_INTERNAL_WARDEN_NOTE" not in payload_text
    assert "Aarav Sharma" not in payload_text
    assert "2026CSB4101" not in payload_text
    assert "stu1.p41@hostelcare.test" not in payload_text


def test_analytics_overview_date_validation_and_ist_boundaries(analytics_app):
    ids = _seed_base_users(analytics_app)

    # Create a complaint at 23:30 IST on 2026-11-10 (= 18:00 UTC on 2026-11-10)
    ist_late = datetime(2026, 11, 10, 23, 30, tzinfo=_IST)
    with analytics_app.app_context():
        blk = Block(code="A", name="Block A", display_order=1, is_active=True)
        db.session.add(blk)
        db.session.flush()
        rm = Room(block_id=blk.id, room_number="A-101", floor=1, capacity=2, is_active=True)
        db.session.add(rm)
        db.session.flush()
        db.session.add(
            Complaint(
                student_user_id=ids["stu1_id"],
                location_type="room",
                room_id=rm.id,
                title="Late night IST test",
                description="Boundary verification",
                category="Electrical",
                priority="low",
                status="submitted",
                created_at=ist_late,
                updated_at=ist_late,
            )
        )
        db.session.commit()

    client = analytics_app.test_client()
    _login(client, "warden.p41@hostelcare.test", "AdminPass123!")

    # Included in 2026-11-10..2026-11-10 IST
    in_resp = client.get(
        "/api/v1/admin/analytics/overview?preset=custom&date_from=2026-11-10&date_to=2026-11-10"
    )
    assert in_resp.status_code == 200
    assert in_resp.get_json()["complaints"]["total"] == 1

    # Excluded from 2026-11-11..2026-11-11 IST
    out_resp = client.get(
        "/api/v1/admin/analytics/overview?preset=custom&date_from=2026-11-11&date_to=2026-11-11"
    )
    assert out_resp.status_code == 200
    assert out_resp.get_json()["complaints"]["total"] == 0

    # Presets 7d and this_month succeed
    assert client.get("/api/v1/admin/analytics/overview?preset=7d").status_code == 200
    assert client.get("/api/v1/admin/analytics/overview?preset=this_month").status_code == 200

    # Invalid inputs rejected with 400 validation_error
    bad_urls = [
        "/api/v1/admin/analytics/overview?preset=all_time",
        "/api/v1/admin/analytics/overview?preset=custom",
        "/api/v1/admin/analytics/overview?date_from=2026-11-10",
        "/api/v1/admin/analytics/overview?date_from=10/11/2026&date_to=11/11/2026",
        "/api/v1/admin/analytics/overview?date_from=2026-02-30&date_to=2026-03-01",
        "/api/v1/admin/analytics/overview?date_from=2026-11-15&date_to=2026-11-10",
        "/api/v1/admin/analytics/overview?date_from=2025-11-10&date_to=2026-11-18",  # > 365 days
    ]
    for url in bad_urls:
        r = client.get(url)
        assert r.status_code == 400, f"Expected 400 for {url}, got {r.status_code}"
        assert r.get_json()["error"]["code"] == "validation_error"


def test_analytics_overview_active_residents_distinct_and_eligibility(analytics_app):
    """Verify distinct resident counting, allocation overlaps, room/block active status & role."""
    ids = _seed_base_users(analytics_app)
    today_ist = datetime.now(_IST).date()

    with analytics_app.app_context():
        blk_active = Block(code="A", name="Block A", display_order=1, is_active=True)
        blk_inactive = Block(code="I", name="Block Inactive", display_order=2, is_active=True)
        db.session.add_all([blk_active, blk_inactive])
        db.session.flush()

        rm_active = Room(
            block_id=blk_active.id, room_number="A-101", floor=1, capacity=4, is_active=True
        )
        rm_inactive = Room(
            block_id=blk_active.id, room_number="A-102", floor=1, capacity=2, is_active=True
        )
        rm_in_inactive_blk = Room(
            block_id=blk_inactive.id, room_number="I-101", floor=1, capacity=2, is_active=True
        )
        db.session.add_all([rm_active, rm_inactive, rm_in_inactive_blk])
        db.session.flush()

        # Additional active & suspended students
        stu_suspended = User(
            email="stu.susp@hostelcare.test",
            full_name="Suspended Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="suspended",
        )
        stu_inactive_room = User(
            email="stu.inactrm@hostelcare.test",
            full_name="Inactive Room Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_inactive_blk = User(
            email="stu.inactblk@hostelcare.test",
            full_name="Inactive Block Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_ended = User(
            email="stu.ended@hostelcare.test",
            full_name="Ended Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu_future = User(
            email="stu.future@hostelcare.test",
            full_name="Future Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all(
            [stu_suspended, stu_inactive_room, stu_inactive_blk, stu_ended, stu_future]
        )
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(user_id=stu_suspended.id, role="student", roll_number="2026CSB9001"),
                StudentProfile(
                    user_id=stu_inactive_room.id, role="student", roll_number="2026CSB9002"
                ),
                StudentProfile(
                    user_id=stu_inactive_blk.id, role="student", roll_number="2026CSB9003"
                ),
                StudentProfile(user_id=stu_ended.id, role="student", roll_number="2026CSB9004"),
                StudentProfile(user_id=stu_future.id, role="student", roll_number="2026CSB9005"),
            ]
        )
        db.session.flush()

        # 1. Active student with prior ended allocation + current active allocation -> counts 1
        db.session.add_all(
            [
                RoomAllocation(
                    room_id=rm_active.id,
                    student_user_id=ids["stu1_id"],
                    bed_number=1,
                    start_date=today_ist - timedelta(days=30),
                    end_date=today_ist - timedelta(days=5),
                    allocated_by=ids["admin_id"],
                    ended_by=ids["admin_id"],
                    end_reason="Room transfer",
                ),
                RoomAllocation(
                    room_id=rm_active.id,
                    student_user_id=ids["stu1_id"],
                    bed_number=2,
                    start_date=today_ist - timedelta(days=5),
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
            ]
        )

        # 2. Allocations that must be EXCLUDED:
        #    - Active room/block but student suspended (set active for insert, then suspend)
        db.session.execute(
            text("UPDATE users SET status = 'active' WHERE id = :uid"),
            {"uid": stu_suspended.id},
        )
        db.session.add(
            RoomAllocation(
                room_id=rm_active.id,
                student_user_id=stu_suspended.id,
                bed_number=3,
                start_date=today_ist - timedelta(days=3),
                end_date=None,
                allocated_by=ids["admin_id"],
            )
        )
        db.session.flush()
        db.session.execute(
            text("UPDATE users SET status = 'suspended' WHERE id = :uid"),
            {"uid": stu_suspended.id},
        )

        #    - Allocation in subsequently deactivated room/block, ended today, and future allocation
        db.session.add_all(
            [
                RoomAllocation(
                    room_id=rm_inactive.id,
                    student_user_id=stu_inactive_room.id,
                    bed_number=1,
                    start_date=today_ist - timedelta(days=3),
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
                RoomAllocation(
                    room_id=rm_in_inactive_blk.id,
                    student_user_id=stu_inactive_blk.id,
                    bed_number=1,
                    start_date=today_ist - timedelta(days=3),
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
                RoomAllocation(
                    room_id=rm_active.id,
                    student_user_id=stu_ended.id,
                    bed_number=4,
                    start_date=today_ist - timedelta(days=10),
                    end_date=today_ist,
                    allocated_by=ids["admin_id"],
                    ended_by=ids["admin_id"],
                    end_reason="Checked out today",
                ),
                RoomAllocation(
                    room_id=rm_active.id,
                    student_user_id=stu_future.id,
                    bed_number=4,
                    start_date=today_ist + timedelta(days=2),
                    end_date=None,
                    allocated_by=ids["admin_id"],
                ),
            ]
        )
        db.session.flush()
        db.session.execute(
            text("UPDATE rooms SET is_active = false WHERE id = :rid"),
            {"rid": rm_inactive.id},
        )
        db.session.execute(
            text("UPDATE blocks SET is_active = false WHERE id = :bid"),
            {"bid": blk_inactive.id},
        )
        db.session.commit()

    client = analytics_app.test_client()
    _login(client, "warden.p41@hostelcare.test", "AdminPass123!")
    resp = client.get("/api/v1/admin/analytics/overview?preset=30d")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["residents"]["activeCount"] == 1

