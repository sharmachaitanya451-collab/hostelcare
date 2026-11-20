"""CLI utility to safely migrate local complaint photo attachments to Cloudflare R2.

Dry-run mode is the default:
    flask --app wsgi migrate-attachments-r2

Apply mode requires an explicit `--apply` flag and owner database privileges:
    flask --app wsgi migrate-attachments-r2 --apply
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import create_engine, text

from app.auth.service import AuthServiceError
from app.complaints.attachment_service import _FORMAT_SPEC, _detect_magic_format
from app.complaints.storage import (
    LocalAttachmentStorage,
    R2AttachmentStorage,
    build_r2_object_key,
    build_r2_storage_ref,
    extract_r2_key,
    get_local_storage,
    get_r2_storage,
    is_r2_storage_ref,
)


class AttachmentMigrationError(RuntimeError):
    """Raised when source validation, R2 verification, or DB update fails safely."""


@dataclass(frozen=True, slots=True)
class PlannedAttachmentAction:
    """Validated plan for one `complaint_attachments` record."""

    attachment_id: int
    public_id: str
    complaint_id: int
    original_filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str
    current_storage_path: str
    target_storage_path: str
    target_r2_key: str
    status: str
    payload: bytes | None = None


@dataclass(frozen=True, slots=True)
class AttachmentMigrationResult:
    """Structured outcome returned by dry-run or apply execution."""

    mode: str
    total_records: int
    migrated_count: int
    reused_count: int
    already_on_r2_count: int
    planned_count: int
    items: list[PlannedAttachmentAction]


def _resolve_migration_db_uri(explicit_uri: str | None = None) -> str:
    if explicit_uri:
        return explicit_uri
    mig_uri = current_app.config.get("MIGRATION_DATABASE_URI")
    app_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    uri = mig_uri or app_uri
    if not uri:
        raise AttachmentMigrationError(
            "Database URI is not configured (set MIGRATION_DATABASE_URL or DATABASE_URL)."
        )
    return str(uri)


def _validate_local_binary(
    att_id: int,
    public_id: str,
    rel_path: str,
    expected_size: int,
    expected_sha256: str,
    expected_mime: str,
    local_storage: LocalAttachmentStorage,
) -> bytes:
    try:
        local_path = local_storage.resolve_path(rel_path)
        data = local_path.read_bytes()
    except (AuthServiceError, OSError) as exc:
        raise AttachmentMigrationError(
            f"Attachment id={att_id} (public_id={public_id}): source file for "
            f"storage_path={rel_path!r} is missing or unreadable."
        ) from exc

    if len(data) != expected_size:
        raise AttachmentMigrationError(
            f"Attachment id={att_id} (public_id={public_id}): local file size {len(data)} "
            f"does not match recorded file_size_bytes={expected_size}."
        )

    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        raise AttachmentMigrationError(
            f"Attachment id={att_id} (public_id={public_id}): local file SHA-256 mismatch."
        )

    magic_fmt = _detect_magic_format(data)
    detected_mime = _FORMAT_SPEC[magic_fmt][0] if magic_fmt in _FORMAT_SPEC else None
    if detected_mime != expected_mime:
        raise AttachmentMigrationError(
            f"Attachment id={att_id} (public_id={public_id}): detected image format "
            f"{detected_mime!r} does not match recorded mime_type={expected_mime!r}."
        )
    return data


def run_historical_attachment_migration(
    *,
    apply: bool = False,
    r2_storage: R2AttachmentStorage | None = None,
    local_storage: LocalAttachmentStorage | None = None,
    db_uri: str | None = None,
) -> AttachmentMigrationResult:
    """Inspect all attachment rows and optionally migrate local binaries to Cloudflare R2."""
    uri = _resolve_migration_db_uri(db_uri)
    local_backend = local_storage or get_local_storage()
    r2_backend: R2AttachmentStorage | None = None
    if apply:
        try:
            r2_backend = r2_storage or get_r2_storage()
        except AuthServiceError as exc:
            raise AttachmentMigrationError(exc.message) from exc

    engine = create_engine(uri, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id,
                           public_id::text AS public_id,
                           complaint_id,
                           storage_path,
                           original_filename,
                           file_size_bytes,
                           mime_type,
                           checksum_sha256
                    FROM public.complaint_attachments
                    ORDER BY id ASC
                    """
                )
            ).fetchall()
            conn.rollback()

        planned: list[PlannedAttachmentAction] = []
        for row in rows:
            att_id = int(row.id)
            pub_id = str(row.public_id)
            cur_path = str(row.storage_path)

            if is_r2_storage_ref(cur_path):
                key = extract_r2_key(cur_path)
                planned.append(
                    PlannedAttachmentAction(
                        attachment_id=att_id,
                        public_id=pub_id,
                        complaint_id=int(row.complaint_id),
                        original_filename=str(row.original_filename),
                        mime_type=str(row.mime_type),
                        file_size_bytes=int(row.file_size_bytes),
                        checksum_sha256=str(row.checksum_sha256),
                        current_storage_path=cur_path,
                        target_storage_path=cur_path,
                        target_r2_key=key,
                        status="already_on_r2",
                        payload=None,
                    )
                )
                continue

            data = _validate_local_binary(
                att_id,
                pub_id,
                cur_path,
                int(row.file_size_bytes),
                str(row.checksum_sha256),
                str(row.mime_type),
                local_backend,
            )
            r2_key = build_r2_object_key(cur_path)
            r2_ref = build_r2_storage_ref(r2_key)
            planned.append(
                PlannedAttachmentAction(
                    attachment_id=att_id,
                    public_id=pub_id,
                    complaint_id=int(row.complaint_id),
                    original_filename=str(row.original_filename),
                    mime_type=str(row.mime_type),
                    file_size_bytes=int(row.file_size_bytes),
                    checksum_sha256=str(row.checksum_sha256),
                    current_storage_path=cur_path,
                    target_storage_path=r2_ref,
                    target_r2_key=r2_key,
                    status="pending_upload",
                    payload=data if apply else None,
                )
            )

        if not apply:
            already_cnt = sum(1 for item in planned if item.status == "already_on_r2")
            planned_cnt = sum(1 for item in planned if item.status == "pending_upload")
            return AttachmentMigrationResult(
                mode="dry-run",
                total_records=len(planned),
                migrated_count=0,
                reused_count=0,
                already_on_r2_count=already_cnt,
                planned_count=planned_cnt,
                items=planned,
            )

        if r2_backend is None:
            raise AttachmentMigrationError("R2 storage backend is not configured.")
        final_items: list[PlannedAttachmentAction] = []
        pending_db_updates: list[tuple[int, str, str]] = []
        migrated_cnt = 0
        reused_cnt = 0
        already_cnt = 0

        for item in planned:
            if item.status == "already_on_r2":
                try:
                    head_meta = r2_backend.head(item.target_storage_path)
                except AuthServiceError as exc:
                    raise AttachmentMigrationError(
                        f"Attachment id={item.attachment_id}: "
                        f"R2 verification failed ({exc.message})"
                    ) from exc
                if head_meta is None or head_meta.size_bytes != item.file_size_bytes:
                    raise AttachmentMigrationError(
                        f"Attachment id={item.attachment_id}: existing R2 object "
                        f"{item.target_storage_path!r} is missing or has mismatched size."
                    )
                already_cnt += 1
                final_items.append(replace(item, status="already_on_r2_verified"))
                continue

            if item.payload is None:
                raise AttachmentMigrationError(
                    f"Attachment id={item.attachment_id}: binary payload missing."
                )
            try:
                existing = r2_backend.head(item.target_storage_path)
            except AuthServiceError as exc:
                raise AttachmentMigrationError(
                    f"Attachment id={item.attachment_id}: R2 pre-check failed ({exc.message})"
                ) from exc

            if existing is not None:
                if existing.size_bytes != item.file_size_bytes or (
                    existing.sha256 is not None and existing.sha256 != item.checksum_sha256
                ):
                    raise AttachmentMigrationError(
                        f"Attachment id={item.attachment_id}: target R2 object "
                        f"{item.target_storage_path!r} already exists with mismatch."
                    )
                reused_cnt += 1
                action_status = "reused_existing_r2"
            else:
                try:
                    saved_ref = r2_backend.save(
                        item.current_storage_path,
                        item.payload,
                        content_type=item.mime_type,
                        checksum_sha256=item.checksum_sha256,
                    )
                    verified = r2_backend.head(saved_ref)
                except AuthServiceError as exc:
                    raise AttachmentMigrationError(
                        f"Attachment id={item.attachment_id}: R2 upload failed ({exc.message})"
                    ) from exc

                if verified is None or verified.size_bytes != item.file_size_bytes:
                    raise AttachmentMigrationError(
                        f"Attachment id={item.attachment_id}: "
                        "uploaded R2 object verification failed."
                    )
                migrated_cnt += 1
                action_status = "uploaded_to_r2"

            pending_db_updates.append(
                (item.attachment_id, item.current_storage_path, item.target_storage_path)
            )
            final_items.append(replace(item, status=action_status, payload=None))

        if pending_db_updates:
            with engine.begin() as tx:
                for att_id, old_ref, new_ref in pending_db_updates:
                    res = tx.execute(
                        text(
                            """
                            UPDATE public.complaint_attachments
                            SET storage_path = :new_ref
                            WHERE id = :att_id AND storage_path = :old_ref
                            """
                        ),
                        {"att_id": att_id, "old_ref": old_ref, "new_ref": new_ref},
                    )
                    if res.rowcount != 1:
                        raise AttachmentMigrationError(
                            f"Attachment id={att_id}: database storage_path changed concurrently."
                        )

        return AttachmentMigrationResult(
            mode="apply",
            total_records=len(final_items),
            migrated_count=migrated_cnt,
            reused_count=reused_cnt,
            already_on_r2_count=already_cnt,
            planned_count=0,
            items=final_items,
        )
    finally:
        engine.dispose()


@click.command("migrate-attachments-r2")
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Upload validated local binaries to R2 and update complaint_attachments.storage_path.",
)
@with_appcontext
def migrate_attachments_r2_cmd(apply: bool) -> None:
    """Inspect or migrate historical local complaint attachments to private Cloudflare R2."""
    try:
        result = run_historical_attachment_migration(apply=apply)
    except AttachmentMigrationError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"--- Complaint Attachment R2 Migration ({result.mode}) ---")
    click.echo(f"Total records inspected: {result.total_records}")
    for item in result.items:
        click.echo(
            f"  [id={item.attachment_id} complaint_id={item.complaint_id}] "
            f"{item.original_filename} ({item.file_size_bytes} B, {item.mime_type}) | "
            f"{item.current_storage_path} -> {item.target_storage_path} [{item.status}]"
        )
    if result.mode == "dry-run":
        click.echo(
            f"Dry-run complete: {result.planned_count} ready to upload, "
            f"{result.already_on_r2_count} already on R2. No uploads or DB writes executed."
        )
    else:
        click.echo(
            f"Apply complete: uploaded={result.migrated_count}, "
            f"reused_existing={result.reused_count}, "
            f"already_on_r2={result.already_on_r2_count}."
        )
