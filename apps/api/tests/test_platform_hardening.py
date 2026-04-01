from fastapi.testclient import TestClient

from app.main import app
from app.services.broker import EastMoneyAdapter, MockBroker, get_broker


client = TestClient(app)


def test_request_id_roundtrip() -> None:
    response = client.get("/health", headers={"X-Request-ID": "rid-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "rid-123"


def test_broker_factory() -> None:
    assert isinstance(get_broker("mock"), MockBroker)
    assert isinstance(get_broker("eastmoney"), EastMoneyAdapter)

