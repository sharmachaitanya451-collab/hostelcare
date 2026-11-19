"""Razorpay Test Mode HTTP client and HMAC SHA-256 signature verification utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from typing import Any

from flask import current_app

from app.fines.service import FineServiceError


def _validate_test_mode_only(mode: str, key_id: str) -> None:
    """Reject non-test Razorpay configurations to guarantee Test Mode only operation."""
    clean_mode = str(mode or "test").strip().lower()
    if clean_mode != "test":
        raise FineServiceError(
            "live_mode_forbidden",
            "Live payment mode is disabled. Only Razorpay Test Mode is supported.",
            403,
        )
    if str(key_id or "").strip().startswith("rzp_live_"):
        raise FineServiceError(
            "live_mode_forbidden",
            "Live Razorpay API keys are forbidden. Configure a rzp_test_ key.",
            403,
        )


def is_razorpay_configured() -> bool:
    """Return True when Razorpay Test Mode credentials are present and valid."""
    mode = str(current_app.config.get("RAZORPAY_MODE", "test")).strip().lower()
    key_id = str(current_app.config.get("RAZORPAY_KEY_ID", "")).strip()
    key_secret = str(current_app.config.get("RAZORPAY_KEY_SECRET", "")).strip()
    if mode != "test" or key_id.startswith("rzp_live_"):
        return False
    return bool(key_id and key_secret)


def get_razorpay_test_credentials() -> tuple[str, str, str, int]:
    """Return validated `(key_id, key_secret, api_base, timeout)` in Test Mode only."""
    mode = str(current_app.config.get("RAZORPAY_MODE", "test")).strip().lower()
    key_id = str(current_app.config.get("RAZORPAY_KEY_ID", "")).strip()
    key_secret = str(current_app.config.get("RAZORPAY_KEY_SECRET", "")).strip()
    _validate_test_mode_only(mode, key_id)

    if not key_id or not key_secret:
        raise FineServiceError(
            "online_payment_unavailable",
            "Online payments are not currently configured. Please contact the Warden office.",
            503,
        )

    api_base = str(
        current_app.config.get("RAZORPAY_API_BASE_URL", "https://api.razorpay.com/v1")
    ).rstrip("/")
    timeout = max(3, int(current_app.config.get("RAZORPAY_TIMEOUT_SECONDS", 15)))
    return key_id, key_secret, api_base, timeout


def get_razorpay_webhook_secret() -> str:
    """Return validated webhook secret while enforcing Razorpay Test Mode."""
    mode = str(current_app.config.get("RAZORPAY_MODE", "test")).strip().lower()
    key_id = str(current_app.config.get("RAZORPAY_KEY_ID", "")).strip()
    _validate_test_mode_only(mode, key_id)

    secret = str(current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")).strip()
    if not secret:
        raise FineServiceError(
            "webhook_not_configured",
            "Razorpay webhook verification secret is not configured.",
            503,
        )
    return secret


def _razorpay_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key_id, key_secret, api_base, timeout = get_razorpay_test_credentials()
    auth_token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_token}",
        "Accept": "application/json",
    }
    body_bytes: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(  # noqa: S310
        url=f"{api_base}{path}",
        data=body_bytes,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise FineServiceError(
                    "gateway_error",
                    "Unexpected response format from payment gateway.",
                    502,
                )
            return parsed
    except urllib.error.HTTPError as exc:
        err_msg = "Payment gateway request failed."
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            err_obj = err_body.get("error") if isinstance(err_body, dict) else None
            if isinstance(err_obj, dict) and err_obj.get("description"):
                err_msg = str(err_obj["description"])
        except Exception:  # noqa: S110
            pass
        raise FineServiceError("gateway_error", err_msg, 502) from exc
    except urllib.error.URLError as exc:
        raise FineServiceError(
            "gateway_unreachable",
            "Unable to reach Razorpay payment gateway. Please try again shortly.",
            502,
        ) from exc
    except TimeoutError as exc:
        raise FineServiceError(
            "gateway_timeout",
            "Razorpay payment gateway timed out. Please try again shortly.",
            504,
        ) from exc


def create_razorpay_order(
    *,
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: dict[str, str],
) -> dict[str, Any]:
    """Create a Razorpay order via `/v1/orders`."""
    return _razorpay_request(
        "POST",
        "/orders",
        payload={
            "amount": int(amount_paise),
            "currency": currency,
            "receipt": receipt,
            "notes": notes,
        },
    )


def fetch_razorpay_payment(payment_id: str) -> dict[str, Any]:
    """Fetch authoritative payment state from Razorpay `/v1/payments/{id}`."""
    clean_id = str(payment_id or "").strip()
    if not clean_id:
        raise FineServiceError("validation_error", "Razorpay payment ID is required.", 400)
    return _razorpay_request("GET", f"/payments/{clean_id}")


def fetch_razorpay_order_payments(order_id: str) -> list[dict[str, Any]]:
    """Fetch payments associated with a Razorpay order `/v1/orders/{id}/payments`."""
    clean_id = str(order_id or "").strip()
    if not clean_id:
        raise FineServiceError("validation_error", "Razorpay order ID is required.", 400)
    data = _razorpay_request("GET", f"/orders/{clean_id}/payments")
    items = data.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def verify_checkout_signature(
    *,
    order_id: str,
    payment_id: str,
    signature: str,
    key_secret: str,
) -> bool:
    """Verify Razorpay Checkout callback HMAC SHA-256 signature (`order_id|payment_id`)."""
    if not order_id or not payment_id or not signature or not key_secret:
        return False
    message = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature).strip())


def verify_webhook_signature(
    *,
    raw_body: bytes,
    signature: str | None,
    webhook_secret: str,
) -> bool:
    """Verify Razorpay webhook HMAC SHA-256 signature over raw request payload bytes."""
    if not raw_body or not signature or not webhook_secret:
        return False
    expected = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature).strip())
