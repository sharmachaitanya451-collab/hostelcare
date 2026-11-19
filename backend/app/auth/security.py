"""Authentication security primitives: Argon2id hashing, password policy, session_version
verification, CSRF protection, Origin validation, and RBAC decorators.
"""

from __future__ import annotations

import contextlib
import re
import secrets
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import Flask, current_app, g, request, session
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.errors import error_response
from app.extensions import db
from app.models.identity import User

UNUSABLE_PASSWORD_MARKER = "!"  # noqa: S105

_ph = PasswordHasher()
# Precomputed Argon2id hash used for constant-time dummy verification when an account does not
# exist or carries the unusable password marker '!'.
_DUMMY_ARGON2_HASH: str = _ph.hash("hostelcare-constant-time-dummy-verification-target")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ROLL_NUMBER_RE = re.compile(r"^[A-Z0-9][A-Z0-9/_-]{2,31}$")
_STAFF_CODE_RE = re.compile(r"^[A-Z0-9-]{3,20}$")


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using Argon2id (`argon2-cffi`)."""
    if not isinstance(plaintext, str) or not plaintext:
        raise ValueError("Password cannot be empty.")
    if plaintext == UNUSABLE_PASSWORD_MARKER:
        raise ValueError("Password cannot equal the unusable password marker.")
    return _ph.hash(plaintext)


def verify_password_safe(password_hash: str | None, candidate: str) -> tuple[bool, bool]:
    """Verify `candidate` against `password_hash` in constant-time fashion.

    Returns `(is_valid, needs_rehash)`.
    Explicitly rejects the unusable password marker `'!'` (or any non-Argon2id string)
    before normal verification while still executing a dummy Argon2id verification to
    prevent timing side-channel enumeration.
    """
    candidate_str = candidate if isinstance(candidate, str) else ""

    if (
        not password_hash
        or password_hash == UNUSABLE_PASSWORD_MARKER
        or not password_hash.startswith("$argon2id$")
    ):
        with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
            _ph.verify(_DUMMY_ARGON2_HASH, candidate_str)
        return False, False

    try:
        _ph.verify(password_hash, candidate_str)
        return True, bool(_ph.check_needs_rehash(password_hash))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False


def validate_password_policy(
    password: str | None,
    confirm_password: str | None = None,
    *,
    require_confirmation: bool = True,
) -> str | None:
    """Validate password strength and optional confirmation match.

    Returns an error message string if invalid, or None if valid.
    """
    if not isinstance(password, str) or not password:
        return "Password is required."
    if password == UNUSABLE_PASSWORD_MARKER:
        return "Invalid password."
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 128:
        return "Password must not exceed 128 characters."
    if not password.strip():
        return "Password cannot consist solely of whitespace."
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "Password must contain at least one letter and one number."
    if require_confirmation:
        if not isinstance(confirm_password, str) or not confirm_password:
            return "Password confirmation is required."
        if password != confirm_password:
            return "Password and confirmation password do not match."
    elif confirm_password is not None and password != confirm_password:
        return "Password and confirmation password do not match."
    return None


def normalize_and_validate_email(raw_email: str | None) -> tuple[str | None, str | None]:
    """Normalize email (trim + lowercase) and validate format."""
    if not isinstance(raw_email, str) or not raw_email.strip():
        return None, "Email address is required."
    normalized = raw_email.strip().lower()
    if len(normalized) > 254 or not _EMAIL_RE.match(normalized):
        return None, "Please provide a valid email address."
    return normalized, None


def normalize_and_validate_roll_number(raw_roll: str | None) -> tuple[str | None, str | None]:
    """Normalize roll number (trim + uppercase) and validate format."""
    if not isinstance(raw_roll, str) or not raw_roll.strip():
        return None, "Roll number is required."
    normalized = raw_roll.strip().upper()
    if not _ROLL_NUMBER_RE.match(normalized):
        return (
            None,
            "Roll number must be 3–32 uppercase alphanumeric characters (e.g. 2024CSB1042).",
        )
    return normalized, None


def normalize_and_validate_staff_code(raw_code: str | None) -> tuple[str | None, str | None]:
    """Normalize staff code (trim + uppercase) and validate format."""
    if not isinstance(raw_code, str) or not raw_code.strip():
        return None, "Staff code is required."
    normalized = raw_code.strip().upper()
    if not _STAFF_CODE_RE.match(normalized):
        return (
            None,
            "Staff code must be 3–20 uppercase letters, digits, or hyphens (e.g. STF-0001).",
        )
    return normalized, None


def establish_authenticated_session(user: User) -> str:
    """Create a fresh authenticated cookie session bound to `user.public_id` and version."""
    session.clear()
    csrf_token = secrets.token_urlsafe(32)
    session["user_public_id"] = str(user.public_id)
    session["session_version"] = int(user.session_version)
    session["csrf_token"] = csrf_token
    session.permanent = True
    g.current_user = user
    g.clear_auth_cookies = False
    return csrf_token


def ensure_csrf_token() -> str:
    """Return the current session's CSRF token, generating one if needed."""
    token = session.get("csrf_token")
    if not token or not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def clear_authenticated_session() -> None:
    """Invalidate the current browser session and mark auth cookies for deletion."""
    session.clear()
    g.current_user = None
    g.clear_auth_cookies = True


