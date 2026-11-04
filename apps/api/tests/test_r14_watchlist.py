from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
HEADERS = {'Origin':'http://testserver'}


def test_notebook_crud_persists_and_keeps_provenance():
    body = {'kind':'us_equity','symbol':'AAPL','thesis':'业绩待核验','counter_thesis':'估值风险','invalidation':'下季证据不支持','sector':'technology','horizon':'medium_long'}
    r=client.post('/api/research/v3/watchlist',json=body,headers=HEADERS)
    assert r.status_code==201, r.text
    item=r.json();assert item['can_trade'] is False
    assert client.get('/api/research/v3/watchlist').json()['items'][0]['invalidation']==body['invalidation']
    r=client.patch('/api/research/v3/watchlist/'+str(item['id']),json={'thesis':'已补证据'},headers=HEADERS)
    assert r.status_code==200 and r.json()['counter_thesis']=='估值风险'
    r=client.request('DELETE','/api/research/v3/watchlist/'+str(item['id']),json={},headers=HEADERS)
    assert r.status_code==200
    assert client.get('/api/research/v3/watchlist').json()['items']==[]


def test_notebook_rejects_cross_origin_bad_instrument_and_oversize():
    body={'kind':'us_equity','symbol':'AAPL'}
    assert client.post('/api/research/v3/watchlist',json=body).status_code==403
    assert client.post('/api/research/v3/watchlist',json=body,headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/research/v3/watchlist',json={**body,'symbol':'../bad'},headers=HEADERS).status_code==422
    assert client.post('/api/research/v3/watchlist',json={**body,'thesis':'x'*8001},headers=HEADERS).status_code==422


def test_notebook_rejects_malformed_origin_and_supports_explicit_container_host(monkeypatch):
    assert client.post('/api/research/v3/watchlist',json={'kind':'us_equity','symbol':'AAPL'},headers={'Origin':'http://['}).status_code==403
    monkeypatch.setenv('AISTOCK_NOTEBOOK_HOSTS','api')
    r=client.post('/api/research/v3/watchlist',json={'kind':'us_equity','symbol':'AAPL'},headers={'Host':'api:8000','Origin':'http://localhost:3000'})
    assert r.status_code==201
    assert client.get('/api/research/v3/watchlist',headers={'Host':'evil.example'}).status_code==403


def test_loopback_alias_origin_supported():
    r=client.post('/api/research/v3/watchlist',json={'kind':'us_equity','symbol':'AAPL'},headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:3000'})
    assert r.status_code==201
