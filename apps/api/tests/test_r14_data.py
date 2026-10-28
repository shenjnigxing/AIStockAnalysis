"""Data identity, dimensional correctness and incremental-boundary regressions."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
import sys

import pytest
from sqlalchemy import select

from app.db.models import DailyBar, PublicQuoteSnapshot, SyncCheckpoint
from app.db.session import SessionLocal
from app.services import public_quote_cache as cache
from app.services.public_quote_sources import fetch_public_quote, source_spec, PublicQuoteSourceError
from app.services.data_sync import DataSyncService


class Frame:
    empty = False
    def __init__(self, rows): self.rows = rows
    def __len__(self): return len(self.rows)
    def iterrows(self): return iter(enumerate(self.rows))


@pytest.mark.parametrize('symbol,unit,value', [('Au99.99','CNY/g',800), ('Ag99.99','CNY/kg',8500)])
def test_instrument_units_survive_persistence_and_integrity(monkeypatch,symbol,unit,value):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    monkeypatch.setitem(sys.modules,'akshare',SimpleNamespace(spot_quotations_sge=lambda **_: Frame([
        {'品种':symbol,'现价':value,'更新时间':''}])) )
    observation=fetch_public_quote('sge_gold',symbol)
    monkeypatch.setattr(cache,'fetch_supervised',lambda *_:observation)
    with SessionLocal() as db:
        output=cache.refresh_quote(db,kind='sge_gold',symbol=symbol)['quote']
        assert output['unit']==unit and output['value']==value
        assert cache.cached_quote(db,kind='sge_gold',symbol=symbol)['unit']==unit
        if symbol=='Ag99.99':
            row=db.get(PublicQuoteSnapshot,output['id']);row.unit='CNY/g';db.commit()
            with pytest.raises(cache.QuoteIntegrityError): cache.cached_quote(db,kind='sge_gold',symbol=symbol)


@pytest.mark.parametrize('identity',[{}, {'symbol':'螺纹钢2612'}, {'symbol':'RB2612'}, {'contract':'AU2611'},
                                      {'contract':'AU2612','code':'RB2612'}])
def test_unverified_or_wrong_futures_identity_is_rejected(monkeypatch,identity):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    monkeypatch.setitem(sys.modules,'akshare',SimpleNamespace(futures_zh_spot=lambda **_:Frame([
        {**identity,'current_price':3333,'time':'220000'}])))
    with pytest.raises(PublicQuoteSourceError,match='identity'): fetch_public_quote('futures','AU2612')


def _bar(day,symbol='600000'):
    return dict(symbol=symbol,trade_date=day,open=10,high=11,low=9,close=10,volume=100,amount=1000)


@pytest.mark.parametrize('rows',[
    [_bar(date(2099,1,1))], [_bar(date(2026,9,1))], [_bar(date(2026,10,21))],
    [_bar(date(2026,10,19),'600001')], [_bar('2026-10-19')],
    [_bar(date(2026,10,19)),_bar(date(2026,10,19))],
    [_bar(date(2026,10,19)),_bar(date(2026,10,18))],
])
def test_bad_window_rejects_all_prices_and_does_not_advance(monkeypatch,rows):
    with SessionLocal() as db:
        service=DataSyncService(db)
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',lambda **_:rows)
        job=service.sync_daily(['600000'],date(2026,10,17),date(2026,10,20))
        assert job.status=='failed'
        assert db.scalar(select(DailyBar.id)) is None
        cp=db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.scope_key=='600000'))
        assert cp is not None and cp.checkpoint_value==''


def test_partial_window_keeps_actual_watermark_and_revisits_missing_day(monkeypatch):
    with SessionLocal() as db:
        service=DataSyncService(db)
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',lambda **_:[_bar(date(2026,10,19))])
        first=service.sync_daily(['600000'],date(2026,10,17),date(2026,10,20))
        assert first.status=='completed'
        cp=db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.scope_key=='600000'))
        assert cp.checkpoint_value=='2026-10-19'
        requested=[]
        def fetch(**kw):
            requested.append(kw)
            return [_bar(date(2026,10,19)),_bar(date(2026,10,20))]
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',fetch)
        assert service.sync_daily(['600000'],None,date(2026,10,20)).status=='completed'
        assert requested[0]['start_date'] <= date(2026,10,19)
        assert cp.checkpoint_value=='2026-10-20'
        assert len(db.scalars(select(DailyBar)).all())==2
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',lambda **_:[])
        assert service.sync_daily(['600000'],None,date(2026,10,21)).status=='completed'
        assert cp.checkpoint_value=='2026-10-20'


def test_today_observation_never_certifies_completed_day(monkeypatch):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    with SessionLocal() as db:
        service = DataSyncService(db)
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',lambda **_:[_bar(today)])
        job = service.sync_daily(['600000'],today,today)
        assert job.status == 'completed'
        cp = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.scope_key=='600000'))
        assert cp.checkpoint_value == ''
        assert db.scalar(select(DailyBar.id)) is not None


def test_old_invented_watermark_is_not_preserved(monkeypatch):
    with SessionLocal() as db:
        db.add(SyncCheckpoint(job_type='daily',scope_key='600000',checkpoint_value='2026-10-20'))
        db.commit()
        service = DataSyncService(db)
        monkeypatch.setattr(service.adapter,'fetch_daily_bars',lambda **_:[_bar(date(2026,10,19))])
        assert service.sync_daily(['600000'],date(2026,10,17),date(2026,10,20)).status == 'completed'
        cp = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.scope_key=='600000'))
        assert cp.checkpoint_value == '2026-10-19'
