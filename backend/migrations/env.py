"""Alembic migration environment configured for HostelCare's migration role (`hostelcare_owner`).

Migrations always connect via `MIGRATION_DATABASE_URI` (`hostelcare_owner`) and never via
the restricted runtime `SQLALCHEMY_DATABASE_URI` (`hostelcare_app`). After migrations run,
all privileges on `public.alembic_version` are explicitly revoked from `PUBLIC` and
`hostelcare_app`.
"""

from __future__ import annotations

import logging
import os
import re
from logging.config import fileConfig

from alembic import context
from flask import current_app
from sqlalchemy import create_engine, text

_SAFE_PG_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _safe_role_name(env_key: str, default: str) -> str:
    val = os.environ.get(env_key, default).strip() or default
    if not _SAFE_PG_IDENT.match(val):
        raise RuntimeError(f"Invalid PostgreSQL identifier in {env_key}: {val!r}")
    return val

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_migration_url() -> str:
    """Return MIGRATION_DATABASE_URI; refuse to fall back to the runtime role connection."""
    migration_uri = current_app.config.get("MIGRATION_DATABASE_URI")
    if not migration_uri:
        raise RuntimeError(
            "MIGRATION_DATABASE_URI is not configured. Migrations must run as hostelcare_owner."
        )
    return str(migration_uri)


def get_metadata():
    migrate_ext = current_app.extensions["migrate"]
    if hasattr(migrate_ext.db, "metadatas"):
        return migrate_ext.db.metadatas[None]
    return migrate_ext.db.metadata


target_metadata = get_metadata()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_migration_url().replace("%", "%%")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using `MIGRATION_DATABASE_URI` (`DB_MIGRATION_ROLE`)."""
    migration_url = get_migration_url()
    migration_role = _safe_role_name("DB_MIGRATION_ROLE", "hostelcare_owner")
    app_role = _safe_role_name("DB_APP_ROLE", "hostelcare_app")
    connectable = create_engine(migration_url, pool_pre_ping=True)

    with connectable.connect() as connection:
        current_role = connection.execute(text("SELECT current_user")).scalar()
        if current_role != migration_role:
            raise RuntimeError(
                f"Migrations must run as '{migration_role}', but connected as '{current_role}'."
            )

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
            # Ensure alembic_version is strictly inaccessible to PUBLIC and runtime app role
            has_alembic_table = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar()
            if has_alembic_table:
                connection.execute(text("REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC"))
                has_app_role = (
                    connection.execute(
                        text("SELECT 1 FROM pg_roles WHERE rolname = :role_name"),
                        {"role_name": app_role},
                    ).scalar()
                    is not None
                )
                if has_app_role:
                    connection.execute(
                        text(f"REVOKE ALL ON TABLE public.alembic_version FROM {app_role}")
                    )
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
