"""Module C — Student complaints, staff assignments, student-visible updates, and history ledger.

NOTE: Private admin notes (`complaint_internal_notes`) are structurally isolated in
`app.models.complaint_internal_notes` and intentionally have NO relationship on `Complaint`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import StaffProfile, StudentProfile, User
    from app.models.rooms import Block, Room

COMPLAINT_REF_DEFAULT = text(
    "'CMP-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
    "|| '-' || to_char(nextval('public.complaint_ref_seq'), 'FM9999999999999900000')"
)


class Complaint(db.Model):
    """Student maintenance complaint (room-specific or common-area)."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    reference_no: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=COMPLAINT_REF_DEFAULT
    )
    student_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("student_profiles.user_id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    location_type: Mapped[str] = mapped_column(String(11), nullable=False)
    room_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    block_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("blocks.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    location_detail: Mapped[str | None] = mapped_column(String(150), nullable=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default=text("'medium'")
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'submitted'")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("reference_no", name="uq_complaints_reference_no"),
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'assigned', 'accepted', "
            "'in_progress', 'completed', 'closed', 'rejected')",
            name="status_valid",
        ),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="priority_valid"),
        CheckConstraint("location_type IN ('room', 'common_area')", name="location_type_valid"),
        CheckConstraint("btrim(title) <> ''", name="title_nonempty"),
        CheckConstraint(
            "btrim(description) <> '' AND char_length(description) <= 5000",
            name="description_valid",
        ),
        CheckConstraint(
            "(location_type = 'room' AND room_id IS NOT NULL AND block_id IS NULL "
            "AND location_detail IS NULL) OR "
            "(location_type = 'common_area' AND room_id IS NULL "
            "AND location_detail IS NOT NULL AND btrim(location_detail) <> '')",
            name="location_consistency",
        ),
        CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="rejection_reason_required",
        ),
        CheckConstraint(
            "rejection_reason IS NULL OR btrim(rejection_reason) <> ''",
            name="rejection_reason_nonempty",
        ),
        CheckConstraint(
            "(status IN ('completed', 'closed')) = (completed_at IS NOT NULL)",
            name="completed_at_consistency",
        ),
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)",
            name="closed_at_consistency",
        ),
        CheckConstraint("version >= 1", name="version_pos"),
        Index("ix_complaints_student", "student_user_id", text("created_at DESC")),
        Index("ix_complaints_queue", "status", "priority", "created_at"),
        Index("ix_complaints_room", "room_id", postgresql_where=text("room_id IS NOT NULL")),
        Index("ix_complaints_block", "block_id", postgresql_where=text("block_id IS NOT NULL")),
    )

    student: Mapped[StudentProfile] = relationship("StudentProfile", foreign_keys=[student_user_id])
    room: Mapped[Room | None] = relationship("Room", foreign_keys=[room_id])
    block: Mapped[Block | None] = relationship("Block", foreign_keys=[block_id])
    assignments: Mapped[list[ComplaintAssignment]] = relationship(
        "ComplaintAssignment", back_populates="complaint"
    )
    updates: Mapped[list[ComplaintUpdate]] = relationship(
        "ComplaintUpdate", back_populates="complaint"
    )
    history: Mapped[list[ComplaintHistory]] = relationship(
        "ComplaintHistory", back_populates="complaint"
    )
    attachments: Mapped[list[ComplaintAttachment]] = relationship(
        "ComplaintAttachment",
        back_populates="complaint",
        order_by="ComplaintAttachment.created_at, ComplaintAttachment.id",
    )


