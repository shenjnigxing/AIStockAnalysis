"""Five-asset V3 contract, risk gates, provenance, horizon and delivery safety."""
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.multi_asset_research import evaluate_multi_asset

client = TestClient(app)
DAY = date(2026, 10, 20)


def series(n=130):
    return [{"date": (DAY - timedelta(days=n-i-1)).isoformat(),
             "close": round(100 * (1.001 ** i), 6)} for i in range(n)]


def instrument(asset_class, product_type=None, n=130):
    base = {
        "equity": ("common_stock", {"is_st": False, "suspended": False, "turnover_amount_yi": 2.0}),
        "precious_metal": ("bank_paper", {"bid_ask_spread_bps": 25}),
        "fund": ("etf", {"annual_fee_pct": .5, "premium_discount_pct": .2}),
        "futures": ("commodity_future", {"expiry": "2027-02-01", "contract_multiplier": 10, "margin_ratio": .12}),
        "treasury": ("cash_bond", {"yield_to_maturity_pct": 2.1, "modified_duration": 6.2}),
    }
    kind, m = base[asset_class]
    if product_type:
        kind = product_type
        if kind == "open_end":
            m = {"annual_fee_pct": 1.2, "nav_published_on": DAY.isoformat()}
        elif kind == "continuous":
            m = {"expiry": "2027-02-01", "contract_multiplier": 10, "margin_ratio": .12}
        elif kind == "leveraged_deferred":
            m = {}
    return {
        "symbol": f"TEST_{asset_class.upper()}_{kind.upper()}",
        "name": f"合成 {asset_class} {kind}",
        "asset_class": asset_class, "product_type": kind, "currency": "CNY",
        "prices": series(n), "metadata": m,
    }


def request(horizon="short"):
    return {
        "as_of": DAY.isoformat(), "source": "synthetic_demo", "horizon": horizon,
        "instruments": [instrument(kind) for kind in
                        ("equity", "precious_metal", "fund", "futures", "treasury")],
    }


@pytest.mark.parametrize("horizon", ["short", "medium_long"])
def test_five_assets_two_horizons(horizon):
    result = client.post("/api/research/v3/evaluate", json=request(horizon))
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["count"] == 5 and len(data["groups"]) == 5
    assert data["can_trade"] is False and data["can_deliver"] is False
    assert data["model_validation"] == "not_backtested"
    assert data["validated_alpha"] is False
    assert data["source_grade"] == "synthetic_demo"
    assert len(data["input_sha256"]) == 64
    for group in data["groups"]:
        assert len(group["items"]) == 1
        row = group["items"][0]
        assert row["score"] is None or 0 <= row["score"] <= 100
        assert row["asset_class"] == group["asset_class"]
        assert row["currency"] == group["currency"]


def test_fingerprint_order_independent():
    x = request("short")
    y = request("short")
    y["instruments"].reverse()
    a = client.post("/api/research/v3/evaluate", json=x).json()
    b = client.post("/api/research/v3/evaluate", json=y).json()
    assert a["input_sha256"] == b["input_sha256"]
    assert a["groups"] == b["groups"]


def test_minimum_short_history_no_60day_lookahead():
    item = instrument("equity", n=26)
    response = client.post("/api/research/v3/evaluate", json={
        **request("short"), "instruments": [item]})
    assert response.status_code == 200, response.text
    features = response.json()["groups"][0]["items"][0]["features"]
    assert features["return_60_pct"] is None
    assert features["return_120_pct"] is None


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(source="pit_verified"),
    lambda p: p.update(as_of="2099-01-01"),
    lambda p: p["instruments"][0]["prices"][-1].update(close=0),
    lambda p: p["instruments"][0]["prices"][-1].update(close="Infinity"),
    lambda p: p["instruments"][0]["prices"][5].update(date=p["instruments"][0]["prices"][4]["date"]),
    lambda p: p["instruments"][0]["prices"][-1].update(date="2026-10-21"),
    lambda p: p["instruments"][0].update(product_type="unrecognized"),
    lambda p: p["instruments"][0].update(metadata={}),
    lambda p: p["instruments"][0].update(currency="BTC"),
    lambda p: p["instruments"][0].update(unknown="bad"),
    lambda p: p["instruments"].append(p["instruments"][0]),
])
def test_invalid_data_never_returns_partial_recommendation(mutator):
    x = request()
    mutator(x)
    response = client.post("/api/research/v3/evaluate", json=x)
    assert response.status_code == 422, response.text


