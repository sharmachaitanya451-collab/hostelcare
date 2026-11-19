"""Phase 3E.2 Fine Disputes & Administrative Review PostgreSQL Integration Tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.fines.service import FineServiceError, review_fine_dispute
from app.models.audit import AuditLog
from app.models.fines import Fine, FineDispute, FineHistory
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.payments import Payment
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def disputes_app():
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
def _clean_disputes_tables(disputes_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    clear_console_outbox()
    owner_engine = create_engine(disputes_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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


def _login_and_csrf(client, identifier: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()
    return {"X-CSRF-Token": resp.get_json()["csrf_token"]}


def _seed_actors(app) -> dict[str, str | int]:
    with app.app_context():
        admin1 = User(
            email="warden1.dispute@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        admin2 = User(
            email="warden2.dispute@hostelcare.test",
            full_name="Prof. S. R. Joshi",
            designation="Assistant Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add_all([admin1, admin2])
        db.session.flush()

        block = Block(code="BLKA", name="Block A", display_order=1, is_active=True)
        db.session.add(block)
        db.session.flush()

        room = Room(
            block_id=block.id,
            room_number="A-101",
            floor=1,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()

        stu1 = User(
            email="aarav.dispute@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="meera.dispute@hostelcare.test",
            full_name="Meera Krishnan",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        staff = User(
            email="ramesh.dispute@hostelcare.test",
            full_name="Ramesh Babu",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add_all([stu1, stu2, staff])
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(
                    user_id=stu1.id,
                    roll_number="2026CSB2001",
                    reviewed_by=admin1.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StudentProfile(
                    user_id=stu2.id,
                    roll_number="2026ECE2002",
                    reviewed_by=admin1.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StaffProfile(
                    user_id=staff.id,
                    staff_code="STF-2001",
                    trade="Electrician",
                ),
            ]
        )
        db.session.flush()

        db.session.add(
            RoomAllocation(
                student_user_id=stu1.id,
                room_id=room.id,
                bed_number=1,
                start_date=date.today() - timedelta(days=5),
                allocated_by=admin1.id,
            )
        )
        db.session.commit()

        return {
            "admin1_id": admin1.id,
            "admin1_email": admin1.email,
            "admin2_id": admin2.id,
            "admin2_email": admin2.email,
            "stu1_id": stu1.id,
            "stu1_email": stu1.email,
            "stu1_public_id": str(stu1.public_id),
            "stu1_roll": "2026CSB2001",
            "stu2_email": stu2.email,
            "stu2_public_id": str(stu2.public_id),
            "staff_email": staff.email,
        }


def _issue_fine(admin_client, headers: dict[str, str], student_id: str, desc: str) -> dict:
    resp = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": student_id,
            "category": "Hostel Rule Violation",
            "description": desc,
            "amount_inr": "500.00",
            "due_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["fine"]


@pytest.mark.db
def test_student_dispute_submission_validation_ownership_and_duplicates(disputes_app):
    """Test valid student dispute submission, validation, ownership, and duplicate rejection."""
    actors = _seed_actors(disputes_app)
    admin_client = disputes_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    fine1 = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Heater found in room"
    )
    fine2 = _issue_fine(
        admin_client, admin_headers, str(actors["stu2_public_id"]), "Window latch broken"
    )
    fine_waived = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Waived before dispute"
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_waived['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "Waived by warden"},
        ).status_code
        == 200
    )

    stu1_client = disputes_app.test_client()
    stu1_headers = _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")
    staff_client = disputes_app.test_client()
    staff_headers = _login_and_csrf(staff_client, str(actors["staff_email"]), "StaffPass123!")

    # Empty explanation rejected
    assert (
        stu1_client.post(
            f"/api/v1/student/fines/{fine1['referenceNo']}/dispute",
            headers=stu1_headers,
            json={"reason": "   "},
        ).status_code
        == 400
    )

    # Cannot dispute another student's fine
    idor_resp = stu1_client.post(
        f"/api/v1/student/fines/{fine2['referenceNo']}/dispute",
        headers=stu1_headers,
        json={"reason": "Trying to dispute someone else's fine"},
    )
    assert idor_resp.status_code == 403

    # Cannot dispute a waived/paid/cancelled fine
    invalid_state = stu1_client.post(
        f"/api/v1/student/fines/{fine_waived['referenceNo']}/dispute",
        headers=stu1_headers,
        json={"reason": "Already waived"},
    )
    assert invalid_state.status_code == 409

    # Staff and Admin cannot use student dispute endpoint
    assert (
        staff_client.post(
            f"/api/v1/student/fines/{fine1['referenceNo']}/dispute",
            headers=staff_headers,
            json={"reason": "Staff attempt"},
        ).status_code
        == 403
    )
    assert (
        admin_client.post(
            f"/api/v1/student/fines/{fine1['referenceNo']}/dispute",
            headers=admin_headers,
            json={"reason": "Admin attempt"},
        ).status_code
        == 403
    )

    # Valid dispute submission
    disp_resp = stu1_client.post(
        f"/api/v1/student/fines/{fine1['referenceNo']}/dispute",
        headers=stu1_headers,
        json={
            "reason": "I was out of station on that date; my roommate was away too.",
            "status": "waived",
        },
    )
    assert disp_resp.status_code == 201, disp_resp.get_json()
    disputed = disp_resp.get_json()["fine"]
    assert disputed["status"] == "disputed"
    assert disputed["dispute"]["status"] == "open"
    assert (
        disputed["dispute"]["reason"]
        == "I was out of station on that date; my roommate was away too."
    )
    assert "decidedBy" not in disputed["dispute"]
    assert [h["action"] for h in disputed["history"]] == ["issued", "dispute_submitted"]

    # Duplicate dispute rejected
    dup_resp = stu1_client.post(
        f"/api/v1/student/fines/{fine1['referenceNo']}/dispute",
        headers=stu1_headers,
        json={"reason": "Submitting a second dispute"},
    )
    assert dup_resp.status_code == 409

    # Verify admin notifications and audit log created
    with disputes_app.app_context():
        notifs = (
            db.session.execute(
                select(Notification).where(Notification.event_type == "fine_dispute_submitted")
            )
            .scalars()
            .all()
        )
        assert len(notifs) == 2  # both active admins notified
        audits = (
            db.session.execute(select(AuditLog).where(AuditLog.action == "fine_dispute_submitted"))
            .scalars()
            .all()
        )
        assert len(audits) == 1


@pytest.mark.db
def test_admin_dispute_listing_filtering_and_approve_reject_workflows(disputes_app):
    """Test admin dispute listing/filtering and approve/reject review transitions."""
    actors = _seed_actors(disputes_app)
    admin_client = disputes_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    stu1_client = disputes_app.test_client()
    stu1_headers = _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")

    stu2_client = disputes_app.test_client()
    stu2_headers = _login_and_csrf(stu2_client, str(actors["stu2_email"]), "StudentPass123!")

    staff_client = disputes_app.test_client()
    staff_headers = _login_and_csrf(staff_client, str(actors["staff_email"]), "StaffPass123!")

    fine_a = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Dispute A to approve"
    )
    fine_b = _issue_fine(
        admin_client, admin_headers, str(actors["stu2_public_id"]), "Dispute B to reject"
    )

    assert (
        stu1_client.post(
            f"/api/v1/student/fines/{fine_a['referenceNo']}/dispute",
            headers=stu1_headers,
            json={"reason": "Wrong room recorded in inspection log."},
        ).status_code
        == 201
    )
    assert (
        stu2_client.post(
            f"/api/v1/student/fines/{fine_b['referenceNo']}/dispute",
            headers=stu2_headers,
            json={"reason": "Disputing noise complaint."},
        ).status_code
        == 201
    )

    # RBAC: student and staff cannot access admin dispute endpoints
    assert stu1_client.get("/api/v1/admin/fines/disputes", headers=stu1_headers).status_code == 403
    assert (
        staff_client.get("/api/v1/admin/fines/disputes", headers=staff_headers).status_code == 403
    )
    assert (
        stu1_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
            headers=stu1_headers,
            json={"decision": "approve", "reason": "Self-approve attempt"},
        ).status_code
        == 403
    )
    assert (
        staff_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
            headers=staff_headers,
            json={"decision": "approve", "reason": "Staff attempt"},
        ).status_code
        == 403
    )

    # Admin lists open disputes & filters by student/reference/pagination
    list_resp = admin_client.get("/api/v1/admin/fines/disputes?status=open&page=1&page_size=10")
    assert list_resp.status_code == 200
    disputes = list_resp.get_json()["disputes"]
    assert len(disputes) == 2
    assert list_resp.get_json()["pagination"]["total"] == 2

    stu1_list = admin_client.get(f"/api/v1/admin/fines/disputes?student={actors['stu1_roll']}")
    assert stu1_list.status_code == 200
    assert [d["referenceNo"] for d in stu1_list.get_json()["disputes"]] == [fine_a["referenceNo"]]

    # Missing reason or invalid decision rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
            headers=admin_headers,
            json={"decision": "approve", "reason": "   "},
        ).status_code
        == 400
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
            headers=admin_headers,
            json={"decision": "ignore", "reason": "Invalid decision"},
        ).status_code
        == 400
    )

    # Approve Dispute A -> Fine transitions disputed -> waived
    approve_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
        headers=admin_headers,
        json={"decision": "approve", "reason": "Verified room log mismatch; fine waived."},
    )
    assert approve_resp.status_code == 200, approve_resp.get_json()
    approved_fine = approve_resp.get_json()["fine"]
    assert approved_fine["status"] == "waived"
    assert approved_fine["amountInr"] == fine_a["amountInr"]
    assert approved_fine["dueDate"] == fine_a["dueDate"]
    assert approved_fine["dispute"]["status"] == "approved"
    assert approved_fine["dispute"]["decisionReason"] == "Verified room log mismatch; fine waived."
    assert approved_fine["dispute"]["decidedBy"] == "Dr. K. S. Verma"
    assert [h["action"] for h in approved_fine["history"]] == [
        "issued",
        "dispute_submitted",
        "dispute_approved",
    ]

    # Repeated review rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/dispute/review",
            headers=admin_headers,
            json={"decision": "reject", "reason": "Conflicting second decision"},
        ).status_code
        == 409
    )

    # Reject Dispute B -> Fine transitions disputed -> pending (preserving amount & dueDate)
    reject_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine_b['referenceNo']}/dispute/review",
        headers=admin_headers,
        json={"decision": "reject", "reason": "CCTV confirms corridor violation."},
    )
    assert reject_resp.status_code == 200, reject_resp.get_json()
    rejected_fine = reject_resp.get_json()["fine"]
    assert rejected_fine["status"] == "pending"
    assert rejected_fine["amountInr"] == fine_b["amountInr"]
    assert rejected_fine["dueDate"] == fine_b["dueDate"]
    assert rejected_fine["resolvedBy"] is None
    assert rejected_fine["resolutionReason"] is None
    assert rejected_fine["dispute"]["status"] == "rejected"
    assert rejected_fine["dispute"]["decisionReason"] == "CCTV confirms corridor violation."
    assert [h["action"] for h in rejected_fine["history"]] == [
        "issued",
        "dispute_submitted",
        "dispute_rejected",
    ]

    # Student sees dispute outcome without internal admin identity fields
    stu1_detail = stu1_client.get(f"/api/v1/student/fines/{fine_a['referenceNo']}").get_json()[
        "fine"
    ]
    assert stu1_detail["status"] == "waived"
    assert stu1_detail["dispute"]["status"] == "approved"
    assert "decidedBy" not in stu1_detail["dispute"]

    # Verify student notifications, audit logs, and zero payments created
    with disputes_app.app_context():
        assert db.session.execute(select(Payment)).scalars().all() == []
        notif_events = [
            n.event_type
            for n in db.session.execute(
                select(Notification).where(
                    Notification.event_type.in_(["fine_dispute_approved", "fine_dispute_rejected"])
                )
            )
            .scalars()
            .all()
        ]
        assert sorted(notif_events) == ["fine_dispute_approved", "fine_dispute_rejected"]
        audit_actions = [
            a.action
            for a in db.session.execute(
                select(AuditLog).where(
                    AuditLog.action.in_(["fine_dispute_approved", "fine_dispute_rejected"])
                )
            )
            .scalars()
            .all()
        ]
        assert sorted(audit_actions) == ["fine_dispute_approved", "fine_dispute_rejected"]


@pytest.mark.db
def test_dispute_transaction_rollback_and_payment_triggers_preserved(disputes_app, monkeypatch):
    """Verify mid-transaction failure rolls back dispute/review and preserves payment triggers."""
    actors = _seed_actors(disputes_app)
    admin_client = disputes_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")
    stu1_client = disputes_app.test_client()
    stu1_headers = _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")

    fine = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Rollback test fine"
    )

    import app.fines.service as fines_service

    def _boom(**kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(fines_service, "record_audit_event", _boom)

    resp = stu1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/dispute",
        headers=stu1_headers,
        json={"reason": "Should rollback completely."},
    )
    assert resp.status_code == 500

    with disputes_app.app_context():
        fine_row = db.session.get(Fine, fine["fineId"])
        assert fine_row.status == "pending"
        assert db.session.execute(select(FineDispute)).scalars().all() == []
        # Only the initial 'issued' history entry remains
        histories = (
            db.session.execute(select(FineHistory).where(FineHistory.fine_id == fine_row.id))
            .scalars()
            .all()
        )
        assert [h.action for h in histories] == ["issued"]

    # T2a trigger still prevents marking a fine paid without a Payment row
    with disputes_app.app_context():
        fine_row = db.session.get(Fine, fine["fineId"])
        fine_row.status = "paid"
        fine_row.paid_at = datetime.now(UTC)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


@pytest.mark.db
def test_concurrent_dispute_review_serializes_with_row_lock(disputes_app):
    """Two concurrent review attempts cannot produce conflicting decisions."""
    actors = _seed_actors(disputes_app)
    admin_client = disputes_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")
    stu1_client = disputes_app.test_client()
    stu1_headers = _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")

    fine = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Concurrency test fine"
    )
    assert (
        stu1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/dispute",
            headers=stu1_headers,
            json={"reason": "Testing concurrent review locking."},
        ).status_code
        == 201
    )

    ref_no = fine["referenceNo"]

    def _run_review(admin_id: int, decision: str) -> str:
        with disputes_app.app_context():
            admin_user = db.session.get(User, admin_id)
            try:
                review_fine_dispute(
                    admin_user,
                    ref_no,
                    {"decision": decision, "reason": f"Concurrent {decision}"},
                )
                return f"ok:{decision}"
            except FineServiceError as exc:
                return f"err:{exc.status}:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_review, int(actors["admin1_id"]), "approve")
        f2 = pool.submit(_run_review, int(actors["admin2_id"]), "reject")
        outcomes = sorted([f1.result(), f2.result()])

    assert any(o.startswith("ok:") for o in outcomes)
    assert any(o == "err:409:invalid_state_transition" for o in outcomes)

    with disputes_app.app_context():
        dispute = db.session.execute(
            select(FineDispute).where(FineDispute.fine_id == fine["fineId"])
        ).scalar_one()
        assert dispute.status in {"approved", "rejected"}
        fine_row = db.session.get(Fine, fine["fineId"])
        if dispute.status == "approved":
            assert fine_row.status == "waived"
        else:
            assert fine_row.status == "pending"
        # Ensure fine amount never changed
        assert fine_row.amount_inr == Decimal("500.00")
