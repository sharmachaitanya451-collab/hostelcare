"""Staff task listing, inspection, acceptance, progress update, and completion services.

SECURITY & PRIVACY INVARIANT:
This module must NEVER import `ComplaintInternalNote` or `app.models.complaint_internal_notes`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.audit.service import record_audit_event
from app.auth.service import AuthServiceError
from app.complaints.serializers import complaint_load_options, resolve_complaint_by_identifier
from app.extensions import db
from app.models.complaints import (
    Complaint,
    ComplaintAssignment,
    ComplaintHistory,
    ComplaintUpdate,
)
from app.models.identity import User
from app.notifications.service import create_notification, notify_active_admins


def _ensure_active_staff(staff_user: User) -> None:
    if staff_user.role != "staff" or staff_user.status != "active":
        raise AuthServiceError(
            "forbidden_role",
            "Only active maintenance staff members can access staff task endpoints.",
            403,
        )


def _get_and_verify_staff_task(
    staff_user: User,
    complaint_identifier: str,
    *,
    for_update: bool = False,
) -> tuple[Complaint, ComplaintAssignment]:
    """Resolve `Complaint` and verify `staff_user` holds the active assignment."""
    _ensure_active_staff(staff_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=for_update)
    if complaint is None:
        raise AuthServiceError("task_not_found", "Task not found.", 404)

    assign_stmt = select(ComplaintAssignment).where(
        ComplaintAssignment.complaint_id == complaint.id,
        ComplaintAssignment.ended_at.is_(None),
    )
    if for_update:
        assign_stmt = assign_stmt.with_for_update(of=ComplaintAssignment)

    open_assign = db.session.execute(assign_stmt).scalar_one_or_none()
    if open_assign is None or open_assign.staff_user_id != staff_user.id:
        raise AuthServiceError(
            "forbidden",
            "You do not have permission to access or update a task not assigned to you.",
            403,
        )
    return complaint, open_assign


def list_staff_tasks(
    staff_user: User,
    *,
    status_filter: str | None = None,
) -> list[Complaint]:
    """Return complaints where `staff_user` holds the open (`ended_at IS NULL`) assignment."""
    _ensure_active_staff(staff_user)

    stmt = (
        select(Complaint)
        .join(
            ComplaintAssignment,
            (ComplaintAssignment.complaint_id == Complaint.id)
            & (ComplaintAssignment.ended_at.is_(None)),
        )
        .options(*complaint_load_options())
        .where(ComplaintAssignment.staff_user_id == staff_user.id)
    )

    if status_filter:
        norm = status_filter.strip().lower().replace(" ", "_")
        if norm == "resolved":
            norm = "completed"
        if norm != "all":
            stmt = stmt.where(Complaint.status == norm)

    stmt = stmt.order_by(Complaint.created_at.desc(), Complaint.id.desc())
    return list(db.session.execute(stmt).scalars().all())


def get_staff_task(staff_user: User, complaint_identifier: str) -> Complaint:
    """Return a single assigned task after verifying active ownership by `staff_user`."""
    complaint, _ = _get_and_verify_staff_task(
        staff_user,
        complaint_identifier,
        for_update=False,
    )
    return complaint


def accept_staff_task(staff_user: User, complaint_identifier: str) -> Complaint:
    """Transition an assigned task from `assigned` -> `accepted`."""
    complaint, open_assign = _get_and_verify_staff_task(
        staff_user,
        complaint_identifier,
        for_update=True,
    )

    if complaint.status != "assigned":
        raise AuthServiceError(
            "invalid_transition",
            f"Cannot accept task when status is '{complaint.status}'. Expected 'assigned'.",
            409,
        )

    now = datetime.now(UTC)
    accepted_ts = max(now, open_assign.assigned_at) if open_assign.assigned_at else now

    db.session.execute(
        update(ComplaintAssignment)
        .where(ComplaintAssignment.id == open_assign.id)
        .values(accepted_at=accepted_ts)
    )
    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="accepted",
            version=Complaint.version + 1,
            updated_at=accepted_ts,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=staff_user.id,
            action="accepted",
            from_status="assigned",
            to_status="accepted",
            note="Assignment accepted by maintenance staff.",
            assignment_id=open_assign.id,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.accepted",
        title=f"Technician Accepted {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} has accepted your maintenance request "
            f"'{complaint.title}' ({complaint.reference_no})."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    notify_active_admins(
        category="complaint",
        event_type="complaint.accepted",
        title=f"Task Accepted: {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} accepted assignment for complaint "
            f"{complaint.reference_no} ('{complaint.title}')."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.accepted",
        actor=staff_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "assigned",
            "to_status": "accepted",
            "assignment_id": open_assign.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return resolve_complaint_by_identifier(complaint.reference_no) or complaint


def start_staff_task(
    staff_user: User,
    complaint_identifier: str,
    payload: dict[str, Any] | None = None,
) -> Complaint:
    """Transition an accepted task from `accepted` -> `in_progress`."""
    complaint, open_assign = _get_and_verify_staff_task(
        staff_user,
        complaint_identifier,
        for_update=True,
    )

    if complaint.status != "accepted":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot start work when status is '{complaint.status}'. "
                "Task must be in 'accepted' status first."
            ),
            409,
        )

    body_dict = payload or {}
    raw_note = str(
        body_dict.get("note") or body_dict.get("body") or body_dict.get("message") or ""
    ).strip()
    if len(raw_note) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Progress note must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    accepted_base = open_assign.accepted_at or open_assign.assigned_at or now
    started_ts = max(now, accepted_base)

    assign_values: dict[str, Any] = {"started_at": started_ts}
    if open_assign.accepted_at is None:
        assign_values["accepted_at"] = accepted_base

    db.session.execute(
        update(ComplaintAssignment)
        .where(ComplaintAssignment.id == open_assign.id)
        .values(**assign_values)
    )

    upd_row: ComplaintUpdate | None = None
    if raw_note:
        upd_row = ComplaintUpdate(
            complaint_id=complaint.id,
            assignment_id=open_assign.id,
            author_user_id=staff_user.id,
            update_type="progress",
            body=raw_note,
        )
        db.session.add(upd_row)
        db.session.flush()

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="in_progress",
            version=Complaint.version + 1,
            updated_at=started_ts,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=staff_user.id,
            action="work_started",
            from_status="accepted",
            to_status="in_progress",
            note=raw_note or "Technician started active maintenance work.",
            assignment_id=open_assign.id,
            update_id=upd_row.id if upd_row is not None else None,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.work_started",
        title=f"Work Started on {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} has started maintenance work on your complaint "
            f"'{complaint.title}' ({complaint.reference_no})."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    notify_active_admins(
        category="complaint",
        event_type="complaint.work_started",
        title=f"Work Started: {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} started work on complaint "
            f"{complaint.reference_no} ('{complaint.title}')."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.work_started",
        actor=staff_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "accepted",
            "to_status": "in_progress",
            "assignment_id": open_assign.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return resolve_complaint_by_identifier(complaint.reference_no) or complaint


def post_staff_progress_update(
    staff_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> Complaint:
    """Append a student-visible progress update while task is `in_progress`."""
    complaint, open_assign = _get_and_verify_staff_task(
        staff_user,
        complaint_identifier,
        for_update=True,
    )

    if complaint.status != "in_progress":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Progress updates can only be added when status is 'in_progress' "
                f"(current status: '{complaint.status}')."
            ),
            409,
        )

    raw_body = str(
        payload.get("body") or payload.get("note") or payload.get("message") or ""
    ).strip()
    if not raw_body:
        raise AuthServiceError(
            "validation_error",
            "Progress update note is required and cannot be empty.",
            400,
        )
    if len(raw_body) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Progress update note must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    upd = ComplaintUpdate(
        complaint_id=complaint.id,
        assignment_id=open_assign.id,
        author_user_id=staff_user.id,
        update_type="progress",
        body=raw_body,
    )
    db.session.add(upd)
    db.session.flush()

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=staff_user.id,
            action="progress_updated",
            from_status="in_progress",
            to_status="in_progress",
            note=raw_body,
            assignment_id=open_assign.id,
            update_id=upd.id,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.progress_updated",
        title=f"Progress Update on {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} posted an update on {complaint.reference_no}: {raw_body[:200]}"
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    notify_active_admins(
        category="complaint",
        event_type="complaint.progress_updated",
        title=f"Staff Update: {complaint.reference_no}",
        message=f"{staff_user.full_name} updated {complaint.reference_no}: {raw_body[:200]}",
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.progress_updated",
        actor=staff_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "status": "in_progress",
            "update_id": upd.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return resolve_complaint_by_identifier(complaint.reference_no) or complaint


def complete_staff_task(
    staff_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> Complaint:
    """Mark an `in_progress` task as `completed` with a mandatory completion note."""
    complaint, open_assign = _get_and_verify_staff_task(
        staff_user,
        complaint_identifier,
        for_update=True,
    )

    if complaint.status != "in_progress":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot complete task when status is '{complaint.status}'. "
                "Task must be in 'in_progress' status."
            ),
            409,
        )

    raw_note = str(
        payload.get("note")
        or payload.get("completion_note")
        or payload.get("completionNote")
        or payload.get("body")
        or payload.get("message")
        or ""
    ).strip()
    if not raw_note:
        raise AuthServiceError(
            "validation_error",
            "A completion summary note is required when marking a task as completed.",
            400,
        )
    if len(raw_note) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Completion note must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    upd = ComplaintUpdate(
        complaint_id=complaint.id,
        assignment_id=open_assign.id,
        author_user_id=staff_user.id,
        update_type="completion",
        body=raw_note,
    )
    db.session.add(upd)
    db.session.flush()

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="completed",
            completed_at=now,
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=staff_user.id,
            action="completed",
            from_status="in_progress",
            to_status="completed",
            note=raw_note,
            assignment_id=open_assign.id,
            update_id=upd.id,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.completed",
        title=f"Maintenance Work Completed: {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} marked work on '{complaint.title}' ({complaint.reference_no}) "
            f"as completed: {raw_note[:200]}"
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    notify_active_admins(
        category="complaint",
        event_type="complaint.completed",
        title=f"Ready for Warden Verification: {complaint.reference_no}",
        message=(
            f"{staff_user.full_name} completed work on {complaint.reference_no} "
            f"('{complaint.title}'). Ready for verification and closure."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.completed",
        actor=staff_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "in_progress",
            "to_status": "completed",
            "assignment_id": open_assign.id,
            "update_id": upd.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return resolve_complaint_by_identifier(complaint.reference_no) or complaint
