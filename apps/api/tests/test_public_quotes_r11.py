"""Public quote operational tests: source stubs, no live internet in CI."""
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import PublicQuoteSnapshot, PublicQuoteFetchAttempt, DailyBar
from app.db.session import SessionLocal
from app.services import public_quote_cache
from app.services.public_quote_cache import QuoteUnavailable
from app.services.public_quote_sources import fetch_public_quote, PublicQuoteSourceError

client = TestClient(app)
TOKEN = "r11-unit-test-admin-token-unique-0123456789"
HEADER = {"X-Research-Admin-Token": TOKEN}


def _fake(quality="time_unverified", timestamp=None, value=15.2):
    return {
        "value": value, "source_display_time": "14:30:08",
        "source_timestamp_utc": timestamp, "time_quality": quality,
        "source_record": {"代码":"600000", "最新":value},
    }


def _enable(monkeypatch, record=None):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN", TOKEN)
    monkeypatch.setattr(public_quote_cache, "fetch_supervised", lambda k,s: record or _fake())


def _refresh(kind="equity",symbol="600000",headers=HEADER):
    return client.post("/api/research/v3/market-data/refresh",
                       json={"kind":kind,"symbol":symbol},headers=headers)


def test_public_sources_and_read_missing_quote_without_network():
    data=client.get("/api/research/v3/market-data/sources").json()
    assert len(data["providers"]) == 8
    assert data["research_eligible"] is False
    assert data["notifications_enabled"] is False
    assert client.get("/api/research/v3/market-data/quote?kind=equity&symbol=600000").status_code==404
    assert client.get("/api/research/v3/market-data/quote?kind=equity&symbol=EVIL").status_code==422


def test_admin_auth_is_fail_closed(monkeypatch):
    monkeypatch.delenv("AISTOCK_RESEARCH_INGEST_TOKEN", raising=False)
    assert _refresh().status_code==503
    monkeypatch.setenv("AISTOCK_RESEARCH_INGEST_TOKEN",TOKEN)
    assert _refresh(headers={}).status_code==403
    assert _refresh(headers={"X-Research-Admin-Token":"wrong"}).status_code==403


def test_snapshot_is_persisted_and_second_refresh_cached(monkeypatch):
    _enable(monkeypatch)
    r=_refresh()
    assert r.status_code==200,r.text
    first=r.json()
    assert first["cached"] is False
    quote=first["quote"]
    assert quote["value"]==15.2
    assert quote["time_quality"]=="time_unverified"
    assert quote["source_age_seconds"] is None
    assert quote["freshness"]=="time_unverified"
    assert quote["research_eligible"] is False and quote["can_trade"] is False
    second=_refresh()
    assert second.status_code==200 and second.json()["cached"] is True
    assert second.json()["quote"]["id"]==quote["id"]
    retrieved=client.get("/api/research/v3/market-data/quote?kind=equity&symbol=600000")
    assert retrieved.status_code==200
    assert retrieved.json()["source_record_sha256"] == quote["source_record_sha256"]
    with SessionLocal() as db:
        assert len(db.scalars(select(PublicQuoteSnapshot)).all())==1
        assert len(db.scalars(select(PublicQuoteFetchAttempt)).all())==1
        assert db.scalar(select(DailyBar.id)) is None


def test_future_source_timestamp_is_rejected(monkeypatch):
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    _enable(monkeypatch,_fake("provider_update_timestamp",future))
    first=_refresh()
    assert first.status_code==502
    with SessionLocal() as db:
        assert db.scalar(select(PublicQuoteSnapshot.id)) is None
        attempts=db.scalars(select(PublicQuoteFetchAttempt)).all()
        assert len(attempts)==1 and attempts[0].state=="failure"
    assert _refresh().status_code==429


