"""HostelCare Flask application factory."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import app.models  # noqa: E402, F401
from app.analytics.routes import bp as analytics_bp  # noqa: E402
from app.auth.cli import create_admin_cmd, purge_reset_tokens_cmd  # noqa: E402
from app.auth.routes import bp as auth_bp  # noqa: E402
from app.auth.security import init_auth_security  # noqa: E402
from app.complaints.routes import bp as complaints_bp  # noqa: E402
from app.config import CONFIGS  # noqa: E402
from app.core.db_cli import db_cli  # noqa: E402
from app.core.errors import register_error_handlers  # noqa: E402
from app.core.logging import init_logging  # noqa: E402
from app.core.routes import bp as core_bp  # noqa: E402
from app.extensions import db, migrate  # noqa: E402
from app.fines.routes import bp as fines_bp  # noqa: E402
from app.notifications.routes import bp as notifications_bp  # noqa: E402
from app.rooms.routes import bp as rooms_bp  # noqa: E402


def create_app(config_name: str | None = None) -> Flask:
    name = config_name or os.environ.get("FLASK_ENV", "development")
    config_cls = CONFIGS[name]
    if hasattr(config_cls, "validate"):
        config_cls.validate()

    app = Flask(__name__)
    app.config.from_object(config_cls)

    init_logging(app)
    register_error_handlers(app)

    # The database is optional in early phases: the app (and /healthz) must boot before
    # DATABASE_URL exists. /readyz reports "not_configured" in that case.
    if app.config.get("SQLALCHEMY_DATABASE_URI"):
        db.init_app(app)
        # Migrate uses MIGRATION_DATABASE_URI if present, or falls back to db
        migration_uri = app.config.get("MIGRATION_DATABASE_URI")
        if migration_uri:
            # Flask-Migrate is initialized; Alembic reads MIGRATION_DATABASE_URI
            migrate.init_app(app, db)
        else:
            migrate.init_app(app, db)

    init_auth_security(app)
    app.register_blueprint(core_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(fines_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(rooms_bp)
    app.cli.add_command(db_cli)
    app.cli.add_command(create_admin_cmd)
    app.cli.add_command(purge_reset_tokens_cmd)

    if app.config.get("PROXY_FIX_ENABLED"):
        hop_count = int(app.config.get("TRUSTED_PROXY_COUNT", 1))
        if hop_count > 0:
            app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
                app.wsgi_app,
                x_for=hop_count,
                x_proto=hop_count,
                x_host=hop_count,
                x_prefix=hop_count,
            )

    if app.config.get("SERVE_FRONTEND"):
        _register_spa_routes(app)

    return app


def _register_spa_routes(app: Flask) -> None:
    """Serve the compiled React SPA cleanly on a single-service deployment."""
    dist_raw = app.config.get("FRONTEND_DIST_DIR")
    if not dist_raw:
        return
    dist_dir = Path(str(dist_raw)).resolve()
    if not (dist_dir / "index.html").is_file():
        app.logger.warning("SERVE_FRONTEND enabled, but %s/index.html not found.", dist_dir)
        return

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def _serve_spa(path: str):
        clean_path = path.lstrip("/")
        if (
            clean_path == "api"
            or clean_path.startswith("api/")
            or clean_path in ("healthz", "readyz")
        ):
            abort(404)

        if clean_path:
            candidate = (dist_dir / clean_path).resolve()
            if candidate.is_relative_to(dist_dir) and candidate.is_file():
                return send_from_directory(dist_dir, clean_path)

        resp = send_from_directory(dist_dir, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp
