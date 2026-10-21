"""R1 release provenance and fail-closed ingestion regression tests.

Provider transport is stubbed. No external requests and no claim of live data.
"""
from datetime import date, timedelta
import json
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.db.models import DatasetRelease, DatasetPriceObservation, DailyBar
from app.services import dataset_releases
from app.services.dataset_sources import fetch_akshare_daily, UpstreamDataError
from app.services.dataset_releases import (
    DatasetIntegrityError, DatasetValidationError, get_dataset_release,
    ingest_equity_or_etf_daily, validate_bars,
)

client = TestClient(app)
TOKEN = "fixed-strong-test-only-admin-token-0123456789"
START = date(2026, 1, 5)


def rows(close_change=0.0):
    return [
        {"obs_date": START + timedelta(days=n), "open": 10.0,
         "high": 11.5, "low": 9.5, "close": 10.4 + (close_change if n==2 else 0),
         "volume": 10000.0, "amount": 105000.0}
        for n in range(3)
    ]


def _stub(monkeypatch, change=0.0):
    monkeypatch.setattr(
        dataset_releases, "fetch_akshare_daily",
        lambda kind, symbol, start, end: ('[{"provider":"mocked_akshare_frame"}]',
                                           rows(close_change=change)),
    )


def _request():
    return {"kind":"equity","symbol":"600000",
            "start_date":START.isoformat(),"end_date":(START+timedelta(days=2)).isoformat()}


def test_disabled_without_admin_config_and_wrong_token(monkeypatch):
    monkeypatch.delenv("AISTOCK_RESEARCH_INGEST_TOKEN", raising=False)
    assert client.post("/api/research/v3/datasets/equity-daily/sync", json=_request()).status_code == 503
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN", TOKEN)
    assert client.post("/api/research/v3/datasets/equity-daily/sync", json=_request()).status_code == 403
    assert client.post("/api/research/v3/datasets/equity-daily/sync", json=_request(),
                       headers={"X-Research-Admin-Token":"wrong"}).status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(DatasetRelease.id)) is None


