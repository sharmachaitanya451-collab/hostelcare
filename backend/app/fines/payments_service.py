"""Payment recording, payment attempt failure tracking, and receipt services for fines."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.audit.service import record_audit_event
from app.extensions import db
from app.fines.razorpay_client import (
    create_razorpay_order,
    fetch_razorpay_order_payments,
    fetch_razorpay_payment,
    get_razorpay_test_credentials,
    get_razorpay_webhook_secret,
    is_razorpay_configured,
    verify_checkout_signature,
    verify_webhook_signature,
)
from app.fines.service import (
    FineServiceError,
    _find_fine,
    _parse_positive_amount,
    serialize_fine_for_admin,
    serialize_fine_for_student,
)
from app.models.fines import Fine, FineHistory
from app.models.identity import StudentProfile, User
from app.models.payments import Payment, PaymentAttempt, PaymentEvent
from app.notifications.service import create_notification, notify_active_admins

VALID_MANUAL_PAYMENT_METHODS = frozenset(
    {"cash", "bank_transfer", "upi", "card", "netbanking", "wallet", "other"}
)
VALID_ATTEMPT_PAYMENT_METHODS = frozenset({"upi", "card", "netbanking", "wallet", "other"})


def _serialize_payment_for_admin(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.public_id),
        "paymentId": payment.id,
        "fineReference": payment.fine.reference_no if payment.fine else None,
        "receiptNumber": payment.receipt_number,
        "channel": payment.channel,
        "paymentMethod": payment.payment_method,
        "verificationMethod": payment.verification_method,
        "amountInr": f"{payment.amount_inr:.2f}",
        "amount": float(payment.amount_inr),
        "currency": payment.currency,
        "manualReference": payment.manual_reference,
        "gatewayOrderId": payment.gateway_order_id,
        "gatewayPaymentId": payment.gateway_payment_id,
        "transactionReference": payment.manual_reference or payment.gateway_payment_id,
        "recordedBy": payment.recorder.full_name if payment.recorder else None,
        "verifiedAt": payment.verified_at.isoformat() if payment.verified_at else None,
        "createdAt": payment.created_at.isoformat() if payment.created_at else None,
    }


def _serialize_payment_for_student(payment: Payment) -> dict[str, Any]:
    """Serialize payment for the owning student without internal admin IDs or audit metadata."""
    tx_ref = payment.manual_reference or payment.gateway_payment_id
    return {
        "id": str(payment.public_id),
        "receiptNumber": payment.receipt_number,
        "channel": payment.channel,
        "paymentMethod": payment.payment_method,
        "amountInr": f"{payment.amount_inr:.2f}",
        "amount": float(payment.amount_inr),
        "currency": payment.currency,
        "reference": tx_ref,
        "transactionReference": tx_ref,
        "gatewayOrderId": payment.gateway_order_id,
        "gatewayPaymentId": payment.gateway_payment_id,
        "status": "paid",
        "paidAt": payment.verified_at.isoformat() if payment.verified_at else None,
    }


def _build_receipt_payload(
    payment: Payment, *, include_admin_fields: bool = False
) -> dict[str, Any]:
    fine = payment.fine
    student_profile = fine.student if fine else None
    student_user = student_profile.user if student_profile else None

    receipt: dict[str, Any] = {
        "institution": "HostelCare",
        "receiptNumber": payment.receipt_number,
        "fineReference": fine.reference_no if fine else None,
        "fineCategory": fine.category if fine else None,
        "fineDescription": fine.description if fine else None,
        "amountInr": f"{payment.amount_inr:.2f}",
        "amount": float(payment.amount_inr),
        "currency": payment.currency,
        "paymentMethod": payment.payment_method,
        "channel": payment.channel,
        "transactionReference": payment.manual_reference or payment.gateway_payment_id,
        "paymentStatus": "paid",
        "paidAt": payment.verified_at.isoformat() if payment.verified_at else None,
        "studentName": student_user.full_name if student_user else None,
        "studentRoll": student_profile.roll_number if student_profile else None,
    }
    if include_admin_fields:
        receipt["recordedBy"] = payment.recorder.full_name if payment.recorder else None
    return receipt


def record_manual_fine_payment(
    admin_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Record a verified manual full payment against a `pending` fine atomically."""
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_amount = (
        data.get("amount_inr")
        if data.get("amount_inr") is not None
        else data.get("amountInr")
        if data.get("amountInr") is not None
        else data.get("amount")
    )
    amount_inr = _parse_positive_amount(raw_amount)

    raw_method = str(data.get("payment_method") or data.get("paymentMethod") or "").strip().lower()
    if raw_method not in VALID_MANUAL_PAYMENT_METHODS:
        allowed = ", ".join(sorted(VALID_MANUAL_PAYMENT_METHODS))
        raise FineServiceError(
            "validation_error",
            f"Unsupported payment_method '{raw_method}'. Must be one of: {allowed}.",
            400,
        )

    raw_ref = (
        data.get("manual_reference")
        if data.get("manual_reference") is not None
        else data.get("manualReference")
        if data.get("manualReference") is not None
        else data.get("transaction_reference")
        if data.get("transaction_reference") is not None
        else data.get("reference")
    )
    manual_reference = str(raw_ref or "").strip()
    if not manual_reference:
        raise FineServiceError(
            "validation_error",
            "A transaction/receipt reference (manual_reference) is required.",
            400,
        )
    if len(manual_reference) > 120:
        raise FineServiceError(
            "validation_error",
            "Transaction reference must not exceed 120 characters.",
            400,
        )

    try:
        fine = _find_fine(fine_identifier, lock=True)

        if fine.status != "pending":
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot record payment for fine {fine.reference_no} "
                f"because its current status is '{fine.status}'.",
                409,
            )

        existing_payment = db.session.execute(
            select(Payment).where(Payment.fine_id == fine.id)
        ).scalar_one_or_none()
        if existing_payment is not None:
            raise FineServiceError(
                "conflict",
                f"Fine {fine.reference_no} already has a recorded payment.",
                409,
            )

        dup_ref = db.session.execute(
            select(Payment.id).where(
                func.lower(Payment.manual_reference) == manual_reference.lower()
            )
        ).scalar_one_or_none()
        if dup_ref is not None:
            raise FineServiceError(
                "conflict",
                f"Transaction reference '{manual_reference}' has already been recorded.",
                409,
            )

        if amount_inr > fine.amount_inr:
            raise FineServiceError(
                "validation_error",
                f"Payment amount INR {amount_inr:.2f} exceeds outstanding balance "
                f"INR {fine.amount_inr:.2f}.",
                400,
            )
        if amount_inr < fine.amount_inr:
            raise FineServiceError(
                "validation_error",
                f"Partial payments are not supported; exact fine amount "
                f"INR {fine.amount_inr:.2f} is required.",
                400,
            )

        now = datetime.now(UTC)
        fine.status = "paid"
        fine.paid_at = now
        fine.version += 1

        payment = Payment(
            fine_id=fine.id,
            channel="manual",
            amount_inr=amount_inr,
            currency="INR",
            payment_method=raw_method,
            verification_method="manual_entry",
            verified_at=now,
            recorded_by=admin_user.id,
            manual_reference=manual_reference,
        )
        db.session.add(payment)
        db.session.flush()

        history_note = (
            f"Manual {raw_method} payment of INR {amount_inr:.2f} recorded "
            f"(Ref: {manual_reference}, Receipt: {payment.receipt_number})."
        )
        history = FineHistory(
            fine_id=fine.id,
            actor_user_id=admin_user.id,
            action="manual_payment_recorded",
            from_status="pending",
            to_status="paid",
            note=history_note,
            payment_id=payment.id,
        )
        db.session.add(history)

        create_notification(
            recipient_user_id=fine.student_user_id,
            category="payment",
            event_type="fine_payment_recorded",
            title=f"Fine Payment Recorded ({fine.reference_no})",
            message=(
                f"Payment of INR {amount_inr:.2f} via {raw_method} was recorded for fine "
                f"{fine.reference_no}. Receipt: {payment.receipt_number}."
            ),
            entity_type="fine",
            entity_ref=fine.reference_no,
        )

        record_audit_event(
            action="fine_payment_recorded",
            actor=admin_user,
            target_type="payment",
            target_id=payment.receipt_number,
            metadata={
                "fine_reference": fine.reference_no,
                "amount_inr": f"{amount_inr:.2f}",
                "payment_method": raw_method,
                "manual_reference": manual_reference,
            },
        )
        db.session.commit()
    except FineServiceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict",
            "Unable to record payment due to a database integrity constraint.",
            409,
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    reloaded_fine = _find_fine(fine.reference_no)
    reloaded_payment = db.session.execute(
        select(Payment)
        .options(
            joinedload(Payment.fine).joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(Payment.recorder),
        )
        .where(Payment.id == payment.id)
    ).scalar_one()

    return {
        "fine": serialize_fine_for_admin(reloaded_fine),
        "payment": _serialize_payment_for_admin(reloaded_payment),
        "receipt": _build_receipt_payload(reloaded_payment, include_admin_fields=True),
    }


