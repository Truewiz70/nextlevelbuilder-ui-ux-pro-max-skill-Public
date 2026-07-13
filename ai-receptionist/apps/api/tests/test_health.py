from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_healthz_reports_ok() -> None:
    app = create_app(Settings(app_env="test"))
    # Liveness must not touch external dependencies, so no DB/Redis is needed.
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_docs_disabled_in_production() -> None:
    app = create_app(Settings(app_env="production"))
    assert app.docs_url is None
