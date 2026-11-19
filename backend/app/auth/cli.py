"""CLI commands for administrator provisioning and expired reset-token cleanup."""

from __future__ import annotations

import getpass

import click
from flask.cli import with_appcontext
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.audit.service import record_audit_event
from app.auth.security import (
    UNUSABLE_PASSWORD_MARKER,
    hash_password,
    normalize_and_validate_email,
    validate_password_policy,
)
from app.extensions import db
from app.models.identity import User


@click.command("create-admin")
@click.option("--email", required=True, help="Administrator email address.")
@click.option(
    "--name",
    "--full-name",
    "full_name",
    required=True,
    help="Administrator full name.",
)
@click.option("--designation", default="Chief Hostel Warden", help="Display designation.")
@click.option(
    "--password",
    default=None,
    help="Optional initial password (if omitted, prompts interactively using getpass).",
)
@click.option(
    "--no-password",
    is_flag=True,
    default=False,
    help="Skip password prompt and use email-based setup flow (sets unusable password marker).",
)
@with_appcontext
def create_admin_cmd(
    email: str,
    full_name: str,
    designation: str,
    password: str | None,
    no_password: bool = False,
) -> None:
    """Create the initial active administrator account with secure interactive password setup."""
    cleaned_name = full_name.strip() if full_name else ""
    if not cleaned_name:
        raise click.ClickException("Administrator name is required.")

    norm_email, err = normalize_and_validate_email(email)
    if err or not norm_email:
        raise click.ClickException(err or "Invalid email address.")

    # 1. Enforce single initial administrator safeguard
    existing_admin = db.session.execute(select(User).where(User.role == "admin")).scalars().first()
    if existing_admin is not None:
        raise click.ClickException(
            f"An administrator account already exists ({existing_admin.email})."
        )

    # 2. Check for duplicate account by email
    existing_user = db.session.execute(
        select(User).where(User.email == norm_email)
    ).scalar_one_or_none()
    if existing_user is not None:
        raise click.ClickException(f"Account with email '{norm_email}' already exists.")

    # 3. Secure interactive or supplied password setup
    if no_password:
        pw_hash = UNUSABLE_PASSWORD_MARKER
    elif password is not None:
        if not password:
            pw_hash = UNUSABLE_PASSWORD_MARKER
        else:
            pw_err = validate_password_policy(password, require_confirmation=False)
            if pw_err:
                raise click.ClickException(pw_err)
            pw_hash = hash_password(password)
    else:
        try:
            raw_password = getpass.getpass("Password: ")
        except (EOFError, KeyboardInterrupt):
            raw_password = ""

        if not raw_password:
            pw_hash = UNUSABLE_PASSWORD_MARKER
        else:
            try:
                confirm_password = getpass.getpass("Confirm password: ")
            except (EOFError, KeyboardInterrupt):
                confirm_password = ""

            pw_err = validate_password_policy(
                raw_password,
                confirm_password,
                require_confirmation=True,
            )
            if pw_err:
                raise click.ClickException(pw_err)
            pw_hash = hash_password(raw_password)

    # 4. Atomic database transaction to persist the administrator and audit log
    try:
        admin = User(
            email=norm_email,
            full_name=cleaned_name,
            designation=designation.strip() or None,
            password_hash=pw_hash,
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.flush()

        record_audit_event(
            action="admin.created_cli",
            actor=admin,
            target_type="user",
            target_id=str(admin.public_id),
            metadata={"designation": admin.designation},
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise click.ClickException(f"Account with email '{norm_email}' already exists.") from None
    except Exception:
        db.session.rollback()
        raise

    click.echo(f"Created admin account: {admin.email} (public_id={admin.public_id})")


@click.command("purge-reset-tokens")
@with_appcontext
def purge_reset_tokens_cmd() -> None:
    """Purge password reset tokens expired for more than 24 hours via SECURITY DEFINER function."""
    deleted = db.session.execute(
        text("SELECT public.purge_expired_password_reset_tokens()")
    ).scalar_one()
    db.session.commit()
    click.echo(f"Purged {deleted} expired password reset token(s).")
