import pytest
from fastapi.testclient import TestClient

from app.api.routes import health as health_module
from app.main import app


def test_health_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ready() -> bool:
        return True

    monkeypatch.setattr(health_module, "database_is_ready", ready)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(health_module, "database_is_ready", unavailable)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
