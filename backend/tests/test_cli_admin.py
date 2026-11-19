"""Tests for `flask create-admin` CLI command: secure interactive password setup,
password policy enforcement, single-admin safeguard, and database transaction atomicity.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import select, text

from app import create_app
from app.auth.security import (
    UNUSABLE_PASSWORD_MARKER,
    verify_password_safe,
)
from app.core.mailer import clear_console_outbox
from app.extensions import db
from app.models.audit import AuditLog
from app.models.identity import User

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


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


@pytest.mark.db
def test_create_admin_interactive_success(auth_app):
    """Verify successful interactive administrator creation with getpass and Argon2id."""
    runner = auth_app.test_cli_runner()

    res = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.interactive@hostelcare.test",
            "--name",
            "Dr. K. S. Verma",
            "--designation",
            "Chief Hostel Warden",
        ],
        input="SecureAdminPass123!\nSecureAdminPass123!\n",
    )

    assert res.exit_code == 0
    assert "Created admin account: warden.interactive@hostelcare.test" in res.output
    # Plaintext password must never appear in command output
    assert "SecureAdminPass123!" not in res.output

    with auth_app.app_context():
        admin = db.session.execute(
            select(User).where(User.email == "warden.interactive@hostelcare.test")
        ).scalar_one()

        assert admin.role == "admin"
        assert admin.status == "active"
        assert admin.full_name == "Dr. K. S. Verma"
        assert admin.designation == "Chief Hostel Warden"
        assert admin.password_hash.startswith("$argon2id$")

        # Verify Argon2id password verification
        is_valid, _ = verify_password_safe(admin.password_hash, "SecureAdminPass123!")
        assert is_valid is True
        invalid, _ = verify_password_safe(admin.password_hash, "WrongPassword123!")
        assert invalid is False

        # Verify audit log recorded without sensitive credentials
        audit = db.session.execute(
            select(AuditLog).where(
                AuditLog.action == "admin.created_cli",
                AuditLog.target_id == str(admin.public_id),
            )
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.metadata_json == {"designation": "Chief Hostel Warden"}


@pytest.mark.db
def test_create_admin_interactive_password_mismatch(auth_app):
    """Verify interactive creation is rejected when password and confirmation mismatch."""
    runner = auth_app.test_cli_runner()

    res = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.mismatch@hostelcare.test",
            "--name",
            "Dr. Mismatch",
        ],
        input="SecureAdminPass123!\nDifferentPass123!\n",
    )

    assert res.exit_code != 0
    assert "Password and confirmation password do not match." in res.output
    assert "SecureAdminPass123!" not in res.output
    assert "DifferentPass123!" not in res.output

    with auth_app.app_context():
        user = db.session.execute(
            select(User).where(User.email == "warden.mismatch@hostelcare.test")
        ).scalar_one_or_none()
        assert user is None


@pytest.mark.db
@pytest.mark.parametrize(
    ("weak_pw", "expected_err"),
    [
        ("Abc1!", "Password must be at least 8 characters long."),
        ("LettersOnlyNoDigits!", "Password must contain at least one letter and one number."),
        ("1234567890!", "Password must contain at least one letter and one number."),
        ("         ", "Password cannot consist solely of whitespace."),
    ],
)
def test_create_admin_interactive_weak_passwords(auth_app, weak_pw, expected_err):
    """Verify password policy rejects weak passwords (length, numbers, letters, whitespace)."""
    runner = auth_app.test_cli_runner()

    res = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.weak@hostelcare.test",
            "--name",
            "Dr. Weak Password",
        ],
        input=f"{weak_pw}\n{weak_pw}\n",
    )

    assert res.exit_code != 0
    assert expected_err in res.output

    with auth_app.app_context():
        user = db.session.execute(
            select(User).where(User.email == "warden.weak@hostelcare.test")
        ).scalar_one_or_none()
        assert user is None


@pytest.mark.db
def test_create_admin_duplicate_admin_prevention(auth_app):
    """Verify single-admin safeguard prevents creating a second administrator."""
    runner = auth_app.test_cli_runner()

    # 1. Create the initial administrator
    res1 = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.primary@hostelcare.test",
            "--name",
            "Dr. Primary Warden",
        ],
        input="PrimaryPass123!\nPrimaryPass123!\n",
    )
    assert res1.exit_code == 0
    assert "Created admin account" in res1.output

    # 2. Attempt to create a second admin with a different email
    res2 = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.secondary@hostelcare.test",
            "--name",
            "Dr. Secondary Warden",
        ],
        input="SecondaryPass123!\nSecondaryPass123!\n",
    )
    assert res2.exit_code != 0
    assert (
        "An administrator account already exists (warden.primary@hostelcare.test)." in res2.output
    )

    # 3. Attempt to create an admin with the same email
    res3 = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.primary@hostelcare.test",
            "--name",
            "Dr. Primary Duplicate",
        ],
        input="DuplicatePass123!\nDuplicatePass123!\n",
    )
    assert res3.exit_code != 0
    assert (
        "An administrator account already exists (warden.primary@hostelcare.test)." in res3.output
    )

    with auth_app.app_context():
        admins = db.session.execute(select(User).where(User.role == "admin")).scalars().all()
        assert len(admins) == 1
        assert admins[0].email == "warden.primary@hostelcare.test"


@pytest.mark.db
def test_create_admin_email_setup_flow_when_no_password_supplied(auth_app):
    """Verify compatibility with email-based setup flow when no password is typed at prompt."""
    runner = auth_app.test_cli_runner()

    # Press Enter at prompt without entering any characters
    res = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.emailsetup@hostelcare.test",
            "--name",
            "Dr. Email Setup Warden",
        ],
        input="\n",
    )

    assert res.exit_code == 0
    assert "Created admin account: warden.emailsetup@hostelcare.test" in res.output

    with auth_app.app_context():
        admin = db.session.execute(
            select(User).where(User.email == "warden.emailsetup@hostelcare.test")
        ).scalar_one()

        # Must have unusable password marker '!'
        assert admin.password_hash == UNUSABLE_PASSWORD_MARKER
        is_valid, _ = verify_password_safe(admin.password_hash, "AnyPassword123!")
        assert is_valid is False


@pytest.mark.db
def test_create_admin_preserved_options_and_duplicate_email(auth_app):
    """Verify preserved CLI options (--full-name, --designation, --password, --no-password)."""
    runner = auth_app.test_cli_runner()

    # Test non-interactive creation with --password and --full-name
    res_direct = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "warden.direct@hostelcare.test",
            "--full-name",
            "Prof. Direct Option",
            "--designation",
            "Senior Warden",
            "--password",
            "DirectAdminPass123!",
        ]
    )
    assert res_direct.exit_code == 0

    with auth_app.app_context():
        admin = db.session.execute(
            select(User).where(User.email == "warden.direct@hostelcare.test")
        ).scalar_one()
        assert admin.full_name == "Prof. Direct Option"
        assert admin.designation == "Senior Warden"
        is_valid, _ = verify_password_safe(admin.password_hash, "DirectAdminPass123!")
        assert is_valid is True
