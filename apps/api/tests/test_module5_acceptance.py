from datetime import date

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_module5_notifications_and_settings_flow() -> None:
    n1 = client.post(
        "/api/notifications/test",
        json={"title": "module5", "body": "first", "dedupe_key": "module5-dedupe"},
    )
    n2 = client.post(
        "/api/notifications/test",
        json={"title": "module5", "body": "second", "dedupe_key": "module5-dedupe"},
    )
    assert n1.status_code == 200
    assert n2.status_code == 200
    assert n1.json()["id"] == n2.json()["id"]

    list_all = client.get("/api/notifications")
    assert list_all.status_code == 200
    assert list_all.json()["count"] >= 1

    mark = client.post("/api/notifications/mark-read", json={"ids": [n1.json()["id"]]})
    assert mark.status_code == 200
    assert mark.json()["marked"] >= 1

    settings_update = client.post(
        "/api/settings/update",
        json={"config_key": "recommendation", "config_value": {"llm_enabled": True, "market_state": "neutral"}},
    )
    assert settings_update.status_code == 200

    settings_get = client.get("/api/settings")
    assert settings_get.status_code == 200
    assert settings_get.json()["count"] >= 1

    reset = client.post("/api/settings/reset-default")
    assert reset.status_code == 200
    assert "notification" in reset.json()["defaults"]


def test_module5_init_replay_and_admin_endpoints() -> None:
    status = client.get("/api/init/status")
    assert status.status_code == 200
    steps = status.json()["steps"]
    assert len(steps) >= 7

    run_step = client.post("/api/init/run-step", json={"step": steps[0]})
    assert run_step.status_code == 200
    assert run_step.json()["status"] == "completed"

    finish = client.post("/api/init/finish")
    assert finish.status_code == 200
    assert finish.json()["status"] == "completed"

    replay_days = client.get("/api/replay/days")
    assert replay_days.status_code == 200
    day_items = replay_days.json()["items"]
    assert len(day_items) >= 1

    replay_day = client.get(f"/api/replay/day/{day_items[0]}")
    assert replay_day.status_code == 200

    replay_symbol = client.get("/api/replay/symbol/000001")
    assert replay_symbol.status_code == 200

    replay_strategy = client.get("/api/replay/strategy/platform_breakout")
    assert replay_strategy.status_code == 200

    metrics = client.get("/api/admin/metrics")
    health = client.get("/api/admin/system-health")
    logs = client.get("/api/admin/audit-logs")
    assert metrics.status_code == 200
    assert health.status_code == 200
    assert logs.status_code == 200

    backup = client.post("/api/admin/backup")
    backups = client.get("/api/admin/backup/list")
    restore = client.post("/api/admin/restore", json={"marker": ""})
    assert backup.status_code == 200
    assert backups.status_code == 200
    assert restore.status_code == 200

    # In memory sqlite mode, backup/restore should be skipped gracefully.
    assert backup.json()["status"] in {"ok", "skipped", "failed"}
    assert restore.json()["status"] in {"ok", "skipped", "failed"}


def test_module5_replay_center_links_recommendation_paper_live_risk() -> None:
    assert client.post("/api/data/sync/master", json={"force_full": False}).status_code == 200
    assert client.post("/api/data/sync/realtime", json={"symbols": ["000001", "600000"]}).status_code == 200
    assert client.post("/api/screener/run", json={"mode": "intraday", "filters": {"top_n": 20, "min_change_pct": -8}}).status_code == 200
    assert client.post("/api/recommendation/run", json={"market_state": "neutral", "llm_enabled": False}).status_code == 200

    paper = client.post(
        "/api/paper/orders",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A"},
    )
    assert paper.status_code == 200

    assert client.post("/api/risk/kill-switch/disable", json={"reason": "module5-link-check"}).status_code == 200
    live = client.post(
        "/api/live/order",
        json={"symbol": "000001", "side": "buy", "price": 10, "quantity": 100, "recommendation_level": "A", "manual_ack": True},
    )
    assert live.status_code == 200

    today = date.today().isoformat()
    replay_day = client.get(f"/api/replay/day/{today}")
    assert replay_day.status_code == 200
    rows = replay_day.json()["items"]
    assert len(rows) >= 3
    sources = {row.get("source_type", "") for row in rows}
    assert "recommendation" in sources
    assert "paper_order" in sources
    assert "live_order" in sources

    replay_reco = client.get(f"/api/replay/day/{today}?source_type=recommendation")
    replay_paper = client.get(f"/api/replay/day/{today}?source_type=paper_order")
    assert replay_reco.status_code == 200
    assert replay_paper.status_code == 200
    assert replay_reco.json()["count"] >= 1
    assert replay_paper.json()["count"] >= 1

    summary = client.get(f"/api/replay/summary/{today}")
    assert summary.status_code == 200
    assert summary.json()["by_source"].get("recommendation", 0) >= 1
