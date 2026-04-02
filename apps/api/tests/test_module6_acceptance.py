from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _bootstrap_candidates() -> None:
    assert client.post("/api/data/sync/master", json={"force_full": False}).status_code == 200
    assert client.post("/api/data/sync/realtime", json={"symbols": ["000001", "600000", "600519"]}).status_code == 200
    run = client.post("/api/screener/run", json={"mode": "intraday", "filters": {"top_n": 20, "min_change_pct": -10}})
    assert run.status_code == 200


def test_module6_llm_provider_integration_and_degrade() -> None:
    _bootstrap_candidates()

    run = client.post(
        "/api/recommendation/run",
        json={"market_state": "neutral", "llm_enabled": True, "llm_provider": "openai_compat"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["llm_provider"] == "openai_compat"
    assert isinstance(body["llm_degraded_count"], int)
    assert body["llm_degraded_count"] >= 1

    latest = client.get("/api/recommendation/latest")
    assert latest.status_code == 200
    items = latest.json()["items"]
    assert len(items) >= 1
    assert all(isinstance(row["llm_score_adjustment"], (int, float)) for row in items)
    assert any(str(row["llm_explanation"]).strip() for row in items)


def test_module6_live_gray_and_broker_capabilities() -> None:
    cfg = client.post(
        "/api/risk/live-gray/config",
        json={
            "live_gray_mode_enabled": True,
            "live_gray_max_notional": 10000,
            "live_gray_whitelist": ["000001"],
            "live_gray_blocklist": ["600519"],
            "live_auto_submit": False,
        },
    )
    assert cfg.status_code == 200
    assert cfg.json()["config"]["live_gray_mode_enabled"] is True

    blocked = client.post(
        "/api/live/order/preview",
        json={"symbol": "600519", "side": "buy", "price": 100, "quantity": 100, "recommendation_level": "A"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["decision"] == "reject"

    manual = client.post(
        "/api/live/order/preview",
        json={"symbol": "600000", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert manual.status_code == 200
    assert manual.json()["decision"] in {"manual_review_required", "pass_with_warning"}

    placed_hold = client.post(
        "/api/live/order",
        json={"symbol": "600000", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert placed_hold.status_code == 200
    assert placed_hold.json()["status"] in {"previewed", "rejected"}

    placed_ack = client.post(
        "/api/live/order",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A", "manual_ack": True},
    )
    assert placed_ack.status_code == 200
    assert placed_ack.json()["status"] in {"filled", "accepted", "previewed"}

    caps_default = client.get("/api/live/broker/capabilities")
    caps_em = client.get("/api/live/broker/capabilities?provider=eastmoney")
    assert caps_default.status_code == 200
    assert caps_em.status_code == 200
    assert caps_default.json()["provider"] == "mock"
    assert caps_default.json()["ready"] is True
    assert caps_em.json()["provider"] == "eastmoney"
    assert caps_em.json()["ready"] is False


def test_module6_backtest_detail_and_runtime_readiness() -> None:
    bt = client.post("/api/backtest/run", json={"name": "phase6-detail", "symbol": "000001", "initial_cash": 200000})
    assert bt.status_code == 200
    job_id = bt.json()["job_id"]

    detail = client.get(f"/api/backtest/report/{job_id}/detail")
    assert detail.status_code == 200
    detail_json = detail.json()
    assert "granularity" in detail_json
    assert "daily_returns" in detail_json["granularity"]
    assert "rolling_drawdown" in detail_json["granularity"]
    assert "trade_distribution" in detail_json["granularity"]

    runtime = client.get("/api/admin/runtime-health")
    dr = client.get("/api/admin/dr/readiness")
    system_health = client.get("/api/admin/system-health")
    assert runtime.status_code == 200
    assert dr.status_code == 200
    assert system_health.status_code == 200
    assert runtime.json()["status"] in {"ok", "degraded"}
    assert dr.json()["status"] in {"ready", "partial"}
    assert isinstance(dr.json()["score"], int)

