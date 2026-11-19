"""Phase 3E.1 Backend Fines Service & Core APIs Integration Tests."""

from __future__ import annotations

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
from app.models.audit import AuditLog
from app.models.fines import Fine, FineHistory
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.payments import Payment
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def fines_app():
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
def _clean_fines_tables(fines_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    clear_console_outbox()
    owner_engine = create_engine(fines_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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
        admin = User(
            email="warden.fines@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
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
            email="aarav.fines@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="meera.fines@hostelcare.test",
            full_name="Meera Krishnan",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        pending_stu = User(
            email="pending.fines@hostelcare.test",
            full_name="Pending Student",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="pending",
        )
        staff = User(
            email="ramesh.fines@hostelcare.test",
            full_name="Ramesh Babu",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add_all([stu1, stu2, pending_stu, staff])
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(
                    user_id=stu1.id,
                    roll_number="2026CSB1001",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StudentProfile(
                    user_id=stu2.id,
                    roll_number="2026ECE1002",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StudentProfile(
                    user_id=pending_stu.id,
                    roll_number="2026MECH1003",
                ),
                StaffProfile(
                    user_id=staff.id,
                    staff_code="STF-1001",
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
                allocated_by=admin.id,
            )
        )
        db.session.commit()

        return {
            "admin_email": admin.email,
            "stu1_email": stu1.email,
            "stu1_public_id": str(stu1.public_id),
            "stu1_roll": "2026CSB1001",
            "stu2_email": stu2.email,
            "stu2_public_id": str(stu2.public_id),
            "stu2_roll": "2026ECE1002",
            "pending_public_id": str(pending_stu.public_id),
            "staff_email": staff.email,
            "staff_public_id": str(staff.public_id),
            "room_id": room.id,
        }


@pytest.mark.db
def test_issue_fine_validation_sequence_and_mass_assignment_protection(fines_app):
    """Test valid fine issuance, decimal precision, validation, and mass-assignment defense."""
    actors = _seed_actors(fines_app)
    admin_client = fines_app.test_client()
    headers = _login_and_csrf(admin_client, str(actors["admin_email"]), "AdminPass123!")

    today = date.today()
    due = (today + timedelta(days=14)).isoformat()

    # Valid fine issuance (with attempted mass-assignment of protected fields)
    resp = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": actors["stu1_public_id"],
            "category": "Prohibited Electrical Appliance",
            "description": "Unauthorized high-wattage immersion heater found in room A-101.",
            "amount_inr": "500.75",
            "due_date": due,
            "status": "paid",
            "reference_no": "FIN-9999-99999",
            "issued_by": 99999,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    fine = resp.get_json()["fine"]
    assert fine["referenceNo"].startswith(f"FIN-{today.year}-")
    assert len(fine["referenceNo"]) == 14  # FIN-YYYY-NNNNN
    assert fine["status"] == "pending"
    assert fine["amountInr"] == "500.75"
    assert fine["room"] == "A-101"
    assert fine["block"] == "Block A"
    assert fine["issuedBy"] == "Dr. K. S. Verma"
    assert len(fine["history"]) == 1
    assert fine["history"][0]["action"] == "issued"
    assert fine["history"][0]["toStatus"] == "pending"

    # Second fine increments sequence
    resp2 = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": actors["stu2_roll"],
            "description": "Late night noise violation in common corridor.",
            "amount_inr": "250.00",
            "due_date": due,
        },
    )
    assert resp2.status_code == 201, resp2.get_json()
    fine2 = resp2.get_json()["fine"]
    assert fine2["referenceNo"] != fine["referenceNo"]
    assert fine2["referenceNo"].startswith(f"FIN-{today.year}-")

    # Invalid amounts
    for bad_amount in [0, -100, "abc", True, "500.123", None, ""]:
        bad_resp = admin_client.post(
            "/api/v1/admin/fines",
            headers=headers,
            json={
                "student_id": actors["stu1_public_id"],
                "description": "Valid description for invalid amount test.",
                "amount_inr": bad_amount,
                "due_date": due,
            },
        )
        assert bad_resp.status_code == 400, f"Expected 400 for amount={bad_amount!r}"

    # Invalid due dates (missing, malformed, before issue_date)
    for bad_due in [None, "", "15-11-2026", (today - timedelta(days=1)).isoformat()]:
        bad_resp = admin_client.post(
            "/api/v1/admin/fines",
            headers=headers,
            json={
                "student_id": actors["stu1_public_id"],
                "description": "Valid description for invalid date test.",
                "amount_inr": "100.00",
                "issue_date": today.isoformat(),
                "due_date": bad_due,
            },
        )
        assert bad_resp.status_code == 400, f"Expected 400 for due_date={bad_due!r}"

    # Missing description
    no_desc = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": actors["stu1_public_id"],
            "description": "   ",
            "amount_inr": "100.00",
            "due_date": due,
        },
    )
    assert no_desc.status_code == 400

    # Invalid / ineligible student (nonexistent, staff, pending student)
    missing_stu = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": "2026NONE9999",
            "description": "Nonexistent student test.",
            "amount_inr": "100.00",
            "due_date": due,
        },
    )
    assert missing_stu.status_code == 404

    staff_target = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": actors["staff_public_id"],
            "description": "Cannot fine staff member.",
            "amount_inr": "100.00",
            "due_date": due,
        },
    )
    assert staff_target.status_code == 404

    pending_target = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": actors["pending_public_id"],
            "description": "Cannot fine pending student.",
            "amount_inr": "100.00",
            "due_date": due,
        },
    )
    assert pending_target.status_code == 400