def init_auth_security(app: Flask) -> None:
    """Register request hooks for session restoration, `session_version` enforcement, and CSRF."""

    @app.before_request
    def _load_authenticated_user() -> None:
        g.current_user = None
        g.session_expired = False
        g.inactive_user = None
        g.clear_auth_cookies = False

        if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
            return

        raw_public_id = session.get("user_public_id")
        sess_version = session.get("session_version")
        if not raw_public_id:
            return

        try:
            pub_uuid = uuid.UUID(str(raw_public_id))
        except (ValueError, TypeError):
            clear_authenticated_session()
            g.session_expired = True
            return

        stmt = (
            select(User)
            .options(joinedload(User.student_profile), joinedload(User.staff_profile))
            .where(User.public_id == pub_uuid)
        )
        user = db.session.execute(stmt).scalar_one_or_none()

        if user is None or int(user.session_version) != int(sess_version or -1):
            clear_authenticated_session()
            g.session_expired = True
            return

        if user.status != "active":
            g.inactive_user = user
            clear_authenticated_session()
            return

        g.current_user = user
        ensure_csrf_token()

    @app.before_request
    def _enforce_origin_and_csrf():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None

        # Payment gateway webhooks do not carry browser sessions or CSRF tokens;
        # they are strictly authenticated via raw-body HMAC signature verification.
        if request.path == "/api/v1/webhooks/razorpay":
            return None

        # Validate Origin header when provided by the client/browser
        origin = request.headers.get("Origin")
        if origin:
            allowed = {item.rstrip("/") for item in current_app.config.get("ALLOWED_ORIGINS", [])}
            allowed.add(request.host_url.rstrip("/"))
            if origin.rstrip("/") not in allowed:
                return error_response(
                    "invalid_origin",
                    "Cross-origin state-changing request is not permitted.",
                    403,
                )

        # Enforce CSRF token on cookie-authenticated state-changing requests
        if (
            current_app.config.get("CSRF_ENABLED", True)
            and getattr(g, "current_user", None) is not None
        ):
            expected_csrf = session.get("csrf_token")
            provided_csrf = request.headers.get("X-CSRF-Token") or request.headers.get(
                "X-XSRF-Token"
            )
            if (
                not expected_csrf
                or not provided_csrf
                or not secrets.compare_digest(str(expected_csrf), str(provided_csrf))
            ):
                return error_response(
                    "csrf_invalid",
                    "Missing or invalid CSRF token for authenticated request.",
                    403,
                )
        return None

    @app.after_request
    def _apply_auth_cookies_and_headers(response):
        if request.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"

        csrf_cookie_name = current_app.config.get("CSRF_COOKIE_NAME", "hc_csrf_token")
        session_cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "hostelcare_session")

        if getattr(g, "clear_auth_cookies", False):
            response.delete_cookie(csrf_cookie_name, path="/")
            response.delete_cookie(session_cookie_name, path="/")
        elif session.get("csrf_token"):
            csrf_val = session["csrf_token"]
            response.headers["X-CSRF-Token"] = csrf_val
            response.set_cookie(
                csrf_cookie_name,
                value=csrf_val,
                httponly=False,
                secure=bool(current_app.config.get("SESSION_COOKIE_SECURE", False)),
                samesite=current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
                path="/",
            )
        return response


def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Require an authenticated, active user session (`status == 'active'`)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        inactive: User | None = getattr(g, "inactive_user", None)
        if inactive is not None:
            if inactive.status == "pending":
                return error_response(
                    "account_pending",
                    (
                        "Your registration is pending warden approval. "
                        "Protected features are unavailable until approved."
                    ),
                    403,
                )
            return error_response(
                f"account_{inactive.status}",
                f"Account is {inactive.status} and cannot access protected resources.",
                403,
            )

        user: User | None = getattr(g, "current_user", None)
        if user is None:
            if getattr(g, "session_expired", False):
                return error_response(
                    "session_expired",
                    "Your session has expired or been revoked. Please sign in again.",
                    401,
                )
            return error_response("unauthenticated", "Authentication is required.", 401)

        if user.status != "active":
            return error_response(
                f"account_{user.status}",
                f"Account is {user.status} and cannot access protected resources.",
                403,
            )

        return fn(*args, **kwargs)

    return wrapper


def require_role(*allowed_roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require an authenticated, active user whose database `role` is in `allowed_roles`."""
    allowed_set = frozenset(allowed_roles)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        @login_required
        def wrapper(*args: Any, **kwargs: Any):
            user: User = g.current_user
            if user.role not in allowed_set:
                return error_response(
                    "forbidden",
                    "You do not have permission to perform this action.",
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
