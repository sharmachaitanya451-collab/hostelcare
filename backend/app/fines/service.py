"""Fines lifecycle service: issuance, listing, filtering, waiving, and cancellation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.audit.service import record_audit_event
from app.auth.service import AuthServiceError
from app.extensions import db
from app.models.fines import Fine, FineDispute, FineHistory
from app.models.identity import StudentProfile, User
from app.models.payments import Payment
from app.models.rooms import Room, RoomAllocation
from app.notifications.service import create_notification, notify_active_admins

_IST = ZoneInfo("Asia/Kolkata")
VALID_FINE_STATUSES = frozenset({"pending", "disputed", "paid", "waived", "cancelled"})
VALID_DISPUTE_STATUSES = frozenset({"open", "approved", "rejected"})
_MUTABLE_UNPAID_STATUSES = frozenset({"pending", "disputed"})


class FineServiceError(AuthServiceError):
    """Domain error for fines operations, mapped to JSON error envelopes."""


def _today_ist() -> date:
    return datetime.now(_IST).date()


def _parse_iso_date(raw: Any, field_name: str) -> date:
    if raw is None or not isinstance(raw, str) or not raw.strip():
        raise FineServiceError("validation_error", f"{field_name} is required (YYYY-MM-DD).", 400)
    text_val = raw.strip()
    try:
        return date.fromisoformat(text_val)
    except ValueError as exc:
        raise FineServiceError(
            "validation_error",
            f"Invalid {field_name} format '{text_val}'. Expected YYYY-MM-DD.",
            400,
        ) from exc


def _parse_positive_amount(raw: Any) -> Decimal:
    """Parse monetary INR amount strictly using Decimal (no binary float drift)."""
    if raw is None or isinstance(raw, bool):
        raise FineServiceError("validation_error", "Fine amount in INR is required.", 400)

    raw_str = str(raw).strip()
    if not raw_str:
        raise FineServiceError("validation_error", "Fine amount in INR is required.", 400)

    try:
        amount = Decimal(raw_str)
    except InvalidOperation as exc:
        raise FineServiceError(
            "validation_error", "Fine amount must be a valid decimal number.", 400
        ) from exc

    if not amount.is_finite():
        raise FineServiceError("validation_error", "Fine amount must be a finite number.", 400)

    if amount <= Decimal("0"):
        raise FineServiceError("validation_error", "Fine amount must be greater than 0 INR.", 400)

    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise FineServiceError(
            "validation_error",
            "Fine amount cannot have more than 2 decimal places.",
            400,
        )

    quantized = amount.quantize(Decimal("0.01"))
    if quantized > Decimal("9999999999.99"):
        raise FineServiceError(
            "validation_error", "Fine amount exceeds maximum allowed limit.", 400
        )
    return quantized


def _resolve_eligible_student(raw_student: Any) -> tuple[User, StudentProfile]:
    """Resolve an active student eligible to receive a fine."""
    if raw_student is None or not str(raw_student).strip():
        raise FineServiceError("validation_error", "Student identifier is required.", 400)

    ident = str(raw_student).strip()
    user: User | None = None

    # 1. Try UUID public_id
    try:
        parsed_uuid = uuid.UUID(ident)
        user = db.session.execute(
            select(User).where(User.public_id == parsed_uuid)
        ).scalar_one_or_none()
    except ValueError:
        user = None

    # 2. Try numeric user.id
    if user is None and ident.isdigit():
        user = db.session.get(User, int(ident))

    # 3. Try StudentProfile.roll_number
    if user is None:
        profile_by_roll = db.session.execute(
            select(StudentProfile).where(func.lower(StudentProfile.roll_number) == ident.lower())
        ).scalar_one_or_none()
        if profile_by_roll is not None:
            user = db.session.get(User, profile_by_roll.user_id)

    if user is None or user.role != "student":
        raise FineServiceError("not_found", f"Student '{ident}' not found.", 404)

    profile = db.session.get(StudentProfile, user.id)
    if profile is None:
        raise FineServiceError("not_found", f"Student profile for '{ident}' not found.", 404)

    if user.status != "active":
        raise FineServiceError(
            "validation_error",
            f"Cannot issue fine to student with status '{user.status}'. Student must be active.",
            400,
        )

    return user, profile


def _find_active_room_id(student_user_id: int) -> int | None:
    today = _today_ist()
    return db.session.execute(
        select(RoomAllocation.room_id)
        .where(
            RoomAllocation.student_user_id == student_user_id,
            RoomAllocation.start_date <= today,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
        )
        .limit(1)
    ).scalar_one_or_none()


def _find_fine(fine_identifier: str, *, lock: bool = False) -> Fine:
    raw = str(fine_identifier or "").strip()
    if not raw:
        raise FineServiceError("not_found", "Fine identifier is required.", 404)

    stmt = select(Fine)
    if not lock:
        stmt = stmt.options(
            joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(Fine.room).joinedload(Room.block),
            joinedload(Fine.issuer),
            joinedload(Fine.resolver),
            joinedload(Fine.dispute).joinedload(FineDispute.decider),
            selectinload(Fine.history).joinedload(FineHistory.actor),
        )

    if raw.upper().startswith("FIN-"):
        stmt = stmt.where(func.upper(Fine.reference_no) == raw.upper())
    elif raw.isdigit():
        stmt = stmt.where(Fine.id == int(raw))
    else:
        stmt = stmt.where(func.upper(Fine.reference_no) == raw.upper())

    if lock:
        stmt = stmt.with_for_update()

    fine = db.session.execute(stmt).scalar_one_or_none()
    if fine is None:
        raise FineServiceError("not_found", f"Fine '{raw}' not found.", 404)
    return fine


def _is_overdue(fine: Fine) -> bool:
    return fine.status in _MUTABLE_UNPAID_STATUSES and fine.due_date < _today_ist()


def _serialize_history_entry(
    entry: FineHistory, *, include_actor_role: bool = True
) -> dict[str, Any]:
    actor_name = entry.actor.full_name if entry.actor else "System"
    payload: dict[str, Any] = {
        "id": entry.id,
        "action": entry.action,
        "fromStatus": entry.from_status,
        "toStatus": entry.to_status,
        "note": entry.note,
        "actorName": actor_name,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
    }
    if include_actor_role:
        payload["actorRole"] = entry.actor.role if entry.actor else None
    return payload


def _serialize_dispute(
    dispute: FineDispute | None, *, include_admin_fields: bool = False
) -> dict[str, Any] | None:
    if dispute is None:
        return None
    payload: dict[str, Any] = {
        "id": dispute.id,
        "status": dispute.status,
        "reason": dispute.reason,
        "decisionReason": dispute.decision_reason,
        "decidedAt": dispute.decided_at.isoformat() if dispute.decided_at else None,
        "createdAt": dispute.created_at.isoformat() if dispute.created_at else None,
    }
    if include_admin_fields:
        payload["decidedBy"] = dispute.decider.full_name if dispute.decider else None
    return payload


def serialize_fine_for_admin(fine: Fine) -> dict[str, Any]:
    student_profile = fine.student
    student_user = student_profile.user if student_profile else None
    room = fine.room
    block = room.block if room else None
    sorted_history = sorted(fine.history, key=lambda h: (h.created_at, h.id))

    return {
        "id": fine.reference_no,
        "fineId": fine.id,
        "referenceNo": fine.reference_no,
        "studentId": str(student_user.public_id) if student_user else None,
        "studentName": student_user.full_name if student_user else None,
        "studentRoll": student_profile.roll_number if student_profile else None,
        "studentEmail": student_user.email if student_user else None,
        "room": room.room_number if room else None,
        "block": block.name if block else None,
        "category": fine.category,
        "description": fine.description,
        "amountInr": f"{fine.amount_inr:.2f}",
        "amount": float(fine.amount_inr),
        "issueDate": fine.issue_date.isoformat(),
        "dueDate": fine.due_date.isoformat(),
        "status": fine.status,
        "isOverdue": _is_overdue(fine),
        "issuedBy": fine.issuer.full_name if fine.issuer else None,
        "paidAt": fine.paid_at.isoformat() if fine.paid_at else None,
        "resolvedBy": fine.resolver.full_name if fine.resolver else None,
        "resolvedAt": fine.resolved_at.isoformat() if fine.resolved_at else None,
        "resolutionReason": fine.resolution_reason,
        "version": fine.version,
        "createdAt": fine.created_at.isoformat() if fine.created_at else None,
        "updatedAt": fine.updated_at.isoformat() if fine.updated_at else None,
        "dispute": _serialize_dispute(fine.dispute, include_admin_fields=True),
        "history": [_serialize_history_entry(h, include_actor_role=True) for h in sorted_history],
    }


def serialize_fine_for_student(fine: Fine) -> dict[str, Any]:
    """Serialize fine for the owning student without exposing internal admin user IDs."""
    room = fine.room
    block = room.block if room else None
    sorted_history = sorted(fine.history, key=lambda h: (h.created_at, h.id))

    return {
        "id": fine.reference_no,
        "referenceNo": fine.reference_no,
        "room": room.room_number if room else None,
        "block": block.name if block else None,
        "category": fine.category,
        "description": fine.description,
        "amountInr": f"{fine.amount_inr:.2f}",
        "amount": float(fine.amount_inr),
        "issueDate": fine.issue_date.isoformat(),
        "dueDate": fine.due_date.isoformat(),
        "status": fine.status,
        "isOverdue": _is_overdue(fine),
        "issuedByName": fine.issuer.full_name if fine.issuer else "Warden Administration",
        "paidAt": fine.paid_at.isoformat() if fine.paid_at else None,
        "resolvedAt": fine.resolved_at.isoformat() if fine.resolved_at else None,
        "resolutionReason": fine.resolution_reason,
        "createdAt": fine.created_at.isoformat() if fine.created_at else None,
        "dispute": _serialize_dispute(fine.dispute, include_admin_fields=False),
        "history": [_serialize_history_entry(h, include_actor_role=False) for h in sorted_history],
    }


def issue_fine(admin_user: User, data: dict[str, Any]) -> dict[str, Any]:
    """Issue a new disciplinary fine against an active student in a single transaction."""
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_student = data.get("student_id") or data.get("studentId") or data.get("student_user_id")
    student_user, student_profile = _resolve_eligible_student(raw_student)

    raw_desc = (
        data.get("description") if data.get("description") is not None else data.get("reason")
    )
    description = str(raw_desc or "").strip()
    if not description:
        raise FineServiceError("validation_error", "Fine description/reason is required.", 400)
    if len(description) > 5000:
        raise FineServiceError(
            "validation_error", "Fine description must not exceed 5000 characters.", 400
        )

    raw_category = data.get("category")
    category: str | None = None
    if raw_category is not None and str(raw_category).strip():
        category = str(raw_category).strip()
        if len(category) > 80:
            raise FineServiceError(
                "validation_error", "Category must not exceed 80 characters.", 400
            )

    raw_amount = (
        data.get("amount_inr")
        if data.get("amount_inr") is not None
        else data.get("amountInr")
        if data.get("amountInr") is not None
        else data.get("amount")
    )
    amount_inr = _parse_positive_amount(raw_amount)

    raw_issue_date = data.get("issue_date") or data.get("issueDate")
    issue_date = (
        _parse_iso_date(raw_issue_date, "issue_date")
        if raw_issue_date is not None
        else _today_ist()
    )

    raw_due_date = data.get("due_date") or data.get("dueDate")
    due_date = _parse_iso_date(raw_due_date, "due_date")
    if due_date < issue_date:
        raise FineServiceError(
            "validation_error",
            "Due date must be on or after the issue date.",
            400,
        )

    room_id: int | None = None
    raw_room_id = data.get("room_id") or data.get("roomId")
    if raw_room_id is not None:
        if not str(raw_room_id).isdigit():
            raise FineServiceError("validation_error", "room_id must be a valid integer.", 400)
        room = db.session.get(Room, int(raw_room_id))
        if room is None:
            raise FineServiceError("not_found", f"Room '{raw_room_id}' not found.", 404)
        room_id = room.id
    else:
        room_id = _find_active_room_id(student_user.id)

    try:
        fine = Fine(
            student_user_id=student_profile.user_id,
            room_id=room_id,
            category=category,
            description=description,
            amount_inr=amount_inr,
            issue_date=issue_date,
            due_date=due_date,
            issued_by=admin_user.id,
            status="pending",
        )
        db.session.add(fine)
        db.session.flush()

        history_note = f"Fine issued for INR {amount_inr:.2f}. Due {due_date.isoformat()}."
        history = FineHistory(
            fine_id=fine.id,
            actor_user_id=admin_user.id,
            action="issued",
            from_status=None,
            to_status="pending",
            note=history_note,
        )
        db.session.add(history)

        record_audit_event(
            action="fine_issued",
            actor=admin_user,
            target_type="fine",
            target_id=fine.reference_no,
            metadata={
                "student_public_id": str(student_user.public_id),
                "roll_number": student_profile.roll_number,
                "amount_inr": f"{amount_inr:.2f}",
                "due_date": due_date.isoformat(),
                "category": category,
            },
        )
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict", "Unable to issue fine due to a database constraint.", 409
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    reloaded = _find_fine(fine.reference_no)
    return serialize_fine_for_admin(reloaded)


def list_admin_fines(filters: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List and filter fines for admins with pagination."""
    stmt = (
        select(Fine)
        .options(
            joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(Fine.room).joinedload(Room.block),
            joinedload(Fine.issuer),
            joinedload(Fine.resolver),
            selectinload(Fine.history).joinedload(FineHistory.actor),
        )
        .order_by(Fine.created_at.desc(), Fine.id.desc())
    )

    status_val = (filters.get("status") or "").strip().lower()
    if status_val and status_val != "all":
        if status_val not in VALID_FINE_STATUSES:
            allowed = ", ".join(sorted(VALID_FINE_STATUSES))
            raise FineServiceError(
                "validation_error",
                f"Invalid status filter '{status_val}'. Must be one of: {allowed}.",
                400,
            )
        stmt = stmt.where(Fine.status == status_val)

    student_val = (filters.get("student") or "").strip()
    if student_val:
        student_conditions = [func.lower(StudentProfile.roll_number) == student_val.lower()]
        try:
            parsed_uuid = uuid.UUID(student_val)
            student_conditions.append(User.public_id == parsed_uuid)
        except ValueError:
            pass
        if student_val.isdigit():
            student_conditions.append(User.id == int(student_val))

        stmt = (
            stmt.join(StudentProfile, Fine.student_user_id == StudentProfile.user_id)
            .join(User, StudentProfile.user_id == User.id)
            .where(or_(*student_conditions))
        )

    date_from_val = (filters.get("date_from") or "").strip()
    if date_from_val:
        date_from = _parse_iso_date(date_from_val, "date_from")
        stmt = stmt.where(Fine.issue_date >= date_from)

    date_to_val = (filters.get("date_to") or "").strip()
    if date_to_val:
        date_to = _parse_iso_date(date_to_val, "date_to")
        stmt = stmt.where(Fine.issue_date <= date_to)

    overdue_raw = filters.get("overdue")
    if overdue_raw is not None and str(overdue_raw).strip() != "":
        overdue_str = str(overdue_raw).strip().lower()
        today = _today_ist()
        if overdue_str in {"true", "1", "yes"}:
            stmt = stmt.where(
                Fine.status.in_(list(_MUTABLE_UNPAID_STATUSES)),
                Fine.due_date < today,
            )
        elif overdue_str in {"false", "0", "no"}:
            stmt = stmt.where(
                or_(
                    ~Fine.status.in_(list(_MUTABLE_UNPAID_STATUSES)),
                    Fine.due_date >= today,
                )
            )
        else:
            raise FineServiceError(
                "validation_error", "overdue filter must be 'true' or 'false'.", 400
            )

    ref_val = (filters.get("reference") or "").strip()
    if ref_val:
        stmt = stmt.where(Fine.reference_no.ilike(f"%{ref_val}%"))

    # Pagination
    try:
        page = max(1, int(filters.get("page") or 1))
    except (TypeError, ValueError) as exc:
        raise FineServiceError("validation_error", "page must be a positive integer.", 400) from exc

    try:
        raw_page_size = int(filters.get("page_size") or 20)
        page_size = max(1, min(raw_page_size, 100))
    except (TypeError, ValueError) as exc:
        raise FineServiceError(
            "validation_error", "page_size must be a positive integer.", 400
        ) from exc

    total = int(
        db.session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()
        or 0
    )
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    paged_fines = (
        db.session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .unique()
        .all()
    )
    return (
        [serialize_fine_for_admin(f) for f in paged_fines],
        {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
        },
    )


