"""Database-backed KPI aggregations for the Admin Dashboard (Phase 4.1)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.auth.service import AuthServiceError
from app.complaints.serializers import (
    PRIORITY_LABELS,
    STATUS_LABELS,
    get_open_assignment,
)
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAssignment
from app.models.fines import Fine, FineDispute
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.payments import Payment
from app.models.rooms import Block, Room, RoomAllocation

_IST = ZoneInfo("Asia/Kolkata")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_PRESETS = frozenset({"7d", "30d", "this_month", "custom"})
_MAX_WINDOW_DAYS = 365
_RECENT_ACTIVITY_LIMIT = 5

_ALL_COMPLAINT_STATUSES = (
    "submitted",
    "under_review",
    "assigned",
    "accepted",
    "in_progress",
    "completed",
    "closed",
    "rejected",
)
_TERMINAL_COMPLAINT_STATUSES = ("completed", "closed", "rejected")


class AnalyticsServiceError(AuthServiceError):
    """Domain error for analytics validation and query failures."""


def _today_ist() -> date:
    return datetime.now(_IST).date()


def _parse_strict_iso_date(raw: Any, field_name: str) -> date:
    if not isinstance(raw, str) or not raw.strip():
        raise AnalyticsServiceError(
            "validation_error",
            f"{field_name} is required in YYYY-MM-DD format.",
            400,
        )
    text_val = raw.strip()
    if not _ISO_DATE_RE.match(text_val):
        raise AnalyticsServiceError(
            "validation_error",
            f"Invalid {field_name} '{text_val}'. Expected ISO 8601 format YYYY-MM-DD.",
            400,
        )
    try:
        return date.fromisoformat(text_val)
    except ValueError as exc:
        raise AnalyticsServiceError(
            "validation_error",
            f"Invalid {field_name} '{text_val}'. Calendar date does not exist.",
            400,
        ) from exc


def resolve_date_range(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and resolve reporting date range into IST date and datetime bounds."""
    query = params or {}
    raw_preset = str(query.get("preset") or "").strip().lower()
    raw_from = str(query.get("date_from") or "").strip()
    raw_to = str(query.get("date_to") or "").strip()

    if raw_preset and raw_preset not in _VALID_PRESETS:
        raise AnalyticsServiceError(
            "validation_error",
            f"Invalid preset '{raw_preset}'. Allowed values: 7d, 30d, this_month, custom.",
            400,
        )

    today = _today_ist()
    use_custom = raw_preset == "custom" or (not raw_preset and (bool(raw_from) or bool(raw_to)))

    if use_custom:
        if not raw_from or not raw_to:
            raise AnalyticsServiceError(
                "validation_error",
                "Both date_from and date_to are required for a custom date range.",
                400,
            )
        start_date = _parse_strict_iso_date(raw_from, "date_from")
        end_date = _parse_strict_iso_date(raw_to, "date_to")
        if start_date > end_date:
            raise AnalyticsServiceError(
                "validation_error",
                "Invalid date range: date_from cannot be after date_to.",
                400,
            )
        span_days = (end_date - start_date).days + 1
        if span_days > _MAX_WINDOW_DAYS:
            raise AnalyticsServiceError(
                "validation_error",
                f"Custom date range cannot exceed {_MAX_WINDOW_DAYS} days.",
                400,
            )
        effective_preset = "custom"
    else:
        effective_preset = raw_preset or "30d"
        end_date = today
        if effective_preset == "7d":
            start_date = end_date - timedelta(days=6)
        elif effective_preset == "this_month":
            start_date = end_date.replace(day=1)
        else:
            start_date = end_date - timedelta(days=29)

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=_IST)
    end_dt_exclusive = datetime.combine(
        end_date + timedelta(days=1), datetime.min.time(), tzinfo=_IST
    )

    return {
        "preset": effective_preset,
        "date_from": start_date,
        "date_to": end_date,
        "start_dt": start_dt,
        "end_dt_exclusive": end_dt_exclusive,
    }


