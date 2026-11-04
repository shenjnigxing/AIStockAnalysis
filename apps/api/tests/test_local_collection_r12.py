"""Operational regression: validate actual CLI and persisted time metadata."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from app.cli import quotes
from app.db.models import PublicQuoteSnapshot
from app.db.session import SessionLocal
from app.services import public_quote_cache as cache
from app.services.public_quote_sources import fetch_public_quote


def test_default_database_path_independent_of_working_directory(tmp_path):
    env = dict(os.environ)
    env.pop('DATABASE_URL', None)
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    command = [sys.executable, '-c', 'from app.core.config import settings; print(settings.database_url)']
    result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True, check=True)
    expected = Path(__file__).resolve().parents[3] / 'data/aistock.local.sqlite3'
    assert result.stdout.strip() == 'sqlite:///' + expected.as_posix()


def test_watchlist_validation_before_any_provider_call(tmp_path):
    path = tmp_path/'list.json'
    path.write_text(json.dumps([{'kind':'us_equity','symbol':'AAPL'}]))
    assert quotes.load_watchlist(path) == [('us_equity','AAPL')]
    for rows in [[], [{'kind':'equity','symbol':'oops'}], [{'kind':'us_equity','symbol':'AAPL','url':'https://evil'}],
                 [{'kind':'us_equity','symbol':'AAPL'}]*2]:
        path.write_text(json.dumps(rows))
        with pytest.raises(ValueError): quotes.load_watchlist(path)


def test_collection_continues_after_one_source_failure(monkeypatch,capsys):
    def fetch(db, *,kind,symbol):
        if symbol == 'AAPL': raise cache.QuoteUnavailable('failed')
        return {'cached':False,'quote':{'symbol':symbol}}
    monkeypatch.setattr(quotes,'refresh_quote',fetch)
    assert quotes.main(['--kind','us_etf','--symbol','QQQ']) == 0
    assert quotes.collect_once([('us_equity','AAPL'),('us_etf','QQQ')]) == 1
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row['state'] for row in output] == ['collected','unavailable','collected']


def test_finite_continuous_collection_and_cadence(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(quotes,'collect_once',lambda items: calls.append(items) or 0)
    monkeypatch.setattr(quotes.time,'sleep',sleeps.append)
    assert quotes.main(['--kind','us_equity','--symbol','AAPL','--cycles','3','--interval','20']) == 0
    assert len(calls) == 3 and sleeps == [20,20]
    with pytest.raises(SystemExit):
        quotes.main(['--kind','us_equity','--symbol','AAPL','--cycles','3'])


@pytest.mark.parametrize('field', ['time_quality','collected_at_utc'])
def test_tampered_freshness_metadata_is_blocked(monkeypatch,field):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    monkeypatch.setattr(cache,'fetch_supervised',lambda *args: {'value':12.3,'source_display_time':'',
        'source_timestamp_utc':None,'time_quality':'time_unverified','source_record':{'value':12.3}})
    with SessionLocal() as db:
        cache.refresh_quote(db,kind='equity',symbol='600000')
        row = db.scalar(select(PublicQuoteSnapshot))
        setattr(row, field, 'provider_update_timestamp' if field == 'time_quality' else datetime.utcnow()+timedelta(days=1))
        db.commit()
        with pytest.raises(cache.QuoteIntegrityError): cache.cached_quote(db,kind='equity',symbol='600000')


@pytest.mark.parametrize('symbol,market',[('IF2612','FF'),('T2612','FF'),('AU2612','CF')])
def test_futures_market_route(monkeypatch,symbol,market):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    calls=[]
    class Frame:
        empty=False
        def __len__(self): return 1
        def iterrows(self): return iter([(0,{'symbol':symbol,'current_price':100,'time':'123000'})])
    def spot(**kw):
        calls.append(kw)
        return Frame()
    monkeypatch.setitem(sys.modules,'akshare',SimpleNamespace(futures_zh_spot=spot))
    assert fetch_public_quote('futures',symbol)['value'] == 100
    assert calls[0]['market'] == market


def test_container_default_path_is_safe():
    from app.core.config import default_database_url
    layout = Path('/app/app/core/config.py').resolve()
    assert default_database_url(layout) == 'sqlite:///' + (layout.parents[2] / 'data/aistock.local.sqlite3').as_posix()
