"""Append-only security and administrative audit logging service."""

from __future__ import annotations

import ipaddress
from typing import Any

from flask import g, has_request_context, request

from app.extensions import db
from app.models.audit import AuditLog
from app.models.identity import User

_FORBIDDEN_METADATA_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "hash",
    "credential",
    "cookie",
    "csrf",
)


def get_client_ip() -> str | None:
    """Return a valid IPv4/IPv6 client address for PostgreSQL `INET` storage, or None."""
    if not has_request_context():
        return None
    raw_ip = request.remote_addr
    if not raw_ip:
        return None
    try:
        return str(ipaddress.ip_address(raw_ip.strip()))
    except ValueError:
        return None


def get_request_id() -> str | None:
    """Return the current request ID if inside a Flask request context."""
    if not has_request_context():
        return None
    req_id = getattr(g, "request_id", None)
    return str(req_id)[:64] if req_id else None


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Strip any sensitive keys from audit metadata so secrets/hashes/tokens are never stored."""
    if not metadata or not isinstance(metadata, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, val in metadata.items():
        key_str = str(key)
        key_lower = key_str.lower()
        if any(forbidden in key_lower for forbidden in _FORBIDDEN_METADATA_SUBSTRINGS):
            continue
        if isinstance(val, dict):
            clean[key_str] = sanitize_audit_metadata(val)
        else:
            clean[key_str] = val
    return clean


def record_audit_event(
    *,
    action: str,
    actor: User | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    commit_immediately: bool = False,
) -> AuditLog:
    """Append an `AuditLog` record.

    Derives the actor from `g.current_user` when not explicitly provided.
    Never stores passwords, reset tokens, hashes, or session secrets in `metadata`.
    """
    resolved_actor = actor
    if resolved_actor is None and actor_user_id is None and has_request_context():
        resolved_actor = getattr(g, "current_user", None)

    final_actor_id = resolved_actor.id if resolved_actor is not None else actor_user_id
    final_actor_role = resolved_actor.role if resolved_actor is not None else actor_role

    if (target_type is None) != (target_id is None):
        raise ValueError("target_type and target_id must both be provided or both be None")

    entry = AuditLog(
        actor_user_id=final_actor_id,
        actor_role=final_actor_role,
        action=action.strip(),
        target_type=target_type,
        target_id=str(target_id)[:40] if target_id is not None else None,
        metadata_json=sanitize_audit_metadata(metadata),
        request_id=get_request_id(),
        ip_address=ip_address if ip_address is not None else get_client_ip(),
    )
    db.session.add(entry)
    if commit_immediately:
        db.session.commit()
    return entry
