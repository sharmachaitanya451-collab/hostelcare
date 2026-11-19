"""Admin/warden complaint lifecycle management, assignment, and internal notes service.

ARCHITECTURAL ISOLATION NOTE:
This is the ONLY complaint service module permitted to import `ComplaintInternalNote`
from `app.models.complaint_internal_notes`. Student and staff modules must never import it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.auth.service import AuthServiceError, _resolve_user_by_identifier
from app.complaints.serializers import (
    _build_common_complaint_fields,
    _fmt_datetime,
    complaint_load_options,
    get_open_assignment,
    resolve_complaint_by_identifier,
)
from app.extensions import db
from app.models.complaint_internal_notes import ComplaintInternalNote
from app.models.complaints import (
    Complaint,
    ComplaintAssignment,
    ComplaintHistory,
)
from app.models.identity import StaffProfile, User
from app.notifications.service import create_notification

_VALID_PRIORITIES = {"low", "medium", "high"}
_PRE_ACCEPTANCE_STATUSES = {"submitted", "under_review", "assigned"}


def _ensure_active_admin(admin_user: User) -> None:
    if admin_user.role != "admin" or admin_user.status != "active":
        raise AuthServiceError(
            "forbidden_role",
            "Administrator privileges are required for this action.",
            403,
        )


def serialize_internal_note(note: ComplaintInternalNote) -> dict[str, Any]:
    """Serialize an admin-only `ComplaintInternalNote`."""
    author = note.author
    author_name = author.full_name if author else "Hostel Warden"
    author_role = (author.designation or "Hostel Warden") if author else "Hostel Warden"
    return {
        "id": note.id,
        "complaint_id": note.complaint_id,
        "author_user_id": str(author.public_id) if author else None,
        "by": author_name,
        "author_name": author_name,
        "role": author_role,
        "author_role": author_role,
        "body": note.body,
        "note": note.body,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "time": _fmt_datetime(note.created_at),
    }


def serialize_previous_assignment(assign: ComplaintAssignment) -> dict[str, Any]:
    """Serialize an ended `ComplaintAssignment` for the admin detail view."""
    stp = assign.staff
    stf_user = stp.user if stp is not None else None
    staff_name = stf_user.full_name if stf_user is not None else "Maintenance Staff"
    staff_role = stp.trade if stp is not None else "Maintenance Staff"
    return {
        "id": assign.id,
        "staffId": str(stf_user.public_id) if stf_user is not None else None,
        "staffName": staff_name,
        "role": staff_role,
        "assignedAt": _fmt_datetime(assign.assigned_at),
        "endedAt": _fmt_datetime(assign.ended_at),
        "instructions": assign.instructions,
        "note": assign.end_note or assign.instructions or "Reassigned / Ended",
    }


def _load_internal_notes_for_complaint(complaint_id: int) -> list[ComplaintInternalNote]:
    stmt = (
        select(ComplaintInternalNote)
        .options(selectinload(ComplaintInternalNote.author))
        .where(ComplaintInternalNote.complaint_id == complaint_id)
        .order_by(ComplaintInternalNote.created_at.asc(), ComplaintInternalNote.id.asc())
    )
    return list(db.session.execute(stmt).scalars().all())


def serialize_complaint_for_admin(
    complaint: Complaint,
    internal_notes: list[ComplaintInternalNote] | None = None,
) -> dict[str, Any]:
    """Serialize full complaint details including active/previous assignments and internal notes."""
    data = _build_common_complaint_fields(complaint, include_admin_history_notes=True)

    open_assign = get_open_assignment(complaint)
    instructions = open_assign.instructions if open_assign is not None else None
    data["instructions"] = instructions
    data["assignmentNotes"] = instructions

    ended_assignments = sorted(
        [a for a in (complaint.assignments or []) if a.ended_at is not None],
        key=lambda a: (a.assigned_at or 0, a.id or 0),
    )
    data["previousAssignments"] = [serialize_previous_assignment(a) for a in ended_assignments]

    notes_list = (
        internal_notes
        if internal_notes is not None
        else _load_internal_notes_for_complaint(complaint.id)
    )
    serialized_notes = [serialize_internal_note(n) for n in notes_list]
    data["internalNotes"] = serialized_notes
    data["internal_notes"] = serialized_notes
    return data


def _normalize_status_param(raw: str | None) -> str | None:
    if not raw:
        return None
    norm = raw.strip().lower().replace(" ", "_")
    if norm in ("all", ""):
        return None
    if norm == "resolved":
        return "completed"
    return norm


def _parse_filter_date(raw: str | None) -> date | None:
    if not raw:
        return None
    val = raw.strip()
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except ValueError:
        pass
    parts = val.split("/")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def list_admin_complaints(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return all complaints for admin review with optional filtering and search."""
    params = filters or {}
    stmt = (
        select(Complaint)
        .options(*complaint_load_options())
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
    )

    status_filter = _normalize_status_param(params.get("status"))
    if status_filter:
        stmt = stmt.where(Complaint.status == status_filter)

    priority_filter = str(params.get("priority") or "").strip().lower()
    if priority_filter and priority_filter != "all":
        stmt = stmt.where(Complaint.priority == priority_filter)

    complaints = list(db.session.execute(stmt).scalars().all())

    # Apply flexible in-memory / relational filters for category, staff, block, date, and search
    cat_filter = str(params.get("category") or "").strip()
    if cat_filter and cat_filter.lower() != "all":
        if cat_filter.lower() in ("uncategorized", "general / custom"):
            complaints = [c for c in complaints if not c.category]
        else:
            complaints = [c for c in complaints if (c.category or "").lower() == cat_filter.lower()]

    staff_filter = str(
        params.get("assigned_staff") or params.get("staff") or params.get("staff_id") or ""
    ).strip()
    if staff_filter and staff_filter.upper() != "ALL":
        if staff_filter.upper() == "UNASSIGNED":
            complaints = [c for c in complaints if get_open_assignment(c) is None]
        else:
            sf_lower = staff_filter.lower()
            filtered_by_staff: list[Complaint] = []
            for c in complaints:
                oa = get_open_assignment(c)
                if oa is not None and oa.staff is not None:
                    stp = oa.staff
                    stf_user = stp.user
                    code = stp.staff_code.lower() if stp.staff_code else ""
                    if stf_user is not None and (
                        str(stf_user.public_id).lower() == sf_lower
                        or str(stf_user.id) == sf_lower
                        or code == sf_lower
                        or sf_lower in stf_user.full_name.lower()
                    ):
                        filtered_by_staff.append(c)
            complaints = filtered_by_staff

    block_filter = str(params.get("block") or "").strip().lower()
    if block_filter and block_filter != "all":
        filtered_by_block: list[Complaint] = []
        for c in complaints:
            blk = c.room.block if (c.room and c.room.block) else c.block
            if blk and (blk.code.lower() == block_filter or block_filter in blk.name.lower()):
                filtered_by_block.append(c)
        complaints = filtered_by_block

    exact_date = _parse_filter_date(params.get("date"))
    date_from = _parse_filter_date(params.get("date_from"))
    date_to = _parse_filter_date(params.get("date_to"))

    if exact_date:
        complaints = [
            c
            for c in complaints
            if c.created_at and c.created_at.astimezone(UTC).date() == exact_date
        ]
    if date_from:
        complaints = [
            c
            for c in complaints
            if c.created_at and c.created_at.astimezone(UTC).date() >= date_from
        ]
    if date_to:
        complaints = [
            c for c in complaints if c.created_at and c.created_at.astimezone(UTC).date() <= date_to
        ]

    q = str(params.get("q") or params.get("search") or "").strip().lower()
    if q:
        matched: list[Complaint] = []
        for c in complaints:
            sp = c.student
            stu_user = sp.user if sp is not None else None
            stu_name = stu_user.full_name.lower() if stu_user is not None else ""
            stu_roll = sp.roll_number.lower() if sp is not None else ""
            rm_num = c.room.room_number.lower() if c.room else ""
            loc_det = (c.location_detail or "").lower()
            haystack = " ".join(
                [
                    c.reference_no.lower(),
                    c.title.lower(),
                    c.description.lower(),
                    (c.category or "general").lower(),
                    stu_name,
                    stu_roll,
                    rm_num,
                    loc_det,
                ]
            )
            if q in haystack:
                matched.append(c)
        complaints = matched

    # Bulk load internal notes for all returned complaints
    comp_ids = [c.id for c in complaints]
    notes_by_comp: dict[int, list[ComplaintInternalNote]] = {cid: [] for cid in comp_ids}
    if comp_ids:
        notes_stmt = (
            select(ComplaintInternalNote)
            .options(selectinload(ComplaintInternalNote.author))
            .where(ComplaintInternalNote.complaint_id.in_(comp_ids))
            .order_by(ComplaintInternalNote.created_at.asc(), ComplaintInternalNote.id.asc())
        )
        for note_row in db.session.execute(notes_stmt).scalars().all():
            notes_by_comp.setdefault(note_row.complaint_id, []).append(note_row)

    return [serialize_complaint_for_admin(c, notes_by_comp.get(c.id, [])) for c in complaints]


