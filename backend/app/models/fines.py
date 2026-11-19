"""Module D — Disciplinary fines, written student disputes, and fine history ledger."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import StudentProfile, User
    from app.models.payments import Payment, PaymentAttempt
    from app.models.rooms import Room

FINE_REF_DEFAULT = text(
    "'FIN-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
    "|| '-' || to_char(nextval('public.fine_ref_seq'), 'FM9999999999999900000')"
)


class Fine(db.Model):
    """Disciplinary fine issued to a student."""

    __tablename__ = "fines"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    reference_no: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=FINE_REF_DEFAULT
    )
    student_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("student_profiles.user_id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    room_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    issued_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'pending'")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("reference_no", name="uq_fines_reference_no"),
        CheckConstraint(
            "status IN ('pending', 'disputed', 'paid', 'waived', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("amount_inr > 0", name="amount_pos"),
        CheckConstraint("due_date >= issue_date", name="due_after_issue"),
        CheckConstraint(
            "btrim(description) <> '' AND char_length(description) <= 5000",
            name="description_valid",
        ),
        CheckConstraint("(status = 'paid') = (paid_at IS NOT NULL)", name="paid_at_consistency"),
        CheckConstraint(
            "(status IN ('waived', 'cancelled')) = (resolution_reason IS NOT NULL "
            "AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL) "
            "AND (status NOT IN ('waived', 'cancelled')) = (resolution_reason IS NULL "
            "AND resolved_by IS NULL AND resolved_at IS NULL)",
            name="resolution_consistency",
        ),
        CheckConstraint(
            "resolution_reason IS NULL OR btrim(resolution_reason) <> ''",
            name="resolution_reason_nonempty",
        ),
        CheckConstraint("version >= 1", name="version_pos"),
        Index("ix_fines_student", "student_user_id", text("created_at DESC")),
        Index("ix_fines_status_due", "status", "due_date"),
    )

    student: Mapped[StudentProfile] = relationship("StudentProfile", foreign_keys=[student_user_id])
    room: Mapped[Room | None] = relationship("Room", foreign_keys=[room_id])
    issuer: Mapped[User] = relationship("User", foreign_keys=[issued_by])
    resolver: Mapped[User | None] = relationship("User", foreign_keys=[resolved_by])
    dispute: Mapped[FineDispute | None] = relationship(
        "FineDispute", back_populates="fine", uselist=False
    )
    history: Mapped[list[FineHistory]] = relationship("FineHistory", back_populates="fine")
    payment_attempts: Mapped[list[PaymentAttempt]] = relationship(
        "PaymentAttempt", back_populates="fine"
    )
    payment: Mapped[Payment | None] = relationship(
        "Payment",
        back_populates="fine",
        uselist=False,
        foreign_keys="[Payment.fine_id]",
        overlaps="attempt",
    )


class FineDispute(db.Model):
    """Written dispute raised by a student against a fine (at most one per fine)."""

    __tablename__ = "fine_disputes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    fine_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fines.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    raised_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("student_profiles.user_id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'open'"))
    decided_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("fine_id", name="uq_fine_disputes_fine_id"),
        CheckConstraint(
            "status IN ('open', 'approved', 'rejected')",
            name="status_valid",
        ),
        CheckConstraint(
            "btrim(reason) <> '' AND char_length(reason) <= 4000",
            name="reason_valid",
        ),
        CheckConstraint(
            "(status = 'open' AND decided_by IS NULL AND decided_at IS NULL "
            "AND decision_reason IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by IS NOT NULL "
            "AND decided_at IS NOT NULL AND decision_reason IS NOT NULL "
            "AND btrim(decision_reason) <> '')",
            name="decision_consistency",
        ),
    )

    fine: Mapped[Fine] = relationship("Fine", back_populates="dispute")
    student: Mapped[StudentProfile] = relationship("StudentProfile", foreign_keys=[raised_by])
    decider: Mapped[User | None] = relationship("User", foreign_keys=[decided_by])


class FineHistory(db.Model):
    """Append-only fine lifecycle ledger."""

    __tablename__ = "fine_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    fine_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fines.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    to_status: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("payments.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    payment_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("payment_attempts.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    dispute_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("fine_disputes.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('issued', 'dispute_submitted', 'dispute_approved', "
            "'dispute_rejected', 'payment_attempted', 'payment_verified', "
            "'manual_payment_recorded', 'payment_needs_review', 'waived', 'cancelled')",
            name="action_valid",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN ('pending', 'disputed', 'paid', "
            "'waived', 'cancelled')",
            name="from_status_valid",
        ),
        CheckConstraint(
            "to_status IN ('pending', 'disputed', 'paid', 'waived', 'cancelled')",
            name="to_status_valid",
        ),
        CheckConstraint(
            "action NOT IN ('dispute_approved', 'dispute_rejected', 'waived', 'cancelled') "
            "OR (note IS NOT NULL AND btrim(note) <> '')",
            name="mandatory_action_note",
        ),
        Index("ix_fhist_fine", "fine_id", "created_at", "id"),
    )

    fine: Mapped[Fine] = relationship("Fine", back_populates="history")
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_user_id])
    payment: Mapped[Payment | None] = relationship("Payment", foreign_keys=[payment_id])
    payment_attempt: Mapped[PaymentAttempt | None] = relationship(
        "PaymentAttempt", foreign_keys=[payment_attempt_id]
    )
    dispute: Mapped[FineDispute | None] = relationship("FineDispute", foreign_keys=[dispute_id])