def _quantize_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _compute_complaint_kpis(start_dt: datetime, end_dt_exclusive: datetime) -> dict[str, Any]:
    """Compute mutually exclusive complaint status counts and active unassigned count."""
    status_rows = db.session.execute(
        select(Complaint.status, func.count(Complaint.id))
        .where(
            Complaint.created_at >= start_dt,
            Complaint.created_at < end_dt_exclusive,
        )
        .group_by(Complaint.status)
    ).all()

    by_status = dict.fromkeys(_ALL_COMPLAINT_STATUSES, 0)
    for status_key, count_val in status_rows:
        if status_key in by_status:
            by_status[status_key] = int(count_val or 0)

    open_assign_exists = (
        select(ComplaintAssignment.id)
        .where(
            ComplaintAssignment.complaint_id == Complaint.id,
            ComplaintAssignment.ended_at.is_(None),
        )
        .exists()
    )
    unassigned_count = int(
        db.session.execute(
            select(func.count(Complaint.id)).where(
                Complaint.created_at >= start_dt,
                Complaint.created_at < end_dt_exclusive,
                Complaint.status.notin_(_TERMINAL_COMPLAINT_STATUSES),
                ~open_assign_exists,
            )
        ).scalar_one()
        or 0
    )

    total = sum(by_status.values())
    resolved = by_status["completed"] + by_status["closed"]

    return {
        "total": total,
        "newSubmissions": by_status["submitted"],
        "underReview": by_status["under_review"],
        "assigned": by_status["assigned"],
        "accepted": by_status["accepted"],
        "inProgress": by_status["in_progress"],
        "completed": by_status["completed"],
        "closed": by_status["closed"],
        "rejected": by_status["rejected"],
        "unassigned": unassigned_count,
        "resolved": resolved,
        "byStatus": by_status,
    }


def _compute_approval_kpis() -> dict[str, int]:
    """Compute live student registration status counts."""
    rows = db.session.execute(
        select(User.status, func.count(User.id))
        .where(User.role == "student")
        .group_by(User.status)
    ).all()

    counts = {str(status_key): int(count_val or 0) for status_key, count_val in rows}
    pending_count = counts.get("pending", 0)
    approved_count = counts.get("active", 0)
    rejected_count = counts.get("rejected", 0)
    total_students = sum(counts.values())

    return {
        "pendingCount": pending_count,
        "approvedCount": approved_count,
        "rejectedCount": rejected_count,
        "totalStudents": total_students,
    }


def _compute_occupancy_kpis(reference_date: date) -> dict[str, Any]:
    """Compute hostel-wide and block-level active bed occupancy as of `reference_date`."""
    blocks = list(
        db.session.execute(
            select(Block)
            .where(Block.is_active.is_(True))
            .order_by(Block.display_order.asc(), Block.code.asc(), Block.name.asc())
        )
        .scalars()
        .all()
    )

    if not blocks:
        return {
            "referenceDate": reference_date.isoformat(),
            "totalCapacity": 0,
            "occupiedBeds": 0,
            "vacantBeds": 0,
            "occupancyRate": 0.0,
            "activeRoomsCount": 0,
            "blocks": [],
        }

    room_rows = db.session.execute(
        select(
            Room.block_id,
            func.count(Room.id).label("active_rooms_count"),
            func.coalesce(func.sum(Room.capacity), 0).label("total_capacity"),
        )
        .join(Block, Room.block_id == Block.id)
        .where(Block.is_active.is_(True), Room.is_active.is_(True))
        .group_by(Room.block_id)
    ).all()
    room_stats = {
        row.block_id: {
            "activeRoomsCount": int(row.active_rooms_count or 0),
            "totalCapacity": int(row.total_capacity or 0),
        }
        for row in room_rows
    }

    alloc_rows = db.session.execute(
        select(Room.block_id, func.count(RoomAllocation.id).label("occupied_beds"))
        .join(Room, RoomAllocation.room_id == Room.id)
        .join(Block, Room.block_id == Block.id)
        .where(
            Block.is_active.is_(True),
            Room.is_active.is_(True),
            RoomAllocation.start_date <= reference_date,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > reference_date),
        )
        .group_by(Room.block_id)
    ).all()
    occupied_by_block = {row.block_id: int(row.occupied_beds or 0) for row in alloc_rows}

    total_capacity = 0
    total_occupied = 0
    total_active_rooms = 0
    block_breakdown: list[dict[str, Any]] = []

    for blk in blocks:
        blk_rooms = room_stats.get(blk.id, {"activeRoomsCount": 0, "totalCapacity": 0})
        cap = blk_rooms["totalCapacity"]
        active_rooms = blk_rooms["activeRoomsCount"]
        occ = occupied_by_block.get(blk.id, 0)
        vacant = max(0, cap - occ)
        rate = round((occ / cap) * 100.0, 1) if cap > 0 else 0.0

        total_capacity += cap
        total_occupied += occ
        total_active_rooms += active_rooms

        block_breakdown.append(
            {
                "blockId": blk.id,
                "code": blk.code,
                "name": blk.name,
                "activeRoomsCount": active_rooms,
                "totalCapacity": cap,
                "occupiedBeds": occ,
                "vacantBeds": vacant,
                "occupancyRate": rate,
            }
        )

    total_vacant = max(0, total_capacity - total_occupied)
    overall_rate = (
        round((total_occupied / total_capacity) * 100.0, 1) if total_capacity > 0 else 0.0
    )

    return {
        "referenceDate": reference_date.isoformat(),
        "totalCapacity": total_capacity,
        "occupiedBeds": total_occupied,
        "vacantBeds": total_vacant,
        "occupancyRate": overall_rate,
        "activeRoomsCount": total_active_rooms,
        "blocks": block_breakdown,
    }


