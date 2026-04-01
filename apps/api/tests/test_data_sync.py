from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import DailyBar, StockMaster, SyncCheckpoint
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def test_sync_master_idempotent() -> None:
    first = client.post("/api/data/sync/master", json={"force_full": False})
    assert first.status_code == 200
    second = client.post("/api/data/sync/master", json={"force_full": False})
    assert second.status_code == 200

    with SessionLocal() as db:
        stock_count = db.scalar(select(func.count()).select_from(StockMaster))
        assert stock_count == 3


def test_sync_daily_writes_data_and_checkpoint() -> None:
    client.post("/api/data/sync/master", json={"force_full": False})

    payload = {
        "symbols": ["000001"],
        "start_date": date(2026, 3, 25).isoformat(),
        "end_date": date(2026, 3, 27).isoformat(),
    }
    response = client.post("/api/data/sync/daily", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    with SessionLocal() as db:
        bar_count = db.scalar(select(func.count()).select_from(DailyBar).where(DailyBar.symbol == "000001"))
        assert bar_count == 3
        cp = db.scalar(
            select(SyncCheckpoint).where(
                SyncCheckpoint.job_type == "daily",
                SyncCheckpoint.scope_key == "000001",
            )
        )
        assert cp is not None
        assert cp.checkpoint_value == "2026-03-27"


def test_jobs_and_retry() -> None:
    create = client.post("/api/data/sync/realtime", json={"symbols": ["000001"]})
    assert create.status_code == 200
    created_job_id = create.json()["job_id"]

    query = client.get(f"/api/data/jobs/{created_job_id}")
    assert query.status_code == 200
    assert query.json()["job_type"] == "realtime"

    retry = client.post(f"/api/data/jobs/{created_job_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["job_type"] == "realtime"
