"""Student complaint submission, listing, and detail services.

SECURITY & PRIVACY INVARIANT:
This module must NEVER import `ComplaintInternalNote` or `app.models.complaint_internal_notes`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.datastructures import FileStorage

from app.audit.service import record_audit_event
from app.auth.service import AuthServiceError, get_active_student_room_allocation
from app.complaints.attachment_service import (
    StagedAttachment,
    cleanup_staged_files,
    get_max_attachments,
    persist_validated_images,
    validate_uploaded_photos,
)
from app.complaints.serializers import (
    complaint_exists_by_identifier,
    complaint_load_options,
    resolve_complaint_by_identifier,
)
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAttachment, ComplaintHistory
from app.models.identity import User
from app.models.rooms import Block
from app.notifications.service import create_notification, notify_active_admins

_VALID_PRIORITIES = {"low", "medium", "high"}
_VALID_LOCATION_TYPES = {"room", "common_area"}


def _resolve_optional_block(raw_block: Any) -> Block | None:
    if raw_block is None:
        return None
    val = str(raw_block).strip()
    if not val:
        return None
    if val.isdigit():
        blk = db.session.execute(
            select(Block).where(Block.id == int(val), Block.is_active.is_(True))
        ).scalar_one_or_none()
        if blk is not None:
            return blk
    blk = db.session.execute(
        select(Block).where(
            (Block.code == val.upper()) | (Block.name.ilike(val)),
            Block.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if blk is None:
        raise AuthServiceError("invalid_block", "Specified hostel block was not found.", 400)
    return blk


def _ensure_active_student(student_user: User) -> None:
    if student_user is None or student_user.role != "student" or student_user.status != "active":
        raise AuthServiceError(
            "forbidden_role",
            "Only active, approved students can access student complaints.",
            403,
        )


def submit_student_complaint(
    student_user: User,
    payload: dict[str, Any],
    uploaded_files: list[FileStorage] | None = None,
) -> Complaint:
    """Create a new student complaint (`status='submitted'`) derived from the session user."""
    _ensure_active_student(student_user)
    if student_user.student_profile is None:
        raise AuthServiceError("profile_missing", "Student profile record is missing.", 400)

    raw_title = str(payload.get("title") or "").strip()
    if not raw_title:
        raise AuthServiceError("validation_error", "Complaint title is required.", 400)
    if len(raw_title) > 150:
        raise AuthServiceError(
            "validation_error",
            "Complaint title must not exceed 150 characters.",
            400,
        )

    raw_description = str(payload.get("description") or "").strip()
    if not raw_description:
        raise AuthServiceError(
            "validation_error",
            "Detailed problem description is required.",
            400,
        )
    if len(raw_description) > 5000:
        raise AuthServiceError(
            "validation_error",
            "Complaint description must not exceed 5000 characters.",
            400,
        )

    raw_category = payload.get("category")
    category: str | None = None
    if raw_category is not None:
        cat_str = str(raw_category).strip()
        if cat_str and cat_str != "Uncategorized (Free-Text)":
            if len(cat_str) > 60:
                raise AuthServiceError(
                    "validation_error",
                    "Category must not exceed 60 characters.",
                    400,
                )
            category = cat_str

    raw_priority = str(payload.get("priority") or "medium").strip().lower()
    if raw_priority not in _VALID_PRIORITIES:
        raise AuthServiceError(
            "validation_error",
            "Priority must be one of: low, medium, high.",
            400,
        )

    raw_loc_type = (
        str(payload.get("location_type") or payload.get("locationType") or "room").strip().lower()
    )
    if raw_loc_type not in _VALID_LOCATION_TYPES:
        raise AuthServiceError(
            "validation_error",
            "location_type must be 'room' or 'common_area'.",
            400,
        )

    room_id: int | None = None
    block_id: int | None = None
    location_detail: str | None = None

    if raw_loc_type == "room":
        active_alloc = get_active_student_room_allocation(student_user.id)
        if active_alloc is None:
            raise AuthServiceError(
                "active_room_required",
                (
                    "Room-specific complaints require an active room allocation. "
                    "Approved students without an active room may submit common-area complaints."
                ),
                400,
            )
        room_id = active_alloc.room_id
        block_id = None
        location_detail = None
    else:
        raw_loc_detail = str(
            payload.get("location_detail") or payload.get("locationDetail") or ""
        ).strip()
        if not raw_loc_detail:
            raise AuthServiceError(
                "validation_error",
                "location_detail is required for common-area complaints.",
                400,
            )
        if len(raw_loc_detail) > 150:
            raise AuthServiceError(
                "validation_error",
                "location_detail must not exceed 150 characters.",
                400,
            )
        location_detail = raw_loc_detail
        raw_block = (
            payload.get("block_id")
            if "block_id" in payload
            else (payload.get("blockId") if "blockId" in payload else payload.get("block_code"))
        )
        blk = _resolve_optional_block(raw_block)
        block_id = blk.id if blk is not None else None
        room_id = None

    files_to_attach = list(uploaded_files or [])
    staged_attachments: list[StagedAttachment] = []
    if files_to_attach:
        validated_images = validate_uploaded_photos(files_to_attach)
        staged_attachments = persist_validated_images(validated_images)

    try:
        complaint = Complaint(
            student_user_id=student_user.id,
            location_type=raw_loc_type,
            room_id=room_id,
            block_id=block_id,
            location_detail=location_detail,
            title=raw_title,
            category=category,
            description=raw_description,
            priority=raw_priority,
            status="submitted",
        )
        db.session.add(complaint)
        db.session.flush()

        for staged in staged_attachments:
            db.session.add(
                ComplaintAttachment(
                    complaint_id=complaint.id,
                    storage_path=staged.storage_path,
                    original_filename=staged.original_filename,
                    file_size_bytes=staged.file_size_bytes,
                    mime_type=staged.mime_type,
                    checksum_sha256=staged.checksum_sha256,
                )
            )

        history_entry = ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=student_user.id,
            action="submitted",
            from_status=None,
            to_status="submitted",
            note="Initial maintenance complaint submitted by student.",
        )
        db.session.add(history_entry)

        create_notification(
            recipient_user_id=student_user.id,
            category="complaint",
            event_type="complaint.submitted",
            title=f"Complaint {complaint.reference_no} Registered",
            message=(
                f"Your maintenance complaint '{complaint.title}' ({complaint.reference_no}) "
                f"has been submitted and is awaiting warden review."
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )

        notify_active_admins(
            category="complaint",
            event_type="complaint.submitted",
            title=f"New Complaint: {complaint.reference_no}",
            message=(
                f"{student_user.full_name} ({student_user.student_profile.roll_number}) "
                f"submitted a {raw_priority.upper()} priority complaint: '{complaint.title}'."
            ),
            entity_type="complaint",
            entity_ref=complaint.reference_no,
        )

        record_audit_event(
            action="complaint.submitted",
            actor=student_user,
            target_type="complaint",
            target_id=complaint.reference_no,
            metadata={
                "location_type": raw_loc_type,
                "priority": raw_priority,
                "category": category or "Uncategorized",
                "attachment_count": len(staged_attachments),
            },
        )

        db.session.commit()
    except Exception:
        db.session.rollback()
        cleanup_staged_files([s.cleanup_ref for s in staged_attachments])
        raise

    loaded = resolve_complaint_by_identifier(complaint.reference_no)
    return loaded or complaint


def attach_student_complaint_photos(
    student_user: User,
    complaint_identifier: str,
    uploaded_files: list[FileStorage],
) -> Complaint:
    """Attach additional photos (up to 3 total) to an existing owned complaint under row lock."""
    _ensure_active_student(student_user)
    if not uploaded_files:
        raise AuthServiceError("validation_error", "At least one photo file is required.", 400)

    complaint = resolve_complaint_by_identifier(
        complaint_identifier,
        for_update=True,
        student_user_id=student_user.id,
    )
    if complaint is None:
        if complaint_exists_by_identifier(complaint_identifier):
            raise AuthServiceError(
                "forbidden",
                "You do not have permission to access another student's complaint.",
                403,
            )
        raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)

    if complaint.status in ("closed", "rejected"):
        raise AuthServiceError(
            "invalid_state",
            "Photos cannot be attached to a closed or rejected complaint.",
            409,
        )

    existing_count = db.session.execute(
        select(func.count(ComplaintAttachment.id)).where(
            ComplaintAttachment.complaint_id == complaint.id
        )
    ).scalar_one()
    max_attachments = get_max_attachments()
    if int(existing_count) + len(uploaded_files) > max_attachments:
        raise AuthServiceError(
            "validation_error",
            f"You may attach at most {max_attachments} photos per complaint.",
            400,
        )

    validated_images = validate_uploaded_photos(uploaded_files)
    staged_attachments = persist_validated_images(validated_images)

    try:
        for staged in staged_attachments:
            db.session.add(
                ComplaintAttachment(
                    complaint_id=complaint.id,
                    storage_path=staged.storage_path,
                    original_filename=staged.original_filename,
                    file_size_bytes=staged.file_size_bytes,
                    mime_type=staged.mime_type,
                    checksum_sha256=staged.checksum_sha256,
                )
            )
        record_audit_event(
            action="complaint.attachments_added",
            actor=student_user,
            target_type="complaint",
            target_id=complaint.reference_no,
            metadata={"added_count": len(staged_attachments)},
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        cleanup_staged_files([s.cleanup_ref for s in staged_attachments])
        raise

    loaded = resolve_complaint_by_identifier(complaint.reference_no)
    return loaded or complaint


def list_student_complaints(
    student_user: User,
    *,
    status_filter: str | None = None,
) -> list[Complaint]:
    """Return complaints belonging strictly to `student_user`."""
    _ensure_active_student(student_user)
    stmt = (
        select(Complaint)
        .options(*complaint_load_options())
        .where(Complaint.student_user_id == student_user.id)
    )
    if status_filter:
        norm_status = status_filter.strip().lower().replace(" ", "_")
        if norm_status == "resolved":
            norm_status = "completed"
        if norm_status != "all":
            stmt = stmt.where(Complaint.status == norm_status)

    stmt = stmt.order_by(Complaint.created_at.desc(), Complaint.id.desc())
    return list(db.session.execute(stmt).scalars().all())


def get_student_complaint(student_user: User, complaint_identifier: str) -> Complaint:
    """Return a single complaint if and only if owned by `student_user`.

    Enforces `Complaint.student_user_id == student_user.id` directly in the
    database query before loading any complaint record into memory.
    """
    _ensure_active_student(student_user)
    complaint = resolve_complaint_by_identifier(
        complaint_identifier,
        student_user_id=student_user.id,
    )
    if complaint is not None:
        return complaint

    if complaint_exists_by_identifier(complaint_identifier):
        raise AuthServiceError(
            "forbidden",
            "You do not have permission to access another student's complaint.",
            403,
        )
    raise AuthServiceError("complaint_not_found", "Complaint not found.", 404)
