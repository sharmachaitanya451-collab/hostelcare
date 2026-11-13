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
