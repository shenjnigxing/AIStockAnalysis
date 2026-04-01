from fastapi.testclient import TestClient
from sqlalchemy import desc, select

from app.db.models import AuditLog
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def test_paper_order_audit_contains_request_id() -> None:
    rid = "rid-paper-001"
    response = client.post(
        "/api/paper/orders",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
        headers={"X-Request-ID": rid},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        log = db.scalar(select(AuditLog).where(AuditLog.action == "paper.place").order_by(desc(AuditLog.created_at)))
        assert log is not None
        assert f"request_id={rid}" in log.detail

