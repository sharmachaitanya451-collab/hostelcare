"""Tests for Cloudflare R2 attachment storage, RBAC, rollback cleanup, and migration CLI."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from flask_migrate import upgrade
from PIL import Image
from sqlalchemy import func, select, text

from app import create_app
from app.auth.security import hash_password
from app.complaints.storage import (
    R2AttachmentStorage,
    extract_r2_key,
    validate_safe_object_key,
)
from app.extensions import db
from app.models.complaints import Complaint, ComplaintAttachment
from app.models.identity import StaffProfile, StudentProfile, User
from app.models.rooms import Block, Room, RoomAllocation

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


def _make_image_bytes(fmt: str = "PNG", color: tuple[int, int, int] = (18, 120, 190)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (24, 24), color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


class _MockBody:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True


class InMemoryMockR2Client:
    """In-memory mock mimicking `boto3.client('s3')` for Cloudflare R2 tests."""

    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}
        self.put_calls: list[dict] = []
        self.delete_calls: list[str] = []
        self.head_calls: list[str] = []
        self.get_calls: list[str] = []
        self.fail_put_exc: Exception | None = None
        self.fail_get_exc: Exception | None = None
        self.fail_head_exc: Exception | None = None

    def put_object(
        self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, Metadata=None, **extra
    ):
        assert "ACL" not in extra, "Public ACLs are strictly forbidden"
        self.put_calls.append(
            {"Bucket": Bucket, "Key": Key, "ContentType": ContentType, "extra": extra}
        )
        if self.fail_put_exc is not None:
            raise self.fail_put_exc
        self.objects[Key] = {
            "Body": bytes(Body),
            "ContentType": ContentType,
            "ContentLength": len(Body),
            "Metadata": dict(Metadata or {}),
        }
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def head_object(self, *, Bucket: str, Key: str):
        self.head_calls.append(Key)
        if self.fail_head_exc is not None:
            raise self.fail_head_exc
        obj = self.objects.get(Key)
        if obj is None:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "Not Found"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadObject",
            )
        return {
            "ContentLength": obj["ContentLength"],
            "ContentType": obj["ContentType"],
            "Metadata": obj["Metadata"],
        }

    def get_object(self, *, Bucket: str, Key: str):
        self.get_calls.append(Key)
        if self.fail_get_exc is not None:
            raise self.fail_get_exc
        obj = self.objects.get(Key)
        if obj is None:
            raise ClientError(
                {
                    "Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "GetObject",
            )
        return {
            "Body": _MockBody(obj["Body"]),
            "ContentType": obj["ContentType"],
            "ContentLength": obj["ContentLength"],
            "Metadata": obj["Metadata"],
        }

    def delete_object(self, *, Bucket: str, Key: str):
        self.delete_calls.append(Key)
        self.objects.pop(Key, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


@pytest.fixture(scope="module")
def r2_db_app():
    app = create_app("testing")
    if not app.config.get("SQLALCHEMY_DATABASE_URI") or not app.config.get(
        "MIGRATION_DATABASE_URI"
    ):
        pytest.skip("TEST_DATABASE_URL / TEST_MIGRATION_DATABASE_URL not configured")
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR, revision="head")
    return app


@pytest.fixture
def mock_r2(r2_db_app, tmp_path, monkeypatch):
    """Reset test tables, bind tmp local upload dir, and wire mocked R2 `boto3.client`."""
    fake_client = InMemoryMockR2Client()
    captured_boto_kwargs: list[dict] = []

    def fake_boto3_client(service_name, **kwargs):
        assert service_name == "s3"
        captured_boto_kwargs.append(kwargs)
        return fake_client

    monkeypatch.setattr(boto3, "client", fake_boto3_client)

    r2_db_app.config["COMPLAINT_ATTACHMENT_STORAGE_BACKEND"] = "r2"
    r2_db_app.config["COMPLAINT_ATTACHMENT_DIR"] = str(tmp_path / "local_uploads")
    r2_db_app.config["R2_ACCOUNT_ID"] = "cfacct123456"
    r2_db_app.config["R2_BUCKET_NAME"] = "hostelcare-private-test"
    r2_db_app.config["R2_ACCESS_KEY_ID"] = "r2-test-key-id"
    r2_db_app.config["R2_SECRET_ACCESS_KEY"] = "r2-test-secret-key"
    r2_db_app.config["R2_ENDPOINT_URL"] = "https://cfacct123456.r2.cloudflarestorage.com"
    r2_db_app.config["R2_REGION"] = "auto"

    owner_engine = create_app("testing")
    from sqlalchemy import create_engine

    eng = create_engine(r2_db_app.config["MIGRATION_DATABASE_URI"], pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "public.audit_logs, public.notifications, public.complaint_attachments, "
                "public.complaint_history, public.complaint_internal_notes, "
                "public.complaint_updates, public.complaint_assignments, public.complaints, "
                "public.room_allocations, public.rooms, public.blocks, "
                "public.password_reset_tokens, public.student_profiles, public.staff_profiles, "
                "public.users RESTART IDENTITY CASCADE"
            )
        )
    eng.dispose()
    del owner_engine

    yield fake_client, captured_boto_kwargs

    r2_db_app.config["COMPLAINT_ATTACHMENT_STORAGE_BACKEND"] = "local"


def _seed_actors(app) -> dict[str, int]:
    with app.app_context():
        admin = User(
            email="warden.r2@hostelcare.test",
            full_name="Dr. K. S. Verma",
            designation="Chief Hostel Warden",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            status="active",
        )
        db.session.add(admin)
        db.session.flush()

        block = Block(code="BLKA", name="Aryabhatta Block", is_active=True)
        db.session.add(block)
        db.session.flush()

        room = Room(block_id=block.id, room_number="A-204", floor=2, capacity=2, is_active=True)
        db.session.add(room)
        db.session.flush()

        stu1 = User(
            email="stu1.r2@hostelcare.test",
            full_name="Aarav Sharma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stu2 = User(
            email="stu2.r2@hostelcare.test",
            full_name="Rohan Verma",
            password_hash=hash_password("StudentPass123!"),
            role="student",
            status="active",
        )
        stf1 = User(
            email="stf1.r2@hostelcare.test",
            full_name="Ramesh Babu",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            status="active",
        )
        stf2 = User(
            email="stf2.r2@hostelcare.test",
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
                StaffProfile(user_id=stf1.id, staff_code="STF-1001", trade="Electrician"),
                StaffProfile(user_id=stf2.id, staff_code="STF-1002", trade="Plumber"),
                RoomAllocation(
                    student_user_id=stu1.id,
                    room_id=room.id,
                    bed_number=1,
                    start_date=db.session.execute(text("SELECT current_date - 2")).scalar_one(),
                    allocated_by=admin.id,
                ),
            ]
        )
        db.session.commit()
        return {
            "admin": admin.id,
            "stu1": stu1.id,
            "stu2": stu2.id,
            "stf1": stf1.id,
            "stf2": stf2.id,
            "stf1_public_id": str(stf1.public_id),
        }


def _login(client, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.get_json()["csrf_token"]}


def test_r2_key_validation_and_production_config_checks(monkeypatch):
    with pytest.raises(Exception, match="Invalid attachment storage path"):
        validate_safe_object_key("../secret.png")
    with pytest.raises(Exception, match="Invalid attachment storage path"):
        validate_safe_object_key("/abs/path.png")
    with pytest.raises(Exception, match="Invalid R2 storage reference"):
        extract_r2_key("2026/11/abc.png")
    assert extract_r2_key("r2://complaints/2026/11/abc.png") == "complaints/2026/11/abc.png"

    monkeypatch.setattr("app.config.ProductionConfig.SECRET_KEY", "strong-prod-secret-key-xyz123")
    monkeypatch.setattr(
        "app.config.ProductionConfig.SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg://hostelcare_app:pw@localhost:5432/hostelcare_test",
    )
    monkeypatch.setattr("app.config.ProductionConfig.COMPLAINT_ATTACHMENT_STORAGE_BACKEND", "r2")
    monkeypatch.setattr("app.config.ProductionConfig.R2_BUCKET_NAME", "")
    with pytest.raises(RuntimeError, match="R2_BUCKET_NAME"):
        create_app("production")


def test_r2_upload_retrieval_rbac_and_legacy_local_compatibility(r2_db_app, mock_r2):
    fake_client, boto_kwargs = mock_r2
    actor_ids = _seed_actors(r2_db_app)

    stu1 = r2_db_app.test_client()
    stu2 = r2_db_app.test_client()
    stf1 = r2_db_app.test_client()
    stf2 = r2_db_app.test_client()
    admin = r2_db_app.test_client()

    stu1_hdr = _login(stu1, "stu1.r2@hostelcare.test", "StudentPass123!")
    _login(stu2, "stu2.r2@hostelcare.test", "StudentPass123!")
    _login(stf1, "stf1.r2@hostelcare.test", "StaffPass123!")
    _login(stf2, "stf2.r2@hostelcare.test", "StaffPass123!")
    adm_hdr = _login(admin, "warden.r2@hostelcare.test", "AdminPass123!")

    # Upload 1 JPEG photo to R2
    jpg_bytes = _make_image_bytes("JPEG")
    resp = stu1.post(
        "/api/v1/student/complaints",
        headers=stu1_hdr,
        data={
            "title": "Ceiling fan sparks",
            "description": "Ceiling fan switch emits sparks.",
            "priority": "high",
            "location_type": "room",
            "photos": (io.BytesIO(jpg_bytes), "../../my_personal_photo.jpg", "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    comp = resp.get_json()["complaint"]
    att = comp["attachments"][0]
    att_url = att["url"]

    # Ensure frontend serialization never leaks R2 key or credentials
    dumped = json.dumps(comp)
    assert "r2://" not in dumped
    assert "r2-test-secret-key" not in dumped
    assert "r2-test-key-id" not in dumped
    assert "hostelcare-private-test" not in dumped
    assert boto_kwargs[0]["endpoint_url"] == "https://cfacct123456.r2.cloudflarestorage.com"
    assert boto_kwargs[0]["region_name"] == "auto"
    assert fake_client.put_calls[0]["extra"] == {}  # no public ACLs

    with r2_db_app.app_context():
        db_att = db.session.execute(select(ComplaintAttachment)).scalar_one()
        assert db_att.storage_path.startswith("r2://complaints/")
        assert "my_personal_photo" not in db_att.storage_path
        r2_key = extract_r2_key(db_att.storage_path)
        assert r2_key in fake_client.objects

    # Assign stf1
    assign_resp = admin.post(
        f"/api/v1/admin/complaints/{comp['referenceNo']}/assign",
        headers=adm_hdr,
        json={"staff_id": actor_ids["stf1_public_id"], "instructions": "Inspect switch."},
    )
    assert assign_resp.status_code == 200

    # RBAC enforcement
    anon = r2_db_app.test_client()
    assert anon.get(att_url).status_code == 401
    assert stu2.get(att_url).status_code == 403
    assert stf2.get(att_url).status_code == 403

    for allowed_client in (stu1, stf1, admin):
        dl = allowed_client.get(att_url)
        assert dl.status_code == 200
        assert dl.mimetype == "image/jpeg"
        assert dl.headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'none'" in dl.headers["Content-Security-Policy"]
        assert dl.headers["Cache-Control"] == "no-store"

    # Legacy local attachment path still works seamlessly even when backend == "r2"
    local_png = _make_image_bytes("PNG", color=(90, 20, 140))
    rel_local = "2026/10/legacy_fixture.png"
    local_target = Path(r2_db_app.config["COMPLAINT_ATTACHMENT_DIR"]) / rel_local
    local_target.parent.mkdir(parents=True, exist_ok=True)
    local_target.write_bytes(local_png)
    with r2_db_app.app_context():
        c_row = db.session.execute(select(Complaint)).scalar_one()
        legacy_att = ComplaintAttachment(
            complaint_id=c_row.id,
            storage_path=rel_local,
            original_filename="legacy.png",
            file_size_bytes=len(local_png),
            mime_type="image/png",
            checksum_sha256=hashlib.sha256(local_png).hexdigest(),
        )
        db.session.add(legacy_att)
        db.session.commit()
        legacy_url = f"/api/v1/complaints/{c_row.reference_no}/attachments/{legacy_att.public_id}"

    legacy_dl = stu1.get(legacy_url)
    assert legacy_dl.status_code == 200
    assert legacy_dl.data == local_png

    # Missing R2 object returns safe 404 without exposing R2 internals
    fake_client.objects.pop(r2_key)
    missing_dl = stu1.get(att_url)
    assert missing_dl.status_code == 404
    err = missing_dl.get_json()["error"]
    assert err["code"] == "attachment_file_missing"
    assert "hostelcare-private-test" not in err["message"]


def test_r2_error_handling_timeouts_bad_creds_and_db_rollback_cleanup(
    r2_db_app, mock_r2, monkeypatch
):
    fake_client, _ = mock_r2
    _seed_actors(r2_db_app)
    stu1 = r2_db_app.test_client()
    hdr = _login(stu1, "stu1.r2@hostelcare.test", "StudentPass123!")

    # 1. Timeout on upload leaves zero DB rows
    fake_client.fail_put_exc = ConnectTimeoutError(
        endpoint_url="https://cfacct123456.r2.cloudflarestorage.com"
    )
    r_timeout = stu1.post(
        "/api/v1/student/complaints",
        headers=hdr,
        data={
            "title": "Timeout test",
            "description": "Testing R2 timeout handling safely.",
            "location_type": "room",
            "photos": (io.BytesIO(_make_image_bytes("PNG")), "t.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert r_timeout.status_code == 500
    assert r_timeout.get_json()["error"]["code"] == "attachment_storage_error"
    assert "cfacct123456" not in r_timeout.get_json()["error"]["message"]
    fake_client.fail_put_exc = None

    # 2. Invalid R2 credentials error on upload handled cleanly
    fake_client.fail_put_exc = ClientError(
        {
            "Error": {"Code": "InvalidAccessKeyId", "Message": "Bad key"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "PutObject",
    )
    r_badcred = stu1.post(
        "/api/v1/student/complaints",
        headers=hdr,
        data={
            "title": "Bad creds test",
            "description": "Testing invalid R2 credentials safely.",
            "location_type": "room",
            "photos": (io.BytesIO(_make_image_bytes("PNG")), "c.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert r_badcred.status_code == 500
    assert r_badcred.get_json()["error"]["code"] == "attachment_storage_error"
    fake_client.fail_put_exc = None

    # 3. DB commit failure AFTER successful R2 upload deletes orphaned R2 object!
    def fail_commit():
        raise RuntimeError("Simulated DB commit failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    r_db_fail = stu1.post(
        "/api/v1/student/complaints",
        headers=hdr,
        data={
            "title": "DB rollback cleanup test",
            "description": "Testing R2 cleanup on DB failure.",
            "location_type": "room",
            "photos": (io.BytesIO(_make_image_bytes("WEBP")), "rb.webp", "image/webp"),
        },
        content_type="multipart/form-data",
    )
    assert r_db_fail.status_code == 500
    monkeypatch.undo()
    assert len(fake_client.put_calls) == 3
    assert len(fake_client.delete_calls) == 1
    assert fake_client.objects == {}
    with r2_db_app.app_context():
        assert db.session.execute(select(func.count(Complaint.id))).scalar_one() == 0
        assert db.session.execute(select(func.count(ComplaintAttachment.id))).scalar_one() == 0

    # 4. ReadTimeoutError during retrieval returns safe 502 error
    storage = R2AttachmentStorage(
        bucket_name="b",
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key_id="k",
        secret_access_key="s",
        client=fake_client,
    )
    fake_client.fail_get_exc = ReadTimeoutError(
        endpoint_url="https://acct.r2.cloudflarestorage.com"
    )
    with pytest.raises(Exception) as exc_info:
        storage.retrieve("r2://complaints/2026/11/x.png")
    assert exc_info.value.status == 502


def test_historical_attachment_migration_dry_run_apply_failures_and_idempotency(r2_db_app, mock_r2):
    fake_client, _ = mock_r2
    _seed_actors(r2_db_app)

    # Seed local complaint with 2 attachments in local mode
    r2_db_app.config["COMPLAINT_ATTACHMENT_STORAGE_BACKEND"] = "local"
    stu1 = r2_db_app.test_client()
    hdr = _login(stu1, "stu1.r2@hostelcare.test", "StudentPass123!")

    p1 = _make_image_bytes("PNG", color=(1, 10, 100))
    p2 = _make_image_bytes("JPEG", color=(100, 10, 1))
    up = stu1.post(
        "/api/v1/student/complaints",
        headers=hdr,
        data={
            "title": "Historical local photos",
            "description": "Submitted while local storage was active.",
            "location_type": "room",
            "photos": [
                (io.BytesIO(p1), "img1.png", "image/png"),
                (io.BytesIO(p2), "img2.jpg", "image/jpeg"),
            ],
        },
        content_type="multipart/form-data",
    )
    assert up.status_code == 201
    comp = up.get_json()["complaint"]

    with r2_db_app.app_context():
        before_rows = (
            db.session.execute(select(ComplaintAttachment).order_by(ComplaintAttachment.id.asc()))
            .scalars()
            .all()
        )
        before_snap = [
            (
                a.id,
                str(a.public_id),
                a.complaint_id,
                a.storage_path,
                a.original_filename,
                a.file_size_bytes,
                a.mime_type,
                a.checksum_sha256,
                a.created_at,
            )
            for a in before_rows
        ]
        assert all(not a.storage_path.startswith("r2://") for a in before_rows)

    cli = r2_db_app.test_cli_runner()

    # 1. Dry-run makes zero uploads and zero DB modifications
    dry = cli.invoke(args=["migrate-attachments-r2"])
    assert dry.exit_code == 0, dry.output
    assert "Dry-run complete: 2 ready to upload, 0 already on R2" in dry.output
    assert fake_client.put_calls == []
    assert fake_client.objects == {}
    with r2_db_app.app_context():
        rows_after_dry = (
            db.session.execute(select(ComplaintAttachment).order_by(ComplaintAttachment.id.asc()))
            .scalars()
            .all()
        )
        assert [a.storage_path for a in rows_after_dry] == [s[3] for s in before_snap]

    # 2. Apply uploads both files, preserves metadata & local files, updates storage_path only
    app_res = cli.invoke(args=["migrate-attachments-r2", "--apply"])
    assert app_res.exit_code == 0, app_res.output
    assert "Apply complete: uploaded=2, reused_existing=0, already_on_r2=0." in app_res.output
    assert len(fake_client.put_calls) == 2

    with r2_db_app.app_context():
        after_rows = (
            db.session.execute(select(ComplaintAttachment).order_by(ComplaintAttachment.id.asc()))
            .scalars()
            .all()
        )
        for idx, row in enumerate(after_rows):
            snap = before_snap[idx]
            assert row.id == snap[0]
            assert str(row.public_id) == snap[1]
            assert row.complaint_id == snap[2]
            assert row.storage_path == f"r2://complaints/{snap[3]}"
            assert row.original_filename == snap[4]
            assert row.file_size_bytes == snap[5]
            assert row.mime_type == snap[6]
            assert row.checksum_sha256 == snap[7]
            assert row.created_at == snap[8]
            # Original local file untouched
            assert (Path(r2_db_app.config["COMPLAINT_ATTACHMENT_DIR"]) / snap[3]).is_file()

    # Verify migrated attachments stream cleanly via authenticated endpoint from R2
    r2_db_app.config["COMPLAINT_ATTACHMENT_STORAGE_BACKEND"] = "r2"
    for att_meta in comp["attachments"]:
        dl = stu1.get(att_meta["url"])
        assert dl.status_code == 200

    # 3. Re-running --apply is idempotent (0 new uploads!)
    puts_before = len(fake_client.put_calls)
    rerun = cli.invoke(args=["migrate-attachments-r2", "--apply"])
    assert rerun.exit_code == 0, rerun.output
    assert "Apply complete: uploaded=0, reused_existing=0, already_on_r2=2." in rerun.output
    assert len(fake_client.put_calls) == puts_before

    # 4. Missing source file fails safely with exact attachment id
    p3 = _make_image_bytes("PNG", color=(50, 60, 70))
    missing_rel = "2026/11/missing_binary.png"
    with r2_db_app.app_context():
        c_row = db.session.execute(select(Complaint)).scalar_one()
        bad_att = ComplaintAttachment(
            complaint_id=c_row.id,
            storage_path=missing_rel,
            original_filename="missing.png",
            file_size_bytes=len(p3),
            mime_type="image/png",
            checksum_sha256=hashlib.sha256(p3).hexdigest(),
        )
        db.session.add(bad_att)
        db.session.commit()
        bad_id = bad_att.id

    fail_res = cli.invoke(args=["migrate-attachments-r2"])
    assert fail_res.exit_code != 0
    assert f"id={bad_id}" in fail_res.output
