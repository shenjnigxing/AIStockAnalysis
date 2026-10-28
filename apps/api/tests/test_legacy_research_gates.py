"""Exercise production legacy services, not copied scoring/backtest harnesses."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.models import (
    BacktestJob, BacktestReport, DailyBar, ScreenerRun, ScreenerCandidate,
    StrategyDefinition, StrategySignal,
)
from app.db.session import SessionLocal
from recommendation_core import recommendation

client = TestClient(app)


def _candidate_run(db, symbols=("000001", "600000")):
    run = ScreenerRun()
    db.add(run)
    db.flush()
    for rank, symbol in enumerate(symbols, 1):
        db.add(ScreenerCandidate(screener_run_id=run.id, symbol=symbol,
                                 rank_no=rank, base_score=90 - rank))
    db.commit()
    return run


def test_llm_adjustment_never_changes_score_or_rank(monkeypatch):
    with SessionLocal() as db:
        _candidate_run(db)
        service = recommendation.RecommendationService(db)
        service.run(llm_enabled=False)
        baseline = [(r.symbol, r.total_score, r.final_rank) for r in service.latest()]
        for adjustment in (-1e9, 1e9, float("nan")):
            explainer = SimpleNamespace(
                provider_name="hostile-test",
                explain=lambda **kw: SimpleNamespace(
                    adjustment=adjustment, explanation="Untrusted numeric suggestion",
                    counter_arguments=["Untrusted commentary"], degraded=False),
            )
            monkeypatch.setattr(recommendation, "get_llm_explainer", lambda _: explainer)
            service.run(llm_enabled=True)
            rows = service.latest()
            assert [(r.symbol, r.total_score, r.final_rank) for r in rows] == baseline
            assert all(r.llm_score_adjustment == 0 for r in rows)
            assert all(r.llm_explanation.startswith("[解释不参与评分]") for r in rows)


def test_only_latest_screener_run_is_used_even_when_empty():
    with SessionLocal() as db:
        _candidate_run(db, ("000001", "600000"))
        _candidate_run(db, ("000001",))
        service = recommendation.RecommendationService(db)
        service.run()
        assert [r.symbol for r in service.latest()] == ["000001"]
        _candidate_run(db, ())
        service.run()
        assert service.latest() == []


def test_disabled_strategies_are_not_reenabled_by_fallback():
    with SessionLocal() as db:
        _candidate_run(db)
        service = recommendation.RecommendationService(db)
        for strategy in service.registry.list_strategies():
            db.add(StrategyDefinition(strategy_key=strategy.strategy_key,
                                      strategy_name=strategy.strategy_name, enabled=False))
        db.commit()
        assert service._enabled_strategy_keys() == []
        service.run()
        assert db.scalar(select(StrategySignal.id)) is None


@pytest.mark.parametrize("mode,environment", [
    ("real", "dev"), ("mock", "production"), ("unknown", "dev"),
])
def test_empty_backtest_refuses_synthetic_prices(monkeypatch, mode, environment):
    monkeypatch.setenv("MARKET_DATA_MODE", mode)
    monkeypatch.setenv("APP_ENV", environment)
    response = client.post("/api/backtest/run", json={"symbol": "600000"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(BacktestJob.id)) is None
        assert db.scalar(select(BacktestReport.id)) is None
        assert db.scalar(select(DailyBar.id)) is None


def test_real_backtest_insufficient_stored_bars_returns_conflict(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    with SessionLocal() as db:
        db.add(DailyBar(symbol="600000", trade_date=date.today(),
                        open=10, high=11, low=9, close=10, volume=100, amount=1000))
        db.commit()
    assert client.post("/api/backtest/run", json={"symbol": "600000"}).status_code == 409


def test_real_backtest_rejects_stored_bars_without_pit_qualification(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    with SessionLocal() as db:
        for n in range(25):
            db.add(DailyBar(symbol="600000", trade_date=date.today() - timedelta(days=25-n),
                            open=10, high=11, low=9, close=10, volume=100, amount=1000))
        db.commit()
    response = client.post("/api/backtest/run", json={"symbol": "600000"})
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(BacktestJob.id)) is None
        assert db.scalar(select(BacktestReport.id)) is None
