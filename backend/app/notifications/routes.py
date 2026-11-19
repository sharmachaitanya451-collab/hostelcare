"""HTTP routes for in-app notifications (`/api/v1/notifications/*`)."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.auth.security import login_required
from app.notifications.service import (
    list_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    serialize_notification,
)

bp = Blueprint("notifications", __name__)


@bp.get("/api/v1/notifications")
@login_required
def get_notifications():
    """Return in-app notifications for the currently authenticated user."""
    unread_param = str(request.args.get("unread") or "").strip().lower()
    unread_only = unread_param in ("1", "true", "yes")
    items = list_user_notifications(g.current_user, unread_only=unread_only)
    serialized = [serialize_notification(n) for n in items]
    unread_count = sum(1 for item in serialized if not item["read"])
    return (
        jsonify(
            {
                "notifications": serialized,
                "unread_count": unread_count,
            }
        ),
        200,
    )


@bp.post("/api/v1/notifications/<notification_id>/read")
@login_required
def read_single_notification(notification_id: str):
    """Mark a single notification belonging to the current user as read."""
    notif = mark_notification_read(g.current_user, notification_id)
    return jsonify({"notification": serialize_notification(notif)}), 200


@bp.post("/api/v1/notifications/read-all")
@login_required
def read_all_notifications():
    """Mark all unread notifications belonging to the current user as read."""
    updated = mark_all_notifications_read(g.current_user)
    return jsonify({"status": "ok", "updated_count": updated}), 200
