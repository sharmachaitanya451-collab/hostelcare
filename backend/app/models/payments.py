"""Module E — Payment attempts, verified immutable payments, and gateway/webhook event log."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.fines import Fine
    from app.models.identity import User

RECEIPT_REF_DEFAULT = text(
    "'RCP-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
    "|| '-' || to_char(nextval('public.receipt_seq'), 'FM9999999999999900000')"
)


class PaymentAttempt(db.Model):
    """Gateway checkout attempt for a fine (mutable status)."""

    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    fine_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fines.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    initiated_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'INR'"))
    gateway_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        String(18), nullable=False, server_default=text("'created'")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_payment_attempts_public_id"),
        UniqueConstraint("id", "fine_id", name="uq_payment_attempts_id_fine"),
        CheckConstraint(
            "status IN ('created', 'processing', 'succeeded', "
            "'captured_unapplied', 'failed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("amount_inr > 0", name="amount_pos"),
        CheckConstraint("currency = 'INR'", name="currency_inr"),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi', 'card', 'netbanking', 'wallet', 'other')",
            name="payment_method_valid",
        ),
        CheckConstraint(
            "(status IN ('succeeded', 'captured_unapplied')) = (verified_at IS NOT NULL)",
            name="verified_at_consistency",
        ),
        CheckConstraint(
            "status NOT IN ('succeeded', 'captured_unapplied') "
            "OR (gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL)",
            name="gateway_ids_on_capture",
        ),
        Index(
            "uq_payment_attempts_gateway_order_id",
            "gateway_order_id",
            unique=True,
            postgresql_where=text("gateway_order_id IS NOT NULL"),
        ),
        Index(
            "uq_payment_attempts_gateway_payment_id",
            "gateway_payment_id",
            unique=True,
            postgresql_where=text("gateway_payment_id IS NOT NULL"),
        ),
        Index(
            "uq_attempt_one_open",
            "fine_id",
            unique=True,
            postgresql_where=text("status IN ('created', 'processing')"),
        ),
        Index("ix_attempts_fine", "fine_id", "created_at"),
        Index(
            "ix_attempts_status_open",
            "status",
            postgresql_where=text("status IN ('created', 'processing')"),
        ),
    )

    fine: Mapped[Fine] = relationship("Fine", back_populates="payment_attempts")
    initiator: Mapped[User] = relationship("User", foreign_keys=[initiated_by])
    events: Mapped[list[PaymentEvent]] = relationship("PaymentEvent", back_populates="attempt")


class Payment(db.Model):
    """Immutable verified financial payment record (SELECT and INSERT only at runtime)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    fine_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fines.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    payment_attempt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'INR'"))
    gateway_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verification_method: Mapped[str] = mapped_column(String(14), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    receipt_number: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=RECEIPT_REF_DEFAULT
    )
    recorded_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    manual_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_attempt_id", "fine_id"],
            ["payment_attempts.id", "payment_attempts.fine_id"],
            name="fk_payments_attempt_fine_payment_attempts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        UniqueConstraint("public_id", name="uq_payments_public_id"),
        UniqueConstraint("receipt_number", name="uq_payments_receipt_number"),
        UniqueConstraint("fine_id", name="uq_payments_fine"),
        CheckConstraint("channel IN ('razorpay', 'manual')", name="channel_valid"),
        CheckConstraint("amount_inr > 0", name="amount_pos"),
        CheckConstraint("currency = 'INR'", name="currency_inr"),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi', 'card', 'netbanking', 'wallet', 'cash', 'bank_transfer', 'other')",
            name="payment_method_valid",
        ),
        CheckConstraint(
            "verification_method IN ('webhook', 'api_fetch', 'manual_entry')",
            name="verification_method_valid",
        ),
        CheckConstraint(
            "channel <> 'razorpay' OR (payment_attempt_id IS NOT NULL "
            "AND gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL "
            "AND verification_method IN ('webhook', 'api_fetch') AND recorded_by IS NULL)",
            name="razorpay_channel_fields",
        ),
        CheckConstraint(
            "channel <> 'manual' OR (payment_attempt_id IS NULL "
            "AND gateway_order_id IS NULL AND gateway_payment_id IS NULL "
            "AND verification_method = 'manual_entry' AND recorded_by IS NOT NULL "
            "AND manual_reference IS NOT NULL AND btrim(manual_reference) <> '')",
            name="manual_channel_fields",
        ),
        Index(
            "uq_payments_attempt",
            "payment_attempt_id",
            unique=True,
            postgresql_where=text("payment_attempt_id IS NOT NULL"),
        ),
        Index(
            "uq_payments_gateway_payment",
            "gateway_payment_id",
            unique=True,
            postgresql_where=text("gateway_payment_id IS NOT NULL"),
        ),
        Index("ix_payments_verified_at", "verified_at"),
    )

    fine: Mapped[Fine] = relationship(
        "Fine",
        back_populates="payment",
        foreign_keys=[fine_id],
        overlaps="attempt",
    )
    attempt: Mapped[PaymentAttempt | None] = relationship(
        "PaymentAttempt",
        primaryjoin="and_(Payment.payment_attempt_id == PaymentAttempt.id, "
        "Payment.fine_id == PaymentAttempt.fine_id)",
        foreign_keys=[payment_attempt_id, fine_id],
        overlaps="fine,payment",
    )
    recorder: Mapped[User | None] = relationship("User", foreign_keys=[recorded_by])


class PaymentEvent(db.Model):
    """Append-only gateway, webhook, and client event log (idempotency anchor)."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    payment_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("payment_attempts.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    gateway_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome: Mapped[str] = mapped_column(String(14), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('webhook', 'client_callback', 'server_verify', 'system', 'admin')",
            name="source_valid",
        ),
        CheckConstraint(
            "outcome IN ('applied', 'duplicate', 'ignored', 'rejected', 'error', 'needs_review')",
            name="outcome_valid",
        ),
        CheckConstraint("btrim(event_type) <> ''", name="event_type_nonempty"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_is_object"),
        Index(
            "uq_payment_events_gateway_event",
            "gateway_event_id",
            unique=True,
            postgresql_where=text("gateway_event_id IS NOT NULL"),
        ),
        Index("ix_payment_events_attempt_created", "payment_attempt_id", "created_at"),
    )

    attempt: Mapped[PaymentAttempt | None] = relationship("PaymentAttempt", back_populates="events")
