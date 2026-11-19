"""Module B — Hostel blocks, rooms, and bed-level room allocations."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import StudentProfile, User


class Block(db.Model):
    """Hostel building block."""

    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    display_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_blocks_code"),
        UniqueConstraint("name", name="uq_blocks_name"),
        CheckConstraint("code ~ '^[A-Z0-9]{1,10}$'", name="code_format"),
        CheckConstraint("btrim(name) <> ''", name="name_nonempty"),
    )

    rooms: Mapped[list[Room]] = relationship("Room", back_populates="block")


class Room(db.Model):
    """Individual hostel room within a block."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    block_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("blocks.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    room_number: Mapped[str] = mapped_column(String(10), nullable=False)
    floor: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("block_id", "room_number", name="uq_rooms_block_id_room_number"),
        CheckConstraint("capacity BETWEEN 1 AND 8", name="capacity_range"),
        CheckConstraint("floor BETWEEN 0 AND 50", name="floor_range"),
        CheckConstraint("room_number ~ '^[A-Za-z0-9-]{1,10}$'", name="room_number_format"),
        Index("ix_rooms_block_id", "block_id"),
        Index("ix_rooms_block_floor", "block_id", "floor"),
    )

    block: Mapped[Block] = relationship("Block", back_populates="rooms")
    allocations: Mapped[list[RoomAllocation]] = relationship(
        "RoomAllocation", back_populates="room"
    )


class RoomAllocation(db.Model):
    """Dated student-to-bed allocation using half-open range [start_date, end_date)."""

    __tablename__ = "room_allocations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    room_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    student_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("student_profiles.user_id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    bed_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    allocated_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    ended_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("bed_number >= 1", name="bed_number_pos"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="date_order"),
        CheckConstraint(
            "(end_date IS NULL AND ended_by IS NULL AND end_reason IS NULL) OR "
            "(end_date IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL "
            "AND btrim(end_reason) <> '')",
            name="termination",
        ),
        ExcludeConstraint(
            (column("student_user_id"), "="),
            (func.daterange(column("start_date"), column("end_date"), text("'[)'")), "&&"),
            name="ex_alloc_student_no_overlap",
            using="gist",
        ),
        ExcludeConstraint(
            (column("room_id"), "="),
            (column("bed_number"), "="),
            (func.daterange(column("start_date"), column("end_date"), text("'[)'")), "&&"),
            name="ex_alloc_bed_no_overlap",
            using="gist",
        ),
        Index("ix_alloc_room_open", "room_id", postgresql_where=text("end_date IS NULL")),
        Index("ix_alloc_student", "student_user_id", text("start_date DESC")),
    )

    room: Mapped[Room] = relationship("Room", back_populates="allocations")
    student: Mapped[StudentProfile] = relationship(
        "StudentProfile",
        back_populates="allocations",
        foreign_keys=[student_user_id],
    )
    allocator: Mapped[User] = relationship("User", foreign_keys=[allocated_by])
    ender: Mapped[User | None] = relationship("User", foreign_keys=[ended_by])
