"""HTTP routes for authentication, student registration/approvals, staff provisioning,
password reset, and role-based profile access.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request

from app.auth.security import ensure_csrf_token, login_required, require_role
from app.auth.service import (
    admin_trigger_password_reset,
    approve_student,
    create_staff_account,
    deactivate_staff_account,
    get_staff_account,
    list_audit_logs,
    list_staff_accounts,
    list_students,
    login_user,
    logout_user,
    reactivate_student,
    redeem_password_reset,
    register_student,
    reject_student,
    request_password_reset,
    serialize_audit_log,
    serialize_staff_record,
    serialize_student_record,
    serialize_user,
    update_own_staff_profile,
    update_staff_account,
)

bp = Blueprint("auth", __name__)


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Public & Session Authentication Routes (`/api/v1/auth/*`)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/auth/csrf")
def get_csrf():
    """Issue or return the current session's CSRF token."""
    token = ensure_csrf_token()
    return jsonify({"csrf_token": token}), 200


@bp.post("/api/v1/auth/register")
def register():
    """Student self-registration (`role='student'`, `status='pending'`)."""
    user = register_student(_json_body())
    return (
        jsonify(
            {
                "status": "pending_approval",
                "message": "Registration submitted and awaiting warden verification.",
                "user": serialize_student_record(user),
            }
        ),
        201,
    )


@bp.post("/api/v1/auth/login")
def login():
    """Authenticate user with email (or student roll number) and password."""
    user, csrf_token = login_user(_json_body())
    return (
        jsonify(
            {
                "status": "authenticated",
                "user": serialize_user(user),
                "csrf_token": csrf_token,
            }
        ),
        200,
    )


@bp.post("/api/v1/auth/logout")
def logout():
    """Invalidate the current authenticated session."""
    current = getattr(g, "current_user", None)
    logout_user(current)
    return jsonify({"status": "logged_out"}), 200


@bp.get("/api/v1/auth/me")
@login_required
def me():
    """Return safe identity and profile details for the currently authenticated user."""
    user = g.current_user
    csrf_token = ensure_csrf_token()
    return (
        jsonify(
            {
                "user": serialize_user(user),
                "csrf_token": csrf_token,
            }
        ),
        200,
    )


@bp.post("/api/v1/auth/forgot-password")
def forgot_password():
    """Initiate self-service password reset; always returns a neutral response."""
    body = _json_body()
    request_password_reset(body.get("email"))
    return (
        jsonify(
            {
                "status": "ok",
                "message": (
                    "If an eligible account exists with this email address, password reset "
                    "instructions have been sent."
                ),
            }
        ),
        200,
    )


@bp.post("/api/v1/auth/reset-password")
def reset_password():
    """Redeem a 30-minute single-use password reset token and update password."""
    redeem_password_reset(_json_body())
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Your password has been updated successfully. Please sign in.",
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Admin Student Registration Approval Routes (`/api/v1/admin/students/*`)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/admin/students")
@require_role("admin")
def admin_list_students():
    """Return all student accounts, optionally filtered by `?status=`."""
    status_filter = request.args.get("status")
    students = list_students(status_filter=status_filter)
    return jsonify({"students": [serialize_student_record(s) for s in students]}), 200


@bp.get("/api/v1/admin/students/pending")
@require_role("admin")
def admin_list_pending_students():
    """Return all student accounts currently awaiting approval (`status='pending'`)."""
    students = list_students(status_filter="pending")
    return jsonify({"students": [serialize_student_record(s) for s in students]}), 200


@bp.post("/api/v1/admin/students/<student_id>/approve")
@require_role("admin")
def admin_approve_student(student_id: str):
    """Approve a pending student registration (`pending -> active`)."""
    body = _json_body()
    note = body.get("note") or body.get("reason")
    student = approve_student(
        student_identifier=student_id,
        admin_user=g.current_user,
        note=note,
    )
    return jsonify({"student": serialize_student_record(student)}), 200


@bp.post("/api/v1/admin/students/<student_id>/reject")
@require_role("admin")
def admin_reject_student(student_id: str):
    """Reject a pending student registration (`pending -> rejected`) with a mandatory reason."""
    body = _json_body()
    reason = body.get("reason") if "reason" in body else body.get("note")
    student = reject_student(
        student_identifier=student_id,
        admin_user=g.current_user,
        reason=reason,
    )
    return jsonify({"student": serialize_student_record(student)}), 200


