"""Storage abstraction for private student complaint photo attachments.

Supports:
- `local`: Private filesystem storage (`YYYY/MM/<uuid>.<ext>` under `COMPLAINT_ATTACHMENT_DIR`)
- `r2`: Private Cloudflare R2 storage via `boto3` (`r2://complaints/YYYY/MM/<uuid>.<ext>`)

Storage backend selection on write is governed by `COMPLAINT_ATTACHMENT_STORAGE_BACKEND`.
Storage backend resolution on read/delete dispatches strictly by stored reference convention:
- `r2://<object_key>` -> Cloudflare R2
- relative paths without `r2://` -> Local filesystem (preserves historical local records)
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app

from app.auth.service import AuthServiceError

R2_STORAGE_PREFIX = "r2://"
R2_KEY_PREFIX = "complaints/"
SUPPORTED_STORAGE_BACKENDS = ("local", "r2")

_SAFE_OBJECT_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9/_\.\-]{0,480}$")
_NOT_FOUND_ERROR_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


@dataclass(frozen=True, slots=True)
class StoredObjectMeta:
    """Authoritative metadata returned from a storage head/stat check."""

    storage_ref: str
    size_bytes: int
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievedAttachment:
    """Loaded attachment payload from either local filesystem or object storage."""

    file_path: Path | None = None
    data: bytes | None = None
    content_type: str | None = None


class AttachmentStorageBackend(Protocol):
    """Protocol implemented by every complaint attachment storage backend."""

    def save(
        self,
        rel_key: str,
        data: bytes,
        *,
        content_type: str,
        checksum_sha256: str,
    ) -> str:
        """Persist validated image bytes and return the database `storage_path` reference."""

    def retrieve(self, storage_ref: str) -> RetrievedAttachment:
        """Retrieve an existing attachment or raise `AuthServiceError` if unavailable."""

    def exists(self, storage_ref: str) -> bool:
        """Return True if the backing file/object exists."""

    def head(self, storage_ref: str) -> StoredObjectMeta | None:
        """Return stored object size/metadata or None if missing."""

    def delete(self, storage_ref: str) -> None:
        """Delete a stored object when authorized application logic or rollback requests it."""


def validate_safe_object_key(raw_key: str) -> str:
    """Validate and normalize a relative storage key, blocking path traversal and injection."""
    key = str(raw_key or "").strip()
    if (
        not key
        or "\\" in key
        or "\x00" in key
        or key.startswith("/")
        or ".." in key.split("/")
        or "://" in key
        or not _SAFE_OBJECT_KEY_RE.match(key)
    ):
        raise AuthServiceError("invalid_storage_path", "Invalid attachment storage path.", 500)
    return key


def is_r2_storage_ref(storage_ref: str | None) -> bool:
    """Return True when `storage_ref` uses the explicit `r2://` object-storage scheme."""
    return isinstance(storage_ref, str) and storage_ref.startswith(R2_STORAGE_PREFIX)


def extract_r2_key(storage_ref: str) -> str:
    """Extract and validate the S3/R2 object key from an `r2://` reference."""
    if not is_r2_storage_ref(storage_ref):
        raise AuthServiceError("invalid_storage_path", "Invalid R2 storage reference.", 500)
    return validate_safe_object_key(storage_ref[len(R2_STORAGE_PREFIX) :])


def build_r2_object_key(rel_key: str) -> str:
    """Normalize a relative `YYYY/MM/<uuid>.<ext>` key into `complaints/YYYY/MM/<uuid>.<ext>`."""
    clean = validate_safe_object_key(rel_key)
    if clean.startswith(R2_KEY_PREFIX):
        return clean
    return validate_safe_object_key(f"{R2_KEY_PREFIX}{clean}")


def build_r2_storage_ref(object_key: str) -> str:
    """Format the canonical database `storage_path` value (`r2://complaints/...`)."""
    return f"{R2_STORAGE_PREFIX}{validate_safe_object_key(object_key)}"


class LocalAttachmentStorage:
    """Private local filesystem storage backend anchored at `COMPLAINT_ATTACHMENT_DIR`."""

    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(str(base_dir)).resolve()

    def _resolve_target(self, rel_key: str, *, require_file: bool) -> Path:
        clean_rel = str(rel_key or "").strip()
        if not clean_rel or "\\" in clean_rel or "\x00" in clean_rel:
            raise AuthServiceError(
                "attachment_file_missing",
                "The requested attachment file is unavailable.",
                404,
            )
        rel = Path(clean_rel)
        if rel.is_absolute():
            raise AuthServiceError(
                "attachment_file_missing",
                "The requested attachment file is unavailable.",
                404,
            )
        resolved = (self.base_dir / rel).resolve()
        if not resolved.is_relative_to(self.base_dir):
            raise AuthServiceError(
                "attachment_file_missing",
                "The requested attachment file is unavailable.",
                404,
            )
        if require_file and not resolved.is_file():
            raise AuthServiceError(
                "attachment_file_missing",
                "The requested attachment file is unavailable.",
                404,
            )
        return resolved

    def save(
        self,
        rel_key: str,
        data: bytes,
        *,
        content_type: str,  # noqa: ARG002
        checksum_sha256: str,  # noqa: ARG002
    ) -> str:
        clean_rel = validate_safe_object_key(rel_key)
        target_path = (self.base_dir / clean_rel).resolve()
        if not target_path.is_relative_to(self.base_dir):
            raise AuthServiceError("invalid_storage_path", "Invalid attachment path.", 500)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = target_path.suffix or ".bin"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target_path.parent,
                prefix=".tmp_",
                suffix=suffix,
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(data)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, target_path)
        except Exception as exc:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
            raise AuthServiceError(
                "attachment_storage_error",
                "Failed to store complaint photo attachment safely.",
                500,
            ) from exc

        return clean_rel

    def resolve_path(self, storage_ref: str) -> Path:
        """Return verified local filesystem path or raise 404 `attachment_file_missing`."""
        return self._resolve_target(storage_ref, require_file=True)

    def retrieve(self, storage_ref: str) -> RetrievedAttachment:
        path = self.resolve_path(storage_ref)
        return RetrievedAttachment(file_path=path)

    def head(self, storage_ref: str) -> StoredObjectMeta | None:
        try:
            path = self.resolve_path(storage_ref)
        except AuthServiceError:
            return None
        return StoredObjectMeta(storage_ref=storage_ref, size_bytes=path.stat().st_size)

    def exists(self, storage_ref: str) -> bool:
        return self.head(storage_ref) is not None

    def delete(self, storage_ref: str) -> None:
        clean_ref = str(storage_ref or "").strip()
        if not clean_ref:
            return
        candidate = Path(clean_ref)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.base_dir / candidate).resolve()
        if resolved.is_relative_to(self.base_dir):
            with contextlib.suppress(OSError):
                resolved.unlink(missing_ok=True)


def _client_error_code(exc: ClientError) -> str:
    resp = getattr(exc, "response", None) or {}
    err = resp.get("Error") if isinstance(resp, dict) else None
    code = str((err or {}).get("Code") or "").strip()
    if code:
        return code
    meta = resp.get("ResponseMetadata") if isinstance(resp, dict) else None
    http_status = (meta or {}).get("HTTPStatusCode")
    return str(http_status or "")


class R2AttachmentStorage:
    """Private Cloudflare R2 storage backend using S3-compatible `boto3`."""

    def __init__(
        self,
        *,
        bucket_name: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "auto",
        connect_timeout: int = 5,
        read_timeout: int = 15,
        client: Any | None = None,
    ) -> None:
        self.bucket_name = str(bucket_name or "").strip()
        self.endpoint_url = str(endpoint_url or "").strip().rstrip("/")
        self.region_name = str(region_name or "auto").strip() or "auto"

        if client is not None:
            self._client = client
            return

        if (
            not self.bucket_name
            or not self.endpoint_url
            or not access_key_id
            or not secret_access_key
        ):
            raise AuthServiceError(
                "storage_not_configured",
                "Cloudflare R2 attachment storage is not properly configured.",
                500,
            )

        boto_cfg = BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=max(1, int(connect_timeout)),
            read_timeout=max(1, int(read_timeout)),
            retries={"max_attempts": 3, "mode": "standard"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=self.region_name,
            config=boto_cfg,
        )

    @staticmethod
    def _log_r2_error(operation: str, exc: Exception, key: str) -> None:
        with contextlib.suppress(Exception):
            current_app.logger.error(
                "R2 attachment %s failed for key=%s (%s)",
                operation,
                key,
                type(exc).__name__,
            )

    def save(
        self,
        rel_key: str,
        data: bytes,
        *,
        content_type: str,
        checksum_sha256: str,
    ) -> str:
        object_key = build_r2_object_key(rel_key)
        storage_ref = build_r2_storage_ref(object_key)
        uploaded = False
        try:
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=data,
                ContentType=content_type,
                Metadata={"sha256": checksum_sha256},
            )
            uploaded = True
            head_resp = self._client.head_object(Bucket=self.bucket_name, Key=object_key)
            stored_len = int(head_resp.get("ContentLength", -1))
            if stored_len != len(data):
                raise ValueError("Uploaded R2 object length verification mismatch.")
        except (ClientError, BotoCoreError, OSError, ValueError) as exc:
            self._log_r2_error("upload", exc, object_key)
            if uploaded:
                with contextlib.suppress(Exception):
                    self._client.delete_object(Bucket=self.bucket_name, Key=object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Failed to store complaint photo attachment safely.",
                500,
            ) from exc

        return storage_ref

    def head(self, storage_ref: str) -> StoredObjectMeta | None:
        object_key = extract_r2_key(storage_ref)
        try:
            resp = self._client.head_object(Bucket=self.bucket_name, Key=object_key)
        except ClientError as exc:
            if _client_error_code(exc) in _NOT_FOUND_ERROR_CODES:
                return None
            self._log_r2_error("head", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Unable to verify complaint attachment storage safely.",
                502,
            ) from exc
        except (BotoCoreError, OSError) as exc:
            self._log_r2_error("head", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Unable to verify complaint attachment storage safely.",
                502,
            ) from exc

        metadata = resp.get("Metadata") if isinstance(resp, dict) else None
        sha = metadata.get("sha256") if isinstance(metadata, dict) else None
        return StoredObjectMeta(
            storage_ref=storage_ref,
            size_bytes=int(resp.get("ContentLength", 0)),
            sha256=sha,
        )

    def exists(self, storage_ref: str) -> bool:
        return self.head(storage_ref) is not None

    def retrieve(self, storage_ref: str) -> RetrievedAttachment:
        object_key = extract_r2_key(storage_ref)
        try:
            resp = self._client.get_object(Bucket=self.bucket_name, Key=object_key)
            body = resp["Body"]
            try:
                data = body.read()
            finally:
                with contextlib.suppress(Exception):
                    body.close()
        except ClientError as exc:
            if _client_error_code(exc) in _NOT_FOUND_ERROR_CODES:
                raise AuthServiceError(
                    "attachment_file_missing",
                    "The requested attachment file is unavailable.",
                    404,
                ) from exc
            self._log_r2_error("retrieve", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Unable to retrieve the requested attachment safely.",
                502,
            ) from exc
        except (BotoCoreError, OSError, KeyError) as exc:
            self._log_r2_error("retrieve", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Unable to retrieve the requested attachment safely.",
                502,
            ) from exc

        content_type = resp.get("ContentType") if isinstance(resp, dict) else None
        return RetrievedAttachment(data=data, content_type=content_type)

    def delete(self, storage_ref: str) -> None:
        object_key = extract_r2_key(storage_ref)
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=object_key)
        except ClientError as exc:
            if _client_error_code(exc) in _NOT_FOUND_ERROR_CODES:
                return
            self._log_r2_error("delete", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Failed to remove complaint attachment object safely.",
                500,
            ) from exc
        except (BotoCoreError, OSError) as exc:
            self._log_r2_error("delete", exc, object_key)
            raise AuthServiceError(
                "attachment_storage_error",
                "Failed to remove complaint attachment object safely.",
                500,
            ) from exc


def get_configured_storage_backend_name() -> str:
    """Return normalized attachment storage backend (`local` or `r2`)."""
    raw = str(current_app.config.get("COMPLAINT_ATTACHMENT_STORAGE_BACKEND", "local") or "local")
    backend = raw.strip().lower()
    if backend not in SUPPORTED_STORAGE_BACKENDS:
        raise AuthServiceError(
            "storage_not_configured",
            f"Unsupported complaint attachment storage backend {backend!r}.",
            500,
        )
    return backend


def get_local_storage() -> LocalAttachmentStorage:
    """Instantiate local filesystem attachment storage from app configuration."""
    raw_dir = current_app.config.get("COMPLAINT_ATTACHMENT_DIR")
    if not raw_dir:
        raise AuthServiceError(
            "storage_not_configured",
            "Complaint attachment storage directory is not configured.",
            500,
        )
    return LocalAttachmentStorage(Path(str(raw_dir)))


def get_r2_storage() -> R2AttachmentStorage:
    """Instantiate Cloudflare R2 attachment storage from app configuration."""
    account_id = str(current_app.config.get("R2_ACCOUNT_ID", "") or "").strip()
    endpoint = str(current_app.config.get("R2_ENDPOINT_URL", "") or "").strip()
    if not endpoint and account_id:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

    return R2AttachmentStorage(
        bucket_name=str(current_app.config.get("R2_BUCKET_NAME", "") or "").strip(),
        endpoint_url=endpoint,
        access_key_id=str(current_app.config.get("R2_ACCESS_KEY_ID", "") or "").strip(),
        secret_access_key=str(current_app.config.get("R2_SECRET_ACCESS_KEY", "") or "").strip(),
        region_name=str(current_app.config.get("R2_REGION", "auto") or "auto").strip(),
        connect_timeout=int(current_app.config.get("R2_CONNECT_TIMEOUT_SECONDS", 5)),
        read_timeout=int(current_app.config.get("R2_READ_TIMEOUT_SECONDS", 15)),
    )


def get_write_storage_backend() -> AttachmentStorageBackend:
    """Return the configured write backend (`local` or `r2`)."""
    backend = get_configured_storage_backend_name()
    if backend == "r2":
        return get_r2_storage()
    return get_local_storage()


def get_storage_backend_for_ref(storage_ref: str) -> AttachmentStorageBackend:
    """Dispatch read/exists/delete by stored reference format (`r2://` vs local relative path)."""
    if is_r2_storage_ref(storage_ref):
        return get_r2_storage()
    return get_local_storage()


def cleanup_storage_refs(refs: Iterable[Path | str]) -> None:
    """Best-effort cleanup of staged local paths or `r2://` keys on failed DB commits."""
    for item in refs:
        if item is None:
            continue
        if isinstance(item, Path):
            with contextlib.suppress(OSError):
                item.unlink(missing_ok=True)
            continue

        ref_str = str(item).strip()
        if not ref_str:
            continue
        if is_r2_storage_ref(ref_str):
            with contextlib.suppress(Exception):
                get_r2_storage().delete(ref_str)
        else:
            with contextlib.suppress(Exception):
                get_local_storage().delete(ref_str)