def get_admin_fine(fine_identifier: str) -> dict[str, Any]:
    fine = _find_fine(fine_identifier)
    return serialize_fine_for_admin(fine)


def _resolve_fine_terminal_status(
    admin_user: User,
    fine_identifier: str,
    data: dict[str, Any],
    *,
    target_status: str,
    audit_action: str,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_reason = (
        data.get("reason")
        if data.get("reason") is not None
        else data.get("resolution_reason")
        if data.get("resolution_reason") is not None
        else data.get("note")
    )
    reason = str(raw_reason or "").strip()
    if not reason:
        verb = "waive" if target_status == "waived" else "cancel"
        raise FineServiceError(
            "validation_error",
            f"A non-empty reason is required to {verb} a fine.",
            400,
        )
    if len(reason) > 2000:
        raise FineServiceError("validation_error", "Reason must not exceed 2000 characters.", 400)

    try:
        fine = _find_fine(fine_identifier, lock=True)
        if fine.status not in _MUTABLE_UNPAID_STATUSES:
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot transition fine {fine.reference_no} from "
                f"'{fine.status}' to '{target_status}'.",
                409,
            )

        # Defense in depth: never waive or cancel if a verified Payment row exists
        has_payment = db.session.execute(
            select(Payment.id).where(Payment.fine_id == fine.id)
        ).scalar_one_or_none()
        if has_payment is not None:
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot mark fine {fine.reference_no} as '{target_status}' "
                "because a payment record already exists.",
                409,
            )

        old_status = fine.status
        now = datetime.now(UTC)
        fine.status = target_status
        fine.resolved_by = admin_user.id
        fine.resolved_at = now
        fine.resolution_reason = reason
        fine.version += 1

        history = FineHistory(
            fine_id=fine.id,
            actor_user_id=admin_user.id,
            action=target_status,
            from_status=old_status,
            to_status=target_status,
            note=reason,
        )
        db.session.add(history)

        record_audit_event(
            action=audit_action,
            actor=admin_user,
            target_type="fine",
            target_id=fine.reference_no,
            metadata={
                "from_status": old_status,
                "to_status": target_status,
                "reason": reason,
            },
        )
        db.session.commit()
    except FineServiceError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise

    reloaded = _find_fine(fine.reference_no)
    return serialize_fine_for_admin(reloaded)