@pytest.mark.db
def test_fines_rbac_authorization_and_admin_filtering(fines_app):
    """Test RBAC on admin/student fine endpoints and admin list filtering + pagination."""
    actors = _seed_actors(fines_app)

    anon_client = fines_app.test_client()
    assert anon_client.get("/api/v1/admin/fines").status_code == 401
    assert anon_client.get("/api/v1/student/fines").status_code == 401

    stu_client = fines_app.test_client()
    stu_headers = _login_and_csrf(stu_client, str(actors["stu1_email"]), "StudentPass123!")

    staff_client = fines_app.test_client()
    staff_headers = _login_and_csrf(staff_client, str(actors["staff_email"]), "StaffPass123!")

    admin_client = fines_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin_email"]), "AdminPass123!")

    # Student and Staff cannot access admin fine endpoints
    for client_obj, hdrs in [(stu_client, stu_headers), (staff_client, staff_headers)]:
        assert client_obj.get("/api/v1/admin/fines", headers=hdrs).status_code == 403
        assert (
            client_obj.post(
                "/api/v1/admin/fines",
                headers=hdrs,
                json={
                    "student_id": actors["stu1_public_id"],
                    "description": "Unauthorized attempt",
                    "amount_inr": "100.00",
                    "due_date": date.today().isoformat(),
                },
            ).status_code
            == 403
        )

    # Admin and Staff cannot access student fine endpoints
    assert admin_client.get("/api/v1/student/fines", headers=admin_headers).status_code == 403
    assert staff_client.get("/api/v1/student/fines", headers=staff_headers).status_code == 403

    # Admin creates an overdue fine for stu1 and a future fine for stu2
    past_issue = (date.today() - timedelta(days=20)).isoformat()
    past_due = (date.today() - timedelta(days=5)).isoformat()
    future_due = (date.today() + timedelta(days=10)).isoformat()

    r1 = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": actors["stu1_public_id"],
            "description": "Overdue library damage penalty.",
            "amount_inr": "300.00",
            "issue_date": past_issue,
            "due_date": past_due,
        },
    )
    assert r1.status_code == 201
    ref1 = r1.get_json()["fine"]["referenceNo"]

    r2 = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": actors["stu2_public_id"],
            "description": "Current hostel window damage penalty.",
            "amount_inr": "450.00",
            "due_date": future_due,
        },
    )
    assert r2.status_code == 201
    ref2 = r2.get_json()["fine"]["referenceNo"]

    # Filter by overdue=true
    overdue_resp = admin_client.get("/api/v1/admin/fines?overdue=true")
    assert overdue_resp.status_code == 200
    overdue_refs = [f["referenceNo"] for f in overdue_resp.get_json()["fines"]]
    assert overdue_refs == [ref1]

    # Filter by student roll number
    stu2_resp = admin_client.get(f"/api/v1/admin/fines?student={actors['stu2_roll']}")
    assert stu2_resp.status_code == 200
    assert [f["referenceNo"] for f in stu2_resp.get_json()["fines"]] == [ref2]

    # Filter by reference
    ref_resp = admin_client.get(f"/api/v1/admin/fines?reference={ref1}")
    assert ref_resp.status_code == 200
    assert [f["referenceNo"] for f in ref_resp.get_json()["fines"]] == [ref1]

    # Filter by date range
    date_resp = admin_client.get(
        f"/api/v1/admin/fines?date_from={date.today().isoformat()}&date_to={date.today().isoformat()}"
    )
    assert date_resp.status_code == 200
    assert [f["referenceNo"] for f in date_resp.get_json()["fines"]] == [ref2]

    # Pagination
    page_resp = admin_client.get("/api/v1/admin/fines?page=1&page_size=1")
    assert page_resp.status_code == 200
    page_body = page_resp.get_json()
    assert len(page_body["fines"]) == 1
    assert page_body["pagination"]["total"] == 2
    assert page_body["pagination"]["totalPages"] == 2


