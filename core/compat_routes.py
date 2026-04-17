"""兼容接口路由：为旧版前端/外部面板提供适配层，避免 404 噪音。"""

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from core.data_manager import get_db_connection
from core.strategies import STRATEGIES, run_multi_strategies

router = APIRouter(prefix="/api", tags=["compat"])


def _empty_page() -> Dict[str, Any]:
    return {"total": 0, "items": []}


@router.get("/system/status")
async def system_status():
    conn = get_db_connection()
    latest = pd.read_sql("SELECT MAX(date) AS d, MAX(created_at) AS t FROM daily_market", conn).iloc[0].to_dict()
    conn.close()
    return {
        "status": "ok",
        "service": "a-share-data-engine",
        "time": datetime.now().isoformat(),
        "latest_date": latest.get("d"),
        "latest_refresh_at": latest.get("t"),
    }


@router.get("/init/status")
async def init_status():
    return {"initialized": True, "status": "ready", "message": "system ready"}


@router.get("/strategy/list")
async def strategy_list():
    return {
        "items": [
            {"id": k, "name": v["name"], "desc": v["desc"], "risk": v["risk"], "suitable": v["suitable"]}
            for k, v in STRATEGIES.items()
        ]
    }


@router.get("/recommendation/top")
async def recommendation_top(limit: int = Query(20, ge=1, le=200)):
    # 兼容接口优先快速返回，避免旧面板超时
    conn = get_db_connection()
    df = pd.read_sql(
        """
        SELECT code, name, price, change_pct, turnover, amount, pe, pb
        FROM daily_market
        WHERE date = (SELECT MAX(date) FROM daily_market)
        ORDER BY change_pct DESC, turnover DESC
        LIMIT ?
        """,
        conn,
        params=[limit],
    )
    conn.close()
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": len(df),
        "items": df.to_dict("records"),
    }


@router.get("/recommendation/{code}")
async def recommendation_by_code(code: str):
    items = run_multi_strategies(list(STRATEGIES.keys()), top_n=200).get("recommendations", [])
    matched = [x for x in items if str(x.get("code")) == str(code)]
    return {"code": code, "count": len(matched), "items": matched}


@router.get("/candidates/top100")
async def candidates_top100():
    conn = get_db_connection()
    query = """
        SELECT code, name, price, change_pct, turnover, amount, pe, pb
        FROM daily_market
        WHERE date = (SELECT MAX(date) FROM daily_market)
        ORDER BY change_pct DESC
        LIMIT 100
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return {"total": len(df), "items": df.to_dict("records")}


@router.get("/data/jobs")
async def data_jobs():
    return _empty_page()


@router.get("/backtest/jobs")
async def backtest_jobs():
    return _empty_page()


@router.get("/data/quality/issues")
async def data_quality_issues():
    conn = get_db_connection()
    latest = pd.read_sql("SELECT MAX(date) AS d FROM daily_market", conn).iloc[0]["d"]
    if not latest:
        conn.close()
        return {"date": None, "total": 1, "items": [{"level": "warn", "message": "暂无行情数据"}]}
    m = pd.read_sql(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS up_count,
               SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS down_count
        FROM daily_market WHERE date = ?
        """,
        conn,
        params=[latest],
    ).iloc[0].to_dict()
    conn.close()
    issues: List[Dict[str, Any]] = []
    total = int(m.get("total") or 0)
    up = int(m.get("up_count") or 0)
    down = int(m.get("down_count") or 0)
    if total == 0:
        issues.append({"level": "warn", "message": "样本为空"})
    if total > 0 and up / total > 0.95:
        issues.append({"level": "warn", "message": "上涨占比异常偏高"})
    if total > 0 and down == 0:
        issues.append({"level": "warn", "message": "无下跌样本"})
    return {"date": latest, "total": len(issues), "items": issues}


@router.get("/paper/assets")
async def paper_assets():
    return {"cash": 1_000_000, "market_value": 0, "equity": 1_000_000, "currency": "CNY"}


@router.get("/paper/orders")
async def paper_orders():
    return _empty_page()


@router.get("/paper/positions")
async def paper_positions():
    return _empty_page()


@router.get("/live/assets")
async def live_assets():
    return {"connected": False, "cash": None, "market_value": None, "equity": None, "currency": "CNY"}


@router.get("/live/orders")
async def live_orders():
    return _empty_page()


@router.get("/live/positions")
async def live_positions():
    return _empty_page()


@router.get("/live/broker/status")
async def live_broker_status():
    return {"connected": False, "message": "broker not configured"}


@router.get("/notifications")
async def notifications():
    return {"total": 0, "items": []}


@router.get("/settings")
async def settings():
    return {
        "theme": "light",
        "refresh_interval_sec": 30,
        "language": "zh-CN",
    }


@router.get("/replay/days")
async def replay_days():
    conn = get_db_connection()
    df = pd.read_sql("SELECT DISTINCT date FROM daily_market ORDER BY date DESC LIMIT 120", conn)
    conn.close()
    return {"total": len(df), "items": df["date"].tolist()}
