"""Uniform JSON error envelope: {"error": {"code", "message"}}."""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def error_response(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    from app.auth.service import AuthServiceError

    @app.errorhandler(AuthServiceError)
    def _auth_service_error(exc: AuthServiceError):
        return error_response(exc.code, exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        return error_response(
            (exc.name or "error").lower().replace(" ", "_"),
            exc.description or exc.name,
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        app.logger.exception("Unhandled exception")
        return error_response("internal_error", "An unexpected error occurred.", 500)