def get_admin_complaint(complaint_identifier: str) -> dict[str, Any]:
    """Return full admin view of a single complaint, including internal notes."""
    complaint = resolve_complaint_by_identifier(complaint_identifier)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)
    return serialize_complaint_for_admin(complaint)


def update_admin_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Perform safe metadata updates or start review (`submitted -> under_review`).

    Arbitrary status changes via PATCH are explicitly rejected with HTTP 409.
    """
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    now = datetime.now(UTC)
    update_values: dict[str, Any] = {}
    metadata_changes: dict[str, Any] = {}

    # Check if status or action is provided
    requested_status = _normalize_status_param(payload.get("status"))
    requested_action = str(payload.get("action") or "").strip().lower()

    starting_review = requested_action in ("start_review", "review_started") or (
        requested_status == "under_review"
    )

    if requested_status is not None and requested_status != "under_review":
        raise AuthServiceError(
            "invalid_transition",
            (
                "Arbitrary status transitions are not permitted via PATCH. "
                "Use the dedicated assign, reassign, close, return-for-rework, "
                "reject, or reopen endpoints."
            ),
            409,
        )

    if starting_review:
        if complaint.status != "submitted":
            raise AuthServiceError(
                "invalid_transition",
                f"Cannot mark complaint 'under_review' from status '{complaint.status}'.",
                409,
            )
        update_values["status"] = "under_review"
        review_note = str(payload.get("note") or "").strip() or (
            "Complaint acknowledged by warden and placed under administrative review."
        )
        db.session.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                actor_user_id=admin_user.id,
                action="review_started",
                from_status="submitted",
                to_status="under_review",
                note=review_note[:2000],
            )
        )
        create_notification(
            recipient_user_id=complaint.student_user_id,
            category="complaint",
            event_type="complaint.review_started",
            title=f"Complaint {complaint.reference_no} Under Review",
            message=(
                f"Your complaint '{complaint.title}' ({complaint.reference_no}) "
                "is now under review by the hostel warden."
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )
        record_audit_event(
            action="complaint.review_started",
            actor=admin_user,
            target_type="complaint",
            target_id=complaint.reference_no,
            metadata={"from_status": "submitted", "to_status": "under_review"},
        )

    if "priority" in payload and payload["priority"] is not None:
        new_prio = str(payload["priority"]).strip().lower()
        if new_prio not in _VALID_PRIORITIES:
            raise AuthServiceError(
                "validation_error",
                "Priority must be one of: low, medium, high.",
                400,
            )
        if new_prio != complaint.priority:
            metadata_changes["old_priority"] = complaint.priority
            metadata_changes["new_priority"] = new_prio
            update_values["priority"] = new_prio

    if "category" in payload:
        raw_cat = payload.get("category")
        clean_cat = str(raw_cat).strip() if raw_cat is not None else None
        if clean_cat in ("", "General / Custom", "Uncategorized"):
            clean_cat = None
        if clean_cat is not None and len(clean_cat) > 80:
            raise AuthServiceError(
                "validation_error",
                "Category must not exceed 80 characters.",
                400,
            )
        if clean_cat != complaint.category:
            metadata_changes["old_category"] = complaint.category
            metadata_changes["new_category"] = clean_cat
            update_values["category"] = clean_cat

    if not update_values:
        raise AuthServiceError(
            "validation_error",
            "No valid review transition or metadata changes were provided.",
            400,
        )

    update_values["version"] = Complaint.version + 1
    update_values["updated_at"] = now

    db.session.execute(
        update(Complaint).where(Complaint.id == complaint.id).values(**update_values)
    )

    if metadata_changes:
        record_audit_event(
            action="complaint.metadata_updated",
            actor=admin_user,
            target_type="complaint",
            target_id=complaint.reference_no,
            metadata=metadata_changes,
        )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def _resolve_active_staff_target(payload: dict[str, Any]) -> User:
    raw_staff_id = (
        payload.get("staff_user_id")
        or payload.get("staff_id")
        or payload.get("staffId")
        or payload.get("assigned_staff_id")
    )
    if not raw_staff_id:
        raise AuthServiceError(
            "validation_error",
            "staff_id is required to assign a maintenance technician.",
            400,
        )
    staff_user = _resolve_user_by_identifier(str(raw_staff_id), expected_role="staff")
    if staff_user is None or staff_user.role != "staff" or staff_user.staff_profile is None:
        raise AuthServiceError("staff_not_found", "Maintenance staff member not found.", 404)
    if staff_user.status != "active":
        raise AuthServiceError(
            "staff_inactive",
            "Cannot assign tasks to an inactive staff account.",
            400,
        )
    return staff_user


def assign_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Assign a complaint (`submitted | under_review -> assigned`) to an active staff member."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status not in ("submitted", "under_review"):
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot perform initial assignment when complaint status is '{complaint.status}'. "
                "Initial assignment requires 'submitted' or 'under_review' status."
            ),
            409,
        )

    staff_user = _resolve_active_staff_target(payload)

    raw_instructions = str(
        payload.get("instructions")
        or payload.get("assignment_notes")
        or payload.get("assignmentNotes")
        or payload.get("note")
        or ""
    ).strip()
    if len(raw_instructions) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Assignment instructions must not exceed 2000 characters.",
            400,
        )
    clean_instructions = raw_instructions or None

    now = datetime.now(UTC)
    prev_status = complaint.status

    # Ensure no lingering open assignment exists
    existing_open = db.session.execute(
        select(ComplaintAssignment)
        .where(
            ComplaintAssignment.complaint_id == complaint.id,
            ComplaintAssignment.ended_at.is_(None),
        )
        .with_for_update(of=ComplaintAssignment)
    ).scalar_one_or_none()
    if existing_open is not None:
        ended_ts = max(now, existing_open.assigned_at) if existing_open.assigned_at else now
        db.session.execute(
            update(ComplaintAssignment)
            .where(ComplaintAssignment.id == existing_open.id)
            .values(
                ended_at=ended_ts,
                ended_by=admin_user.id,
                end_note="Superseded by new assignment.",
            )
        )
        db.session.flush()

    new_assign = ComplaintAssignment(
        complaint_id=complaint.id,
        staff_user_id=staff_user.id,
        assigned_by=admin_user.id,
        assigned_at=now,
        instructions=clean_instructions,
    )
    db.session.add(new_assign)
    db.session.flush()

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="assigned",
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    trade = staff_user.staff_profile.trade if staff_user.staff_profile else "Duty Staff"
    hist_note = f"Assigned to {staff_user.full_name} ({trade})."

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="assigned",
            from_status=prev_status,
            to_status="assigned",
            note=hist_note[:2000],
            assignment_id=new_assign.id,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.assigned",
        title=f"Technician Assigned to {complaint.reference_no}",
        message=(
            f"Your complaint '{complaint.title}' ({complaint.reference_no}) has been assigned "
            f"to {staff_user.full_name} ({trade})."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    create_notification(
        recipient_user_id=staff_user.id,
        category="complaint",
        event_type="complaint.assigned",
        title=f"New Work Order Assigned: {complaint.reference_no}",
        message=(
            f"You have been assigned to complaint {complaint.reference_no}: '{complaint.title}'."
            + (f" Instructions: {clean_instructions[:200]}" if clean_instructions else "")
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.assigned",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": prev_status,
            "to_status": "assigned",
            "staff_user_id": str(staff_user.public_id),
            "staff_name": staff_user.full_name,
            "assignment_id": new_assign.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def reassign_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Reassign an active complaint (`assigned | accepted | in_progress -> assigned`)."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status not in ("assigned", "accepted", "in_progress"):
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot reassign complaint when status is '{complaint.status}'. "
                "Reassignment is only permitted for 'assigned', 'accepted', "
                "or 'in_progress' tickets."
            ),
            409,
        )

    new_staff = _resolve_active_staff_target(payload)

    open_assign = db.session.execute(
        select(ComplaintAssignment)
        .options(selectinload(ComplaintAssignment.staff).selectinload(StaffProfile.user))
        .where(
            ComplaintAssignment.complaint_id == complaint.id,
            ComplaintAssignment.ended_at.is_(None),
        )
        .with_for_update(of=ComplaintAssignment)
    ).scalar_one_or_none()

    if open_assign is None:
        raise AuthServiceError(
            "no_active_assignment",
            "Complaint does not have an open assignment to reassign.",
            409,
        )

    if open_assign.staff_user_id == new_staff.id:
        raise AuthServiceError(
            "same_staff",
            "Complaint is already assigned to this staff member.",
            400,
        )

    raw_instructions = str(
        payload.get("instructions")
        or payload.get("assignment_notes")
        or payload.get("assignmentNotes")
        or payload.get("note")
        or ""
    ).strip()
    raw_reason = str(
        payload.get("reason") or payload.get("end_note") or raw_instructions or ""
    ).strip()
    if len(raw_instructions) > 2000 or len(raw_reason) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Reassignment instructions or reason must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    ended_ts = max(now, open_assign.assigned_at) if open_assign.assigned_at else now
    prev_status = complaint.status
    prev_stp = open_assign.staff
    prev_staff = prev_stp.user if prev_stp is not None else None
    prev_staff_name = prev_staff.full_name if prev_staff is not None else "Previous Technician"

    end_note = raw_reason or f"Reassigned to {new_staff.full_name}."

    # Step 1: Close current open assignment and flush so uq_assign_one_active is satisfied
    db.session.execute(
        update(ComplaintAssignment)
        .where(ComplaintAssignment.id == open_assign.id)
        .values(
            ended_at=ended_ts,
            ended_by=admin_user.id,
            end_note=end_note,
        )
    )
    db.session.flush()

    # Step 2: Insert new open assignment
    new_assign = ComplaintAssignment(
        complaint_id=complaint.id,
        staff_user_id=new_staff.id,
        assigned_by=admin_user.id,
        assigned_at=ended_ts,
        instructions=raw_instructions or None,
    )
    db.session.add(new_assign)
    db.session.flush()

    # Step 3: Reset complaint status to 'assigned' so new technician accepts and starts work
    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="assigned",
            version=Complaint.version + 1,
            updated_at=ended_ts,
        )
    )

    new_trade = new_staff.staff_profile.trade if new_staff.staff_profile else "Duty Staff"
    hist_note = f"Reassigned from {prev_staff_name} to {new_staff.full_name} ({new_trade})."

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="reassigned",
            from_status=prev_status,
            to_status="assigned",
            note=hist_note[:2000],
            assignment_id=new_assign.id,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.reassigned",
        title=f"Technician Reassigned for {complaint.reference_no}",
        message=(
            f"Your complaint '{complaint.title}' ({complaint.reference_no}) has been reassigned "
            f"to {new_staff.full_name} ({new_trade})."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    if open_assign.staff_user_id:
        create_notification(
            recipient_user_id=open_assign.staff_user_id,
            category="complaint",
            event_type="complaint.reassigned_out",
            title=f"Work Order Reassigned: {complaint.reference_no}",
            message=(
                f"Work order {complaint.reference_no} ('{complaint.title}') has been reassigned "
                f"to {new_staff.full_name}."
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )

    create_notification(
        recipient_user_id=new_staff.id,
        category="complaint",
        event_type="complaint.assigned",
        title=f"New Work Order Assigned: {complaint.reference_no}",
        message=(
            f"You have been assigned to complaint {complaint.reference_no}: '{complaint.title}'."
            + (f" Instructions: {raw_instructions[:200]}" if raw_instructions else "")
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.reassigned",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": prev_status,
            "to_status": "assigned",
            "previous_staff_user_id": str(prev_staff.public_id) if prev_staff else None,
            "new_staff_user_id": str(new_staff.public_id),
            "new_staff_name": new_staff.full_name,
            "previous_assignment_id": open_assign.id,
            "new_assignment_id": new_assign.id,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def add_complaint_internal_note(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append an admin-only private internal note to `complaint_internal_notes`."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    raw_body = str(
        payload.get("body") or payload.get("note") or payload.get("message") or ""
    ).strip()
    if not raw_body:
        raise AuthServiceError(
            "validation_error",
            "Internal note body is required and cannot be empty.",
            400,
        )
    if len(raw_body) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Internal note must not exceed 2000 characters.",
            400,
        )

    note_row = ComplaintInternalNote(
        complaint_id=complaint.id,
        author_user_id=admin_user.id,
        body=raw_body,
    )
    db.session.add(note_row)
    db.session.flush()

    # Never store the private note body in audit_logs metadata, complaint_history, or notifications
    record_audit_event(
        action="complaint.internal_note_added",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "note_id": note_row.id,
            "length": len(raw_body),
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def close_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify and close a `completed` complaint (`completed -> closed`)."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status != "completed":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot close complaint when status is '{complaint.status}'. "
                "Only 'completed' complaints can be verified and closed."
            ),
            409,
        )

    body_dict = payload or {}
    raw_note = str(body_dict.get("note") or body_dict.get("reason") or "").strip()
    if len(raw_note) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Closure note must not exceed 2000 characters.",
            400,
        )
    close_note = raw_note or "Resolution verified by warden and ticket closed."

    now = datetime.now(UTC)
    completed_ts = complaint.completed_at or now
    closed_ts = max(now, completed_ts)

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="closed",
            completed_at=completed_ts,
            closed_at=closed_ts,
            version=Complaint.version + 1,
            updated_at=closed_ts,
        )
    )

    open_assign = get_open_assignment(complaint)

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="closed",
            from_status="completed",
            to_status="closed",
            note=close_note,
            assignment_id=open_assign.id if open_assign else None,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.closed",
        title=f"Complaint {complaint.reference_no} Verified & Closed",
        message=(
            f"Your complaint '{complaint.title}' ({complaint.reference_no}) has been "
            f"verified and closed by the warden."
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    if open_assign is not None and open_assign.staff_user_id:
        create_notification(
            recipient_user_id=open_assign.staff_user_id,
            category="complaint",
            event_type="complaint.closed",
            title=f"Work Order Closed: {complaint.reference_no}",
            message=(
                f"Warden verified and closed work order {complaint.reference_no} "
                f"('{complaint.title}')."
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )

    record_audit_event(
        action="complaint.closed",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "completed",
            "to_status": "closed",
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def return_complaint_for_rework(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Return a `completed` complaint to `in_progress` for rework with a mandatory reason."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status != "completed":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot return complaint for rework when status is '{complaint.status}'. "
                "Only 'completed' complaints can be returned for rework."
            ),
            409,
        )

    raw_reason = str(
        payload.get("reason") or payload.get("note") or payload.get("rework_note") or ""
    ).strip()
    if not raw_reason:
        raise AuthServiceError(
            "validation_error",
            "A mandatory reason/note is required when returning a complaint for rework.",
            400,
        )
    if len(raw_reason) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Rework reason must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    open_assign = get_open_assignment(complaint)

    # Clear completed_at so completed_at_consistency CHECK constraint holds for 'in_progress'
    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="in_progress",
            completed_at=None,
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="returned_for_rework",
            from_status="completed",
            to_status="in_progress",
            note=raw_reason,
            assignment_id=open_assign.id if open_assign else None,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.returned_for_rework",
        title=f"Follow-Up Inspection Ordered: {complaint.reference_no}",
        message=(
            f"The warden returned complaint '{complaint.title}' ({complaint.reference_no}) "
            f"to maintenance staff for further work: {raw_reason[:200]}"
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    if open_assign is not None and open_assign.staff_user_id:
        create_notification(
            recipient_user_id=open_assign.staff_user_id,
            category="complaint",
            event_type="complaint.returned_for_rework",
            title=f"Rework Requested: {complaint.reference_no}",
            message=(
                f"Warden returned {complaint.reference_no} ('{complaint.title}') "
                f"for further work: {raw_reason[:200]}"
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )

    record_audit_event(
        action="complaint.returned",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "completed",
            "to_status": "in_progress",
            "reason": raw_reason[:300],
            "assignment_id": open_assign.id if open_assign else None,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def reject_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Reject a pre-acceptance complaint (`submitted | under_review | assigned -> rejected`)."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status not in _PRE_ACCEPTANCE_STATUSES:
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot reject complaint when status is '{complaint.status}'. "
                "Complaints can only be rejected before work is accepted by staff "
                "('submitted', 'under_review', or 'assigned')."
            ),
            409,
        )

    raw_reason = str(
        payload.get("reason")
        or payload.get("rejection_reason")
        or payload.get("rejectionReason")
        or payload.get("note")
        or ""
    ).strip()
    if not raw_reason:
        raise AuthServiceError(
            "validation_error",
            "A mandatory rejection reason is required when rejecting a complaint.",
            400,
        )
    if len(raw_reason) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Rejection reason must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)
    prev_status = complaint.status

    open_assign = db.session.execute(
        select(ComplaintAssignment)
        .where(
            ComplaintAssignment.complaint_id == complaint.id,
            ComplaintAssignment.ended_at.is_(None),
        )
        .with_for_update(of=ComplaintAssignment)
    ).scalar_one_or_none()

    if open_assign is not None:
        ended_ts = max(now, open_assign.assigned_at) if open_assign.assigned_at else now
        db.session.execute(
            update(ComplaintAssignment)
            .where(ComplaintAssignment.id == open_assign.id)
            .values(
                ended_at=ended_ts,
                ended_by=admin_user.id,
                end_note=raw_reason,
            )
        )
        db.session.flush()
        if open_assign.staff_user_id:
            create_notification(
                recipient_user_id=open_assign.staff_user_id,
                category="complaint",
                event_type="complaint.rejected",
                title=f"Work Order Cancelled: {complaint.reference_no}",
                message=(
                    f"Complaint {complaint.reference_no} ('{complaint.title}') was rejected "
                    f"by the warden during review: {raw_reason[:200]}"
                ),
                entity_type="complaint",
                entity_ref=complaint.reference_no,
            )

    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="rejected",
            rejection_reason=raw_reason,
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="rejected",
            from_status=prev_status,
            to_status="rejected",
            note=raw_reason,
            assignment_id=open_assign.id if open_assign else None,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.rejected",
        title=f"Complaint {complaint.reference_no} Not Approved",
        message=(
            f"Your complaint '{complaint.title}' ({complaint.reference_no}) was rejected "
            f"during warden review. Reason: {raw_reason[:200]}"
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.rejected",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": prev_status,
            "to_status": "rejected",
            "reason": raw_reason[:300],
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)


def reopen_complaint(
    admin_user: User,
    complaint_identifier: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Reopen a `closed` complaint (`closed -> under_review`) with a mandatory reason."""
    _ensure_active_admin(admin_user)

    complaint = resolve_complaint_by_identifier(complaint_identifier, for_update=True)
    if complaint is None:
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status != "closed":
        raise AuthServiceError(
            "invalid_transition",
            (
                f"Cannot reopen complaint when status is '{complaint.status}'. "
                "Only 'closed' complaints can be reopened."
            ),
            409,
        )

    raw_reason = str(payload.get("reason") or payload.get("note") or "").strip()
    if not raw_reason:
        raise AuthServiceError(
            "validation_error",
            "A mandatory reason is required to reopen a closed complaint.",
            400,
        )
    if len(raw_reason) > 2000:
        raise AuthServiceError(
            "validation_error",
            "Reopen reason must not exceed 2000 characters.",
            400,
        )

    now = datetime.now(UTC)

    open_assign = db.session.execute(
        select(ComplaintAssignment)
        .where(
            ComplaintAssignment.complaint_id == complaint.id,
            ComplaintAssignment.ended_at.is_(None),
        )
        .with_for_update(of=ComplaintAssignment)
    ).scalar_one_or_none()

    if open_assign is not None:
        ended_ts = max(now, open_assign.assigned_at) if open_assign.assigned_at else now
        db.session.execute(
            update(ComplaintAssignment)
            .where(ComplaintAssignment.id == open_assign.id)
            .values(
                ended_at=ended_ts,
                ended_by=admin_user.id,
                end_note=raw_reason,
            )
        )
        db.session.flush()

    # Clear completed_at and closed_at to satisfy completed_at_consistency and closed_at_consistency
    db.session.execute(
        update(Complaint)
        .where(Complaint.id == complaint.id)
        .values(
            status="under_review",
            completed_at=None,
            closed_at=None,
            version=Complaint.version + 1,
            updated_at=now,
        )
    )

    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=admin_user.id,
            action="reopened",
            from_status="closed",
            to_status="under_review",
            note=raw_reason,
            assignment_id=open_assign.id if open_assign else None,
        )
    )

    create_notification(
        recipient_user_id=complaint.student_user_id,
        category="complaint",
        event_type="complaint.reopened",
        title=f"Complaint {complaint.reference_no} Reopened",
        message=(
            f"The warden reopened your complaint '{complaint.title}' ({complaint.reference_no}) "
            f"for further review. Reason: {raw_reason[:200]}"
        ),
        entity_type="complaint",
        entity_ref=complaint.reference_no,
    )

    record_audit_event(
        action="complaint.reopened",
        actor=admin_user,
        target_type="complaint",
        target_id=complaint.reference_no,
        metadata={
            "from_status": "closed",
            "to_status": "under_review",
            "reason": raw_reason[:300],
            "ended_assignment_id": open_assign.id if open_assign else None,
        },
    )

    db.session.commit()
    db.session.expire_all()
    return get_admin_complaint(complaint.reference_no)
