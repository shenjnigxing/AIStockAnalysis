"""Research-only sector ranking tests: PIT, deterministic output, bounded contract."""
from datetime import date, timedelta
from math import isclose

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.sector_rotation import evaluate_sectors, features, score_features

client = TestClient(app)


def dates(size=81):
    end = date(2026, 10, 20)
    # Synthetic observation dates. No claim these are official exchange sessions.
    return [end - timedelta(days=size - 1 - i) for i in range(size)]


def payload(model="recovery", source="synthetic_demo"):
    ds = dates()
    benchmark = [{"date": day.isoformat(), "close": round(100 * (1.0008 ** idx), 6)}
                 for idx, day in enumerate(ds)]
    sectors = []
    for symbol, label, trend in (("sector_a", "合成行业甲", 1.0017),
                                 ("sector_b", "合成行业乙", 0.9996)):
        sectors.append({
            "sector_id": symbol, "sector_name": label,
            "prices": [{"date": day.isoformat(), "close": round(100 * (trend ** idx), 6)}
                       for idx, day in enumerate(ds)],
        })
    return {
        "as_of": ds[-1].isoformat(), "model": model, "source": source,
        "benchmark_id": "SYNTH_BENCH", "benchmark_prices": benchmark,
        "sectors": sectors,
    }


def test_identical_prices_have_zero_excess_returns():
    prices = [100.0 + 0.3 * i for i in range(81)]
    f = features(prices, prices)
    assert isclose(f["rel_20d_pct"], 0.0, abs_tol=1e-8)
    assert isclose(f["rel_60d_pct"], 0.0, abs_tol=1e-8)
    assert isclose(f["acceleration_pp"], 0.0, abs_tol=1e-8)


def test_api_is_read_only_experimental_and_has_real_research_metadata():
    response = client.post("/api/research/v2/sectors/evaluate", json=payload())
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["sector_count"] == 2
    assert item["observations"] == 81
    assert item["source_grade"] == "synthetic_demo"
    assert item["model_validation"] == "not_backtested"
    assert item["validated_alpha"] is False
    assert len(item["input_sha256"]) == 64
    assert all(v["status"] == "experimental" for v in item["items"])
    assert all(v["score"] >= 0 and v["score"] <= 100 for v in item["items"])
    assert all(v["research_priority"] in ("inspect", "watch") for v in item["items"])
    assert not any(k in item["items"][0] for k in ("order", "execute", "buy", "sell"))


def test_models_differ_without_changing_input_data_hash():
    first = client.post("/api/research/v2/sectors/evaluate", json=payload("recovery")).json()
    second = client.post("/api/research/v2/sectors/evaluate", json=payload("trend")).json()
    assert first["input_sha256"] == second["input_sha256"]
    assert first["items"][0]["factors"] != second["items"][0]["factors"]


def test_order_independent_and_stable():
    one = payload()
    two = payload()
    two["sectors"].reverse()
    left = client.post("/api/research/v2/sectors/evaluate", json=one).json()
    right = client.post("/api/research/v2/sectors/evaluate", json=two).json()
    assert left["items"] == right["items"]
    assert left["input_sha256"] == right["input_sha256"]


@pytest.mark.parametrize("mutate", [
    lambda p: p["benchmark_prices"][-1].update(close=0),
    lambda p: p["benchmark_prices"][-1].update(close=-10),
    lambda p: p["benchmark_prices"][-1].update(close="NaN"),
    lambda p: p["benchmark_prices"][-1].update(close="Infinity"),
    lambda p: p["benchmark_prices"][-1].update(date="2026-10-21"),
    lambda p: p["benchmark_prices"][15].update(date=p["benchmark_prices"][14]["date"]),
    lambda p: p["sectors"][0]["prices"][20].update(date="2026-10-25"),
    lambda p: p.update(as_of="2026-10-19"),
    lambda p: p.update(as_of="2099-01-01"),
    lambda p: p["sectors"][1].update(sector_id="sector_a"),
    lambda p: p["sectors"][1].update(sector_name="合成行业甲"),
    lambda p: p["sectors"][0].update(prices=p["sectors"][0]["prices"][:-30]),
    lambda p: p["sectors"][0].update(extra="unknown"),
    lambda p: p.update(source="pit_verified"),
])
def test_invalid_inputs_fail_closed_with_422(mutate):
    data = payload()
    mutate(data)
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 422, response.text


def test_oversize_request_rejected():
    data = payload()
    data["sectors"] = [dict(data["sectors"][0], sector_id=f"s{i}", sector_name=f"名称{i}") for i in range(13)]
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 422


def test_not_enough_bars_is_rejected():
    data = payload()
    data["benchmark_prices"] = data["benchmark_prices"][-60:]
    for row in data["sectors"]:
        row["prices"] = row["prices"][-60:]
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 422


def test_at_least_61_bars_are_enough():
    data = payload()
    data["benchmark_prices"] = data["benchmark_prices"][-61:]
    for row in data["sectors"]:
        row["prices"] = row["prices"][-61:]
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 200, response.text


def test_risk_penalties_and_scores_stay_bounded():
    f = {
        "rel_20d_pct": 23.0, "rel_60d_pct": -30.0,
        "acceleration_pp": 35.0, "drawdown_60d_pct": 46.0,
    }
    for model in ("recovery", "trend"):
        score, factors, penalties, flags = score_features(f, model)
        assert 0 <= score <= 100
        assert all(0 <= value <= 100 for value in factors.values())
        assert penalties > 0 and flags


def test_as_of_is_consistent_and_no_output_after_invalid_axis():
    data = payload()
    data["sectors"][1]["prices"][0]["date"] = "2001-01-01"
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 422
    assert "items" not in response.json()


def test_source_provenance_is_never_promoted():
    data = payload(source="manual_unverified")
    response = client.post("/api/research/v2/sectors/evaluate", json=data)
    assert response.status_code == 200
    assert response.json()["source_grade"] == "manual_unverified"
    assert response.json()["validated_alpha"] is False


def test_recovery_requires_improvement_not_only_past_underperformance():
    """Adversarial: stagnant relative loser must not outrank genuine recovery."""
    recovering = {
        "rel_20d_pct": 9.0, "rel_60d_pct": -5.0,
        "acceleration_pp": 14.0, "drawdown_60d_pct": 7.0,
    }
    stagnant = {
        "rel_20d_pct": -4.5, "rel_60d_pct": -13.0,
        "acceleration_pp": 0.0, "drawdown_60d_pct": 10.0,
    }
    recovery_score, _, recovery_penalty, _ = score_features(recovering, "recovery")
    stagnant_score, _, stagnant_penalty, risks = score_features(stagnant, "recovery")
    assert recovery_score > stagnant_score + 20
    assert stagnant_penalty > recovery_penalty
    assert any("改善尚未确认" in text for text in risks)


def test_recovery_penalizes_sector_that_has_already_run_up():
    hot = {
        "rel_20d_pct": 8.0, "rel_60d_pct": 25.0,
        "acceleration_pp": 10.0, "drawdown_60d_pct": 0.0,
    }
    _, _, penalty, risks = score_features(hot, "recovery")
    assert penalty >= 15
    assert any("不属于低位修复" in text for text in risks)
