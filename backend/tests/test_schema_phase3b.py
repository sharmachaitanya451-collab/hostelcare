"""Phase 3B integration tests: Alembic migrations, 20 tables, constraints, triggers T1-T3,
scoped token cleanup, and runtime least-privilege verification against `hostelcare_test`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.models.complaints import Complaint

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")

EXPECTED_20_TABLES = {
    "users",
    "student_profiles",
    "staff_profiles",
    "password_reset_tokens",
    "blocks",
    "rooms",
    "room_allocations",
    "complaints",
    "complaint_assignments",
    "complaint_updates",
    "complaint_internal_notes",
    "complaint_history",
    "fines",
    "fine_disputes",
    "fine_history",
    "payment_attempts",
    "payments",
    "payment_events",
    "notifications",
    "audit_logs",
}

APPEND_ONLY_TABLES = (
    "complaint_updates",
    "complaint_internal_notes",
    "complaint_history",
    "fine_history",
    "payments",
    "payment_events",
    "audit_logs",
)

ARGON2_SAMPLE_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQxMjM0NTY$RdescudvJCsgt3ub+b+dWRWJTmaaJObG"
)


@pytest.fixture(scope="module")
def migrated_app():
    """Apply, roll back, and reapply the Phase 3B migration on `hostelcare_test`."""
    from app import create_app

    app = create_app("testing")
    if not app.config.get("MIGRATION_DATABASE_URI") or not app.config.get(
        "SQLALCHEMY_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")

    mig_engine = create_engine(app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)

    # Ensure clean starting state on hostelcare_test
    with app.app_context():
        downgrade(directory=MIGRATIONS_DIR, revision="base")

        # Verify downgrade left 0 application tables
        with mig_engine.connect() as conn:
            remaining = set(inspect(conn).get_table_names(schema="public")) - {"alembic_version"}
            assert remaining == set(), f"Expected 0 tables after downgrade, found: {remaining}"

        # Apply upgrade -> 0001_initial_schema
        upgrade(directory=MIGRATIONS_DIR, revision="0001_initial_schema")

        # Rollback again and reapply to prove full round-trip idempotency
        downgrade(directory=MIGRATIONS_DIR, revision="base")
        with mig_engine.connect() as conn:
            remaining_after_second = set(inspect(conn).get_table_names(schema="public")) - {
                "alembic_version"
            }
            assert remaining_after_second == set()

        upgrade(directory=MIGRATIONS_DIR, revision="0001_initial_schema")

    mig_engine.dispose()
    yield app
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")


@pytest.fixture(scope="module")
def owner_engine(migrated_app):
    engine = create_engine(migrated_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def app_engine(migrated_app):
    engine = create_engine(migrated_app.config["SQLALCHEMY_DATABASE_URI"], pool_pre_ping=True)
    yield engine
    engine.dispose()


def test_internal_notes_structural_isolation_on_complaint_model():
    """Complaint model must have no relationship or backref to ComplaintInternalNote."""
    mapper_rels = {rel.key for rel in inspect(Complaint).relationships}
    assert "internal_notes" not in mapper_rels
    assert "complaint_internal_notes" not in mapper_rels
    for rel in inspect(Complaint).relationships:
        assert rel.mapper.class_.__name__ != "ComplaintInternalNote"


@pytest.mark.db
def test_all_20_tables_extension_sequences_functions_and_triggers_exist(owner_engine):
    """Verify all 20 tables, btree_gist, sequences, functions, and triggers exist."""
    with owner_engine.connect() as conn:
        tables = set(inspect(conn).get_table_names(schema="public")) - {"alembic_version"}
        assert tables == EXPECTED_20_TABLES

        # Extension btree_gist installed
        ext = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'btree_gist'")
        ).scalar()
        assert ext == "btree_gist"

        # Revision in alembic_version
        rev = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar()
        assert rev == "0001_initial_schema"

        # 3 custom sequences
        seqs = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'S' "
                    "AND c.relname IN ('complaint_ref_seq', 'fine_ref_seq', 'receipt_seq')"
                )
            )
        }
        assert seqs == {"complaint_ref_seq", "fine_ref_seq", "receipt_seq"}

        # 6 functions
        funcs = {
            row[0]: (row[1], row[2], row[3])
            for row in conn.execute(
                text(
                    "SELECT p.proname, pg_get_userbyid(p.proowner) AS owner, "
                    "p.prosecdef, has_function_privilege('public', p.oid, 'EXECUTE') AS pub_exec "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' AND p.proname IN ("
                    "'fn_check_room_allocation', 'fn_check_room_capacity_reduction', "
                    "'fn_check_fine_paid_has_payment', 'fn_check_payment_fine_state', "
                    "'fn_check_payment_amount_matches_fine', 'purge_expired_password_reset_tokens')"
                )
            )
        }
        assert len(funcs) == 6
        for fname, (owner, prosecdef, pub_exec) in funcs.items():
            assert owner == "hostelcare_owner", f"{fname} not owned by hostelcare_owner"
            assert pub_exec is False, f"{fname} should not be executable by PUBLIC"
            if fname == "purge_expired_password_reset_tokens":
                assert prosecdef is True
            else:
                assert prosecdef is False

        # Triggers T1a, T1b, T2a, T2b, T3
        triggers = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT tgname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND NOT t.tgisinternal"
                )
            )
        }
        assert {
            "trg_room_allocations_check_capacity",
            "trg_rooms_check_capacity_reduction",
            "trg_fines_paid_requires_payment",
            "trg_payments_requires_paid_fine",
            "trg_payment_attempts_check_amount",
            "trg_payments_check_amount",
        }.issubset(triggers)


@pytest.mark.db
def test_catalogue_permission_verification_queries(owner_engine):
    """Run all 7 permission verification queries from docs/database-design.md Section 12.5."""
    with owner_engine.connect() as conn:
        # 1. Nothing in public is owned by the runtime role (expect 0 rows)
        non_owner = conn.execute(
            text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) <> 'hostelcare_owner'"
            )
        ).fetchall()
        assert non_owner == []

        # 2. Runtime role cannot create objects or touch alembic_version (expect all false)
        q2 = conn.execute(
            text(
                "SELECT has_schema_privilege('hostelcare_app','public','CREATE'), "
                "has_table_privilege('hostelcare_app','public.alembic_version','SELECT'), "
                "has_table_privilege('hostelcare_app','public.alembic_version','INSERT')"
            )
        ).fetchone()
        assert q2 == (False, False, False)

        # 3. Append-only tables: no UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER for runtime role
        q3 = conn.execute(
            text(
                "SELECT t, p FROM unnest(ARRAY['complaint_updates','complaint_internal_notes',"
                "'complaint_history','fine_history','payments','payment_events','audit_logs']) t, "
                "unnest(ARRAY['UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p "
                "WHERE has_table_privilege('hostelcare_app', t, p)"
            )
        ).fetchall()
        assert q3 == []

        # 4. Immutable columns are not updatable (expect all false)
        q4 = conn.execute(
            text(
                "SELECT has_column_privilege('hostelcare_app','fines','amount_inr','UPDATE'), "
                "has_column_privilege('hostelcare_app','users','role','UPDATE'), "
                "has_column_privilege('hostelcare_app','room_allocations','bed_number','UPDATE'), "
                "has_column_privilege('hostelcare_app','complaints','student_user_id','UPDATE'), "
                "has_column_privilege('hostelcare_app','payment_attempts','fine_id','UPDATE')"
            )
        ).fetchone()
        assert q4 == (False, False, False, False, False)

        # 5. Zero tables may be deleted from by the runtime role (expect 0 rows)
        q5 = conn.execute(
            text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                "AND has_table_privilege('hostelcare_app', c.oid, 'DELETE')"
            )
        ).fetchall()
        assert q5 == []

        # 6. Sequences: USAGE only (no UPDATE)
        q6 = conn.execute(
            text(
                "SELECT c.relname, has_sequence_privilege('hostelcare_app', c.oid, 'USAGE') AS u, "
                "has_sequence_privilege('hostelcare_app', c.oid, 'UPDATE') AS upd "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'S' "
                "AND c.relname IN ('complaint_ref_seq','fine_ref_seq','receipt_seq')"
            )
        ).fetchall()
        assert len(q6) == 3
        for _, usage, upd in q6:
            assert usage is True
            assert upd is False


@pytest.mark.db
def test_runtime_role_behavioral_restrictions(app_engine):
    """Verify `hostelcare_app` is blocked from DDL, alembic_version, DELETE, and immutable cols."""
    with app_engine.connect() as conn:
        for forbidden_sql in (
            "CREATE TABLE public._hc_forbidden (id int)",
            "ALTER TABLE public.users ADD COLUMN _forbidden int",
            "DROP TABLE public.audit_logs",
            "TRUNCATE TABLE public.users",
            "SELECT * FROM public.alembic_version",
            "DELETE FROM public.password_reset_tokens",
            "DELETE FROM public.users",
            "DELETE FROM public.complaints",
            "DELETE FROM public.fines",
            "DELETE FROM public.payments",
            "DELETE FROM public.audit_logs",
            "UPDATE public.audit_logs SET action = 'tampered'",
            "UPDATE public.payments SET amount_inr = 1.00",
            "UPDATE public.users SET role = 'admin'",
            "UPDATE public.fines SET amount_inr = 1.00",
            "UPDATE public.room_allocations SET bed_number = 2",
        ):
            with pytest.raises(ProgrammingError) as exc_info:
                conn.execute(text(forbidden_sql))
            err_msg = str(exc_info.value).lower()
            assert "permission denied" in err_msg or "must be owner" in err_msg
            conn.rollback()


@pytest.mark.db
def test_password_hash_marker_and_scoped_reset_token_cleanup(app_engine, owner_engine):
    """Verify `'!'` password_hash marker, CHECK constraints, and scoped token cleanup function."""
    with app_engine.connect() as conn:
        # 1. Admin account with '!' unusable-password marker is allowed
        admin_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('warden.cleanup@hostelcare.test', 'Chief Warden', '!', 'admin', 'active') "
                "RETURNING id"
            )
        ).scalar_one()

        # 2. Invalid password hash (neither '!' nor '$argon2id$%') is rejected
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                    "VALUES ('badhash@hostelcare.test', 'Bad Hash', 'plaintext123', "
                    "'admin', 'active')"
                )
            )
        conn.rollback()

        # Re-insert admin in clean transaction
        admin_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('warden.cleanup@hostelcare.test', 'Chief Warden', '!', 'admin', 'active') "
                "RETURNING id"
            )
        ).scalar_one()

        now = datetime.now(UTC)

        # Insert a >25-hour-old expired token (revoked so we can also insert a recent/active one)
        old_created = now - timedelta(hours=26)
        old_expires = old_created + timedelta(minutes=30)
        old_token_id = conn.execute(
            text(
                "INSERT INTO public.password_reset_tokens "
                "(user_id, token_hash, created_at, expires_at, revoked_at) "
                "VALUES (:uid, :th, :c, :e, :r) RETURNING id"
            ),
            {
                "uid": admin_id,
                "th": "a" * 64,
                "c": old_created,
                "e": old_expires,
                "r": old_expires,
            },
        ).scalar_one()

        # Insert a recently expired token (created 45m ago, expired 15m ago -> inside 1h window)
        recent_created = now - timedelta(minutes=45)
        recent_expires = recent_created + timedelta(minutes=30)
        recent_token_id = conn.execute(
            text(
                "INSERT INTO public.password_reset_tokens "
                "(user_id, token_hash, created_at, expires_at, revoked_at) "
                "VALUES (:uid, :th, :c, :e, :r) RETURNING id"
            ),
            {
                "uid": admin_id,
                "th": "b" * 64,
                "c": recent_created,
                "e": recent_expires,
                "r": recent_expires,
            },
        ).scalar_one()

        # Insert a currently active live token (expires in 25m)
        live_created = now
        live_expires = live_created + timedelta(minutes=25)
        live_token_id = conn.execute(
            text(
                "INSERT INTO public.password_reset_tokens "
                "(user_id, token_hash, created_at, expires_at) "
                "VALUES (:uid, :th, :c, :e) RETURNING id"
            ),
            {
                "uid": admin_id,
                "th": "c" * 64,
                "c": live_created,
                "e": live_expires,
            },
        ).scalar_one()

        # Run scoped cleanup function as hostelcare_app
        deleted_count = conn.execute(
            text("SELECT public.purge_expired_password_reset_tokens()")
        ).scalar_one()
        assert deleted_count == 1

        remaining_ids = {
            row[0]
            for row in conn.execute(
                text("SELECT id FROM public.password_reset_tokens WHERE user_id = :uid"),
                {"uid": admin_id},
            )
        }
        assert old_token_id not in remaining_ids
        assert recent_token_id in remaining_ids
        assert live_token_id in remaining_ids

        conn.rollback()


@pytest.mark.db
def test_room_allocation_termination_exclusion_and_triggers_t1a_t1b(app_engine):
    """Verify all 8 NULL combinations of termination constraint, GiST exclusions, and T1a/T1b."""
    with app_engine.connect() as conn:
        admin_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('admin.rooms@hostelcare.test', 'Admin', :pw, 'admin', 'active') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()

        s1_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('s1.rooms@hostelcare.test', 'Student One', :pw, 'student', 'active') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO public.student_profiles (user_id, role, roll_number) "
                "VALUES (:uid, 'student', '2026CS101')"
            ),
            {"uid": s1_id},
        )

        s2_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('s2.rooms@hostelcare.test', 'Student Two', :pw, 'student', 'active') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO public.student_profiles (user_id, role, roll_number) "
                "VALUES (:uid, 'student', '2026CS102')"
            ),
            {"uid": s2_id},
        )

        pending_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('pending.rooms@hostelcare.test', 'Pending', :pw, 'student', 'pending') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO public.student_profiles (user_id, role, roll_number) "
                "VALUES (:uid, 'student', '2026CS103')"
            ),
            {"uid": pending_id},
        )

        block_id = conn.execute(
            text("INSERT INTO public.blocks (code, name) VALUES ('A', 'Block A') RETURNING id")
        ).scalar_one()

        room_id = conn.execute(
            text(
                "INSERT INTO public.rooms "
                "(block_id, room_number, floor, room_type, capacity, is_active) "
                "VALUES (:bid, '101', 1, 'Double', 2, true) RETURNING id"
            ),
            {"bid": block_id},
        ).scalar_one()

        # Verify all 6 invalid NULL/NOT NULL combinations of (end_date, ended_by, end_reason) fail
        invalid_termination_combos = [
            (None, None, "Graduated"),
            (None, admin_id, None),
            (None, admin_id, "Graduated"),
            (date(2026, 12, 1), None, None),
            (date(2026, 12, 1), None, "Graduated"),
            (date(2026, 12, 1), admin_id, None),
            (date(2026, 12, 1), admin_id, "   "),  # blank reason
        ]
        for end_dt, end_by, end_rsn in invalid_termination_combos:
            sp = conn.begin_nested()
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO public.room_allocations "
                        "(room_id, student_user_id, bed_number, start_date, end_date, "
                        "allocated_by, ended_by, end_reason) "
                        "VALUES (:rid, :sid, 1, '2026-11-01', :ed, :ab, :eb, :er)"
                    ),
                    {
                        "rid": room_id,
                        "sid": s1_id,
                        "ed": end_dt,
                        "ab": admin_id,
                        "eb": end_by,
                        "er": end_rsn,
                    },
                )
            sp.rollback()

        # Valid active allocation: (NULL, NULL, NULL)
        alloc1_id = conn.execute(
            text(
                "INSERT INTO public.room_allocations "
                "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                "VALUES (:rid, :sid, 2, '2026-11-01', :ab) RETURNING id"
            ),
            {"rid": room_id, "sid": s1_id, "ab": admin_id},
        ).scalar_one()

        # Exclusion constraint 1: overlapping allocation for the same student is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.room_allocations "
                    "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                    "VALUES (:rid, :sid, 1, '2026-11-10', :ab)"
                ),
                {"rid": room_id, "sid": s1_id, "ab": admin_id},
            )
        sp.rollback()

        # Exclusion constraint 2: same bed (room_id, bed_number=2) for another student is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.room_allocations "
                    "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                    "VALUES (:rid, :sid, 2, '2026-11-10', :ab)"
                ),
                {"rid": room_id, "sid": s2_id, "ab": admin_id},
            )
        sp.rollback()

        # Trigger T1a: bed_number (3) > room capacity (2) is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.room_allocations "
                    "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                    "VALUES (:rid, :sid, 3, '2026-11-10', :ab)"
                ),
                {"rid": room_id, "sid": s2_id, "ab": admin_id},
            )
        sp.rollback()

        # Trigger T1a: non-active student ('pending') is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.room_allocations "
                    "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                    "VALUES (:rid, :sid, 1, '2026-11-10', :ab)"
                ),
                {"rid": room_id, "sid": pending_id, "ab": admin_id},
            )
        sp.rollback()

        # Trigger T1b: reducing room capacity to 1 while bed 2 is occupied is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text("UPDATE public.rooms SET capacity = 1 WHERE id = :rid"),
                {"rid": room_id},
            )
        sp.rollback()

        # Same-day room transfer: end old allocation on 2026-11-14 with all 3 termination fields,
        # and insert new allocation starting on 2026-11-14 (half-open [start, end) ranges)
        conn.execute(
            text(
                "UPDATE public.room_allocations "
                "SET end_date = '2026-11-14', ended_by = :eb, "
                "end_reason = 'Room transfer to bed 1' "
                "WHERE id = :aid"
            ),
            {"eb": admin_id, "aid": alloc1_id},
        )
        conn.execute(
            text(
                "INSERT INTO public.room_allocations "
                "(room_id, student_user_id, bed_number, start_date, allocated_by) "
                "VALUES (:rid, :sid, 1, '2026-11-14', :ab)"
            ),
            {"rid": room_id, "sid": s1_id, "ab": admin_id},
        )

        conn.rollback()


@pytest.mark.db
def test_payment_fine_triggers_t2a_t2b_t3_and_cross_fine_isolation(app_engine):
    """Verify T2a, T2b, T3, composite FK `(payment_attempt_id, fine_id)`, and atomic payment."""
    with app_engine.connect() as conn:
        admin_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('admin.pay@hostelcare.test', 'Admin', :pw, 'admin', 'active') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()

        student_id = conn.execute(
            text(
                "INSERT INTO public.users (email, full_name, password_hash, role, status) "
                "VALUES ('student.pay@hostelcare.test', 'Student', :pw, 'student', 'active') "
                "RETURNING id"
            ),
            {"pw": ARGON2_SAMPLE_HASH},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO public.student_profiles (user_id, role, roll_number) "
                "VALUES (:uid, 'student', '2026CS201')"
            ),
            {"uid": student_id},
        )

        fine1_id = conn.execute(
            text(
                "INSERT INTO public.fines "
                "(student_user_id, description, amount_inr, issue_date, due_date, issued_by) "
                "VALUES (:sid, 'Damaged study chair', 500.00, '2026-11-01', '2026-11-15', :aid) "
                "RETURNING id"
            ),
            {"sid": student_id, "aid": admin_id},
        ).scalar_one()

        fine2_id = conn.execute(
            text(
                "INSERT INTO public.fines "
                "(student_user_id, description, amount_inr, issue_date, due_date, issued_by) "
                "VALUES (:sid, 'Late night noise', 750.00, '2026-11-02', '2026-11-16', :aid) "
                "RETURNING id"
            ),
            {"sid": student_id, "aid": admin_id},
        ).scalar_one()

        # 1. Trigger T3: payment_attempt with wrong amount (400.00 != 500.00) is rejected
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.payment_attempts "
                    "(fine_id, initiated_by, amount_inr, currency, status) "
                    "VALUES (:fid, :uid, 400.00, 'INR', 'created')"
                ),
                {"fid": fine1_id, "uid": student_id},
            )
        sp.rollback()

        # 2. Valid payment_attempt for fine1 (500.00 INR)
        attempt1_id = conn.execute(
            text(
                "INSERT INTO public.payment_attempts "
                "(fine_id, initiated_by, amount_inr, currency, gateway_order_id, status) "
                "VALUES (:fid, :uid, 500.00, 'INR', 'order_test_001', 'created') RETURNING id"
            ),
            {"fid": fine1_id, "uid": student_id},
        ).scalar_one()

        # 3. Cross-fine reuse: linking attempt1 (fine1) to a payment for fine2 fails composite FK
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(fine_id, payment_attempt_id, channel, amount_inr, currency, "
                    "gateway_order_id, gateway_payment_id, payment_method, "
                    "verification_method, verified_at) "
                    "VALUES (:f2, :att1, 'razorpay', 750.00, 'INR', 'order_test_001', "
                    "'pay_test_001', 'upi', 'webhook', now())"
                ),
                {"f2": fine2_id, "att1": attempt1_id},
            )
        sp.rollback()

        # 4. Trigger T2a: marking fine1 'paid' without a verified payment row fails
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text("UPDATE public.fines SET status = 'paid', paid_at = now() WHERE id = :fid"),
                {"fid": fine1_id},
            )
            conn.execute(text("SET CONSTRAINTS trg_fines_paid_requires_payment IMMEDIATE"))
        sp.rollback()

        # 5. Trigger T2b: inserting a payment without updating fine1.status to 'paid' fails
        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(fine_id, payment_attempt_id, channel, amount_inr, currency, "
                    "gateway_order_id, gateway_payment_id, payment_method, "
                    "verification_method, verified_at) "
                    "VALUES (:f1, :att1, 'razorpay', 500.00, 'INR', 'order_test_001', "
                    "'pay_test_001', 'upi', 'webhook', now())"
                ),
                {"f1": fine1_id, "att1": attempt1_id},
            )
            conn.execute(text("SET CONSTRAINTS trg_payments_requires_paid_fine IMMEDIATE"))
        sp.rollback()

        # 6. Complete atomic transaction (payment + attempt succeeded + fine paid) succeeds
        sp = conn.begin_nested()
        pay_id, receipt_no = conn.execute(
            text(
                "INSERT INTO public.payments "
                "(fine_id, payment_attempt_id, channel, amount_inr, currency, "
                "gateway_order_id, gateway_payment_id, payment_method, "
                "verification_method, verified_at) "
                "VALUES (:f1, :att1, 'razorpay', 500.00, 'INR', 'order_test_001', "
                "'pay_test_001', 'upi', 'webhook', now()) RETURNING id, receipt_number"
            ),
            {"f1": fine1_id, "att1": attempt1_id},
        ).fetchone()
        assert receipt_no.startswith("RCP-")

        conn.execute(
            text(
                "UPDATE public.payment_attempts "
                "SET status = 'succeeded', gateway_payment_id = 'pay_test_001', "
                "payment_method = 'upi', verified_at = now(), updated_at = now() "
                "WHERE id = :att1"
            ),
            {"att1": attempt1_id},
        )
        conn.execute(
            text(
                "UPDATE public.fines "
                "SET status = 'paid', paid_at = now(), version = version + 1, updated_at = now() "
                "WHERE id = :f1"
            ),
            {"f1": fine1_id},
        )
        conn.execute(
            text(
                "INSERT INTO public.payment_events "
                "(payment_attempt_id, source, event_type, gateway_event_id, "
                "signature_valid, outcome, payload) "
                "VALUES (:att1, 'webhook', 'payment.captured', 'evt_unique_001', "
                "true, 'applied', '{\"ok\": true}'::jsonb)"
            ),
            {"att1": attempt1_id},
        )
        # Validate deferred triggers T2a and T2b immediately
        conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))

        # 7. Duplicate webhook event id is rejected by uq_payment_events_gateway_event
        sp_dup = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO public.payment_events "
                    "(payment_attempt_id, source, event_type, gateway_event_id, "
                    "signature_valid, outcome, payload) "
                    "VALUES (:att1, 'webhook', 'payment.captured', 'evt_unique_001', "
                    "true, 'duplicate', '{}'::jsonb)"
                ),
                {"att1": attempt1_id},
            )
        sp_dup.rollback()

        sp.rollback()
        conn.rollback()


@pytest.mark.db
def test_readyz_succeeds_with_runtime_database_connection(migrated_app):
    """Verify Flask `/readyz` endpoint connects using the runtime role (`hostelcare_app`)."""
    client = migrated_app.test_client()
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


@pytest.mark.db
def test_all_20_sqlalchemy_models_round_trip_under_runtime_role(migrated_app):
    """Verify `hostelcare_app` can perform approved ORM operations across all 20 models."""
    from app.extensions import db
    from app.models import (
        AuditLog,
        Block,
        Complaint,
        ComplaintAssignment,
        ComplaintHistory,
        ComplaintInternalNote,
        ComplaintUpdate,
        Fine,
        FineDispute,
        FineHistory,
        Notification,
        PasswordResetToken,
        Payment,
        PaymentAttempt,
        PaymentEvent,
        Room,
        RoomAllocation,
        StaffProfile,
        StudentProfile,
        User,
    )

    now = datetime.now(UTC)
    with migrated_app.app_context():
        # 1. Users (admin, staff, student)
        admin = User(
            email="orm.admin@hostelcare.test",
            full_name="ORM Admin",
            designation="Chief Warden",
            password_hash=ARGON2_SAMPLE_HASH,
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.flush()

        staff_user = User(
            email="orm.staff@hostelcare.test",
            full_name="ORM Electrician",
            password_hash="!",  # noqa: S106
            role="staff",
            status="active",
            created_by=admin.id,
        )
        student_user = User(
            email="orm.student@hostelcare.test",
            full_name="ORM Student",
            password_hash=ARGON2_SAMPLE_HASH,
            role="student",
            status="pending",
        )
        db.session.add_all([staff_user, student_user])
        db.session.flush()

        # 2. Block & Room
        block = Block(code="B", name="Block B (Takshashila)", display_order=1, is_active=True)
        db.session.add(block)
        db.session.flush()

        room = Room(
            block_id=block.id,
            room_number="204",
            floor=2,
            room_type="Double Occupancy",
            capacity=2,
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()

        # 3. StudentProfile & StaffProfile
        student_prof = StudentProfile(
            user_id=student_user.id,
            role="student",
            roll_number="2026EE301",
            requested_room_id=room.id,
        )
        staff_prof = StaffProfile(
            user_id=staff_user.id,
            role="staff",
            staff_code="STF-0101",
            trade="Electrical",
            shift="Morning",
        )
        db.session.add_all([student_prof, staff_prof])
        db.session.flush()

        # Column-level UPDATE on User and StudentProfile (approve student)
        student_user.status = "active"
        student_user.updated_at = now
        student_prof.reviewed_by = admin.id
        student_prof.reviewed_at = now
        student_prof.review_note = "Approved and verified"
        student_prof.updated_at = now
        db.session.flush()

        # 4. PasswordResetToken (insert + column-level UPDATE)
        prt = PasswordResetToken(
            user_id=staff_user.id,
            token_hash="d" * 64,
            requested_by=admin.id,
            created_at=now,
            expires_at=now + timedelta(minutes=30),
            request_ip="127.0.0.1",
        )
        db.session.add(prt)
        db.session.flush()
        prt.used_at = now
        db.session.flush()

        # 5. RoomAllocation
        alloc = RoomAllocation(
            room_id=room.id,
            student_user_id=student_prof.user_id,
            bed_number=1,
            start_date=date(2026, 11, 14),
            allocated_by=admin.id,
        )
        db.session.add(alloc)
        db.session.flush()

        # 6. Complaint, ComplaintAssignment, ComplaintUpdate, InternalNote, ComplaintHistory
        complaint = Complaint(
            student_user_id=student_prof.user_id,
            location_type="room",
            room_id=room.id,
            title="Ceiling fan regulator broken",
            description="Regulator knob spins freely and fan stays at speed 1.",
            category="Electrical",
            priority="medium",
            status="submitted",
        )
        db.session.add(complaint)
        db.session.flush()
        assert complaint.reference_no.startswith("CMP-")

        complaint.status = "assigned"
        complaint.updated_at = now
        assignment = ComplaintAssignment(
            complaint_id=complaint.id,
            staff_user_id=staff_prof.user_id,
            assigned_by=admin.id,
            instructions="Replace rotary regulator unit",
        )
        db.session.add(assignment)
        db.session.flush()
        db.session.refresh(assignment)

        assignment.accepted_at = assignment.assigned_at + timedelta(seconds=1)
        assignment.started_at = assignment.assigned_at + timedelta(seconds=2)
        complaint.status = "in_progress"
        db.session.flush()

        c_update = ComplaintUpdate(
            complaint_id=complaint.id,
            assignment_id=assignment.id,
            author_user_id=staff_user.id,
            update_type="progress",
            body="Inspected switchboard; replacing capacitor and regulator.",
        )
        c_note = ComplaintInternalNote(
            complaint_id=complaint.id,
            author_user_id=admin.id,
            body="Batch of regulators in Block B under warranty check.",
        )
        db.session.add_all([c_update, c_note])
        db.session.flush()

        c_hist = ComplaintHistory(
            complaint_id=complaint.id,
            actor_user_id=staff_user.id,
            action="progress_updated",
            from_status="in_progress",
            to_status="in_progress",
            note="Progress logged",
            assignment_id=assignment.id,
            update_id=c_update.id,
        )
        db.session.add(c_hist)
        db.session.flush()

        # 7. Fine, FineDispute, FineHistory, PaymentAttempt, Payment, PaymentEvent
        fine = Fine(
            student_user_id=student_prof.user_id,
            room_id=room.id,
            category="Property Damage",
            description="Broken window latch in room 204",
            amount_inr=Decimal("350.00"),
            issue_date=date(2026, 11, 10),
            due_date=date(2026, 11, 25),
            issued_by=admin.id,
            status="disputed",
        )
        db.session.add(fine)
        db.session.flush()
        assert fine.reference_no.startswith("FIN-")

        dispute = FineDispute(
            fine_id=fine.id,
            raised_by=student_prof.user_id,
            reason="Latch was already loose on move-in day.",
            status="open",
        )
        db.session.add(dispute)
        db.session.flush()

        # Reject dispute -> fine back to pending
        dispute.status = "rejected"
        dispute.decided_by = admin.id
        dispute.decided_at = now
        dispute.decision_reason = "Move-in inventory checklist signed with intact latch."
        fine.status = "pending"
        fine.updated_at = now
        db.session.flush()

        # PaymentAttempt + Payment + PaymentEvent + FineHistory
        attempt = PaymentAttempt(
            fine_id=fine.id,
            initiated_by=student_user.id,
            amount_inr=Decimal("350.00"),
            currency="INR",
            gateway_order_id="order_orm_001",
            gateway_payment_id="pay_orm_001",
            payment_method="upi",
            status="succeeded",
            verified_at=now,
        )
        db.session.add(attempt)
        db.session.flush()

        payment = Payment(
            fine_id=fine.id,
            payment_attempt_id=attempt.id,
            channel="razorpay",
            amount_inr=Decimal("350.00"),
            currency="INR",
            gateway_order_id="order_orm_001",
            gateway_payment_id="pay_orm_001",
            payment_method="upi",
            verification_method="webhook",
            verified_at=now,
        )
        fine.status = "paid"
        fine.paid_at = now
        fine.version = 2
        fine.updated_at = now
        db.session.add(payment)
        db.session.flush()
        assert payment.receipt_number.startswith("RCP-")

        pevent = PaymentEvent(
            payment_attempt_id=attempt.id,
            source="webhook",
            event_type="payment.captured",
            gateway_event_id="evt_orm_001",
            signature_valid=True,
            outcome="applied",
            payload={"order_id": "order_orm_001", "payment_id": "pay_orm_001"},
        )
        fhist = FineHistory(
            fine_id=fine.id,
            actor_user_id=None,
            action="payment_verified",
            from_status="pending",
            to_status="paid",
            note="Verified via webhook",
            payment_id=payment.id,
            payment_attempt_id=attempt.id,
            dispute_id=dispute.id,
        )
        db.session.add_all([pevent, fhist])
        db.session.flush()

        # 8. Notification & AuditLog
        notif = Notification(
            recipient_user_id=student_user.id,
            category="payment",
            event_type="payment_verified",
            title="Fine payment verified",
            message=f"Payment {payment.receipt_number} for {fine.reference_no} received.",
            entity_type="fine",
            entity_ref=fine.reference_no,
        )
        audit = AuditLog(
            actor_user_id=admin.id,
            actor_role="admin",
            action="payment.verified",
            target_type="fine",
            target_id=fine.reference_no,
            metadata_json={"receipt": payment.receipt_number},
            request_id="req-orm-test-1",
            ip_address="127.0.0.1",
        )
        db.session.add_all([notif, audit])
        db.session.flush()

        # Mark notification read (column-level UPDATE on notifications.read_at)
        notif.read_at = now
        db.session.flush()

        # Verify deferred triggers T2a and T2b pass on ORM state
        db.session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        db.session.rollback()
