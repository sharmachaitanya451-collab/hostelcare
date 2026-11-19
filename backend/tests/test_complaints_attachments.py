"""Integration and security tests for student complaint photo attachments.

Covers:
1. Valid JPEG, PNG, and WebP uploads (1 photo and 3 photos).
2. Rejection of >3 photos, >5 MB photos, unsupported formats (SVG/PDF/HTML/EXE),
   spoofed extensions/MIME types, and corrupted/malformed image payloads.
3. Unauthenticated upload & retrieval rejections.
4. Strict authorization & IDOR isolation across students, assigned/unassigned/reassigned staff,
   admins, and cross-complaint attachment access.
5. EXIF/GPS metadata removal verification.
6. Atomic rollback & orphan cleanup on DB commit failure and storage failure.
7. Concurrency race protection ensuring concurrent uploads cannot exceed 3 attachments.
8. Zero-attachment backward compatibility and missing-file-on-disk error handling.
"""

from __future__ import annotations

import io
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from PIL import Image
from sqlalchemy import create_engine, func, select, text

from app import create_app
from app.auth.security import hash_password
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAttachment
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


@pytest.fixture(scope="module")
def attachments_app():
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
def _clean_attachment_tables_and_dir(attachments_app, tmp_path):
    """Truncate complaint tables and bind an isolated temp attachment dir per test."""
    attachments_app.config["COMPLAINT_ATTACHMENT_DIR"] = str(tmp_path / "complaint_uploads")
    owner_engine = create_engine(
        attachments_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True
    )
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, "
                "public.notifications, "
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
                "public.student_profiles, "
                "public.staff_profiles, "
                "public.users "
                "RESTART IDENTITY CASCADE"
            )
        )
    owner_engine.dispose()
    yield


