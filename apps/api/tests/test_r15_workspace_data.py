"""Workspace read models use authenticated source stubs, never live providers."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.db.models import PublicQuoteFetchAttempt, PublicQuoteSnapshot
from app.db.session import SessionLocal
from app.services import public_quote_cache as cache

client = TestClient(app)
BASE = "/api/research/v3/market-data"


def seed(monkeypatch, observations):
    """Use real cache publication logic, faking only upstream and clock."""
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    ids = []
    for minute, (kind, symbol, value) in enumerate(observations):
        now = datetime(2026, 10, 28, 1) + timedelta(minutes=10 * minute)
        monkeypatch.setattr(cache, "_now", lambda now=now: now)
        monkeypatch.setattr(cache, "fetch_supervised", lambda kind, symbol, value=value: {
            "value": value, "source_display_time": "unverified fixture",
            "source_timestamp_utc": None, "time_quality": "time_unverified",
            "source_record": {"symbol": symbol, "fixture": True, "value": value},
        })
        with SessionLocal() as db:
            ids.append(cache.refresh_quote(db, kind=kind, symbol=symbol)["quote"]["id"])
    # Any attempt to collect from a read endpoint must fail the test.
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only workspace endpoint attempted collection")
    monkeypatch.setattr(cache, "fetch_supervised", forbidden)
    return ids


def test_empty_workspace_is_explicit_and_does_not_collect(monkeypatch):
    seed(monkeypatch, [])
    history = client.get(BASE + "/history?kind=us_equity&symbol=AAPL")
    assert history.status_code == 200
    assert history.json() == {"kind": "us_equity", "symbol": "AAPL", "points": [],
                              "basis": "collection_snapshots", "can_trade": False}
    assert client.get(BASE + "/overview").json() == {
        "items": [], "rejected_count": 0, "can_trade": False}


def test_history_is_instrument_scoped_and_newest_bounded_in_time_order(monkeypatch):
    ids = seed(monkeypatch, [("us_equity", "AAPL", 100), ("us_equity", "MSFT", 200),
                             ("us_equity", "AAPL", 101), ("us_equity", "AAPL", 102),
                             ("us_etf", "AAPL", 300)])
    response = client.get(BASE + "/history?kind=us_equity&symbol=AAPL&limit=2")
    assert response.status_code == 200
    result = response.json()
    assert result["basis"] == "collection_snapshots"
    assert [point["id"] for point in result["points"]] == [ids[2], ids[3]]
    assert [point["value"] for point in result["points"]] == [101, 102]
    assert all(point["kind"] == "us_equity" and point["symbol"] == "AAPL"
               and point["can_trade"] is False and point["source_record_sha256"]
               for point in result["points"])
    assert result["points"][0]["collected_at_utc"] < result["points"][1]["collected_at_utc"]


def test_overview_publishes_only_latest_per_instrument_and_supports_filter_limit(monkeypatch):
    ids = seed(monkeypatch, [("us_equity", "AAPL", 100), ("us_equity", "MSFT", 200),
                             ("us_equity", "AAPL", 101), ("us_etf", "SPY", 300)])
    result = client.get(BASE + "/overview").json()
    assert [point["id"] for point in result["items"]] == [ids[3], ids[2], ids[1]]
    assert result["rejected_count"] == 0 and result["can_trade"] is False
    filtered = client.get(BASE + "/overview?kind=us_equity&limit=1").json()
    assert [point["id"] for point in filtered["items"]] == [ids[2]]
    with SessionLocal() as db:
        # Read operations neither publish new data nor log collection attempts.
        assert db.scalar(select(func.count()).select_from(PublicQuoteSnapshot)) == 4
        assert db.scalar(select(func.count()).select_from(PublicQuoteFetchAttempt)) == 4


def test_corrupt_history_fails_closed_and_overview_does_not_fall_back(monkeypatch):
    ids = seed(monkeypatch, [("us_equity", "AAPL", 100), ("us_equity", "AAPL", 101),
                             ("us_equity", "MSFT", 200)])
    with SessionLocal() as db:
        db.get(PublicQuoteSnapshot, ids[1]).value = 999
        db.commit()
    assert client.get(BASE + "/history?kind=us_equity&symbol=AAPL").status_code == 409
    result = client.get(BASE + "/overview").json()
    assert result["rejected_count"] == 1
    assert [item["symbol"] for item in result["items"]] == ["MSFT"]


@pytest.mark.parametrize("path", [
    "/history?kind=us_equity&symbol=AAPL&limit=1",
    "/history?kind=us_equity&symbol=AAPL&limit=241",
    "/history?kind=us_equity&symbol=AAPL&limit=2.5",
    "/history?kind=equity&symbol=AAPL",
    "/history?kind=us_equity&symbol=aapl",
    "/history?kind=unknown&symbol=AAPL",
    "/overview?limit=0", "/overview?limit=201", "/overview?kind=unknown",
])
def test_workspace_query_rejects_unbounded_or_invalid_input(path):
    assert client.get(BASE + path).status_code == 422


def test_service_limits_also_bound_internal_callers():
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            cache.quote_history(db, kind="us_equity", symbol="AAPL", limit=999)
        with pytest.raises(ValueError):
            cache.quote_overview(db, limit=999)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), 0, -1, 1_000_000_000])
def test_invalid_cached_numeric_value_is_integrity_error_not_user_input(monkeypatch, value):
    ids = seed(monkeypatch, [("us_equity", "AAPL", 100), ("us_equity", "MSFT", 200)])
    with SessionLocal() as db:
        db.get(PublicQuoteSnapshot, ids[0]).value = value
        db.commit()
    response = client.get(BASE + "/history?kind=us_equity&symbol=AAPL")
    assert response.status_code == 409
    assert response.json()["detail"] == "Cached quote history integrity violation"
    overview = client.get(BASE + "/overview").json()
    assert overview["rejected_count"] == 1
    assert [point["symbol"] for point in overview["items"]] == ["MSFT"]
