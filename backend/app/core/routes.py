from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db

bp = Blueprint("core", __name__)


@bp.get("/healthz")
def healthz():
    """Liveness: the process is up. Never touches the database."""
    return jsonify({"status": "ok"})


@bp.get("/readyz")
def readyz():
    """Readiness: the database is configured and reachable."""
    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return jsonify({"status": "unavailable", "database": "not_configured"}), 503
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        current_app.logger.exception("Readiness check failed")
        return jsonify({"status": "unavailable", "database": "unreachable"}), 503
    return jsonify({"status": "ok", "database": "ok"})


@bp.get("/api/v1/meta")
def meta():
    """Public, non-sensitive deployment info for the frontend."""
    return jsonify(
        {
            "hostel_name": current_app.config["HOSTEL_NAME"],
            "blocks": current_app.config["HOSTEL_BLOCKS"],
        }
    )