def _seed_actors(app) -> dict[str, str]:
    with app.app_context():
        admin = User(
            email="warden.att@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.flush()

        block_a = Block(code="BLKA", name="Aryabhatta Block", is_active=True)
        db.session.add(block_a)
        db.session.flush()

        room_204 = Room(
            block_id=block_a.id,
            room_number="A-204",
            floor=2,
            capacity=2,
            room_type="double",
            is_active=True,
        )
        db.session.add(room_204)
        db.session.flush()

        stu1 = User(
            email="stu1.att@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="stu2.att@hostelcare.test",
            full_name="Rohan Verma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stf1 = User(
            email="stf1.att@hostelcare.test",
            full_name="Ramesh Babu",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        stf2 = User(
            email="stf2.att@hostelcare.test",
            full_name="Santosh Kumar",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        db.session.add_all([stu1, stu2, stf1, stf2])
        db.session.flush()

        db.session.add_all(
            [
                StudentProfile(
                    user_id=stu1.id,
                    roll_number="2026CSB1042",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                ),
                StudentProfile(
                    user_id=stu2.id,
                    roll_number="2026CSB1043",
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                ),
                StaffProfile(
                    user_id=stf1.id,
                    staff_code="STF-1001",
                    trade="Electrician",
                ),
                StaffProfile(
                    user_id=stf2.id,
                    staff_code="STF-1002",
                    trade="Plumber",
                ),
                RoomAllocation(
                    student_user_id=stu1.id,
                    room_id=room_204.id,
                    bed_number=1,
                    start_date=date.today() - timedelta(days=5),
                    allocated_by=admin.id,
                ),
                RoomAllocation(
                    student_user_id=stu2.id,
                    room_id=room_204.id,
                    bed_number=2,
                    start_date=date.today() - timedelta(days=5),
                    allocated_by=admin.id,
                ),
            ]
        )
        db.session.commit()
        return {
            "admin_id": str(admin.public_id),
            "stu1_id": str(stu1.public_id),
            "stu2_id": str(stu2.public_id),
            "stf1_id": str(stf1.public_id),
            "stf2_id": str(stf2.public_id),
        }


def _login_headers(client, identifier: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert resp.status_code == 200, resp.get_json()
    return {"X-CSRF-Token": resp.get_json()["csrf_token"]}


def _make_image_bytes(
    fmt: str, *, color: tuple[int, int, int] = (200, 60, 100), exif: bool = False
) -> bytes:
    img = Image.new("RGB", (32, 24), color=color)
    buf = io.BytesIO()
    if fmt == "JPEG" and exif:
        exif_obj = Image.Exif()
        # EXIF tag 0x010E ImageDescription & 0x8825 GPSInfo pointer simulation via 0x010F Make
        exif_obj[0x010E] = "PrivateGPSCoords:12.9716,77.5946"
        exif_obj[0x010F] = "SecretPhoneModel"
        img.save(buf, format="JPEG", exif=exif_obj.tobytes())
    else:
        img.save(buf, format=fmt)
    return buf.getvalue()


def _multipart_complaint_data(
    photos: list[tuple[io.BytesIO, str] | tuple[io.BytesIO, str, str]],
) -> dict:
    return {
        "title": "Faulty ceiling fan wiring",
        "description": "Sparking noise from ceiling fan regulator when turned on.",
        "priority": "high",
        "location_type": "room",
        "category": "Electrical",
        "photos": photos,
    }


@pytest.mark.db
def test_upload_one_valid_jpeg_and_exif_sanitization(attachments_app):
    """Test 1: Upload 1 valid JPEG with EXIF metadata; verify persisted & EXIF stripped."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    jpeg_with_exif = _make_image_bytes("JPEG", exif=True)
    assert b"PrivateGPSCoords" in jpeg_with_exif

    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [(io.BytesIO(jpeg_with_exif), "../../ceiling_fan.jpg", "image/jpeg")]
        ),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.get_json()
    comp = resp.get_json()["complaint"]
    assert len(comp["attachments"]) == 1
    att = comp["attachments"][0]
    assert att["mimeType"] == "image/jpeg"
    assert att["filename"] == "ceiling_fan.jpg"
    assert "storage_path" not in att
    assert att["url"] == f"/api/v1/complaints/{comp['referenceNo']}/attachments/{att['id']}"

    # Verify stored file on disk has no EXIF payload and is outside static dir
    dl_resp = stu_client.get(att["url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["Content-Type"] == "image/jpeg"
    assert dl_resp.headers["X-Content-Type-Options"] == "nosniff"
    assert dl_resp.headers["Cache-Control"] == "no-store"
    assert "sandbox" in dl_resp.headers["Content-Security-Policy"].lower()
    assert b"PrivateGPSCoords" not in dl_resp.data
    with Image.open(io.BytesIO(dl_resp.data)) as downloaded:
        assert downloaded.format == "JPEG"
        assert len(downloaded.getexif()) == 0


@pytest.mark.db
def test_upload_three_valid_images_mixed_formats(attachments_app):
    """Test 2: Upload 3 valid images (JPEG, PNG, WebP) in one complaint submission."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    files = [
        (io.BytesIO(_make_image_bytes("JPEG")), "one.jpg", "image/jpeg"),
        (io.BytesIO(_make_image_bytes("PNG")), "two.png", "image/png"),
        (io.BytesIO(_make_image_bytes("WEBP")), "three.webp", "image/webp"),
    ]
    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(files),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.get_json()
    attachments = resp.get_json()["complaint"]["attachments"]
    assert len(attachments) == 3
    assert [a["mimeType"] for a in attachments] == ["image/jpeg", "image/png", "image/webp"]


@pytest.mark.db
def test_reject_fourth_image_and_preserve_clean_state(attachments_app):
    """Test 3: Submitting 4 images must fail with 400 and leave no complaint or files."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    files = [
        (io.BytesIO(_make_image_bytes("JPEG")), f"img_{i}.jpg", "image/jpeg") for i in range(4)
    ]
    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(files),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"

    with attachments_app.app_context():
        assert db.session.execute(select(func.count(Complaint.id))).scalar_one() == 0
        assert db.session.execute(select(func.count(ComplaintAttachment.id))).scalar_one() == 0

    upload_dir = Path(attachments_app.config["COMPLAINT_ATTACHMENT_DIR"])
    assert not upload_dir.exists() or not any(upload_dir.rglob("*.*"))


@pytest.mark.db
def test_reject_image_larger_than_5mb(attachments_app):
    """Test 4: Reject an upload exceeding 5 MB (5,242,880 bytes)."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    oversized = _make_image_bytes("JPEG") + (b"\x00" * (5 * 1024 * 1024 + 1024))
    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data([(io.BytesIO(oversized), "huge.jpg", "image/jpeg")]),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"

    with attachments_app.app_context():
        assert db.session.execute(select(func.count(Complaint.id))).scalar_one() == 0


@pytest.mark.db
@pytest.mark.parametrize(
    ("raw_bytes", "filename", "content_type"),
    [
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "xss.svg",
            "image/svg+xml",
        ),
        (b"%PDF-1.7\n1 0 obj\n<<>>\nendobj", "doc.pdf", "application/pdf"),
        (b"<html><body><script>alert(1)</script></body></html>", "page.html", "text/html"),
        (b"MZ\x90\x00\x03\x00\x00\x00", "payload.exe", "application/octet-stream"),
    ],
)
def test_reject_unsupported_formats(attachments_app, raw_bytes, filename, content_type):
    """Test 5: Reject SVG, PDF, HTML, and executable files."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data([(io.BytesIO(raw_bytes), filename, content_type)]),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.db
def test_reject_spoofed_extension_and_mime_type(attachments_app):
    """Test 6: Reject HTML/SVG content disguised with `.jpg` extension and `image/jpeg` MIME."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    spoofed = b"<script>alert('xss')</script>"
    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data([(io.BytesIO(spoofed), "innocent.jpg", "image/jpeg")]),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.db
def test_reject_corrupted_or_malformed_image_data(attachments_app):
    """Test 7: Valid JPEG/PNG magic bytes followed by corrupted body must fail Pillow decoding."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    corrupt_jpeg = b"\xff\xd8\xff\xe0" + b"corrupt-non-image-payload-123456"
    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data([(io.BytesIO(corrupt_jpeg), "broken.jpg", "image/jpeg")]),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_image"


@pytest.mark.db
def test_reject_unauthenticated_upload_and_retrieval(attachments_app):
    """Tests 8 & 9: Unauthenticated upload and unauthenticated attachment retrieval return 401."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    create_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [(io.BytesIO(_make_image_bytes("PNG")), "leak.png", "image/png")]
        ),
        content_type="multipart/form-data",
    )
    assert create_resp.status_code == 201
    att_url = create_resp.get_json()["complaint"]["attachments"][0]["url"]

    anon_client = attachments_app.test_client()
    up_resp = anon_client.post(
        "/api/v1/student/complaints",
        data=_multipart_complaint_data(
            [(io.BytesIO(_make_image_bytes("PNG")), "anon.png", "image/png")]
        ),
        content_type="multipart/form-data",
    )
    assert up_resp.status_code == 401

    get_resp = anon_client.get(att_url)
    assert get_resp.status_code == 401