def _compute_resident_kpis(reference_date: date) -> dict[str, int]:
    """Count distinct active student accounts holding an active allocation on `reference_date`."""
    active_count = int(
        db.session.execute(
            select(func.count(func.distinct(RoomAllocation.student_user_id)))
            .join(StudentProfile, RoomAllocation.student_user_id == StudentProfile.user_id)
            .join(User, StudentProfile.user_id == User.id)
            .join(Room, RoomAllocation.room_id == Room.id)
            .join(Block, Room.block_id == Block.id)
            .where(
                User.role == "student",
                User.status == "active",
                Block.is_active.is_(True),
                Room.is_active.is_(True),
                RoomAllocation.start_date <= reference_date,
                (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > reference_date),
            )
        ).scalar_one()
        or 0
    )
    return {"activeCount": active_count}


def _compute_financial_kpis(
    start_date: date,
    end_date: date,
    start_dt: datetime,
    end_dt_exclusive: datetime,
) -> dict[str, Any]:
    """Compute fine issuance, verified payment collections, resolutions, and disputes."""
    levied_row = db.session.execute(
        select(
            func.coalesce(func.sum(Fine.amount_inr), 0),
            func.count(Fine.id),
        ).where(
            Fine.issue_date >= start_date,
            Fine.issue_date <= end_date,
        )
    ).one()
    levied_dec = _quantize_money(levied_row[0])
    levied_count = int(levied_row[1] or 0)

    # Query verified Payment records directly (1-to-1 with paid fines via uq_payments_fine)
    collected_row = db.session.execute(
        select(
            func.coalesce(func.sum(Payment.amount_inr), 0),
            func.count(Payment.id),
        )
        .join(Fine, Payment.fine_id == Fine.id)
        .where(
            Fine.status == "paid",
            Payment.verified_at >= start_dt,
            Payment.verified_at < end_dt_exclusive,
        )
    ).one()
    collected_dec = _quantize_money(collected_row[0])
    collected_count = int(collected_row[1] or 0)

    resolved_rows = db.session.execute(
        select(
            Fine.status,
            func.coalesce(func.sum(Fine.amount_inr), 0),
            func.count(Fine.id),
        )
        .where(
            Fine.status.in_(("waived", "cancelled")),
            Fine.resolved_at.is_not(None),
            Fine.resolved_at >= start_dt,
            Fine.resolved_at < end_dt_exclusive,
        )
        .group_by(Fine.status)
    ).all()

    waived_dec = Decimal("0.00")
    waived_count = 0
    cancelled_dec = Decimal("0.00")
    cancelled_count = 0
    for status_key, amount_sum, count_val in resolved_rows:
        if status_key == "waived":
            waived_dec = _quantize_money(amount_sum)
            waived_count = int(count_val or 0)
        elif status_key == "cancelled":
            cancelled_dec = _quantize_money(amount_sum)
            cancelled_count = int(count_val or 0)

    outstanding_row = db.session.execute(
        select(
            func.coalesce(func.sum(Fine.amount_inr), 0),
            func.count(Fine.id),
        ).where(Fine.status.in_(("pending", "disputed")))
    ).one()
    outstanding_dec = _quantize_money(outstanding_row[0])
    outstanding_count = int(outstanding_row[1] or 0)

    pending_disputes_count = int(
        db.session.execute(
            select(func.count(FineDispute.id)).where(FineDispute.status == "open")
        ).scalar_one()
        or 0
    )

    return {
        "leviedAmount": float(levied_dec),
        "leviedAmountInr": f"{levied_dec:.2f}",
        "leviedCount": levied_count,
        "collectedAmount": float(collected_dec),
        "collectedAmountInr": f"{collected_dec:.2f}",
        "collectedCount": collected_count,
        "outstandingAmount": float(outstanding_dec),
        "outstandingAmountInr": f"{outstanding_dec:.2f}",
        "outstandingCount": outstanding_count,
        "waivedAmount": float(waived_dec),
        "waivedAmountInr": f"{waived_dec:.2f}",
        "waivedCount": waived_count,
        "cancelledAmount": float(cancelled_dec),
        "cancelledAmountInr": f"{cancelled_dec:.2f}",
        "cancelledCount": cancelled_count,
        "pendingDisputesCount": pending_disputes_count,
    }