@bp.post("/api/v1/admin/students/<student_id>/reactivate")
@require_role("admin")
def admin_reactivate_student(student_id: str):
    """Reactivate a rejected student (`rejected -> pending`) with a mandatory reason."""
    body = _json_body()
    reason = body.get("reason") if "reason" in body else body.get("note")
    student = reactivate_student(
        student_identifier=student_id,
        admin_user=g.current_user,
        reason=reason,
    )
    return jsonify({"student": serialize_student_record(student)}), 200


# ---------------------------------------------------------------------------
# Admin Staff Account Provisioning Routes (`/api/v1/admin/staff/*`)
# ---------------------------------------------------------------------------


@bp.post("/api/v1/admin/staff")
@require_role("admin")
def admin_create_staff():
    """Create a staff account with unusable password `'!'` and send setup link email."""
    staff_user = create_staff_account(data=_json_body(), admin_user=g.current_user)
    return (
        jsonify(
            {
                "staff": serialize_staff_record(staff_user),
                "message": "Staff account created and password setup link dispatched via email.",
            }
        ),
        201,
    )


@bp.get("/api/v1/admin/staff")
@require_role("admin")
def admin_list_staff():
    """List all maintenance staff accounts."""
    staff_list = list_staff_accounts()
    return jsonify({"staff": [serialize_staff_record(s) for s in staff_list]}), 200


@bp.get("/api/v1/admin/staff/<staff_id>")
@require_role("admin")
def admin_get_staff(staff_id: str):
    """Get a single maintenance staff account."""
    staff_user = get_staff_account(staff_id)
    return jsonify({"staff": serialize_staff_record(staff_user)}), 200


@bp.patch("/api/v1/admin/staff/<staff_id>")
@require_role("admin")
def admin_update_staff(staff_id: str):
    """Update a maintenance staff account and profile."""
    staff_user = update_staff_account(
        staff_identifier=staff_id,
        data=_json_body(),
        admin_user=g.current_user,
    )
    return jsonify({"staff": serialize_staff_record(staff_user)}), 200


@bp.post("/api/v1/admin/staff/<staff_id>/deactivate")
@require_role("admin")
def admin_deactivate_staff(staff_id: str):
    """Deactivate a maintenance staff account (`status='deactivated'`)."""
    staff_user = deactivate_staff_account(
        staff_identifier=staff_id,
        admin_user=g.current_user,
    )
    return jsonify({"staff": serialize_staff_record(staff_user)}), 200


# ---------------------------------------------------------------------------
# Admin Password Reset Trigger & Audit Logs
# ---------------------------------------------------------------------------


@bp.post("/api/v1/admin/users/<user_id>/send-password-reset")
@require_role("admin")
def admin_send_password_reset(user_id: str):
    """Trigger a 30-minute password reset link email for a user (never exposes token)."""
    admin_trigger_password_reset(
        target_user_identifier=user_id,
        admin_user=g.current_user,
    )
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Password reset instructions have been queued for delivery.",
            }
        ),
        200,
    )


@bp.get("/api/v1/admin/audit-logs")
@require_role("admin")
def admin_get_audit_logs():
    """Return recent security and administrative audit logs (Admin only)."""
    raw_limit = request.args.get("limit", "100")
    limit = int(raw_limit) if raw_limit.isdigit() else 100
    logs = list_audit_logs(limit=limit)
    return jsonify({"audit_logs": [serialize_audit_log(entry) for entry in logs]}), 200


# ---------------------------------------------------------------------------
# Role-Scoped Student & Staff Profile Endpoints
# ---------------------------------------------------------------------------


@bp.get("/api/v1/student/profile")
@require_role("student")
def student_get_profile():
    """Return the authenticated active student's profile."""
    return jsonify({"user": serialize_user(g.current_user)}), 200


@bp.get("/api/v1/staff/profile")
@require_role("staff")
def staff_get_profile():
    """Return the authenticated active staff member's profile."""
    return jsonify({"user": serialize_user(g.current_user)}), 200


@bp.patch("/api/v1/staff/profile")
@require_role("staff")
def staff_patch_profile():
    """Allow an authenticated active staff member to update their own `phone` and `shift`."""
    updated = update_own_staff_profile(staff_user=g.current_user, data=_json_body())
    return jsonify({"user": serialize_user(updated)}), 200
