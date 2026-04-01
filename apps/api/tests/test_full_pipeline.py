from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_phase3_to_phase7_pipeline() -> None:
    # Data sync bootstrap
    assert client.post("/api/data/sync/master", json={"force_full": False}).status_code == 200
    assert client.post("/api/data/sync/realtime", json={"symbols": ["000001", "600000"]}).status_code == 200

    # Screener and strategies
    run = client.post("/api/screener/run", json={"mode": "intraday", "filters": {"top_n": 20, "min_change_pct": -5}}).json()
    assert run["status"] == "completed"
    candidates = client.get("/api/candidates/top100").json()["items"]
    assert len(candidates) >= 1

    strategy_list = client.get("/api/strategy/list").json()["items"]
    assert len(strategy_list) >= 20
    eval_res = client.post(
        "/api/strategy/evaluate",
        json={
            "symbol": candidates[0]["symbol"],
            "context": {"quote": {"change_pct": 3.2, "volume": 10000}, "market_state": "bullish"},
        },
    ).json()
    assert len(eval_res["items"]) >= 20

    # Recommendation
    rec_run = client.post("/api/recommendation/run", json={"market_state": "neutral", "llm_enabled": True}).json()
    assert "recommendation_run_id" in rec_run
    rec_top = client.get("/api/recommendation/top?limit=10").json()["items"]
    assert len(rec_top) >= 1

    # Backtest
    bt = client.post("/api/backtest/run", json={"name": "smoke-bt", "initial_cash": 1000000}).json()
    assert bt["status"] == "completed"
    assert client.get(f"/api/backtest/report/{bt['job_id']}").status_code == 200

    # Paper trading and risk
    preview = client.post(
        "/api/paper/order/preview",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "B"},
    ).json()
    assert preview["decision"] in {"pass", "pass_with_warning", "manual_review_required"}
    order = client.post(
        "/api/paper/orders",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "B"},
    ).json()
    assert "order_id" in order
    assert client.get("/api/paper/positions").status_code == 200

    # Live trading and kill switch
    enable = client.post("/api/risk/kill-switch/enable", json={"reason": "test"}).json()
    assert enable["enabled"] is True
    live_order = client.post(
        "/api/live/order",
        json={"symbol": "600000", "side": "buy", "price": 11, "quantity": 100, "recommendation_level": "A"},
    ).json()
    assert live_order["status"] in {"rejected", "filled", "accepted"}
    disable = client.post("/api/risk/kill-switch/disable", json={"reason": "test done"}).json()
    assert disable["enabled"] is False
    assert client.get("/api/live/broker/status").status_code == 200

    # Notification, settings, init, replay, admin
    nid = client.post("/api/notifications/test", json={"title": "pipeline", "body": "ok", "dedupe_key": "pipeline-1"}).json()["id"]
    assert nid > 0
    assert client.post("/api/notifications/mark-read", json={"ids": [nid]}).status_code == 200
    assert client.post("/api/settings/update", json={"config_key": "recommendation", "config_value": {"llm_enabled": True}}).status_code == 200
    assert client.get("/api/init/status").status_code == 200
    assert client.post("/api/init/run-step", json={"step": "env_check"}).status_code == 200
    assert client.get("/api/replay/days").status_code == 200
    assert client.get("/api/admin/system-health").status_code == 200