def record_payment_attempt(
    admin_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Record an initiated or failed payment attempt without marking the fine as paid."""
    if not isinstance(data, dict):
        raise FineServiceError("validation_error", "Request body must be a JSON object.", 400)

    raw_status = str(data.get("status") or "created").strip().lower()
    if raw_status not in {"created", "failed"}:
        raise FineServiceError(
            "validation_error",
            "Payment attempt status must be 'created' or 'failed'.",
            400,
        )

    raw_method = data.get("payment_method") or data.get("paymentMethod")
    payment_method: str | None = None
    if raw_method is not None and str(raw_method).strip():
        payment_method = str(raw_method).strip().lower()
        if payment_method not in VALID_ATTEMPT_PAYMENT_METHODS:
            allowed = ", ".join(sorted(VALID_ATTEMPT_PAYMENT_METHODS))
            raise FineServiceError(
                "validation_error",
                f"Unsupported attempt payment_method '{payment_method}'. "
                f"Must be one of: {allowed}.",
                400,
            )

    failure_code = str(data.get("failure_code") or "").strip()[:60] or None
    failure_reason = str(data.get("failure_reason") or "").strip()[:255] or None
    if raw_status == "failed" and not failure_reason:
        raise FineServiceError(
            "validation_error",
            "failure_reason is required when recording a failed payment attempt.",
            400,
        )

    try:
        fine = _find_fine(fine_identifier, lock=True)
        if fine.status != "pending":
            raise FineServiceError(
                "invalid_state_transition",
                f"Cannot record payment attempt for fine {fine.reference_no} "
                f"with status '{fine.status}'.",
                409,
            )

        raw_amount = (
            data.get("amount_inr")
            if data.get("amount_inr") is not None
            else data.get("amount")
            if data.get("amount") is not None
            else fine.amount_inr
        )
        amount_inr = _parse_positive_amount(raw_amount)
        if amount_inr != fine.amount_inr:
            raise FineServiceError(
                "validation_error",
                f"Attempt amount must match exact fine amount INR {fine.amount_inr:.2f}.",
                400,
            )

        attempt = PaymentAttempt(
            fine_id=fine.id,
            initiated_by=admin_user.id,
            amount_inr=amount_inr,
            currency="INR",
            payment_method=payment_method,
            status=raw_status,
            failure_code=failure_code if raw_status == "failed" else None,
            failure_reason=failure_reason if raw_status == "failed" else None,
        )
        db.session.add(attempt)
        db.session.flush()

        db.session.add(
            PaymentEvent(
                payment_attempt_id=attempt.id,
                source="admin",
                event_type="payment_attempt_failed"
                if raw_status == "failed"
                else "payment_attempt_created",
                outcome="rejected" if raw_status == "failed" else "applied",
                payload={
                    "fine_reference": fine.reference_no,
                    "amount_inr": f"{amount_inr:.2f}",
                    "failure_code": failure_code,
                },
            )
        )

        db.session.add(
            FineHistory(
                fine_id=fine.id,
                actor_user_id=admin_user.id,
                action="payment_attempted",
                from_status="pending",
                to_status="pending",
                note=(
                    f"Payment attempt failed: {failure_reason}"
                    if raw_status == "failed"
                    else "Payment attempt initiated."
                ),
                payment_attempt_id=attempt.id,
            )
        )
        db.session.commit()
    except FineServiceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict",
            "Unable to record payment attempt due to an active attempt or constraint.",
            409,
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    return {
        "attempt": {
            "id": str(attempt.public_id),
            "fineReference": fine.reference_no,
            "status": attempt.status,
            "amountInr": f"{attempt.amount_inr:.2f}",
            "paymentMethod": attempt.payment_method,
            "failureCode": attempt.failure_code,
            "failureReason": attempt.failure_reason,
            "createdAt": attempt.created_at.isoformat() if attempt.created_at else None,
        }
    }


def list_admin_fine_payments(fine_identifier: str) -> dict[str, Any]:
    """Return recorded payment and attempts for a fine (admin view)."""
    fine = _find_fine(fine_identifier)
    payment = db.session.execute(
        select(Payment)
        .options(
            joinedload(Payment.fine).joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(Payment.recorder),
        )
        .where(Payment.fine_id == fine.id)
    ).scalar_one_or_none()
    attempts = (
        db.session.execute(
            select(PaymentAttempt)
            .where(PaymentAttempt.fine_id == fine.id)
            .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
        )
        .scalars()
        .all()
    )
    return {
        "payments": [_serialize_payment_for_admin(payment)] if payment else [],
        "outstandingInr": "0.00" if fine.status == "paid" or payment else f"{fine.amount_inr:.2f}",
        "attempts": [
            {
                "id": str(a.public_id),
                "status": a.status,
                "amountInr": f"{a.amount_inr:.2f}",
                "paymentMethod": a.payment_method,
                "gatewayOrderId": a.gateway_order_id,
                "gatewayPaymentId": a.gateway_payment_id,
                "failureCode": a.failure_code,
                "failureReason": a.failure_reason,
                "verifiedAt": a.verified_at.isoformat() if a.verified_at else None,
                "createdAt": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attempts
        ],
    }


def list_student_fine_payments(student_user: User, fine_identifier: str) -> dict[str, Any]:
    """Return payment and receipt details for an owned fine."""
    fine = _find_fine(fine_identifier)
    if fine.student_user_id != student_user.id:
        raise FineServiceError(
            "forbidden",
            "You do not have permission to access another student's payment history.",
            403,
        )

    payment = db.session.execute(
        select(Payment)
        .options(
            joinedload(Payment.fine).joinedload(Fine.student).joinedload(StudentProfile.user),
        )
        .where(Payment.fine_id == fine.id)
    ).scalar_one_or_none()

    return {
        "fineReference": fine.reference_no,
        "fineStatus": fine.status,
        "outstandingInr": "0.00"
        if fine.status in {"paid", "waived", "cancelled"} or payment
        else f"{fine.amount_inr:.2f}",
        "onlinePaymentEnabled": is_razorpay_configured(),
        "payments": [_serialize_payment_for_student(payment)] if payment else [],
    }


def _find_payment_by_receipt(receipt_number: str) -> Payment:
    clean_rcp = str(receipt_number or "").strip()
    if not clean_rcp:
        raise FineServiceError("not_found", "Receipt number is required.", 404)

    payment = db.session.execute(
        select(Payment)
        .options(
            joinedload(Payment.fine).joinedload(Fine.student).joinedload(StudentProfile.user),
            joinedload(Payment.recorder),
        )
        .where(func.upper(Payment.receipt_number) == clean_rcp.upper())
    ).scalar_one_or_none()
    if payment is None:
        raise FineServiceError("not_found", f"Receipt '{clean_rcp}' not found.", 404)
    return payment


def get_admin_receipt(receipt_number: str) -> dict[str, Any]:
    payment = _find_payment_by_receipt(receipt_number)
    return _build_receipt_payload(payment, include_admin_fields=True)


def get_student_receipt(student_user: User, receipt_number: str) -> dict[str, Any]:
    payment = _find_payment_by_receipt(receipt_number)
    if payment.fine.student_user_id != student_user.id:
        raise FineServiceError(
            "forbidden",
            "You do not have permission to access another student's receipt.",
            403,
        )
    return _build_receipt_payload(payment, include_admin_fields=False)


# ---------------------------------------------------------------------------
# Phase 3E.5: Student Razorpay Online Payments (Test Mode Only) & Webhooks
# ---------------------------------------------------------------------------


def _fine_amount_paise(fine: Fine) -> int:
    """Convert exact numeric INR fine amount to integer paise without float drift."""
    return int((fine.amount_inr * 100).to_integral_value())


def _normalize_gateway_method(raw_method: Any) -> str:
    val = str(raw_method or "").strip().lower()
    if val in VALID_ATTEMPT_PAYMENT_METHODS:
        return val
    return "other"


def _parse_gateway_timestamp(raw_epoch: Any) -> datetime:
    if isinstance(raw_epoch, (int, float)) and raw_epoch > 0:
        try:
            return datetime.fromtimestamp(int(raw_epoch), tz=UTC)
        except (OverflowError, OSError, ValueError):
            pass
    return datetime.now(UTC)


def _sanitized_gateway_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a minimal, safe snapshot of gateway metadata for PaymentEvent logs."""
    if not isinstance(payload, dict):
        return {}
    allowed_keys = ("id", "order_id", "amount", "currency", "status", "method", "error_code")
    snap = {k: payload[k] for k in allowed_keys if k in payload}
    if "error_description" in payload and payload["error_description"]:
        snap["error_description"] = str(payload["error_description"])[:240]
    return snap


def _flag_captured_unapplied(
    *,
    attempt: PaymentAttempt,
    fine: Fine,
    gateway_payment_id: str,
    normalized_method: str,
    verified_at: datetime,
    actor_user: User | None,
    failure_code: str,
    failure_reason: str,
    event_source: str,
    event_type: str,
    gateway_event_id: str | None,
    signature_valid: bool | None,
    event_payload: dict[str, Any],
) -> None:
    """Record a captured gateway payment that could not settle the fine safely."""
    now = datetime.now(UTC)
    attempt.gateway_payment_id = gateway_payment_id
    attempt.payment_method = normalized_method
    attempt.status = "captured_unapplied"
    attempt.verified_at = verified_at
    attempt.failure_code = failure_code[:60]
    attempt.failure_reason = failure_reason[:255]
    attempt.updated_at = now

    db.session.add(
        FineHistory(
            fine_id=fine.id,
            actor_user_id=actor_user.id if actor_user else None,
            action="payment_needs_review",
            from_status=fine.status,
            to_status=fine.status,
            note=f"{failure_reason} (Gateway payment: {gateway_payment_id}).",
            payment_attempt_id=attempt.id,
        )
    )
    db.session.add(
        PaymentEvent(
            payment_attempt_id=attempt.id,
            source=event_source,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            signature_valid=signature_valid,
            outcome="needs_review",
            payload=event_payload,
        )
    )
    notify_active_admins(
        category="payment",
        event_type="payment_needs_review",
        title=f"Payment Needs Review ({fine.reference_no})",
        message=(
            f"Razorpay payment {gateway_payment_id} was captured for fine {fine.reference_no}, "
            f"but could not be auto-applied ({failure_reason}). "
            "Please inspect for reconciliation/refund."
        ),
        entity_type="fine",
        entity_ref=fine.reference_no,
    )
    record_audit_event(
        action="fine_payment_needs_review",
        actor=actor_user,
        actor_role="system" if actor_user is None else None,
        target_type="fine",
        target_id=fine.reference_no,
        metadata={
            "fine_reference": fine.reference_no,
            "attempt_id": str(attempt.public_id),
            "gateway_payment_id": gateway_payment_id,
            "failure_code": failure_code,
        },
    )


def _settle_razorpay_payment(
    *,
    fine: Fine,
    attempt: PaymentAttempt,
    gateway_payment_id: str,
    amount_paise: int,
    currency: str,
    raw_method: Any,
    verification_method: str,
    verified_at: datetime,
    actor_user: User | None,
    event_source: str,
    event_type: str,
    gateway_event_id: str | None,
    signature_valid: bool | None,
    event_payload: dict[str, Any],
) -> dict[str, Any]:
    """Atomically settle an eligible pending fine or safely isolate conflicts."""
    now = datetime.now(UTC)
    normalized_method = _normalize_gateway_method(raw_method)
    expected_paise = _fine_amount_paise(fine)

    existing_payment = db.session.execute(
        select(Payment).options(joinedload(Payment.recorder)).where(Payment.fine_id == fine.id)
    ).scalar_one_or_none()

    if existing_payment is not None:
        if existing_payment.gateway_payment_id == gateway_payment_id:
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id,
                    source=event_source,
                    event_type=event_type,
                    gateway_event_id=gateway_event_id,
                    signature_valid=signature_valid,
                    outcome="duplicate",
                    payload=event_payload,
                )
            )
            db.session.commit()
            return {"status": "duplicate", "fine": fine, "payment": existing_payment}

        reason = (
            f"Fine was already settled via {existing_payment.channel} "
            f"(receipt {existing_payment.receipt_number}); "
            f"captured payment {gateway_payment_id} requires refund/review."
        )
        _flag_captured_unapplied(
            attempt=attempt,
            fine=fine,
            gateway_payment_id=gateway_payment_id,
            normalized_method=normalized_method,
            verified_at=verified_at,
            actor_user=actor_user,
            failure_code="fine_already_paid",
            failure_reason=reason,
            event_source=event_source,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            signature_valid=signature_valid,
            event_payload=event_payload,
        )
        db.session.commit()
        return {
            "status": "needs_review",
            "conflict_reason": reason,
            "fine": fine,
            "payment": existing_payment,
        }

    if fine.status != "pending":
        reason = f"Payment captured while fine status was '{fine.status}'."
        _flag_captured_unapplied(
            attempt=attempt,
            fine=fine,
            gateway_payment_id=gateway_payment_id,
            normalized_method=normalized_method,
            verified_at=verified_at,
            actor_user=actor_user,
            failure_code=f"fine_status_{fine.status}",
            failure_reason=reason,
            event_source=event_source,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            signature_valid=signature_valid,
            event_payload=event_payload,
        )
        db.session.commit()
        return {"status": "needs_review", "conflict_reason": reason, "fine": fine, "payment": None}

    if str(currency or "").strip().upper() != "INR" or int(amount_paise) != expected_paise:
        reason = (
            f"Gateway amount ({amount_paise} {currency}) did not match exact fine amount "
            f"({expected_paise} INR)."
        )
        _flag_captured_unapplied(
            attempt=attempt,
            fine=fine,
            gateway_payment_id=gateway_payment_id,
            normalized_method=normalized_method,
            verified_at=verified_at,
            actor_user=actor_user,
            failure_code="amount_mismatch",
            failure_reason=reason,
            event_source=event_source,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            signature_valid=signature_valid,
            event_payload=event_payload,
        )
        db.session.commit()
        return {"status": "needs_review", "conflict_reason": reason, "fine": fine, "payment": None}

    # Atomic settlement respecting DEFERRED constraint triggers T2a, T2b and trigger T3.
    attempt.gateway_payment_id = gateway_payment_id
    attempt.payment_method = normalized_method
    attempt.status = "succeeded"
    attempt.verified_at = verified_at
    attempt.failure_code = None
    attempt.failure_reason = None
    attempt.updated_at = now

    fine.status = "paid"
    fine.paid_at = verified_at
    fine.version = int(fine.version) + 1
    fine.updated_at = now

    payment = Payment(
        fine_id=fine.id,
        payment_attempt_id=attempt.id,
        channel="razorpay",
        amount_inr=fine.amount_inr,
        currency="INR",
        gateway_order_id=attempt.gateway_order_id,
        gateway_payment_id=gateway_payment_id,
        payment_method=normalized_method,
        verification_method=verification_method,
        verified_at=verified_at,
        recorded_by=None,
        manual_reference=None,
    )
    db.session.add(payment)
    db.session.flush()

    db.session.add(
        FineHistory(
            fine_id=fine.id,
            actor_user_id=actor_user.id if actor_user else None,
            action="payment_verified",
            from_status="pending",
            to_status="paid",
            note=(
                f"Verified Razorpay online {normalized_method.upper()} payment "
                f"({gateway_payment_id}). Receipt: {payment.receipt_number}."
            ),
            payment_id=payment.id,
            payment_attempt_id=attempt.id,
        )
    )
    db.session.add(
        PaymentEvent(
            payment_attempt_id=attempt.id,
            source=event_source,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            signature_valid=signature_valid,
            outcome="applied",
            payload=event_payload,
        )
    )
    create_notification(
        recipient_user_id=fine.student_user_id,
        category="payment",
        event_type="fine_payment_verified",
        title=f"Fine Paid Online ({fine.reference_no})",
        message=(
            f"Online payment of INR {fine.amount_inr:.2f} via Razorpay ({normalized_method}) "
            f"was verified for fine {fine.reference_no}. Receipt: {payment.receipt_number}."
        ),
        entity_type="fine",
        entity_ref=fine.reference_no,
    )
    notify_active_admins(
        category="payment",
        event_type="fine_payment_verified",
        title=f"Online Fine Payment Received ({fine.reference_no})",
        message=(
            f"Student paid fine {fine.reference_no} (INR {fine.amount_inr:.2f}) via Razorpay "
            f"({normalized_method}). Receipt: {payment.receipt_number}."
        ),
        entity_type="fine",
        entity_ref=fine.reference_no,
    )
    record_audit_event(
        action="fine_online_payment_verified",
        actor=actor_user,
        actor_role="system" if actor_user is None else None,
        target_type="payment",
        target_id=payment.receipt_number,
        metadata={
            "fine_reference": fine.reference_no,
            "channel": "razorpay",
            "verification_method": verification_method,
            "payment_method": normalized_method,
            "gateway_order_id": attempt.gateway_order_id,
            "gateway_payment_id": gateway_payment_id,
            "amount_inr": f"{fine.amount_inr:.2f}",
        },
    )
    db.session.commit()
    return {"status": "applied", "fine": fine, "payment": payment}