@pytest.mark.db
def test_authorization_idor_and_cross_complaint_isolation(attachments_app):
    """Tests 10-15: Full RBAC, roommate IDOR, staff reassignment & cross-ref checks."""
    actors = _seed_actors(attachments_app)
    stu1_client = attachments_app.test_client()
    stu2_client = attachments_app.test_client()
    stf1_client = attachments_app.test_client()
    stf2_client = attachments_app.test_client()
    admin_client = attachments_app.test_client()

    stu1_hdr = _login_headers(stu1_client, "stu1.att@hostelcare.test", "StudentPass123!")
    _login_headers(stu2_client, "stu2.att@hostelcare.test", "StudentPass123!")
    _login_headers(stf1_client, "stf1.att@hostelcare.test", "StaffPass123!")
    _login_headers(stf2_client, "stf2.att@hostelcare.test", "StaffPass123!")
    admin_hdr = _login_headers(admin_client, "warden.att@hostelcare.test", "AdminPass123!")

    png_bytes = _make_image_bytes("PNG", color=(10, 120, 220))
    c1_resp = stu1_client.post(
        "/api/v1/student/complaints",
        headers=stu1_hdr,
        data=_multipart_complaint_data([(io.BytesIO(png_bytes), "pipe.png", "image/png")]),
        content_type="multipart/form-data",
    )
    assert c1_resp.status_code == 201
    c1 = c1_resp.get_json()["complaint"]
    c1_ref = c1["referenceNo"]
    att1 = c1["attachments"][0]
    att1_url = att1["url"]

    # Second complaint by stu1 (no attachments) to test cross-complaint reference mismatch
    c2_resp = stu1_client.post(
        "/api/v1/student/complaints",
        headers=stu1_hdr,
        json={
            "title": "Desk chair wobble",
            "description": "Study chair screw is loose.",
            "priority": "low",
            "location_type": "room",
        },
    )
    assert c2_resp.status_code == 201
    c2_ref = c2_resp.get_json()["complaint"]["referenceNo"]

    # Test 13: Owner can retrieve
    assert stu1_client.get(att1_url).status_code == 200

    # Test 10: Student B (even roommate in same Room A-204) cannot retrieve Student A's attachment
    assert stu2_client.get(att1_url).status_code == 403

    # Test 14: Admin can retrieve even before assignment
    assert admin_client.get(att1_url).status_code == 200

    # Test 11: Unassigned staff cannot retrieve
    assert stf1_client.get(att1_url).status_code == 403
    assert stf2_client.get(att1_url).status_code == 403

    # Assign complaint 1 to Staff 1
    assign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{c1_ref}/assign",
        headers=admin_hdr,
        json={"staff_id": actors["stf1_id"], "instructions": "Inspect wiring."},
    )
    assert assign_resp.status_code == 200

    # Test 12: Assigned Staff 1 can retrieve; unassigned Staff 2 still 403
    stf1_dl = stf1_client.get(att1_url)
    assert stf1_dl.status_code == 200
    assert len(stf1_dl.data) > 0
    assert stf2_client.get(att1_url).status_code == 403

    # Reassign to Staff 2 -> Staff 1's access must be revoked immediately!
    reassign_resp = admin_client.post(
        f"/api/v1/admin/complaints/{c1_ref}/reassign",
        headers=admin_hdr,
        json={"staff_id": actors["stf2_id"], "reason": "Reassigned to plumber"},
    )
    assert reassign_resp.status_code == 200
    assert stf1_client.get(att1_url).status_code == 403
    assert stf2_client.get(att1_url).status_code == 200

    # Test 15: Attachment cannot be retrieved through a different complaint reference
    wrong_ref_url = f"/api/v1/complaints/{c2_ref}/attachments/{att1['id']}"
    assert stu1_client.get(wrong_ref_url).status_code == 404
    assert admin_client.get(wrong_ref_url).status_code == 404


