"""Add `complaint_attachments` table for private student complaint photo metadata.

Revision ID: 0002_complaint_attachments
Revises: 0001_initial_schema
Create Date: 2026-11-17 04:01:00+05:30
"""

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

_SAFE_PG_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _app_role() -> str:
    val = os.environ.get("DB_APP_ROLE", "hostelcare_app").strip() or "hostelcare_app"
    if not _SAFE_PG_IDENT.match(val):
        raise RuntimeError(f"Invalid DB_APP_ROLE identifier: {val!r}")
    return val

revision = "0002_complaint_attachments"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "complaint_attachments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaint_attachments"),
        sa.UniqueConstraint("public_id", name="uq_complaint_attachments_public_id"),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_complaint_attachments_complaint_id_complaints",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 5242880",
            name="file_size_valid",
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="mime_type_valid",
        ),
        sa.CheckConstraint("btrim(storage_path) <> ''", name="storage_path_nonempty"),
        sa.CheckConstraint("btrim(original_filename) <> ''", name="original_filename_nonempty"),
        sa.CheckConstraint(
            "char_length(checksum_sha256) = 64 AND checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
    )
    op.create_index(
        "ix_cattach_complaint_created",
        "complaint_attachments",
        ["complaint_id", "created_at", "id"],
        unique=False,
    )

    op.execute("REVOKE ALL ON TABLE public.complaint_attachments FROM PUBLIC")
    app_role = _app_role()
    has_app_role = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": app_role})
        .scalar()
        is not None
    )
    if has_app_role:
        op.execute(f"REVOKE ALL ON TABLE public.complaint_attachments FROM {app_role}")
        op.execute(f"GRANT SELECT, INSERT ON TABLE public.complaint_attachments TO {app_role}")


def downgrade() -> None:
    op.drop_index("ix_cattach_complaint_created", table_name="complaint_attachments")
    op.drop_table("complaint_attachments")