class ComplaintAssignment(db.Model):
    """Staff assignment record for a complaint; partial unique index enforces one open row."""

    __tablename__ = "complaint_assignments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaints.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    staff_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_profiles.user_id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    assigned_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    end_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "accepted_at IS NULL OR accepted_at >= assigned_at",
            name="accepted_after_assigned",
        ),
        CheckConstraint(
            "started_at IS NULL OR (accepted_at IS NOT NULL AND started_at >= accepted_at)",
            name="started_after_accepted",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= assigned_at",
            name="ended_after_assigned",
        ),
        CheckConstraint("(ended_at IS NULL) = (ended_by IS NULL)", name="ended_by_consistency"),
        Index(
            "uq_assign_one_active",
            "complaint_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_assign_complaint", "complaint_id", "assigned_at"),
        Index("ix_assign_staff_active", "staff_user_id", postgresql_where=text("ended_at IS NULL")),
    )

    complaint: Mapped[Complaint] = relationship("Complaint", back_populates="assignments")
    staff: Mapped[StaffProfile] = relationship("StaffProfile", foreign_keys=[staff_user_id])
    assigner: Mapped[User] = relationship("User", foreign_keys=[assigned_by])
    ender: Mapped[User | None] = relationship("User", foreign_keys=[ended_by])
    updates: Mapped[list[ComplaintUpdate]] = relationship(
        "ComplaintUpdate", back_populates="assignment"
    )


class ComplaintUpdate(db.Model):
    """Append-only student-visible staff progress and completion updates."""

    __tablename__ = "complaint_updates"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaints.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    assignment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaint_assignments.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    author_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    update_type: Mapped[str] = mapped_column(String(12), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "update_type IN ('progress', 'completion')",
            name="update_type_valid",
        ),
        CheckConstraint(
            "btrim(body) <> '' AND char_length(body) <= 4000",
            name="body_valid",
        ),
        Index("ix_complaint_updates_complaint_created", "complaint_id", "created_at"),
    )

    complaint: Mapped[Complaint] = relationship("Complaint", back_populates="updates")
    assignment: Mapped[ComplaintAssignment] = relationship(
        "ComplaintAssignment", back_populates="updates"
    )
    author: Mapped[User] = relationship("User", foreign_keys=[author_user_id])


class ComplaintHistory(db.Model):
    """Append-only complaint lifecycle ledger."""

    __tablename__ = "complaint_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaints.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    to_status: Mapped[str] = mapped_column(String(12), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("complaint_assignments.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    update_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("complaint_updates.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('submitted', 'review_started', 'assigned', 'reassigned', "
            "'accepted', 'work_started', 'progress_updated', 'completed', "
            "'returned_for_rework', 'closed', 'rejected', 'reopened')",
            name="action_valid",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN ('submitted', 'under_review', "
            "'assigned', 'accepted', 'in_progress', 'completed', 'closed', 'rejected')",
            name="from_status_valid",
        ),
        CheckConstraint(
            "to_status IN ('submitted', 'under_review', 'assigned', 'accepted', "
            "'in_progress', 'completed', 'closed', 'rejected')",
            name="to_status_valid",
        ),
        CheckConstraint(
            "action NOT IN ('returned_for_rework', 'rejected', 'reopened') "
            "OR (note IS NOT NULL AND btrim(note) <> '')",
            name="mandatory_action_note",
        ),
        Index("ix_chist_complaint", "complaint_id", "created_at", "id"),
    )

    complaint: Mapped[Complaint] = relationship("Complaint", back_populates="history")
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_user_id])
    assignment: Mapped[ComplaintAssignment | None] = relationship(
        "ComplaintAssignment", foreign_keys=[assignment_id]
    )
    update: Mapped[ComplaintUpdate | None] = relationship(
        "ComplaintUpdate", foreign_keys=[update_id]
    )


class ComplaintAttachment(db.Model):
    """Private photo attachment metadata for a student maintenance complaint."""

    __tablename__ = "complaint_attachments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    complaint_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaints.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_complaint_attachments_public_id"),
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 5242880",
            name="file_size_valid",
        ),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="mime_type_valid",
        ),
        CheckConstraint("btrim(storage_path) <> ''", name="storage_path_nonempty"),
        CheckConstraint("btrim(original_filename) <> ''", name="original_filename_nonempty"),
        CheckConstraint(
            "char_length(checksum_sha256) = 64 AND checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
        Index("ix_cattach_complaint_created", "complaint_id", "created_at", "id"),
    )

    complaint: Mapped[Complaint] = relationship("Complaint", back_populates="attachments")
