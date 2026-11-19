"""Environment-based configuration. All values come from environment variables."""

import os
from datetime import timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _normalize_database_url(raw: str | None) -> str | None:
    """Normalize PostgreSQL URLs to the installed SQLAlchemy psycopg 3 dialect."""
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("DATABASE_URL"))
    MIGRATION_DATABASE_URI = _normalize_database_url(os.environ.get("MIGRATION_DATABASE_URL"))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    SERVE_FRONTEND = _bool(os.environ.get("SERVE_FRONTEND"), default=False)
    FRONTEND_DIST_DIR = os.environ.get(
        "FRONTEND_DIST_DIR",
        str(BACKEND_ROOT.parent / "frontend" / "dist"),
    )
    PROXY_FIX_ENABLED = _bool(os.environ.get("PROXY_FIX_ENABLED"), default=False)
    TRUSTED_PROXY_COUNT = max(0, int(os.environ.get("TRUSTED_PROXY_COUNT", "1")))
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", str(20 * 1024 * 1024))
    )  # 20 MB request cap (accommodates 3x 5 MB photos + multipart overhead)

    # Complaint Photo Attachments (Private Filesystem Storage)
    COMPLAINT_ATTACHMENT_DIR = os.environ.get(
        "COMPLAINT_ATTACHMENT_DIR",
        str(BACKEND_ROOT / "uploads" / "complaints"),
    )
    COMPLAINT_MAX_ATTACHMENTS = int(os.environ.get("COMPLAINT_MAX_ATTACHMENTS", "3"))
    COMPLAINT_MAX_ATTACHMENT_BYTES = int(
        os.environ.get("COMPLAINT_MAX_ATTACHMENT_BYTES", str(5 * 1024 * 1024))
    )

    # Complaint SLA Targets (resolution hours by priority)
    COMPLAINT_SLA_HOURS = {
        "high": 24,
        "medium": 72,
        "low": 168,
    }

    HOSTEL_NAME = os.environ.get("HOSTEL_NAME", "Your Hostel Name")
    HOSTEL_BLOCKS = _csv(os.environ.get("HOSTEL_BLOCKS", "A,B,C"))
    HOSTEL_ROOM_PATTERN = os.environ.get("HOSTEL_ROOM_PATTERN", r"^[0-9]{3}$")

    # Session and Cookie Security
    SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "hostelcare_session")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), default=False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "12"))
    )
    CSRF_COOKIE_NAME = "hc_csrf_token"
    CSRF_ENABLED = True
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    ALLOWED_ORIGINS = _csv(
        os.environ.get(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000,http://127.0.0.1:5000",
        )
    )

    # Authentication & Rate Limiting
    AUTH_MAX_FAILED_LOGINS = int(os.environ.get("AUTH_MAX_FAILED_LOGINS", "5"))
    AUTH_LOCKOUT_MINUTES = int(os.environ.get("AUTH_LOCKOUT_MINUTES", "15"))
    AUTH_LOGIN_IP_LIMIT_15M = int(os.environ.get("AUTH_LOGIN_IP_LIMIT_15M", "15"))
    AUTH_REGISTER_IP_LIMIT_1H = int(os.environ.get("AUTH_REGISTER_IP_LIMIT_1H", "15"))
    AUTH_RESET_USER_LIMIT_1H = int(os.environ.get("AUTH_RESET_USER_LIMIT_1H", "3"))
    AUTH_RESET_IP_LIMIT_1H = int(os.environ.get("AUTH_RESET_IP_LIMIT_1H", "10"))
    AUTH_RESET_INVALID_IP_LIMIT_15M = int(os.environ.get("AUTH_RESET_INVALID_IP_LIMIT_15M", "10"))

    # Provider-Independent Mailer Configuration (ADR-023)
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "console").strip().lower()
    MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@hostelcare.local")
    MAIL_SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "localhost")
    MAIL_SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "587"))
    MAIL_SMTP_USERNAME = os.environ.get("MAIL_SMTP_USERNAME", "")
    MAIL_SMTP_PASSWORD = os.environ.get("MAIL_SMTP_PASSWORD", "")
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS"), default=True)
    MAIL_TIMEOUT_SECONDS = int(os.environ.get("MAIL_TIMEOUT_SECONDS", "10"))

    # Razorpay Online Payments (Test Mode Only)
    RAZORPAY_MODE = os.environ.get("RAZORPAY_MODE", "test").strip().lower()
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()
    RAZORPAY_API_BASE_URL = os.environ.get(
        "RAZORPAY_API_BASE_URL", "https://api.razorpay.com/v1"
    ).rstrip("/")
    RAZORPAY_TIMEOUT_SECONDS = int(os.environ.get("RAZORPAY_TIMEOUT_SECONDS", "15"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key"  # noqa: S105
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("TEST_DATABASE_URL"))
    MIGRATION_DATABASE_URI = _normalize_database_url(os.environ.get("TEST_MIGRATION_DATABASE_URL"))
    SESSION_COOKIE_SECURE = False
    SERVE_FRONTEND = False
    PROXY_FIX_ENABLED = False
    MAIL_BACKEND = "console"
    COMPLAINT_ATTACHMENT_DIR = str(BACKEND_ROOT / "uploads" / "complaints_test")


class ProductionConfig(BaseConfig):
    DEBUG = False
    PROXY_FIX_ENABLED = _bool(os.environ.get("PROXY_FIX_ENABLED"), default=True)
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), default=True)
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")

    @classmethod
    def validate(cls) -> None:
        if (
            not cls.SECRET_KEY
            or cls.SECRET_KEY.startswith("change-me")
            or cls.SECRET_KEY == "dev-secret-key-change-in-production"  # noqa: S105
        ):
            raise RuntimeError("SECRET_KEY must be set to a strong value in production")
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL must be set in production")
        if cls.RAZORPAY_MODE != "test" or cls.RAZORPAY_KEY_ID.startswith("rzp_live_"):
            raise RuntimeError("HostelCare permits Razorpay Test Mode only")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