def test_failed_refresh_does_not_replace_prior_snapshot(monkeypatch):
    _enable(monkeypatch)
    first=_refresh().json()["quote"]["id"]
    with SessionLocal() as db:
        old=db.get(PublicQuoteSnapshot,first)
        old.collected_at_utc -= timedelta(seconds=600)
        attempt=db.scalar(select(PublicQuoteFetchAttempt))
        attempt.attempted_at_utc -= timedelta(seconds=600)
        db.commit()
    monkeypatch.setattr(public_quote_cache,"fetch_supervised",
                        lambda k,s: (_ for _ in ()).throw(QuoteUnavailable("timeout")))
    assert _refresh().status_code==502
    quote=client.get("/api/research/v3/market-data/quote?kind=equity&symbol=600000").json()
    assert quote["id"]==first
    assert quote["freshness"]=="stale_cache"
    with SessionLocal() as db:
        attempts=db.scalars(select(PublicQuoteFetchAttempt)).all()
        assert len(attempts)==2 and attempts[-1].state=="failure"


@pytest.mark.parametrize("field,value",[
    ("value",999999.0),("unit","USD/oz"),("currency","USD"),
    ("source_id","forged_source"),("source_record_json",'{"tamper":true}'),
])
def test_quote_integrity_fails_closed(monkeypatch,field,value):
    _enable(monkeypatch)
    ident=_refresh().json()["quote"]["id"]
    with SessionLocal() as db:
        row=db.get(PublicQuoteSnapshot,ident)
        setattr(row,field,value)
        db.commit()
    assert client.get("/api/research/v3/market-data/quote?kind=equity&symbol=600000").status_code==409


@pytest.mark.parametrize("kind,symbol",[
    ("equity","<script>"),("etf","600000"),("futures","AU; rm -rf /"),
    ("sge_gold","Au(T+D)"),("treasury_10y","CN5Y"),
])
def test_identity_allowlist_rejects_bad_symbols(monkeypatch,kind,symbol):
    _enable(monkeypatch)
    assert _refresh(kind,symbol).status_code==422


def _frame(rows):
    class Frame:
        empty = not bool(rows)
        def __len__(self):return len(rows)
        def iterrows(self):
            for i,row in enumerate(rows):yield i,row
    return Frame()


def test_equity_akshare_depth_field_mapping(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        stock_bid_ask_em=lambda symbol: _frame([
            {"item":"最新","value":"10.88"},
            {"item":"买一","value":"10.87"},
        ])
    ))
    result=fetch_public_quote("equity","600000")
    assert result["value"]==10.88
    assert result["time_quality"]=="time_unverified"


def test_etf_akshare_quote_timestamps(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        fund_etf_spot_em=lambda: _frame([
            {"代码":"510300","最新价":4.666,"数据日期":"2026-10-20","更新时间":"14:50:31"},
            {"代码":"159915","最新价":2.2,"数据日期":"2026-10-20","更新时间":"14:50:31"},
        ])
    ))
    result=fetch_public_quote("etf","510300")
    assert result["value"]==4.666
    assert result["time_quality"]=="provider_update_timestamp"
    assert result["source_timestamp_utc"].isoformat().startswith("2026-10-20T06:50")


def test_gold_sge_quote_distinct_from_bank_paper(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        spot_quotations_sge=lambda symbol: _frame([
            {"品种":"Au99.99","现价":777.1,"更新时间":"2026年10月20日 15:30:00"},
            {"品种":"Au99.99","现价":778.2,"更新时间":"2026年10月20日 15:30:00"},
        ])
    ))
    result=fetch_public_quote("sge_gold","Au99.99")
    assert result["value"]==778.2
    assert result["time_quality"]=="provider_update_timestamp"


def test_futures_clock_alone_does_not_create_overnight_trade_date(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        futures_zh_spot=lambda **kwargs: _frame([
            {"symbol":"黄金2612","time":"224015","current_price":1076.2,"bid_price":1076.1}
        ])
    ))
    result=fetch_public_quote("futures","AU2612")
    assert result["value"]==1076.2
    assert result["source_timestamp_utc"] is None
    assert result["time_quality"]=="time_unverified"


def test_treasury_yield_not_price_and_not_realtime(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        bond_gb_zh_sina=lambda **kwargs: _frame([
            {"date":"2026-10-19","close":1.91},
            {"date":"2026-10-20","close":1.87},
        ])
    ))
    result=fetch_public_quote("treasury_10y","CN10Y")
    assert result["value"]==1.87
    assert result["time_quality"]=="daily_observation"


