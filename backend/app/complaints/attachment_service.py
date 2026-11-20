"""Private filesystem storage, image validation, EXIF sanitization, and safe retrieval
for student complaint photo attachments.

SECURITY INVARIANTS:
- Never trust client-provided filenames, extensions, or MIME types.
- Validate magic bytes AND fully decode images with Pillow (rejecting corrupt/bomb inputs).
- Re-encode validated images to strip EXIF/GPS metadata and neutralize polyglots.
- Persist files outside static web roots using random UUID filenames and atomic replacement.
- Never expose internal filesystem paths to API clients.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.auth.service import AuthServiceError
from app.complaints.storage import (
    RetrievedAttachment,
    cleanup_storage_refs,
    get_local_storage,
    get_storage_backend_for_ref,
    get_write_storage_backend,
    is_r2_storage_ref,
)
from app.models.complaints import ComplaintAttachment

MAX_ATTACHMENTS_PER_COMPLAINT = 3
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5,242,880 bytes
MAX_IMAGE_WIDTH = 8192
MAX_IMAGE_HEIGHT = 8192
MAX_IMAGE_PIXELS = 25_000_000

_FORMAT_SPEC: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    data: bytes
    mime_type: str
    ext: str
    file_size_bytes: int
    checksum_sha256: str
    original_filename: str


@dataclass(frozen=True, slots=True)
class StagedAttachment:
    storage_path: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    checksum_sha256: str
    abs_path: Path | None = None

    @property
    def cleanup_ref(self) -> Path | str:
        """Return the safest target handle for rollback cleanup (`Path` for local, key for R2)."""
        return self.abs_path if self.abs_path is not None else self.storage_path


def get_max_attachments() -> int:
    return int(current_app.config.get("COMPLAINT_MAX_ATTACHMENTS", MAX_ATTACHMENTS_PER_COMPLAINT))


def get_max_attachment_bytes() -> int:
    return int(current_app.config.get("COMPLAINT_MAX_ATTACHMENT_BYTES", MAX_ATTACHMENT_BYTES))


def get_attachment_base_dir() -> Path:
    raw = current_app.config.get("COMPLAINT_ATTACHMENT_DIR")
    if not raw:
        raise AuthServiceError(
            "storage_not_configured",
            "Complaint attachment storage directory is not configured.",
            500,
        )
    return Path(str(raw)).resolve()


def _detect_magic_format(raw_bytes: bytes) -> str | None:
    if raw_bytes.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        return "WEBP"
    return None


def sanitize_display_filename(raw_filename: str | None, verified_ext: str) -> str:
    """Produce a safe, non-empty display filename matching the verified image extension."""
    raw = (raw_filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = secure_filename(raw)
    stem = Path(cleaned).stem if cleaned else "photo"
    if not stem:
        stem = "photo"
    max_stem_len = 180
    stem = stem[:max_stem_len]
    return f"{stem}.{verified_ext}"


def _composite_alpha_onto_white(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.split()[3])
    return background


def _reencode_image(img: Image.Image, fmt: str, max_bytes: int) -> bytes:
    """Re-encode an already-loaded image without EXIF/GPS/comment metadata."""
    if fmt == "JPEG":
        if img.mode in ("RGBA", "LA", "PA"):
            out_img = _composite_alpha_onto_white(img)
        elif img.mode not in ("RGB", "L"):
            out_img = img.convert("RGB")
        else:
            out_img = img

        for quality in (88, 78, 68):
            buf = io.BytesIO()
            out_img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data
        raise AuthServiceError(
            "validation_error",
            "Processed JPEG photo exceeds the 5 MB limit.",
            400,
        )

    if fmt == "PNG":
        out_img = img
        if out_img.mode == "P":
            out_img = out_img.convert("RGBA" if "transparency" in out_img.info else "RGB")
        elif out_img.mode not in ("RGB", "RGBA", "L", "LA", "1"):
            out_img = out_img.convert("RGBA")
        buf = io.BytesIO()
        out_img.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        if len(data) > max_bytes:
            raise AuthServiceError(
                "validation_error",
                "Processed PNG photo exceeds the 5 MB limit.",
                400,
            )
        return data

    if fmt == "WEBP":
        out_img = img if img.mode in ("RGB", "RGBA") else img.convert("RGB")
        for quality in (85, 75, 65):
            buf = io.BytesIO()
            out_img.save(buf, format="WEBP", quality=quality, method=4)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data
        raise AuthServiceError(
            "validation_error",
            "Processed WebP photo exceeds the 5 MB limit.",
            400,
        )

    raise AuthServiceError("unsupported_media_type", "Unsupported image format.", 400)


def validate_and_sanitize_image(
    file_storage: FileStorage,
    *,
    max_bytes: int | None = None,
) -> ValidatedImage:
    """Strictly validate image size, magic bytes, full Pillow decode, and strip EXIF metadata."""
    limit_bytes = max_bytes if max_bytes is not None else get_max_attachment_bytes()
    stream = file_storage.stream
    if stream is None:
        raise AuthServiceError("validation_error", "Uploaded photo stream is missing.", 400)

    if stream.seekable():
        stream.seek(0)
    raw_bytes = stream.read(limit_bytes + 1)

    if not raw_bytes:
        raise AuthServiceError("validation_error", "Uploaded photo file is empty.", 400)
    if len(raw_bytes) > limit_bytes:
        raise AuthServiceError(
            "validation_error",
            "Each complaint photo must not exceed 5 MB (5,242,880 bytes).",
            400,
        )

    magic_fmt = _detect_magic_format(raw_bytes)
    if magic_fmt is None or magic_fmt not in _FORMAT_SPEC:
        raise AuthServiceError(
            "unsupported_media_type",
            "Unsupported image format. Only JPEG, PNG, and WebP photos are allowed.",
            400,
        )

    mime_type, verified_ext = _FORMAT_SPEC[magic_fmt]
    safe_display_name = sanitize_display_filename(file_storage.filename, verified_ext)

    prev_max_pixels = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            # Pass 1: structural integrity verification
            with Image.open(io.BytesIO(raw_bytes)) as probe_img:
                if probe_img.format != magic_fmt:
                    raise AuthServiceError(
                        "unsupported_media_type",
                        "Image content does not match a supported JPEG, PNG, or WebP format.",
                        400,
                    )
                probe_img.verify()

            # Pass 2: full pixel decode, dimension check, orientation normalization & re-encoding
            with Image.open(io.BytesIO(raw_bytes)) as img:
                if img.format != magic_fmt:
                    raise AuthServiceError(
                        "unsupported_media_type",
                        "Image content does not match a supported JPEG, PNG, or WebP format.",
                        400,
                    )
                width, height = img.size
                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_IMAGE_WIDTH
                    or height > MAX_IMAGE_HEIGHT
                    or (width * height) > MAX_IMAGE_PIXELS
                ):
                    raise AuthServiceError(
                        "validation_error",
                        "Image dimensions exceed allowed safety limits.",
                        400,
                    )
                img.load()
                normalized = ImageOps.exif_transpose(img)
                sanitized_bytes = _reencode_image(normalized, magic_fmt, limit_bytes)
    except AuthServiceError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        ValueError,
        SyntaxError,
        EOFError,
    ) as exc:
        raise AuthServiceError(
            "invalid_image",
            "Uploaded file is corrupted, malformed, or not a valid image.",
            400,
        ) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = prev_max_pixels

    checksum = hashlib.sha256(sanitized_bytes).hexdigest()
    return ValidatedImage(
        data=sanitized_bytes,
        mime_type=mime_type,
        ext=verified_ext,
        file_size_bytes=len(sanitized_bytes),
        checksum_sha256=checksum,
        original_filename=safe_display_name,
    )


def validate_uploaded_photos(files: list[FileStorage]) -> list[ValidatedImage]:
    """Validate count limit (max 3) and decode/sanitize each uploaded photo."""
    max_count = get_max_attachments()
    if len(files) > max_count:
        raise AuthServiceError(
            "validation_error",
            f"You may attach at most {max_count} photos per complaint.",
            400,
        )
    return [validate_and_sanitize_image(f) for f in files]


def cleanup_staged_files(paths: Iterable[Path | str]) -> None:
    """Best-effort cleanup of staged/persisted files or R2 objects when a request rolls back."""
    cleanup_storage_refs(paths)


def persist_validated_images(images: list[ValidatedImage]) -> list[StagedAttachment]:
    """Persist validated images to the configured backend (`local` or `r2`).

    If persisting any item in the batch fails, all previously stored files/objects
    from that batch are deleted before re-raising.
    """
    if not images:
        return []

    backend = get_write_storage_backend()
    now_prefix = datetime.now(UTC).strftime("%Y/%m")
    staged: list[StagedAttachment] = []
    created_refs: list[Path | str] = []

    try:
        for img in images:
            rel_key = f"{now_prefix}/{uuid.uuid4().hex}.{img.ext}"
            storage_ref = backend.save(
                rel_key,
                img.data,
                content_type=img.mime_type,
                checksum_sha256=img.checksum_sha256,
            )
            abs_path: Path | None = None
            if not is_r2_storage_ref(storage_ref):
                abs_path = get_local_storage().resolve_path(storage_ref)
                created_refs.append(abs_path)
            else:
                created_refs.append(storage_ref)

            staged.append(
                StagedAttachment(
                    storage_path=storage_ref,
                    original_filename=img.original_filename,
                    file_size_bytes=img.file_size_bytes,
                    mime_type=img.mime_type,
                    checksum_sha256=img.checksum_sha256,
                    abs_path=abs_path,
                )
            )
    except Exception:
        cleanup_staged_files(created_refs)
        raise

    return staged


def resolve_attachment_file_path(attachment: ComplaintAttachment) -> Path:
    """Safely resolve a local attachment's private filesystem path and confirm it exists."""
    return get_local_storage().resolve_path(attachment.storage_path)


def retrieve_attachment_content(attachment: ComplaintAttachment) -> RetrievedAttachment:
    """Retrieve attachment bytes or path from the appropriate backend (`local` or `r2`)."""
    backend = get_storage_backend_for_ref(attachment.storage_path)
    return backend.retrieve(attachment.storage_path)