def waive_fine(admin_user: User, fine_identifier: str, data: dict[str, Any]) -> dict[str, Any]:
    """Waive an unpaid (`pending` or `disputed`) fine with a mandatory reason."""
    return _resolve_fine_terminal_status(
        admin_user,
        fine_identifier,
        data,
        target_status="waived",
        audit_action="fine_waived",
    )


def cancel_fine(admin_user: User, fine_identifier: str, data: dict[str, Any]) -> dict[str, Any]:
    """Cancel an unpaid (`pending` or `disputed`) fine with a mandatory reason."""
    return _resolve_fine_terminal_status(
        admin_user,
        fine_identifier,
        data,
        target_status="cancelled",
        audit_action="fine_cancelled",
    )


def list_student_fines(
    student_user: User, *, status_filter: str | None = None
) -> list[dict[str, Any]]:
    """List fines strictly owned by the authenticated student."""
    stmt = (
        select(Fine)
        .where(Fine.student_user_id == student_user.id)
        .options(
            joinedload(Fine.room).joinedload(Room.block),
            joinedload(Fine.issuer),
            joinedload(Fine.dispute),
            selectinload(Fine.history).joinedload(FineHistory.actor),
        )
        .order_by(Fine.created_at.desc(), Fine.id.desc())
    )

    clean_status = (status_filter or "").strip().lower()
    if clean_status and clean_status != "all":
        if clean_status not in VALID_FINE_STATUSES:
            raise FineServiceError(
                "validation_error",
                f"Invalid status filter '{clean_status}'.",
                400,
            )
        stmt = stmt.where(Fine.status == clean_status)

    fines = db.session.execute(stmt).scalars().unique().all()
    return [serialize_fine_for_student(f) for f in fines]