@pytest.mark.db
def test_database_failure_rolls_back_and_cleans_up_files(attachments_app, monkeypatch):
    """Test 16: DB commit failure rolls back rows and deletes newly written disk files."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    def fail_commit():
        raise RuntimeError("Simulated database commit failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)

    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [(io.BytesIO(_make_image_bytes("PNG")), "db_fail.png", "image/png")]
        ),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 500

    upload_dir = Path(attachments_app.config["COMPLAINT_ATTACHMENT_DIR"])
    written_files = [p for p in upload_dir.rglob("*") if p.is_file()] if upload_dir.exists() else []
    assert written_files == []


@pytest.mark.db
def test_storage_failure_leaves_no_partial_complaint_data(attachments_app, monkeypatch):
    """Test 17: Filesystem write failure leaves zero complaint or attachment rows in DB."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    import app.complaints.student_service as stu_svc

    def fail_persist(_images):
        from app.auth.service import AuthServiceError

        raise AuthServiceError("attachment_storage_error", "Simulated disk full error.", 500)

    monkeypatch.setattr(stu_svc, "persist_validated_images", fail_persist)

    resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [(io.BytesIO(_make_image_bytes("PNG")), "disk_fail.png", "image/png")]
        ),
        content_type="multipart/form-data",
    )
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "attachment_storage_error"

    with attachments_app.app_context():
        assert db.session.execute(select(func.count(Complaint.id))).scalar_one() == 0
        assert db.session.execute(select(func.count(ComplaintAttachment.id))).scalar_one() == 0


