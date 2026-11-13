"""Environment-based configuration. All values come from environment variables."""

import os


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or None
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # request size cap

    HOSTEL_NAME = os.environ.get("HOSTEL_NAME", "Your Hostel Name")
    HOSTEL_BLOCKS = _csv(os.environ.get("HOSTEL_BLOCKS", "A,B,C"))
    HOSTEL_ROOM_PATTERN = os.environ.get("HOSTEL_ROOM_PATTERN", r"^[0-9]{3}$")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key"  # noqa: S105
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or None


class ProductionConfig(BaseConfig):
    DEBUG = False

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY or cls.SECRET_KEY.startswith("change-me"):
            raise RuntimeError("SECRET_KEY must be set to a strong value in production")
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL must be set in production")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
