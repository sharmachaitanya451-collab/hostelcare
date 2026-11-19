"""Provider-independent email delivery service (ADR-023).

Supports `console` (default for local development and automated tests), `smtp`
(configurable via standard `MAIL_*` environment variables), and `disabled`.
Never logs raw password reset tokens or credentials.
"""

from __future__ import annotations

import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage

from flask import current_app

_TOKEN_URL_RE = re.compile(r"(/reset-password/)[A-Za-z0-9_\-]+")


@dataclass(frozen=True)
class DispatchedEmail:
    """In-memory record of an email sent through the console backend (for dev/test inspection)."""

    to: str
    subject: str
    body: str
    from_email: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# In-memory store populated only when MAIL_BACKEND == "console"
_console_outbox: list[DispatchedEmail] = []


def get_console_outbox() -> list[DispatchedEmail]:
    """Return a copy of the in-memory console outbox (used in tests)."""
    return list(_console_outbox)


def clear_console_outbox() -> None:
    """Clear the in-memory console outbox (used in test fixtures)."""
    _console_outbox.clear()


def redact_reset_tokens(text: str) -> str:
    """Replace any `/reset-password/<token>` segment with `[REDACTED-TOKEN]` for safe logging."""
    return _TOKEN_URL_RE.sub(r"\1[REDACTED-TOKEN]", text)


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    """Deliver a plain-text email via the configured backend (`console`, `smtp`, or `disabled`).

    In console mode (local development/testing), the full email is dispatched to the
    console/outbox so setup and reset links are readily accessible. In production (smtp), raw
    reset tokens and bodies are never written to application logs. Returns True if dispatched,
    False on error.
    """
    backend = current_app.config.get("MAIL_BACKEND", "console").lower()
    from_email = current_app.config.get("MAIL_FROM", "no-reply@hostelcare.local")

    if backend == "disabled":
        return True

    if backend == "console":
        _console_outbox.append(
            DispatchedEmail(
                to=to_email,
                subject=subject,
                body=body,
                from_email=from_email,
            )
        )
        is_production = current_app.config.get("ENV") == "production" or (
            not current_app.config.get("DEBUG", False)
            and not current_app.config.get("TESTING", False)
        )
        if is_production:
            current_app.logger.warning(
                "Console email dispatched in production to %s | subject=%r | body=%s",
                to_email,
                subject,
                redact_reset_tokens(body),
            )
        else:
            current_app.logger.info(
                "Console email dispatched to %s | subject=%r | body=\n%s",
                to_email,
                subject,
                body,
            )
            if not current_app.testing:
                print(
                    f"\n{'=' * 72}\n"
                    f"EMAIL DISPATCHED (console mode):\n"
                    f"To: {to_email}\n"
                    f"From: {from_email}\n"
                    f"Subject: {subject}\n"
                    f"{'-' * 72}\n"
                    f"{body.strip()}\n"
                    f"{'=' * 72}\n",
                    flush=True,
                )
        return True

    if backend == "smtp":
        host = str(current_app.config.get("MAIL_SMTP_HOST", "localhost") or "").strip()
        port = int(current_app.config.get("MAIL_SMTP_PORT", 587))
        username = str(current_app.config.get("MAIL_SMTP_USERNAME", "") or "").strip()
        password = str(current_app.config.get("MAIL_SMTP_PASSWORD", "") or "")
        use_tls = bool(current_app.config.get("MAIL_USE_TLS", True))
        timeout = int(current_app.config.get("MAIL_TIMEOUT_SECONDS", 10))

        if not host:
            current_app.logger.error(
                "SMTP email delivery skipped: MAIL_SMTP_HOST is not configured."
            )
            return False

        effective_from = str(from_email or "").strip()
        if (
            not effective_from or effective_from == "no-reply@hostelcare.local"
        ) and "@" in username:
            effective_from = username

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = effective_from
        msg["To"] = to_email
        msg.set_content(body)

        tls_context = ssl.create_default_context()
        try:
            if port == 465 and use_tls:
                with smtplib.SMTP_SSL(
                    host=host, port=port, timeout=timeout, context=tls_context
                ) as smtp:
                    smtp.ehlo()
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host=host, port=port, timeout=timeout) as smtp:
                    smtp.ehlo()
                    if use_tls:
                        smtp.starttls(context=tls_context)
                        smtp.ehlo()
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(msg)
            current_app.logger.info("SMTP email delivered to %s | subject=%r", to_email, subject)
            return True
        except Exception as exc:
            current_app.logger.error(
                "SMTP email delivery failed for recipient %s (%s)",
                to_email,
                type(exc).__name__,
            )
            return False

    current_app.logger.warning("Unknown MAIL_BACKEND %r; email not sent.", backend)
    return False


def send_password_reset_email(
    *,
    to_email: str,
    full_name: str,
    raw_token: str,
    is_setup: bool = False,
) -> bool:
    """Send a 30-minute password setup or reset link email. Never emails a password."""
    base_url = current_app.config.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    reset_url = f"{base_url}/reset-password/{raw_token}"

    if is_setup:
        subject = "HostelCare — Set Up Your Account Password"
        body = (
            f"Namaste {full_name},\n\n"
            f"An account has been provisioned for you on HostelCare.\n"
            f"Please set your password within 30 minutes using this single-use link:\n\n"
            f"{reset_url}\n\n"
            f"For your security, HostelCare never generates or emails temporary passwords.\n"
        )
    else:
        subject = "HostelCare — Password Reset Instructions"
        body = (
            f"Namaste {full_name},\n\n"
            f"We received a request to reset your HostelCare password.\n"
            f"You can set a new password within 30 minutes using this single-use link:\n\n"
            f"{reset_url}\n\n"
            f"If you did not request this change, you can safely ignore this message.\n"
        )

    return send_email(to_email=to_email, subject=subject, body=body)


def send_password_changed_email(*, to_email: str, full_name: str) -> bool:
    """Send a security notification confirming a password change."""
    subject = "HostelCare — Your Password Was Updated"
    body = (
        f"Namaste {full_name},\n\n"
        f"Your HostelCare account password was recently updated and all active sessions "
        f"have been signed out.\n\n"
        f"If you did not perform this action, please contact the Hostel Warden Office "
        f"immediately.\n"
    )
    return send_email(to_email=to_email, subject=subject, body=body)
