"""HTTP routes for student complaints, admin complaint management, and staff task execution."""

from __future__ import annotations

import json
import uuid
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from app.auth.security import login_required, require_role
from app.auth.service import AuthServiceError
from app.complaints.admin_service import (
    _ensure_active_admin,
    add_complaint_internal_note,
    assign_complaint,
    close_complaint,
    get_admin_complaint,
    list_admin_complaints,
    reassign_complaint,
    reject_complaint,
    reopen_complaint,
    return_complaint_for_rework,
    update_admin_complaint,
)
from app.complaints.attachment_service import resolve_attachment_file_path
from app.complaints.serializers import (
    resolve_complaint_by_identifier,
    serialize_complaint_for_staff,
    serialize_complaint_for_student,
)
from app.complaints.staff_service import (
    accept_staff_task,
    complete_staff_task,
    get_staff_task,
    list_staff_tasks,
    post_staff_progress_update,
    start_staff_task,
)
from app.complaints.student_service import (
    attach_student_complaint_photos,
    get_student_complaint,
    list_student_complaints,
    submit_student_complaint,
)
from app.extensions import db
from app.models.complaints import ComplaintAttachment
from app.models.rooms import Block

bp = Blueprint("complaints", __name__)


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _extract_uploaded_photos() -> list[FileStorage]:
    files: list[FileStorage] = []
    for key in ("photos", "attachments", "files"):
        files.extend(request.files.getlist(key))
    return files


def _extract_complaint_submission_payload_and_files() -> tuple[dict[str, Any], list[FileStorage]]:
    if request.mimetype == "multipart/form-data" or bool(request.files):
        payload: dict[str, Any] = {}
        raw_json_part = request.form.get("payload")
        if raw_json_part:
            try:
                parsed = json.loads(raw_json_part)
            except (ValueError, TypeError) as exc:
                raise AuthServiceError(
                    "validation_error",
                    "Malformed complaint payload.",
                    400,
                ) from exc
            if isinstance(parsed, dict):
                payload.update(parsed)

        for field_key in (
            "title",
            "category",
            "description",
            "priority",
            "location_type",
            "locationType",
            "location_detail",
            "locationDetail",
            "block_id",
            "blockId",
            "block_code",
        ):
            if field_key in request.form:
                payload[field_key] = request.form.get(field_key)

        return payload, _extract_uploaded_photos()

    return _json_body(), []


