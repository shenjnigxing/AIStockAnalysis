import importlib
import sqlite3
from datetime import datetime, timedelta

import pytest
import pandas as pd
from fastapi.testclient import TestClient

import core.data_manager as dm
import core.strategies as strat


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "test_stock.db"
    monkeypatch.setattr(dm, "DB_PATH", str(db))
    dm.init_db()

    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            INSERT INTO daily_market (code, date, name, price, pe, pb, turnover, volume, amount, change_pct)
            VALUES
            ('600000','2026-03-31','浦发银行',10.2,6.1,0.8,1.2,100000,300000000,1.5),
            ('000001','2026-03-31','平安银行',12.8,8.4,1.1,2.5,150000,500000000,2.2),
            ('300001','2026-03-31','特锐德',22.5,25.3,2.2,12.5,220000,680000000,4.5),
            ('688001','2026-03-31','华兴科技',35.2,52.0,6.5,18.0,500000,1200000000,20.1),
            ('002999','2026-03-31','ST测试',3.2,0.0,0.0,1.0,50000,90000000,-1.2)
            """
        )
        conn.execute(
            """
            INSERT INTO stock_basic (code, name, list_date, total_shares, float_shares, industry, area, market)
            VALUES ('600000', '浦发银行', '1999-11-10', 293.52, 281.23, '银行', '上海', '主板')
            """
        )
        conn.execute(
            """
            INSERT INTO stock_holder (code, report_date, holder_count, avg_holdings, top10_holder_ratio, top10_flow_ratio)
            VALUES
            ('600000','2025-12-31',120000,23.1,58.2,21.3),
            ('600000','2025-09-30',126000,21.8,57.7,20.5)
            """
        )

        base_day = datetime(2026, 2, 1)
        for i in range(50):
            d = (base_day + timedelta(days=i)).strftime("%Y-%m-%d")
            close = 10 + i * 0.05
            open_price = close - 0.1
            high = close + 0.2
            low = close - 0.2
            volume = 100000 + i * 100
            if i == 49:
                volume = 300000
            conn.execute(
                """
                INSERT INTO kline_data
                (code, date, open, high, low, close, volume, amount, change_pct, amplitude, frequency, adjust_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'daily', 'bfq')
                """,
                ("600000", d, open_price, high, low, close, volume, 80000000 + i * 10000, 0.5, 1.2),
            )

        for i in range(50):
            d = (base_day + timedelta(days=i)).strftime("%Y-%m-%d")
            close = 20 - i * 0.08
            open_price = close + 0.05
            high = close + 0.15
            low = close - 0.25
            volume = 90000
            if i == 49:
                volume = 70000
            conn.execute(
                """
                INSERT INTO kline_data
                (code, date, open, high, low, close, volume, amount, change_pct, amplitude, frequency, adjust_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'daily', 'bfq')
                """,
                ("000001", d, open_price, high, low, close, volume, 50000000 + i * 5000, -0.3, 1.0),
            )

        conn.execute(
            """
            INSERT INTO financial_data
            (code, report_date, pub_date, roe_avg, net_profit, total_revenue)
            VALUES
            ('600000', '2025-12-31', '2026-03-01', 12.5, 1200000000, 8000000000),
            ('600000', '2024-12-31', '2025-03-01', 9.8, 1000000000, 7600000000),
            ('000001', '2025-12-31', '2026-03-01', 8.2, 800000000, 6000000000),
            ('000001', '2024-12-31', '2025-03-01', 8.0, 790000000, 5900000000)
            """
        )

        conn.commit()
    finally:
        conn.close()

    from core.main import app

    client = TestClient(app)
    yield client


def test_stocks_sort_and_pagination(temp_db):
    resp = temp_db.get("/api/market/stocks?page=1&page_size=2&sort_by=change_pct&sort_order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page_size"] == 2
    assert data["data"][0]["code"] == "688001"


def test_stocks_code_prefix_filter(temp_db):
    resp = temp_db.get("/api/market/stocks?code_prefix=60&page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["data"][0]["code"].startswith("60")


def test_stocks_fuzzy_by_code_param(temp_db):
    resp = temp_db.get("/api/market/stocks?code=平安&page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("平安" in x["name"] for x in data["data"])


def test_search_and_resolve_stock_endpoint(temp_db):
    search = temp_db.get("/api/market/search_stocks?q=浦发")
    assert search.status_code == 200
    s = search.json()
    assert s["count"] >= 1
    assert any(x["code"] == "600000" for x in s["items"])

    resolve = temp_db.get("/api/market/resolve_stock?q=浦发银行")
    assert resolve.status_code == 200
    assert resolve.json()["code"] == "600000"


def test_stocks_combined_filters_and_st_exclusion(temp_db):
    resp = temp_db.get("/api/market/stocks?code_prefixes=68&only_limit_up=true&page=1&page_size=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["code"] == "688001"

    resp2 = temp_db.get("/api/market/stocks?exclude_st=true&page=1&page_size=20")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert all("ST" not in x["name"] for x in body2["data"])


def test_screen_supports_sort_and_pages(temp_db):
    resp = temp_db.get("/api/market/screen?page=1&page_size=1&sort_by=turnover&sort_order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["pages"] == 4
    assert len(data["data"]) == 1
    assert data["data"][0]["code"] == "688001"


def test_holder_endpoint(temp_db):
    resp = temp_db.get("/api/market/holder/600000")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["data"][0]["top10_ratio"] == 58.2


def test_invalid_code_validation(temp_db):
    resp = temp_db.get("/api/market/basic/ABC")
    assert resp.status_code == 422


def test_invalid_sort_validation_returns_422(temp_db):
    resp = temp_db.get("/api/market/stocks?sort_by=unknown")
    assert resp.status_code == 422

    resp = temp_db.get("/api/market/screen?sort_order=sideways")
    assert resp.status_code == 422


def test_screen_enrichment_filters_work(temp_db):
    resp = temp_db.get(
        "/api/market/screen?ma5_above=true&volume_ratio_min=2&roe_min=10&profit_growth_min=10"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["code"] == "600000"
    assert body["data"][0]["volume_ratio"] >= 2
    assert body["data"][0]["latest_roe_avg"] >= 10
    assert body["data"][0]["profit_growth_pct"] >= 10


def test_strategy_multi_endpoint(temp_db):
    resp = temp_db.get("/api/market/strategy_multi?strategy_ids=breakthrough,macd_golden&top_n=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body
    assert "backtest_summary" in body


def test_stats_endpoint_exposes_limit_counts_and_refresh_time(temp_db):
    resp = temp_db.get("/api/market/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_stocks"] == 5
    assert body["limit_up_count"] == 1
    assert body["limit_down_count"] == 0
    assert body["latest_refresh_at"] is not None
    assert "沪深A股" in body["market_coverage_label"]


def test_strategy_endpoint_marks_fallback_when_native_signal_missing(temp_db):
    resp = temp_db.get("/api/market/strategy/breakthrough?top_n=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is True
    assert body["native_total_found"] == 0
    assert isinstance(body["recommendations"], list)
    assert len(body["recommendations"]) == 3
    assert "快速评分" in body["fallback_reason"]


def test_first_limit_strategy_uses_enough_calendar_days_for_60_trading_day_check(monkeypatch):
    market_df = pd.DataFrame([
        {"code": "600111", "name": "北方稀土", "price": 12.3, "change_pct": 10.0, "turnover": 6.2}
    ])
    captured = {}

    hist_rows = []
    base = datetime(2026, 1, 1)
    for i in range(70):
        cp = 0.5
        if i == 69:
            cp = 10.0
        hist_rows.append({
            "date": (base + timedelta(days=i)).strftime("%Y-%m-%d"),
            "close": 10 + i * 0.01,
            "change_pct": cp,
        })
    hist_df = pd.DataFrame(hist_rows)

    def fake_get_kline_data(code, days=80):
        captured["days"] = days
        return hist_df

    monkeypatch.setattr(strat, "get_kline_data", fake_get_kline_data)
    rows = strat.strategy_first_limit(market_df)
    assert captured["days"] >= 140
    assert len(rows) == 1
    assert rows[0]["code"] == "600111"


def test_strategy_multi_empty_ids_fallback(temp_db):
    resp = temp_db.get("/api/market/strategy_multi?strategy_ids=&top_n=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body
    assert isinstance(body["recommendations"], list)


def test_indicator_endpoint(temp_db):
    resp = temp_db.get("/api/market/kline/600000/indicators?days=40&frequency=daily")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    first = body["data"][-1]
    assert "macd" in first
    assert "k" in first


def test_kline_adjust_flag_maps_to_baostock(monkeypatch, temp_db):
    import pandas as pd
    import core.api_routes as routes

    calls = []

    def fake_get_kline_data(code, start_date, end_date, adjust_flag, frequency):
        return pd.DataFrame()

    def fake_fetch_kline_history(code, start_date, end_date, adjust_flag):
        calls.append((code, adjust_flag))
        return pd.DataFrame([
            {
                "date": "2026-03-31",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 100000,
                "amount": 2000000,
            }
        ])

    monkeypatch.setattr(routes, "get_kline_data", fake_get_kline_data)
    monkeypatch.setattr(routes, "fetch_kline_history", fake_fetch_kline_history)

    resp = temp_db.get("/api/market/kline/600000?adjust_flag=qfq")
    assert resp.status_code == 200
    assert calls == [("sh.600000", "2")]
    body = resp.json()
    assert body["data"][0]["adjust_flag"] == "qfq"


def test_algo_signal_endpoint(temp_db):
    resp = temp_db.get("/api/market/kline/600000/algo_signals?days=40&frequency=daily")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    assert "summary" in body
    assert "markers" in body
    last = body["data"][-1]
    assert "algo_score" in last
    assert "signal_streak" in last


def test_strategy_leaderboard_endpoint(temp_db):
    resp = temp_db.get("/api/market/strategy_leaderboard?top_n=3&sort_metric=ret_20d")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "sort_metric" in body


def test_data_quality_endpoint(temp_db):
    resp = temp_db.get("/api/market/data_quality")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "metrics" in body


def test_runtime_status_endpoint(temp_db):
    resp = temp_db.get("/api/market/runtime_status")
    assert resp.status_code == 200
    body = resp.json()
    assert "db" in body
    assert "sources" in body
    assert "latest_date" in body


def test_compat_system_status_endpoint(temp_db):
    resp = temp_db.get("/api/system/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_compat_recommendation_top_endpoint(temp_db):
    resp = temp_db.get("/api/recommendation/top?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


def test_create_app_initializes_db_on_startup(tmp_path, monkeypatch):
    db = tmp_path / "startup_stock.db"
    monkeypatch.setattr(dm, "DB_PATH", str(db))

    import core.main as main_module

    app = main_module.create_app()
    with TestClient(app) as client:
        resp = client.get("/api/system/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert db.exists()


def test_create_app_mounts_static_assets():
    import core.main as main_module

    app = main_module.create_app()
    with TestClient(app) as client:
        resp = client.get("/static/chart.html")

    assert resp.status_code == 200
    assert "K 线" in resp.text


def test_ops_page_route_exists():
    import core.main as main_module

    app = main_module.create_app()
    with TestClient(app) as client:
        resp = client.get("/ops")

    assert resp.status_code == 200
    assert "系统维护" in resp.text


def test_run_api_does_not_add_duplicate_root_routes():
    import run_api as run_api_module

    importlib.reload(run_api_module)
    root_routes = [route for route in run_api_module.app.routes if getattr(route, "path", None) == "/"]
    assert len(root_routes) == 1
