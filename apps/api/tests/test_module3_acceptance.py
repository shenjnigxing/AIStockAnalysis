from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_module3_backtest_metrics_and_compare() -> None:
    payload_a = {
        "name": "module3-bt-a",
        "type": "recommendation",
        "symbol": "000001",
        "initial_cash": 1_000_000,
        "position_limit": 0.3,
        "commission": 0.0003,
        "stamp_tax": 0.001,
        "slippage": 0.0008,
    }
    payload_b = {
        "name": "module3-bt-b",
        "type": "strategy",
        "symbol": "600000",
        "initial_cash": 1_000_000,
        "position_limit": 0.4,
        "commission": 0.0002,
        "stamp_tax": 0.001,
        "slippage": 0.0012,
    }
    run_a = client.post("/api/backtest/run", json=payload_a)
    run_b = client.post("/api/backtest/run", json=payload_b)
    assert run_a.status_code == 200
    assert run_b.status_code == 200

    job_a = run_a.json()["job_id"]
    job_b = run_b.json()["job_id"]
    report = client.get(f"/api/backtest/report/{job_a}")
    assert report.status_code == 200
    metrics = report.json()["metrics"]
    required = {
        "total_return",
        "annual_return",
        "benchmark_return",
        "excess_return",
        "max_drawdown",
        "volatility",
        "downside_volatility",
        "sharpe",
        "sortino",
        "calmar",
        "win_rate",
        "pnl_ratio",
        "turnover",
        "avg_holding_days",
        "total_trades",
        "slippage_impact",
        "cost_impact",
        "capacity_hint",
    }
    assert required.issubset(metrics.keys())

    trades = client.get(f"/api/backtest/trades/{job_a}")
    equity = client.get(f"/api/backtest/equity/{job_a}")
    assert trades.status_code == 200
    assert equity.status_code == 200
    assert len(equity.json()["items"]) >= 1

    compare = client.post("/api/backtest/compare", json={"left_job_id": job_a, "right_job_id": job_b})
    assert compare.status_code == 200
    assert "left" in compare.json() and "right" in compare.json()


def test_module3_paper_trading_order_lifecycle() -> None:
    preview = client.post(
        "/api/paper/order/preview",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "B"},
    )
    assert preview.status_code == 200
    assert preview.json()["decision"] in {"pass", "pass_with_warning", "manual_review_required", "reject"}

    place_buy = client.post(
        "/api/paper/orders",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert place_buy.status_code == 200
    order_id = place_buy.json()["order_id"]
    assert isinstance(order_id, int)

    orders = client.get("/api/paper/orders")
    trades = client.get("/api/paper/trades")
    positions = client.get("/api/paper/positions")
    assets = client.get("/api/paper/assets")
    pnl = client.get("/api/paper/pnl")
    assert orders.status_code == 200
    assert trades.status_code == 200
    assert positions.status_code == 200
    assert assets.status_code == 200
    assert pnl.status_code == 200
    assert "total_assets" in assets.json()

    place_sell = client.post(
        "/api/paper/orders",
        json={"symbol": "000001", "side": "sell", "price": 10.5, "quantity": 100, "recommendation_level": "A"},
    )
    assert place_sell.status_code == 200

    cancel = client.post(f"/api/paper/orders/{order_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] in {"cancelled", "filled", "rejected", "created", "submitted"}
