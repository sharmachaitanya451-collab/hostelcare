"""Tests for Gmail SMTP config, delivery, safe failure logging, and password-reset flow."""

from __future__ import annotations

import logging
import smtplib
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth.security import hash_password
from app.core.mailer import (
    clear_console_outbox,
    get_console_outbox,
    send_email,
    send_password_reset_email,
)
from app.extensions import db
from app.models.identity import User

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def mail_db_app():
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture(autouse=True)
def _clean_outbox():
    clear_console_outbox()
    yield
    clear_console_outbox()


def _truncate_test_db(app) -> None:
    owner_engine = create_engine(app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
                "public.password_reset_tokens, "
                "public.staff_profiles, "
                "public.student_profiles, "
                "public.users "
                "RESTART IDENTITY CASCADE;"
            )
        )


def test_smtp_config_loaded_from_environment(monkeypatch):
    monkeypatch.setattr("app.config.BaseConfig.MAIL_BACKEND", "smtp")
    monkeypatch.setattr("app.config.BaseConfig.MAIL_FROM", "HostelCare <demo@gmail.com>")
    monkeypatch.setattr("app.config.BaseConfig.MAIL_SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr("app.config.BaseConfig.MAIL_SMTP_PORT", 587)
    monkeypatch.setattr("app.config.BaseConfig.MAIL_SMTP_USERNAME", "demo@gmail.com")
    monkeypatch.setattr("app.config.BaseConfig.MAIL_SMTP_PASSWORD", "fake-app-pass-for-test")
    monkeypatch.setattr("app.config.BaseConfig.MAIL_USE_TLS", True)
    monkeypatch.setattr("app.config.BaseConfig.MAIL_TIMEOUT_SECONDS", 15)

    app = create_app("development")
    assert app.config["MAIL_BACKEND"] == "smtp"
    assert app.config["MAIL_FROM"] == "HostelCare <demo@gmail.com>"
    assert app.config["MAIL_SMTP_HOST"] == "smtp.gmail.com"
    assert app.config["MAIL_SMTP_PORT"] == 587
    assert app.config["MAIL_SMTP_USERNAME"] == "demo@gmail.com"
    assert app.config["MAIL_SMTP_PASSWORD"] == "fake-app-pass-for-test"
    assert app.config["MAIL_USE_TLS"] is True
    assert app.config["MAIL_TIMEOUT_SECONDS"] == 15


def test_smtp_send_email_starttls_and_from_fallback(monkeypatch):
    recorded: dict[str, object] = {}

    class DummySMTP:
        def __init__(self, *, host, port, timeout):
            recorded["init"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            recorded["ehlo_count"] = int(recorded.get("ehlo_count", 0)) + 1

        def starttls(self, *, context=None):
            recorded["starttls_has_context"] = context is not None

        def login(self, username, password):
            recorded["login"] = (username, password)

        def send_message(self, msg):
            recorded["msg"] = msg

    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)

    app = create_app("testing")
    app.config["MAIL_BACKEND"] = "smtp"
    app.config["MAIL_FROM"] = "no-reply@hostelcare.local"
    app.config["MAIL_SMTP_HOST"] = "smtp.gmail.com"
    app.config["MAIL_SMTP_PORT"] = 587
    app.config["MAIL_SMTP_USERNAME"] = "hostelcare.mailer@gmail.com"
    app.config["MAIL_SMTP_PASSWORD"] = "fake-secret-app-password"
    app.config["MAIL_USE_TLS"] = True
    app.config["APP_BASE_URL"] = "https://hostelcare.onrender.com"

    with app.app_context():
        ok = send_password_reset_email(
            to_email="resident@example.com",
            full_name="Aarav Mehta",
            raw_token="raw-token-abc-123",
            is_setup=False,
        )

    assert ok is True
    assert recorded["init"] == ("smtp.gmail.com", 587, 10)
    assert recorded["ehlo_count"] == 2
    assert recorded["starttls_has_context"] is True
    assert recorded["login"] == ("hostelcare.mailer@gmail.com", "fake-secret-app-password")
    sent_msg = recorded["msg"]
    assert sent_msg["From"] == "hostelcare.mailer@gmail.com"
    assert sent_msg["To"] == "resident@example.com"
    assert (
        "https://hostelcare.onrender.com/reset-password/raw-token-abc-123" in sent_msg.get_content()
    )


def test_smtp_failure_logs_safely_without_exposing_secrets_or_tokens(monkeypatch, caplog):
    class FailingSMTP:
        def __init__(self, *, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            pass

        def starttls(self, *, context=None):
            pass

        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

        def send_message(self, msg):
            raise AssertionError("Should not send when login fails")

    monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)

    app = create_app("testing")
    app.config["MAIL_BACKEND"] = "smtp"
    app.config["MAIL_SMTP_HOST"] = "smtp.gmail.com"
    app.config["MAIL_SMTP_PORT"] = 587
    app.config["MAIL_SMTP_USERNAME"] = "hostelcare.mailer@gmail.com"
    app.config["MAIL_SMTP_PASSWORD"] = "SUPER_SECRET_GMAIL_APP_PASSWORD"
    app.config["MAIL_USE_TLS"] = True

    with caplog.at_level(logging.ERROR), app.app_context():
        ok = send_password_reset_email(
            to_email="resident@example.com",
            full_name="Aarav Mehta",
            raw_token="SENSITIVE_RESET_TOKEN_999",
        )

    assert ok is False
    combined_logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "SMTPAuthenticationError" in combined_logs
    assert "SUPER_SECRET_GMAIL_APP_PASSWORD" not in combined_logs
    assert "SENSITIVE_RESET_TOKEN_999" not in combined_logs


def test_console_mode_still_dispatches_to_outbox():
    app = create_app("testing")
    assert app.config["MAIL_BACKEND"] == "console"
    with app.app_context():
        ok = send_email(
            to_email="local@hostelcare.test",
            subject="Test Subject",
            body="Test Console Body",
        )
    assert ok is True
    outbox = get_console_outbox()
    assert len(outbox) == 1
    assert outbox[0].to == "local@hostelcare.test"


@pytest.mark.db
def test_forgot_password_invokes_smtp_and_handles_smtp_failure_neutrally(mail_db_app, monkeypatch):
    _truncate_test_db(mail_db_app)
    with mail_db_app.app_context():
        db.session.add(
            User(
                email="reset.smtp@hostelcare.test",
                full_name="Priya Nair",
                password_hash=hash_password("OldPass123!"),
                role="student",
                status="active",
            )
        )
        db.session.commit()

    sent_calls: list[dict[str, object]] = []

    class FakeSMTP:
        def __init__(self, *, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            pass

        def starttls(self, *, context=None):
            pass

        def login(self, username, password):
            pass

        def send_message(self, msg):
            sent_calls.append(
                {"to": msg["To"], "subject": msg["Subject"], "body": msg.get_content()}
            )

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    orig_backend = mail_db_app.config.get("MAIL_BACKEND")
    orig_host = mail_db_app.config.get("MAIL_SMTP_HOST")
    orig_user = mail_db_app.config.get("MAIL_SMTP_USERNAME")
    orig_pwd = mail_db_app.config.get("MAIL_SMTP_PASSWORD")

    try:
        mail_db_app.config["MAIL_BACKEND"] = "smtp"
        mail_db_app.config["MAIL_SMTP_HOST"] = "smtp.gmail.com"
        mail_db_app.config["MAIL_SMTP_PORT"] = 587
        mail_db_app.config["MAIL_SMTP_USERNAME"] = "hostelcare.mailer@gmail.com"
        mail_db_app.config["MAIL_SMTP_PASSWORD"] = "fake-pass"
        mail_db_app.config["MAIL_USE_TLS"] = True

        client = mail_db_app.test_client()

        # Unknown account -> identical 200 without SMTP send
        r_unknown = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "doesnotexist@hostelcare.test"},
        )
        assert r_unknown.status_code == 200
        assert len(sent_calls) == 0

        # Known account -> sends real reset link via SMTP
        r_known = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset.smtp@hostelcare.test"},
        )
        assert r_known.status_code == 200
        assert r_known.get_json() == r_unknown.get_json()
        assert len(sent_calls) == 1
        assert sent_calls[0]["to"] == "reset.smtp@hostelcare.test"
        assert "/reset-password/" in str(sent_calls[0]["body"])

        # SMTP outage -> endpoint still returns identical neutral 200
        def _boom(*args, **kwargs):
            raise OSError("Network unreachable")

        monkeypatch.setattr(smtplib, "SMTP", _boom)
        r_outage = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset.smtp@hostelcare.test"},
        )
        assert r_outage.status_code == 200
        assert r_outage.get_json() == r_unknown.get_json()
    finally:
        mail_db_app.config["MAIL_BACKEND"] = orig_backend
        mail_db_app.config["MAIL_SMTP_HOST"] = orig_host
        mail_db_app.config["MAIL_SMTP_USERNAME"] = orig_user
        mail_db_app.config["MAIL_SMTP_PASSWORD"] = orig_pwd
        _truncate_test_db(mail_db_app)