@bp.get("/api/v1/blocks")
@login_required
def list_active_blocks():
    """Return active hostel blocks for common-area complaint block selection."""
    blocks = list(
        db.session.execute(
            select(Block).where(Block.is_active.is_(True)).order_by(Block.code.asc())
        )
        .scalars()
        .all()
    )
    return (
        jsonify(
            {
                "blocks": [
                    {
                        "id": b.id,
                        "code": b.code,
                        "name": b.name,
                        "display_order": b.display_order,
                    }
                    for b in blocks
                ]
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# 1. Student Complaint Endpoints (`/api/v1/student/complaints/*`)
# ---------------------------------------------------------------------------


@bp.post("/api/v1/student/complaints")
@require_role("student")
def create_student_complaint_route():
    """Submit a new room or common-area maintenance complaint for the current student."""
    payload, uploaded_files = _extract_complaint_submission_payload_and_files()
    complaint = submit_student_complaint(g.current_user, payload, uploaded_files=uploaded_files)
    return jsonify({"complaint": serialize_complaint_for_student(complaint)}), 201


@bp.post("/api/v1/student/complaints/<complaint_id>/attachments")
@require_role("student")
def attach_student_complaint_photos_route(complaint_id: str):
    """Upload additional photo attachments (up to 3 total) to an owned complaint."""
    complaint = attach_student_complaint_photos(
        g.current_user, complaint_id, _extract_uploaded_photos()
    )
    return jsonify({"complaint": serialize_complaint_for_student(complaint)}), 201


@bp.get("/api/v1/student/complaints")
@require_role("student")
def list_student_complaints_route():
    """Return all complaints owned by the currently authenticated student."""
    status_filter = request.args.get("status")
    complaints = list_student_complaints(g.current_user, status_filter=status_filter)
    return (
        jsonify(
            {
                "complaints": [serialize_complaint_for_student(c) for c in complaints],
            }
        ),
        200,
    )


@bp.get("/api/v1/student/complaints/<complaint_id>")
@require_role("student")
def get_student_complaint_route(complaint_id: str):
    """Return a single complaint owned by the currently authenticated student."""
    complaint = get_student_complaint(g.current_user, complaint_id)
    return jsonify({"complaint": serialize_complaint_for_student(complaint)}), 200


@bp.get("/api/v1/student/complaints/<complaint_id>/history")
@require_role("student")
def get_student_complaint_history_route(complaint_id: str):
    """Return the visible timeline history for a single complaint owned by the student."""
    complaint = get_student_complaint(g.current_user, complaint_id)
    return jsonify({"history": serialize_complaint_for_student(complaint)["history"]}), 200


@bp.get("/api/v1/student/complaints/<complaint_id>/updates")
@require_role("student")
def get_student_complaint_updates_route(complaint_id: str):
    """Return progress updates for a single complaint owned by the student."""
    complaint = get_student_complaint(g.current_user, complaint_id)
    return jsonify({"updates": serialize_complaint_for_student(complaint)["updates"]}), 200


@bp.patch("/api/v1/student/complaints/<complaint_id>")
@bp.post("/api/v1/student/complaints/<complaint_id>/updates")
@bp.post("/api/v1/student/complaints/<complaint_id>/reopen")
@require_role("student")
def reject_student_complaint_mutation_route(complaint_id: str):
    """Verify ownership (403/404) and reject direct student complaint modifications."""
    get_student_complaint(g.current_user, complaint_id)
    raise AuthServiceError(
        "forbidden_action",
        "Students are not permitted to modify, update, or reopen complaints directly.",
        403,
    )


# ---------------------------------------------------------------------------
# 2. Admin / Warden Complaint Management Endpoints (`/api/v1/admin/complaints/*`)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/admin/complaints")
@require_role("admin")
def admin_list_complaints_route():
    """Return all hostel complaints with optional filtering and search."""
    filters = {
        "status": request.args.get("status"),
        "priority": request.args.get("priority"),
        "category": request.args.get("category"),
        "assigned_staff": (
            request.args.get("assigned_staff")
            or request.args.get("staff")
            or request.args.get("staff_id")
        ),
        "block": request.args.get("block"),
        "date": request.args.get("date"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "q": request.args.get("q") or request.args.get("search"),
    }
    serialized = list_admin_complaints(filters)
    return jsonify({"complaints": serialized}), 200


@bp.get("/api/v1/admin/complaints/<complaint_id>")
@require_role("admin")
def admin_get_complaint_route(complaint_id: str):
    """Return complete admin details (including internal notes) for a single complaint."""
    serialized = get_admin_complaint(complaint_id)
    return jsonify({"complaint": serialized}), 200


@bp.patch("/api/v1/admin/complaints/<complaint_id>")
@require_role("admin")
def admin_patch_complaint_route(complaint_id: str):
    """Update safe metadata (`priority`, `category`) or transition `submitted -> under_review`."""
    serialized = update_admin_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/assign")
@require_role("admin")
def admin_assign_complaint_route(complaint_id: str):
    """Assign a complaint (`submitted | under_review -> assigned`) to active staff."""
    serialized = assign_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/reassign")
@require_role("admin")
def admin_reassign_complaint_route(complaint_id: str):
    """Reassign an active complaint (`assigned | accepted | in_progress -> assigned`)."""
    serialized = reassign_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/internal-notes")
@require_role("admin")
def admin_add_internal_note_route(complaint_id: str):
    """Append a private admin-only internal note to a complaint."""
    serialized = add_complaint_internal_note(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 201


@bp.post("/api/v1/admin/complaints/<complaint_id>/close")
@require_role("admin")
def admin_close_complaint_route(complaint_id: str):
    """Verify and close a `completed` complaint (`completed -> closed`)."""
    serialized = close_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/return-for-rework")
@require_role("admin")
def admin_return_for_rework_route(complaint_id: str):
    """Return a `completed` complaint to `in_progress` with a mandatory rework reason."""
    serialized = return_complaint_for_rework(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/reject")
@require_role("admin")
def admin_reject_complaint_route(complaint_id: str):
    """Reject a pre-acceptance complaint (`submitted | under_review | assigned -> rejected`)."""
    serialized = reject_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


@bp.post("/api/v1/admin/complaints/<complaint_id>/reopen")
@require_role("admin")
def admin_reopen_complaint_route(complaint_id: str):
    """Reopen a `closed` complaint (`closed -> under_review`) with a mandatory reason."""
    serialized = reopen_complaint(g.current_user, complaint_id, _json_body())
    return jsonify({"complaint": serialized}), 200


# ---------------------------------------------------------------------------
# 3. Staff Task Management Endpoints (`/api/v1/staff/tasks/*`)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/staff/tasks")
@require_role("staff")
def staff_list_tasks_route():
    """Return tasks currently assigned (`ended_at IS NULL`) to the authenticated staff member."""
    status_filter = request.args.get("status")
    tasks = list_staff_tasks(g.current_user, status_filter=status_filter)
    serialized = [serialize_complaint_for_staff(t) for t in tasks]
    return jsonify({"tasks": serialized, "complaints": serialized}), 200


@bp.get("/api/v1/staff/tasks/<task_id>")
@require_role("staff")
def staff_get_task_route(task_id: str):
    """Return details for a single task assigned to the authenticated staff member."""
    task = get_staff_task(g.current_user, task_id)
    serialized = serialize_complaint_for_staff(task)
    return jsonify({"task": serialized, "complaint": serialized}), 200


@bp.post("/api/v1/staff/tasks/<task_id>/accept")
@require_role("staff")
def staff_accept_task_route(task_id: str):
    """Accept an assigned task (`assigned -> accepted`)."""
    task = accept_staff_task(g.current_user, task_id)
    serialized = serialize_complaint_for_staff(task)
    return jsonify({"task": serialized, "complaint": serialized}), 200


@bp.post("/api/v1/staff/tasks/<task_id>/start")
@require_role("staff")
def staff_start_task_route(task_id: str):
    """Start maintenance work on an accepted task (`accepted -> in_progress`)."""
    task = start_staff_task(g.current_user, task_id, _json_body())
    serialized = serialize_complaint_for_staff(task)
    return jsonify({"task": serialized, "complaint": serialized}), 200


@bp.post("/api/v1/staff/tasks/<task_id>/updates")
@require_role("staff")
def staff_post_update_route(task_id: str):
    """Post a student-visible progress update on an `in_progress` task."""
    task = post_staff_progress_update(g.current_user, task_id, _json_body())
    serialized = serialize_complaint_for_staff(task)
    return jsonify({"task": serialized, "complaint": serialized}), 201


@bp.post("/api/v1/staff/tasks/<task_id>/complete")
@require_role("staff")
def staff_complete_task_route(task_id: str):
    """Mark an `in_progress` task as `completed` with a mandatory completion note."""
    task = complete_staff_task(g.current_user, task_id, _json_body())
    serialized = serialize_complaint_for_staff(task)
    return jsonify({"task": serialized, "complaint": serialized}), 200


# ---------------------------------------------------------------------------
# 4. Authenticated Complaint Attachment Retrieval
# ---------------------------------------------------------------------------


@bp.get("/api/v1/complaints/<complaint_id>/attachments/<attachment_id>")
@login_required
def get_complaint_attachment_route(complaint_id: str, attachment_id: str):
    """Stream an authorized photo attachment to student owner, assigned staff, or admin."""
    user = g.current_user
    if user.role == "student":
        complaint = get_student_complaint(user, complaint_id)
    elif user.role == "staff":
        complaint = get_staff_task(user, complaint_id)
    elif user.role == "admin":
        _ensure_active_admin(user)
        complaint = resolve_complaint_by_identifier(complaint_id)
        if complaint is None:
            raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)
    else:
        raise AuthServiceError("forbidden_role", "Access is not permitted for this role.", 403)

    try:
        attachment_uuid = uuid.UUID(str(attachment_id).strip())
    except (ValueError, TypeError) as exc:
        raise AuthServiceError("attachment_not_found", "Attachment not found.", 404) from exc

    attachment = db.session.execute(
        select(ComplaintAttachment).where(
            ComplaintAttachment.complaint_id == complaint.id,
            ComplaintAttachment.public_id == attachment_uuid,
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise AuthServiceError("attachment_not_found", "Attachment not found.", 404)

    file_path = resolve_attachment_file_path(attachment)
    response = send_file(
        file_path,
        mimetype=attachment.mime_type,
        as_attachment=False,
        download_name=attachment.original_filename,
        conditional=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
    response.headers["Cache-Control"] = "no-store"
    return response