@pytest.mark.db
def test_concurrent_uploads_cannot_exceed_three_attachments(attachments_app):
    """Test 18: Concurrent upload attempts serialize on row lock and enforce max 3."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    # Create complaint with 2 initial attachments
    init_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [
                (io.BytesIO(_make_image_bytes("PNG", color=(1, 2, 3))), "one.png", "image/png"),
                (io.BytesIO(_make_image_bytes("PNG", color=(4, 5, 6))), "two.png", "image/png"),
            ]
        ),
        content_type="multipart/form-data",
    )
    assert init_resp.status_code == 201
    comp_ref = init_resp.get_json()["complaint"]["referenceNo"]

    # Two concurrent requests each try to attach 1 more photo (only 1 slot remains!)
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def worker(idx: int):
        worker_client = attachments_app.test_client()
        worker_hdr = _login_headers(worker_client, "stu1.att@hostelcare.test", "StudentPass123!")
        barrier.wait(timeout=10)
        r = worker_client.post(
            f"/api/v1/student/complaints/{comp_ref}/attachments",
            headers=worker_hdr,
            data={
                "photos": (
                    io.BytesIO(_make_image_bytes("JPEG", color=(10 * idx, 20, 30))),
                    f"race_{idx}.jpg",
                    "image/jpeg",
                )
            },
            content_type="multipart/form-data",
        )
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert sorted(results) == [201, 400]

    with attachments_app.app_context():
        comp = db.session.execute(
            select(Complaint).where(Complaint.reference_no == comp_ref)
        ).scalar_one()
        count = db.session.execute(
            select(func.count(ComplaintAttachment.id)).where(
                ComplaintAttachment.complaint_id == comp.id
            )
        ).scalar_one()
        assert count == 3


@pytest.mark.db
def test_complaint_without_photos_and_missing_file_handling(attachments_app):
    """Test 19 & missing-file guard: Zero-attachment complaints work; deleted file returns 404."""
    _seed_actors(attachments_app)
    stu_client = attachments_app.test_client()
    headers = _login_headers(stu_client, "stu1.att@hostelcare.test", "StudentPass123!")

    # JSON submission without photos
    json_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        json={
            "title": "Window latch loose",
            "description": "Window latch in Room A-204 does not lock.",
            "priority": "medium",
            "location_type": "room",
        },
    )
    assert json_resp.status_code == 201
    assert json_resp.get_json()["complaint"]["attachments"] == []

    # Multipart submission without photos
    mp_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data={
            "title": "Corridor bulb fused",
            "description": "2nd floor corridor light is out.",
            "priority": "low",
            "location_type": "common_area",
            "location_detail": "2nd floor corridor",
        },
        content_type="multipart/form-data",
    )
    assert mp_resp.status_code == 201
    assert mp_resp.get_json()["complaint"]["attachments"] == []

    # Missing file on disk returns 404 safely without leaking filesystem path
    up_resp = stu_client.post(
        "/api/v1/student/complaints",
        headers=headers,
        data=_multipart_complaint_data(
            [(io.BytesIO(_make_image_bytes("WEBP")), "gone.webp", "image/webp")]
        ),
        content_type="multipart/form-data",
    )
    assert up_resp.status_code == 201
    att_url = up_resp.get_json()["complaint"]["attachments"][0]["url"]

    for f in Path(attachments_app.config["COMPLAINT_ATTACHMENT_DIR"]).rglob("*.webp"):
        f.unlink()

    dl_resp = stu_client.get(att_url)
    assert dl_resp.status_code == 404
    err = dl_resp.get_json()["error"]
    assert err["code"] == "attachment_file_missing"
    assert "complaint_uploads" not in err["message"]


@pytest.mark.db
def test_least_privilege_permissions_on_complaint_attachments(attachments_app):
    """Verify `hostelcare_app` has SELECT/INSERT only on complaint_attachments."""
    owner_engine = create_engine(
        attachments_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True
    )
    try:
        with owner_engine.connect() as conn:
            tbl = "public.complaint_attachments"
            row = conn.execute(
                text(
                    "SELECT "
                    f"has_table_privilege('hostelcare_app', '{tbl}', 'SELECT'), "
                    f"has_table_privilege('hostelcare_app', '{tbl}', 'INSERT'), "
                    f"has_table_privilege('hostelcare_app', '{tbl}', 'UPDATE'), "
                    f"has_table_privilege('hostelcare_app', '{tbl}', 'DELETE')"
                )
            ).fetchone()
            assert row == (True, True, False, False)
    finally:
        owner_engine.dispose()
