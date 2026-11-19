"""Role-isolated serializers and lookup helpers for complaints and tasks.

SECURITY & PRIVACY INVARIANT:
This module must NEVER import `ComplaintInternalNote` or `app.models.complaint_internal_notes`.
Only `app.complaints.admin_service` may access or serialize private internal notes.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.complaints import (
    Complaint,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintHistory,
    ComplaintUpdate,
)
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.rooms import Room

STATUS_LABELS: dict[str, str] = {
    "submitted": "Submitted",
    "under_review": "Under Review",
    "assigned": "Assigned",
    "accepted": "Accepted",
    "in_progress": "In Progress",
    "completed": "Resolved",
    "closed": "Closed",
    "rejected": "Rejected",
}

PRIORITY_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

HISTORY_ACTION_LABELS: dict[str, str] = {
    "submitted": "Complaint Submitted",
    "review_started": "Under Warden Review",
    "assigned": "Assigned to Duty Staff",
    "reassigned": "Reassigned to Duty Staff",
    "accepted": "Assignment Accepted by Staff",
    "work_started": "Maintenance Work Started",
    "progress_updated": "Progress Update Logged",
    "completed": "Work Completed (Resolved)",
    "returned_for_rework": "Returned for Further Work",
    "closed": "Ticket Verified & Closed",
    "rejected": "Complaint Rejected",
    "reopened": "Complaint Reopened by Warden",
}


def complaint_load_options():
    """Return SQLAlchemy loader options for `Complaint` (excluding internal notes)."""
    return (
        selectinload(Complaint.student).selectinload(StudentProfile.user),
        selectinload(Complaint.room).selectinload(Room.block),
        selectinload(Complaint.block),
        selectinload(Complaint.assignments)
        .selectinload(ComplaintAssignment.staff)
        .selectinload(StaffProfile.user),
        selectinload(Complaint.assignments).selectinload(ComplaintAssignment.assigner),
        selectinload(Complaint.assignments).selectinload(ComplaintAssignment.ender),
        selectinload(Complaint.updates)
        .selectinload(ComplaintUpdate.author)
        .selectinload(User.staff_profile),
        selectinload(Complaint.history)
        .selectinload(ComplaintHistory.actor)
        .selectinload(User.staff_profile),
        selectinload(Complaint.history).selectinload(ComplaintHistory.update),
        selectinload(Complaint.history)
        .selectinload(ComplaintHistory.assignment)
        .selectinload(ComplaintAssignment.staff)
        .selectinload(StaffProfile.user),
        selectinload(Complaint.attachments),
    )


def complaint_exists_by_identifier(identifier: str) -> bool:
    """Return True if a complaint exists by `reference_no` or integer `id`."""
    raw = str(identifier or "").strip()
    if not raw:
        return False

    if raw.upper().startswith("CMP-"):
        found_id = db.session.execute(
            select(Complaint.id).where(Complaint.reference_no == raw.upper())
        ).scalar_one_or_none()
        if found_id is not None:
            return True

    if raw.isdigit():
        found_id = db.session.execute(
            select(Complaint.id).where(Complaint.id == int(raw))
        ).scalar_one_or_none()
        if found_id is not None:
            return True

    return False


def resolve_complaint_by_identifier(
    identifier: str,
    *,
    for_update: bool = False,
    student_user_id: int | None = None,
) -> Complaint | None:
    """Resolve a `Complaint` by `reference_no` (`CMP-...`) or integer `id`.

    When `student_user_id` is provided, the SQL query enforces
    `Complaint.student_user_id == student_user_id` directly in the WHERE clause
    before returning or loading any complaint record.
    """
    raw = str(identifier or "").strip()
    if not raw:
        return None

    stmt = select(Complaint)
    if student_user_id is not None:
        stmt = stmt.where(Complaint.student_user_id == student_user_id)
    if not for_update:
        stmt = stmt.options(*complaint_load_options())

    # 1. Reference number (e.g. CMP-2026-00001)
    if raw.upper().startswith("CMP-"):
        q = stmt.where(Complaint.reference_no == raw.upper())
        if for_update:
            q = q.with_for_update(of=Complaint)
        comp = db.session.execute(q).scalar_one_or_none()
        if comp is not None:
            return comp

    # 2. Integer primary key
    if raw.isdigit():
        q = stmt.where(Complaint.id == int(raw))
        if for_update:
            q = q.with_for_update(of=Complaint)
        comp = db.session.execute(q).scalar_one_or_none()
        if comp is not None:
            return comp

    return None


def _fmt_date(dt) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).strftime("%d/%m/%Y")


def _fmt_datetime(dt) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).strftime("%d/%m/%Y, %H:%M UTC")


def get_open_assignment(complaint: Complaint) -> ComplaintAssignment | None:
    """Return the single active (`ended_at IS NULL`) assignment for `complaint`, if any."""
    for assign in complaint.assignments or []:
        if assign.ended_at is None:
            return assign
    return None


def serialize_complaint_attachment(
    att: ComplaintAttachment,
    complaint_ref: str,
) -> dict[str, Any]:
    """Serialize safe public metadata for a complaint photo attachment."""
    pub_id = str(att.public_id)
    url = f"/api/v1/complaints/{complaint_ref}/attachments/{pub_id}"
    return {
        "id": pub_id,
        "public_id": pub_id,
        "publicId": pub_id,
        "filename": att.original_filename,
        "original_filename": att.original_filename,
        "originalFilename": att.original_filename,
        "mime_type": att.mime_type,
        "mimeType": att.mime_type,
        "file_size_bytes": att.file_size_bytes,
        "fileSizeBytes": att.file_size_bytes,
        "created_at": att.created_at.isoformat() if att.created_at else None,
        "createdAt": att.created_at.isoformat() if att.created_at else None,
        "url": url,
    }


def serialize_complaint_update(upd: ComplaintUpdate) -> dict[str, Any]:
    """Serialize a public progress or completion update posted by staff."""
    author = upd.author
    author_name = author.full_name if author else "Duty Staff"
    author_role = "Duty Staff"
    if author and author.staff_profile:
        author_role = author.staff_profile.trade
    elif author and author.designation:
        author_role = author.designation

    return {
        "id": upd.id,
        "complaint_id": upd.complaint_id,
        "assignment_id": upd.assignment_id,
        "author_user_id": str(author.public_id) if author else None,
        "authorName": author_name,
        "author_name": author_name,
        "authorRole": author_role,
        "author_role": author_role,
        "update_type": upd.update_type,
        "updateType": upd.update_type,
        "body": upd.body,
        "note": upd.body,
        "message": upd.body,
        "created_at": upd.created_at.isoformat() if upd.created_at else None,
        "timestamp": _fmt_datetime(upd.created_at),
        "time": _fmt_datetime(upd.created_at),
    }


def _strip_legacy_instruction_suffix(note_text: str) -> str:
    """Remove legacy warden note / instruction suffixes from assignment history text."""
    lower = note_text.lower()
    cut_idx = -1
    for marker in (" warden note:", " instructions:"):
        idx = lower.find(marker)
        if idx != -1 and (cut_idx == -1 or idx < cut_idx):
            cut_idx = idx
    if cut_idx != -1:
        cleaned = note_text[:cut_idx].rstrip()
        if cleaned and not cleaned.endswith("."):
            cleaned += "."
        return cleaned
    return note_text


def serialize_history_entry(
    h: ComplaintHistory,
    *,
    sanitize_internal_notes: bool = True,
) -> dict[str, Any]:
    """Serialize a `ComplaintHistory` row, scrubbing internal notes for non-admin views."""
    actor = h.actor
    actor_name = actor.full_name if actor else "System"
    actor_role = "System"
    if actor:
        if actor.role == "admin":
            actor_role = actor.designation or "Hostel Warden"
        elif actor.role == "staff":
            actor_role = (
                actor.staff_profile.trade
                if actor.staff_profile
                else (actor.designation or "Duty Staff")
            )
        elif actor.role == "student":
            actor_role = "Resident Student"

    note_text = h.note
    if not note_text and h.update is not None:
        note_text = h.update.body
    elif (
        not note_text
        and h.action in ("assigned", "reassigned")
        and h.assignment is not None
        and h.assignment.staff is not None
    ):
        stp = h.assignment.staff
        stf_user = stp.user
        staff_name = stf_user.full_name if stf_user else "Duty Staff"
        trade = stp.trade or "Duty Staff"
        verb = "Reassigned to" if h.action == "reassigned" else "Assigned to"
        note_text = f"{verb} {staff_name} ({trade})."

    if sanitize_internal_notes:
        if h.action == "assigned":
            if h.assignment is not None and h.assignment.staff is not None:
                stp = h.assignment.staff
                stf_user = stp.user
                staff_name = stf_user.full_name if stf_user else "Duty Staff"
                trade = stp.trade or "Duty Staff"
                note_text = f"Assigned to {staff_name} ({trade})."
            elif note_text:
                note_text = _strip_legacy_instruction_suffix(note_text)
        elif h.action == "reassigned":
            if note_text:
                note_text = _strip_legacy_instruction_suffix(note_text)
            if not note_text and h.assignment is not None and h.assignment.staff is not None:
                stp = h.assignment.staff
                stf_user = stp.user
                staff_name = stf_user.full_name if stf_user else "Duty Staff"
                trade = stp.trade or "Duty Staff"
                note_text = f"Reassigned to {staff_name} ({trade})."
        elif h.action == "review_started":
            note_text = "Complaint acknowledged by warden and placed under administrative review."

    return {
        "id": h.id,
        "action": h.action,
        "action_code": h.action,
        "actionLabel": HISTORY_ACTION_LABELS.get(h.action, h.action),
        "from_status": h.from_status,
        "to_status": h.to_status,
        "by": actor_name,
        "actor_name": actor_name,
        "role": actor_role,
        "actor_role": actor_role,
        "time": _fmt_datetime(h.created_at),
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "note": note_text,
        "assignment_id": h.assignment_id,
        "update_id": h.update_id,
    }


def _build_common_complaint_fields(
    complaint: Complaint,
    *,
    include_admin_history_notes: bool = False,
) -> dict[str, Any]:
    """Build fields shared across student, staff, and admin views (never internal notes)."""
    sp = complaint.student
    stu_user = sp.user if sp is not None else None
    student_roll = sp.roll_number if sp is not None else "UNASSIGNED"
    student_name = stu_user.full_name if stu_user is not None else "Resident Student"
    student_public_id = str(stu_user.public_id) if stu_user is not None else None

    if complaint.location_type == "room" and complaint.room is not None:
        room_label = complaint.room.room_number
        room_number = complaint.room.room_number
        block_name = complaint.room.block.name if complaint.room.block else "Hostel"
        block_code = complaint.room.block.code if complaint.room.block else None
    else:
        detail = complaint.location_detail or "Common Area"
        room_label = f"Common Area ({detail})"
        room_number = None
        block_name = complaint.block.name if complaint.block else "Campus Common Area"
        block_code = complaint.block.code if complaint.block else None

    open_assign = get_open_assignment(complaint)
    assigned_staff_id = None
    assigned_staff_name = None
    assigned_staff_role = None
    assigned_staff_contact = None
    assigned_date = None
    accepted_at_iso = None
    started_at_iso = None

    if open_assign is not None and open_assign.staff is not None:
        stp = open_assign.staff
        stf_user = stp.user
        assigned_staff_id = str(stf_user.public_id) if stf_user is not None else None
        assigned_staff_name = stf_user.full_name if stf_user is not None else None
        assigned_staff_role = stp.trade or "Maintenance Staff"
        assigned_staff_contact = stf_user.phone if stf_user is not None else None
        assigned_date = _fmt_datetime(open_assign.assigned_at)
        accepted_at_iso = open_assign.accepted_at.isoformat() if open_assign.accepted_at else None
        started_at_iso = open_assign.started_at.isoformat() if open_assign.started_at else None

    sorted_updates = sorted(
        complaint.updates or [],
        key=lambda u: (u.created_at or 0, u.id or 0),
    )
    serialized_updates = [serialize_complaint_update(u) for u in sorted_updates]

    completion_note = None
    for upd in reversed(sorted_updates):
        if upd.update_type == "completion":
            completion_note = upd.body
            break

    sorted_history = sorted(
        complaint.history or [],
        key=lambda h: (h.created_at or 0, h.id or 0),
    )
    serialized_history = [
        serialize_history_entry(h, sanitize_internal_notes=not include_admin_history_notes)
        for h in sorted_history
    ]

    rework_note = None
    for h_item in reversed(sorted_history):
        if h_item.action == "returned_for_rework" and h_item.note:
            rework_note = h_item.note
            break

    sorted_attachments = sorted(
        complaint.attachments or [],
        key=lambda a: (a.created_at or 0, a.id or 0),
    )
    serialized_attachments = [
        serialize_complaint_attachment(a, complaint.reference_no) for a in sorted_attachments
    ]

    category_display = complaint.category or "General / Custom"
    display_status = STATUS_LABELS.get(complaint.status, complaint.status)
    display_priority = PRIORITY_LABELS.get(complaint.priority, complaint.priority)

    return {
        "id": complaint.reference_no,
        "reference_no": complaint.reference_no,
        "referenceNo": complaint.reference_no,
        "public_id": complaint.reference_no,
        "publicId": complaint.reference_no,
        "student_user_id": student_public_id,
        "studentId": student_public_id,
        "studentName": student_name,
        "student_name": student_name,
        "studentRoll": student_roll,
        "student_roll": student_roll,
        "location_type": complaint.location_type,
        "locationType": complaint.location_type,
        "room_id": complaint.room_id,
        "roomId": complaint.room_id,
        "room_number": room_number,
        "roomNumber": room_number,
        "room": room_label,
        "block_id": complaint.block_id,
        "blockId": complaint.block_id,
        "block": block_name,
        "blockCode": block_code,
        "location_detail": complaint.location_detail,
        "locationDetail": complaint.location_detail,
        "title": complaint.title,
        "category": category_display,
        "raw_category": complaint.category,
        "description": complaint.description,
        "priority": complaint.priority,
        "displayPriority": display_priority,
        "status": complaint.status,
        "displayStatus": display_status,
        "rejection_reason": complaint.rejection_reason,
        "rejectionReason": complaint.rejection_reason,
        "completed_at": complaint.completed_at.isoformat() if complaint.completed_at else None,
        "completedAt": _fmt_datetime(complaint.completed_at),
        "closed_at": complaint.closed_at.isoformat() if complaint.closed_at else None,
        "closedAt": _fmt_datetime(complaint.closed_at),
        "created_at": complaint.created_at.isoformat() if complaint.created_at else None,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else None,
        "date": _fmt_date(complaint.created_at),
        "updatedDate": _fmt_date(complaint.updated_at),
        "version": complaint.version,
        "assignedStaffId": assigned_staff_id,
        "assigned_staff_id": assigned_staff_id,
        "assignedStaff": assigned_staff_name,
        "assigned_staff": assigned_staff_name,
        "assignedStaffRole": assigned_staff_role,
        "assigned_staff_role": assigned_staff_role,
        "assignedStaffContact": assigned_staff_contact,
        "assigned_staff_contact": assigned_staff_contact,
        "assignedDate": assigned_date,
        "accepted_at": accepted_at_iso,
        "started_at": started_at_iso,
        "completionNote": completion_note,
        "completion_note": completion_note,
        "reworkNote": rework_note,
        "rework_note": rework_note,
        "updates": serialized_updates,
        "history": serialized_history,
        "attachments": serialized_attachments,
    }


def serialize_complaint_for_student(complaint: Complaint) -> dict[str, Any]:
    """Serialize a complaint for the owning student.

    Strictly omits `internal_notes`, `internalNotes`, warden dispatch `instructions`,
    and `previousAssignments`.
    """
    return _build_common_complaint_fields(complaint)


def serialize_complaint_for_staff(complaint: Complaint) -> dict[str, Any]:
    """Serialize an assigned task for the assigned staff member.

    Includes warden dispatch `instructions` (`assignmentNotes`) for the active assignment,
    and strictly omits `internal_notes` / `internalNotes`.
    """
    data = _build_common_complaint_fields(complaint)
    open_assign = get_open_assignment(complaint)
    instructions = open_assign.instructions if open_assign is not None else None
    data["instructions"] = instructions
    data["assignmentNotes"] = instructions
    return data
