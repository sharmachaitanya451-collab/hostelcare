"""Module G — Append-only security and administrative audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import User


class AuditLog(db.Model):
    """Append-only cross-system security and administrative audit log."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=True,
    )
    actor_role: Mapped[str | None] = mapped_column(String(10), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    __table_args__ = (
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
        CheckConstraint("btrim(action) <> ''", name="action_nonempty"),
        CheckConstraint("(target_type IS NULL) = (target_id IS NULL)", name="target_pair"),
        Index("ix_audit_occurred", text("occurred_at DESC")),
        Index("ix_audit_actor", "actor_user_id", text("occurred_at DESC")),
        Index("ix_audit_target", "target_type", "target_id"),
        Index(
            "ix_audit_action_ip",
            "action",
            "ip_address",
            text("occurred_at DESC"),
            postgresql_where=text("ip_address IS NOT NULL"),
        ),
    )

    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_user_id])
