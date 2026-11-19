"""Centralized SLA target policy and SQL deadline helpers for complaint analytics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import case

DEFAULT_COMPLAINT_SLA_HOURS: dict[str, int] = {
    "high": 24,
    "medium": 72,
    "low": 168,
}

PRIORITY_ORDER: tuple[str, ...] = ("high", "medium", "low")
PRIORITY_LABELS: dict[str, str] = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def get_complaint_sla_hours() -> dict[str, int]:
    """Return configured SLA resolution target hours keyed by lowercase priority."""
    configured = current_app.config.get("COMPLAINT_SLA_HOURS") if current_app else None
    if isinstance(configured, dict):
        return {
            key: int(configured.get(key, default_hrs))
            for key, default_hrs in DEFAULT_COMPLAINT_SLA_HOURS.items()
        }
    return dict(DEFAULT_COMPLAINT_SLA_HOURS)


def compute_sla_deadline(created_at: datetime, priority: str) -> datetime:
    """Return timezone-aware SLA deadline timestamp for a complaint."""
    hours_map = get_complaint_sla_hours()
    norm_priority = str(priority or "medium").strip().lower()
    hours = hours_map.get(norm_priority, hours_map["medium"])
    return created_at + timedelta(hours=hours)


def sla_deadline_sql_expr(created_at_col: Any, priority_col: Any) -> Any:
    """Build parameterized SQLAlchemy expression computing `created_at + priority_sla_interval`."""
    hours_map = get_complaint_sla_hours()
    return case(
        (priority_col == "high", created_at_col + timedelta(hours=hours_map["high"])),
        (priority_col == "medium", created_at_col + timedelta(hours=hours_map["medium"])),
        else_=created_at_col + timedelta(hours=hours_map["low"]),
    )
