"""Regression for mock leakage, provenance, and research-readiness barriers."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import DailyBar, StockMaster, SyncCheckpoint
from app.db.session import SessionLocal
from app.main import app
from app.services.adapters.market_data import AkshareMarketDataAdapter
from app.services.data_sync import DataSyncService, _validate_ohlc_row

client = TestClient(app)


def test_real_provider_missing_fails_closed(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    adapter = AkshareMarketDataAdapter()
    adapter._ak = None
    with pytest.raises(RuntimeError, match="Refusing synthetic fallback"):
        adapter.fetch_stock_master()
    with pytest.raises(RuntimeError, match="Refusing synthetic fallback"):
        adapter.fetch_daily_bars("000001", date(2026, 10, 19), date(2026, 10, 20))
    with pytest.raises(RuntimeError, match="Refusing synthetic fallback"):
        adapter.fetch_realtime_quotes(["000001"])
    with pytest.raises(RuntimeError, match="Refusing synthetic fallback"):
        adapter.fetch_minute_bars("000001", datetime(2026, 10, 20), datetime(2026, 10, 20))


def test_synthetic_mode_is_explicit_and_blocked_in_production(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValueError, match="forbidden"):
        AkshareMarketDataAdapter()
    monkeypatch.setenv("APP_ENV", "test")
    adapter = AkshareMarketDataAdapter()
    assert adapter.fetch_stock_master()[0]["symbol"] == "000001"


def test_real_mode_never_falls_back_to_demo_stock_universe(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    with SessionLocal() as db:
        service = DataSyncService(db)
        service.adapter._ak = None
        job = service.sync_realtime(symbols=None)
        assert job.status == "failed"
        assert "Stock master is empty" in job.error_message


def test_mock_job_is_labeled_and_not_research_ready():
    response = client.post("/api/data/sync/master", json={"force_full": False})
    assert response.status_code == 200
    assert response.json()["result"]["data_mode"] == "mock"
    assert response.json()["result"]["data_provider"] == "synthetic_demo"
    response = client.post("/api/data/sync/daily", json={
        "symbols": ["000001"], "start_date": "2026-10-19", "end_date": "2026-10-20",
    })
    assert response.json()["status"] == "completed"
    readiness = client.get("/api/research/v2/data-readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["state"] == "synthetic_data_detected"
    assert body["can_generate_v2_recommendations"] is False
    assert body["is_research_ready"] is False
    assert body["provenance"] == "unverified_legacy_store"
    assert body["symbols_with_daily_bars"] == 1
    assert body["last_daily_sync"]["mode"] == "mock"


def test_readiness_on_empty_database_does_not_invent_results():
    response = client.get("/api/research/v2/data-readiness")
    assert response.status_code == 200
    result = response.json()
    assert result["state"] == "no_usable_dataset"
    assert result["latest_daily_bar"] is None
    assert result["is_research_ready"] is False


@pytest.mark.parametrize("update", [
    {"low": 12.0}, {"high": 8.0}, {"open": 0.0},
    {"volume": float("nan")}, {"amount": -1.0},
])
def test_corrupt_ohlc_is_rejected(update):
    bar = {"open": 10.0, "high": 10.8, "low": 9.5, "close": 10.5,
           "volume": 1000.0, "amount": 10000.0}
    bar.update(update)
    assert not _validate_ohlc_row(bar)


def test_all_invalid_daily_rows_do_not_advance_checkpoint(monkeypatch):
    def bad_bars(self, symbol, start_date, end_date):
        return [{"symbol": symbol, "trade_date": start_date,
                 "open": 10.0, "high": 9.0, "low": 9.5, "close": 10.0,
                 "volume": 1000.0, "amount": 9000.0}]
    monkeypatch.setattr(AkshareMarketDataAdapter, "fetch_daily_bars", bad_bars)
    with SessionLocal() as db:
        job = DataSyncService(db).sync_daily(
            symbols=["000001"], start_date=date(2026, 10, 19), end_date=date(2026, 10, 19)
        )
        assert job.status == "failed"
        checkpoint = db.scalar(select(SyncCheckpoint).where(
            SyncCheckpoint.job_type == "daily", SyncCheckpoint.scope_key == "000001"
        ))
        assert checkpoint is not None
        assert checkpoint.checkpoint_value == ""
        assert db.scalar(select(DailyBar.id)) is None
