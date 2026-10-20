"""Adversarial, offline tests for point-in-time research scoring."""
from datetime import date, timedelta
import pytest

from app.services.research_v2 import evaluate_batch, evaluate_one


def snapshot(as_of: date, **overrides):
    row = {
        "symbol": "DEMO001", "sector": "示例行业", "source": "synthetic_unit_test",
        "as_of": as_of.isoformat(),
        "fundamentals_published_on": (as_of - timedelta(days=30)).isoformat(),
        "is_st": False, "suspended": False, "float_cap_yi": 125.0,
        "sector_excess_20d_pct": -1.5, "sector_excess_60d_pct": -3.0,
        "revenue_yoy_pct": 10.0, "roe_ttm_pct": 12.0,
        "net_profit_ttm_yi": 2.0, "ocf_ttm_yi": 3.0,
        "drawdown_120d_pct": 28.0, "return_20d_pct": 1.0,
        "valuation_percentile_3y": 30.0, "relative_volume_20d": 1.12,
        "turnover_amount_20d_yi": 2.0, "volatility_20d_pct": 3.0,
    }
    row.update(overrides)
    return row


def test_output_is_research_not_execution():
    day = date(2026, 10, 16)
    result = evaluate_one(snapshot(day), evaluation_date=day, market_regime="neutral")
    assert result["status"] == "research_candidate"
    assert result["research_priority"] in ("verify_first", "watch")
    assert 0 <= result["score"] <= 100
    assert "buy" not in str(result).lower() and "execute" not in str(result).lower()


def test_missing_financial_inputs_fail_closed():
    day = date(2026, 10, 16)
    row = snapshot(day)
    row.pop("ocf_ttm_yi")
    result = evaluate_one(row, evaluation_date=day, market_regime="neutral")
    assert result["status"] == "insufficient_data"
    assert result["score"] is None


def test_point_in_time_disclosure_rejection():
    day = date(2026, 10, 16)
    result = evaluate_one(
        snapshot(day, fundamentals_published_on="2026-10-17"),
        evaluation_date=day, market_regime="neutral",
    )
    assert result["status"] == "insufficient_data"


def test_st_and_bad_cash_flow_are_excluded():
    day = date(2026, 10, 16)
    assert evaluate_one(snapshot(day, is_st=True), evaluation_date=day, market_regime="neutral")["status"] == "excluded"
    assert evaluate_one(snapshot(day, ocf_ttm_yi=-1), evaluation_date=day, market_regime="neutral")["status"] == "excluded"


def test_stale_quotes_fail_closed():
    day = date(2026, 10, 16)
    result = evaluate_one(snapshot(date(2026, 9, 29)), evaluation_date=day, market_regime="neutral")
    assert result["status"] == "stale_data"


def test_weak_market_never_returns_priority():
    day = date(2026, 10, 16)
    result = evaluate_one(snapshot(day), evaluation_date=day, market_regime="weak")
    assert result["research_priority"] == "watch"


def test_duplicate_symbol_fails_batch():
    day = date(2026, 10, 16)
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_batch([snapshot(day), snapshot(day)], evaluation_date=day, market_regime="neutral")


def test_non_finite_values_fail_closed():
    day = date(2026, 10, 16)
    result = evaluate_one(snapshot(day, roe_ttm_pct=float("nan")), evaluation_date=day, market_regime="neutral")
    assert result["score"] is None


def test_deterministic_batch_rank():
    day = date(2026, 10, 16)
    a = snapshot(day)
    b = snapshot(day, symbol="DEMO002", roe_ttm_pct=8.0)
    first = evaluate_batch([b, a], evaluation_date=day, market_regime="neutral")
    second = evaluate_batch([a, b], evaluation_date=day, market_regime="neutral")
    assert first["items"] == second["items"]


def test_old_disclosures_are_not_silently_treated_as_current():
    day = date(2026, 10, 16)
    result = evaluate_one(
        snapshot(day, fundamentals_published_on="2025-12-01"),
        evaluation_date=day, market_regime="neutral",
    )
    assert result["status"] == "stale_fundamentals"
    assert result["score"] is None


def test_high_scoring_manual_inputs_are_not_approved_trades():
    day = date(2026, 10, 16)
    result = evaluate_one(snapshot(day), evaluation_date=day, market_regime="neutral")
    assert result["evidence_grade"] == "unverified_manual_input"
    assert result["model_validation"] == "not_backtested"
    if result["score"] is not None:
        assert 0 <= sum(result["score_components"].values()) <= 100.01
        assert result["research_priority"] != "buy"


def test_sector_summary_is_sample_only_and_flags_sparse_groups():
    day = date(2026, 10, 16)
    result = evaluate_batch(
        [snapshot(day), snapshot(day, symbol="DEMO002", sector="另一行业")],
        evaluation_date=day, market_regime="neutral",
    )
    assert result["input_validation"] == "manual_unverified"
    assert all(v["coverage"] == "insufficient" for v in result["sector_overview"])
