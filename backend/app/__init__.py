"""HostelCare Flask application factory."""

import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from app.config import CONFIGS  # noqa: E402
from app.core.errors import register_error_handlers  # noqa: E402
from app.core.logging import init_logging  # noqa: E402
from app.core.routes import bp as core_bp  # noqa: E402
from app.extensions import db, migrate  # noqa: E402


def create_app(config_name: str | None = None) -> Flask:
    name = config_name or os.environ.get("FLASK_ENV", "development")
    config_cls = CONFIGS[name]
    if hasattr(config_cls, "validate"):
        config_cls.validate()

    app = Flask(__name__)
    app.config.from_object(config_cls)

    init_logging(app)
    register_error_handlers(app)

    # The database is optional in Phase 0: the app (and /healthz) must boot before
    # DATABASE_URL exists. /readyz reports "not_configured" in that case.
    if app.config.get("SQLALCHEMY_DATABASE_URI"):
        db.init_app(app)
        migrate.init_app(app, db)

    app.register_blueprint(core_bp)
    return app
