"""Phase 3C integration tests: Authentication, Identity Lifecycle, Staff Provisioning,
Password Reset, Session/CSRF Security, Audit Logging, Rate Limiting, and RBAC Matrix.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import select, text

from app import create_app
from app.auth.security import UNUSABLE_PASSWORD_MARKER, hash_password
from app.core.mailer import clear_console_outbox, get_console_outbox, redact_reset_tokens
from app.extensions import db
from app.models.audit import AuditLog
from app.models.identity import PasswordResetToken, StaffProfile, StudentProfile, User

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")
_TOKEN_EXTRACT_RE = re.compile(r"/reset-password/([A-Za-z0-9_\-]+)")


@pytest.fixture(scope="module")
def auth_app():
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
def _clean_auth_tables(auth_app):
    """Clean test data between tests using `hostelcare_owner`."""
    from sqlalchemy import create_engine

    clear_console_outbox()
    owner_engine = create_engine(auth_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
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


def _create_active_admin(
    app, email: str = "warden@hostelcare.test", password: str = "AdminPass123!"
) -> str:
    """Helper to seed an active admin user and return their `public_id` string."""
    with app.app_context():
        admin = User(
            email=email,
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password(password),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.commit()
        return str(admin.public_id)


def _login(client, email: str, password: str, role: str | None = None):
    """Helper to call `POST /api/v1/auth/login`."""
    payload = {"email": email, "password": password}
    if role is not None:
        payload["role"] = role
    return client.post(
        "/api/v1/auth/login",
        json=payload,
    )


@pytest.mark.db
def test_student_registration_success_and_duplicate_rejection(auth_app):
    """Verify student registration, Argon2id hashing, escalation prevention, and duplicates."""
    client = auth_app.test_client()

    # 1. Privilege escalation attempt (trying to register as admin or active) is rejected
    esc_resp = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Escalation Attacker",
            "email": "attacker@hostelcare.test",
            "rollNumber": "2026CS999",
            "phone": "+91 9876543210",
            "password": "Password123!",
            "confirmPassword": "Password123!",
            "role": "admin",
        },
    )
    assert esc_resp.status_code == 403
    assert esc_resp.get_json()["error"]["code"] == "forbidden_field"

    # 2. Valid student self-registration succeeds -> role='student', status='pending'
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Aarav Sharma",
            "email": "  Aarav.Sharma@HostelCare.test ",
            "rollNumber": " 2026csb1042 ",
            "phone": "+91 98234 56789",
            "password": "StudentPass123!",
            "confirmPassword": "StudentPass123!",
        },
    )
    assert reg_resp.status_code == 201
    payload = reg_resp.get_json()
    assert payload["status"] == "pending_approval"
    user_data = payload["user"]
    assert user_data["email"] == "aarav.sharma@hostelcare.test"
    assert user_data["rollNumber"] == "2026CSB1042"
    assert user_data["role"] == "student"
    assert user_data["status"] == "pending"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # Verify DB state: Argon2id hash stored, never plaintext
    with auth_app.app_context():
        user = db.session.execute(
            select(User).where(User.email == "aarav.sharma@hostelcare.test")
        ).scalar_one()
        assert user.password_hash.startswith("$argon2id$")
        assert "StudentPass123!" not in user.password_hash
        assert user.role == "student"
        assert user.status == "pending"
        assert user.student_profile is not None
        assert user.student_profile.roll_number == "2026CSB1042"

    # 3. Duplicate email registration is rejected neutrally without leaking which field matched
    dup_email_resp = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Another Student",
            "email": "aarav.sharma@hostelcare.test",
            "rollNumber": "2026CSB9999",
            "phone": "+91 90000 11111",
            "password": "StudentPass123!",
            "confirmPassword": "StudentPass123!",
        },
    )
    assert dup_email_resp.status_code == 409
    err_email = dup_email_resp.get_json()["error"]
    assert err_email["code"] == "registration_conflict"

    # 4. Duplicate roll number registration returns the exact same neutral 409 response
    dup_roll_resp = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Another Student",
            "email": "unique.student@hostelcare.test",
            "rollNumber": "2026CSB1042",
            "phone": "+91 90000 11111",
            "password": "StudentPass123!",
            "confirmPassword": "StudentPass123!",
        },
    )
    assert dup_roll_resp.status_code == 409
    err_roll = dup_roll_resp.get_json()["error"]
    assert err_roll == err_email


@pytest.mark.db
def test_student_lifecycle_pending_login_blocked_approve_reject_reactivate(auth_app):
    """Verify pending login block, admin approve, reject, and reactivation on same row."""
    _create_active_admin(auth_app)
    student_client = auth_app.test_client()
    admin_client = auth_app.test_client()

    # Register student
    reg_resp = student_client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Vikram Malhotra",
            "email": "vikram@hostelcare.test",
            "rollNumber": "2026MEB1015",
            "phone": "+91 99887 76655",
            "password": "VikramPass123!",
            "confirmPassword": "VikramPass123!",
        },
    )
    assert reg_resp.status_code == 201
    student_pub_id = reg_resp.get_json()["user"]["id"]

    # 1. Pending student cannot log in (403 account_pending) and gets no session
    login_pending = _login(student_client, "vikram@hostelcare.test", "VikramPass123!")
    assert login_pending.status_code == 403
    assert login_pending.get_json()["error"]["code"] == "account_pending"
    assert student_client.get("/api/v1/auth/me").status_code == 401
    assert student_client.get("/api/v1/student/profile").status_code == 401

    # 2. Admin logs in and lists pending students
    admin_login = _login(admin_client, "warden@hostelcare.test", "AdminPass123!")
    assert admin_login.status_code == 200
    admin_csrf = admin_login.get_json()["csrf_token"]

    pending_list = admin_client.get("/api/v1/admin/students/pending")
    assert pending_list.status_code == 200
    assert len(pending_list.get_json()["students"]) == 1
    assert pending_list.get_json()["students"][0]["id"] == student_pub_id

    # 3. Rejecting without a reason fails with 400
    bad_reject = admin_client.post(
        f"/api/v1/admin/students/{student_pub_id}/reject",
        json={"reason": "   "},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert bad_reject.status_code == 400

    # 4. Admin rejects student with mandatory reason (`pending -> rejected`)
    reject_resp = admin_client.post(
        f"/api/v1/admin/students/{student_pub_id}/reject",
        json={"reason": "ID card scan was illegible; please show original at warden desk."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.get_json()["student"]["status"] == "rejected"

    # Rejected student cannot log in (`403 account_rejected`)
    login_rejected = _login(student_client, "vikram@hostelcare.test", "VikramPass123!")
    assert login_rejected.status_code == 403
    assert login_rejected.get_json()["error"]["code"] == "account_rejected"

    # 5. Admin reactivates rejected student (`rejected -> pending`) on the SAME account row
    reactivate_resp = admin_client.post(
        f"/api/v1/admin/students/{student_pub_id}/reactivate",
        json={"reason": "Original college ID verified in person at Warden Office."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.get_json()["student"]["status"] == "pending"
    assert reactivate_resp.get_json()["student"]["id"] == student_pub_id

    # 6. Admin approves the reactivated student (`pending -> active`)
    approve_resp = admin_client.post(
        f"/api/v1/admin/students/{student_pub_id}/approve",
        json={"note": "Approved for academic session 2026-27."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.get_json()["student"]["status"] == "active"

    # 7. Active student can now log in and access `/api/v1/auth/me` and `/api/v1/student/profile`
    login_active = _login(student_client, "vikram@hostelcare.test", "VikramPass123!")
    assert login_active.status_code == 200
    me_resp = student_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.get_json()["user"]["id"] == student_pub_id
    assert me_resp.get_json()["user"]["status"] == "active"
    assert student_client.get("/api/v1/student/profile").status_code == 200


@pytest.mark.db
def test_staff_provisioning_unusable_password_marker_setup_and_deactivation(auth_app):
    """Verify staff creation with `'!'` marker, login block for `'!'`, setup, and deactivation."""
    _create_active_admin(auth_app)
    admin_client = auth_app.test_client()
    staff_client = auth_app.test_client()

    admin_csrf = _login(admin_client, "warden@hostelcare.test", "AdminPass123!").get_json()[
        "csrf_token"
    ]

    # 1. Admin creates staff account
    create_resp = admin_client.post(
        "/api/v1/admin/staff",
        json={
            "fullName": "Ramesh Babu",
            "email": "ramesh.electrician@hostelcare.test",
            "phone": "+91 94421 88901",
            "staffCode": "STF-0001",
            "trade": "Electrician",
            "shift": "Morning (08:00 AM - 04:30 PM)",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create_resp.status_code == 201
    staff_data = create_resp.get_json()["staff"]
    staff_pub_id = staff_data["id"]
    assert staff_data["role"] == "staff"
    assert staff_data["staffCode"] == "STF-0001"
    assert staff_data["trade"] == "Electrician"
    # API never returns password_hash or reset token
    assert "password_hash" not in staff_data
    assert "token" not in str(create_resp.get_json())

    # 2. Verify DB has password_hash == '!' and a hashed reset token
    with auth_app.app_context():
        staff_user = db.session.execute(
            select(User).where(User.email == "ramesh.electrician@hostelcare.test")
        ).scalar_one()
        assert staff_user.password_hash == UNUSABLE_PASSWORD_MARKER

    # 3. Attempting to log in with "!" before password setup is unconditionally rejected
    bang_login = _login(staff_client, "ramesh.electrician@hostelcare.test", "!")
    assert bang_login.status_code == 401
    assert bang_login.get_json()["error"]["code"] == "invalid_credentials"

    # 4. Extract raw setup token from console mailer outbox and verify only SHA-256 hash is in DB
    outbox = get_console_outbox()
    assert len(outbox) == 1
    assert outbox[0].to == "ramesh.electrician@hostelcare.test"
    match = _TOKEN_EXTRACT_RE.search(outbox[0].body)
    assert match is not None
    raw_setup_token = match.group(1)
    expected_sha256 = hashlib.sha256(raw_setup_token.encode("utf-8")).hexdigest()

    with auth_app.app_context():
        prt = db.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == staff_user.id)
        ).scalar_one()
        assert prt.token_hash == expected_sha256
        assert prt.token_hash != raw_setup_token

    # 5. Staff sets password using the single-use setup token
    reset_resp = staff_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_setup_token,
            "password": "RameshStrongPass1!",
            "confirmPassword": "RameshStrongPass1!",
        },
    )
    assert reset_resp.status_code == 200

    # 6. Staff can now log in and update own phone/shift, but cannot alter trade or role
    staff_login = _login(staff_client, "ramesh.electrician@hostelcare.test", "RameshStrongPass1!")
    assert staff_login.status_code == 200
    staff_csrf = staff_login.get_json()["csrf_token"]

    patch_ok = staff_client.patch(
        "/api/v1/staff/profile",
        json={"phone": "+91 94421 99999", "shift": "Evening (01:00 PM - 09:30 PM)"},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert patch_ok.status_code == 200
    assert patch_ok.get_json()["user"]["phone"] == "+91 94421 99999"

    patch_forbidden = staff_client.patch(
        "/api/v1/staff/profile",
        json={"trade": "Chief Warden"},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert patch_forbidden.status_code == 403

    # 7. Admin deactivates staff account -> open staff session is immediately revoked
    deact_resp = admin_client.post(
        f"/api/v1/admin/staff/{staff_pub_id}/deactivate",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert deact_resp.status_code == 200
    assert deact_resp.get_json()["staff"]["status"] == "deactivated"

    # Existing staff session fails `/api/v1/auth/me` and `/api/v1/staff/profile`
    assert staff_client.get("/api/v1/auth/me").status_code == 401
    assert staff_client.get("/api/v1/staff/profile").status_code == 401

    # Deactivated staff cannot log in again
    relogin = _login(staff_client, "ramesh.electrician@hostelcare.test", "RameshStrongPass1!")
    assert relogin.status_code == 403
    assert relogin.get_json()["error"]["code"] == "account_deactivated"


@pytest.mark.db
def test_staff_email_editing_validation_audit_and_password_setup_workflow(auth_app):
    """Verify editing staff email with validation, audit logging, and password setup flow."""
    _create_active_admin(auth_app)
    admin_client = auth_app.test_client()
    anon_client = auth_app.test_client()
    staff_client = auth_app.test_client()

    admin_csrf = _login(admin_client, "warden@hostelcare.test", "AdminPass123!").get_json()[
        "csrf_token"
    ]

    # Create staff with placeholder email
    create_resp = admin_client.post(
        "/api/v1/admin/staff",
        json={
            "fullName": "Suresh Carpenter",
            "email": "suresh.placeholder@hostelcare.test",
            "phone": "+91 98888 11111",
            "staffCode": "STF-0099",
            "trade": "Carpenter",
            "shift": "General (09:00 AM - 05:30 PM)",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create_resp.status_code == 201
    staff_data = create_resp.get_json()["staff"]
    staff_pub_id = staff_data["id"]

    # 1. Unauthorized attempts to update staff email are rejected
    assert (
        anon_client.patch(
            f"/api/v1/admin/staff/{staff_pub_id}",
            json={"email": "hacked@hostelcare.test"},
        ).status_code
        == 401
    )

    # 2. Invalid email formats are rejected with 400
    for invalid_email in ["not-an-email", "@hostelcare.test", "suresh@", "suresh@.test", ""]:
        bad_resp = admin_client.patch(
            f"/api/v1/admin/staff/{staff_pub_id}",
            json={"email": invalid_email},
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert bad_resp.status_code == 400
        assert bad_resp.get_json()["error"]["code"] == "validation_error"

    # 3. Duplicate email (already used by admin) is rejected with 409
    dup_resp = admin_client.patch(
        f"/api/v1/admin/staff/{staff_pub_id}",
        json={"email": "warden@hostelcare.test"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert dup_resp.status_code == 409
    assert dup_resp.get_json()["error"]["code"] == "conflict"

    # 4. Successful email update to real email
    clear_console_outbox()
    update_resp = admin_client.patch(
        f"/api/v1/admin/staff/{staff_pub_id}",
        json={"email": " Suresh.Real@HostelCare.TEST "},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.get_json()["staff"]
    # Email is normalized to lowercase and trimmed
    assert updated_data["email"] == "suresh.real@hostelcare.test"
    assert updated_data["id"] == staff_pub_id
    assert updated_data["role"] == "staff"
    assert updated_data["staffCode"] == "STF-0099"

    # 5. Verify database state and audit log
    with auth_app.app_context():
        user_row = db.session.execute(
            select(User).where(User.public_id == staff_pub_id)
        ).scalar_one()
        assert user_row.email == "suresh.real@hostelcare.test"
        assert user_row.role == "staff"
        assert user_row.status == "active"
        assert user_row.staff_profile.staff_code == "STF-0099"

        # Verify audit log was recorded for email change
        audit_entry = db.session.execute(
            select(AuditLog)
            .where(
                AuditLog.action == "staff.email_updated",
                AuditLog.target_id == str(staff_pub_id),
            )
            .order_by(AuditLog.id.desc())
        ).scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.metadata_json["new_email"] == "suresh.real@hostelcare.test"
        assert audit_entry.metadata_json["old_email"] == "suresh.placeholder@hostelcare.test"
        # Never contains passwords or tokens
        assert "password" not in str(audit_entry.metadata_json)
        assert "token" not in str(audit_entry.metadata_json)

    # 6. Admin triggers password setup link for the updated staff member
    clear_console_outbox()
    reset_trigger_resp = admin_client.post(
        f"/api/v1/admin/users/{staff_pub_id}/send-password-reset",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert reset_trigger_resp.status_code == 200

    outbox = get_console_outbox()
    assert len(outbox) == 1
    assert outbox[0].to == "suresh.real@hostelcare.test"
    match = _TOKEN_EXTRACT_RE.search(outbox[0].body)
    assert match is not None
    setup_token = match.group(1)

    # 7. Staff completes password setup using the token sent to the updated email
    setup_resp = staff_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": setup_token,
            "password": "SureshRealPass123!",
            "confirmPassword": "SureshRealPass123!",
        },
    )
    assert setup_resp.status_code == 200

    # 8. Staff logs in with the new email
    staff_login = _login(staff_client, "suresh.real@hostelcare.test", "SureshRealPass123!")
    assert staff_login.status_code == 200
    assert staff_login.get_json()["user"]["email"] == "suresh.real@hostelcare.test"

    # Old placeholder email cannot log in
    old_login = _login(anon_client, "suresh.placeholder@hostelcare.test", "SureshRealPass123!")
    assert old_login.status_code == 401


@pytest.mark.db
def test_staff_password_setup_token_lifecycle_console_mode_and_rejection_cases(auth_app):
    """Verify complete password setup token lifecycle for staff, unredacted console mode URL,
    atomic single-use redemption, Argon2id update, and login verification.
    """
    _create_active_admin(auth_app)
    admin_client = auth_app.test_client()
    anon_client = auth_app.test_client()
    staff_client = auth_app.test_client()

    admin_csrf = _login(admin_client, "warden@hostelcare.test", "AdminPass123!").get_json()[
        "csrf_token"
    ]

    # 1. Create staff account with placeholder email
    create_resp = admin_client.post(
        "/api/v1/admin/staff",
        json={
            "fullName": "Raghu Staff",
            "email": "raghu.initial@hostelcare.test",
            "phone": "+91 91234 56789",
            "staffCode": "STF-0777",
            "trade": "Electrician",
            "shift": "Morning (07:00 AM - 03:30 PM)",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create_resp.status_code == 201
    staff_pub_id = create_resp.get_json()["staff"]["id"]

    # 2. Update staff email to real address
    update_resp = admin_client.patch(
        f"/api/v1/admin/staff/{staff_pub_id}",
        json={"email": "raghu.verified@hostelcare.test"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["staff"]["email"] == "raghu.verified@hostelcare.test"

    # 3. Trigger setup link dispatch
    clear_console_outbox()
    send_resp = admin_client.post(
        f"/api/v1/admin/users/{staff_pub_id}/send-password-reset",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert send_resp.status_code == 200

    outbox = get_console_outbox()
    assert len(outbox) == 1
    dispatched = outbox[0]
    assert dispatched.to == "raghu.verified@hostelcare.test"
    assert "Set Up Your Account Password" in dispatched.subject

    match = _TOKEN_EXTRACT_RE.search(dispatched.body)
    assert match is not None
    raw_token = match.group(1)
    assert len(raw_token) >= 43  # 256 bits via token_urlsafe(32)

    # 4. Verify DB stores only SHA-256 hash, not plaintext token
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with auth_app.app_context():
        # Previous token issued at creation must be revoked
        tokens = db.session.execute(
            select(PasswordResetToken)
            .join(User, User.id == PasswordResetToken.user_id)
            .where(User.public_id == staff_pub_id)
            .order_by(PasswordResetToken.id.asc())
        ).scalars().all()
        assert len(tokens) == 2
        initial_token, fresh_token = tokens[0], tokens[1]
        assert initial_token.revoked_at is not None
        assert initial_token.used_at is None
        assert fresh_token.revoked_at is None
        assert fresh_token.used_at is None
        assert fresh_token.token_hash == expected_hash
        assert fresh_token.token_hash != raw_token
        assert fresh_token.expires_at > datetime.now(UTC)

    # 5. Redacted token placeholder is rejected
    redacted_resp = anon_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "[REDACTED-TOKEN]",
            "password": "RaghuStrongPass123!",
            "confirmPassword": "RaghuStrongPass123!",
        },
    )
    assert redacted_resp.status_code == 400
    assert redacted_resp.get_json()["error"]["code"] == "invalid_or_expired_token"

    # 6. Weak password policy rejection
    weak_resp = anon_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "password": "weak",
            "confirmPassword": "weak",
        },
    )
    assert weak_resp.status_code == 400
    assert weak_resp.get_json()["error"]["code"] == "validation_error"

    # 7. Password mismatch rejection
    mismatch_resp = anon_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "password": "RaghuStrongPass123!",
            "confirmPassword": "DifferentPassword123!",
        },
    )
    assert mismatch_resp.status_code == 400
    assert mismatch_resp.get_json()["error"]["code"] == "validation_error"

    # 8. Successful atomic redemption with valid raw token
    redeem_resp = anon_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "password": "RaghuStrongPass123!",
            "confirmPassword": "RaghuStrongPass123!",
        },
    )
    assert redeem_resp.status_code == 200
    assert "updated successfully" in redeem_resp.get_json()["message"]

    # 9. Verify token is marked used and user password is now Argon2id hash
    with auth_app.app_context():
        token_after = db.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == expected_hash)
        ).scalar_one()
        assert token_after.used_at is not None

        user_after = db.session.execute(
            select(User).where(User.public_id == staff_pub_id)
        ).scalar_one()
        assert user_after.password_hash.startswith("$argon2id$")
        assert user_after.password_hash != UNUSABLE_PASSWORD_MARKER

    # 10. Re-using the same token fails (single-use enforcement)
    reuse_resp = anon_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "password": "AnotherNewPass123!",
            "confirmPassword": "AnotherNewPass123!",
        },
    )
    assert reuse_resp.status_code == 400
    assert reuse_resp.get_json()["error"]["code"] == "invalid_or_expired_token"

    # 11. Staff can log in immediately with updated email and new password
    staff_login = _login(staff_client, "raghu.verified@hostelcare.test", "RaghuStrongPass123!")
    assert staff_login.status_code == 200
    login_user = staff_login.get_json()["user"]
    assert login_user["email"] == "raghu.verified@hostelcare.test"
    assert login_user["role"] == "staff"


@pytest.mark.db
def test_cross_role_authorization_matrix_and_csrf_protection(auth_app):
    """Verify strict RBAC isolation across student, staff, and admin plus CSRF & Origin checks."""
    _create_active_admin(auth_app)
    admin_client = auth_app.test_client()
    student_client = auth_app.test_client()
    staff_client = auth_app.test_client()
    anon_client = auth_app.test_client()

    admin_csrf = _login(admin_client, "warden@hostelcare.test", "AdminPass123!").get_json()[
        "csrf_token"
    ]

    # Create active student
    reg = student_client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Ananya Iyer",
            "email": "ananya@hostelcare.test",
            "rollNumber": "2026ECB1089",
            "phone": "+91 97123 45678",
            "password": "AnanyaPass123!",
            "confirmPassword": "AnanyaPass123!",
        },
    )
    stu_id = reg.get_json()["user"]["id"]
    admin_client.post(
        f"/api/v1/admin/students/{stu_id}/approve",
        headers={"X-CSRF-Token": admin_csrf},
    )
    stu_csrf = _login(student_client, "ananya@hostelcare.test", "AnanyaPass123!").get_json()[
        "csrf_token"
    ]

    # Create active staff with password
    admin_client.post(
        "/api/v1/admin/staff",
        json={
            "fullName": "Santosh Kumar",
            "email": "santosh@hostelcare.test",
            "phone": "+91 94421 88902",
            "staffCode": "STF-0002",
            "trade": "Plumber",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    raw_token = _TOKEN_EXTRACT_RE.search(get_console_outbox()[-1].body).group(1)
    staff_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "password": "SantoshPass123!",
            "confirmPassword": "SantoshPass123!",
        },
    )
    staff_csrf = _login(staff_client, "santosh@hostelcare.test", "SantoshPass123!").get_json()[
        "csrf_token"
    ]

    # 1. Anonymous client is denied all protected endpoints (401)
    for path in (
        "/api/v1/auth/me",
        "/api/v1/student/profile",
        "/api/v1/staff/profile",
        "/api/v1/admin/students",
        "/api/v1/admin/students/pending",
        "/api/v1/admin/staff",
        "/api/v1/admin/audit-logs",
    ):
        assert anon_client.get(path).status_code == 401

    # 2. Student cannot access staff or admin endpoints (403 forbidden)
    assert student_client.get("/api/v1/staff/profile").status_code == 403
    assert student_client.get("/api/v1/admin/students").status_code == 403
    assert student_client.get("/api/v1/admin/staff").status_code == 403
    assert student_client.get("/api/v1/admin/audit-logs").status_code == 403
    assert (
        student_client.post(
            "/api/v1/admin/staff",
            json={"fullName": "Fake", "email": "f@hc.test", "trade": "Plumber"},
            headers={"X-CSRF-Token": stu_csrf},
        ).status_code
        == 403
    )

    # 3. Staff cannot access student or admin endpoints (403 forbidden)
    assert staff_client.get("/api/v1/student/profile").status_code == 403
    assert staff_client.get("/api/v1/admin/students").status_code == 403
    assert staff_client.get("/api/v1/admin/staff").status_code == 403
    assert staff_client.get("/api/v1/admin/audit-logs").status_code == 403
    assert (
        staff_client.post(
            f"/api/v1/admin/students/{stu_id}/reject",
            json={"reason": "Unauthorized attempt"},
            headers={"X-CSRF-Token": staff_csrf},
        ).status_code
        == 403
    )

    # 4. Admin cannot access student-only or staff-only endpoints (403 forbidden)
    assert admin_client.get("/api/v1/student/profile").status_code == 403
    assert admin_client.get("/api/v1/staff/profile").status_code == 403

    # 5. Missing or wrong CSRF token on cookie-authenticated POST/PATCH is rejected with 403
    no_csrf = admin_client.post("/api/v1/auth/logout")
    assert no_csrf.status_code == 403
    assert no_csrf.get_json()["error"]["code"] == "csrf_invalid"

    # 6. Untrusted Origin header on state-changing request is rejected with 403
    bad_origin = admin_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": admin_csrf, "Origin": "https://evil.example.com"},
    )
    assert bad_origin.status_code == 403
    assert bad_origin.get_json()["error"]["code"] == "invalid_origin"

    # 7. Valid logout clears session
    logout_ok = student_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": stu_csrf},
    )
    assert logout_ok.status_code == 200
    assert student_client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.db
def test_login_strict_role_enforcement_and_mismatch_rejection(auth_app):
    """Verify backend role enforcement upon login:
    - Student + Student selection -> 200
    - Staff + Staff selection -> 200
    - Admin + Warden/Admin selection -> 200
    - Student + Staff selection -> 403 role_mismatch
    - Staff + Student selection -> 403 role_mismatch
    - Admin + Student selection -> 403 role_mismatch
    - Role mismatch does not create an authenticated session (GET /me -> 401)
    - Bad credentials return 401 invalid_credentials without leaking role info
    """
    _create_active_admin(auth_app, email="warden.strict@hostelcare.test", password="AdminPass123!")

    # 1. Create active student
    with auth_app.app_context():
        student = User(
            email="student.strict@hostelcare.test",
            password_hash=hash_password("StudentPass123!"),
            full_name="Aakash Student",
            role="student",
            status="active",
        )
        student.student_profile = StudentProfile(
            roll_number="2026STRICT01",
        )
        # Create active staff
        staff = User(
            email="staff.strict@hostelcare.test",
            password_hash=hash_password("StaffPass123!"),
            full_name="Santosh Staff",
            role="staff",
            status="active",
        )
        staff.staff_profile = StaffProfile(
            staff_code="STF-STR01",
            trade="Plumbing",
            shift="Morning",
        )
        db.session.add_all([student, staff])
        db.session.commit()

    # 2. Positive matches with canonical and display labels
    # Student + Student selection -> success
    stu_client = auth_app.test_client()
    resp = _login(
        stu_client, "student.strict@hostelcare.test", "StudentPass123!", role="student"
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["role"] == "student"
    assert stu_client.get("/api/v1/auth/me").status_code == 200

    # Staff + Staff selection -> success
    staff_client = auth_app.test_client()
    resp = _login(staff_client, "staff.strict@hostelcare.test", "StaffPass123!", role="staff")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["role"] == "staff"
    assert staff_client.get("/api/v1/auth/me").status_code == 200

    # Admin + Warden/Admin selection -> success
    admin_client = auth_app.test_client()
    resp = _login(
        admin_client, "warden.strict@hostelcare.test", "AdminPass123!", role="Warden/Admin"
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["role"] == "admin"
    assert admin_client.get("/api/v1/auth/me").status_code == 200

    # 3. Role mismatch rejections with HTTP 403
    # Student account + Staff selection -> HTTP 403
    mismatch_client1 = auth_app.test_client()
    resp = _login(
        mismatch_client1, "student.strict@hostelcare.test", "StudentPass123!", role="staff"
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "role_mismatch"
    assert "selected role does not match" in resp.get_json()["error"]["message"]
    # Verify no authenticated session was established
    assert mismatch_client1.get("/api/v1/auth/me").status_code == 401

    # Staff account + Student selection -> HTTP 403
    mismatch_client2 = auth_app.test_client()
    resp = _login(
        mismatch_client2, "staff.strict@hostelcare.test", "StaffPass123!", role="student"
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "role_mismatch"
    assert mismatch_client2.get("/api/v1/auth/me").status_code == 401

    # Admin account + Student selection -> HTTP 403
    mismatch_client3 = auth_app.test_client()
    resp = _login(
        mismatch_client3, "warden.strict@hostelcare.test", "AdminPass123!", role="student"
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "role_mismatch"
    assert mismatch_client3.get("/api/v1/auth/me").status_code == 401

    # Admin account + Staff selection -> HTTP 403
    mismatch_client4 = auth_app.test_client()
    resp = _login(
        mismatch_client4, "warden.strict@hostelcare.test", "AdminPass123!", role="staff"
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "role_mismatch"
    assert mismatch_client4.get("/api/v1/auth/me").status_code == 401

    # 4. Unknown account or bad password returns 401 without leaking role mismatch
    bad_pw_client = auth_app.test_client()
    bad_pw_resp = _login(
        bad_pw_client, "student.strict@hostelcare.test", "WrongPassword123!", role="staff"
    )
    assert bad_pw_resp.status_code == 401
    assert bad_pw_resp.get_json()["error"]["code"] == "invalid_credentials"
    assert bad_pw_client.get("/api/v1/auth/me").status_code == 401

    unknown_client = auth_app.test_client()
    unknown_resp = _login(
        unknown_client, "nonexistent@hostelcare.test", "SomePass123!", role="admin"
    )
    assert unknown_resp.status_code == 401
    assert unknown_resp.get_json()["error"]["code"] == "invalid_credentials"
    assert unknown_client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.db
def test_password_reset_neutrality_single_use_expiry_and_session_invalidation(auth_app):
    """Verify neutral forgot-password responses, single-use & expired tokens, and session bump."""
    _create_active_admin(auth_app, email="warden@hostelcare.test", password="OldPassword123!")
    browser_session = auth_app.test_client()
    reset_client = auth_app.test_client()

    # Log in on `browser_session`
    login_resp = _login(browser_session, "warden@hostelcare.test", "OldPassword123!")
    assert login_resp.status_code == 200
    assert browser_session.get("/api/v1/auth/me").status_code == 200

    # 1. Forgot-password for unknown email vs known email returns identical neutral response
    unknown_resp = reset_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@hostelcare.test"},
    )
    known_resp = reset_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "warden@hostelcare.test"},
    )
    assert unknown_resp.status_code == 200
    assert known_resp.status_code == 200
    assert unknown_resp.get_json() == known_resp.get_json()
    assert len(get_console_outbox()) == 1
    first_token = _TOKEN_EXTRACT_RE.search(get_console_outbox()[0].body).group(1)

    # Verify redact_reset_tokens never leaves raw token in log strings
    assert first_token not in redact_reset_tokens(get_console_outbox()[0].body)

    # 2. Requesting a second reset token revokes the first token
    second_resp = reset_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "warden@hostelcare.test"},
    )
    assert second_resp.status_code == 200
    second_token = _TOKEN_EXTRACT_RE.search(get_console_outbox()[1].body).group(1)
    assert second_token != first_token

    # First token is now revoked and cannot be redeemed
    revoked_attempt = reset_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": first_token,
            "password": "NewPassword123!",
            "confirmPassword": "NewPassword123!",
        },
    )
    assert revoked_attempt.status_code == 400
    assert revoked_attempt.get_json()["error"]["code"] == "invalid_or_expired_token"

    # 3. Redeem second token -> succeeds, increments session_version, invalidates `browser_session`
    redeem_ok = reset_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": second_token,
            "password": "NewPassword123!",
            "confirmPassword": "NewPassword123!",
        },
    )
    assert redeem_ok.status_code == 200

    # Existing logged-in browser session is immediately invalidated on session_version increment!
    me_after_reset = browser_session.get("/api/v1/auth/me")
    assert me_after_reset.status_code == 401
    assert me_after_reset.get_json()["error"]["code"] == "session_expired"

    # 4. Reusing the already-redeemed second token is rejected (single-use)
    reuse_attempt = reset_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": second_token,
            "password": "AnotherPassword123!",
            "confirmPassword": "AnotherPassword123!",
        },
    )
    assert reuse_attempt.status_code == 400
    assert reuse_attempt.get_json()["error"]["code"] == "invalid_or_expired_token"

    # 5. Expired token rejection
    with auth_app.app_context():
        admin_user = db.session.execute(
            select(User).where(User.email == "warden@hostelcare.test")
        ).scalar_one()
        expired_raw = "expired-test-token-value-1234567890"
        expired_hash = hashlib.sha256(expired_raw.encode("utf-8")).hexdigest()
        past_created = datetime.now(UTC) - timedelta(minutes=45)
        past_expires = past_created + timedelta(minutes=30)
        db.session.add(
            PasswordResetToken(
                user_id=admin_user.id,
                token_hash=expired_hash,
                created_at=past_created,
                expires_at=past_expires,
            )
        )
        db.session.commit()

    expired_attempt = reset_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": expired_raw,
            "password": "ExpiredTryPassword123!",
            "confirmPassword": "ExpiredTryPassword123!",
        },
    )
    assert expired_attempt.status_code == 400
    assert expired_attempt.get_json()["error"]["code"] == "invalid_or_expired_token"


@pytest.mark.db
def test_rate_limiting_and_audit_log_sanitization(auth_app):
    """Verify per-user and per-IP rate limits, account lockout, and audit log completeness."""
    admin_pub_id = _create_active_admin(
        auth_app, email="warden@hostelcare.test", password="AdminPass123!"
    )
    client = auth_app.test_client()

    # 1. Per-user password reset rate limit: max 3 tokens created per user per hour
    for _ in range(4):
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "warden@hostelcare.test"},
        )
        assert resp.status_code == 200

    # Only 3 emails/tokens were issued; the 4th was silently suppressed with neutral 200 response
    assert len(get_console_outbox()) == 3

    # 2. Account lockout after 5 failed password attempts
    for _ in range(5):
        fail_resp = _login(client, "warden@hostelcare.test", "WrongPassword999!")
        assert fail_resp.status_code == 401

    # 6th attempt even with the right password is rejected with 429 account_locked
    locked_resp = _login(client, "warden@hostelcare.test", "AdminPass123!")
    assert locked_resp.status_code == 429
    assert locked_resp.get_json()["error"]["code"] == "account_locked"

    # 3. Verify audit logs recorded events and never stored sensitive fields
    with auth_app.app_context():
        logs = list(db.session.execute(select(AuditLog)).scalars().all())
        actions = {entry.action for entry in logs}
        assert "auth.reset_requested" in actions
        assert "auth.login_failed" in actions
        assert "auth.login_locked" in actions
        for entry in logs:
            serialized_meta = str(entry.metadata_json).lower()
            assert "adminpass123" not in serialized_meta
            assert "wrongpassword999" not in serialized_meta
            assert "$argon2id$" not in serialized_meta
    assert admin_pub_id


@pytest.mark.db
def test_admin_triggered_password_reset_and_cli_commands(auth_app):
    """Verify `POST /api/v1/admin/users/{id}/send-password-reset` and auth CLI commands."""
    runner = auth_app.test_cli_runner()

    # 1. Seed an active admin via the `flask create-admin` CLI command
    res_cli = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "cli.warden@hostelcare.test",
            "--full-name",
            "Prof. A. K. Sharma",
            "--password",
            "CliAdminPass123!",
        ]
    )
    assert res_cli.exit_code == 0
    assert "Created admin account" in res_cli.output

    admin_client = auth_app.test_client()
    login_resp = _login(admin_client, "cli.warden@hostelcare.test", "CliAdminPass123!")
    assert login_resp.status_code == 200
    admin_csrf = login_resp.get_json()["csrf_token"]

    # 2. Create a staff account and trigger an admin-initiated password reset for them
    staff_resp = admin_client.post(
        "/api/v1/admin/staff",
        json={
            "fullName": "Deepak Verma",
            "email": "deepak.carpenter@hostelcare.test",
            "phone": "+91 98111 22333",
            "staffCode": "STF-0099",
            "trade": "Carpenter",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert staff_resp.status_code == 201
    staff_pub_id = staff_resp.get_json()["staff"]["id"]
    clear_console_outbox()

    trigger_resp = admin_client.post(
        f"/api/v1/admin/users/{staff_pub_id}/send-password-reset",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert trigger_resp.status_code == 200
    assert len(get_console_outbox()) == 1
    assert get_console_outbox()[0].to == "deepak.carpenter@hostelcare.test"

    # 3. Verify `flask purge-reset-tokens` invokes `app_purge_expired_reset_tokens()`
    purge_cli = runner.invoke(args=["purge-reset-tokens"])
    assert purge_cli.exit_code == 0
    assert "Purged" in purge_cli.output
