"""Phase 3E.5 Razorpay Online Payment Integration (Test Mode Only) PostgreSQL Integration Tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, select, text

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.models.audit import AuditLog
from app.models.fines import Fine, FineHistory
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.payments import Payment, PaymentAttempt, PaymentEvent
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


def _checkout_sig(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _webhook_sig(raw_body: bytes, webhook_secret: str) -> str:
    return hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


@pytest.fixture(scope="module")
def razorpay_app():
    """Create a testing Flask app configured for Razorpay Test Mode and migrated to head."""
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")

    app.config["RAZORPAY_MODE"] = "test"
    app.config["RAZORPAY_KEY_ID"] = "rzp_test_hostelcare_1234"
    app.config["RAZORPAY_KEY_SECRET"] = "rzp_test_secret_abcdef"  # noqa: S105
    app.config["RAZORPAY_WEBHOOK_SECRET"] = "rzp_webhook_secret_xyz"  # noqa: S105

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture(autouse=True)
def _clean_razorpay_tables(razorpay_app):
    """Truncate tables and restore Razorpay test config between tests."""
    clear_console_outbox()
    razorpay_app.config["RAZORPAY_MODE"] = "test"
    razorpay_app.config["RAZORPAY_KEY_ID"] = "rzp_test_hostelcare_1234"
    razorpay_app.config["RAZORPAY_KEY_SECRET"] = "rzp_test_secret_abcdef"  # noqa: S105
    razorpay_app.config["RAZORPAY_WEBHOOK_SECRET"] = "rzp_webhook_secret_xyz"  # noqa: S105

    owner_engine = create_engine(razorpay_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
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
            email="warden.rzp@hostelcare.test",
            full_name="Chief Warden",
            password_hash=hash_password("WardenPass!123"),
            role="admin",
            status="active",
        )
        staff = User(
            email="staff.rzp@hostelcare.test",
            full_name="Maintenance Staff",
            password_hash=hash_password("StaffPass!123"),
            role="staff",
            status="active",
        )
        s1 = User(
            email="student1.rzp@hostelcare.test",
            full_name="Aarav Sharma",
            phone="+919876543210",
            password_hash=hash_password("StudentPass!123"),
            role="student",
            status="active",
        )
        s2 = User(
            email="student2.rzp@hostelcare.test",
            full_name="Priya Verma",
            phone="+919876543211",
            password_hash=hash_password("StudentPass!123"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, staff, s1, s2])
        db.session.flush()

        block = Block(code="A", name="Block A", display_order=1, is_active=True)
        db.session.add(block)
        db.session.flush()

        room = Room(
            block_id=block.id,
            room_number="101",
            floor=1,
            room_type="double",
            capacity=2,
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()

        db.session.add_all(
            [
                StaffProfile(
                    user_id=staff.id, staff_code="STF-001", trade="electrical", shift="day"
                ),
                StudentProfile(user_id=s1.id, roll_number="CS26B001"),
                StudentProfile(user_id=s2.id, roll_number="CS26B002"),
            ]
        )
        db.session.add(
            RoomAllocation(
                student_user_id=s1.id,
                room_id=room.id,
                bed_number=1,
                start_date=date.today() - timedelta(days=30),
                allocated_by=admin.id,
            )
        )
        db.session.commit()
        return {
            "admin_email": admin.email,
            "s1_email": s1.email,
            "s1_roll": "CS26B001",
            "s2_email": s2.email,
            "s2_roll": "CS26B002",
        }


def _issue_fine(
    client, admin_csrf: dict[str, str], student_roll: str, amount: str = "500.00"
) -> dict:
    resp = client.post(
        "/api/v1/admin/fines",
        headers=admin_csrf,
        json={
            "student_id": student_roll,
            "category": "Noise Curfew",
            "description": "Late night noise violation.",
            "amount_inr": amount,
            "issue_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["fine"]


def test_razorpay_test_mode_enforcement_and_unconfigured_state(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "450.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    # 1. Live mode flag must be strictly rejected
    razorpay_app.config["RAZORPAY_MODE"] = "live"
    live_mode_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s1_csrf,
        json={},
    )
    assert live_mode_resp.status_code == 403
    assert live_mode_resp.get_json()["error"]["code"] == "live_mode_forbidden"

    # 2. Live key prefix must be rejected even if mode says test
    razorpay_app.config["RAZORPAY_MODE"] = "test"
    razorpay_app.config["RAZORPAY_KEY_ID"] = "rzp_live_should_fail"
    live_key_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s1_csrf,
        json={},
    )
    assert live_key_resp.status_code == 403
    assert live_key_resp.get_json()["error"]["code"] == "live_mode_forbidden"

    # 3. Missing credentials returns clean 503 and reports disabled status
    razorpay_app.config["RAZORPAY_KEY_ID"] = ""
    razorpay_app.config["RAZORPAY_KEY_SECRET"] = ""
    payments_status = s1_client.get(f"/api/v1/student/fines/{fine['referenceNo']}/payments")
    assert payments_status.status_code == 200
    assert payments_status.get_json()["onlinePaymentEnabled"] is False

    unconfigured_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s1_csrf,
        json={},
    )
    assert unconfigured_resp.status_code == 503
    assert unconfigured_resp.get_json()["error"]["code"] == "online_payment_unavailable"


def test_student_order_verify_settlement_receipt_and_pdf_flow(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "750.50")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")
    s2_client = razorpay_app.test_client()
    s2_csrf = _login_and_csrf(s2_client, actors["s2_email"], "StudentPass!123")

    # Other student forbidden
    forbidden_resp = s2_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s2_csrf,
        json={},
    )
    assert forbidden_resp.status_code == 403

    # Owning student creates Razorpay order -> paise computed server-side from DB (750.50 -> 75050)
    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_RzpTest001", "amount": 75050, "currency": "INR"},
    ) as mock_create_order:
        order_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={"amount": 100},  # ignored client amount
        )
    assert order_resp.status_code == 201, order_resp.get_json()
    mock_create_order.assert_called_once()
    assert mock_create_order.call_args.kwargs["amount_paise"] == 75050
    order_payload = order_resp.get_json()["order"]
    assert order_payload["orderId"] == "order_RzpTest001"
    assert order_payload["amountPaise"] == 75050
    assert order_payload["keyId"] == "rzp_test_hostelcare_1234"
    assert "rzp_test_secret_abcdef" not in json.dumps(order_payload)

    # Re-requesting while attempt still created reuses existing open order idempotently
    reuse_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s1_csrf,
        json={},
    )
    assert reuse_resp.status_code == 200
    assert reuse_resp.get_json()["reused"] is True
    assert reuse_resp.get_json()["order"]["orderId"] == "order_RzpTest001"

    # Bad signature rejected
    bad_sig_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/verify",
        headers=s1_csrf,
        json={
            "razorpay_order_id": "order_RzpTest001",
            "razorpay_payment_id": "pay_RzpTest001",
            "razorpay_signature": "forged_signature",
        },
    )
    assert bad_sig_resp.status_code == 400
    assert bad_sig_resp.get_json()["error"]["code"] == "invalid_signature"

    # Valid signature + authorized-only (not captured) must NOT settle fine
    valid_sig = _checkout_sig("order_RzpTest001", "pay_RzpTest001", "rzp_test_secret_abcdef")
    with patch(
        "app.fines.payments_service.fetch_razorpay_payment",
        return_value={
            "id": "pay_RzpTest001",
            "order_id": "order_RzpTest001",
            "status": "authorized",
            "amount": 75050,
            "currency": "INR",
            "method": "upi",
        },
    ):
        auth_only_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/verify",
            headers=s1_csrf,
            json={
                "razorpay_order_id": "order_RzpTest001",
                "razorpay_payment_id": "pay_RzpTest001",
                "razorpay_signature": valid_sig,
            },
        )
    assert auth_only_resp.status_code == 409
    assert auth_only_resp.get_json()["error"]["code"] == "payment_not_captured"

    # Valid signature + captured payment settles fine atomically
    with patch(
        "app.fines.payments_service.fetch_razorpay_payment",
        return_value={
            "id": "pay_RzpTest001",
            "order_id": "order_RzpTest001",
            "status": "captured",
            "amount": 75050,
            "currency": "INR",
            "method": "upi",
            "created_at": 1763260000,
        },
    ):
        verify_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/verify",
            headers=s1_csrf,
            json={
                "razorpay_order_id": "order_RzpTest001",
                "razorpay_payment_id": "pay_RzpTest001",
                "razorpay_signature": valid_sig,
            },
        )
    assert verify_resp.status_code == 200, verify_resp.get_json()
    body = verify_resp.get_json()
    assert body["fine"]["status"] == "paid"
    assert body["payment"]["channel"] == "razorpay"
    assert body["payment"]["gatewayPaymentId"] == "pay_RzpTest001"
    rcp_no = body["receipt"]["receiptNumber"]
    assert rcp_no.startswith("RCP-")
    assert body["receipt"]["transactionReference"] == "pay_RzpTest001"

    # Idempotent repeat verification succeeds cleanly without duplicate settlement
    repeat_verify = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/verify",
        headers=s1_csrf,
        json={
            "razorpay_order_id": "order_RzpTest001",
            "razorpay_payment_id": "pay_RzpTest001",
            "razorpay_signature": valid_sig,
        },
    )
    assert repeat_verify.status_code == 200
    assert repeat_verify.get_json()["alreadySettled"] is True

    # Student and Admin can both retrieve structured receipt + downloadable PDF
    s_pdf = s1_client.get(f"/api/v1/student/receipts/{rcp_no}/pdf")
    assert s_pdf.status_code == 200
    assert s_pdf.data.startswith(b"%PDF-")

    a_payments = admin_client.get(f"/api/v1/admin/fines/{fine['referenceNo']}/payments")
    assert a_payments.status_code == 200
    a_pay = a_payments.get_json()["payments"][0]
    assert a_pay["channel"] == "razorpay"
    assert a_pay["verificationMethod"] == "api_fetch"
    assert a_pay["gatewayOrderId"] == "order_RzpTest001"
    assert a_pay["gatewayPaymentId"] == "pay_RzpTest001"

    # Manual payment rejected after online settlement
    manual_after_online = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/payments",
        headers=admin_csrf,
        json={"amount_inr": "750.50", "payment_method": "cash", "manual_reference": "CASH-1"},
    )
    assert manual_after_online.status_code == 409

    with razorpay_app.app_context():
        assert db.session.execute(select(Payment)).scalars().all().__len__() == 1
        assert (
            db.session.execute(
                select(AuditLog).where(AuditLog.action == "fine_online_payment_verified")
            ).scalar_one_or_none()
            is not None
        )


def test_disputed_and_dispute_rejected_payment_eligibility_and_failures(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "300.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    # Submit dispute -> payment must be blocked while disputed
    dispute_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/dispute",
        headers=s1_csrf,
        json={"reason": "Incorrect room number listed on notice."},
    )
    assert dispute_resp.status_code == 201
    blocked_resp = s1_client.post(
        f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
        headers=s1_csrf,
        json={},
    )
    assert blocked_resp.status_code == 409

    # Warden rejects dispute -> returns fine to pending -> online checkout permitted
    review_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/dispute/review",
        headers=admin_csrf,
        json={"decision": "rejected", "reason": "Verified against security register."},
    )
    assert review_resp.status_code == 200
    assert review_resp.get_json()["fine"]["status"] == "pending"

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        side_effect=[
            {"id": "order_RzpCancel01", "amount": 30000, "currency": "INR"},
            {"id": "order_RzpRetry02", "amount": 30000, "currency": "INR"},
        ],
    ):
        o1 = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
        assert o1.status_code == 201

        # Student closes checkout -> attempt cancelled, fine stays pending
        fail_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/fail",
            headers=s1_csrf,
            json={"razorpay_order_id": "order_RzpCancel01", "cancelled": True},
        )
        assert fail_resp.status_code == 200
        assert fail_resp.get_json()["attemptStatus"] == "cancelled"

        # Retry spawns fresh Razorpay order cleanly
        o2 = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
        assert o2.status_code == 201
        assert o2.get_json()["order"]["orderId"] == "order_RzpRetry02"


def test_razorpay_webhook_settlement_idempotency_and_out_of_order_safety(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "600.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_Webhook001", "amount": 60000, "currency": "INR"},
    ):
        o_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert o_resp.status_code == 201

    webhook_client = razorpay_app.test_client()
    captured_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_Webhook001",
                    "order_id": "order_Webhook001",
                    "amount": 60000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                    "created_at": 1763261000,
                }
            }
        },
    }
    raw_bytes = json.dumps(captured_payload).encode("utf-8")

    # 1. Invalid webhook signature rejected without settling fine
    bad_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=raw_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": "bad_sig", "X-Razorpay-Event-Id": "evt_1"},
    )
    assert bad_wh.status_code == 400

    # 2. Valid webhook settles fine atomically even without browser session/CSRF
    good_sig = _webhook_sig(raw_bytes, "rzp_webhook_secret_xyz")
    ok_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=raw_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": good_sig, "X-Razorpay-Event-Id": "evt_capture_1"},
    )
    assert ok_wh.status_code == 200, ok_wh.get_json()
    assert ok_wh.get_json()["status"] == "applied"
    rcp_no = ok_wh.get_json()["receiptNumber"]
    assert rcp_no.startswith("RCP-")

    # 3. Replay with same event ID deduplicated cleanly
    dup_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=raw_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": good_sig, "X-Razorpay-Event-Id": "evt_capture_1"},
    )
    assert dup_wh.status_code == 200
    assert dup_wh.get_json()["status"] == "duplicate"

    # 4. order.paid webhook with new event ID deduplicates without extra payment
    order_paid_bytes = json.dumps(
        {
            "event": "order.paid",
            "payload": {
                "order": {"entity": {"id": "order_Webhook001", "amount": 60000}},
                "payment": captured_payload["payload"]["payment"],
            },
        }
    ).encode("utf-8")
    order_paid_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=order_paid_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(order_paid_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_order_paid_2",
        },
    )
    assert order_paid_wh.status_code == 200
    assert order_paid_wh.get_json()["status"] == "duplicate"

    # 5. Late out-of-order payment.failed webhook must NOT downgrade paid fine or succeeded attempt
    failed_bytes = json.dumps(
        {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_FailedDelayed",
                        "order_id": "order_Webhook001",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Stale event",
                    }
                }
            },
        }
    ).encode("utf-8")
    late_fail_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=failed_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(failed_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_late_fail_3",
        },
    )
    assert late_fail_wh.status_code == 200
    assert late_fail_wh.get_json()["status"] == "ignored"

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "paid"
        attempt_row = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_Webhook001")
        ).scalar_one()
        assert attempt_row.status == "succeeded"


def test_offline_vs_online_race_conflict_flags_captured_unapplied(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "800.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    # Student starts online checkout order
    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_Race001", "amount": 80000, "currency": "INR"},
    ):
        order_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert order_resp.status_code == 201

    # Warden records offline cash payment BEFORE Razorpay webhook arrives
    manual_resp = admin_client.post(
        f"/api/v1/admin/fines/{fine['referenceNo']}/payments",
        headers=admin_csrf,
        json={
            "amount_inr": "800.00",
            "payment_method": "cash",
            "manual_reference": "CASH-REG-901",
        },
    )
    assert manual_resp.status_code == 201
    manual_rcp = manual_resp.get_json()["receipt"]["receiptNumber"]

    # Delayed Razorpay captured webhook arrives for the already-settled fine
    wh_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_RaceLate001",
                        "order_id": "order_Race001",
                        "amount": 80000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                    }
                }
            },
        }
    ).encode("utf-8")
    wh_resp = razorpay_app.test_client().post(
        "/api/v1/webhooks/razorpay",
        data=wh_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(wh_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_race_1",
        },
    )
    assert wh_resp.status_code == 200
    assert wh_resp.get_json()["status"] == "needs_review"

    with razorpay_app.app_context():
        payments = db.session.execute(select(Payment)).scalars().all()
        assert len(payments) == 1
        assert payments[0].receipt_number == manual_rcp
        assert payments[0].channel == "manual"

        attempt = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_Race001")
        ).scalar_one()
        assert attempt.status == "captured_unapplied"
        assert attempt.failure_code == "fine_already_paid"

        review_history = db.session.execute(
            select(FineHistory).where(FineHistory.action == "payment_needs_review")
        ).scalar_one_or_none()
        assert review_history is not None

        evt = db.session.execute(
            select(PaymentEvent).where(PaymentEvent.gateway_event_id == "evt_race_1")
        ).scalar_one()
        assert evt.outcome == "needs_review"

        admin_notif = db.session.execute(
            select(Notification).where(Notification.event_type == "payment_needs_review")
        ).scalar_one_or_none()
        assert admin_notif is not None


def test_webhook_payment_failed_lifecycle_and_clean_retry(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "500.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")
    webhook_client = razorpay_app.test_client()

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        side_effect=[
            {"id": "order_FailRetry01", "amount": 50000, "currency": "INR"},
            {"id": "order_FailRetry02", "amount": 50000, "currency": "INR"},
        ],
    ):
        o1_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
        assert o1_resp.status_code == 201

        fail_bytes = json.dumps(
            {
                "event": "payment.failed",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_Fail01",
                            "order_id": "order_FailRetry01",
                            "amount": 50000,
                            "currency": "INR",
                            "status": "failed",
                            "method": "upi",
                            "error_code": "BAD_REQUEST_ERROR",
                            "error_description": "Insufficient funds",
                        }
                    }
                },
            }
        ).encode("utf-8")
        fail_wh = webhook_client.post(
            "/api/v1/webhooks/razorpay",
            data=fail_bytes,
            content_type="application/json",
            headers={
                "X-Razorpay-Signature": _webhook_sig(fail_bytes, "rzp_webhook_secret_xyz"),
                "X-Razorpay-Event-Id": "evt_fail_1",
            },
        )
        assert fail_wh.status_code == 200
        assert fail_wh.get_json() == {"status": "applied", "eventType": "payment.failed"}

        with razorpay_app.app_context():
            fine_row = db.session.execute(
                select(Fine).where(Fine.reference_no == fine["referenceNo"])
            ).scalar_one()
            assert fine_row.status == "pending"
            assert fine_row.paid_at is None
            assert db.session.execute(select(Payment)).scalars().all() == []

            attempt1 = db.session.execute(
                select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_FailRetry01")
            ).scalar_one()
            assert attempt1.status == "failed"
            assert attempt1.gateway_payment_id == "pay_Fail01"
            assert attempt1.failure_code == "BAD_REQUEST_ERROR"
            assert attempt1.failure_reason == "Insufficient funds"

            fail_evt = db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == "evt_fail_1")
            ).scalar_one()
            assert fail_evt.source == "webhook"
            assert fail_evt.event_type == "payment.failed"
            assert fail_evt.signature_valid is True
            assert fail_evt.outcome == "applied"
            assert fail_evt.payment_attempt_id == attempt1.id

        # Second order for the same fine must succeed after failed attempt
        o2_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
        assert o2_resp.status_code == 201
        assert o2_resp.get_json()["order"]["orderId"] == "order_FailRetry02"

    cap_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_Success02",
                        "order_id": "order_FailRetry02",
                        "amount": 50000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "created_at": 1763320000,
                    }
                }
            },
        }
    ).encode("utf-8")
    cap_wh = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=cap_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(cap_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_cap_retry_2",
        },
    )
    assert cap_wh.status_code == 200
    cap_body = cap_wh.get_json()
    assert cap_body["status"] == "applied"
    assert cap_body["receiptNumber"].startswith("RCP-")

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "paid"
        assert fine_row.version == 2

        attempt2 = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_FailRetry02")
        ).scalar_one()
        assert attempt2.status == "succeeded"

        payments = db.session.execute(select(Payment)).scalars().all()
        assert len(payments) == 1
        assert payments[0].receipt_number == cap_body["receiptNumber"]
        assert payments[0].gateway_order_id == "order_FailRetry02"
        assert payments[0].gateway_payment_id == "pay_Success02"
        assert payments[0].verification_method == "webhook"


def test_webhook_capture_on_waived_cancelled_and_disputed_fines(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")
    webhook_client = razorpay_app.test_client()

    cases = [
        ("waived", "order_Waived01", "pay_Waived01", "evt_cap_waived"),
        ("cancelled", "order_Cancel01", "pay_Cancel01", "evt_cap_cancelled"),
        ("disputed", "order_Dispute01", "pay_Dispute01", "evt_cap_disputed"),
    ]

    for target_state, order_id, payment_id, event_id in cases:
        fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "350.00")
        with patch(
            "app.fines.payments_service.create_razorpay_order",
            return_value={"id": order_id, "amount": 35000, "currency": "INR"},
        ):
            o_resp = s1_client.post(
                f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
                headers=s1_csrf,
                json={},
            )
        assert o_resp.status_code == 201

        if target_state == "waived":
            st_resp = admin_client.post(
                f"/api/v1/admin/fines/{fine['referenceNo']}/waive",
                headers=admin_csrf,
                json={"reason": "Approved warden appeal."},
            )
        elif target_state == "cancelled":
            st_resp = admin_client.post(
                f"/api/v1/admin/fines/{fine['referenceNo']}/cancel",
                headers=admin_csrf,
                json={"reason": "Issued to wrong room."},
            )
        else:
            st_resp = s1_client.post(
                f"/api/v1/student/fines/{fine['referenceNo']}/dispute",
                headers=s1_csrf,
                json={"reason": "I was out of station on that date."},
            )
        assert st_resp.status_code in (200, 201), st_resp.get_json()

        cap_bytes = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": payment_id,
                            "order_id": order_id,
                            "amount": 35000,
                            "currency": "INR",
                            "status": "captured",
                            "method": "card",
                        }
                    }
                },
            }
        ).encode("utf-8")
        wh_resp = webhook_client.post(
            "/api/v1/webhooks/razorpay",
            data=cap_bytes,
            content_type="application/json",
            headers={
                "X-Razorpay-Signature": _webhook_sig(cap_bytes, "rzp_webhook_secret_xyz"),
                "X-Razorpay-Event-Id": event_id,
            },
        )
        assert wh_resp.status_code == 200
        assert wh_resp.get_json()["status"] == "needs_review"
        assert wh_resp.get_json()["receiptNumber"] is None

        with razorpay_app.app_context():
            fine_row = db.session.execute(
                select(Fine).where(Fine.reference_no == fine["referenceNo"])
            ).scalar_one()
            assert fine_row.status == target_state
            assert fine_row.paid_at is None

            attempt = db.session.execute(
                select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == order_id)
            ).scalar_one()
            assert attempt.status == "captured_unapplied"
            assert attempt.failure_code == f"fine_status_{target_state}"
            assert attempt.gateway_payment_id == payment_id
            assert attempt.verified_at is not None

            assert (
                db.session.execute(
                    select(Payment).where(Payment.fine_id == fine_row.id)
                ).scalar_one_or_none()
                is None
            )
            assert (
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fine_row.id,
                        FineHistory.action == "payment_needs_review",
                        FineHistory.payment_attempt_id == attempt.id,
                    )
                ).scalar_one_or_none()
                is not None
            )
            assert (
                db.session.execute(
                    select(Notification).where(
                        Notification.event_type == "payment_needs_review",
                        Notification.entity_ref == fine["referenceNo"],
                    )
                ).scalar_one_or_none()
                is not None
            )
            evt = db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == event_id)
            ).scalar_one()
            assert evt.outcome == "needs_review"
            assert evt.signature_valid is True
            assert (
                db.session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "fine_payment_needs_review",
                        AuditLog.target_id == fine["referenceNo"],
                    )
                ).scalar_one_or_none()
                is not None
            )


def test_webhook_amount_and_currency_mismatch_flags_unapplied(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")
    webhook_client = razorpay_app.test_client()

    mismatch_cases = [
        ("order_AmtMis01", "pay_AmtMis01", "evt_amt_mis", 40000, "INR"),
        ("order_CurMis01", "pay_CurMis01", "evt_cur_mis", 50000, "USD"),
    ]

    for order_id, payment_id, event_id, bad_amount, bad_currency in mismatch_cases:
        fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "500.00")
        with patch(
            "app.fines.payments_service.create_razorpay_order",
            return_value={"id": order_id, "amount": 50000, "currency": "INR"},
        ):
            o_resp = s1_client.post(
                f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
                headers=s1_csrf,
                json={},
            )
        assert o_resp.status_code == 201

        wh_bytes = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": payment_id,
                            "order_id": order_id,
                            "amount": bad_amount,
                            "currency": bad_currency,
                            "status": "captured",
                            "method": "upi",
                        }
                    }
                },
            }
        ).encode("utf-8")
        wh_resp = webhook_client.post(
            "/api/v1/webhooks/razorpay",
            data=wh_bytes,
            content_type="application/json",
            headers={
                "X-Razorpay-Signature": _webhook_sig(wh_bytes, "rzp_webhook_secret_xyz"),
                "X-Razorpay-Event-Id": event_id,
            },
        )
        assert wh_resp.status_code == 200
        assert wh_resp.get_json()["status"] == "needs_review"
        assert wh_resp.get_json()["receiptNumber"] is None

        with razorpay_app.app_context():
            fine_row = db.session.execute(
                select(Fine).where(Fine.reference_no == fine["referenceNo"])
            ).scalar_one()
            assert fine_row.status == "pending"
            assert fine_row.paid_at is None
            assert fine_row.version == 1

            attempt = db.session.execute(
                select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == order_id)
            ).scalar_one()
            assert attempt.status == "captured_unapplied"
            assert attempt.failure_code == "amount_mismatch"
            assert attempt.verified_at is not None

            assert (
                db.session.execute(
                    select(Payment).where(Payment.fine_id == fine_row.id)
                ).scalar_one_or_none()
                is None
            )
            assert (
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fine_row.id,
                        FineHistory.action == "payment_needs_review",
                    )
                ).scalar_one_or_none()
                is not None
            )
            assert (
                db.session.execute(
                    select(Notification).where(
                        Notification.event_type == "payment_needs_review",
                        Notification.entity_ref == fine["referenceNo"],
                    )
                ).scalar_one_or_none()
                is not None
            )
            evt = db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == event_id)
            ).scalar_one()
            assert evt.outcome == "needs_review"
            assert (
                db.session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "fine_payment_needs_review",
                        AuditLog.target_id == fine["referenceNo"],
                    )
                ).scalar_one_or_none()
                is not None
            )


def test_webhook_and_browser_callback_interleaving_and_dedup_assertions(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")
    webhook_client = razorpay_app.test_client()

    # Sequence A: Webhook first -> Browser verification callback second
    fine_a = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "400.00")
    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_SeqA01", "amount": 40000, "currency": "INR"},
    ):
        oa_resp = s1_client.post(
            f"/api/v1/student/fines/{fine_a['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert oa_resp.status_code == 201

    wh_a_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_SeqA01",
                        "order_id": "order_SeqA01",
                        "amount": 40000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "created_at": 1763321000,
                    }
                }
            },
        }
    ).encode("utf-8")
    wh_a = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=wh_a_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(wh_a_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_seq_a_1",
        },
    )
    assert wh_a.status_code == 200
    assert wh_a.get_json()["status"] == "applied"
    rcp_a = wh_a.get_json()["receiptNumber"]

    cb_a = s1_client.post(
        f"/api/v1/student/fines/{fine_a['referenceNo']}/payments/razorpay/verify",
        headers=s1_csrf,
        json={
            "razorpay_order_id": "order_SeqA01",
            "razorpay_payment_id": "pay_SeqA01",
            "razorpay_signature": _checkout_sig(
                "order_SeqA01", "pay_SeqA01", "rzp_test_secret_abcdef"
            ),
        },
    )
    assert cb_a.status_code == 200
    assert cb_a.get_json()["alreadySettled"] is True
    assert cb_a.get_json()["receipt"]["receiptNumber"] == rcp_a

    with razorpay_app.app_context():
        fa_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine_a["referenceNo"])
        ).scalar_one()
        assert fa_row.status == "paid"
        assert fa_row.version == 2
        att_a = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_SeqA01")
        ).scalar_one()
        assert att_a.status == "succeeded"

        pays_a = (
            db.session.execute(select(Payment).where(Payment.fine_id == fa_row.id)).scalars().all()
        )
        assert len(pays_a) == 1
        assert pays_a[0].receipt_number == rcp_a
        assert (
            len(
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fa_row.id,
                        FineHistory.action == "payment_verified",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(Notification).where(
                        Notification.entity_ref == fine_a["referenceNo"],
                        Notification.event_type == "fine_payment_verified",
                        Notification.recipient_user_id == fa_row.student_user_id,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "fine_online_payment_verified",
                        AuditLog.target_id == rcp_a,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        evts_a = (
            db.session.execute(
                select(PaymentEvent)
                .where(PaymentEvent.payment_attempt_id == att_a.id)
                .order_by(PaymentEvent.id.asc())
            )
            .scalars()
            .all()
        )
        assert [(e.source, e.event_type, e.outcome) for e in evts_a] == [
            ("system", "order.created", "applied"),
            ("webhook", "payment.captured", "applied"),
            ("client_callback", "payment.verify", "duplicate"),
        ]

    # Sequence B: Browser callback first -> payment.captured -> order.paid
    fine_b = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "450.00")
    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_SeqB01", "amount": 45000, "currency": "INR"},
    ):
        ob_resp = s1_client.post(
            f"/api/v1/student/fines/{fine_b['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert ob_resp.status_code == 201

    with patch(
        "app.fines.payments_service.fetch_razorpay_payment",
        return_value={
            "id": "pay_SeqB01",
            "order_id": "order_SeqB01",
            "status": "captured",
            "amount": 45000,
            "currency": "INR",
            "method": "netbanking",
            "created_at": 1763322000,
        },
    ):
        cb_b = s1_client.post(
            f"/api/v1/student/fines/{fine_b['referenceNo']}/payments/razorpay/verify",
            headers=s1_csrf,
            json={
                "razorpay_order_id": "order_SeqB01",
                "razorpay_payment_id": "pay_SeqB01",
                "razorpay_signature": _checkout_sig(
                    "order_SeqB01", "pay_SeqB01", "rzp_test_secret_abcdef"
                ),
            },
        )
    assert cb_b.status_code == 200
    assert cb_b.get_json()["alreadySettled"] is False
    rcp_b = cb_b.get_json()["receipt"]["receiptNumber"]

    wh_b_cap_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_SeqB01",
                        "order_id": "order_SeqB01",
                        "amount": 45000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "netbanking",
                    }
                }
            },
        }
    ).encode("utf-8")
    wh_b_cap = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=wh_b_cap_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(wh_b_cap_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_seq_b_cap",
        },
    )
    assert wh_b_cap.status_code == 200
    assert wh_b_cap.get_json()["status"] == "duplicate"

    wh_b_ord_bytes = json.dumps(
        {
            "event": "order.paid",
            "payload": {
                "order": {"entity": {"id": "order_SeqB01", "amount": 45000}},
                "payment": {
                    "entity": {
                        "id": "pay_SeqB01",
                        "order_id": "order_SeqB01",
                        "amount": 45000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "netbanking",
                    }
                },
            },
        }
    ).encode("utf-8")
    wh_b_ord = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=wh_b_ord_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(wh_b_ord_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_seq_b_ord",
        },
    )
    assert wh_b_ord.status_code == 200
    assert wh_b_ord.get_json()["status"] == "duplicate"

    with razorpay_app.app_context():
        fb_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine_b["referenceNo"])
        ).scalar_one()
        assert fb_row.status == "paid"
        assert fb_row.version == 2
        att_b = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_SeqB01")
        ).scalar_one()
        assert att_b.status == "succeeded"

        pays_b = (
            db.session.execute(select(Payment).where(Payment.fine_id == fb_row.id)).scalars().all()
        )
        assert len(pays_b) == 1
        assert pays_b[0].receipt_number == rcp_b
        assert (
            len(
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fb_row.id,
                        FineHistory.action == "payment_verified",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(Notification).where(
                        Notification.entity_ref == fine_b["referenceNo"],
                        Notification.event_type == "fine_payment_verified",
                        Notification.recipient_user_id == fb_row.student_user_id,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "fine_online_payment_verified",
                        AuditLog.target_id == rcp_b,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        evts_b = (
            db.session.execute(
                select(PaymentEvent)
                .where(PaymentEvent.payment_attempt_id == att_b.id)
                .order_by(PaymentEvent.id.asc())
            )
            .scalars()
            .all()
        )
        assert [(e.source, e.event_type, e.outcome) for e in evts_b] == [
            ("system", "order.created", "applied"),
            ("server_verify", "payment.verified", "applied"),
            ("webhook", "payment.captured", "duplicate"),
            ("webhook", "order.paid", "duplicate"),
        ]


def test_webhook_security_edge_cases_and_payload_anomalies(razorpay_app):
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "250.00")
    webhook_client = razorpay_app.test_client()

    # 1. Invalid webhook signature -> 400 + rejected PaymentEvent logged
    bad_sig_bytes = json.dumps({"event": "payment.captured"}).encode("utf-8")
    bad_sig_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=bad_sig_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": "forged_sig", "X-Razorpay-Event-Id": "evt_bad_sig"},
    )
    assert bad_sig_resp.status_code == 400
    assert bad_sig_resp.get_json()["error"]["code"] == "invalid_signature"

    # 2. Malformed JSON payload with valid signature -> 400 validation_error
    malformed_bytes = b"{invalid-json"
    malformed_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=malformed_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": _webhook_sig(malformed_bytes, "rzp_webhook_secret_xyz")},
    )
    assert malformed_resp.status_code == 400
    assert malformed_resp.get_json()["error"]["code"] == "validation_error"

    # 3a. Empty payload -> 400 invalid_signature (no raw_body)
    empty_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=b"",
        content_type="application/json",
        headers={"X-Razorpay-Signature": "any"},
    )
    assert empty_resp.status_code == 400
    assert empty_resp.get_json()["error"]["code"] == "invalid_signature"

    # 3b. Non-object JSON payload -> 400 validation_error
    list_bytes = b"[]"
    list_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=list_bytes,
        content_type="application/json",
        headers={"X-Razorpay-Signature": _webhook_sig(list_bytes, "rzp_webhook_secret_xyz")},
    )
    assert list_resp.status_code == 400
    assert list_resp.get_json()["error"]["code"] == "validation_error"

    # 3c. Incomplete JSON object `{}` -> 200 ignored
    empty_obj_bytes = b"{}"
    empty_obj_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=empty_obj_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(empty_obj_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_incomplete_obj",
        },
    )
    assert empty_obj_resp.status_code == 200
    assert empty_obj_resp.get_json() == {"status": "ignored", "eventType": "unknown"}

    # 4. Unknown gateway order ID -> 200 ignored
    unknown_ord_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_Unknown999",
                        "order_id": "order_Unknown999",
                        "amount": 25000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }
    ).encode("utf-8")
    unknown_ord_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=unknown_ord_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(unknown_ord_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_unknown_ord",
        },
    )
    assert unknown_ord_resp.status_code == 200
    assert unknown_ord_resp.get_json() == {"status": "ignored", "eventType": "payment.captured"}

    # 5. Unknown webhook event type -> 200 ignored
    unknown_type_bytes = json.dumps({"event": "subscription.charged", "payload": {}}).encode(
        "utf-8"
    )
    unknown_type_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=unknown_type_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(unknown_type_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_unknown_type",
        },
    )
    assert unknown_type_resp.status_code == 200
    assert unknown_type_resp.get_json() == {
        "status": "ignored",
        "eventType": "subscription.charged",
    }

    # 6. Non-captured payment event (`payment.authorized`) -> 200 ignored
    auth_only_bytes = json.dumps(
        {
            "event": "payment.authorized",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_AuthOnly01",
                        "order_id": "order_AuthOnly01",
                        "amount": 25000,
                        "currency": "INR",
                        "status": "authorized",
                    }
                }
            },
        }
    ).encode("utf-8")
    auth_only_resp = webhook_client.post(
        "/api/v1/webhooks/razorpay",
        data=auth_only_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": _webhook_sig(auth_only_bytes, "rzp_webhook_secret_xyz"),
            "X-Razorpay-Event-Id": "evt_auth_only",
        },
    )
    assert auth_only_resp.status_code == 200
    assert auth_only_resp.get_json() == {"status": "ignored", "eventType": "payment.authorized"}

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "pending"
        assert db.session.execute(select(Payment)).scalars().all() == []

        rejected_evts = (
            db.session.execute(
                select(PaymentEvent).where(PaymentEvent.event_type == "webhook.invalid_signature")
            )
            .scalars()
            .all()
        )
        assert len(rejected_evts) == 2
        for rejected_evt in rejected_evts:
            assert rejected_evt.signature_valid is False
            assert rejected_evt.outcome == "rejected"
            assert rejected_evt.gateway_event_id is None

        for eid, expected_type in (
            ("evt_incomplete_obj", "unknown"),
            ("evt_unknown_ord", "payment.captured"),
            ("evt_unknown_type", "subscription.charged"),
            ("evt_auth_only", "payment.authorized"),
        ):
            evt = db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == eid)
            ).scalar_one()
            assert evt.source == "webhook"
            assert evt.event_type == expected_type
            assert evt.signature_valid is True
            assert evt.outcome == "ignored"


def test_concurrent_duplicate_payment_captured_webhooks_settle_once(razorpay_app):
    """Two concurrent payment.captured deliveries serialize via FOR UPDATE and settle once."""
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "550.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_Conc001", "amount": 55000, "currency": "INR"},
    ):
        order_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert order_resp.status_code == 201

    raw_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_Conc001",
                        "order_id": "order_Conc001",
                        "amount": 55000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "created_at": 1763323000,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = _webhook_sig(raw_bytes, "rzp_webhook_secret_xyz")
    barrier = Barrier(2, timeout=5)

    def _deliver_webhook(event_id: str) -> tuple[int, dict]:
        client = razorpay_app.test_client()
        barrier.wait()
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            data=raw_bytes,
            content_type="application/json",
            headers={
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": event_id,
            },
        )
        return resp.status_code, resp.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut1 = pool.submit(_deliver_webhook, "evt_conc_1")
        fut2 = pool.submit(_deliver_webhook, "evt_conc_2")
        res1 = fut1.result()
        res2 = fut2.result()

    assert res1[0] == 200, res1
    assert res2[0] == 200, res2
    statuses = sorted([res1[1]["status"], res2[1]["status"]])
    assert statuses == ["applied", "duplicate"]

    applied_body = res1[1] if res1[1]["status"] == "applied" else res2[1]
    rcp_no = applied_body["receiptNumber"]
    assert rcp_no and rcp_no.startswith("RCP-")

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "paid"
        assert fine_row.version == 2
        assert fine_row.paid_at is not None

        attempt_row = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_Conc001")
        ).scalar_one()
        assert attempt_row.status == "succeeded"
        assert attempt_row.gateway_payment_id == "pay_Conc001"

        payments = (
            db.session.execute(select(Payment).where(Payment.fine_id == fine_row.id))
            .scalars()
            .all()
        )
        assert len(payments) == 1
        assert payments[0].receipt_number == rcp_no
        assert payments[0].gateway_payment_id == "pay_Conc001"

        verified_history = (
            db.session.execute(
                select(FineHistory).where(
                    FineHistory.fine_id == fine_row.id,
                    FineHistory.action == "payment_verified",
                )
            )
            .scalars()
            .all()
        )
        assert len(verified_history) == 1

        student_notifs = (
            db.session.execute(
                select(Notification).where(
                    Notification.entity_ref == fine["referenceNo"],
                    Notification.event_type == "fine_payment_verified",
                    Notification.recipient_user_id == fine_row.student_user_id,
                )
            )
            .scalars()
            .all()
        )
        assert len(student_notifs) == 1

        audits = (
            db.session.execute(
                select(AuditLog).where(
                    AuditLog.action == "fine_online_payment_verified",
                    AuditLog.target_id == rcp_no,
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 1

        wh_events = (
            db.session.execute(
                select(PaymentEvent).where(
                    PaymentEvent.payment_attempt_id == attempt_row.id,
                    PaymentEvent.source == "webhook",
                )
            )
            .scalars()
            .all()
        )
        assert len(wh_events) == 2
        assert sorted(e.outcome for e in wh_events) == ["applied", "duplicate"]


def test_webhook_settlement_exception_rolls_back_partial_changes(razorpay_app, monkeypatch):
    """Mid-transaction failure during webhook settlement rolls back all partial DB changes."""
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "650.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_Rollback01", "amount": 65000, "currency": "INR"},
    ):
        order_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert order_resp.status_code == 201

    raw_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_Rollback01",
                        "order_id": "order_Rollback01",
                        "amount": 65000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "card",
                        "created_at": 1763324000,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = _webhook_sig(raw_bytes, "rzp_webhook_secret_xyz")

    import app.fines.payments_service as pay_service

    def _boom(**kwargs):
        raise RuntimeError("Simulated mid-settlement audit failure")

    monkeypatch.setattr(pay_service, "record_audit_event", _boom)
    err_resp = razorpay_app.test_client().post(
        "/api/v1/webhooks/razorpay",
        data=raw_bytes,
        content_type="application/json",
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": "evt_rollback_1",
        },
    )
    assert err_resp.status_code == 500
    monkeypatch.undo()

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "pending"
        assert fine_row.version == 1
        assert fine_row.paid_at is None

        attempt_row = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_Rollback01")
        ).scalar_one()
        assert attempt_row.status == "created"
        assert attempt_row.gateway_payment_id is None
        assert attempt_row.verified_at is None

        assert db.session.execute(select(Payment)).scalars().all() == []
        assert (
            db.session.execute(
                select(FineHistory).where(
                    FineHistory.fine_id == fine_row.id,
                    FineHistory.action == "payment_verified",
                )
            )
            .scalars()
            .all()
            == []
        )
        assert (
            db.session.execute(
                select(Notification).where(
                    Notification.entity_ref == fine["referenceNo"],
                    Notification.event_type == "fine_payment_verified",
                )
            )
            .scalars()
            .all()
            == []
        )
        assert (
            db.session.execute(
                select(AuditLog).where(AuditLog.action == "fine_online_payment_verified")
            )
            .scalars()
            .all()
            == []
        )
        assert (
            db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == "evt_rollback_1")
            ).scalar_one_or_none()
            is None
        )


def test_concurrent_same_webhook_event_id_returns_duplicate_without_500(razorpay_app, monkeypatch):
    """Concurrent requests with identical X-Razorpay-Event-Id recover cleanly without HTTP 500."""
    actors = _seed_actors(razorpay_app)
    admin_client = razorpay_app.test_client()
    admin_csrf = _login_and_csrf(admin_client, actors["admin_email"], "WardenPass!123")
    fine = _issue_fine(admin_client, admin_csrf, actors["s1_roll"], "700.00")

    s1_client = razorpay_app.test_client()
    s1_csrf = _login_and_csrf(s1_client, actors["s1_email"], "StudentPass!123")

    with patch(
        "app.fines.payments_service.create_razorpay_order",
        return_value={"id": "order_SameEvt01", "amount": 70000, "currency": "INR"},
    ):
        order_resp = s1_client.post(
            f"/api/v1/student/fines/{fine['referenceNo']}/payments/razorpay/order",
            headers=s1_csrf,
            json={},
        )
    assert order_resp.status_code == 201

    raw_bytes = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_SameEvt01",
                        "order_id": "order_SameEvt01",
                        "amount": 70000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "created_at": 1763325000,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = _webhook_sig(raw_bytes, "rzp_webhook_secret_xyz")
    same_event_id = "evt_same_race_001"

    import app.fines.payments_service as pay_service

    orig_select = pay_service.select
    post_precheck_barrier = Barrier(2, timeout=5)

    def _sync_before_attempt_lock(*entities, **kwargs):
        # Wait after both threads pass the initial gateway_event_id pre-check so both
        # serialize on PaymentAttempt FOR UPDATE and hit uq_payment_events_gateway_event.
        if len(entities) == 1 and entities[0] is PaymentAttempt:
            post_precheck_barrier.wait()
        return orig_select(*entities, **kwargs)

    monkeypatch.setattr(pay_service, "select", _sync_before_attempt_lock)

    def _deliver_same_event() -> tuple[int, dict]:
        client = razorpay_app.test_client()
        resp = client.post(
            "/api/v1/webhooks/razorpay",
            data=raw_bytes,
            content_type="application/json",
            headers={
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": same_event_id,
            },
        )
        return resp.status_code, resp.get_json()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut1 = pool.submit(_deliver_same_event)
            fut2 = pool.submit(_deliver_same_event)
            res1 = fut1.result()
            res2 = fut2.result()
    finally:
        monkeypatch.undo()

    assert res1[0] == 200, res1
    assert res2[0] == 200, res2
    assert sorted([res1[1]["status"], res2[1]["status"]]) == ["applied", "duplicate"]

    applied_body = res1[1] if res1[1]["status"] == "applied" else res2[1]
    dup_body = res2[1] if res1[1]["status"] == "applied" else res1[1]
    rcp_no = applied_body["receiptNumber"]
    assert rcp_no and rcp_no.startswith("RCP-")
    assert dup_body == {"status": "duplicate", "eventId": same_event_id}

    with razorpay_app.app_context():
        fine_row = db.session.execute(
            select(Fine).where(Fine.reference_no == fine["referenceNo"])
        ).scalar_one()
        assert fine_row.status == "paid"
        assert fine_row.version == 2
        assert fine_row.paid_at is not None

        attempt_row = db.session.execute(
            select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == "order_SameEvt01")
        ).scalar_one()
        assert attempt_row.status == "succeeded"
        assert attempt_row.gateway_payment_id == "pay_SameEvt01"

        matching_evts = (
            db.session.execute(
                select(PaymentEvent).where(PaymentEvent.gateway_event_id == same_event_id)
            )
            .scalars()
            .all()
        )
        assert len(matching_evts) == 1
        assert matching_evts[0].outcome == "applied"
        assert matching_evts[0].signature_valid is True

        payments = (
            db.session.execute(select(Payment).where(Payment.fine_id == fine_row.id))
            .scalars()
            .all()
        )
        assert len(payments) == 1
        assert payments[0].receipt_number == rcp_no
        assert payments[0].gateway_payment_id == "pay_SameEvt01"

        assert (
            len(
                db.session.execute(
                    select(FineHistory).where(
                        FineHistory.fine_id == fine_row.id,
                        FineHistory.action == "payment_verified",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(Notification).where(
                        Notification.entity_ref == fine["referenceNo"],
                        Notification.event_type == "fine_payment_verified",
                        Notification.recipient_user_id == fine_row.student_user_id,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db.session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "fine_online_payment_verified",
                        AuditLog.target_id == rcp_no,
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
