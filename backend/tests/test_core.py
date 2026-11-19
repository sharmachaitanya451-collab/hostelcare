import pytest

from app import create_app


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_readyz_reports_unconfigured_database(app, client):
    app.config["SQLALCHEMY_DATABASE_URI"] = None
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.get_json()["database"] == "not_configured"


def test_meta_exposes_only_placeholders(client):
    data = client.get("/api/v1/meta").get_json()
    assert set(data) == {"hostel_name", "blocks"}
    assert isinstance(data["blocks"], list)


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_production_requires_secret_and_database(monkeypatch):
    monkeypatch.setattr("app.config.ProductionConfig.SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        create_app("production")


def test_normalize_database_url_converts_postgres_schemes():
    from app.config import _normalize_database_url

    assert _normalize_database_url("postgres://u:p@host:5432/db") == (
        "postgresql+psycopg://u:p@host:5432/db"
    )
    assert _normalize_database_url("postgresql://u:p@host:5432/db") == (
        "postgresql+psycopg://u:p@host:5432/db"
    )
    assert _normalize_database_url("postgresql+psycopg://u:p@host:5432/db") == (
        "postgresql+psycopg://u:p@host:5432/db"
    )
    assert _normalize_database_url("") is None


def test_production_spa_serving_and_proxy_fix(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<html><body>HostelCare SPA</body></html>", encoding="utf-8"
    )
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    monkeypatch.setattr("app.config.ProductionConfig.SECRET_KEY", "test-prod-secret-value-123456")
    monkeypatch.setattr(
        "app.config.ProductionConfig.SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg://hostelcare_app:pw@localhost:5432/hostelcare_test",
    )
    monkeypatch.setattr("app.config.ProductionConfig.SERVE_FRONTEND", True)
    monkeypatch.setattr("app.config.ProductionConfig.FRONTEND_DIST_DIR", str(dist_dir))
    monkeypatch.setattr("app.config.ProductionConfig.PROXY_FIX_ENABLED", True)

    prod_app = create_app("production")
    assert prod_app.debug is False
    c = prod_app.test_client()

    # SPA routes & static assets
    assert b"HostelCare SPA" in c.get("/").data
    assert b"HostelCare SPA" in c.get("/student/dashboard").data
    assert b"console.log" in c.get("/assets/app.js").data

    # Unknown API routes still return JSON 404, not index.html
    api_404 = c.get("/api/v1/does-not-exist")
    assert api_404.status_code == 404
    assert api_404.get_json()["error"]["code"] == "not_found"

    # ProxyFix wraps wsgi_app and normalizes forwarded proto/client IP
    from werkzeug.middleware.proxy_fix import ProxyFix

    assert isinstance(prod_app.wsgi_app, ProxyFix)
    captured = {}
    orig_inner = prod_app.wsgi_app.app

    def _spy(environ, start_response):
        captured["remote_addr"] = environ.get("REMOTE_ADDR")
        captured["scheme"] = environ.get("wsgi.url_scheme")
        return orig_inner(environ, start_response)

    prod_app.wsgi_app.app = _spy
    assert (
        c.get(
            "/healthz",
            headers={"X-Forwarded-For": "203.0.113.5", "X-Forwarded-Proto": "https"},
        ).status_code
        == 200
    )
    assert captured == {"remote_addr": "203.0.113.5", "scheme": "https"}
