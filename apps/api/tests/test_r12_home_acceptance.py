"""R1.2 home-execution acceptance: no hardcoded machine path, no secrets, no web refresh."""
from datetime import datetime, timedelta
import json
import re
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.config import _DEFAULT_DB
from app.cli.market_data import main as cli_main
from app.db.models import PublicQuoteSnapshot, PublicQuoteFetchAttempt
from app.db.session import SessionLocal
from app.services import public_quote_cache

client=TestClient(app)


def test_default_db_path_is_repo_local_and_cross_platform():
    assert "workstation" not in _DEFAULT_DB.lower()
    assert "E:/workstation" not in _DEFAULT_DB
    assert _DEFAULT_DB.endswith("/data/aistock.local.sqlite3")


def test_offline_doctor_does_not_fetch_external_data(monkeypatch, capsys):
    def fail(*_args):
        raise AssertionError("doctor must not fetch public websites")
    monkeypatch.setattr(public_quote_cache, "fetch_supervised", fail)
    assert cli_main(["doctor"]) == 0
    output=capsys.readouterr().out
    data=json.loads(output)
    assert data["can_generate_real_recommendations"] is False
    assert data["broker_accounts_connected"] is False
    assert len(data["providers"]) == 8
    assert "postgresql://" not in output


def test_cli_refresh_is_readable_by_api_without_browser_credentials(monkeypatch, capsys):
    monkeypatch.setenv("MARKET_DATA_MODE", "real")
    monkeypatch.setattr(public_quote_cache, "fetch_supervised", lambda kind, symbol: {
        "value": 201.0, "source_display_time": "",
        "source_timestamp_utc": None, "time_quality": "time_unverified",
        "source_record": {"symbol": symbol, "price": 201.0},
    })
    assert cli_main(["refresh", "--kind", "us_equity", "--symbol", "AAPL"]) == 0
    written=json.loads(capsys.readouterr().out)
    assert written["quote"]["currency"] == "USD"
    assert written["quote"]["can_trade"] is False
    result=client.get("/api/research/v3/market-data/quote?kind=us_equity&symbol=AAPL")
    assert result.status_code == 200
    assert result.json()["value"] == 201.0
    assert cli_main(["status","--kind","us_equity","--symbol","AAPL"]) == 0
    assert json.loads(capsys.readouterr().out)["value"] == 201.0


def test_cli_bad_symbol_never_fetches(monkeypatch, capsys):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    monkeypatch.setattr(public_quote_cache, "fetch_supervised", lambda *_: (
        _ for _ in ()
    ).throw(AssertionError("no network")))
    assert cli_main(["refresh","--kind","us_equity","--symbol","../../etc"]) == 2
    assert "输入错误" in capsys.readouterr().err


def test_cli_missing_quote_and_mock_mode_closed(monkeypatch,capsys):
    assert cli_main(["status","--kind","us_equity","--symbol","AAPL"]) == 3
    assert "未发现本地行情" in capsys.readouterr().err
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    assert cli_main(["refresh","--kind","us_equity","--symbol","AAPL"]) == 4
    assert "QuoteUnavailable" in capsys.readouterr().err


def test_provider_failure_state_available_but_not_misleading(monkeypatch):
    with SessionLocal() as db:
        db.add(PublicQuoteFetchAttempt(
            kind="us_equity",symbol="AAPL",
            attempted_at_utc=datetime.utcnow(),
            duration_ms=12000,state="failure",error_code="provider_timeout"))
        db.commit()
    response=client.get("/api/research/v3/market-data/sources")
    assert response.status_code == 200
    row=next(x for x in response.json()["providers"] if x["kind"]=="us_equity")
    assert row["last_attempt_state"]=="failure"
    assert row["last_error_code"]=="provider_timeout"
    assert row["has_cached_snapshot"] is False


def test_reject_unbounded_untrusted_request_id():
    bad="x"*500
    response=client.get("/health",headers={"X-Request-ID":bad})
    assert response.status_code==200
    assert response.headers["X-Request-ID"]!=bad
    assert re.fullmatch(r"[a-f0-9-]{36}",response.headers["X-Request-ID"])
    normal=client.get("/health",headers={"X-Request-ID":"test_session-42"})
    assert normal.headers["X-Request-ID"]=="test_session-42"


def test_quote_cache_stale_source_separate_from_request_duration(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE","real")
    moment=datetime.utcnow()-timedelta(hours=2)
    monkeypatch.setattr(public_quote_cache,"fetch_supervised",lambda *_:{
        "value":192.2,"source_display_time":"2 hours ago",
        "source_timestamp_utc":moment,
        "time_quality":"bar_timestamp",
        "source_record":{"close":192.2},
    })
    from app.services.public_quote_cache import refresh_quote
    with SessionLocal() as db:
        row=refresh_quote(db,kind="us_equity",symbol="AAPL")["quote"]
    assert row["freshness"]=="stale_source"
    assert row["cache_age_seconds"] < 30
    assert row["source_age_seconds"] >= 7000
    assert row["request_duration_ms"] >= 0


def test_legacy_real_order_account_mutations_are_off_by_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("BROKER_PROVIDER", "mock")
    for method,path in [
        ("post","/api/live/order"),
        ("post","/api/live/order/preview"),
        ("post","/api/live/order/1/cancel"),
        ("post","/api/live/sync/account"),
        ("get","/api/live/orders"),
        ("get","/api/live/positions"),
        ("get","/api/live/assets"),
        ("get","/api/live/broker/status"),
        ("get","/api/live/broker/capabilities"),
    ]:
        response=client.post(path,json={}) if method=="post" else client.get(path)
        assert response.status_code==403,(path,response.text)
        assert "disabled" in response.json()["detail"]


def test_live_capability_requires_both_test_environment_and_mock_broker(monkeypatch):
    from fastapi import HTTPException
    from app.api.routes.live import _require_test_only_live
    monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("BROKER_PROVIDER","mock")
    assert _require_test_only_live() is None
    monkeypatch.setenv("BROKER_PROVIDER","real")
    with pytest.raises(HTTPException) as exc:
        _require_test_only_live()
    assert exc.value.status_code==403
