"""Research eligibility, quote qualification and filter contracts."""
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db.session import SessionLocal
from app.db.models import StockMaster, RealtimeQuote, RecommendationRun, DailyBar
from app.services.recommendation import RecommendationService
from app.services.screener import ScreenerService
from app.services.research_gate import ResearchEligibilityError
from recommendation_core.recommendation import _risk_from_tags
from app.services.multi_asset_research import _asset_risks

client = TestClient(app)


@pytest.mark.parametrize('environment,mode', [('production','real'), ('dev','real'), ('production','mock'), ('dev','mock'), ('test','real')])
def test_legacy_research_reads_and_writes_fail_closed(monkeypatch,environment,mode):
    monkeypatch.setenv('APP_ENV',environment)
    monkeypatch.setenv('MARKET_DATA_MODE',mode)
    for path in ['/latest','/top','/history','/history/list','/600000']:
        assert client.get('/api/recommendation'+path).status_code == 409
    assert client.post('/api/recommendation/run',json={}).status_code == 409
    with SessionLocal() as db:
        with pytest.raises(ResearchEligibilityError): RecommendationService(db).run()
        assert db.scalar(select(RecommendationRun.id)) is None


def test_explicit_test_demo_has_honest_contract():
    assert client.post('/api/recommendation/run',json={}).status_code == 200
    body = client.get('/api/screener/candidates/latest').json()
    assert body['source_grade'] == 'synthetic_demo'
    assert body['can_trade'] is False
    assert body['confidence_is_probability'] is False
    with SessionLocal() as db:
        service = RecommendationService(db)
        assert service._action_suggestion('A','bullish',0) == 'demo_research'


@pytest.mark.parametrize('filters', [{'min_market_cap_yi':30},{'exclude_st':False},{'industry':'bank'},{'financial_health':True},{'min_price':10,'max_price':1},{'top_n':0}])
def test_unknown_or_unsupported_filters_are_not_silently_accepted(filters):
    assert client.post('/api/screener/run',json={'filters':filters}).status_code == 422
    assert client.post('/api/screener/presets',json={'name':'bad','params':filters}).status_code == 422


def test_missing_preset_fields_returns_422():
    assert client.post('/api/screener/presets',json={}).status_code == 422


@pytest.mark.parametrize('variant', ['missing_master','inactive','st','stale','future','missing_history'])
def test_real_screener_never_promotes_ineligible_quote(monkeypatch,variant):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    now = datetime.utcnow()
    with SessionLocal() as db:
        if variant != 'missing_master':
            db.add(StockMaster(symbol='600000',name='*ST样本' if variant=='st' else '样本',market='SH',is_active=variant!='inactive'))
        quoted=now-timedelta(days=100) if variant=='stale' else now+timedelta(minutes=1) if variant=='future' else now
        db.add(RealtimeQuote(symbol='600000',quote_time=quoted,price=12,change_pct=3,amount=1e8,volume=1e6))
        if variant != 'missing_history':
            for i in range(20):
                db.add(DailyBar(symbol='600000',trade_date=now.date()-timedelta(days=i),
                    open=11,high=13,low=10,close=12,volume=1e6,amount=1e8))
        db.commit()
        service = ScreenerService(db)
        service.run({})
        assert service.latest_candidates() == []


def test_weak_volume_aliases_have_identical_single_penalty():
    canonical = _risk_from_tags(['weak_volume'],'neutral')
    assert canonical[0] == 8
    assert _risk_from_tags(['weak_volume_support'],'neutral') == canonical
    assert _risk_from_tags(['weak_volume','weak_volume_support'],'neutral') == canonical


@pytest.mark.parametrize('margin', [.01,.12,.35])
def test_futures_without_position_stress_model_are_all_blocked(margin):
    from datetime import date
    penalty, warnings, blocks = _asset_risks({'asset_class':'futures','product_type':'commodity_future',
        'metadata':{'expiry':date.today()+timedelta(days=100),'margin_ratio':margin}}, date.today())
    assert any('头寸' in block for block in blocks)
    assert penalty == 0


def test_qualified_observation_is_not_promoted_to_verified_recommendation(monkeypatch):
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    now=datetime.utcnow()
    with SessionLocal() as db:
        db.add(StockMaster(symbol='600000',name='样本',market='SH',is_active=True))
        db.add(RealtimeQuote(symbol='600000',quote_time=now,price=12,change_pct=3,amount=1e8,volume=1e6))
        for i in range(20):
            db.add(DailyBar(symbol='600000',trade_date=now.date()-timedelta(days=i),
                open=11,high=13,low=10,close=12,volume=1e6,amount=1e8))
        db.commit()
        ScreenerService(db).run({})
    body=client.get('/api/screener/candidates/latest').json()
    assert len(body['items'])==1
    assert body['source_grade']=='unverified_legacy_store' and body['can_trade'] is False
    assert client.post('/api/recommendation/run',json={}).status_code==409
