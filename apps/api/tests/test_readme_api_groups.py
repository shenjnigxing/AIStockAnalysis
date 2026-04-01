from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_readme_required_endpoints_reachable() -> None:
    paths = [
        "/health",
        "/version",
        "/api/system/status",
        "/api/init/status",
        "/api/data/jobs",
        "/api/screener/presets",
        "/api/candidates/top100",
        "/api/strategy/list",
        "/api/recommendation/top?limit=5",
        "/api/recommendation/history",
        "/api/backtest/jobs",
        "/api/paper/orders",
        "/api/risk/status",
        "/api/live/orders",
        "/api/notifications",
        "/api/settings",
        "/api/replay/days",
        "/api/admin/system-health",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