def create_student_razorpay_order(student_user: User, fine_identifier: str) -> dict[str, Any]:
    """Create (or reuse) a Razorpay Test Mode checkout order for an eligible pending fine."""
    key_id, _key_secret, _api_base, _timeout = get_razorpay_test_credentials()

    try:
        fine = _find_fine(fine_identifier, lock=True)
        if fine.student_user_id != student_user.id:
            raise FineServiceError(
                "forbidden",
                "You do not have permission to initiate payment for another student's fine.",
                403,
            )

        existing_payment = db.session.execute(
            select(Payment).where(Payment.fine_id == fine.id)
        ).scalar_one_or_none()
        if existing_payment is not None or fine.status == "paid":
            raise FineServiceError("conflict", "This fine has already been paid.", 409)
        if fine.status == "disputed":
            raise FineServiceError(
                "conflict",
                "Disputed fines cannot be paid while under Warden review.",
                409,
            )
        if fine.status != "pending":
            raise FineServiceError(
                "conflict",
                f"Cannot pay a fine in '{fine.status}' status.",
                409,
            )

        amount_paise = _fine_amount_paise(fine)
        open_attempt = db.session.execute(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.fine_id == fine.id,
                PaymentAttempt.status.in_(("created", "processing")),
            )
            .with_for_update()
        ).scalar_one_or_none()

        if open_attempt is not None:
            if open_attempt.status == "processing":
                raise FineServiceError(
                    "payment_in_progress",
                    "A payment verification is already in progress for this fine. "
                    "Please wait a moment and refresh.",
                    409,
                )
            if open_attempt.gateway_order_id and open_attempt.amount_inr == fine.amount_inr:
                db.session.add(
                    PaymentEvent(
                        payment_attempt_id=open_attempt.id,
                        source="system",
                        event_type="order.reused",
                        outcome="duplicate",
                        payload={
                            "order_id": open_attempt.gateway_order_id,
                            "amount_paise": amount_paise,
                            "currency": "INR",
                        },
                    )
                )
                db.session.commit()
                return {
                    "reused": True,
                    "order": {
                        "attemptId": str(open_attempt.public_id),
                        "orderId": open_attempt.gateway_order_id,
                        "keyId": key_id,
                        "amountPaise": amount_paise,
                        "amountInr": f"{fine.amount_inr:.2f}",
                        "currency": "INR",
                        "fineReference": fine.reference_no,
                        "name": "HostelCare",
                        "description": f"Fine Settlement — {fine.reference_no}",
                        "prefill": {
                            "name": student_user.full_name,
                            "email": student_user.email,
                            "contact": student_user.phone or "",
                        },
                        "notes": {
                            "fineReference": fine.reference_no,
                            "attemptId": str(open_attempt.public_id),
                        },
                    },
                }

            open_attempt.status = "cancelled"
            open_attempt.failure_code = "superseded"
            open_attempt.failure_reason = "Replaced by new online checkout session."
            open_attempt.updated_at = datetime.now(UTC)
            db.session.flush()

        student_profile = fine.student
        rzp_order = create_razorpay_order(
            amount_paise=amount_paise,
            currency="INR",
            receipt=fine.reference_no,
            notes={
                "fine_reference": fine.reference_no,
                "student_roll": student_profile.roll_number if student_profile else "",
                "mode": "test",
            },
        )
        gateway_order_id = str(rzp_order.get("id") or "").strip()
        if not gateway_order_id:
            raise FineServiceError(
                "gateway_error",
                "Payment gateway did not return a valid order identifier.",
                502,
            )

        attempt = PaymentAttempt(
            fine_id=fine.id,
            initiated_by=student_user.id,
            amount_inr=fine.amount_inr,
            currency="INR",
            gateway_order_id=gateway_order_id,
            status="created",
        )
        db.session.add(attempt)
        db.session.flush()

        db.session.add(
            FineHistory(
                fine_id=fine.id,
                actor_user_id=student_user.id,
                action="payment_attempted",
                from_status=fine.status,
                to_status=fine.status,
                note=f"Initiated Razorpay online checkout (Order {gateway_order_id}).",
                payment_attempt_id=attempt.id,
            )
        )
        db.session.add(
            PaymentEvent(
                payment_attempt_id=attempt.id,
                source="system",
                event_type="order.created",
                outcome="applied",
                payload={
                    "order_id": gateway_order_id,
                    "amount_paise": amount_paise,
                    "currency": "INR",
                },
            )
        )
        record_audit_event(
            action="fine_online_order_created",
            actor=student_user,
            target_type="fine",
            target_id=fine.reference_no,
            metadata={
                "fine_reference": fine.reference_no,
                "attempt_id": str(attempt.public_id),
                "gateway_order_id": gateway_order_id,
                "amount_inr": f"{fine.amount_inr:.2f}",
            },
        )
        db.session.commit()

        return {
            "reused": False,
            "order": {
                "attemptId": str(attempt.public_id),
                "orderId": gateway_order_id,
                "keyId": key_id,
                "amountPaise": amount_paise,
                "amountInr": f"{fine.amount_inr:.2f}",
                "currency": "INR",
                "fineReference": fine.reference_no,
                "name": "HostelCare",
                "description": f"Fine Settlement — {fine.reference_no}",
                "prefill": {
                    "name": student_user.full_name,
                    "email": student_user.email,
                    "contact": student_user.phone or "",
                },
                "notes": {
                    "fineReference": fine.reference_no,
                    "attemptId": str(attempt.public_id),
                },
            },
        }
    except FineServiceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict",
            "An open checkout session already exists for this fine. Please refresh and retry.",
            409,
        ) from exc
    except Exception:
        db.session.rollback()
        raise


