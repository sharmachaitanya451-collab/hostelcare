"""PostgreSQL-backed Complaint Analytics, SLA Monitoring, and Staff Performance (Phase 4.2)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, select

from app.analytics.service import resolve_date_range
from app.analytics.sla import (
    PRIORITY_LABELS,
    PRIORITY_ORDER,
    get_complaint_sla_hours,
    sla_deadline_sql_expr,
)
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAssignment
from app.models.identity import StaffProfile, User

_ACTIVE_ASSIGNMENT_STATUSES = ("assigned", "accepted", "in_progress")
_COMPLETED_STATUSES = ("completed", "closed")


def _compute_category_distribution(
    start_dt: datetime, end_dt_exclusive: datetime
) -> list[dict[str, Any]]:
    """Aggregate complaint counts and percentages by category (`created_at` in period)."""
    cat_expr = func.coalesce(
        func.nullif(func.btrim(Complaint.category), ""),
        "Uncategorized",
    )
    rows = db.session.execute(
        select(cat_expr.label("category"), func.count(Complaint.id).label("cnt"))
        .where(
            Complaint.created_at >= start_dt,
            Complaint.created_at < end_dt_exclusive,
        )
        .group_by(cat_expr)
        .order_by(func.count(Complaint.id).desc(), cat_expr.asc())
    ).all()

    total = sum(int(row.cnt or 0) for row in rows)
    if total == 0:
        return []

    return [
        {
            "category": str(row.category),
            "count": int(row.cnt or 0),
            "percentage": round((int(row.cnt or 0) / total) * 100.0, 1),
        }
        for row in rows
    ]


def _choose_trend_interval(start_date: date, end_date: date) -> str:
    span_days = (end_date - start_date).days + 1
    if span_days <= 31:
        return "daily"
    if span_days <= 120:
        return "weekly"
    return "monthly"


def _generate_trend_buckets(
    start_date: date, end_date: date, interval: str
) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    if interval == "daily":
        cur = start_date
        while cur <= end_date:
            buckets.append(
                {
                    "bucket_date": cur,
                    "period": cur.isoformat(),
                    "label": cur.strftime("%d %b"),
                }
            )
            cur += timedelta(days=1)
    elif interval == "weekly":
        cur = start_date - timedelta(days=start_date.weekday())
        while cur <= end_date:
            buckets.append(
                {
                    "bucket_date": cur,
                    "period": cur.isoformat(),
                    "label": f"Wk {cur.strftime('%d %b')}",
                }
            )
            cur += timedelta(days=7)
    else:
        cur = start_date.replace(day=1)
        while cur <= end_date:
            buckets.append(
                {
                    "bucket_date": cur,
                    "period": cur.strftime("%Y-%m"),
                    "label": cur.strftime("%b %Y"),
                }
            )
            cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return buckets


def _compute_trends(
    start_date: date,
    end_date: date,
    start_dt: datetime,
    end_dt_exclusive: datetime,
) -> dict[str, Any]:
    """Compute submitted (`created_at`) and completed (`completed_at`) IST trend series."""
    interval = _choose_trend_interval(start_date, end_date)
    trunc_unit = "day" if interval == "daily" else ("week" if interval == "weekly" else "month")

    submitted_bucket = cast(
        func.date_trunc(trunc_unit, func.timezone("Asia/Kolkata", Complaint.created_at)),
        Date,
    )
    submitted_rows = db.session.execute(
        select(submitted_bucket.label("bucket"), func.count(Complaint.id).label("cnt"))
        .where(
            Complaint.created_at >= start_dt,
            Complaint.created_at < end_dt_exclusive,
        )
        .group_by(submitted_bucket)
    ).all()
    submitted_map = {row.bucket: int(row.cnt or 0) for row in submitted_rows if row.bucket}

    completed_bucket = cast(
        func.date_trunc(trunc_unit, func.timezone("Asia/Kolkata", Complaint.completed_at)),
        Date,
    )
    completed_rows = db.session.execute(
        select(completed_bucket.label("bucket"), func.count(Complaint.id).label("cnt"))
        .where(
            Complaint.completed_at.is_not(None),
            Complaint.status.in_(_COMPLETED_STATUSES),
            Complaint.completed_at >= start_dt,
            Complaint.completed_at < end_dt_exclusive,
        )
        .group_by(completed_bucket)
    ).all()
    completed_map = {row.bucket: int(row.cnt or 0) for row in completed_rows if row.bucket}

    series = [
        {
            "period": b["period"],
            "label": b["label"],
            "submitted": submitted_map.get(b["bucket_date"], 0),
            "completed": completed_map.get(b["bucket_date"], 0),
        }
        for b in _generate_trend_buckets(start_date, end_date, interval)
    ]

    return {
        "interval": interval,
        "series": series,
    }


def _compute_resolution_mttr(start_dt: datetime, end_dt_exclusive: datetime) -> dict[str, Any]:
    """Compute MTTR and median resolution duration (`completed_at - created_at`) in SQL."""
    duration_sec = func.greatest(
        0.0,
        func.extract("epoch", Complaint.completed_at - Complaint.created_at),
    )
    row = db.session.execute(
        select(
            func.count(Complaint.id).label("completed_count"),
            func.avg(duration_sec).label("avg_sec"),
            func.percentile_cont(0.5).within_group(duration_sec).label("median_sec"),
        ).where(
            Complaint.completed_at.is_not(None),
            Complaint.status.in_(_COMPLETED_STATUSES),
            Complaint.completed_at >= start_dt,
            Complaint.completed_at < end_dt_exclusive,
        )
    ).one()

    completed_count = int(row.completed_count or 0)
    if completed_count == 0 or row.avg_sec is None:
        return {
            "completedCount": 0,
            "averageSeconds": None,
            "averageHours": None,
            "medianSeconds": None,
            "medianHours": None,
        }

    avg_sec = round(float(row.avg_sec), 1)
    med_sec = round(float(row.median_sec), 1) if row.median_sec is not None else None
    return {
        "completedCount": completed_count,
        "averageSeconds": avg_sec,
        "averageHours": round(avg_sec / 3600.0, 2),
        "medianSeconds": med_sec,
        "medianHours": round(med_sec / 3600.0, 2) if med_sec is not None else None,
    }


def _compute_sla_metrics(start_dt: datetime, end_dt_exclusive: datetime) -> dict[str, Any]:
    """Compute priority-wise and overall SLA compliance and active overdue counts."""
    now_utc = datetime.now(UTC)
    hours_map = get_complaint_sla_hours()
    deadline_expr = sla_deadline_sql_expr(Complaint.created_at, Complaint.priority)

    is_completed = Complaint.status.in_(_COMPLETED_STATUSES) & Complaint.completed_at.is_not(None)
    is_active = Complaint.status.notin_((*_COMPLETED_STATUSES, "rejected"))

    rows = db.session.execute(
        select(
            Complaint.priority,
            func.count(Complaint.id).label("eligible_count"),
            func.count(Complaint.id)
            .filter(is_active & (now_utc > deadline_expr))
            .label("active_overdue"),
            func.count(Complaint.id)
            .filter(is_active & (now_utc <= deadline_expr))
            .label("active_within_sla"),
            func.count(Complaint.id)
            .filter(is_completed & (Complaint.completed_at <= deadline_expr))
            .label("completed_within_sla"),
            func.count(Complaint.id)
            .filter(is_completed & (Complaint.completed_at > deadline_expr))
            .label("completed_after_sla"),
        )
        .where(
            Complaint.created_at >= start_dt,
            Complaint.created_at < end_dt_exclusive,
            Complaint.status != "rejected",
        )
        .group_by(Complaint.priority)
    ).all()

    by_prio_map = {str(row.priority): row for row in rows}
    by_priority: list[dict[str, Any]] = []

    total_eligible = 0
    total_active_overdue = 0
    total_active_within = 0
    total_completed_within = 0
    total_completed_after = 0

    for prio in PRIORITY_ORDER:
        row = by_prio_map.get(prio)
        eligible = int(row.eligible_count or 0) if row else 0
        act_overdue = int(row.active_overdue or 0) if row else 0
        act_within = int(row.active_within_sla or 0) if row else 0
        cmp_within = int(row.completed_within_sla or 0) if row else 0
        cmp_after = int(row.completed_after_sla or 0) if row else 0

        denom = cmp_within + cmp_after
        prio_rate = round((cmp_within / denom) * 100.0, 1) if denom > 0 else None

        total_eligible += eligible
        total_active_overdue += act_overdue
        total_active_within += act_within
        total_completed_within += cmp_within
        total_completed_after += cmp_after

        by_priority.append(
            {
                "priority": prio,
                "label": PRIORITY_LABELS[prio],
                "targetHours": hours_map[prio],
                "total": eligible,
                "activeOverdue": act_overdue,
                "activeWithinSla": act_within,
                "completedWithinSla": cmp_within,
                "completedAfterSla": cmp_after,
                "complianceRate": prio_rate,
            }
        )

    overall_denom = total_completed_within + total_completed_after
    overall_rate = (
        round((total_completed_within / overall_denom) * 100.0, 1) if overall_denom > 0 else None
    )

    return {
        "targetsHours": hours_map,
        "eligibleCount": total_eligible,
        "activeOverdue": total_active_overdue,
        "activeWithinSla": total_active_within,
        "completedWithinSla": total_completed_within,
        "completedAfterSla": total_completed_after,
        "complianceRate": overall_rate,
        "byPriority": by_priority,
    }


def _workload_indicator(active_count: int) -> str:
    if active_count <= 0:
        return "Available"
    if active_count <= 2:
        return "Normal"
    if active_count <= 4:
        return "Busy"
    return "Heavy"


def _compute_staff_analytics(
    start_dt: datetime, end_dt_exclusive: datetime
) -> list[dict[str, Any]]:
    """Compute active workload, completed task attribution, and turnaround durations per staff."""
    staff_rows = db.session.execute(
        select(
            User.id,
            User.public_id,
            User.full_name,
            StaffProfile.staff_code,
            StaffProfile.trade,
        )
        .join(StaffProfile, StaffProfile.user_id == User.id)
        .where(User.role == "staff", User.status == "active")
        .order_by(User.full_name.asc(), StaffProfile.staff_code.asc())
    ).all()

    if not staff_rows:
        return []

    # 1. Current active workload (open assignment + non-terminal active complaint status)
    active_rows = db.session.execute(
        select(
            ComplaintAssignment.staff_user_id,
            func.count(ComplaintAssignment.id).label("active_total"),
            func.count(ComplaintAssignment.id)
            .filter(Complaint.status == "assigned")
            .label("assigned_cnt"),
            func.count(ComplaintAssignment.id)
            .filter(Complaint.status == "accepted")
            .label("accepted_cnt"),
            func.count(ComplaintAssignment.id)
            .filter(Complaint.status == "in_progress")
            .label("in_progress_cnt"),
        )
        .join(Complaint, Complaint.id == ComplaintAssignment.complaint_id)
        .where(
            ComplaintAssignment.ended_at.is_(None),
            Complaint.status.in_(_ACTIVE_ASSIGNMENT_STATUSES),
        )
        .group_by(ComplaintAssignment.staff_user_id)
    ).all()
    active_map = {row.staff_user_id: row for row in active_rows}

    # 2. Completed task attribution & assignment-to-completion duration in period
    completion_dur = func.greatest(
        0.0,
        func.extract("epoch", Complaint.completed_at - ComplaintAssignment.assigned_at),
    )
    completed_rows = db.session.execute(
        select(
            ComplaintAssignment.staff_user_id,
            func.count(ComplaintAssignment.id).label("completed_cnt"),
            func.avg(completion_dur).label("avg_comp_sec"),
        )
        .join(Complaint, Complaint.id == ComplaintAssignment.complaint_id)
        .where(
            ComplaintAssignment.ended_at.is_(None),
            Complaint.status.in_(_COMPLETED_STATUSES),
            Complaint.completed_at.is_not(None),
            Complaint.completed_at >= start_dt,
            Complaint.completed_at < end_dt_exclusive,
        )
        .group_by(ComplaintAssignment.staff_user_id)
    ).all()
    completed_map = {row.staff_user_id: row for row in completed_rows}

    # 3. Assignment-to-acceptance duration for assignments issued within period
    accept_dur = func.greatest(
        0.0,
        func.extract("epoch", ComplaintAssignment.accepted_at - ComplaintAssignment.assigned_at),
    )
    acceptance_rows = db.session.execute(
        select(
            ComplaintAssignment.staff_user_id,
            func.avg(accept_dur).label("avg_acc_sec"),
        )
        .where(
            ComplaintAssignment.assigned_at >= start_dt,
            ComplaintAssignment.assigned_at < end_dt_exclusive,
            ComplaintAssignment.accepted_at.is_not(None),
        )
        .group_by(ComplaintAssignment.staff_user_id)
    ).all()
    acceptance_map = {row.staff_user_id: row for row in acceptance_rows}

    results: list[dict[str, Any]] = []
    for stf in staff_rows:
        act = active_map.get(stf.id)
        cmp_row = completed_map.get(stf.id)
        acc_row = acceptance_map.get(stf.id)

        active_total = int(act.active_total or 0) if act else 0
        assigned_cnt = int(act.assigned_cnt or 0) if act else 0
        accepted_cnt = int(act.accepted_cnt or 0) if act else 0
        in_progress_cnt = int(act.in_progress_cnt or 0) if act else 0

        completed_cnt = int(cmp_row.completed_cnt or 0) if cmp_row else 0
        avg_comp_sec = (
            round(float(cmp_row.avg_comp_sec), 1)
            if cmp_row and cmp_row.avg_comp_sec is not None
            else None
        )
        avg_acc_sec = (
            round(float(acc_row.avg_acc_sec), 1)
            if acc_row and acc_row.avg_acc_sec is not None
            else None
        )

        results.append(
            {
                "staffId": str(stf.public_id),
                "staffCode": stf.staff_code,
                "name": stf.full_name,
                "trade": stf.trade,
                "activeAssigned": active_total,
                "assignedTasks": assigned_cnt,
                "acceptedTasks": accepted_cnt,
                "inProgressTasks": in_progress_cnt,
                "completedCount": completed_cnt,
                "avgCompletionSeconds": avg_comp_sec,
                "avgCompletionHours": round(avg_comp_sec / 3600.0, 2)
                if avg_comp_sec is not None
                else None,
                "avgAcceptanceSeconds": avg_acc_sec,
                "avgAcceptanceHours": round(avg_acc_sec / 3600.0, 2)
                if avg_acc_sec is not None
                else None,
                "workloadIndicator": _workload_indicator(active_total),
            }
        )
    return results


def get_complaint_analytics(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return PostgreSQL-aggregated complaint, SLA, MTTR, trend, and staff analytics."""
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
        "categories": _compute_category_distribution(start_dt, end_dt_exclusive),
        "trends": _compute_trends(start_date, end_date, start_dt, end_dt_exclusive),
        "resolution": _compute_resolution_mttr(start_dt, end_dt_exclusive),
        "sla": _compute_sla_metrics(start_dt, end_dt_exclusive),
        "staff": _compute_staff_analytics(start_dt, end_dt_exclusive),
        "semantics": {
            "categories": "Filtered by complaint created_at within the selected IST date range.",
            "trendsSubmitted": "Submitted counts grouped by complaint created_at in IST.",
            "trendsCompleted": "Completed counts grouped by complaint completed_at in IST.",
            "resolution": (
                "Mean and median (completed_at - created_at) for non-rejected complaints "
                "completed in the IST period; measures time to completion, not closure."
            ),
            "sla": (
                "Compliance % = completedWithinSla / (completedWithinSla + completedAfterSla)"
                " * 100 for non-rejected complaints created in period; active overdue uses "
                "current time against priority deadlines (High=24h, Medium=72h, Low=168h)."
            ),
            "staff": (
                "Active workload reflects live open assignments (ended_at IS NULL, status in "
                "assigned/accepted/in_progress). Completed attribution credits the active "
                "non-ended assignment on complaints completed in period; prior pre-reassignment "
                "technicians are not credited with final completion."
            ),
        },
    }