def test_medium_long_requires_at_least_121_prices():
    x = request("medium_long")
    x["instruments"][0]["prices"] = x["instruments"][0]["prices"][-120:]
    result = client.post("/api/research/v3/evaluate", json=x)
    assert result.status_code == 422


def test_futures_contract_expiry_and_margin_blocks():
    x = request()
    future = x["instruments"][3]
    future["metadata"]["expiry"] = "2026-10-25"
    result = client.post("/api/research/v3/evaluate", json=x)
    assert result.status_code == 200
    future_result = next(g["items"][0] for g in result.json()["groups"] if g["asset_class"] == "futures")
    assert future_result["score"] is None and future_result["status"] == "blocked"
    assert "到期" in " ".join(future_result["blocked_reasons"])
    future["metadata"]["expiry"] = "2027-02-01"
    future["metadata"]["margin_ratio"] = .35
    row = next(g["items"][0] for g in client.post("/api/research/v3/evaluate", json=x).json()["groups"]
               if g["asset_class"] == "futures")
    assert row["status"] == "blocked"


def test_paper_gold_spread_safety():
    x = request()
    x["instruments"][1]["metadata"]["bid_ask_spread_bps"] = 180
    row = next(g["items"][0] for g in client.post("/api/research/v3/evaluate", json=x).json()["groups"]
               if g["asset_class"] == "precious_metal")
    assert row["status"] == "blocked"
    assert row["score"] is None


def test_open_end_fund_nav_must_have_been_published():
    x = request()
    x["instruments"] = [instrument("fund", "open_end")]
    x["instruments"][0]["metadata"]["nav_published_on"] = "2026-10-21"
    assert client.post("/api/research/v3/evaluate", json=x).status_code == 422
    x["instruments"][0]["metadata"]["nav_published_on"] = DAY.isoformat()
    assert client.post("/api/research/v3/evaluate", json=x).status_code == 200


def test_treasury_duration_interest_sensitivity_is_scenario_not_forecast():
    x = request()
    x["instruments"] = [instrument("treasury")]
    row = client.post("/api/research/v3/evaluate", json=x).json()["groups"][0]["items"][0]
    assert row["rate_up_50bps_price_sensitivity_pct"] == -3.1
    assert "predicted_return" not in row and "target_price" not in row


def test_cross_asset_scores_are_never_in_a_global_leaderboard():
    out = client.post("/api/research/v3/evaluate", json=request()).json()
    assert "items" not in out
    assert "ranking" not in out
    assert all(len(g["items"]) == 1 for g in out["groups"])


def test_notification_preview_never_sends_or_accepts_recipients():
    x = {"research": request(), "channels": ["wecom", "email"]}
    out = client.post("/api/research/v3/notifications/preview", json=x)
    assert out.status_code == 200
    body = out.json()
    assert body["delivery_allowed"] is False
    assert all(row["status"] == "preview_only" for row in body["channels"])
    assert "@" not in str(body)
    x["recipient"] = "private@example.com"
    assert client.post("/api/research/v3/notifications/preview", json=x).status_code == 422


def test_no_actual_signal_or_trade_capability():
    result = client.get("/api/research/v3/capabilities")
    assert result.status_code == 200
    body = result.json()
    assert body["verified_market_data"] is False
    assert body["can_trade"] is False
    assert body["notifications_enabled"] is False
