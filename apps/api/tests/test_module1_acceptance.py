from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import DataQualityIssue, DailyBar, ScreenerPreset, SyncCheckpoint
from app.db.session import SessionLocal
from app.main import app
from app.services.data_sync import DataSyncService
from app.services.adapters.market_data import AkshareMarketDataAdapter


client = TestClient(app)


def test_module1_daily_incremental_and_idempotent_checkpoint() -> None:
    assert client.post("/api/data/sync/master", json={"force_full": False}).status_code == 200

    payload = {
        "symbols": ["000001"],
        "start_date": date(2026, 3, 24).isoformat(),
        "end_date": date(2026, 3, 26).isoformat(),
    }
    run1 = client.post("/api/data/sync/daily", json=payload)
    assert run1.status_code == 200
    assert run1.json()["status"] == "completed"

    with SessionLocal() as db:
        first_count = db.scalar(
            select(func.count())
            .select_from(DailyBar)
            .where(
                DailyBar.symbol == "000001",
                DailyBar.trade_date >= date(2026, 3, 24),
                DailyBar.trade_date <= date(2026, 3, 26),
            )
        )
        cp = db.scalar(
            select(SyncCheckpoint).where(
                SyncCheckpoint.job_type == "daily",
                SyncCheckpoint.scope_key == "000001",
            )
        )
        assert cp is not None
        assert cp.checkpoint_value == "2026-03-26"

    run2 = client.post("/api/data/sync/daily", json=payload)
    assert run2.status_code == 200
    assert run2.json()["status"] == "completed"

    with SessionLocal() as db:
        second_count = db.scalar(
            select(func.count())
            .select_from(DailyBar)
            .where(
                DailyBar.symbol == "000001",
                DailyBar.trade_date >= date(2026, 3, 24),
                DailyBar.trade_date <= date(2026, 3, 26),
            )
        )
        assert second_count == first_count


def test_module1_quality_issue_recorded_for_invalid_ohlc(monkeypatch) -> None:
    def broken_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[dict]:
        return [
            {
                "symbol": symbol,
                "trade_date": start_date,
                "open": 10.0,
                "high": 9.0,
                "low": 9.5,
                "close": 9.8,
                "volume": 1000.0,
                "amount": 9800.0,
            }
        ]

    monkeypatch.setattr(AkshareMarketDataAdapter, "fetch_daily_bars", broken_daily_bars, raising=True)
    with SessionLocal() as db:
        service = DataSyncService(db)
        job = service.sync_daily(symbols=["000001"], start_date=date(2026, 3, 28), end_date=date(2026, 3, 28))
        assert job.status == "completed"

    with SessionLocal() as db:
        issue_count = db.scalar(
            select(func.count())
            .select_from(DataQualityIssue)
            .where(DataQualityIssue.issue_type == "invalid_ohlc", DataQualityIssue.symbol == "000001")
        )
        assert issue_count >= 1


def test_module1_screener_topn_and_presets_flow() -> None:
    assert client.post("/api/data/sync/realtime", json={"symbols": ["000001", "600000", "600519"]}).status_code == 200

    run = client.post(
        "/api/screener/run",
        json={
            "mode": "intraday",
            "filters": {
                "top_n": 5,
                "min_change_pct": -10,
                "max_change_pct": 10,
                "min_price": 1,
                "min_volume_ratio": 0.1,
            },
        },
    )
    assert run.status_code == 200
    assert run.json()["status"] == "completed"

    latest = client.get("/api/candidates/latest")
    top100 = client.get("/api/candidates/top100")
    assert latest.status_code == 200
    assert top100.status_code == 200
    assert latest.json()["count"] <= 5
    assert top100.json()["count"] <= 5

    create = client.post(
        "/api/screener/presets",
        json={"name": "module1-acceptance", "params": {"top_n": 8, "min_price": 2}},
    )
    assert create.status_code == 200
    preset_id = create.json()["id"]

    update = client.post(f"/api/screener/presets/{preset_id}/update", json={"params": {"top_n": 10, "min_price": 3}})
    assert update.status_code == 200

    listing = client.get("/api/screener/presets")
    assert listing.status_code == 200
    rows = listing.json()["items"]
    matched = [row for row in rows if row["id"] == preset_id]
    assert len(matched) == 1
    assert matched[0]["params"]["top_n"] == 10
    assert matched[0]["params"]["min_price"] == 3

    with SessionLocal() as db:
        preset_count = db.scalar(select(func.count()).select_from(ScreenerPreset).where(ScreenerPreset.id == preset_id))
        assert preset_count == 1