@pytest.mark.db
def test_student_fine_ownership_and_idor_prevention(fines_app):
    """Students can only list and view their own fines; IDOR attempts are blocked."""
    actors = _seed_actors(fines_app)
    admin_client = fines_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin_email"]), "AdminPass123!")

    due = (date.today() + timedelta(days=7)).isoformat()
    f1 = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": actors["stu1_public_id"],
            "description": "Student 1 private fine description.",
            "amount_inr": "200.00",
            "due_date": due,
        },
    ).get_json()["fine"]

    f2 = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": actors["stu2_public_id"],
            "description": "Student 2 private fine description.",
            "amount_inr": "350.00",
            "due_date": due,
        },
    ).get_json()["fine"]

    stu1_client = fines_app.test_client()
    _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")

    # Manipulating query params does not return Student 2's fines
    list_resp = stu1_client.get(
        f"/api/v1/student/fines?student_id={actors['stu2_public_id']}&student={actors['stu2_roll']}"
    )
    assert list_resp.status_code == 200
    stu1_fines = list_resp.get_json()["fines"]
    assert [f["referenceNo"] for f in stu1_fines] == [f1["referenceNo"]]
    assert "Student 2 private fine description" not in str(stu1_fines)

    # Own detail succeeds without leaking internal admin IDs
    own_detail = stu1_client.get(f"/api/v1/student/fines/{f1['referenceNo']}")
    assert own_detail.status_code == 200
    assert own_detail.get_json()["fine"]["referenceNo"] == f1["referenceNo"]
    assert "fineId" not in own_detail.get_json()["fine"]

    # Accessing Student 2's fine by reference_no or numeric ID is forbidden (403)
    idor_ref = stu1_client.get(f"/api/v1/student/fines/{f2['referenceNo']}")
    assert idor_ref.status_code == 403
    assert "Student 2 private fine description" not in str(idor_ref.get_json())

    idor_num = stu1_client.get(f"/api/v1/student/fines/{f2['fineId']}")
    assert idor_num.status_code == 403

    # Unknown fine returns 404
    assert stu1_client.get("/api/v1/student/fines/FIN-2026-99999").status_code == 404


