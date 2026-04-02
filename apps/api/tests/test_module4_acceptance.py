from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_module4_risk_config_and_kill_switch() -> None:
    config_get = client.get("/api/risk/config")
    assert config_get.status_code == 200
    assert "max_single_order_amount" in config_get.json()["config"]

    config_update = client.post(
        "/api/risk/config",
        json={
            "max_single_order_amount": 120000,
            "max_position_ratio": 0.35,
            "max_daily_loss": 18000,
            "max_daily_trade_count": 30,
            "min_recommendation_level": "B",
        },
    )
    assert config_update.status_code == 200
    assert config_update.json()["config"]["max_single_order_amount"] == 120000

    enable = client.post("/api/risk/kill-switch/enable", json={"reason": "module4-test"})
    assert enable.status_code == 200
    assert enable.json()["enabled"] is True

    status = client.get("/api/risk/status")
    assert status.status_code == 200
    assert status.json()["kill_switch_enabled"] is True

    disable = client.post("/api/risk/kill-switch/disable", json={"reason": "module4-test-done"})
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False


def test_module4_live_preview_place_and_sync() -> None:
    # Turn on kill switch first to verify hard reject.
    assert client.post("/api/risk/kill-switch/enable", json={"reason": "reject-check"}).status_code == 200
    preview_reject = client.post(
        "/api/live/order/preview",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert preview_reject.status_code == 200
    assert preview_reject.json()["decision"] == "reject"

    assert client.post("/api/risk/kill-switch/disable", json={"reason": "allow-live"}).status_code == 200
    preview = client.post(
        "/api/live/order/preview",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert preview.status_code == 200
    assert preview.json()["decision"] in {"pass", "pass_with_warning", "manual_review_required", "reject"}

    place = client.post(
        "/api/live/order",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert place.status_code == 200
    assert place.json()["status"] in {"filled", "rejected", "previewed", "accepted"}

    assert client.post("/api/live/sync/account").status_code == 200
    assert client.get("/api/live/broker/status").status_code == 200
    assert client.get("/api/live/orders").status_code == 200
    assert client.get("/api/live/trades").status_code == 200
    assert client.get("/api/live/positions").status_code == 200
    assert client.get("/api/live/assets").status_code == 200

    events = client.get("/api/risk/events")
    assert events.status_code == 200
    assert "items" in events.json()
