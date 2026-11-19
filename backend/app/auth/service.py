"""Authentication, identity lifecycle, staff provisioning, and password reset services."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from flask import current_app
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.audit.service import get_client_ip, record_audit_event
from app.auth.security import (
    UNUSABLE_PASSWORD_MARKER,
    clear_authenticated_session,
    establish_authenticated_session,
    hash_password,
    normalize_and_validate_email,
    normalize_and_validate_roll_number,
    normalize_and_validate_staff_code,
    validate_password_policy,
    verify_password_safe,
)
from app.core.mailer import send_password_changed_email, send_password_reset_email
from app.extensions import db
from app.models.audit import AuditLog
from app.models.complaints import Complaint, ComplaintAssignment
from app.models.identity import PasswordResetToken, StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.rooms import Block, Room, RoomAllocation

_IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> date:
    return datetime.now(_IST).date()


def _format_floor_label(floor: int) -> str:
    if floor == 0:
        return "Ground Floor"
    if floor == 1:
        return "1st Floor"
    if floor == 2:
        return "2nd Floor"
    if floor == 3:
        return "3rd Floor"
    return f"{floor}th Floor"


def get_active_student_room_allocation(student_user_id: int) -> RoomAllocation | None:
    """Return the student's active-today `RoomAllocation` (with `Room` and `Block` loaded)."""
    stmt = (
        select(RoomAllocation)
        .options(joinedload(RoomAllocation.room).joinedload(Room.block))
        .where(
            RoomAllocation.student_user_id == student_user_id,
            RoomAllocation.start_date <= func.current_date(),
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > func.current_date()),
        )
        .order_by(RoomAllocation.start_date.desc(), RoomAllocation.id.desc())
        .limit(1)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def _get_active_roommates(room_id: int, exclude_student_user_id: int) -> list[RoomAllocation]:
    """Return active-today `RoomAllocation` rows for co-residents in `room_id`."""
    stmt = (
        select(RoomAllocation)
        .options(joinedload(RoomAllocation.student).joinedload(StudentProfile.user))
        .where(
            RoomAllocation.room_id == room_id,
            RoomAllocation.student_user_id != exclude_student_user_id,
            RoomAllocation.start_date <= func.current_date(),
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > func.current_date()),
        )
        .order_by(RoomAllocation.bed_number.asc(), RoomAllocation.id.asc())
    )
    return list(db.session.execute(stmt).scalars().all())