@pytest.mark.db
def test_fine_waive_cancel_state_transitions_and_paid_protection(fines_app):
    """Test waive/cancel transitions, mandatory reasons, and paid-fine immutability."""
    actors = _seed_actors(fines_app)
    admin_client = fines_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin_email"]), "AdminPass123!")

    due = (date.today() + timedelta(days=7)).isoformat()

    def _create_fine(desc: str) -> dict:
        r = admin_client.post(
            "/api/v1/admin/fines",
            headers=admin_headers,
            json={
                "student_id": actors["stu1_public_id"],
                "description": desc,
                "amount_inr": "400.00",
                "due_date": due,
            },
        )
        assert r.status_code == 201
        return r.get_json()["fine"]

    fine_a = _create_fine("Fine A to waive")
    fine_b = _create_fine("Fine B to cancel")
    fine_c = _create_fine("Fine C marked paid with payment record")

    # Missing reason rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "   "},
        ).status_code
        == 400
    )

    # Waive Fine A
    waive_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine_a['referenceNo']}/waive",
        headers=admin_headers,
        json={"reason": "First-time offense waived by Chief Warden."},
    )
    assert waive_resp.status_code == 200
    waived = waive_resp.get_json()["fine"]
    assert waived["status"] == "waived"
    assert waived["resolutionReason"] == "First-time offense waived by Chief Warden."
    assert waived["resolvedBy"] == "Dr. K. S. Verma"
    assert waived["version"] == 2
    assert [h["action"] for h in waived["history"]] == ["issued", "waived"]

    # Cannot waive or cancel an already waived fine
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "Duplicate waive"},
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_a['referenceNo']}/cancel",
            headers=admin_headers,
            json={"reason": "Cannot cancel waived"},
        ).status_code
        == 409
    )

    # Cancel Fine B
    cancel_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine_b['referenceNo']}/cancel",
        headers=admin_headers,
        json={"reason": "Issued to wrong room resident."},
    )
    assert cancel_resp.status_code == 200
    cancelled = cancel_resp.get_json()["fine"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["resolutionReason"] == "Issued to wrong room resident."
    assert [h["action"] for h in cancelled["history"]] == ["issued", "cancelled"]

    # Cannot waive or cancel an already cancelled fine
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_b['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "Cannot waive cancelled"},
        ).status_code
        == 409
    )

    # Mark Fine C as paid with a valid Payment record (respecting T2a, T2b, T3)
    with fines_app.app_context():
        fine_c_row = db.session.get(Fine, fine_c["fineId"])
        admin_row = db.session.execute(
            select(User).where(User.email == actors["admin_email"])
        ).scalar_one()
        now = datetime.now(UTC)
        fine_c_row.status = "paid"
        fine_c_row.paid_at = now
        db.session.add(
            Payment(
                fine_id=fine_c_row.id,
                channel="manual",
                amount_inr=Decimal("400.00"),
                currency="INR",
                payment_method="cash",
                verification_method="manual_entry",
                verified_at=now,
                recorded_by=admin_row.id,
                manual_reference="CASH-2026-001",
            )
        )
        db.session.commit()

    # Paid fine cannot be waived or cancelled
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_c['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "Should fail on paid fine"},
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_c['referenceNo']}/cancel",
            headers=admin_headers,
            json={"reason": "Should fail on paid fine"},
        ).status_code
        == 409
    )

    # Verify audit logs recorded
    with fines_app.app_context():
        actions = [
            row.action
            for row in db.session.execute(
                select(AuditLog).where(AuditLog.target_type == "fine").order_by(AuditLog.id.asc())
            )
            .scalars()
            .all()
        ]
        assert actions.count("fine_issued") == 3
        assert "fine_waived" in actions
        assert "fine_cancelled" in actions


@pytest.mark.db
def test_fine_transaction_rollback_and_payment_triggers_preserved(fines_app, monkeypatch):
    """Verify mid-transaction failure rolls back fine/history and T2a trigger remains active."""
    actors = _seed_actors(fines_app)
    admin_client = fines_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin_email"]), "AdminPass123!")

    # Simulate audit failure after fine + history flush
    import app.fines.service as fines_service

    def _boom(**kwargs):
        raise RuntimeError("Simulated audit write failure")

    monkeypatch.setattr(fines_service, "record_audit_event", _boom)

    resp = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": actors["stu1_public_id"],
            "description": "Should rollback completely on error.",
            "amount_inr": "150.00",
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
        },
    )
    assert resp.status_code == 500

    with fines_app.app_context():
        assert db.session.execute(select(Fine)).scalars().all() == []
        assert db.session.execute(select(FineHistory)).scalars().all() == []

    # Verify T2a trigger still prevents marking a fine paid without a Payment row
    with fines_app.app_context():
        stu_row = db.session.execute(
            select(User).where(User.email == actors["stu1_email"])
        ).scalar_one()
        admin_row = db.session.execute(
            select(User).where(User.email == actors["admin_email"])
        ).scalar_one()
        bad_fine = Fine(
            student_user_id=stu_row.id,
            description="Trigger T2a check",
            amount_inr=Decimal("100.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=3),
            issued_by=admin_row.id,
            status="paid",
            paid_at=datetime.now(UTC),
        )
        db.session.add(bad_fine)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