def test_missing_vendor_columns_rejected_not_filled(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setitem(sys.modules,"akshare",SimpleNamespace(
        fund_etf_spot_em=lambda: _frame([{"代码":"510300","最新价":"--"}])
    ))
    with pytest.raises(PublicQuoteSourceError):
        fetch_public_quote("etf","510300")


def test_us_equity_and_etf_are_supported_by_source_registry_but_not_verified():
    sources=client.get("/api/research/v3/market-data/sources").json()
    kinds={p["kind"] for p in sources["providers"]}
    assert {"us_equity","us_etf","okx_stock_token"}.issubset(kinds)
    assert sources["provider_verified"] is False
    assert client.get("/api/research/v3/market-data/quote?kind=us_equity&symbol=AAPL").status_code==404
    assert client.get("/api/research/v3/market-data/quote?kind=us_etf&symbol=SPY").status_code==404
    assert client.get("/api/research/v3/market-data/quote?kind=okx_stock_token&symbol=XTSLA-USDT").status_code==404


def test_yahoo_us_bar_source_is_not_exchange_realtime_or_okx(monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    bar_time=datetime(2026,10,20,15,30,tzinfo=timezone.utc)
    class Pos:
        def __getitem__(self, n): return 193.12 if n == "Close" else None
    class Index:
        def __getitem__(self, n): return bar_time
    class Iloc:
        def __getitem__(self,n): return Pos()
    class Frame:
        empty=False
        def __len__(self):return 2
        iloc=Iloc()
        index=Index()
    class Ticker:
        def __init__(self,symbol): self.symbol=symbol
        def history(self,**kw):
            assert kw["interval"]=="1m"
            assert kw["auto_adjust"] is False
            assert self.symbol in ("AAPL","SPY")
            return Frame()
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(Ticker=Ticker))
    stock=fetch_public_quote("us_equity","AAPL")
    fund=fetch_public_quote("us_etf","SPY")
    assert stock["value"]==193.12
    assert stock["time_quality"]=="bar_timestamp"
    assert stock["source_timestamp_utc"]==bar_time.replace(tzinfo=None)
    assert fund["time_quality"]=="bar_timestamp"
    assert stock["source_record"]["bar_interval"]=="1m"
    assert stock["source_record"]["session"]=="regular_or_extended_not_individually_verified"


def test_yahoo_missing_timezone_fails_closed(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    class F:
        empty=False
        def __len__(self):return 1
        iloc=SimpleNamespace(__getitem__=lambda self,n: {"Close":120.1})
        index=[datetime(2026,10,20,10,30)]
    class Ticker:
        def __init__(self,s):pass
        def history(self,**kwargs):return F()
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(Ticker=Ticker))
    with pytest.raises(PublicQuoteSourceError):
        fetch_public_quote("us_equity","MSFT")


def test_invalid_us_and_okx_instrument_identifiers_rejected(monkeypatch):
    _enable(monkeypatch)
    for kind,symbol in [
        ("us_equity","../../a"),("us_etf","SPY;evil"),
        ("okx_stock_token","BTC-USDT"),("okx_stock_token","XTSLA-USDT?evil")
    ]:
        assert _refresh(kind,symbol).status_code==422


def test_us_and_okx_are_not_cross_account_ownership(monkeypatch):
    _enable(monkeypatch)
    q=_refresh(kind="us_equity",symbol="AAPL")
    assert q.status_code==200,q.text
    row=q.json()["quote"]
    assert row["currency"]=="USD"
    assert row["metric"]=="bar_close"
    assert row["research_eligible"] is False and row["can_trade"] is False
    okx=_refresh(kind="okx_stock_token",symbol="XTSLA-USDT")
    assert okx.status_code==200,okx.text
    assert okx.json()["quote"]["currency"]=="USDT"
    assert okx.json()["quote"]["product_type"]=="tokenized_stock"