def test_source_fingerprint_idempotence_and_revision(monkeypatch):
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN", TOKEN)
    _stub(monkeypatch)
    url="/api/research/v3/datasets/equity-daily/sync"
    headers={"X-Research-Admin-Token":TOKEN}
    first=client.post(url, json=_request(), headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True
    release=first.json()["release"]
    assert release["status"]=="provider_recorded"
    assert release["pit_verified"] is False
    assert release["research_eligible"] is False
    assert release["row_count"]==3
    assert len(release["fingerprint"])==64
    second=client.post(url, json=_request(), headers=headers)
    assert second.status_code==200
    assert second.json()["created"] is False
    assert second.json()["release"]["id"]==release["id"]
    detail=client.get(f"/api/research/v3/datasets/releases/{release['id']}")
    assert detail.status_code==200
    assert detail.json()["integrity"]=="content_hash_consistent"
    assert detail.json()["observations"][0]["close"]==10.4
    _stub(monkeypatch, change=0.1)
    third=client.post(url, json=_request(), headers=headers)
    assert third.status_code==200,third.text
    assert third.json()["created"] is True
    assert third.json()["release"]["id"] != release["id"]
    with SessionLocal() as db:
        releases=db.scalars(select(DatasetRelease).order_by(DatasetRelease.id)).all()
        assert len(releases)==2
        assert releases[0].rows_sha256 != releases[1].rows_sha256
        assert db.scalar(select(DailyBar.id)) is None


@pytest.mark.parametrize("mutation", [
    lambda r: r[1].update(obs_date=r[0]["obs_date"]),
    lambda r: r[0].update(high=9.0),
    lambda r: r[0].update(open=0),
    lambda r: r[0].update(close=float("nan")),
    lambda r: r[0].update(volume=-1),
    lambda r: r[2].update(obs_date=date(2025,1,1)),
])
def test_invalid_batch_rejected_without_partial_records(monkeypatch, mutation):
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN", TOKEN)
    data=rows()
    mutation(data)
    monkeypatch.setattr(dataset_releases, "fetch_akshare_daily",
                        lambda *args: ('{"records":3}',data))
    response=client.post("/api/research/v3/datasets/equity-daily/sync",
                         headers={"X-Research-Admin-Token":TOKEN},json=_request())
    assert response.status_code==422,response.text
    with SessionLocal() as db:
        assert db.scalar(select(DatasetRelease.id)) is None
        assert db.scalar(select(DatasetPriceObservation.id)) is None


def test_wrong_provider_and_excessive_request_refused_before_fetch(monkeypatch):
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN", TOKEN)
    _stub(monkeypatch)
    url="/api/research/v3/datasets/equity-daily/sync"
    h={"X-Research-Admin-Token":TOKEN}
    for payload in [
        {**_request(),"kind":"futures"},
        {**_request(),"symbol":"DEMO01"},
        {**_request(),"kind":"etf","symbol":"600000"},
        {**_request(),"start_date":"2023-01-01"},
        {**_request(),"end_date":"2099-01-01"},
        {**_request(),"source_id":"pit_verified"},
        {**_request(),"url":"https://example.com/evil"},
    ]:
        assert client.post(url,headers=h,json=payload).status_code==422


def test_tampering_caught_and_readiness_still_blocked(monkeypatch):
    _stub(monkeypatch)
    with SessionLocal() as db:
        first=ingest_equity_or_etf_daily(db,kind="equity",symbol="600000",
                                         start=START,end=START+timedelta(days=2))
        rid=first["release"]["id"]
        assert get_dataset_release(db,rid)["integrity"]=="content_hash_consistent"
        obs=db.scalar(select(DatasetPriceObservation).where(DatasetPriceObservation.release_id==rid))
        obs.close=10.9
        db.commit()
    assert client.get(f"/api/research/v3/datasets/releases/{rid}").status_code==409
    status=client.get("/api/research/v3/datasets/readiness").json()
    assert status["can_generate_real_recommendations"] is False
    assert status["historical_pit_verified"] is False


def test_mock_only_market_adapter_cannot_be_published(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","mock")
    with pytest.raises(UpstreamDataError,match="Real provider"):
        fetch_akshare_daily("equity","600000",START,START+timedelta(days=2))


def test_etf_adapter_fixed_method_and_raw_table_capture(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    columns=["日期","股票代码","开盘","最高","最低","收盘","成交量","成交额"]
    raw=[{"日期":"2026-01-05","股票代码":"510300","开盘":10,
          "最高":11,"最低":9,"收盘":10.5,"成交量":500,"成交额":5200}]
    class MiniTable:
        empty=False
        columns=["日期","股票代码","开盘","最高","最低","收盘","成交量","成交额"]
        def iterrows(self):
            for i,v in enumerate(raw):
                yield i,v
        def to_json(self,**kwargs):
            return json.dumps(raw,ensure_ascii=False)
    called=[]
    def fetch(**kwargs):
        called.append(kwargs)
        return MiniTable()
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(fund_etf_hist_em=fetch))
    snapshot,bars=fetch_akshare_daily("etf","510300",START,START)
    assert bars[0]["obs_date"]==START
    assert bars[0]["close"]==10.5
    assert "股票代码" in snapshot
    assert called[0]["adjust"]==""
    assert called[0]["symbol"]=="510300"


def test_public_readiness_and_release_limits():
    r=client.get("/api/research/v3/datasets/readiness")
    assert r.status_code==200
    body=r.json()
    assert body["recorded_release_count"]==0
    assert body["data_state"]=="no_provider_releases"
    assert body["can_generate_real_recommendations"] is False
    assert client.get("/api/research/v3/datasets/releases?limit=101").status_code==422
    assert client.get("/api/research/v3/datasets/releases/999").status_code==404
