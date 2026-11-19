"""Module F — In-app notifications."""

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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import User


class Notification(db.Model):
    """In-app notification delivered to a user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    recipient_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(14), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_notifications_public_id"),
        CheckConstraint(
            "category IN ('complaint', 'fine', 'dispute', 'payment', 'registration', 'system')",
            name="category_valid",
        ),
        CheckConstraint("btrim(event_type) <> ''", name="event_type_nonempty"),
        CheckConstraint("btrim(title) <> ''", name="title_nonempty"),
        CheckConstraint(
            "btrim(message) <> '' AND char_length(message) <= 1000",
            name="message_valid",
        ),
        CheckConstraint("(entity_type IS NULL) = (entity_ref IS NULL)", name="entity_link_pair"),
        CheckConstraint(
            "entity_type IS NULL OR entity_type IN ('complaint', 'fine', 'payment', 'student')",
            name="entity_type_valid",
        ),
        Index("ix_notif_recipient", "recipient_user_id", text("created_at DESC")),
        Index("ix_notif_unread", "recipient_user_id", postgresql_where=text("read_at IS NULL")),
    )

    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_user_id])