def verify_student_razorpay_payment(
    student_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Verify student Checkout callback HMAC signature + Razorpay captured status and settle."""
    if not isinstance(data, dict):
        raise FineServiceError(
            "validation_error", "Verification payload must be a JSON object.", 400
        )

    _key_id, key_secret, _api_base, _timeout = get_razorpay_test_credentials()

    order_id = str(data.get("razorpay_order_id") or data.get("orderId") or "").strip()
    payment_id = str(data.get("razorpay_payment_id") or data.get("paymentId") or "").strip()
    signature = str(data.get("razorpay_signature") or data.get("signature") or "").strip()

    if not order_id or not payment_id or not signature:
        raise FineServiceError(
            "validation_error",
            "razorpay_order_id, razorpay_payment_id, and razorpay_signature are required.",
            400,
        )

    try:
        fine = _find_fine(fine_identifier, lock=True)
        if fine.student_user_id != student_user.id:
            raise FineServiceError(
                "forbidden",
                "You do not have permission to verify payment for another student's fine.",
                403,
            )

        attempt = db.session.execute(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.fine_id == fine.id,
                PaymentAttempt.gateway_order_id == order_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if attempt is None:
            raise FineServiceError(
                "not_found",
                "No matching payment order was found for this fine.",
                404,
            )

        if not verify_checkout_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            key_secret=key_secret,
        ):
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id,
                    source="client_callback",
                    event_type="payment.verify",
                    signature_valid=False,
                    outcome="rejected",
                    payload={"order_id": order_id, "payment_id": payment_id},
                )
            )
            db.session.commit()
            raise FineServiceError(
                "invalid_signature",
                "Razorpay payment signature verification failed.",
                400,
            )

        # Idempotent return if webhook already settled this exact payment before client callback.
        existing_same = db.session.execute(
            select(Payment)
            .options(joinedload(Payment.recorder))
            .where(
                Payment.fine_id == fine.id,
                Payment.gateway_payment_id == payment_id,
            )
        ).scalar_one_or_none()
        if existing_same is not None:
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id,
                    source="client_callback",
                    event_type="payment.verify",
                    signature_valid=True,
                    outcome="duplicate",
                    payload={"order_id": order_id, "payment_id": payment_id},
                )
            )
            db.session.commit()
            reloaded_fine = _find_fine(fine.reference_no)
            reloaded_payment = _find_payment_by_receipt(existing_same.receipt_number)
            return {
                "alreadySettled": True,
                "fine": serialize_fine_for_student(reloaded_fine),
                "payment": _serialize_payment_for_student(reloaded_payment),
                "receipt": _build_receipt_payload(reloaded_payment, include_admin_fields=False),
            }

        rzp_payment = fetch_razorpay_payment(payment_id)
        if str(rzp_payment.get("order_id") or "").strip() != order_id:
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id,
                    source="server_verify",
                    event_type="payment.order_mismatch",
                    signature_valid=True,
                    outcome="rejected",
                    payload=_sanitized_gateway_snapshot(rzp_payment),
                )
            )
            db.session.commit()
            raise FineServiceError(
                "order_mismatch",
                "Payment does not belong to the initiated Razorpay order.",
                400,
            )

        rzp_status = str(rzp_payment.get("status") or "").strip().lower()
        rzp_amount = int(rzp_payment.get("amount") or 0)
        rzp_currency = str(rzp_payment.get("currency") or "").strip().upper()

        if rzp_status != "captured":
            now = datetime.now(UTC)
            if rzp_status == "authorized":
                attempt.status = "processing"
                attempt.gateway_payment_id = payment_id
                attempt.payment_method = _normalize_gateway_method(rzp_payment.get("method"))
                attempt.updated_at = now
                db.session.add(
                    PaymentEvent(
                        payment_attempt_id=attempt.id,
                        source="server_verify",
                        event_type="payment.authorized",
                        signature_valid=True,
                        outcome="ignored",
                        payload=_sanitized_gateway_snapshot(rzp_payment),
                    )
                )
                db.session.commit()
                raise FineServiceError(
                    "payment_not_captured",
                    "Payment is authorized but not yet captured. Please wait a moment and refresh.",
                    409,
                )

            attempt.status = "failed"
            attempt.gateway_payment_id = payment_id
            attempt.failure_code = str(rzp_payment.get("error_code") or f"status_{rzp_status}")[:60]
            attempt.failure_reason = str(
                rzp_payment.get("error_description")
                or f"Gateway payment is in '{rzp_status}' state."
            )[:255]
            attempt.updated_at = now
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id,
                    source="server_verify",
                    event_type=f"payment.{rzp_status or 'invalid'}",
                    signature_valid=True,
                    outcome="rejected",
                    payload=_sanitized_gateway_snapshot(rzp_payment),
                )
            )
            db.session.commit()
            raise FineServiceError(
                "payment_not_captured",
                "Payment could not be completed because it was not captured by Razorpay.",
                400,
            )

        settlement = _settle_razorpay_payment(
            fine=fine,
            attempt=attempt,
            gateway_payment_id=payment_id,
            amount_paise=rzp_amount,
            currency=rzp_currency,
            raw_method=rzp_payment.get("method"),
            verification_method="api_fetch",
            verified_at=_parse_gateway_timestamp(rzp_payment.get("created_at")),
            actor_user=student_user,
            event_source="server_verify",
            event_type="payment.verified",
            gateway_event_id=None,
            signature_valid=True,
            event_payload=_sanitized_gateway_snapshot(rzp_payment),
        )
        if settlement["status"] == "needs_review":
            raise FineServiceError(
                "conflict",
                settlement.get("conflict_reason")
                or "This fine could not be settled automatically and needs Warden review.",
                409,
            )
    except FineServiceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise FineServiceError(
            "conflict",
            "Unable to settle payment due to a concurrent settlement conflict.",
            409,
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    reloaded_fine = _find_fine(fine.reference_no)
    settled_payment = settlement["payment"]
    reloaded_payment = _find_payment_by_receipt(settled_payment.receipt_number)
    return {
        "alreadySettled": settlement["status"] == "duplicate",
        "fine": serialize_fine_for_student(reloaded_fine),
        "payment": _serialize_payment_for_student(reloaded_payment),
        "receipt": _build_receipt_payload(reloaded_payment, include_admin_fields=False),
    }


def record_student_razorpay_failure(
    student_user: User, fine_identifier: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Record client-reported Razorpay failure or modal dismissal without marking fine paid."""
    if not isinstance(data, dict):
        data = {}

    order_id = str(data.get("razorpay_order_id") or data.get("orderId") or "").strip()
    payment_id = str(data.get("razorpay_payment_id") or data.get("paymentId") or "").strip() or None
    cancelled = bool(data.get("cancelled", False))
    default_code = "checkout_dismissed" if cancelled else "payment_failed"
    failure_code = str(data.get("error_code") or data.get("code") or default_code).strip()[:60]
    default_reason = (
        "Student cancelled checkout before completing payment."
        if cancelled
        else "Online payment failed."
    )
    failure_reason = str(
        data.get("error_description") or data.get("reason") or default_reason
    ).strip()[:255]

    fine = _find_fine(fine_identifier, lock=True)
    if fine.student_user_id != student_user.id:
        raise FineServiceError(
            "forbidden",
            "You do not have permission to update another student's payment attempt.",
            403,
        )

    stmt = select(PaymentAttempt).where(PaymentAttempt.fine_id == fine.id)
    if order_id:
        stmt = stmt.where(PaymentAttempt.gateway_order_id == order_id)
    else:
        stmt = stmt.where(PaymentAttempt.status == "created")

    attempt = db.session.execute(
        stmt.order_by(PaymentAttempt.id.desc()).with_for_update()
    ).scalar_one_or_none()

    if attempt is None:
        return {"recorded": False, "status": fine.status}

    if attempt.status in ("succeeded", "captured_unapplied"):
        return {"recorded": False, "status": attempt.status}

    if attempt.status == "created":
        attempt.status = "cancelled" if cancelled else "failed"
        if payment_id and not attempt.gateway_payment_id:
            existing_pid = db.session.execute(
                select(PaymentAttempt.id).where(PaymentAttempt.gateway_payment_id == payment_id)
            ).scalar_one_or_none()
            if existing_pid is None:
                attempt.gateway_payment_id = payment_id
        attempt.failure_code = failure_code
        attempt.failure_reason = failure_reason
        attempt.updated_at = datetime.now(UTC)

    db.session.add(
        PaymentEvent(
            payment_attempt_id=attempt.id,
            source="client_callback",
            event_type="checkout.dismissed" if cancelled else "payment.failed",
            outcome="applied",
            payload={
                "order_id": attempt.gateway_order_id,
                "payment_id": payment_id,
                "failure_code": failure_code,
                "failure_reason": failure_reason,
            },
        )
    )
    db.session.commit()
    return {"recorded": True, "attemptStatus": attempt.status, "fineStatus": fine.status}


def handle_razorpay_webhook(
    *,
    raw_body: bytes,
    signature: str | None,
    event_id: str | None,
) -> dict[str, Any]:
    """Process authenticated Razorpay webhook events idempotently."""
    webhook_secret = get_razorpay_webhook_secret()

    if not verify_webhook_signature(
        raw_body=raw_body,
        signature=signature,
        webhook_secret=webhook_secret,
    ):
        db.session.add(
            PaymentEvent(
                payment_attempt_id=None,
                source="webhook",
                event_type="webhook.invalid_signature",
                gateway_event_id=None,
                signature_valid=False,
                outcome="rejected",
                payload={"has_signature": bool(signature)},
            )
        )
        db.session.commit()
        raise FineServiceError("invalid_signature", "Invalid Razorpay webhook signature.", 400)

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FineServiceError("validation_error", "Malformed JSON webhook body.", 400) from exc

    if not isinstance(body, dict):
        raise FineServiceError("validation_error", "Webhook payload must be a JSON object.", 400)

    clean_event_id = str(event_id or "").strip()[:100] or None
    if clean_event_id:
        existing_evt = db.session.execute(
            select(PaymentEvent.id).where(PaymentEvent.gateway_event_id == clean_event_id)
        ).scalar_one_or_none()
        if existing_evt is not None:
            return {"status": "duplicate", "eventId": clean_event_id}

    try:
        return _dispatch_verified_webhook_event(body=body, clean_event_id=clean_event_id)
    except IntegrityError as exc:
        db.session.rollback()
        constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        is_event_id_conflict = (
            constraint_name == "uq_payment_events_gateway_event"
            if constraint_name is not None
            else "uq_payment_events_gateway_event" in str(exc)
        )
        if clean_event_id and is_event_id_conflict:
            existing_evt = db.session.execute(
                select(PaymentEvent.id).where(PaymentEvent.gateway_event_id == clean_event_id)
            ).scalar_one_or_none()
            if existing_evt is not None:
                return {"status": "duplicate", "eventId": clean_event_id}
        raise


def _dispatch_verified_webhook_event(
    *, body: dict[str, Any], clean_event_id: str | None
) -> dict[str, Any]:
    """Dispatch a signature-verified Razorpay webhook event within its DB transaction."""
    event_type = str(body.get("event") or "").strip()[:60] or "unknown"
    payload_obj = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    payment_entity = (
        payload_obj.get("payment", {}).get("entity")
        if isinstance(payload_obj.get("payment"), dict)
        and isinstance(payload_obj.get("payment", {}).get("entity"), dict)
        else {}
    )
    order_entity = (
        payload_obj.get("order", {}).get("entity")
        if isinstance(payload_obj.get("order"), dict)
        and isinstance(payload_obj.get("order", {}).get("entity"), dict)
        else {}
    )

    if event_type in ("payment.captured", "order.paid"):
        order_id = str(payment_entity.get("order_id") or order_entity.get("id") or "").strip()
        payment_id = str(payment_entity.get("id") or "").strip()

        if event_type == "order.paid" and not payment_id and order_id:
            order_payments = fetch_razorpay_order_payments(order_id)
            captured = next(
                (p for p in order_payments if str(p.get("status") or "").lower() == "captured"),
                None,
            )
            if captured:
                payment_entity = captured
                payment_id = str(captured.get("id") or "").strip()

        attempt = (
            db.session.execute(
                select(PaymentAttempt)
                .where(PaymentAttempt.gateway_order_id == order_id)
                .with_for_update()
            ).scalar_one_or_none()
            if order_id
            else None
        )
        if attempt is None or not payment_id:
            db.session.add(
                PaymentEvent(
                    payment_attempt_id=attempt.id if attempt else None,
                    source="webhook",
                    event_type=event_type,
                    gateway_event_id=clean_event_id,
                    signature_valid=True,
                    outcome="ignored",
                    payload={
                        "order_id": order_id or None,
                        "payment_id": payment_id or None,
                    },
                )
            )
            db.session.commit()
            return {"status": "ignored", "eventType": event_type}

        fine = db.session.execute(
            select(Fine).where(Fine.id == attempt.fine_id).with_for_update()
        ).scalar_one()

        result = _settle_razorpay_payment(
            fine=fine,
            attempt=attempt,
            gateway_payment_id=payment_id,
            amount_paise=int(payment_entity.get("amount") or 0),
            currency=str(payment_entity.get("currency") or "INR").strip().upper(),
            raw_method=payment_entity.get("method"),
            verification_method="webhook",
            verified_at=_parse_gateway_timestamp(payment_entity.get("created_at")),
            actor_user=None,
            event_source="webhook",
            event_type=event_type,
            gateway_event_id=clean_event_id,
            signature_valid=True,
            event_payload=_sanitized_gateway_snapshot(payment_entity),
        )
        return {
            "status": result["status"],
            "eventType": event_type,
            "fineReference": fine.reference_no,
            "receiptNumber": result["payment"].receipt_number
            if result.get("payment") and result["status"] in ("applied", "duplicate")
            else None,
        }

    if event_type == "payment.failed":
        order_id = str(payment_entity.get("order_id") or "").strip()
        payment_id = str(payment_entity.get("id") or "").strip() or None
        attempt = (
            db.session.execute(
                select(PaymentAttempt)
                .where(PaymentAttempt.gateway_order_id == order_id)
                .with_for_update()
            ).scalar_one_or_none()
            if order_id
            else None
        )
        outcome = "ignored"
        if attempt is not None and attempt.status in ("created", "processing"):
            attempt.status = "failed"
            if payment_id and not attempt.gateway_payment_id:
                existing_pid = db.session.execute(
                    select(PaymentAttempt.id).where(PaymentAttempt.gateway_payment_id == payment_id)
                ).scalar_one_or_none()
                if existing_pid is None:
                    attempt.gateway_payment_id = payment_id
            attempt.payment_method = _normalize_gateway_method(payment_entity.get("method"))
            attempt.failure_code = str(payment_entity.get("error_code") or "payment_failed")[:60]
            attempt.failure_reason = str(
                payment_entity.get("error_description") or "Payment failed at Razorpay."
            )[:255]
            attempt.updated_at = datetime.now(UTC)
            outcome = "applied"

        db.session.add(
            PaymentEvent(
                payment_attempt_id=attempt.id if attempt else None,
                source="webhook",
                event_type=event_type,
                gateway_event_id=clean_event_id,
                signature_valid=True,
                outcome=outcome,
                payload=_sanitized_gateway_snapshot(payment_entity),
            )
        )
        db.session.commit()
        return {"status": outcome, "eventType": event_type}

    db.session.add(
        PaymentEvent(
            payment_attempt_id=None,
            source="webhook",
            event_type=event_type,
            gateway_event_id=clean_event_id,
            signature_valid=True,
            outcome="ignored",
            payload=_sanitized_gateway_snapshot(payment_entity or order_entity),
        )
    )
    db.session.commit()
    return {"status": "ignored", "eventType": event_type}
