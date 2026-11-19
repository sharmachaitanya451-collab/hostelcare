"""HTTP routes for admin fine management and student fine viewing."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, Response, g, jsonify, request

from app.auth.security import require_role
from app.fines.payments_service import (
    create_student_razorpay_order,
    get_admin_receipt,
    get_student_receipt,
    handle_razorpay_webhook,
    list_admin_fine_payments,
    list_student_fine_payments,
    record_manual_fine_payment,
    record_payment_attempt,
    record_student_razorpay_failure,
    verify_student_razorpay_payment,
)
from app.fines.receipt_pdf import render_receipt_pdf, sanitize_receipt_filename
from app.fines.service import (
    cancel_fine,
    get_admin_fine,
    get_student_fine,
    issue_fine,
    list_admin_fine_disputes,
    list_admin_fines,
    list_student_fines,
    review_fine_dispute,
    submit_student_fine_dispute,
    waive_fine,
)

bp = Blueprint("fines", __name__)


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Admin / Warden Fine Management Routes
# ---------------------------------------------------------------------------


@bp.post("/api/v1/admin/fines")
@require_role("admin")
def admin_issue_fine_route():
    """Issue a disciplinary fine against an active student."""
    created = issue_fine(g.current_user, _json_body())
    return jsonify({"fine": created}), 201


@bp.get("/api/v1/admin/fines")
@require_role("admin")
def admin_list_fines_route():
    """List and filter hostel fines with pagination."""
    filters = {
        "student": request.args.get("student") or request.args.get("student_id"),
        "status": request.args.get("status"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "overdue": request.args.get("overdue"),
        "reference": request.args.get("reference")
        or request.args.get("reference_no")
        or request.args.get("q"),
        "page": request.args.get("page"),
        "page_size": request.args.get("page_size") or request.args.get("per_page"),
    }
    fines, pagination = list_admin_fines(filters)
    return jsonify({"fines": fines, "pagination": pagination}), 200


@bp.get("/api/v1/admin/fines/disputes")
@require_role("admin")
def admin_list_fine_disputes_route():
    """List and filter fine disputes for administrative review."""
    filters = {
        "student": request.args.get("student") or request.args.get("student_id"),
        "status": request.args.get("status") or request.args.get("dispute_status"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "reference": request.args.get("reference")
        or request.args.get("reference_no")
        or request.args.get("q"),
        "page": request.args.get("page"),
        "page_size": request.args.get("page_size") or request.args.get("per_page"),
    }
    disputes, pagination = list_admin_fine_disputes(filters)
    return jsonify({"disputes": disputes, "pagination": pagination}), 200


@bp.get("/api/v1/admin/fines/<fine_id>")
@require_role("admin")
def admin_get_fine_route(fine_id: str):
    """Return full details and history for a single fine."""
    fine = get_admin_fine(fine_id)
    return jsonify({"fine": fine}), 200


@bp.post("/api/v1/admin/fines/<fine_id>/dispute/review")
@require_role("admin")
def admin_review_fine_dispute_route(fine_id: str):
    """Approve or reject an open fine dispute."""
    updated = review_fine_dispute(g.current_user, fine_id, _json_body())
    return jsonify({"fine": updated}), 200


@bp.post("/api/v1/admin/fines/<fine_id>/waive")
@require_role("admin")
def admin_waive_fine_route(fine_id: str):
    """Waive an unpaid fine with a mandatory reason."""
    updated = waive_fine(g.current_user, fine_id, _json_body())
    return jsonify({"fine": updated}), 200


@bp.post("/api/v1/admin/fines/<fine_id>/cancel")
@require_role("admin")
def admin_cancel_fine_route(fine_id: str):
    """Cancel an unpaid fine with a mandatory reason."""
    updated = cancel_fine(g.current_user, fine_id, _json_body())
    return jsonify({"fine": updated}), 200


# ---------------------------------------------------------------------------
# Student Fine Routes (Strict Ownership)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/student/fines")
@require_role("student")
def student_list_fines_route():
    """List fines belonging strictly to the authenticated student."""
    fines = list_student_fines(g.current_user, status_filter=request.args.get("status"))
    return jsonify({"fines": fines}), 200


@bp.get("/api/v1/student/fines/<fine_id>")
@require_role("student")
def student_get_fine_route(fine_id: str):
    """Return details for a single fine owned by the authenticated student."""
    fine = get_student_fine(g.current_user, fine_id)
    return jsonify({"fine": fine}), 200


@bp.post("/api/v1/student/fines/<fine_id>/dispute")
@require_role("student")
def student_submit_fine_dispute_route(fine_id: str):
    """Submit a written dispute against an owned pending fine."""
    updated = submit_student_fine_dispute(g.current_user, fine_id, _json_body())
    return jsonify({"fine": updated}), 201


# ---------------------------------------------------------------------------
# Phase 3E.3: Payment Recording, Attempts & Receipts
# ---------------------------------------------------------------------------


@bp.post("/api/v1/admin/fines/<fine_id>/payments")
@require_role("admin")
def admin_record_fine_payment_route(fine_id: str):
    """Record a verified manual full payment against a pending fine."""
    result = record_manual_fine_payment(g.current_user, fine_id, _json_body())
    return jsonify(result), 201


@bp.get("/api/v1/admin/fines/<fine_id>/payments")
@require_role("admin")
def admin_list_fine_payments_route(fine_id: str):
    """List recorded payments and attempts for a fine."""
    result = list_admin_fine_payments(fine_id)
    return jsonify(result), 200


@bp.post("/api/v1/admin/fines/<fine_id>/payment-attempts")
@require_role("admin")
def admin_record_payment_attempt_route(fine_id: str):
    """Record an initiated or failed payment attempt without marking the fine paid."""
    result = record_payment_attempt(g.current_user, fine_id, _json_body())
    return jsonify(result), 201


def _pdf_receipt_response(receipt: dict[str, Any]) -> Response:
    pdf_bytes = render_receipt_pdf(receipt)
    filename = sanitize_receipt_filename(str(receipt.get("receiptNumber") or "receipt"))
    return Response(
        pdf_bytes,
        status=200,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/api/v1/admin/receipts/<receipt_number>")
@require_role("admin")
def admin_get_receipt_route(receipt_number: str):
    """Return structured receipt details for a recorded payment."""
    receipt = get_admin_receipt(receipt_number)
    return jsonify({"receipt": receipt}), 200


@bp.get("/api/v1/admin/receipts/<receipt_number>/pdf")
@require_role("admin")
def admin_download_receipt_pdf_route(receipt_number: str):
    """Download an official PDF receipt for a recorded payment."""
    receipt = get_admin_receipt(receipt_number)
    return _pdf_receipt_response(receipt)


@bp.get("/api/v1/student/fines/<fine_id>/payments")
@require_role("student")
def student_list_fine_payments_route(fine_id: str):
    """List payments and receipt references for an owned fine."""
    result = list_student_fine_payments(g.current_user, fine_id)
    return jsonify(result), 200


@bp.get("/api/v1/student/receipts/<receipt_number>")
@require_role("student")
def student_get_receipt_route(receipt_number: str):
    """Return receipt details for a payment on an owned fine."""
    receipt = get_student_receipt(g.current_user, receipt_number)
    return jsonify({"receipt": receipt}), 200


@bp.get("/api/v1/student/receipts/<receipt_number>/pdf")
@require_role("student")
def student_download_receipt_pdf_route(receipt_number: str):
    """Download an official PDF receipt for a payment on an owned fine."""
    receipt = get_student_receipt(g.current_user, receipt_number)
    return _pdf_receipt_response(receipt)


# ---------------------------------------------------------------------------
# Phase 3E.5: Student Razorpay Online Payments (Test Mode) & Webhooks
# ---------------------------------------------------------------------------


@bp.post("/api/v1/student/fines/<fine_id>/payments/razorpay/order")
@require_role("student")
def student_create_razorpay_order_route(fine_id: str):
    """Create (or reuse) a Razorpay Test Mode order for an owned pending fine."""
    result = create_student_razorpay_order(g.current_user, fine_id)
    status_code = 200 if result.get("reused") else 201
    return jsonify({"order": result["order"], "reused": result["reused"]}), status_code


@bp.post("/api/v1/student/fines/<fine_id>/payments/razorpay/verify")
@require_role("student")
def student_verify_razorpay_payment_route(fine_id: str):
    """Verify Razorpay signature and gateway capture status before settling the fine."""
    result = verify_student_razorpay_payment(g.current_user, fine_id, _json_body())
    return jsonify(result), 200


@bp.post("/api/v1/student/fines/<fine_id>/payments/razorpay/fail")
@require_role("student")
def student_record_razorpay_failure_route(fine_id: str):
    """Record client-side payment failure or checkout cancellation safely."""
    result = record_student_razorpay_failure(g.current_user, fine_id, _json_body())
    return jsonify(result), 200


@bp.post("/api/v1/webhooks/razorpay")
def razorpay_webhook_route():
    """Authenticate via raw-body HMAC signature and process Razorpay webhook events."""
    raw_body = request.get_data(cache=True)
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")
    result = handle_razorpay_webhook(
        raw_body=raw_body,
        signature=signature,
        event_id=event_id,
    )
    return jsonify(result), 200
