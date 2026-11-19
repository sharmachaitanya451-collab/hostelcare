"""Phase 3E.3 Payment Recording, Payment Integrity & Receipts PostgreSQL Integration Tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.fines.payments_service import record_manual_fine_payment
from app.fines.service import FineServiceError
from app.models.audit import AuditLog
from app.models.fines import Fine, FineHistory
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.payments import Payment, PaymentAttempt, PaymentEvent
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def payments_app():
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
def _clean_payments_tables(payments_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    clear_console_outbox()
    owner_engine = create_engine(payments_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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
            email="warden1.pay@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        admin2 = User(
            email="warden2.pay@hostelcare.test",
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
            email="aarav.pay@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="meera.pay@hostelcare.test",
            full_name="Meera Krishnan",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        staff = User(
            email="ramesh.pay@hostelcare.test",
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
                    roll_number="2026CSB3001",
                    reviewed_by=admin1.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StudentProfile(
                    user_id=stu2.id,
                    roll_number="2026ECE3002",
                    reviewed_by=admin1.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="Approved",
                ),
                StaffProfile(
                    user_id=staff.id,
                    staff_code="STF-3001",
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
            "stu1_email": stu1.email,
            "stu1_public_id": str(stu1.public_id),
            "stu2_email": stu2.email,
            "stu2_public_id": str(stu2.public_id),
            "staff_email": staff.email,
        }


def _issue_fine(
    admin_client, headers: dict[str, str], student_id: str, desc: str, amount: str = "500.00"
) -> dict:
    resp = admin_client.post(
        "/api/v1/admin/fines",
        headers=headers,
        json={
            "student_id": student_id,
            "category": "Disciplinary Penalty",
            "description": desc,
            "amount_inr": amount,
            "due_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["fine"]


@pytest.mark.db
def test_payment_recording_validation_methods_and_receipt_generation(payments_app):
    """Test valid full payments, unique receipts, invalid amounts/methods, and duplicate refs."""
    actors = _seed_actors(payments_app)
    admin_client = payments_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    fine1 = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Fine 1 cash", "500.00"
    )
    fine2 = _issue_fine(
        admin_client, admin_headers, str(actors["stu2_public_id"]), "Fine 2 bank", "750.50"
    )
    fine_waived = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Fine waived", "300.00"
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_waived['referenceNo']}/waive",
            headers=admin_headers,
            json={"reason": "Waived"},
        ).status_code
        == 200
    )

    # Partial payment and overpayment rejected
    for bad_amt in ["250.00", "600.00", "0", "-100", "abc"]:
        assert (
            admin_client.post(
                f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
                headers=admin_headers,
                json={
                    "amount_inr": bad_amt,
                    "payment_method": "cash",
                    "manual_reference": "CASH-BAD-1",
                },
            ).status_code
            == 400
        )

    # Invalid payment method and missing reference rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
            headers=admin_headers,
            json={
                "amount_inr": "500.00",
                "payment_method": "crypto",
                "manual_reference": "REF-1",
            },
        ).status_code
        == 400
    )
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
            headers=admin_headers,
            json={
                "amount_inr": "500.00",
                "payment_method": "cash",
                "manual_reference": "   ",
            },
        ).status_code
        == 400
    )

    # Payment against waived fine rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine_waived['referenceNo']}/payments",
            headers=admin_headers,
            json={
                "amount_inr": "300.00",
                "payment_method": "cash",
                "manual_reference": "CASH-WAIVED-1",
            },
        ).status_code
        == 409
    )

    # Valid full payment for fine1 (attempting to spoof receipt_number ignored)
    pay1_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
        headers=admin_headers,
        json={
            "amount_inr": "500.00",
            "payment_method": "cash",
            "manual_reference": "CASH-REG-001",
            "receipt_number": "RCP-FAKE-99999",
        },
    )
    assert pay1_resp.status_code == 201, pay1_resp.get_json()
    body1 = pay1_resp.get_json()
    assert body1["fine"]["status"] == "paid"
    assert body1["fine"]["paidAt"] is not None
    rcp1 = body1["receipt"]["receiptNumber"]
    assert rcp1.startswith(f"RCP-{date.today().year}-")
    assert rcp1 != "RCP-FAKE-99999"
    assert body1["receipt"]["institution"] == "HostelCare"
    assert body1["receipt"]["paymentStatus"] == "paid"
    assert body1["receipt"]["amountInr"] == "500.00"
    assert [h["action"] for h in body1["fine"]["history"]] == [
        "issued",
        "manual_payment_recorded",
    ]

    # Duplicate payment on already paid fine rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
            headers=admin_headers,
            json={
                "amount_inr": "500.00",
                "payment_method": "cash",
                "manual_reference": "CASH-REG-002",
            },
        ).status_code
        == 409
    )

    # Duplicate transaction reference across fines rejected
    assert (
        admin_client.post(
            f"/api/v1/admin/fines/{fine2['referenceNo']}/payments",
            headers=admin_headers,
            json={
                "amount_inr": "750.50",
                "payment_method": "bank_transfer",
                "manual_reference": "cash-reg-001",
            },
        ).status_code
        == 409
    )

    # Valid bank_transfer payment for fine2 generates distinct receipt
    pay2_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine2['referenceNo']}/payments",
        headers=admin_headers,
        json={
            "amount_inr": "750.50",
            "payment_method": "bank_transfer",
            "manual_reference": "NEFT-2026-8891",
        },
    )
    assert pay2_resp.status_code == 201, pay2_resp.get_json()
    rcp2 = pay2_resp.get_json()["receipt"]["receiptNumber"]
    assert rcp2 != rcp1
    assert rcp2.startswith(f"RCP-{date.today().year}-")

    # Verify audit log and student notification
    with payments_app.app_context():
        assert (
            len(
                db.session.execute(
                    select(AuditLog).where(AuditLog.action == "fine_payment_recorded")
                )
                .scalars()
                .all()
            )
            == 2
        )
        assert (
            len(
                db.session.execute(
                    select(Notification).where(Notification.event_type == "fine_payment_recorded")
                )
                .scalars()
                .all()
            )
            == 2
        )


@pytest.mark.db
def test_student_payment_history_receipt_ownership_and_rbac(payments_app):
    """Test student payment/receipt access, cross-student IDOR blocking, and RBAC."""
    actors = _seed_actors(payments_app)
    admin_client = payments_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    stu1_client = payments_app.test_client()
    stu1_headers = _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")
    stu2_client = payments_app.test_client()
    _login_and_csrf(stu2_client, str(actors["stu2_email"]), "StudentPass123!")
    staff_client = payments_app.test_client()
    staff_headers = _login_and_csrf(staff_client, str(actors["staff_email"]), "StaffPass123!")

    fine1 = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Stu1 paid fine", "400.00"
    )
    fine2 = _issue_fine(
        admin_client, admin_headers, str(actors["stu2_public_id"]), "Stu2 paid fine", "600.00"
    )

    # Students and staff cannot record payments
    assert (
        stu1_client.post(
            f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
            headers=stu1_headers,
            json={"amount_inr": "400.00", "payment_method": "upi", "manual_reference": "UPI-1"},
        ).status_code
        == 403
    )
    assert (
        staff_client.post(
            f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
            headers=staff_headers,
            json={"amount_inr": "400.00", "payment_method": "upi", "manual_reference": "UPI-1"},
        ).status_code
        == 403
    )

    # Before payment, student sees outstanding balance and zero payments
    pre_pay = stu1_client.get(f"/api/v1/student/fines/{fine1['referenceNo']}/payments")
    assert pre_pay.status_code == 200
    assert pre_pay.get_json()["outstandingInr"] == "400.00"
    assert pre_pay.get_json()["payments"] == []

    # Record payments for both fines
    rcp1 = admin_client.post(
        f"/api/v1/admin/fines/{fine1['referenceNo']}/payments",
        headers=admin_headers,
        json={"amount_inr": "400.00", "payment_method": "upi", "manual_reference": "UPI-STU1-1"},
    ).get_json()["receipt"]["receiptNumber"]

    rcp2 = admin_client.post(
        f"/api/v1/admin/fines/{fine2['referenceNo']}/payments",
        headers=admin_headers,
        json={"amount_inr": "600.00", "payment_method": "upi", "manual_reference": "UPI-STU2-1"},
    ).get_json()["receipt"]["receiptNumber"]

    # Student 1 sees own payment & receipt without internal admin fields
    post_pay = stu1_client.get(f"/api/v1/student/fines/{fine1['referenceNo']}/payments")
    assert post_pay.status_code == 200
    assert post_pay.get_json()["outstandingInr"] == "0.00"
    assert len(post_pay.get_json()["payments"]) == 1
    assert post_pay.get_json()["payments"][0]["receiptNumber"] == rcp1

    own_rcp = stu1_client.get(f"/api/v1/student/receipts/{rcp1}")
    assert own_rcp.status_code == 200
    receipt_data = own_rcp.get_json()["receipt"]
    assert receipt_data["receiptNumber"] == rcp1
    assert receipt_data["studentName"] == "Aarav Sharma"
    assert "recordedBy" not in receipt_data

    # Cross-student payment history & receipt access rejected (403)
    assert (
        stu1_client.get(f"/api/v1/student/fines/{fine2['referenceNo']}/payments").status_code == 403
    )
    assert stu1_client.get(f"/api/v1/student/receipts/{rcp2}").status_code == 403
    assert stu2_client.get(f"/api/v1/student/receipts/{rcp1}").status_code == 403


@pytest.mark.db
def test_failed_payment_attempts_and_immutability_and_rollback(payments_app, monkeypatch):
    """Test failed payment attempts, T3/immutability triggers, and transaction rollback."""
    actors = _seed_actors(payments_app)
    admin_client = payments_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    fine = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Attempt test fine", "450.00"
    )

    # Record failed payment attempt -> fine stays pending, no Payment or Receipt created
    fail_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/payment-attempts",
        headers=admin_headers,
        json={
            "status": "failed",
            "payment_method": "upi",
            "failure_code": "BANK_DECLINED",
            "failure_reason": "Insufficient balance in payer account.",
        },
    )
    assert fail_resp.status_code == 201, fail_resp.get_json()
    assert fail_resp.get_json()["attempt"]["status"] == "failed"

    with payments_app.app_context():
        fine_row = db.session.get(Fine, fine["fineId"])
        assert fine_row.status == "pending"
        assert db.session.execute(select(Payment)).scalars().all() == []
        assert len(db.session.execute(select(PaymentAttempt)).scalars().all()) == 1
        assert len(db.session.execute(select(PaymentEvent)).scalars().all()) == 1

    # Rollback on mid-transaction failure leaves zero payments and fine still pending
    import app.fines.payments_service as pay_service

    def _boom(**kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(pay_service, "record_audit_event", _boom)

    err_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/payments",
        headers=admin_headers,
        json={
            "amount_inr": "450.00",
            "payment_method": "cash",
            "manual_reference": "CASH-ROLLBACK-1",
        },
    )
    assert err_resp.status_code == 500
    monkeypatch.undo()

    with payments_app.app_context():
        fine_row = db.session.get(Fine, fine["fineId"])
        assert fine_row.status == "pending"
        assert db.session.execute(select(Payment)).scalars().all() == []

    # T3 trigger: Payment with mismatched amount fails at DB level
    with payments_app.app_context():
        fine_row = db.session.get(Fine, fine["fineId"])
        fine_row.status = "paid"
        fine_row.paid_at = datetime.now(UTC)
        db.session.add(
            Payment(
                fine_id=fine_row.id,
                channel="manual",
                amount_inr=Decimal("100.00"),
                currency="INR",
                payment_method="cash",
                verification_method="manual_entry",
                verified_at=datetime.now(UTC),
                recorded_by=int(actors["admin1_id"]),
                manual_reference="CASH-T3-FAIL",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    # Record a legitimate payment and verify Payment row cannot be updated by hostelcare_app
    ok_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/payments",
        headers=admin_headers,
        json={
            "amount_inr": "450.00",
            "payment_method": "cash",
            "manual_reference": "CASH-IMMUTABLE-1",
        },
    )
    assert ok_resp.status_code == 201
    with payments_app.app_context():
        with pytest.raises(ProgrammingError):
            db.session.execute(
                text("UPDATE public.payments SET manual_reference = 'TAMPERED' WHERE id = 1")
            )
            db.session.commit()
        db.session.rollback()


@pytest.mark.db
def test_concurrent_payment_recording_prevents_double_payment(payments_app):
    """Two concurrent payment attempts against the same fine serialize via FOR UPDATE."""
    actors = _seed_actors(payments_app)
    admin_client = payments_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    fine = _issue_fine(
        admin_client, admin_headers, str(actors["stu1_public_id"]), "Concurrent pay", "500.00"
    )
    ref_no = fine["referenceNo"]

    def _pay(admin_id: int, ref: str) -> str:
        with payments_app.app_context():
            admin_user = db.session.get(User, admin_id)
            try:
                record_manual_fine_payment(
                    admin_user,
                    ref_no,
                    {
                        "amount_inr": "500.00",
                        "payment_method": "cash",
                        "manual_reference": ref,
                    },
                )
                return f"ok:{ref}"
            except FineServiceError as exc:
                return f"err:{exc.status}:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_pay, int(actors["admin1_id"]), "CONC-CASH-1")
        f2 = pool.submit(_pay, int(actors["admin2_id"]), "CONC-CASH-2")
        outcomes = sorted([f1.result(), f2.result()])

    assert any(o.startswith("ok:") for o in outcomes)
    assert any(o == "err:409:invalid_state_transition" for o in outcomes)

    with payments_app.app_context():
        payments = (
            db.session.execute(select(Payment).where(Payment.fine_id == fine["fineId"]))
            .scalars()
            .all()
        )
        assert len(payments) == 1
        assert payments[0].amount_inr == Decimal("500.00")
        assert (
            len(
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fine["fineId"],
                        FineHistory.action == "manual_payment_recorded",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )


@pytest.mark.db
def test_receipt_pdf_download_and_authorization(payments_app):
    """Test authorized admin/student PDF receipt downloads, IDOR blocking, and 404 handling."""
    actors = _seed_actors(payments_app)
    admin_client = payments_app.test_client()
    admin_headers = _login_and_csrf(admin_client, str(actors["admin1_email"]), "AdminPass123!")

    stu1_client = payments_app.test_client()
    _login_and_csrf(stu1_client, str(actors["stu1_email"]), "StudentPass123!")
    stu2_client = payments_app.test_client()
    _login_and_csrf(stu2_client, str(actors["stu2_email"]), "StudentPass123!")
    anon_client = payments_app.test_client()

    fine_resp = admin_client.post(
        "/api/v1/admin/fines",
        headers=admin_headers,
        json={
            "student_id": str(actors["stu1_public_id"]),
            "category": "Late Entry",
            "description": "Returned after hostel gate closing hours.",
            "amount_inr": "500.00",
            "issue_date": "2026-11-10",
            "due_date": "2026-11-24",
        },
    )
    assert fine_resp.status_code == 201
    fine_ref = fine_resp.get_json()["fine"]["referenceNo"]

    pay_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine_ref}/payments",
        headers=admin_headers,
        json={
            "amount_inr": "500.00",
            "payment_method": "upi",
            "manual_reference": "TEST-UPI-PDF-001",
        },
    )
    assert pay_resp.status_code == 201
    rcp_no = pay_resp.get_json()["receipt"]["receiptNumber"]

    # Unauthenticated download blocked
    assert anon_client.get(f"/api/v1/student/receipts/{rcp_no}/pdf").status_code == 401
    assert anon_client.get(f"/api/v1/admin/receipts/{rcp_no}/pdf").status_code == 401

    # Admin PDF download succeeds
    admin_pdf = admin_client.get(f"/api/v1/admin/receipts/{rcp_no}/pdf")
    assert admin_pdf.status_code == 200
    assert admin_pdf.mimetype == "application/pdf"
    assert f'filename="HostelCare-{rcp_no}.pdf"' in admin_pdf.headers.get("Content-Disposition", "")
    assert admin_pdf.data.startswith(b"%PDF-")
    assert admin_pdf.data.rstrip().endswith(b"%%EOF")

    # Owning student PDF download succeeds
    stu1_pdf = stu1_client.get(f"/api/v1/student/receipts/{rcp_no}/pdf")
    assert stu1_pdf.status_code == 200
    assert stu1_pdf.mimetype == "application/pdf"
    assert f'filename="HostelCare-{rcp_no}.pdf"' in stu1_pdf.headers.get("Content-Disposition", "")
    assert stu1_pdf.data.startswith(b"%PDF-")
    assert stu1_pdf.data.rstrip().endswith(b"%%EOF")

    # Other student attempting to download receipt is blocked with 403
    stu2_pdf = stu2_client.get(f"/api/v1/student/receipts/{rcp_no}/pdf")
    assert stu2_pdf.status_code == 403

    # Unknown receipt returns 404
    assert admin_client.get("/api/v1/admin/receipts/RCP-2026-99999/pdf").status_code == 404
    assert stu1_client.get("/api/v1/student/receipts/RCP-2026-99999/pdf").status_code == 404