def get_student_fine(student_user: User, fine_identifier: str) -> dict[str, Any]:
    """Return a single fine only if owned by the authenticated student."""
    fine = _find_fine(fine_identifier)
    if fine.student_user_id != student_user.id:
        raise FineServiceError(
            "forbidden",
            "You do not have permission to access another student's fine.",
            403,
        )
    return serialize_fine_for_student(fine)


# ---------------------------------------------------------------------------
# Phase 3E.2: Fine Disputes & Administrative Review
# ---------------------------------------------------------------------------


def submit_student_fine_dispute(
    student_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Submit a student dispute against an owned `pending` fine atomically."""
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_reason = data.get("reason") if data.get("reason") is not None else data.get("explanation")
    reason = str(raw_reason or "").strip()
    if not reason:
        raise FineServiceError(
            "validation_error", "A non-empty dispute explanation is required.", 400
        )
    if len(reason) > 4000:
        raise FineServiceError(
            "validation_error",
            "Dispute explanation must not exceed 4000 characters.",
            400,
        )

    try:
        fine = _find_fine(fine_identifier, lock=True)
        if fine.student_user_id != student_user.id:
            raise FineServiceError(
                "forbidden",
                "You do not have permission to dispute another student's fine.",
                403,
            )

        if fine.status != "pending":
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot dispute fine {fine.reference_no} because its status is '{fine.status}'.",
                409,
            )

        existing_dispute = db.session.execute(
            select(FineDispute).where(FineDispute.fine_id == fine.id)
        ).scalar_one_or_none()
        if existing_dispute is not None:
            raise FineServiceError(
                "conflict",
                f"A dispute already exists for fine {fine.reference_no}.",
                409,
            )

        dispute = FineDispute(
            fine_id=fine.id,
            raised_by=student_user.id,
            reason=reason,
            status="open",
        )
        db.session.add(dispute)
        db.session.flush()

        fine.status = "disputed"
        fine.version += 1

        history = FineHistory(
            fine_id=fine.id,
            actor_user_id=student_user.id,
            action="dispute_submitted",
            from_status="pending",
            to_status="disputed",
            note=reason,
            dispute_id=dispute.id,
        )
        db.session.add(history)

        notify_active_admins(
            category="dispute",
            event_type="fine_dispute_submitted",
            title=f"Fine Dispute Submitted ({fine.reference_no})",
            message=(
                f"{student_user.full_name} disputed fine {fine.reference_no} "
                f"(INR {fine.amount_inr:.2f})."
            ),
            entity_type="fine",
            entity_ref=fine.reference_no,
        )

        record_audit_event(
            action="fine_dispute_submitted",
            actor=student_user,
            target_type="fine",
            target_id=fine.reference_no,
            metadata={
                "dispute_id": dispute.id,
                "from_status": "pending",
                "to_status": "disputed",
            },
        )
        db.session.commit()
    except FineServiceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict",
            "Unable to submit dispute due to a database constraint.",
            409,
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    reloaded = _find_fine(fine.reference_no)
    return serialize_fine_for_student(reloaded)


def _serialize_admin_dispute_row(dispute: FineDispute) -> dict[str, Any]:
    fine = dispute.fine
    student_profile = fine.student if fine else None
    student_user = student_profile.user if student_profile else None
    room = fine.room if fine else None
    block = room.block if room else None

    return {
        "disputeId": dispute.id,
        "status": dispute.status,
        "reason": dispute.reason,
        "decisionReason": dispute.decision_reason,
        "decidedBy": dispute.decider.full_name if dispute.decider else None,
        "decidedAt": dispute.decided_at.isoformat() if dispute.decided_at else None,
        "createdAt": dispute.created_at.isoformat() if dispute.created_at else None,
        "fineId": fine.id if fine else None,
        "referenceNo": fine.reference_no if fine else None,
        "fineStatus": fine.status if fine else None,
        "category": fine.category if fine else None,
        "description": fine.description if fine else None,
        "amountInr": f"{fine.amount_inr:.2f}" if fine else None,
        "amount": float(fine.amount_inr) if fine else None,
        "issueDate": fine.issue_date.isoformat() if fine else None,
        "dueDate": fine.due_date.isoformat() if fine else None,
        "isOverdue": _is_overdue(fine) if fine else False,
        "studentId": str(student_user.public_id) if student_user else None,
        "studentName": student_user.full_name if student_user else None,
        "studentRoll": student_profile.roll_number if student_profile else None,
        "room": room.room_number if room else None,
        "block": block.name if block else None,
    }


def list_admin_fine_disputes(
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List and filter fine disputes for administrative review with pagination."""
    stmt = (
        select(FineDispute)
        .join(Fine, FineDispute.fine_id == Fine.id)
        .options(
            joinedload(FineDispute.fine).joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(FineDispute.fine).joinedload(Fine.room).joinedload(Room.block),
            joinedload(FineDispute.decider),
        )
        .order_by(FineDispute.created_at.desc(), FineDispute.id.desc())
    )

    status_val = (filters.get("status") or "").strip().lower()
    if status_val and status_val != "all":
        if status_val not in VALID_DISPUTE_STATUSES:
            allowed = ", ".join(sorted(VALID_DISPUTE_STATUSES))
            raise FineServiceError(
                "validation_error",
                f"Invalid dispute status filter '{status_val}'. Must be one of: {allowed}.",
                400,
            )
        stmt = stmt.where(FineDispute.status == status_val)

    student_val = (filters.get("student") or "").strip()
    if student_val:
        student_conditions = [func.lower(StudentProfile.roll_number) == student_val.lower()]
        try:
            parsed_uuid = uuid.UUID(student_val)
            student_conditions.append(User.public_id == parsed_uuid)
        except ValueError:
            pass
        if student_val.isdigit():
            student_conditions.append(User.id == int(student_val))

        stmt = (
            stmt.join(StudentProfile, Fine.student_user_id == StudentProfile.user_id)
            .join(User, StudentProfile.user_id == User.id)
            .where(or_(*student_conditions))
        )

    ref_val = (filters.get("reference") or "").strip()
    if ref_val:
        stmt = stmt.where(Fine.reference_no.ilike(f"%{ref_val}%"))

    date_from_val = (filters.get("date_from") or "").strip()
    if date_from_val:
        date_from = _parse_iso_date(date_from_val, "date_from")
        start_dt = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
        stmt = stmt.where(FineDispute.created_at >= start_dt)

    date_to_val = (filters.get("date_to") or "").strip()
    if date_to_val:
        date_to = _parse_iso_date(date_to_val, "date_to")
        end_dt = datetime.combine(date_to, datetime.max.time(), tzinfo=UTC)
        stmt = stmt.where(FineDispute.created_at <= end_dt)

    try:
        page = max(1, int(filters.get("page") or 1))
    except (TypeError, ValueError) as exc:
        raise FineServiceError("validation_error", "page must be a positive integer.", 400) from exc

    try:
        raw_page_size = int(filters.get("page_size") or 20)
        page_size = max(1, min(raw_page_size, 100))
    except (TypeError, ValueError) as exc:
        raise FineServiceError(
            "validation_error", "page_size must be a positive integer.", 400
        ) from exc

    total = int(
        db.session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()
        or 0
    )
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    paged = (
        db.session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .unique()
        .all()
    )
    return (
        [_serialize_admin_dispute_row(d) for d in paged],
        {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
        },
    )


def review_fine_dispute(
    admin_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Approve (`disputed -> waived`) or reject (`disputed -> pending`) a fine dispute."""
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_decision = str(data.get("decision") or data.get("action") or "").strip().lower()
    if raw_decision in {"approve", "approved"}:
        decision = "approved"
    elif raw_decision in {"reject", "rejected"}:
        decision = "rejected"
    else:
        raise FineServiceError(
            "validation_error",
            "Decision must be 'approve' or 'reject'.",
            400,
        )

    raw_reason = (
        data.get("reason")
        if data.get("reason") is not None
        else data.get("decision_reason")
        if data.get("decision_reason") is not None
        else data.get("note")
    )
    decision_reason = str(raw_reason or "").strip()
    if not decision_reason:
        raise FineServiceError(
            "validation_error",
            "A non-empty decision reason is required to review a fine dispute.",
            400,
        )
    if len(decision_reason) > 2000:
        raise FineServiceError(
            "validation_error",
            "Decision reason must not exceed 2000 characters.",
            400,
        )

    try:
        fine = _find_fine(fine_identifier, lock=True)
        dispute = db.session.execute(
            select(FineDispute).where(FineDispute.fine_id == fine.id).with_for_update()
        ).scalar_one_or_none()

        if fine.status != "disputed" or dispute is None or dispute.status != "open":
            dispute_state = dispute.status if dispute else None
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot review dispute for fine {fine.reference_no} "
                f"(fine_status='{fine.status}', dispute_status='{dispute_state}').",
                409,
            )

        has_payment = db.session.execute(
            select(Payment.id).where(Payment.fine_id == fine.id)
        ).scalar_one_or_none()
        if has_payment is not None:
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot resolve dispute for fine {fine.reference_no} "
                "because a payment record exists.",
                409,
            )

        now = datetime.now(UTC)
        dispute.status = decision
        dispute.decided_by = admin_user.id
        dispute.decided_at = now
        dispute.decision_reason = decision_reason

        if decision == "approved":
            target_fine_status = "waived"
            history_action = "dispute_approved"
            fine.status = "waived"
            fine.resolved_by = admin_user.id
            fine.resolved_at = now
            fine.resolution_reason = decision_reason
            notif_event = "fine_dispute_approved"
            notif_title = f"Fine Dispute Approved ({fine.reference_no})"
            notif_msg = (
                f"Your dispute for fine {fine.reference_no} (INR {fine.amount_inr:.2f}) "
                f"was approved and the fine has been waived."
            )
        else:
            target_fine_status = "pending"
            history_action = "dispute_rejected"
            fine.status = "pending"
            fine.resolved_by = None
            fine.resolved_at = None
            fine.resolution_reason = None
            notif_event = "fine_dispute_rejected"
            notif_title = f"Fine Dispute Rejected ({fine.reference_no})"
            notif_msg = (
                f"Your dispute for fine {fine.reference_no} (INR {fine.amount_inr:.2f}) "
                f"was rejected. Due date remains {fine.due_date.isoformat()}."
            )

        fine.version += 1

        history = FineHistory(
            fine_id=fine.id,
            actor_user_id=admin_user.id,
            action=history_action,
            from_status="disputed",
            to_status=target_fine_status,
            note=decision_reason,
            dispute_id=dispute.id,
        )
        db.session.add(history)

        create_notification(
            recipient_user_id=fine.student_user_id,
            category="dispute",
            event_type=notif_event,
            title=notif_title,
            message=notif_msg,
            entity_type="fine",
            entity_ref=fine.reference_no,
        )

        record_audit_event(
            action=f"fine_dispute_{decision}",
            actor=admin_user,
            target_type="fine",
            target_id=fine.reference_no,
            metadata={
                "dispute_id": dispute.id,
                "decision": decision,
                "from_status": "disputed",
                "to_status": target_fine_status,
                "reason": decision_reason,
            },
        )
        db.session.commit()
    except FineServiceError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise

    reloaded = _find_fine(fine.reference_no)
    return serialize_fine_for_admin(reloaded)
