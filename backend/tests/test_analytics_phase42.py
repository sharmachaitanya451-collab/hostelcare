"""Phase 4.2 Complaint Analytics, SLA Monitoring & Staff Performance PostgreSQL Tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.auth.security import hash_password
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAssignment
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.rooms import Block, Room

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")
_IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(scope="module")
def analytics42_app():
    """Create testing Flask app and ensure `hostelcare_test` is migrated to head."""
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture(autouse=True)
def _clean_analytics42_tables(analytics42_app):
    """Truncate tables between tests using `hostelcare_owner`."""
    owner_engine = create_engine(
        analytics42_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True
    )
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
                "public.payment_events, "
                "public.payments, "
                "public.payment_attempts, "
                "public.fine_history, "
                "public.fine_disputes, "
                "public.fines, "
                "public.complaint_attachments, "
                "public.complaint_history, "
                "public.complaint_internal_notes, "
                "public.complaint_updates, "
                "public.complaint_assignments, "
                "public.complaints, "
                "public.room_allocations, "
                "public.rooms, "
                "public.blocks, "
                "public.password_reset_tokens, "
                "public.staff_profiles, "
                "public.student_profiles, "
                "public.users "
                "RESTART IDENTITY CASCADE;"
            )
        )


def _login(client, identifier: str, password: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()


def _seed_actors_and_room(app) -> dict[str, int]:
    with app.app_context():
        admin = User(
            email="warden.p42@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        staff1 = User(
            email="tech1.p42@hostelcare.test",
            full_name="Ramesh Kumar",
            phone="9876543210",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        staff2 = User(
            email="tech2.p42@hostelcare.test",
            full_name="Suresh Nair",
            phone="9876543211",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        stu = User(
            email="stu1.p42@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        db.session.add_all([admin, staff1, staff2, stu])
        db.session.flush()

        db.session.add_all(
            [
                StaffProfile(
                    user_id=staff1.id, role="staff", staff_code="STF-4201", trade="Electrical"
                ),
                StaffProfile(
                    user_id=staff2.id, role="staff", staff_code="STF-4202", trade="Plumbing"
                ),
                StudentProfile(user_id=stu.id, role="student", roll_number="2026CSB4201"),
            ]
        )

        blk = Block(code="A", name="Block A", display_order=1, is_active=True)
        db.session.add(blk)
        db.session.flush()
        rm = Room(block_id=blk.id, room_number="A-101", floor=1, capacity=2, is_active=True)
        db.session.add(rm)
        db.session.commit()
        return {
            "admin_id": admin.id,
            "staff1_id": staff1.id,
            "staff2_id": staff2.id,
            "stu_id": stu.id,
            "room_id": rm.id,
        }


def test_complaint_analytics_rbac_and_no_pii(analytics42_app):
    _seed_actors_and_room(analytics42_app)

    unauth = analytics42_app.test_client()
    assert unauth.get("/api/v1/admin/analytics/complaints").status_code == 401

    stu_client = analytics42_app.test_client()
    _login(stu_client, "stu1.p42@hostelcare.test", "StudentPass123!")
    assert stu_client.get("/api/v1/admin/analytics/complaints").status_code == 403

    staff_client = analytics42_app.test_client()
    _login(staff_client, "tech1.p42@hostelcare.test", "StaffPass123!")
    assert staff_client.get("/api/v1/admin/analytics/complaints").status_code == 403

    admin_client = analytics42_app.test_client()
    _login(admin_client, "warden.p42@hostelcare.test", "AdminPass123!")
    resp = admin_client.get("/api/v1/admin/analytics/complaints?preset=7d")
    assert resp.status_code == 200
    payload = resp.get_json()
    text_dump = str(payload)
    assert "9876543210" not in text_dump
    assert "tech1.p42@hostelcare.test" not in text_dump
    assert "Aarav Sharma" not in text_dump
    assert "password" not in text_dump.lower()


def test_complaint_analytics_empty_data_and_zero_denominators(analytics42_app):
    _seed_actors_and_room(analytics42_app)
    client = analytics42_app.test_client()
    _login(client, "warden.p42@hostelcare.test", "AdminPass123!")

    resp = client.get("/api/v1/admin/analytics/complaints?preset=7d")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["categories"] == []
    assert data["trends"]["interval"] == "daily"
    assert len(data["trends"]["series"]) == 7
    assert all(pt["submitted"] == 0 and pt["completed"] == 0 for pt in data["trends"]["series"])

    assert data["resolution"]["completedCount"] == 0
    assert data["resolution"]["averageSeconds"] is None
    assert data["resolution"]["averageHours"] is None
    assert data["resolution"]["medianSeconds"] is None

    assert data["sla"]["eligibleCount"] == 0
    assert data["sla"]["complianceRate"] is None
    assert len(data["sla"]["byPriority"]) == 3
    assert all(p["complianceRate"] is None for p in data["sla"]["byPriority"])

    # Zero-task staff still listed with Available indicator
    assert len(data["staff"]) == 2
    assert all(
        s["activeAssigned"] == 0 and s["workloadIndicator"] == "Available" for s in data["staff"]
    )


def test_categories_mttr_sla_thresholds_and_staff_attribution(analytics42_app):
    ids = _seed_actors_and_room(analytics42_app)
    now_utc = datetime.now(UTC)

    with analytics42_app.app_context():
        # 1. High priority completed AT EXACT 24h deadline -> SLA compliant
        c1_created = now_utc - timedelta(hours=30)
        c1_completed = c1_created + timedelta(hours=24)  # exact 24h -> compliant!
        c1 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="High exact deadline",
            description="Details",
            category="Electrical",
            priority="high",
            status="completed",
            completed_at=c1_completed,
            created_at=c1_created,
            updated_at=c1_completed,
        )

        # 2. Medium priority completed AFTER 72h deadline (73h -> SLA breach!)
        c2_created = now_utc - timedelta(hours=80)
        c2_completed = c2_created + timedelta(hours=73)
        c2 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="Medium SLA breach",
            description="Details",
            category="Plumbing",
            priority="medium",
            status="closed",
            completed_at=c2_completed,
            closed_at=c2_completed,
            created_at=c2_created,
            updated_at=c2_completed,
        )

        # 3. Low priority completed within 168h (10h -> compliant, uncategorized NULL)
        c3_created = now_utc - timedelta(hours=20)
        c3_completed = c3_created + timedelta(hours=10)
        c3 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="Low quick fix",
            description="Details",
            category=None,
            priority="low",
            status="completed",
            completed_at=c3_completed,
            created_at=c3_created,
            updated_at=c3_completed,
        )

        # 4. High priority ACTIVE overdue (created 25h ago, still in_progress)
        c4_created = now_utc - timedelta(hours=25)
        c4 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="High active overdue",
            description="Details",
            category="Electrical",
            priority="high",
            status="in_progress",
            created_at=c4_created,
            updated_at=c4_created,
        )

        # 5. Low priority ACTIVE within SLA (created 100h ago < 168h, assigned)
        c5_created = now_utc - timedelta(hours=100)
        c5 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="Low active within SLA",
            description="Details",
            category="   ",  # whitespace -> Uncategorized
            priority="low",
            status="assigned",
            created_at=c5_created,
            updated_at=c5_created,
        )

        # 6. Rejected complaint (must be EXCLUDED from MTTR & SLA!)
        c6_created = now_utc - timedelta(hours=50)
        c6 = Complaint(
            student_user_id=ids["stu_id"],
            location_type="room",
            room_id=ids["room_id"],
            title="Rejected spam",
            description="Details",
            category="General",
            priority="high",
            status="rejected",
            rejection_reason="Spam",
            created_at=c6_created,
            updated_at=c6_created,
        )

        db.session.add_all([c1, c2, c3, c4, c5, c6])
        db.session.flush()

        # Staff assignments:
        # c1: initially assigned to staff2 (ended/reassigned), completed by staff1 (ended_at NULL)
        #     -> staff2 gets NO completion credit; staff1 gets completion credit & 6h duration
        db.session.add_all(
            [
                ComplaintAssignment(
                    complaint_id=c1.id,
                    staff_user_id=ids["staff2_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=c1_created + timedelta(hours=1),
                    ended_at=c1_created + timedelta(hours=2),
                    ended_by=ids["admin_id"],
                    end_note="Reassigned",
                ),
                ComplaintAssignment(
                    complaint_id=c1.id,
                    staff_user_id=ids["staff1_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=c1_created + timedelta(hours=18),
                    accepted_at=c1_created + timedelta(hours=19),  # 1h acceptance
                ),
                # c4: active in_progress assigned to staff1
                ComplaintAssignment(
                    complaint_id=c4.id,
                    staff_user_id=ids["staff1_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=c4_created + timedelta(hours=1),
                    accepted_at=c4_created + timedelta(hours=3),  # 2h acceptance
                ),
                # c5: active assigned to staff2
                ComplaintAssignment(
                    complaint_id=c5.id,
                    staff_user_id=ids["staff2_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=c5_created + timedelta(hours=1),
                ),
                # c6: ended rejected assignment for staff2 (must NOT count as active!)
                ComplaintAssignment(
                    complaint_id=c6.id,
                    staff_user_id=ids["staff2_id"],
                    assigned_by=ids["admin_id"],
                    assigned_at=c6_created + timedelta(hours=1),
                    ended_at=c6_created + timedelta(hours=2),
                    ended_by=ids["admin_id"],
                    end_note="Rejected",
                ),
            ]
        )
        db.session.commit()

    client = analytics42_app.test_client()
    _login(client, "warden.p42@hostelcare.test", "AdminPass123!")

    resp = client.get("/api/v1/admin/analytics/complaints?preset=7d")
    assert resp.status_code == 200
    data = resp.get_json()

    # Categories (all 6 submitted in 7d: Electrical=2, Uncategorized=2, General=1, Plumbing=1)
    cat_map = {c["category"]: c for c in data["categories"]}
    assert cat_map["Electrical"]["count"] == 2
    assert cat_map["Uncategorized"]["count"] == 2
    assert cat_map["Plumbing"]["count"] == 1
    assert cat_map["General"]["count"] == 1
    assert sum(c["count"] for c in data["categories"]) == 6
    assert 99.0 <= sum(c["percentage"] for c in data["categories"]) <= 101.0

    # MTTR: c1=24h, c2=73h, c3=10h -> avg = 107/3 = 35.67h, median = 24.0h (rejected c6 excluded!)
    res = data["resolution"]
    assert res["completedCount"] == 3
    assert res["averageHours"] == pytest.approx(35.67, abs=0.05)
    assert res["medianHours"] == pytest.approx(24.0, abs=0.05)

    # SLA: eligible=5 (c6 rejected excluded)
    # Completed within SLA: c1 (24h<=24h), c3 (10h<=168h) => 2
    # Completed after SLA: c2 (73h>72h) => 1
    # Compliance rate = 2 / 3 * 100 = 66.7%
    # Active overdue: c4 (High 25h>24h) => 1
    # Active within SLA: c5 (Low 100h<=168h) => 1
    sla = data["sla"]
    assert sla["eligibleCount"] == 5
    assert sla["completedWithinSla"] == 2
    assert sla["completedAfterSla"] == 1
    assert sla["activeOverdue"] == 1
    assert sla["activeWithinSla"] == 1
    assert sla["complianceRate"] == 66.7

    prio_map = {p["priority"]: p for p in sla["byPriority"]}
    assert prio_map["high"]["completedWithinSla"] == 1
    assert prio_map["high"]["activeOverdue"] == 1
    assert prio_map["high"]["complianceRate"] == 100.0
    assert prio_map["medium"]["completedAfterSla"] == 1
    assert prio_map["medium"]["complianceRate"] == 0.0
    assert prio_map["low"]["completedWithinSla"] == 1
    assert prio_map["low"]["activeWithinSla"] == 1

    # Staff analytics
    staff_map = {s["name"]: s for s in data["staff"]}
    ramesh = staff_map["Ramesh Kumar"]
    suresh = staff_map["Suresh Nair"]

    assert ramesh["activeAssigned"] == 1  # c4 only (c1 is completed, so NOT active!)
    assert ramesh["inProgressTasks"] == 1
    assert ramesh["completedCount"] == 1  # c1 credited to Ramesh, NOT Suresh
    assert ramesh["avgCompletionHours"] == pytest.approx(6.0, abs=0.05)  # c1: 24h - 18h = 6h
    assert ramesh["avgAcceptanceHours"] == pytest.approx(1.5, abs=0.05)  # avg(1h, 2h) = 1.5h
    assert ramesh["workloadIndicator"] == "Normal"

    assert suresh["activeAssigned"] == 1  # c5 only (c1 ended, c6 ended rejected)
    assert suresh["assignedTasks"] == 1
    assert suresh["completedCount"] == 0


def test_trends_intervals_ist_boundaries_and_completion_vs_creation_dates(analytics42_app):
    ids = _seed_actors_and_room(analytics42_app)

    # Create complaint on 2026-11-10 23:30 IST, completed on 2026-11-12 10:00 IST
    created_ist = datetime(2026, 11, 10, 23, 30, tzinfo=_IST)
    completed_ist = datetime(2026, 11, 12, 10, 0, tzinfo=_IST)
    with analytics42_app.app_context():
        db.session.add(
            Complaint(
                student_user_id=ids["stu_id"],
                location_type="room",
                room_id=ids["room_id"],
                title="Cross-day IST complaint",
                description="Details",
                category="Internet",
                priority="medium",
                status="completed",
                created_at=created_ist,
                completed_at=completed_ist,
                updated_at=completed_ist,
            )
        )
        db.session.commit()

    client = analytics42_app.test_client()
    _login(client, "warden.p42@hostelcare.test", "AdminPass123!")

    # Daily interval (<= 31 days)
    daily = client.get(
        "/api/v1/admin/analytics/complaints?preset=custom&date_from=2026-11-10&date_to=2026-11-13"
    ).get_json()
    assert daily["trends"]["interval"] == "daily"
    series_by_day = {pt["period"]: pt for pt in daily["trends"]["series"]}
    assert series_by_day["2026-11-10"]["submitted"] == 1
    assert series_by_day["2026-11-10"]["completed"] == 0
    assert series_by_day["2026-11-11"]["submitted"] == 0
    assert series_by_day["2026-11-11"]["completed"] == 0
    assert series_by_day["2026-11-12"]["submitted"] == 0
    assert series_by_day["2026-11-12"]["completed"] == 1  # uses completed_at, NOT created_at!

    # Weekly interval (32..120 days)
    weekly = client.get(
        "/api/v1/admin/analytics/complaints?preset=custom&date_from=2026-10-01&date_to=2026-11-15"
    ).get_json()
    assert weekly["trends"]["interval"] == "weekly"
    assert len(weekly["trends"]["series"]) >= 7

    # Monthly interval (> 120 days)
    monthly = client.get(
        "/api/v1/admin/analytics/complaints?preset=custom&date_from=2026-06-01&date_to=2026-11-15"
    ).get_json()
    assert monthly["trends"]["interval"] == "monthly"
    month_map = {pt["period"]: pt for pt in monthly["trends"]["series"]}
    assert month_map["2026-11"]["submitted"] == 1
    assert month_map["2026-11"]["completed"] == 1
    assert month_map["2026-06"]["submitted"] == 0

    # Invalid date range rejected with 400
    bad = client.get(
        "/api/v1/admin/analytics/complaints?preset=custom&date_from=2025-01-01&date_to=2026-11-15"
    )
    assert bad.status_code == 400
    assert bad.get_json()["error"]["code"] == "validation_error"
