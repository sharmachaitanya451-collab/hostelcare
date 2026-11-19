"""Module A — Identity and authentication models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.rooms import Room, RoomAllocation


class User(db.Model):
    """One login account per person; holds role and account lifecycle status."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    failed_login_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_users_public_id"),
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("id", "role", name="uq_users_id_role"),
        CheckConstraint("role IN ('student', 'staff', 'admin')", name="role_valid"),
        CheckConstraint(
            "status IN ('pending', 'active', 'rejected', 'suspended', 'deactivated')",
            name="status_valid",
        ),
        CheckConstraint(
            "role = 'student' OR status NOT IN ('pending', 'rejected')",
            name="role_status_valid",
        ),
        CheckConstraint(
            "email = lower(btrim(email)) AND position('@' in email) > 1",
            name="email_normalized",
        ),
        CheckConstraint("btrim(full_name) <> ''", name="full_name_nonempty"),
        CheckConstraint(
            "password_hash = '!' OR password_hash LIKE '$argon2id$%'",
            name="password_hash_format",
        ),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_nonneg"),
        CheckConstraint("session_version >= 1", name="session_version_pos"),
        Index("ix_users_role_status", "role", "status"),
        Index(
            "ix_users_pending",
            "created_at",
            postgresql_where=text("role = 'student' AND status = 'pending'"),
        ),
    )

    creator: Mapped[User | None] = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[created_by],
    )
    student_profile: Mapped[StudentProfile | None] = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        primaryjoin="and_(User.id == StudentProfile.user_id, User.role == StudentProfile.role)",
        foreign_keys="[StudentProfile.user_id, StudentProfile.role]",
        overlaps="role",
    )
    staff_profile: Mapped[StaffProfile | None] = relationship(
        "StaffProfile",
        back_populates="user",
        uselist=False,
        primaryjoin="and_(User.id == StaffProfile.user_id, User.role == StaffProfile.role)",
        foreign_keys="[StaffProfile.user_id, StaffProfile.role]",
        overlaps="role,student_profile",
    )


class StudentProfile(db.Model):
    """Student-specific identity data and latest registration review metadata (1:1 with users)."""

    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'student'"))
    roll_number: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_room_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "role"],
            ["users.id", "users.role"],
            name="fk_student_profiles_user_id_role_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        UniqueConstraint("roll_number", name="uq_student_profiles_roll_number"),
        CheckConstraint("role = 'student'", name="role_is_student"),
        CheckConstraint(
            "roll_number = upper(btrim(roll_number)) "
            "AND roll_number ~ '^[A-Z0-9][A-Z0-9/_-]{2,31}$'",
            name="roll_number_format",
        ),
        CheckConstraint("(reviewed_by IS NULL) = (reviewed_at IS NULL)", name="review_audit_pair"),
        CheckConstraint(
            "review_note IS NULL OR btrim(review_note) <> ''", name="review_note_nonempty"
        ),
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="student_profile",
        primaryjoin="and_(StudentProfile.user_id == User.id, StudentProfile.role == User.role)",
        foreign_keys=[user_id, role],
        overlaps="staff_profile",
    )
    requested_room: Mapped[Room | None] = relationship(
        "Room",
        foreign_keys=[requested_room_id],
    )
    reviewer: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        overlaps="student_profile,user",
    )
    allocations: Mapped[list[RoomAllocation]] = relationship(
        "RoomAllocation",
        back_populates="student",
        foreign_keys="[RoomAllocation.student_user_id]",
    )


class StaffProfile(db.Model):
    """Maintenance staff profile data (1:1 with users)."""

    __tablename__ = "staff_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'staff'"))
    staff_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade: Mapped[str] = mapped_column(String(60), nullable=False)
    shift: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "role"],
            ["users.id", "users.role"],
            name="fk_staff_profiles_user_id_role_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        UniqueConstraint("staff_code", name="uq_staff_profiles_staff_code"),
        CheckConstraint("role = 'staff'", name="role_is_staff"),
        CheckConstraint("btrim(trade) <> ''", name="trade_nonempty"),
        CheckConstraint("staff_code ~ '^[A-Z0-9-]{3,20}$'", name="staff_code_format"),
        Index("ix_staff_profiles_trade", "trade"),
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="staff_profile",
        primaryjoin="and_(StaffProfile.user_id == User.id, StaffProfile.role == User.role)",
        foreign_keys=[user_id, role],
        overlaps="student_profile,user",
    )


class PasswordResetToken(db.Model):
    """Hashed, single-use, 30-minute password reset tokens."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(INET, nullable=True)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_hex"),
        CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '30 minutes'",
            name="expires_within_30m",
        ),
        CheckConstraint(
            "NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="not_used_and_revoked",
        ),
        Index(
            "uq_prt_one_live",
            "user_id",
            unique=True,
            postgresql_where=text("used_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("ix_prt_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_prt_ip_created",
            "request_ip",
            text("created_at DESC"),
            postgresql_where=text("request_ip IS NOT NULL"),
        ),
        Index("ix_prt_expires", "expires_at"),
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    requester: Mapped[User | None] = relationship("User", foreign_keys=[requested_by])
