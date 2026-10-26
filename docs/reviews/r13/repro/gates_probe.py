"""Review-only reproduction against real services; all rows are artificial fixtures."""
import os
if os.environ.get('DATABASE_URL') != 'sqlite:///:memory:':
    raise SystemExit('Set DATABASE_URL=sqlite:///:memory:')
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.models import ScreenerRun, ScreenerCandidate
init_db()
os.environ.update(APP_ENV='production', MARKET_DATA_MODE='real')
client=TestClient(app,raise_server_exceptions=False)
with SessionLocal() as db:
    run=ScreenerRun();db.add(run);db.flush()
    db.add(ScreenerCandidate(screener_run_id=run.id,symbol='600000',rank_no=1,base_score=99));db.commit()
print('GATE readiness',client.get('/api/research/v2/data-readiness').json()['is_research_ready'])
print('GATE recommendation_run',client.post('/api/recommendation/run',json={}).status_code)
result=client.get('/api/recommendation/latest').json()
print('GATE recommendation',result)
print('INPUT missing_paper_fields',client.post('/api/paper/orders',json={}).status_code)
print('LIVE default_gate',client.post('/api/live/order',json={}).status_code)
