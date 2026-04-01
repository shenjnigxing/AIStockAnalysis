from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    assert "version" in response.json()


def test_system_status() -> None:
    response = client.get("/api/system/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "app_name" in payload