def _fetch_recent_complaints(
    start_dt: datetime,
    end_dt_exclusive: datetime,
    limit: int = _RECENT_ACTIVITY_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch recent complaint summaries without exposing student PII or internal notes."""
    stmt = (
        select(Complaint)
        .options(
            selectinload(Complaint.room).selectinload(Room.block),
            selectinload(Complaint.block),
            selectinload(Complaint.assignments)
            .selectinload(ComplaintAssignment.staff)
            .selectinload(StaffProfile.user),
        )
        .where(
            Complaint.created_at >= start_dt,
            Complaint.created_at < end_dt_exclusive,
        )
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .limit(limit)
    )
    rows = list(db.session.execute(stmt).scalars().all())

    items: list[dict[str, Any]] = []
    for c in rows:
        if c.location_type == "room" and c.room is not None:
            room_label = c.room.room_number
            block_name = c.room.block.name if c.room.block else "Hostel"
        else:
            detail = c.location_detail or "Common Area"
            room_label = f"Common Area ({detail})"
            block_name = c.block.name if c.block else "Campus Common Area"

        open_assign = get_open_assignment(c)
        assigned_staff_name = None
        if open_assign is not None and open_assign.staff is not None:
            stf_user = open_assign.staff.user
            assigned_staff_name = stf_user.full_name if stf_user is not None else "Duty Staff"

        items.append(
            {
                "id": c.reference_no,
                "referenceNo": c.reference_no,
                "room": room_label,
                "block": block_name,
                "category": c.category or "General",
                "title": c.title,
                "assignedStaff": assigned_staff_name,
                "priority": PRIORITY_LABELS.get(c.priority, c.priority),
                "rawPriority": c.priority,
                "status": STATUS_LABELS.get(c.status, c.status),
                "rawStatus": c.status,
                "createdAt": c.created_at.isoformat() if c.created_at else None,
            }
        )
    return items


def get_admin_overview_analytics(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return authoritative PostgreSQL-backed KPI metrics for the Admin Overview Dashboard."""
    dr = resolve_date_range(params)
    start_date: date = dr["date_from"]
    end_date: date = dr["date_to"]
    start_dt: datetime = dr["start_dt"]
    end_dt_exclusive: datetime = dr["end_dt_exclusive"]

    return {
        "dateRange": {
            "preset": dr["preset"],
            "dateFrom": start_date.isoformat(),
            "dateTo": end_date.isoformat(),
            "timezone": "Asia/Kolkata",
        },
        "complaints": _compute_complaint_kpis(start_dt, end_dt_exclusive),
        "approvals": _compute_approval_kpis(),
        "occupancy": _compute_occupancy_kpis(end_date),
        "residents": _compute_resident_kpis(end_date),
        "finances": _compute_financial_kpis(start_date, end_date, start_dt, end_dt_exclusive),
        "recentActivity": _fetch_recent_complaints(start_dt, end_dt_exclusive),
        "semantics": {
            "complaints": "Filtered by complaint created_at within the selected IST date range.",
            "financesLevied": "Filtered by fine issue_date within the selected date range.",
            "financesCollected": (
                "Verified payments only, filtered by payment verified_at within the IST range."
            ),
            "financesWaivedAndCancelled": (
                "Filtered by fine resolved_at within the selected IST date range."
            ),
            "financesOutstanding": (
                "Live unpaid balance (pending + disputed fines) as of current ledger state."
            ),
            "approvals": "Live student registration queue counts (not filtered by date range).",
            "occupancy": (
                "Active bed allocations overlapping dateTo against current active room capacity."
            ),
            "residents": (
                "Distinct active student accounts with an active room allocation in an active "
                "room and block overlapping dateTo."
            ),
        },
    }
