"""CLI commands for database management and verification."""

import sys
from urllib.parse import urlparse

import click
from flask import current_app
from flask.cli import AppGroup
from sqlalchemy import create_engine, text

db_cli = AppGroup("db-verify", help="Database connectivity verification commands.")


def _mask_url(url: str | None) -> str:
    if not url:
        return "<not set>"
    try:
        parsed = urlparse(url)
        # e.g., postgresql+psycopg://hostelcare_app@localhost:5432/hostelcare
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{parsed.username}@{parsed.hostname}{port}{parsed.path}"
    except Exception:
        return "<malformed url>"


def verify_connection(url: str | None, role_name: str, check_ddl: bool = False) -> tuple[bool, str]:
    if not url:
        return False, "URL not configured"
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            # 1. Basic query & session user check
            result = conn.execute(text("SELECT current_user, current_database()")).fetchone()
            current_user, current_db = result[0], result[1]
            if current_user != role_name:
                return (
                    False,
                    f"Connected as unexpected user '{current_user}' (expected '{role_name}')",
                )

            # 2. Check DDL permissions
            if check_ddl:
                # Expect DDL to SUCCEED
                try:
                    conn.execute(
                        text("CREATE TABLE _hc_ddl_test (id int); DROP TABLE _hc_ddl_test;")
                    )
                    conn.commit()
                except Exception as e:
                    return False, f"DDL test failed: {e}"
            else:
                # Expect DDL to FAIL for runtime role
                ddl_blocked = False
                try:
                    conn.execute(text("CREATE TABLE _hc_ddl_forbidden (id int);"))
                    conn.commit()
                except Exception:
                    ddl_blocked = True
                    conn.rollback()

                if not ddl_blocked:
                    # Clean up if it unexpectedly succeeded
                    conn.execute(text("DROP TABLE IF EXISTS _hc_ddl_forbidden;"))
                    conn.commit()
                    return False, "Security check failed: Runtime role was able to create tables!"

            return True, f"OK (connected as {current_user} to {current_db})"
    except Exception as e:
        return False, f"Connection failed: {e.__class__.__name__}: {e}"


@db_cli.command("check")
def check_databases():
    """Verify runtime and migration database connections without exposing credentials."""
    app_url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    mig_url = current_app.config.get("MIGRATION_DATABASE_URI")

    click.echo("--- HostelCare Database Connectivity Verification ---")
    click.echo(f"Runtime target:   {_mask_url(app_url)}")
    click.echo(f"Migration target: {_mask_url(mig_url)}")
    click.echo()

    # 1. Check runtime role on main database
    click.echo("Testing runtime role (hostelcare_app)... ", nl=False)
    ok, msg = verify_connection(app_url, "hostelcare_app", check_ddl=False)
    if ok:
        click.secho(msg, fg="green")
    else:
        click.secho(msg, fg="red")

    # 2. Check migration role on main database
    click.echo("Testing migration role (hostelcare_owner)... ", nl=False)
    ok_mig, msg_mig = verify_connection(mig_url, "hostelcare_owner", check_ddl=True)
    if ok_mig:
        click.secho(msg_mig, fg="green")
    else:
        click.secho(msg_mig, fg="red")

    if not (ok and ok_mig):
        sys.exit(1)
