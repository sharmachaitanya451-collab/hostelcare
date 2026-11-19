"""Admin-only private complaint notes model (`complaint_internal_notes`).

Structurally isolated from `app.models.complaints` per ADR-013 and ADR-025:
- `Complaint` has NO `relationship()` or backref to `ComplaintInternalNote`.
- Student and staff services must never import this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.identity import User


class ComplaintInternalNote(db.Model):
    """Append-only administrative private note on a complaint."""

    __tablename__ = "complaint_internal_notes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("complaints.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    author_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="NO ACTION"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "btrim(body) <> '' AND char_length(body) <= 4000",
            name="body_valid",
        ),
        Index("ix_complaint_internal_notes_complaint_created", "complaint_id", "created_at"),
    )

    author: Mapped[User] = relationship("User", foreign_keys=[author_user_id])
