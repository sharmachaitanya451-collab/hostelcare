"""HTTP routes for admin dashboard analytics and KPI intelligence."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.analytics.complaints_service import get_complaint_analytics
from app.analytics.service import get_admin_overview_analytics
from app.auth.security import require_role

bp = Blueprint("analytics", __name__)


@bp.get("/api/v1/admin/analytics/overview")
@require_role("admin")
def admin_overview_analytics_route():
    """Return database-backed operational, occupancy, and financial KPIs for admins."""
    payload = get_admin_overview_analytics(request.args.to_dict())
    return jsonify(payload), 200


@bp.get("/api/v1/admin/analytics/complaints")
@require_role("admin")
def admin_complaint_analytics_route():
    """Return PostgreSQL-backed complaint category, trend, MTTR, SLA, and staff analytics."""
    payload = get_complaint_analytics(request.args.to_dict())
    return jsonify(payload), 200
