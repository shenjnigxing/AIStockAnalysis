from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _bootstrap_candidates() -> None:
    assert client.post("/api/data/sync/master", json={"force_full": False}).status_code == 200
    assert client.post("/api/data/sync/realtime", json={"symbols": ["000001", "600000", "600519"]}).status_code == 200
    run = client.post("/api/screener/run", json={"mode": "intraday", "filters": {"top_n": 20, "min_change_pct": -10}})
    assert run.status_code == 200


def test_module2_strategy_list_and_output_contract() -> None:
    listing = client.get("/api/strategy/list")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) >= 20
    assert all("strategy_key" in row and "strategy_name" in row and "category" in row for row in items)

    evaluate = client.post(
        "/api/strategy/evaluate",
        json={
            "symbol": "000001",
            "context": {
                "market_state": "bullish",
                "quote": {"price": 12.6, "open": 12.2, "high": 12.8, "low": 12.1, "change_pct": 4.3, "volume": 200000, "amount": 2500000},
                "daily_bars": [
                    {"trade_date": "2026-03-20", "open": 11.7, "high": 11.9, "low": 11.5, "close": 11.8, "volume": 120000, "amount": 1416000},
                    {"trade_date": "2026-03-21", "open": 11.8, "high": 12.0, "low": 11.6, "close": 11.9, "volume": 130000, "amount": 1547000},
                    {"trade_date": "2026-03-22", "open": 11.9, "high": 12.2, "low": 11.8, "close": 12.1, "volume": 140000, "amount": 1694000},
                    {"trade_date": "2026-03-23", "open": 12.1, "high": 12.3, "low": 11.9, "close": 12.2, "volume": 150000, "amount": 1830000},
                    {"trade_date": "2026-03-24", "open": 12.2, "high": 12.7, "low": 12.0, "close": 12.6, "volume": 160000, "amount": 2016000},
                ],
            },
        },
    )
    assert evaluate.status_code == 200
    outputs = evaluate.json()["items"]
    assert len(outputs) >= 20
    sample = outputs[0]
    required_fields = {
        "symbol",
        "strategy_key",
        "hit",
        "score",
        "confidence",
        "reasons",
        "risk_tags",
        "feature_snapshot",
        "market_fit_score",
        "conflict_tags",
    }
    assert required_fields.issubset(sample.keys())


def test_module2_strategy_toggle_and_params_versioning() -> None:
    listing = client.get("/api/strategy/list").json()["items"]
    key = listing[0]["strategy_key"]

    toggle_off = client.post("/api/strategy/toggle", json={"strategy_key": key, "enabled": False})
    assert toggle_off.status_code == 200
    assert toggle_off.json()["enabled"] is False

    update_params = client.post(
        "/api/strategy/params/update",
        json={"strategy_key": key, "version": "1.0.9", "params": {"threshold": 0.76, "window": 20}},
    )
    assert update_params.status_code == 200
    assert update_params.json()["version"] == "1.0.9"

    detail = client.get(f"/api/strategy/{key}")
    assert detail.status_code == 200
    assert detail.json()["enabled"] is False
    assert detail.json()["default_params"]["threshold"] == 0.76

    toggle_on = client.post("/api/strategy/toggle", json={"strategy_key": key, "enabled": True})
    assert toggle_on.status_code == 200
    assert toggle_on.json()["enabled"] is True


def test_module2_recommendation_pipeline_and_history() -> None:
    _bootstrap_candidates()

    run_llm_off = client.post("/api/recommendation/run", json={"market_state": "neutral", "llm_enabled": False})
    assert run_llm_off.status_code == 200
    assert run_llm_off.json()["status"] == "completed"

    top = client.get("/api/recommendation/top?limit=10")
    assert top.status_code == 200
    rows = top.json()["items"]
    assert len(rows) >= 1
    levels = {row["recommendation_level"] for row in rows}
    assert levels.issubset({"A", "B", "C", "D"})
    assert all("reasons" in row and "risk_tags" in row and "action_suggestion" in row for row in rows)

    run_llm_on = client.post("/api/recommendation/run", json={"market_state": "bullish", "llm_enabled": True})
    assert run_llm_on.status_code == 200
    assert run_llm_on.json()["status"] == "completed"

    latest = client.get("/api/recommendation/latest")
    assert latest.status_code == 200
    latest_rows = latest.json()["items"]
    assert len(latest_rows) >= 1
    assert any(isinstance(row["llm_score_adjustment"], (int, float)) for row in latest_rows)

    history = client.get("/api/recommendation/history")
    assert history.status_code == 200
    assert history.json()["items"][0]["market_state"] in {"bullish", "neutral", "weak", "panic"}
