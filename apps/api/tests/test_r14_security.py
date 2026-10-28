import os
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.api.deps import get_db
from app.db.base import Base
from app.db.models import PaperOrder, PaperIdempotency
from app.db.session import SessionLocal

TOKEN='separate-admin-secret-at-least-32-characters'
ORDER={'symbol':'600000','side':'buy','price':10,'quantity':100,'recommendation_level':'A'}


def test_admin_authority_separate_and_fail_closed(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('MARKET_DATA_MODE','real')
    monkeypatch.delenv('AISTOCK_ADMIN_TOKEN',raising=False)
    monkeypatch.setenv('AISTOCK_RESEARCH_INGEST_TOKEN',TOKEN)
    with TestClient(app) as client:
        for url in ['/api/settings','/api/risk/status','/api/admin/audit-logs']:
            assert client.get(url).status_code==503
        monkeypatch.setenv('AISTOCK_ADMIN_TOKEN',TOKEN)
        assert client.post('/api/risk/kill-switch/disable',json={}).status_code==403
        assert client.get('/api/settings',headers={'X-Research-Admin-Token':TOKEN}).status_code==403
        headers={'X-Aistock-Admin-Token':TOKEN}
        assert client.post('/api/settings/update',headers=headers,json={'config_key':'probe','config_value':{'safe':True}}).status_code==200
        assert client.get('/api/settings',headers=headers).status_code==200
        assert client.post('/api/settings/update',headers=headers,json={}).status_code==422
        assert client.post('/api/live/order',headers=headers,json={}).status_code==403


def test_paper_idempotency_and_conflicting_payload():
    with TestClient(app) as client:
        headers={'Idempotency-Key':'same-order'}
        a=client.post('/api/paper/orders',headers=headers,json=ORDER)
        b=client.post('/api/paper/orders',headers=headers,json=ORDER)
        assert a.status_code==b.status_code==200
        assert a.json()==b.json()
        assert client.post('/api/paper/orders',headers=headers,json={**ORDER,'quantity':200}).status_code==409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder))==1
        assert db.scalar(select(func.count()).select_from(PaperIdempotency))==1


def test_paper_invalid_payloads_are_422():
    with TestClient(app) as client:
        for data in [{},{**ORDER,'side':'oops'},{**ORDER,'quantity':-100},{**ORDER,'price':-1},{**ORDER,'quantity':'100'}]:
            assert client.post('/api/paper/orders',json=data).status_code==422
            assert client.post('/api/paper/order/preview',json=data).status_code==422


def test_concurrent_duplicate_key_has_one_persistent_order(tmp_path):
    # Dedicated disposable file tests the unique claim across independent sessions.
    engine=create_engine('sqlite:///'+str(tmp_path/'concurrent-test.sqlite3'),connect_args={'check_same_thread':False,'timeout':15})
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    def sessions():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=sessions
    try:
        # One application lifespan; concurrent requests use separate DB sessions.
        # Starting two app lifespans races schema inspection on the shared test engine.
        with TestClient(app) as client:
            def submit(_):
                r=client.post('/api/paper/orders',headers={'Idempotency-Key':'concurrent'},json=ORDER)
                return r.status_code,r.json()
            with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(submit,range(2)))
        assert all(status==200 for status,_ in results),results
        assert results[0][1]==results[1][1]
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(PaperOrder))==1
            assert db.scalar(select(func.count()).select_from(PaperIdempotency))==1
    finally:
        app.dependency_overrides.pop(get_db,None)
        engine.dispose()


def test_order_failure_rolls_back_reservation_and_all_effects(monkeypatch):
    from app.services.paper_trading import PaperTradingService
    def broken(*args): raise RuntimeError('injected matcher failure')
    monkeypatch.setattr(PaperTradingService,'_match',broken)
    with TestClient(app,raise_server_exceptions=False) as client:
        assert client.post('/api/paper/orders',headers={'Idempotency-Key':'failed'},json=ORDER).status_code==500
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder))==0
        assert db.scalar(select(func.count()).select_from(PaperIdempotency))==0


def test_real_paper_order_requires_idempotency_and_init_missing_field_is_422(monkeypatch):
    with TestClient(app) as client:
        assert client.post('/api/init/run-step',json={}).status_code==422
        monkeypatch.setenv('APP_ENV','dev')
        monkeypatch.setenv('MARKET_DATA_MODE','real')
        assert client.post('/api/paper/orders',json=ORDER).status_code==422
