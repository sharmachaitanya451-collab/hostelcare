"""Initial HostelCare Phase 3B schema: 20 tables, btree_gist, sequences, triggers T1-T3, cleanup function, and least-privilege grants.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-14 14:05:00+05:30
"""

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

_SAFE_PG_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _role_name(env_key: str, default: str) -> str:
    val = os.environ.get(env_key, default).strip() or default
    if not _SAFE_PG_IDENT.match(val):
        raise RuntimeError(f"Invalid PostgreSQL identifier in {env_key}: {val!r}")
    return val


def _has_role(role_name: str) -> bool:
    return (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role_name})
        .scalar()
        is not None
    )


def upgrade() -> None:
    owner_role = _role_name("DB_MIGRATION_ROLE", "hostelcare_owner")
    app_role = _role_name("DB_APP_ROLE", "hostelcare_app")
    has_owner_role = _has_role(owner_role)
    has_app_role = _has_role(app_role)

    # -------------------------------------------------------------------------
    # 1. PostgreSQL Extension (`btree_gist` — trusted extension in PG 18)
    # -------------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # -------------------------------------------------------------------------
    # 2. Custom Reference Sequences & Sequence Grants
    # -------------------------------------------------------------------------
    for seq_name in ("complaint_ref_seq", "fine_ref_seq", "receipt_seq"):
        op.execute(
            f"CREATE SEQUENCE public.{seq_name} AS bigint "
            "START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1"
        )
        if has_owner_role:
            op.execute(f"ALTER SEQUENCE public.{seq_name} OWNER TO {owner_role}")
        op.execute(f"REVOKE ALL ON SEQUENCE public.{seq_name} FROM PUBLIC")
        if has_app_role:
            op.execute(f"REVOKE ALL ON SEQUENCE public.{seq_name} FROM {app_role}")
            op.execute(f"GRANT USAGE ON SEQUENCE public.{seq_name} TO {app_role}")

    # -------------------------------------------------------------------------
    # 3. Tables (in strict foreign-key dependency order)
    # -------------------------------------------------------------------------

    # 3.1 `users`
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("designation", sa.String(length=80), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "session_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "failed_login_count",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_users_created_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("public_id", name="uq_users_public_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("id", "role", name="uq_users_id_role"),
        sa.CheckConstraint("role IN ('student', 'staff', 'admin')", name="role_valid"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'rejected', 'suspended', 'deactivated')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "role = 'student' OR status NOT IN ('pending', 'rejected')",
            name="role_status_valid",
        ),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND position('@' in email) > 1",
            name="email_normalized",
        ),
        sa.CheckConstraint("btrim(full_name) <> ''", name="full_name_nonempty"),
        sa.CheckConstraint(
            "password_hash = '!' OR password_hash LIKE '$argon2id$%'",
            name="password_hash_format",
        ),
        sa.CheckConstraint(
            "failed_login_count >= 0",
            name="failed_login_count_nonneg",
        ),
        sa.CheckConstraint("session_version >= 1", name="session_version_pos"),
    )
    op.create_index("ix_users_role_status", "users", ["role", "status"], unique=False)
    op.create_index(
        "ix_users_pending",
        "users",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("role = 'student' AND status = 'pending'"),
    )

    # 3.2 `blocks`
    op.create_table(
        "blocks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "display_order",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_blocks"),
        sa.UniqueConstraint("code", name="uq_blocks_code"),
        sa.UniqueConstraint("name", name="uq_blocks_name"),
        sa.CheckConstraint("code ~ '^[A-Z0-9]{1,10}$'", name="code_format"),
        sa.CheckConstraint("btrim(name) <> ''", name="name_nonempty"),
    )

    # 3.3 `rooms`
    op.create_table(
        "rooms",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("block_id", sa.BigInteger(), nullable=False),
        sa.Column("room_number", sa.String(length=10), nullable=False),
        sa.Column("floor", sa.SmallInteger(), nullable=False),
        sa.Column("room_type", sa.String(length=40), nullable=True),
        sa.Column("capacity", sa.SmallInteger(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["blocks.id"],
            name="fk_rooms_block_id_blocks",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("block_id", "room_number", name="uq_rooms_block_id_room_number"),
        sa.CheckConstraint("capacity BETWEEN 1 AND 8", name="capacity_range"),
        sa.CheckConstraint("floor BETWEEN 0 AND 50", name="floor_range"),
        sa.CheckConstraint(
            "room_number ~ '^[A-Za-z0-9-]{1,10}$'",
            name="room_number_format",
        ),
    )
    op.create_index("ix_rooms_block_id", "rooms", ["block_id"], unique=False)
    op.create_index("ix_rooms_block_floor", "rooms", ["block_id", "floor"], unique=False)

    # 3.4 `student_profiles`
    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=10),
            server_default=sa.text("'student'"),
            nullable=False,
        ),
        sa.Column("roll_number", sa.String(length=32), nullable=False),
        sa.Column("requested_room_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_student_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id", "role"],
            ["users.id", "users.role"],
            name="fk_student_profiles_user_id_role_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["requested_room_id"],
            ["rooms.id"],
            name="fk_student_profiles_requested_room_id_rooms",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name="fk_student_profiles_reviewed_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("roll_number", name="uq_student_profiles_roll_number"),
        sa.CheckConstraint("role = 'student'", name="role_is_student"),
        sa.CheckConstraint(
            "roll_number = upper(btrim(roll_number)) "
            "AND roll_number ~ '^[A-Z0-9][A-Z0-9/_-]{2,31}$'",
            name="roll_number_format",
        ),
        sa.CheckConstraint(
            "(reviewed_by IS NULL) = (reviewed_at IS NULL)",
            name="review_audit_pair",
        ),
        sa.CheckConstraint(
            "review_note IS NULL OR btrim(review_note) <> ''",
            name="review_note_nonempty",
        ),
    )

    # 3.5 `staff_profiles`
    op.create_table(
        "staff_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=10),
            server_default=sa.text("'staff'"),
            nullable=False,
        ),
        sa.Column("staff_code", sa.String(length=20), nullable=False),
        sa.Column("trade", sa.String(length=60), nullable=False),
        sa.Column("shift", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_staff_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id", "role"],
            ["users.id", "users.role"],
            name="fk_staff_profiles_user_id_role_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("staff_code", name="uq_staff_profiles_staff_code"),
        sa.CheckConstraint("role = 'staff'", name="role_is_staff"),
        sa.CheckConstraint("btrim(trade) <> ''", name="trade_nonempty"),
        sa.CheckConstraint(
            "staff_code ~ '^[A-Z0-9-]{3,20}$'",
            name="staff_code_format",
        ),
    )
    op.create_index("ix_staff_profiles_trade", "staff_profiles", ["trade"], unique=False)

    # 3.6 `password_reset_tokens`
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", postgresql.INET(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_password_reset_tokens_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_password_reset_tokens_requested_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name="token_hash_hex",
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '30 minutes'",
            name="expires_within_30m",
        ),
        sa.CheckConstraint(
            "NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="not_used_and_revoked",
        ),
    )
    op.create_index(
        "uq_prt_one_live",
        "password_reset_tokens",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_index(
        "ix_prt_user_created",
        "password_reset_tokens",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_prt_ip_created",
        "password_reset_tokens",
        ["request_ip", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("request_ip IS NOT NULL"),
    )
    op.create_index("ix_prt_expires", "password_reset_tokens", ["expires_at"], unique=False)

    # 3.7 `room_allocations`
    op.create_table(
        "room_allocations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("bed_number", sa.SmallInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("allocated_by", sa.BigInteger(), nullable=False),
        sa.Column("ended_by", sa.BigInteger(), nullable=True),
        sa.Column("end_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_room_allocations"),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_room_allocations_room_id_rooms",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"],
            ["student_profiles.user_id"],
            name="fk_room_allocations_student_user_id_student_profiles",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["allocated_by"],
            ["users.id"],
            name="fk_room_allocations_allocated_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["users.id"],
            name="fk_room_allocations_ended_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint("bed_number >= 1", name="bed_number_pos"),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="date_order",
        ),
        sa.CheckConstraint(
            "(end_date IS NULL AND ended_by IS NULL AND end_reason IS NULL) OR "
            "(end_date IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL "
            "AND btrim(end_reason) <> '')",
            name="termination",
        ),
        postgresql.ExcludeConstraint(
            (sa.column("student_user_id"), "="),
            (
                sa.func.daterange(sa.column("start_date"), sa.column("end_date"), sa.text("'[)'")),
                "&&",
            ),
            name="ex_alloc_student_no_overlap",
            using="gist",
        ),
        postgresql.ExcludeConstraint(
            (sa.column("room_id"), "="),
            (sa.column("bed_number"), "="),
            (
                sa.func.daterange(sa.column("start_date"), sa.column("end_date"), sa.text("'[)'")),
                "&&",
            ),
            name="ex_alloc_bed_no_overlap",
            using="gist",
        ),
    )
    op.create_index(
        "ix_alloc_room_open",
        "room_allocations",
        ["room_id"],
        unique=False,
        postgresql_where=sa.text("end_date IS NULL"),
    )
    op.create_index(
        "ix_alloc_student",
        "room_allocations",
        ["student_user_id", sa.text("start_date DESC")],
        unique=False,
    )

    # 3.8 `complaints`
    op.create_table(
        "complaints",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "reference_no",
            sa.String(length=20),
            server_default=sa.text(
                "'CMP-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
                "|| '-' || to_char(nextval('public.complaint_ref_seq'), 'FM9999999999999900000')"
            ),
            nullable=False,
        ),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("location_type", sa.String(length=11), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=True),
        sa.Column("block_id", sa.BigInteger(), nullable=True),
        sa.Column("location_detail", sa.String(length=150), nullable=True),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column(
            "priority",
            sa.String(length=6),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=12),
            server_default=sa.text("'submitted'"),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaints"),
        sa.ForeignKeyConstraint(
            ["student_user_id"],
            ["student_profiles.user_id"],
            name="fk_complaints_student_user_id_student_profiles",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_complaints_room_id_rooms",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["blocks.id"],
            name="fk_complaints_block_id_blocks",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("reference_no", name="uq_complaints_reference_no"),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'assigned', 'accepted', "
            "'in_progress', 'completed', 'closed', 'rejected')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="priority_valid",
        ),
        sa.CheckConstraint(
            "location_type IN ('room', 'common_area')",
            name="location_type_valid",
        ),
        sa.CheckConstraint("btrim(title) <> ''", name="title_nonempty"),
        sa.CheckConstraint(
            "btrim(description) <> '' AND char_length(description) <= 5000",
            name="description_valid",
        ),
        sa.CheckConstraint(
            "(location_type = 'room' AND room_id IS NOT NULL AND block_id IS NULL "
            "AND location_detail IS NULL) OR "
            "(location_type = 'common_area' AND room_id IS NULL "
            "AND location_detail IS NOT NULL AND btrim(location_detail) <> '')",
            name="location_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="rejection_reason_required",
        ),
        sa.CheckConstraint(
            "rejection_reason IS NULL OR btrim(rejection_reason) <> ''",
            name="rejection_reason_nonempty",
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'closed')) = (completed_at IS NOT NULL)",
            name="completed_at_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)",
            name="closed_at_consistency",
        ),
        sa.CheckConstraint("version >= 1", name="version_pos"),
    )
    op.create_index(
        "ix_complaints_student",
        "complaints",
        ["student_user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_complaints_queue",
        "complaints",
        ["status", "priority", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_complaints_room",
        "complaints",
        ["room_id"],
        unique=False,
        postgresql_where=sa.text("room_id IS NOT NULL"),
    )
    op.create_index(
        "ix_complaints_block",
        "complaints",
        ["block_id"],
        unique=False,
        postgresql_where=sa.text("block_id IS NOT NULL"),
    )

    # 3.9 `complaint_assignments`
    op.create_table(
        "complaint_assignments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("staff_user_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", sa.BigInteger(), nullable=True),
        sa.Column("end_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_complaint_assignments"),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_complaint_assignments_complaint_id_complaints",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_profiles.user_id"],
            name="fk_complaint_assignments_staff_user_id_staff_profiles",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name="fk_complaint_assignments_assigned_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["users.id"],
            name="fk_complaint_assignments_ended_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "accepted_at IS NULL OR accepted_at >= assigned_at",
            name="accepted_after_assigned",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR (accepted_at IS NOT NULL AND started_at >= accepted_at)",
            name="started_after_accepted",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= assigned_at",
            name="ended_after_assigned",
        ),
        sa.CheckConstraint(
            "(ended_at IS NULL) = (ended_by IS NULL)",
            name="ended_by_consistency",
        ),
    )
    op.create_index(
        "uq_assign_one_active",
        "complaint_assignments",
        ["complaint_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "ix_assign_complaint",
        "complaint_assignments",
        ["complaint_id", "assigned_at"],
        unique=False,
    )
    op.create_index(
        "ix_assign_staff_active",
        "complaint_assignments",
        ["staff_user_id"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # 3.10 `complaint_updates`
    op.create_table(
        "complaint_updates",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("assignment_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column("update_type", sa.String(length=12), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaint_updates"),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_complaint_updates_complaint_id_complaints",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["complaint_assignments.id"],
            name="fk_complaint_updates_assignment_id_complaint_assignments",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name="fk_complaint_updates_author_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "update_type IN ('progress', 'completion')",
            name="update_type_valid",
        ),
        sa.CheckConstraint(
            "btrim(body) <> '' AND char_length(body) <= 4000",
            name="body_valid",
        ),
    )
    op.create_index(
        "ix_complaint_updates_complaint_created",
        "complaint_updates",
        ["complaint_id", "created_at"],
        unique=False,
    )

    # 3.11 `complaint_internal_notes`
    op.create_table(
        "complaint_internal_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaint_internal_notes"),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_complaint_internal_notes_complaint_id_complaints",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name="fk_complaint_internal_notes_author_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "btrim(body) <> '' AND char_length(body) <= 4000",
            name="body_valid",
        ),
    )
    op.create_index(
        "ix_complaint_internal_notes_complaint_created",
        "complaint_internal_notes",
        ["complaint_id", "created_at"],
        unique=False,
    )

    # 3.12 `complaint_history`
    op.create_table(
        "complaint_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=12), nullable=True),
        sa.Column("to_status", sa.String(length=12), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("assignment_id", sa.BigInteger(), nullable=True),
        sa.Column("update_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaint_history"),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_complaint_history_complaint_id_complaints",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_complaint_history_actor_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["complaint_assignments.id"],
            name="fk_complaint_history_assignment_id_complaint_assignments",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["update_id"],
            ["complaint_updates.id"],
            name="fk_complaint_history_update_id_complaint_updates",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "action IN ('submitted', 'review_started', 'assigned', 'reassigned', "
            "'accepted', 'work_started', 'progress_updated', 'completed', "
            "'returned_for_rework', 'closed', 'rejected', 'reopened')",
            name="action_valid",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('submitted', 'under_review', "
            "'assigned', 'accepted', 'in_progress', 'completed', 'closed', 'rejected')",
            name="from_status_valid",
        ),
        sa.CheckConstraint(
            "to_status IN ('submitted', 'under_review', 'assigned', 'accepted', "
            "'in_progress', 'completed', 'closed', 'rejected')",
            name="to_status_valid",
        ),
        sa.CheckConstraint(
            "action NOT IN ('returned_for_rework', 'rejected', 'reopened') "
            "OR (note IS NOT NULL AND btrim(note) <> '')",
            name="mandatory_action_note",
        ),
    )
    op.create_index(
        "ix_chist_complaint",
        "complaint_history",
        ["complaint_id", "created_at", "id"],
        unique=False,
    )

    # 3.13 `fines`
    op.create_table(
        "fines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "reference_no",
            sa.String(length=20),
            server_default=sa.text(
                "'FIN-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
                "|| '-' || to_char(nextval('public.fine_ref_seq'), 'FM9999999999999900000')"
            ),
            nullable=False,
        ),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("issued_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=10),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fines"),
        sa.ForeignKeyConstraint(
            ["student_user_id"],
            ["student_profiles.user_id"],
            name="fk_fines_student_user_id_student_profiles",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_fines_room_id_rooms",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"],
            ["users.id"],
            name="fk_fines_issued_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name="fk_fines_resolved_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("reference_no", name="uq_fines_reference_no"),
        sa.CheckConstraint(
            "status IN ('pending', 'disputed', 'paid', 'waived', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("amount_inr > 0", name="amount_pos"),
        sa.CheckConstraint("due_date >= issue_date", name="due_after_issue"),
        sa.CheckConstraint(
            "btrim(description) <> '' AND char_length(description) <= 5000",
            name="description_valid",
        ),
        sa.CheckConstraint(
            "(status = 'paid') = (paid_at IS NOT NULL)",
            name="paid_at_consistency",
        ),
        sa.CheckConstraint(
            "(status IN ('waived', 'cancelled')) = (resolution_reason IS NOT NULL "
            "AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL) "
            "AND (status NOT IN ('waived', 'cancelled')) = (resolution_reason IS NULL "
            "AND resolved_by IS NULL AND resolved_at IS NULL)",
            name="resolution_consistency",
        ),
        sa.CheckConstraint(
            "resolution_reason IS NULL OR btrim(resolution_reason) <> ''",
            name="resolution_reason_nonempty",
        ),
        sa.CheckConstraint("version >= 1", name="version_pos"),
    )
    op.create_index(
        "ix_fines_student",
        "fines",
        ["student_user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index("ix_fines_status_due", "fines", ["status", "due_date"], unique=False)

    # 3.14 `fine_disputes`
    op.create_table(
        "fine_disputes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("fine_id", sa.BigInteger(), nullable=False),
        sa.Column("raised_by", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=10),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fine_disputes"),
        sa.ForeignKeyConstraint(
            ["fine_id"],
            ["fines.id"],
            name="fk_fine_disputes_fine_id_fines",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["raised_by"],
            ["student_profiles.user_id"],
            name="fk_fine_disputes_raised_by_student_profiles",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name="fk_fine_disputes_decided_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("fine_id", name="uq_fine_disputes_fine_id"),
        sa.CheckConstraint(
            "status IN ('open', 'approved', 'rejected')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "btrim(reason) <> '' AND char_length(reason) <= 4000",
            name="reason_valid",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND decided_by IS NULL AND decided_at IS NULL "
            "AND decision_reason IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by IS NOT NULL "
            "AND decided_at IS NOT NULL AND decision_reason IS NOT NULL "
            "AND btrim(decision_reason) <> '')",
            name="decision_consistency",
        ),
    )

    # 3.15 `payment_attempts`
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fine_id", sa.BigInteger(), nullable=False),
        sa.Column("initiated_by", sa.BigInteger(), nullable=False),
        sa.Column("amount_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=True),
        sa.Column("gateway_payment_id", sa.String(length=64), nullable=True),
        sa.Column("payment_method", sa.String(length=20), nullable=True),
        sa.Column(
            "status",
            sa.String(length=18),
            server_default=sa.text("'created'"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=60), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payment_attempts"),
        sa.ForeignKeyConstraint(
            ["fine_id"],
            ["fines.id"],
            name="fk_payment_attempts_fine_id_fines",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by"],
            ["users.id"],
            name="fk_payment_attempts_initiated_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("public_id", name="uq_payment_attempts_public_id"),
        sa.UniqueConstraint("id", "fine_id", name="uq_payment_attempts_id_fine"),
        sa.CheckConstraint(
            "status IN ('created', 'processing', 'succeeded', "
            "'captured_unapplied', 'failed', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("amount_inr > 0", name="amount_pos"),
        sa.CheckConstraint("currency = 'INR'", name="currency_inr"),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi', 'card', 'netbanking', 'wallet', 'other')",
            name="payment_method_valid",
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'captured_unapplied')) = (verified_at IS NOT NULL)",
            name="verified_at_consistency",
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded', 'captured_unapplied') "
            "OR (gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL)",
            name="gateway_ids_on_capture",
        ),
    )
    op.create_index(
        "uq_payment_attempts_gateway_order_id",
        "payment_attempts",
        ["gateway_order_id"],
        unique=True,
        postgresql_where=sa.text("gateway_order_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payment_attempts_gateway_payment_id",
        "payment_attempts",
        ["gateway_payment_id"],
        unique=True,
        postgresql_where=sa.text("gateway_payment_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attempt_one_open",
        "payment_attempts",
        ["fine_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('created', 'processing')"),
    )
    op.create_index(
        "ix_attempts_fine",
        "payment_attempts",
        ["fine_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_attempts_status_open",
        "payment_attempts",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status IN ('created', 'processing')"),
    )

    # 3.16 `payments`
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fine_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("amount_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=True),
        sa.Column("gateway_payment_id", sa.String(length=64), nullable=True),
        sa.Column("payment_method", sa.String(length=20), nullable=True),
        sa.Column("verification_method", sa.String(length=14), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "receipt_number",
            sa.String(length=24),
            server_default=sa.text(
                "'RCP-' || EXTRACT(YEAR FROM (now() AT TIME ZONE 'Asia/Kolkata'))::int::text "
                "|| '-' || to_char(nextval('public.receipt_seq'), 'FM9999999999999900000')"
            ),
            nullable=False,
        ),
        sa.Column("recorded_by", sa.BigInteger(), nullable=True),
        sa.Column("manual_reference", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.ForeignKeyConstraint(
            ["fine_id"],
            ["fines.id"],
            name="fk_payments_fine_id_fines",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id", "fine_id"],
            ["payment_attempts.id", "payment_attempts.fine_id"],
            name="fk_payments_attempt_fine_payment_attempts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["users.id"],
            name="fk_payments_recorded_by_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("public_id", name="uq_payments_public_id"),
        sa.UniqueConstraint("receipt_number", name="uq_payments_receipt_number"),
        sa.UniqueConstraint("fine_id", name="uq_payments_fine"),
        sa.CheckConstraint(
            "channel IN ('razorpay', 'manual')",
            name="channel_valid",
        ),
        sa.CheckConstraint("amount_inr > 0", name="amount_pos"),
        sa.CheckConstraint("currency = 'INR'", name="currency_inr"),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi', 'card', 'netbanking', 'wallet', 'cash', 'bank_transfer', 'other')",
            name="payment_method_valid",
        ),
        sa.CheckConstraint(
            "verification_method IN ('webhook', 'api_fetch', 'manual_entry')",
            name="verification_method_valid",
        ),
        sa.CheckConstraint(
            "channel <> 'razorpay' OR (payment_attempt_id IS NOT NULL "
            "AND gateway_order_id IS NOT NULL AND gateway_payment_id IS NOT NULL "
            "AND verification_method IN ('webhook', 'api_fetch') AND recorded_by IS NULL)",
            name="razorpay_channel_fields",
        ),
        sa.CheckConstraint(
            "channel <> 'manual' OR (payment_attempt_id IS NULL "
            "AND gateway_order_id IS NULL AND gateway_payment_id IS NULL "
            "AND verification_method = 'manual_entry' AND recorded_by IS NOT NULL "
            "AND manual_reference IS NOT NULL AND btrim(manual_reference) <> '')",
            name="manual_channel_fields",
        ),
    )
    op.create_index(
        "uq_payments_attempt",
        "payments",
        ["payment_attempt_id"],
        unique=True,
        postgresql_where=sa.text("payment_attempt_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payments_gateway_payment",
        "payments",
        ["gateway_payment_id"],
        unique=True,
        postgresql_where=sa.text("gateway_payment_id IS NOT NULL"),
    )
    op.create_index("ix_payments_verified_at", "payments", ["verified_at"], unique=False)

    # 3.17 `payment_events`
    op.create_table(
        "payment_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("payment_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("gateway_event_id", sa.String(length=100), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=True),
        sa.Column("outcome", sa.String(length=14), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payment_events"),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
            name="fk_payment_events_payment_attempt_id_payment_attempts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "source IN ('webhook', 'client_callback', 'server_verify', 'system', 'admin')",
            name="source_valid",
        ),
        sa.CheckConstraint(
            "outcome IN ('applied', 'duplicate', 'ignored', 'rejected', 'error', 'needs_review')",
            name="outcome_valid",
        ),
        sa.CheckConstraint(
            "btrim(event_type) <> ''",
            name="event_type_nonempty",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="payload_is_object",
        ),
    )
    op.create_index(
        "uq_payment_events_gateway_event",
        "payment_events",
        ["gateway_event_id"],
        unique=True,
        postgresql_where=sa.text("gateway_event_id IS NOT NULL"),
    )
    op.create_index(
        "ix_payment_events_attempt_created",
        "payment_events",
        ["payment_attempt_id", "created_at"],
        unique=False,
    )

    # 3.18 `fine_history` (depends on fines, users, payments, payment_attempts, fine_disputes)
    op.create_table(
        "fine_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("fine_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=10), nullable=True),
        sa.Column("to_status", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payment_id", sa.BigInteger(), nullable=True),
        sa.Column("payment_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("dispute_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fine_history"),
        sa.ForeignKeyConstraint(
            ["fine_id"],
            ["fines.id"],
            name="fk_fine_history_fine_id_fines",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_fine_history_actor_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_fine_history_payment_id_payments",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
            name="fk_fine_history_payment_attempt_id_payment_attempts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["dispute_id"],
            ["fine_disputes.id"],
            name="fk_fine_history_dispute_id_fine_disputes",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "action IN ('issued', 'dispute_submitted', 'dispute_approved', "
            "'dispute_rejected', 'payment_attempted', 'payment_verified', "
            "'manual_payment_recorded', 'payment_needs_review', 'waived', 'cancelled')",
            name="action_valid",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('pending', 'disputed', 'paid', "
            "'waived', 'cancelled')",
            name="from_status_valid",
        ),
        sa.CheckConstraint(
            "to_status IN ('pending', 'disputed', 'paid', 'waived', 'cancelled')",
            name="to_status_valid",
        ),
        sa.CheckConstraint(
            "action NOT IN ('dispute_approved', 'dispute_rejected', 'waived', 'cancelled') "
            "OR (note IS NOT NULL AND btrim(note) <> '')",
            name="mandatory_action_note",
        ),
    )
    op.create_index(
        "ix_fhist_fine",
        "fine_history",
        ["fine_id", "created_at", "id"],
        unique=False,
    )

    # 3.19 `notifications`
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("recipient_user_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=14), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=True),
        sa.Column("entity_ref", sa.String(length=40), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            name="fk_notifications_recipient_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.UniqueConstraint("public_id", name="uq_notifications_public_id"),
        sa.CheckConstraint(
            "category IN ('complaint', 'fine', 'dispute', 'payment', 'registration', 'system')",
            name="category_valid",
        ),
        sa.CheckConstraint(
            "btrim(event_type) <> ''",
            name="event_type_nonempty",
        ),
        sa.CheckConstraint("btrim(title) <> ''", name="title_nonempty"),
        sa.CheckConstraint(
            "btrim(message) <> '' AND char_length(message) <= 1000",
            name="message_valid",
        ),
        sa.CheckConstraint(
            "(entity_type IS NULL) = (entity_ref IS NULL)",
            name="entity_link_pair",
        ),
        sa.CheckConstraint(
            "entity_type IS NULL OR entity_type IN ('complaint', 'fine', 'payment', 'student')",
            name="entity_type_valid",
        ),
    )
    op.create_index(
        "ix_notif_recipient",
        "notifications",
        ["recipient_user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_notif_unread",
        "notifications",
        ["recipient_user_id"],
        unique=False,
        postgresql_where=sa.text("read_at IS NULL"),
    )

    # 3.20 `audit_logs`
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_role", sa.String(length=10), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=True),
        sa.Column("target_id", sa.String(length=40), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'",
            name="metadata_is_object",
        ),
        sa.CheckConstraint("btrim(action) <> ''", name="action_nonempty"),
        sa.CheckConstraint(
            "(target_type IS NULL) = (target_id IS NULL)",
            name="target_pair",
        ),
    )
    op.create_index(
        "ix_audit_occurred",
        "audit_logs",
        [sa.text("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_actor",
        "audit_logs",
        ["actor_user_id", sa.text("occurred_at DESC")],
        unique=False,
    )
    op.create_index("ix_audit_target", "audit_logs", ["target_type", "target_id"], unique=False)
    op.create_index(
        "ix_audit_action_ip",
        "audit_logs",
        ["action", "ip_address", sa.text("occurred_at DESC")],
        unique=False,
        postgresql_where=sa.text("ip_address IS NOT NULL"),
    )

    # -------------------------------------------------------------------------
    # 4. PostgreSQL Functions and Constraint Triggers (T1a, T1b, T2a, T2b, T3)
    #    & Scoped Cleanup Function (`purge_expired_password_reset_tokens`)
    # -------------------------------------------------------------------------

    # 4.1 Trigger Function T1a: `fn_check_room_allocation` (SECURITY INVOKER)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_check_room_allocation()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_capacity smallint;
            v_is_active boolean;
            v_student_status varchar(12);
        BEGIN
            SELECT capacity, is_active
              INTO v_capacity, v_is_active
              FROM public.rooms
             WHERE id = NEW.room_id
               FOR SHARE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Room % does not exist', NEW.room_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;

            IF NEW.bed_number > v_capacity THEN
                RAISE EXCEPTION 'bed_number (%) exceeds room capacity (%) for room %',
                    NEW.bed_number, v_capacity, NEW.room_id
                    USING ERRCODE = 'check_violation';
            END IF;

            IF TG_OP = 'INSERT' THEN
                IF NOT v_is_active THEN
                    RAISE EXCEPTION 'Cannot allocate bed in inactive room %', NEW.room_id
                        USING ERRCODE = 'check_violation';
                END IF;

                SELECT status
                  INTO v_student_status
                  FROM public.users
                 WHERE id = NEW.student_user_id;

                IF v_student_status IS DISTINCT FROM 'active' THEN
                    RAISE EXCEPTION 'Cannot allocate room to non-active student % (status: %)',
                        NEW.student_user_id, v_student_status
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(f"ALTER FUNCTION public.fn_check_room_allocation() OWNER TO {owner_role}")
    op.execute("REVOKE ALL ON FUNCTION public.fn_check_room_allocation() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_room_allocations_check_capacity
        BEFORE INSERT OR UPDATE OF room_id, bed_number, start_date, end_date
        ON public.room_allocations
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_room_allocation();
        """
    )

    # 4.2 Trigger Function T1b: `fn_check_room_capacity_reduction` (SECURITY INVOKER)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_check_room_capacity_reduction()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_max_bed smallint;
        BEGIN
            IF NEW.capacity < OLD.capacity THEN
                SELECT max(bed_number)
                  INTO v_max_bed
                  FROM public.room_allocations
                 WHERE room_id = NEW.id
                   AND (
                       end_date IS NULL
                       OR end_date > (now() AT TIME ZONE 'Asia/Kolkata')::date
                   );

                IF v_max_bed IS NOT NULL AND NEW.capacity < v_max_bed THEN
                    RAISE EXCEPTION 'Cannot reduce room % capacity to % below active/future bed_number %',
                        NEW.id, NEW.capacity, v_max_bed
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(
            f"ALTER FUNCTION public.fn_check_room_capacity_reduction() OWNER TO {owner_role}"
        )
    op.execute("REVOKE ALL ON FUNCTION public.fn_check_room_capacity_reduction() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_rooms_check_capacity_reduction
        BEFORE UPDATE OF capacity
        ON public.rooms
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_room_capacity_reduction();
        """
    )

    # 4.3 Trigger Function T2a: `fn_check_fine_paid_has_payment` (SECURITY INVOKER, DEFERRED)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_check_fine_paid_has_payment()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_status varchar(10);
        BEGIN
            SELECT status INTO v_status FROM public.fines WHERE id = NEW.id;
            IF v_status = 'paid' THEN
                IF NOT EXISTS (SELECT 1 FROM public.payments WHERE fine_id = NEW.id) THEN
                    RAISE EXCEPTION 'Fine % cannot be marked paid without a verified payment record',
                        NEW.id
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(f"ALTER FUNCTION public.fn_check_fine_paid_has_payment() OWNER TO {owner_role}")
    op.execute("REVOKE ALL ON FUNCTION public.fn_check_fine_paid_has_payment() FROM PUBLIC")
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_fines_paid_requires_payment
        AFTER INSERT OR UPDATE OF status
        ON public.fines
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_fine_paid_has_payment();
        """
    )

    # 4.4 Trigger Function T2b: `fn_check_payment_fine_state` (SECURITY INVOKER, DEFERRED)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_check_payment_fine_state()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_fine_status varchar(10);
            v_attempt_status varchar(18);
        BEGIN
            SELECT status INTO v_fine_status FROM public.fines WHERE id = NEW.fine_id;
            IF v_fine_status IS DISTINCT FROM 'paid' THEN
                RAISE EXCEPTION 'Verified payment for fine % requires fine status to be paid (found %)',
                    NEW.fine_id, v_fine_status
                    USING ERRCODE = 'check_violation';
            END IF;

            IF NEW.payment_attempt_id IS NOT NULL THEN
                SELECT status
                  INTO v_attempt_status
                  FROM public.payment_attempts
                 WHERE id = NEW.payment_attempt_id;
                IF v_attempt_status IS DISTINCT FROM 'succeeded' THEN
                    RAISE EXCEPTION 'Verified payment linked to attempt % requires attempt status to be succeeded (found %)',
                        NEW.payment_attempt_id, v_attempt_status
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(f"ALTER FUNCTION public.fn_check_payment_fine_state() OWNER TO {owner_role}")
    op.execute("REVOKE ALL ON FUNCTION public.fn_check_payment_fine_state() FROM PUBLIC")
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_payments_requires_paid_fine
        AFTER INSERT
        ON public.payments
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_payment_fine_state();
        """
    )

    # 4.5 Trigger Function T3: `fn_check_payment_amount_matches_fine` (SECURITY INVOKER)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_check_payment_amount_matches_fine()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_fine_amount numeric(12, 2);
        BEGIN
            SELECT amount_inr
              INTO v_fine_amount
              FROM public.fines
             WHERE id = NEW.fine_id
               FOR SHARE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Fine % does not exist', NEW.fine_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;

            IF NEW.amount_inr <> v_fine_amount THEN
                RAISE EXCEPTION 'Payment amount (%) must equal exact fine amount (%) for fine %',
                    NEW.amount_inr, v_fine_amount, NEW.fine_id
                    USING ERRCODE = 'check_violation';
            END IF;

            IF NEW.currency <> 'INR' THEN
                RAISE EXCEPTION 'Payment currency (%) must be INR', NEW.currency
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(
            f"ALTER FUNCTION public.fn_check_payment_amount_matches_fine() OWNER TO {owner_role}"
        )
    op.execute(
        "REVOKE ALL ON FUNCTION public.fn_check_payment_amount_matches_fine() FROM PUBLIC"
    )
    op.execute(
        """
        CREATE TRIGGER trg_payment_attempts_check_amount
        BEFORE INSERT
        ON public.payment_attempts
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_payment_amount_matches_fine();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payments_check_amount
        BEFORE INSERT
        ON public.payments
        FOR EACH ROW
        EXECUTE FUNCTION public.fn_check_payment_amount_matches_fine();
        """
    )

    # 4.6 Scoped Cleanup Function: `purge_expired_password_reset_tokens` (SECURITY DEFINER)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.purge_expired_password_reset_tokens()
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            deleted_count integer;
        BEGIN
            DELETE FROM public.password_reset_tokens
             WHERE expires_at < now() - interval '24 hours'
               AND created_at < now() - interval '24 hours';
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$;
        """
    )
    if has_owner_role:
        op.execute(
            f"ALTER FUNCTION public.purge_expired_password_reset_tokens() OWNER TO {owner_role}"
        )
    op.execute(
        "REVOKE ALL ON FUNCTION public.purge_expired_password_reset_tokens() FROM PUBLIC"
    )
    if has_app_role:
        op.execute(
            f"GRANT EXECUTE ON FUNCTION public.purge_expired_password_reset_tokens() TO {app_role}"
        )

    # -------------------------------------------------------------------------
    # 5. Exact Least-Privilege Table and Column Grants for `hostelcare_app`
    #    (Zero DELETE privileges across all 20 tables)
    # -------------------------------------------------------------------------
    all_tables = (
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
    )
    for tbl in all_tables:
        op.execute(f"REVOKE ALL ON TABLE public.{tbl} FROM PUBLIC")
        if has_app_role:
            op.execute(f"REVOKE ALL ON TABLE public.{tbl} FROM {app_role}")
            op.execute(f"GRANT SELECT, INSERT ON TABLE public.{tbl} TO {app_role}")

    mutable_column_grants: dict[str, tuple[str, ...]] = {
        "users": (
            "email",
            "full_name",
            "phone",
            "designation",
            "password_hash",
            "status",
            "password_changed_at",
            "session_version",
            "failed_login_count",
            "locked_until",
            "last_login_at",
            "updated_at",
        ),
        "student_profiles": (
            "roll_number",
            "requested_room_id",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "updated_at",
        ),
        "staff_profiles": (
            "trade",
            "shift",
            "updated_at",
        ),
        "password_reset_tokens": (
            "used_at",
            "revoked_at",
        ),
        "blocks": (
            "name",
            "display_order",
            "is_active",
            "updated_at",
        ),
        "rooms": (
            "floor",
            "room_type",
            "capacity",
            "is_active",
            "updated_at",
        ),
        "room_allocations": (
            "end_date",
            "ended_by",
            "end_reason",
        ),
        "complaints": (
            "category",
            "priority",
            "status",
            "rejection_reason",
            "completed_at",
            "closed_at",
            "version",
            "updated_at",
        ),
        "complaint_assignments": (
            "accepted_at",
            "started_at",
            "ended_at",
            "ended_by",
            "end_note",
        ),
        "fines": (
            "status",
            "paid_at",
            "resolved_by",
            "resolved_at",
            "resolution_reason",
            "version",
            "updated_at",
        ),
        "fine_disputes": (
            "status",
            "decided_by",
            "decided_at",
            "decision_reason",
        ),
        "payment_attempts": (
            "gateway_order_id",
            "gateway_payment_id",
            "payment_method",
            "status",
            "verified_at",
            "failure_code",
            "failure_reason",
            "updated_at",
        ),
        "notifications": ("read_at",),
    }

    if has_app_role:
        for tbl, cols in mutable_column_grants.items():
            col_list = ", ".join(cols)
            op.execute(f"GRANT UPDATE ({col_list}) ON TABLE public.{tbl} TO {app_role}")


def downgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Drop Triggers
    # -------------------------------------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS trg_payments_check_amount ON public.payments")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_payment_attempts_check_amount ON public.payment_attempts"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_payments_requires_paid_fine ON public.payments")
    op.execute("DROP TRIGGER IF EXISTS trg_fines_paid_requires_payment ON public.fines")
    op.execute("DROP TRIGGER IF EXISTS trg_rooms_check_capacity_reduction ON public.rooms")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_room_allocations_check_capacity ON public.room_allocations"
    )

    # -------------------------------------------------------------------------
    # 2. Drop Functions
    # -------------------------------------------------------------------------
    op.execute("DROP FUNCTION IF EXISTS public.purge_expired_password_reset_tokens()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_check_payment_amount_matches_fine()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_check_payment_fine_state()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_check_fine_paid_has_payment()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_check_room_capacity_reduction()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_check_room_allocation()")

    # -------------------------------------------------------------------------
    # 3. Drop Tables in Reverse Foreign-Key Dependency Order
    # -------------------------------------------------------------------------
    reverse_tables = (
        "audit_logs",
        "notifications",
        "fine_history",
        "payment_events",
        "payments",
        "payment_attempts",
        "fine_disputes",
        "fines",
        "complaint_history",
        "complaint_internal_notes",
        "complaint_updates",
        "complaint_assignments",
        "complaints",
        "room_allocations",
        "password_reset_tokens",
        "staff_profiles",
        "student_profiles",
        "rooms",
        "blocks",
        "users",
    )
    for tbl in reverse_tables:
        op.drop_table(tbl)

    # -------------------------------------------------------------------------
    # 4. Drop Sequences
    # -------------------------------------------------------------------------
    for seq_name in ("receipt_seq", "fine_ref_seq", "complaint_ref_seq"):
        op.execute(f"DROP SEQUENCE IF EXISTS public.{seq_name}")

    # -------------------------------------------------------------------------
    # 5. Drop Extension
    # -------------------------------------------------------------------------
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