class AuthServiceError(Exception):
    """Domain exception carrying an API error code, message, and HTTP status."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Safe Serializers (never expose password_hash, token_hash, or internal secrets)
# ---------------------------------------------------------------------------


def serialize_user(user: User) -> dict[str, Any]:
    """Serialize a `User` and its role-specific profile into a safe API dictionary."""
    join_date_str = (
        user.created_at.astimezone(UTC).strftime("%d/%m/%Y") if user.created_at else "14/11/2026"
    )
    payload: dict[str, Any] = {
        "id": str(user.public_id),
        "public_id": str(user.public_id),
        "email": user.email,
        "full_name": user.full_name,
        "fullName": user.full_name,
        "name": user.full_name,
        "phone": user.phone,
        "designation": user.designation,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "joinDate": join_date_str,
    }

    if user.role == "student" and user.student_profile is not None:
        sp = user.student_profile
        alloc = get_active_student_room_allocation(user.id) if user.id is not None else None
        payload["roll_number"] = sp.roll_number
        payload["rollNumber"] = sp.roll_number
        if alloc is not None and alloc.room is not None:
            rm = alloc.room
            blk = rm.block
            co_allocs = _get_active_roommates(rm.id, user.id) if user.id is not None else []
            roommates_payload = [
                {
                    "id": str(c.student.user.public_id),
                    "fullName": c.student.user.full_name,
                    "rollNumber": c.student.roll_number,
                    "bed": f"Bed {c.bed_number}",
                    "phone": c.student.user.phone,
                }
                for c in co_allocs
                if c.student is not None and c.student.user is not None
            ]
            first_roommate = roommates_payload[0] if roommates_payload else None
            payload["room"] = rm.room_number
            payload["roomId"] = rm.id
            payload["block"] = blk.name if blk else "Hostel"
            payload["blockCode"] = blk.code if blk else None
            payload["blockId"] = rm.block_id
            payload["floor"] = _format_floor_label(int(rm.floor))
            payload["bed"] = f"Bed {alloc.bed_number}"
            payload["allocationStartDate"] = (
                alloc.start_date.strftime("%d/%m/%Y") if alloc.start_date else None
            )
            payload["roommate"] = (
                first_roommate["fullName"] if first_roommate else "No Roommate Assigned"
            )
            payload["roommateRoll"] = first_roommate["rollNumber"] if first_roommate else None
            payload["roommateBed"] = first_roommate["bed"] if first_roommate else None
            payload["roommatePhone"] = first_roommate["phone"] if first_roommate else None
            payload["roommates"] = roommates_payload
            payload["hasActiveRoom"] = True
        else:
            payload["room"] = "Unassigned"
            payload["roomId"] = None
            payload["block"] = "Not Assigned"
            payload["blockCode"] = None
            payload["blockId"] = None
            payload["floor"] = "Not Assigned"
            payload["bed"] = "Not Assigned"
            payload["allocationStartDate"] = None
            payload["roommate"] = "No Roommate Assigned"
            payload["roommateRoll"] = None
            payload["roommateBed"] = None
            payload["roommatePhone"] = None
            payload["roommates"] = []
            payload["hasActiveRoom"] = False
        payload["avatarColor"] = "bg-[#D94378]"
        payload["student_profile"] = {
            "roll_number": sp.roll_number,
            "requested_room_id": sp.requested_room_id,
            "reviewed_at": sp.reviewed_at.isoformat() if sp.reviewed_at else None,
            "review_note": sp.review_note,
        }
    elif user.role == "staff" and user.staff_profile is not None:
        stp = user.staff_profile
        payload["staff_code"] = stp.staff_code
        payload["staffCode"] = stp.staff_code
        payload["trade"] = stp.trade
        payload["shift"] = stp.shift or "General (09:00 AM - 05:30 PM)"
        payload["staff_profile"] = {
            "staff_code": stp.staff_code,
            "trade": stp.trade,
            "shift": stp.shift,
        }

    return payload


def serialize_student_record(user: User) -> dict[str, Any]:
    """Serialize a student user + profile for admin student/approval endpoints."""
    data = serialize_user(user)
    sp = user.student_profile
    if sp is not None:
        data["review_note"] = sp.review_note
        data["reviewed_at"] = sp.reviewed_at.isoformat() if sp.reviewed_at else None
    return data


def serialize_staff_record(user: User) -> dict[str, Any]:
    """Serialize a staff user + profile for admin staff management endpoints."""
    data = serialize_user(user)
    data["display_status"] = "Active" if user.status == "active" else "Inactive"
    active_count = 0
    if user.id is not None:
        stmt = (
            select(func.count())
            .select_from(ComplaintAssignment)
            .join(Complaint, Complaint.id == ComplaintAssignment.complaint_id)
            .where(
                ComplaintAssignment.staff_user_id == user.id,
                ComplaintAssignment.ended_at.is_(None),
                Complaint.status.in_(("assigned", "accepted", "in_progress")),
            )
        )
        active_count = int(db.session.execute(stmt).scalar_one() or 0)
    data["activeTickets"] = active_count
    return data


def serialize_audit_log(log: AuditLog) -> dict[str, Any]:
    """Serialize an `AuditLog` entry for the admin audit log viewer."""
    ts_str = (
        log.occurred_at.astimezone(UTC).strftime("%d/%m/%Y, %H:%M UTC") if log.occurred_at else ""
    )
    actor_label = "System / Anonymous"
    if log.actor is not None:
        actor_label = f"{log.actor.full_name} ({log.actor_role or log.actor.role})"
    elif log.actor_role:
        actor_label = log.actor_role

    target_label = (
        f"{log.target_type}:{log.target_id}" if log.target_type and log.target_id else "-"
    )
    meta = log.metadata_json or {}
    details_parts = [f"{k}={v}" for k, v in meta.items() if v is not None and v != ""]
    details_str = ", ".join(details_parts) if details_parts else log.action

    return {
        "id": f"AUD-{log.id:04d}",
        "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        "timestamp": ts_str,
        "actor_user_id": str(log.actor.public_id) if log.actor else None,
        "actor_role": log.actor_role,
        "actor": actor_label,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "target": target_label,
        "metadata": meta,
        "details": details_str,
        "request_id": log.request_id,
    }


# ---------------------------------------------------------------------------
# Lookup Helpers
# ---------------------------------------------------------------------------


def _resolve_user_by_identifier(
    identifier: str,
    *,
    expected_role: str | None = None,
    for_update: bool = False,
) -> User | None:
    """Resolve a user by UUID `public_id`, integer `id`, `roll_number`, or `staff_code`."""
    raw = str(identifier or "").strip()
    if not raw:
        return None

    stmt = select(User)
    if not for_update:
        stmt = stmt.options(joinedload(User.student_profile), joinedload(User.staff_profile))

    # 1. Try UUID public_id
    try:
        pub_uuid = uuid.UUID(raw)
        q = stmt.where(User.public_id == pub_uuid)
        if expected_role:
            q = q.where(User.role == expected_role)
        if for_update:
            q = q.with_for_update(of=User)
        user = db.session.execute(q).scalar_one_or_none()
        if user is not None:
            return user
    except (ValueError, TypeError):
        pass

    # 2. Try integer ID
    if raw.isdigit():
        q = stmt.where(User.id == int(raw))
        if expected_role:
            q = q.where(User.role == expected_role)
        if for_update:
            q = q.with_for_update(of=User)
        user = db.session.execute(q).scalar_one_or_none()
        if user is not None:
            return user

    # 3. Try roll_number (for students) or staff_code (for staff)
    if expected_role in (None, "student"):
        sp = db.session.execute(
            select(StudentProfile).where(StudentProfile.roll_number == raw.upper())
        ).scalar_one_or_none()
        if sp is not None:
            q = stmt.where(User.id == sp.user_id)
            if for_update:
                q = q.with_for_update(of=User)
            return db.session.execute(q).scalar_one_or_none()

    if expected_role in (None, "staff"):
        stp = db.session.execute(
            select(StaffProfile).where(StaffProfile.staff_code == raw.upper())
        ).scalar_one_or_none()
        if stp is not None:
            q = stmt.where(User.id == stp.user_id)
            if for_update:
                q = q.with_for_update(of=User)
            return db.session.execute(q).scalar_one_or_none()

    return None


# ---------------------------------------------------------------------------
# Database-Backed Rate Limiting (ADR-017, U1)
# ---------------------------------------------------------------------------


def _count_audit_events_for_ip(action: str, ip_address: str | None, window: timedelta) -> int:
    if not ip_address:
        return 0
    cutoff = datetime.now(UTC) - window
    stmt = (
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == action,
            AuditLog.ip_address == ip_address,
            AuditLog.occurred_at >= cutoff,
        )
    )
    return int(db.session.execute(stmt).scalar_one() or 0)


def _count_reset_tokens_for_user(user_id: int, window: timedelta) -> int:
    cutoff = datetime.now(UTC) - window
    stmt = (
        select(func.count())
        .select_from(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.created_at >= cutoff,
        )
    )
    return int(db.session.execute(stmt).scalar_one() or 0)


# ---------------------------------------------------------------------------
# 1. Student Registration & Approval Workflow
# ---------------------------------------------------------------------------


def register_student(data: dict[str, Any]) -> User:
    """Self-register a new student account (`role='student'`, `status='pending'`)."""
    # Prevent privilege escalation via submitted role or status fields
    if "role" in data and str(data["role"]).strip().lower() != "student":
        raise AuthServiceError(
            "forbidden_field",
            "Self-registration is restricted to student accounts only.",
            403,
        )
    if "status" in data and str(data["status"]).strip().lower() != "pending":
        raise AuthServiceError(
            "forbidden_field",
            "Approval status cannot be set during registration.",
            403,
        )

    client_ip = get_client_ip()
    ip_limit = int(current_app.config.get("AUTH_REGISTER_IP_LIMIT_1H", 15))
    if _count_audit_events_for_ip("student.registered", client_ip, timedelta(hours=1)) >= ip_limit:
        raise AuthServiceError(
            "rate_limited",
            "Too many registration attempts from this network. Please try again later.",
            429,
        )

    full_name = str(data.get("fullName") or data.get("full_name") or "").strip()
    if not full_name or len(full_name) > 120:
        raise AuthServiceError(
            "validation_error",
            "Full name is required and must not exceed 120 characters.",
            400,
        )

    raw_email = data.get("email")
    email, email_err = normalize_and_validate_email(raw_email)
    if email_err or not email:
        raise AuthServiceError("validation_error", email_err or "Invalid email.", 400)

    raw_roll = data.get("rollNumber") or data.get("roll_number")
    roll_number, roll_err = normalize_and_validate_roll_number(raw_roll)
    if roll_err or not roll_number:
        raise AuthServiceError("validation_error", roll_err or "Invalid roll number.", 400)

    phone_raw = str(data.get("phone") or data.get("phone_number") or "").strip()
    if not phone_raw or len(phone_raw) > 20:
        raise AuthServiceError(
            "validation_error",
            "A valid phone number (up to 20 characters) is required.",
            400,
        )

    password = data.get("password")
    confirm_password = (
        data.get("confirmPassword") if "confirmPassword" in data else data.get("confirm_password")
    )
    pw_err = validate_password_policy(
        password,
        confirm_password,
        require_confirmation=True,
    )
    if pw_err:
        raise AuthServiceError("validation_error", pw_err, 400)

    # Check existing email or roll number without revealing which matched
    existing_email = db.session.execute(
        select(User.id).where(User.email == email)
    ).scalar_one_or_none()
    existing_roll = db.session.execute(
        select(StudentProfile.user_id).where(StudentProfile.roll_number == roll_number)
    ).scalar_one_or_none()
    if existing_email is not None or existing_roll is not None:
        raise AuthServiceError(
            "registration_conflict",
            (
                "Unable to complete registration with the provided details. "
                "If you already registered, please sign in or contact the warden office."
            ),
            409,
        )

    pw_hash = hash_password(str(password))

    try:
        user = User(
            email=email,
            full_name=full_name,
            phone=phone_raw,
            password_hash=pw_hash,
            role="student",
            status="pending",
        )
        db.session.add(user)
        db.session.flush()

        profile = StudentProfile(
            user_id=user.id,
            role="student",
            roll_number=roll_number,
        )
        db.session.add(profile)
        db.session.flush()

        record_audit_event(
            action="student.registered",
            actor=user,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"roll_number": roll_number},
        )
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise AuthServiceError(
            "registration_conflict",
            (
                "Unable to complete registration with the provided details. "
                "If you already registered, please sign in or contact the warden office."
            ),
            409,
        ) from exc

    db.session.refresh(user)
    return user


def list_students(*, status_filter: str | None = None) -> list[User]:
    """List student accounts with their `StudentProfile`, optionally filtered by status."""
    stmt = (
        select(User)
        .options(joinedload(User.student_profile))
        .where(User.role == "student")
        .order_by(User.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(User.status == status_filter.strip().lower())
    return list(db.session.execute(stmt).scalars().all())


def approve_student(*, student_identifier: str, admin_user: User, note: str | None = None) -> User:
    """Transition a pending student registration to `active` (`pending -> active`)."""
    student = _resolve_user_by_identifier(
        student_identifier, expected_role="student", for_update=True
    )
    if student is None or student.student_profile is None:
        raise AuthServiceError("not_found", "Student account not found.", 404)

    if student.status != "pending":
        raise AuthServiceError(
            "invalid_state_transition",
            f"Only pending student accounts can be approved (current status: {student.status}).",
            409,
        )

    now = datetime.now(UTC)
    clean_note = note.strip() if isinstance(note, str) and note.strip() else None

    student.status = "active"
    student.updated_at = now
    student.student_profile.reviewed_by = admin_user.id
    student.student_profile.reviewed_at = now
    student.student_profile.review_note = clean_note
    student.student_profile.updated_at = now

    notif = Notification(
        recipient_user_id=student.id,
        category="registration",
        event_type="account_approved",
        title="Hostel Registration Approved",
        message="Your student registration has been verified and approved by the Warden Office.",
        entity_type="student",
        entity_ref=student.student_profile.roll_number,
    )
    db.session.add(notif)

    record_audit_event(
        action="student.approved",
        actor=admin_user,
        target_type="user",
        target_id=str(student.public_id),
        metadata={
            "roll_number": student.student_profile.roll_number,
            "from_status": "pending",
            "to_status": "active",
            "note": clean_note,
        },
    )
    db.session.commit()
    return student


def reject_student(*, student_identifier: str, admin_user: User, reason: str | None) -> User:
    """Reject a pending student registration (`pending -> rejected`) with a mandatory reason."""
    clean_reason = reason.strip() if isinstance(reason, str) else ""
    if not clean_reason:
        raise AuthServiceError(
            "validation_error",
            "A rejection reason is required when rejecting a student registration.",
            400,
        )

    student = _resolve_user_by_identifier(
        student_identifier, expected_role="student", for_update=True
    )
    if student is None or student.student_profile is None:
        raise AuthServiceError("not_found", "Student account not found.", 404)

    if student.status != "pending":
        raise AuthServiceError(
            "invalid_state_transition",
            f"Only pending student accounts can be rejected (current status: {student.status}).",
            409,
        )

    now = datetime.now(UTC)
    student.status = "rejected"
    student.session_version = int(student.session_version) + 1
    student.updated_at = now
    student.student_profile.reviewed_by = admin_user.id
    student.student_profile.reviewed_at = now
    student.student_profile.review_note = clean_reason
    student.student_profile.updated_at = now

    notif = Notification(
        recipient_user_id=student.id,
        category="registration",
        event_type="account_rejected",
        title="Hostel Registration Not Approved",
        message=f"Your registration was not approved. Reason: {clean_reason[:800]}",
        entity_type="student",
        entity_ref=student.student_profile.roll_number,
    )
    db.session.add(notif)

    record_audit_event(
        action="student.rejected",
        actor=admin_user,
        target_type="user",
        target_id=str(student.public_id),
        metadata={
            "roll_number": student.student_profile.roll_number,
            "from_status": "pending",
            "to_status": "rejected",
            "reason": clean_reason,
        },
    )
    db.session.commit()
    return student


def reactivate_student(*, student_identifier: str, admin_user: User, reason: str | None) -> User:
    """Reactivate a rejected student (`rejected -> pending`) on the existing row (ADR-021)."""
    clean_reason = reason.strip() if isinstance(reason, str) else ""
    if not clean_reason:
        raise AuthServiceError(
            "validation_error",
            "A reason is required to reactivate a rejected student registration.",
            400,
        )

    student = _resolve_user_by_identifier(
        student_identifier, expected_role="student", for_update=True
    )
    if student is None or student.student_profile is None:
        raise AuthServiceError("not_found", "Student account not found.", 404)

    if student.status != "rejected":
        raise AuthServiceError(
            "invalid_state_transition",
            (
                f"Only rejected student accounts can be reactivated to pending "
                f"(current status: {student.status})."
            ),
            409,
        )

    now = datetime.now(UTC)
    student.status = "pending"
    student.updated_at = now
    student.student_profile.reviewed_by = admin_user.id
    student.student_profile.reviewed_at = now
    student.student_profile.review_note = clean_reason
    student.student_profile.updated_at = now

    notif = Notification(
        recipient_user_id=student.id,
        category="registration",
        event_type="account_reactivated",
        title="Hostel Registration Reactivated for Review",
        message=(
            f"Your registration has been reactivated for warden review. Note: {clean_reason[:800]}"
        ),
        entity_type="student",
        entity_ref=student.student_profile.roll_number,
    )
    db.session.add(notif)

    record_audit_event(
        action="student.reactivated",
        actor=admin_user,
        target_type="user",
        target_id=str(student.public_id),
        metadata={
            "roll_number": student.student_profile.roll_number,
            "from_status": "rejected",
            "to_status": "pending",
            "reason": clean_reason,
        },
    )
    db.session.commit()
    return student


# ---------------------------------------------------------------------------
# 2. Login & Logout Services
# ---------------------------------------------------------------------------


def _normalize_role(role_raw: str | None) -> str:
    """Normalize user-facing or API role strings to canonical internal roles.

    Supported roles: 'student', 'staff', 'admin'.
    """
    if not role_raw:
        return ""
    norm = str(role_raw).strip().lower()
    if norm in ("admin", "warden", "warden/admin", "warden / admin", "warden_admin"):
        return "admin"
    if norm in ("student", "resident"):
        return "student"
    if norm in ("staff", "duty staff", "duty_staff", "technician"):
        return "staff"
    return norm


def login_user(data: dict[str, Any]) -> tuple[User, str]:
    """Authenticate a user by email (or student roll number) and password."""
    client_ip = get_client_ip()
    ip_limit = int(current_app.config.get("AUTH_LOGIN_IP_LIMIT_15M", 15))
    if (
        _count_audit_events_for_ip("auth.login_failed", client_ip, timedelta(minutes=15))
        >= ip_limit
    ):
        raise AuthServiceError(
            "rate_limited",
            "Too many failed sign-in attempts from this network. Please wait 15 minutes.",
            429,
        )

    raw_identifier = str(data.get("email") or data.get("identifier") or "").strip()
    raw_password = data.get("password")
    if not raw_identifier or not isinstance(raw_password, str) or not raw_password:
        raise AuthServiceError("validation_error", "Email and password are required.", 400)

    # Look up by normalized email first, or by student roll number if not an email
    user: User | None = None
    if "@" in raw_identifier:
        user = db.session.execute(
            select(User)
            .options(joinedload(User.student_profile), joinedload(User.staff_profile))
            .where(User.email == raw_identifier.lower())
        ).scalar_one_or_none()
    else:
        sp = db.session.execute(
            select(StudentProfile).where(StudentProfile.roll_number == raw_identifier.upper())
        ).scalar_one_or_none()
        if sp is not None:
            user = db.session.execute(
                select(User)
                .options(joinedload(User.student_profile), joinedload(User.staff_profile))
                .where(User.id == sp.user_id)
            ).scalar_one_or_none()

    now = datetime.now(UTC)

    # Unknown account -> run constant-time dummy Argon2id verification
    if user is None:
        verify_password_safe(None, raw_password)
        record_audit_event(
            action="auth.login_failed",
            actor_user_id=None,
            actor_role=None,
            metadata={"reason": "unknown_account"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        raise AuthServiceError("invalid_credentials", "Invalid email or password.", 401)

    # Temporary account lockout check
    if user.locked_until is not None and user.locked_until > now:
        verify_password_safe(None, raw_password)
        record_audit_event(
            action="auth.login_failed",
            actor_user_id=None,
            actor_role=None,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"reason": "account_locked"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        raise AuthServiceError(
            "account_locked",
            (
                "This account is temporarily locked due to repeated failed sign-in attempts. "
                "Please try again later or reset your password."
            ),
            429,
        )

    # Explicitly reject the unusable password marker '!' before normal Argon2 verification
    if user.password_hash == UNUSABLE_PASSWORD_MARKER or not user.password_hash.startswith(
        "$argon2id$"
    ):
        verify_password_safe(UNUSABLE_PASSWORD_MARKER, raw_password)
        record_audit_event(
            action="auth.login_failed",
            actor_user_id=None,
            actor_role=None,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"reason": "unusable_password_marker"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        raise AuthServiceError("invalid_credentials", "Invalid email or password.", 401)

    is_valid, needs_rehash = verify_password_safe(user.password_hash, raw_password)
    if not is_valid:
        max_failures = int(current_app.config.get("AUTH_MAX_FAILED_LOGINS", 5))
        lockout_mins = int(current_app.config.get("AUTH_LOCKOUT_MINUTES", 15))
        user.failed_login_count = int(user.failed_login_count) + 1
        user.updated_at = now
        if user.failed_login_count >= max_failures:
            user.locked_until = now + timedelta(minutes=lockout_mins)
            record_audit_event(
                action="auth.login_locked",
                actor_user_id=None,
                actor_role=None,
                target_type="user",
                target_id=str(user.public_id),
                metadata={"failed_login_count": user.failed_login_count},
                ip_address=client_ip,
            )
        record_audit_event(
            action="auth.login_failed",
            actor_user_id=None,
            actor_role=None,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"reason": "bad_password"},
            ip_address=client_ip,
        )
        db.session.commit()
        raise AuthServiceError("invalid_credentials", "Invalid email or password.", 401)

    # Password is valid -> enforce account lifecycle status before creating any session
    if user.status != "active":
        record_audit_event(
            action="auth.login_failed",
            actor_user_id=user.id,
            actor_role=user.role,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"reason": f"status_{user.status}"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        if user.status == "pending":
            raise AuthServiceError(
                "account_pending",
                (
                    "Your registration is pending warden approval. "
                    "Please check back after verification."
                ),
                403,
            )
        if user.status == "rejected":
            raise AuthServiceError(
                "account_rejected",
                "Your registration was not approved. Please contact the hostel warden office.",
                403,
            )
        if user.status == "suspended":
            raise AuthServiceError(
                "account_suspended",
                "Your account is currently suspended. Please contact the hostel administration.",
                403,
            )
        raise AuthServiceError(
            "account_deactivated",
            "This account has been deactivated and cannot sign in.",
            403,
        )

    # Enforce requested role selection (Part B)
    raw_role = data.get("role") or data.get("selected_role") or data.get("portal_role")
    if raw_role is not None and str(raw_role).strip() != "":
        requested_role = _normalize_role(str(raw_role))
        if requested_role != user.role:
            record_audit_event(
                action="auth.login_failed",
                actor_user_id=user.id,
                actor_role=user.role,
                target_type="user",
                target_id=str(user.public_id),
                metadata={
                    "reason": "role_mismatch",
                    "requested_role": requested_role,
                    "actual_role": user.role,
                },
                ip_address=client_ip,
                commit_immediately=True,
            )
            raise AuthServiceError(
                "role_mismatch",
                (
                    "The selected role does not match this account's credentials. "
                    "Please select the correct portal."
                ),
                403,
            )

    # Successful login for an active account
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.updated_at = now
    if needs_rehash:
        user.password_hash = hash_password(raw_password)

    record_audit_event(
        action="auth.login_succeeded",
        actor=user,
        target_type="user",
        target_id=str(user.public_id),
        metadata={"role": user.role},
        ip_address=client_ip,
    )
    db.session.commit()

    csrf_token = establish_authenticated_session(user)
    return user, csrf_token


def logout_user(current_user: User | None) -> None:
    """Invalidate the current session and record an audit event if authenticated."""
    if current_user is not None:
        record_audit_event(
            action="auth.logout",
            actor=current_user,
            target_type="user",
            target_id=str(current_user.public_id),
            metadata={"role": current_user.role},
            commit_immediately=True,
        )
    clear_authenticated_session()


# ---------------------------------------------------------------------------
# 3. Password Reset & Initial Account Setup (ADR-017)
# ---------------------------------------------------------------------------


def _issue_reset_token_for_user(
    *,
    user: User,
    requested_by_admin: User | None,
    client_ip: str | None,
) -> str:
    """Revoke any open token for `user`, insert a 30-min SHA-256 token, and return raw token."""
    now = datetime.now(UTC)
    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        requested_by=requested_by_admin.id if requested_by_admin is not None else None,
        created_at=now,
        expires_at=now + timedelta(minutes=30),
        request_ip=client_ip,
    )
    db.session.add(token_row)
    return raw_token


def request_password_reset(raw_email: str | None) -> None:
    """Self-service password reset request (`POST /api/v1/auth/forgot-password`).

    Always completes neutrally without revealing whether the account exists.
    Enforces per-IP (10/hr) and per-user (3/hr) rate limits.
    """
    client_ip = get_client_ip()
    ip_limit = int(current_app.config.get("AUTH_RESET_IP_LIMIT_1H", 10))
    ip_count = _count_audit_events_for_ip("auth.reset_requested", client_ip, timedelta(hours=1))
    if ip_count >= ip_limit:
        # Per Section 3.4 of database-design.md: when IP is over limit, do not write more audit rows
        raise AuthServiceError(
            "rate_limited",
            "Too many password reset requests from this network. Please try again later.",
            429,
        )

    email, email_err = normalize_and_validate_email(raw_email)
    if email_err or not email:
        # Still record request attempt and return neutrally
        record_audit_event(
            action="auth.reset_requested",
            actor_user_id=None,
            actor_role=None,
            metadata={"outcome": "invalid_email_format"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        return

    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None or user.status != "active":
        record_audit_event(
            action="auth.reset_requested",
            actor_user_id=None,
            actor_role=None,
            metadata={"outcome": "ignored"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        return

    user_limit = int(current_app.config.get("AUTH_RESET_USER_LIMIT_1H", 3))
    if _count_reset_tokens_for_user(user.id, timedelta(hours=1)) >= user_limit:
        record_audit_event(
            action="auth.reset_requested",
            actor_user_id=None,
            actor_role=None,
            target_type="user",
            target_id=str(user.public_id),
            metadata={"outcome": "user_rate_limited"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        return

    raw_token = _issue_reset_token_for_user(
        user=user,
        requested_by_admin=None,
        client_ip=client_ip,
    )
    record_audit_event(
        action="auth.reset_requested",
        actor_user_id=user.id,
        actor_role=user.role,
        target_type="user",
        target_id=str(user.public_id),
        metadata={"outcome": "issued"},
        ip_address=client_ip,
    )
    db.session.commit()

    send_password_reset_email(
        to_email=user.email,
        full_name=user.full_name,
        raw_token=raw_token,
        is_setup=(user.password_hash == UNUSABLE_PASSWORD_MARKER),
    )


def admin_trigger_password_reset(*, target_user_identifier: str, admin_user: User) -> User:
    """Admin-initiated password reset (`POST /api/v1/admin/users/{id}/send-password-reset`)."""
    target_user = _resolve_user_by_identifier(target_user_identifier, for_update=True)
    if target_user is None:
        raise AuthServiceError("not_found", "User account not found.", 404)

    if target_user.status != "active":
        raise AuthServiceError(
            "invalid_state",
            f"Cannot send password reset to a {target_user.status} account.",
            409,
        )

    client_ip = get_client_ip()
    raw_token = _issue_reset_token_for_user(
        user=target_user,
        requested_by_admin=admin_user,
        client_ip=client_ip,
    )
    record_audit_event(
        action="auth.reset_triggered",
        actor=admin_user,
        target_type="user",
        target_id=str(target_user.public_id),
        metadata={"target_role": target_user.role},
        ip_address=client_ip,
    )
    db.session.commit()

    send_password_reset_email(
        to_email=target_user.email,
        full_name=target_user.full_name,
        raw_token=raw_token,
        is_setup=(target_user.password_hash == UNUSABLE_PASSWORD_MARKER),
    )
    return target_user


def redeem_password_reset(data: dict[str, Any]) -> User:
    """Redeem a single-use 30-minute reset token (`POST /api/v1/auth/reset-password`)."""
    client_ip = get_client_ip()
    invalid_limit = int(current_app.config.get("AUTH_RESET_INVALID_IP_LIMIT_15M", 10))
    if (
        _count_audit_events_for_ip("auth.reset_invalid", client_ip, timedelta(minutes=15))
        >= invalid_limit
    ):
        raise AuthServiceError(
            "rate_limited",
            "Too many invalid password reset attempts. Please wait 15 minutes.",
            429,
        )

    raw_token = str(data.get("token") or "").strip().strip("\"'")
    if not raw_token:
        raise AuthServiceError("validation_error", "Reset token is required.", 400)

    password = data.get("password")
    confirm_password = (
        data.get("confirmPassword") if "confirmPassword" in data else data.get("confirm_password")
    )
    pw_err = validate_password_policy(
        password,
        confirm_password,
        require_confirmation=(confirm_password is not None),
    )
    if pw_err:
        raise AuthServiceError("validation_error", pw_err, 400)

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)

    # Atomic single-use token redemption via conditional UPDATE ... RETURNING
    redeem_row = db.session.execute(
        text(
            "UPDATE public.password_reset_tokens "
            "SET used_at = :now "
            "WHERE token_hash = :th "
            "  AND used_at IS NULL "
            "  AND revoked_at IS NULL "
            "  AND expires_at > :now "
            "RETURNING id, user_id"
        ),
        {"now": now, "th": token_hash},
    ).fetchone()

    if redeem_row is None:
        record_audit_event(
            action="auth.reset_invalid",
            actor_user_id=None,
            actor_role=None,
            metadata={"reason": "invalid_expired_or_used"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        raise AuthServiceError(
            "invalid_or_expired_token",
            "This password reset link is invalid, expired, or has already been used.",
            400,
        )

    redeemed_token_id, user_id = int(redeem_row[0]), int(redeem_row[1])
    user = db.session.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()

    if user is None or user.status != "active":
        db.session.rollback()
        record_audit_event(
            action="auth.reset_invalid",
            actor_user_id=None,
            actor_role=None,
            metadata={"reason": "inactive_user"},
            ip_address=client_ip,
            commit_immediately=True,
        )
        raise AuthServiceError(
            "invalid_or_expired_token",
            "This password reset link is invalid, expired, or has already been used.",
            400,
        )

    user.password_hash = hash_password(str(password))
    user.password_changed_at = now
    user.session_version = int(user.session_version) + 1
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = now

    # Revoke any other live tokens for this user
    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != redeemed_token_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    record_audit_event(
        action="auth.reset_redeemed",
        actor=user,
        target_type="user",
        target_id=str(user.public_id),
        metadata={"session_version": user.session_version},
        ip_address=client_ip,
    )
    db.session.commit()

    clear_authenticated_session()
    send_password_changed_email(to_email=user.email, full_name=user.full_name)
    return user


# ---------------------------------------------------------------------------
# 4. Admin-Created Staff Accounts (Section 5)
# ---------------------------------------------------------------------------


def _generate_next_staff_code() -> str:
    """Generate a unique valid `STF-XXXX` code when not explicitly provided."""
    count = int(
        db.session.execute(select(func.count()).select_from(StaffProfile)).scalar_one() or 0
    )
    for offset in range(1, 1000):
        candidate = f"STF-{count + offset:04d}"
        exists = db.session.execute(
            select(StaffProfile.user_id).where(StaffProfile.staff_code == candidate)
        ).scalar_one_or_none()
        if exists is None:
            return candidate
    return f"STF-{secrets.randbelow(900000) + 100000}"


def create_staff_account(*, data: dict[str, Any], admin_user: User) -> User:
    """Admin creates a staff account with `password_hash='!'` and triggers a password setup link."""
    if "role" in data and str(data["role"]).strip().lower() != "staff":
        raise AuthServiceError(
            "forbidden_field",
            "Staff creation endpoint can only create accounts with role 'staff'.",
            400,
        )

    full_name = str(data.get("fullName") or data.get("full_name") or data.get("name") or "").strip()
    if not full_name or len(full_name) > 120:
        raise AuthServiceError(
            "validation_error",
            "Staff full name is required and must not exceed 120 characters.",
            400,
        )

    email, email_err = normalize_and_validate_email(data.get("email"))
    if email_err or not email:
        raise AuthServiceError("validation_error", email_err or "Valid email is required.", 400)

    phone = str(data.get("phone") or "").strip() or None
    if phone and len(phone) > 20:
        raise AuthServiceError(
            "validation_error", "Phone number must not exceed 20 characters.", 400
        )

    trade = str(data.get("trade") or "").strip()
    if not trade or len(trade) > 60:
        raise AuthServiceError(
            "validation_error",
            "Staff trade/specialization is required and must not exceed 60 characters.",
            400,
        )

    designation = str(data.get("designation") or "").strip() or None
    if designation and len(designation) > 80:
        raise AuthServiceError(
            "validation_error", "Designation must not exceed 80 characters.", 400
        )

    shift = str(data.get("shift") or "").strip() or "General (09:00 AM - 05:30 PM)"
    if len(shift) > 60:
        raise AuthServiceError("validation_error", "Shift must not exceed 60 characters.", 400)

    raw_staff_code = data.get("staffCode") or data.get("staff_code")
    if raw_staff_code:
        staff_code, code_err = normalize_and_validate_staff_code(str(raw_staff_code))
        if code_err or not staff_code:
            raise AuthServiceError("validation_error", code_err or "Invalid staff code.", 400)
    else:
        staff_code = _generate_next_staff_code()

    # Check uniqueness
    existing_email = db.session.execute(
        select(User.id).where(User.email == email)
    ).scalar_one_or_none()
    if existing_email is not None:
        raise AuthServiceError(
            "conflict",
            "An account with this email address already exists.",
            409,
        )
    existing_code = db.session.execute(
        select(StaffProfile.user_id).where(StaffProfile.staff_code == staff_code)
    ).scalar_one_or_none()
    if existing_code is not None:
        raise AuthServiceError(
            "conflict",
            f"A staff profile with code '{staff_code}' already exists.",
            409,
        )

    client_ip = get_client_ip()
    try:
        staff_user = User(
            email=email,
            full_name=full_name,
            phone=phone,
            designation=designation,
            password_hash=UNUSABLE_PASSWORD_MARKER,
            role="staff",
            status="active",
            created_by=admin_user.id,
        )
        db.session.add(staff_user)
        db.session.flush()

        staff_profile = StaffProfile(
            user_id=staff_user.id,
            role="staff",
            staff_code=staff_code,
            trade=trade,
            shift=shift,
        )
        db.session.add(staff_profile)
        db.session.flush()

        raw_token = _issue_reset_token_for_user(
            user=staff_user,
            requested_by_admin=admin_user,
            client_ip=client_ip,
        )

        record_audit_event(
            action="staff.created",
            actor=admin_user,
            target_type="user",
            target_id=str(staff_user.public_id),
            metadata={"staff_code": staff_code, "trade": trade},
            ip_address=client_ip,
        )
        record_audit_event(
            action="auth.reset_triggered",
            actor=admin_user,
            target_type="user",
            target_id=str(staff_user.public_id),
            metadata={"purpose": "initial_staff_setup", "staff_code": staff_code},
            ip_address=client_ip,
        )
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise AuthServiceError(
            "conflict",
            "A staff account with the given email or staff code already exists.",
            409,
        ) from exc

    send_password_reset_email(
        to_email=staff_user.email,
        full_name=staff_user.full_name,
        raw_token=raw_token,
        is_setup=True,
    )
    db.session.refresh(staff_user)
    return staff_user


def list_staff_accounts() -> list[User]:
    """Return all staff accounts ordered by creation date descending."""
    stmt = (
        select(User)
        .options(joinedload(User.staff_profile))
        .where(User.role == "staff")
        .order_by(User.created_at.desc())
    )
    return list(db.session.execute(stmt).scalars().all())


def get_staff_account(staff_identifier: str) -> User:
    """Return a single staff account by `public_id`, `staff_code`, or `id`."""
    user = _resolve_user_by_identifier(staff_identifier, expected_role="staff")
    if user is None or user.staff_profile is None:
        raise AuthServiceError("not_found", "Staff account not found.", 404)
    return user


def update_staff_account(*, staff_identifier: str, data: dict[str, Any], admin_user: User) -> User:
    """Update mutable staff account and profile attributes (Admin only). Never alters `role`."""
    if "role" in data and str(data["role"]).strip().lower() != "staff":
        raise AuthServiceError(
            "forbidden_field",
            "Role escalation or modification is strictly prohibited.",
            403,
        )

    staff_user = _resolve_user_by_identifier(
        staff_identifier, expected_role="staff", for_update=True
    )
    if staff_user is None or staff_user.staff_profile is None:
        raise AuthServiceError("not_found", "Staff account not found.", 404)

    now = datetime.now(UTC)
    changed_fields: list[str] = []

    if any(k in data for k in ("fullName", "full_name", "name")):
        new_name = str(
            data.get("fullName") or data.get("full_name") or data.get("name") or ""
        ).strip()
        if not new_name or len(new_name) > 120:
            raise AuthServiceError("validation_error", "Invalid full name.", 400)
        staff_user.full_name = new_name
        changed_fields.append("full_name")

    old_email = staff_user.email
    if "email" in data and data["email"] is not None:
        new_email, email_err = normalize_and_validate_email(str(data["email"]))
        if email_err or not new_email:
            raise AuthServiceError("validation_error", email_err or "Invalid email.", 400)
        if new_email != staff_user.email:
            dup = db.session.execute(
                select(User.id).where(User.email == new_email, User.id != staff_user.id)
            ).scalar_one_or_none()
            if dup is not None:
                raise AuthServiceError("conflict", "Email address is already in use.", 409)
            staff_user.email = new_email
            changed_fields.append("email")

    if "phone" in data:
        new_phone = str(data.get("phone") or "").strip() or None
        if new_phone and len(new_phone) > 20:
            raise AuthServiceError("validation_error", "Phone number too long.", 400)
        staff_user.phone = new_phone
        changed_fields.append("phone")

    if "designation" in data:
        new_desig = str(data.get("designation") or "").strip() or None
        if new_desig and len(new_desig) > 80:
            raise AuthServiceError("validation_error", "Designation too long.", 400)
        staff_user.designation = new_desig
        changed_fields.append("designation")

    if "trade" in data and data["trade"] is not None:
        new_trade = str(data["trade"]).strip()
        if not new_trade or len(new_trade) > 60:
            raise AuthServiceError("validation_error", "Valid trade is required.", 400)
        staff_user.staff_profile.trade = new_trade
        changed_fields.append("trade")

    if "shift" in data:
        new_shift = str(data.get("shift") or "").strip() or None
        if new_shift and len(new_shift) > 60:
            raise AuthServiceError("validation_error", "Shift too long.", 400)
        staff_user.staff_profile.shift = new_shift
        changed_fields.append("shift")

    if "status" in data and data["status"] is not None:
        raw_status = str(data["status"]).strip().lower()
        mapped_status = (
            "active"
            if raw_status in ("active", "on duty")
            else "deactivated"
            if raw_status in ("deactivated", "inactive")
            else "suspended"
            if raw_status == "suspended"
            else ""
        )
        if not mapped_status:
            raise AuthServiceError("validation_error", "Invalid staff status.", 400)
        if mapped_status != staff_user.status:
            staff_user.status = mapped_status
            if mapped_status != "active":
                staff_user.session_version = int(staff_user.session_version) + 1
            changed_fields.append("status")

    staff_user.updated_at = now
    staff_user.staff_profile.updated_at = now

    record_audit_event(
        action="staff.updated",
        actor=admin_user,
        target_type="user",
        target_id=str(staff_user.public_id),
        metadata={
            "staff_code": staff_user.staff_profile.staff_code,
            "changed_fields": changed_fields,
        },
    )

    if "email" in changed_fields:
        record_audit_event(
            action="staff.email_updated",
            actor=admin_user,
            target_type="user",
            target_id=str(staff_user.public_id),
            metadata={
                "staff_user_id": staff_user.id,
                "staff_code": staff_user.staff_profile.staff_code,
                "action": "email_change",
                "old_email": old_email,
                "new_email": staff_user.email,
            },
        )

    db.session.commit()
    return staff_user


def deactivate_staff_account(*, staff_identifier: str, admin_user: User) -> User:
    """Deactivate a staff account (`status='deactivated'`), revoking sessions and open tokens."""
    staff_user = _resolve_user_by_identifier(
        staff_identifier, expected_role="staff", for_update=True
    )
    if staff_user is None or staff_user.staff_profile is None:
        raise AuthServiceError("not_found", "Staff account not found.", 404)

    now = datetime.now(UTC)
    staff_user.status = "deactivated"
    staff_user.session_version = int(staff_user.session_version) + 1
    staff_user.updated_at = now

    db.session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == staff_user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    record_audit_event(
        action="staff.deactivated",
        actor=admin_user,
        target_type="user",
        target_id=str(staff_user.public_id),
        metadata={"staff_code": staff_user.staff_profile.staff_code},
    )
    db.session.commit()
    return staff_user


def update_own_staff_profile(*, staff_user: User, data: dict[str, Any]) -> User:
    """Allow an authenticated active staff member to update their own `phone` and `shift` only."""
    for forbidden_key in (
        "role",
        "status",
        "trade",
        "staff_code",
        "staffCode",
        "full_name",
        "fullName",
    ):
        if forbidden_key in data:
            raise AuthServiceError(
                "forbidden_field",
                f"Field '{forbidden_key}' can only be modified by hostel administration.",
                403,
            )

    locked_user = _resolve_user_by_identifier(
        str(staff_user.public_id), expected_role="staff", for_update=True
    )
    if locked_user is None or locked_user.staff_profile is None:
        raise AuthServiceError("not_found", "Staff profile not found.", 404)

    now = datetime.now(UTC)
    if "phone" in data:
        new_phone = str(data.get("phone") or "").strip() or None
        if new_phone and len(new_phone) > 20:
            raise AuthServiceError(
                "validation_error", "Phone number must not exceed 20 characters.", 400
            )
        locked_user.phone = new_phone

    if "shift" in data:
        new_shift = str(data.get("shift") or "").strip() or None
        if new_shift and len(new_shift) > 60:
            raise AuthServiceError("validation_error", "Shift must not exceed 60 characters.", 400)
        locked_user.staff_profile.shift = new_shift

    locked_user.updated_at = now
    locked_user.staff_profile.updated_at = now
    db.session.commit()
    return locked_user


def list_audit_logs(*, limit: int = 100) -> list[AuditLog]:
    """Return recent `AuditLog` entries ordered by `occurred_at DESC` (Admin only)."""
    capped_limit = max(1, min(limit, 500))
    stmt = (
        select(AuditLog)
        .options(joinedload(AuditLog.actor))
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(capped_limit)
    )
    return list(db.session.execute(stmt).scalars().all())


def serialize_room_occupancy(
    room: Room, active_allocations: list[RoomAllocation]
) -> dict[str, Any]:
    """Explicit serializer for room occupancy and bed-level resident allocation."""
    capacity = int(room.capacity)
    valid_allocs = [
        alloc
        for alloc in active_allocations
        if alloc.student is not None and alloc.student.user is not None
    ]
    occupied = len(valid_allocs)
    vacant_beds = max(0, capacity - occupied)

    by_bed: dict[int, RoomAllocation] = {int(alloc.bed_number): alloc for alloc in valid_allocs}
    resident_names: list[str] = []
    resident_details: list[dict[str, Any]] = []

    for alloc in valid_allocs:
        stu_profile = alloc.student
        stu_user = stu_profile.user
        resident_names.append(stu_user.full_name)
        resident_details.append(
            {
                "id": str(stu_user.public_id),
                "full_name": stu_user.full_name,
                "fullName": stu_user.full_name,
                "roll_number": stu_profile.roll_number,
                "rollNumber": stu_profile.roll_number,
                "bed_number": int(alloc.bed_number),
            }
        )

    beds: list[dict[str, Any]] = []
    students_slots: list[str] = []

    for bed_no in range(1, capacity + 1):
        alloc = by_bed.get(bed_no)
        if alloc is not None and alloc.student is not None and alloc.student.user is not None:
            stu_profile = alloc.student
            stu_user = stu_profile.user
            beds.append(
                {
                    "bed_number": bed_no,
                    "occupied": True,
                    "student_id": str(stu_user.public_id),
                    "student_name": stu_user.full_name,
                    "roll_number": stu_profile.roll_number,
                }
            )
            students_slots.append(stu_user.full_name)
        else:
            beds.append(
                {
                    "bed_number": bed_no,
                    "occupied": False,
                    "student_id": None,
                    "student_name": None,
                    "roll_number": None,
                }
            )
            students_slots.append("(Vacant Bed)")

    block = room.block
    return {
        "id": room.room_number,
        "room_id": room.id,
        "room_number": room.room_number,
        "roomNumber": room.room_number,
        "block": block.name if block is not None else "Hostel",
        "block_id": room.block_id,
        "block_code": block.code if block is not None else None,
        "blockCode": block.code if block is not None else None,
        "floor": _format_floor_label(int(room.floor)),
        "floor_number": int(room.floor),
        "room_type": room.room_type,
        "capacity": capacity,
        "occupied": occupied,
        "occupied_beds": occupied,
        "vacant_beds": vacant_beds,
        "vacantBeds": vacant_beds,
        "residents": resident_names,
        "resident_details": resident_details,
        "beds": beds,
        "students": students_slots,
    }


def list_room_occupancy() -> list[dict[str, Any]]:
    """Return all active hostel rooms and their active-today occupancy in 2 queries (no N+1)."""
    rooms_stmt = (
        select(Room)
        .join(Block, Room.block_id == Block.id)
        .options(joinedload(Room.block))
        .where(Room.is_active.is_(True), Block.is_active.is_(True))
        .order_by(
            Block.display_order.asc(),
            Block.code.asc(),
            Room.floor.asc(),
            Room.room_number.asc(),
        )
    )
    rooms = list(db.session.execute(rooms_stmt).scalars().all())
    if not rooms:
        return []

    room_ids = [rm.id for rm in rooms]
    alloc_stmt = (
        select(RoomAllocation)
        .options(joinedload(RoomAllocation.student).joinedload(StudentProfile.user))
        .where(
            RoomAllocation.room_id.in_(room_ids),
            RoomAllocation.start_date <= func.current_date(),
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > func.current_date()),
        )
        .order_by(
            RoomAllocation.room_id.asc(),
            RoomAllocation.bed_number.asc(),
            RoomAllocation.id.asc(),
        )
    )
    active_allocs = list(db.session.execute(alloc_stmt).scalars().all())

    allocs_by_room: dict[int, list[RoomAllocation]] = {}
    for alloc in active_allocs:
        allocs_by_room.setdefault(alloc.room_id, []).append(alloc)

    return [serialize_room_occupancy(rm, allocs_by_room.get(rm.id, [])) for rm in rooms]
