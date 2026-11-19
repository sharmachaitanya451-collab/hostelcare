"""In-app notification creation, listing, and read-tracking services."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.auth.service import AuthServiceError
from app.extensions import db
from app.models.identity import User
from app.models.notifications import Notification


def serialize_notification(notif: Notification) -> dict[str, Any]:
    """Serialize an in-app `Notification` for student, staff, or admin portals."""
    created_dt = notif.created_at.astimezone(UTC) if notif.created_at else datetime.now(UTC)
    time_label = created_dt.strftime("%d/%m/%Y, %H:%M UTC")
    is_read = notif.read_at is not None

    return {
        "id": str(notif.public_id),
        "public_id": str(notif.public_id),
        "recipient_user_id": notif.recipient_user_id,
        "category": notif.category,
        "event_type": notif.event_type,
        "eventType": notif.event_type,
        "title": notif.title,
        "message": notif.message,
        "entity_type": notif.entity_type,
        "entityType": notif.entity_type,
        "entity_ref": notif.entity_ref,
        "entityRef": notif.entity_ref,
        "read": is_read,
        "read_at": notif.read_at.isoformat() if notif.read_at else None,
        "readAt": notif.read_at.isoformat() if notif.read_at else None,
        "created_at": notif.created_at.isoformat() if notif.created_at else None,
        "createdAt": notif.created_at.isoformat() if notif.created_at else None,
        "time": time_label,
    }


def create_notification(
    *,
    recipient_user_id: int,
    category: str,
    event_type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_ref: str | None = None,
) -> Notification:
    """Insert a new in-app notification respecting PostgreSQL CHECK constraints."""
    clean_title = str(title or "").strip()[:150]
    clean_msg = str(message or "").strip()[:1000]
    if (entity_type is None) != (entity_ref is None):
        entity_type = None
        entity_ref = None

    notif = Notification(
        recipient_user_id=recipient_user_id,
        category=category,
        event_type=event_type.strip()[:40],
        title=clean_title or "HostelCare Notification",
        message=clean_msg or "You have a new HostelCare update.",
        entity_type=entity_type,
        entity_ref=str(entity_ref)[:40] if entity_ref is not None else None,
    )
    db.session.add(notif)
    return notif


def notify_active_admins(
    *,
    category: str,
    event_type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_ref: str | None = None,
    exclude_user_id: int | None = None,
) -> list[Notification]:
    """Create in-app notifications for all active administrator/warden accounts."""
    stmt = select(User.id).where(User.role == "admin", User.status == "active")
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    admin_ids = list(db.session.execute(stmt).scalars().all())
    created: list[Notification] = []
    for admin_id in admin_ids:
        created.append(
            create_notification(
                recipient_user_id=admin_id,
                category=category,
                event_type=event_type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_ref=entity_ref,
            )
        )
    return created


def list_user_notifications(user: User, *, unread_only: bool = False) -> list[Notification]:
    """Return notifications belonging strictly to `user` in reverse chronological order."""
    stmt = select(Notification).where(Notification.recipient_user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    return list(db.session.execute(stmt).scalars().all())


def _resolve_notification(identifier: str) -> Notification | None:
    raw = str(identifier or "").strip()
    if not raw:
        return None
    try:
        pub_uuid = uuid.UUID(raw)
        notif = db.session.execute(
            select(Notification).where(Notification.public_id == pub_uuid)
        ).scalar_one_or_none()
        if notif is not None:
            return notif
    except (ValueError, TypeError):
        pass

    if raw.isdigit():
        return db.session.execute(
            select(Notification).where(Notification.id == int(raw))
        ).scalar_one_or_none()
    return None


def mark_notification_read(user: User, notification_identifier: str) -> Notification:
    """Mark a single notification as read after verifying ownership (`recipient_user_id`)."""
    notif = _resolve_notification(notification_identifier)
    if notif is None:
        raise AuthServiceError("notification_not_found", "Notification not found.", 404)
    if notif.recipient_user_id != user.id:
        raise AuthServiceError(
            "forbidden",
            "You do not have permission to access or modify this notification.",
            403,
        )

    if notif.read_at is None:
        now = datetime.now(UTC)
        db.session.execute(
            update(Notification)
            .where(Notification.id == notif.id, Notification.recipient_user_id == user.id)
            .values(read_at=now)
        )
        db.session.commit()
        db.session.refresh(notif)
    return notif


def mark_all_notifications_read(user: User) -> int:
    """Mark all unread notifications belonging to `user` as read."""
    now = datetime.now(UTC)
    result = db.session.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    db.session.commit()
    return int(result.rowcount or 0)
