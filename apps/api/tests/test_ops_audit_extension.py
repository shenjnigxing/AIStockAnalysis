from fastapi.testclient import TestClient
from sqlalchemy import desc, select

from app.db.models import AuditLog
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _latest_action(action: str) -> AuditLog | None:
    with SessionLocal() as db:
        return db.scalar(select(AuditLog).where(AuditLog.action == action).order_by(desc(AuditLog.created_at)))


def test_notification_dedupe_and_mark_read_audit() -> None:
    first = client.post(
        "/api/notifications/test",
        json={"source_type": "system", "level": "info", "title": "n1", "body": "b1", "dedupe_key": "dup-001"},
    )
    second = client.post(
        "/api/notifications/test",
        json={"source_type": "system", "level": "info", "title": "n2", "body": "b2", "dedupe_key": "dup-001"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    marked = client.post("/api/notifications/mark-read", json={"ids": [first.json()["id"]]})
    assert marked.status_code == 200
    assert marked.json()["marked"] == 1

    dedupe_hit = _latest_action("notification.dedupe_hit")
    assert dedupe_hit is not None
    mark_read = _latest_action("notification.mark_read")
    assert mark_read is not None


def test_init_and_risk_and_admin_and_backtest_audit() -> None:
    assert client.post("/api/init/run-step", json={"step": "env_check"}).status_code == 200
    assert client.post("/api/init/finish").status_code == 200
    assert client.post("/api/risk/kill-switch/enable", json={"reason": "audit-test"}).status_code == 200
    assert client.post("/api/risk/kill-switch/disable", json={"reason": "audit-test"}).status_code == 200
    assert client.post("/api/admin/backup").status_code == 200
    assert client.post("/api/admin/restore").status_code == 200
    assert client.post("/api/backtest/run", json={"name": "audit-backtest", "initial_cash": 1000000}).status_code == 200
    assert client.post("/api/recommendation/run", json={"market_state": "neutral", "llm_enabled": False}).status_code == 200

    assert _latest_action("init.run_step") is not None
    assert _latest_action("init.finish") is not None
    assert _latest_action("risk.kill_switch_enable") is not None
    assert _latest_action("risk.kill_switch_disable") is not None
    assert _latest_action("admin.backup") is not None
    assert _latest_action("admin.restore") is not None
    assert _latest_action("backtest.run") is not None
    assert _latest_action("recommendation.run") is not None
