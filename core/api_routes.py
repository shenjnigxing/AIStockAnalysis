"""市场数据 API 路由 - 扩展版。"""

import io
import os
import re
import time
import threading
from contextlib import redirect_stdout, redirect_stderr
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Query, Response

from core.data_manager import (
    _bs_login_silent,
    _bs_logout_silent,
    get_db_meta,
    fetch_and_cache,
    fetch_financial_data,
    fetch_kline_history,
    fetch_stock_basic_info,
    get_db_connection,
    get_kline_data,
    get_available_dates as dm_get_available_dates,
    load_market_data,
    save_kline_for_all_stocks
)
from core.strategies import (
    STRATEGIES,
    get_latest_market_data,
    normalize_market_scope,
    quick_recommend_market,
    run_multi_strategies,
    run_strategy,
)

router = APIRouter(prefix="/api/market", tags=["market"])

VALID_CODE_PATTERN = re.compile(r"^\d{6}$")
_BAOSTOCK_ADJUST_FLAG_MAP = {"bfq": "3", "qfq": "2", "hfq": "1"}
_ENDPOINT_CACHE: dict = {}
_ENDPOINT_CACHE_TTL_SECONDS = 20
_STRATEGY_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_STARTUP_LOCK = threading.Lock()
_STARTUP_FILE_LOCK = Path(__file__).resolve().parent.parent / "data" / "startup_warmup.lock"
_STARTUP_STATUS = {
    "running": False,
    "last_run": None,
    "last_error": None,
    "synced_today": False,
    "prewarmed": False,
}
_MIN_KLINE_BACKOFF_SECONDS = 90
_MIN_KLINE_FAIL_CACHE: dict[str, float] = {}
_MIN_KLINE_FAIL_LOCK = threading.Lock()


def validate_stock_code(code: str) -> str:
    code = str(code).strip()
    if not VALID_CODE_PATTERN.match(code):
        raise HTTPException(status_code=422, detail="股票代码格式错误，应为 6 位数字，如 600000")
    return code


def normalize_adjust_flag_or_422(adjust_flag: str) -> str:
    value = str(adjust_flag or "bfq").strip().lower()
    if value not in _BAOSTOCK_ADJUST_FLAG_MAP:
        raise HTTPException(status_code=422, detail="adjust_flag 仅支持 bfq、qfq、hfq")
    return value


def to_baostock_adjust_flag(adjust_flag: str) -> str:
    return _BAOSTOCK_ADJUST_FLAG_MAP[normalize_adjust_flag_or_422(adjust_flag)]


def _select_same_period_financial_row(df: pd.DataFrame, latest_report_date: str):
    if df is None or df.empty or not latest_report_date:
        return None
    latest_suffix = str(latest_report_date)[5:]
    same_period = df[df["report_date"].astype(str).str[5:] == latest_suffix]
    return same_period.iloc[0] if not same_period.empty else None


def _apply_screener_enrichment_filters(
    df: pd.DataFrame,
    date: str,
    conn,
    *,
    ma5_above: Optional[bool],
    volume_ratio_min: Optional[float],
    roe_min: Optional[float],
    profit_growth_min: Optional[float],
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    codes = [str(x) for x in out["code"].dropna().astype(str).unique().tolist()]
    if not codes:
        return out.iloc[0:0]

    placeholders = ",".join(["?"] * len(codes))

    if ma5_above is not None or volume_ratio_min is not None:
        kline_df = pd.read_sql(
            f"""
            SELECT code, date, close, volume
            FROM kline_data
            WHERE code IN ({placeholders})
              AND frequency = 'daily'
              AND adjust_flag = 'bfq'
              AND date <= ?
            ORDER BY code, date DESC
            """,
            conn,
            params=[*codes, date],
        )
        if kline_df.empty:
            return out.iloc[0:0]

        tech_rows = []
        for code, group in kline_df.groupby("code"):
            recent = group.head(6).copy()
            if recent.empty:
                continue
            latest = recent.iloc[0]
            prev5 = recent.iloc[1:6]
            ma5 = float(prev5["close"].mean()) if len(prev5) >= 5 else float(recent["close"].mean())
            avg_vol = float(prev5["volume"].mean()) if len(prev5) >= 5 else float(recent["volume"].mean())
            volume_ratio = float(latest["volume"]) / avg_vol if avg_vol and not pd.isna(avg_vol) else np.nan
            tech_rows.append(
                {
                    "code": str(code),
                    "ma5": ma5,
                    "latest_close": float(latest["close"]),
                    "volume_ratio": volume_ratio,
                }
            )

        tech_df = pd.DataFrame(tech_rows)
        if tech_df.empty:
            return out.iloc[0:0]

        out = out.merge(tech_df, on="code", how="left")
        if ma5_above is True:
            out = out[out["latest_close"] >= out["ma5"]]
        elif ma5_above is False:
            out = out[out["latest_close"] < out["ma5"]]
        if volume_ratio_min is not None:
            out = out[out["volume_ratio"].fillna(0) >= float(volume_ratio_min)]

    if roe_min is not None or profit_growth_min is not None:
        fin_df = pd.read_sql(
            f"""
            SELECT code, report_date, roe_avg, net_profit
            FROM financial_data
            WHERE code IN ({placeholders})
            ORDER BY code, report_date DESC
            """,
            conn,
            params=codes,
        )
        if fin_df.empty:
            return out.iloc[0:0]

        fin_rows = []
        for code, group in fin_df.groupby("code"):
            ordered = group.sort_values("report_date", ascending=False).reset_index(drop=True)
            if ordered.empty:
                continue
            latest = ordered.iloc[0]
            base = _select_same_period_financial_row(ordered.iloc[1:], str(latest.get("report_date") or ""))
            if base is None and len(ordered) > 1:
                base = ordered.iloc[1]
            latest_profit = pd.to_numeric(latest.get("net_profit"), errors="coerce")
            base_profit = pd.to_numeric(base.get("net_profit"), errors="coerce") if base is not None else np.nan
            growth = np.nan
            if pd.notna(latest_profit) and pd.notna(base_profit) and abs(float(base_profit)) > 1e-9:
                growth = (float(latest_profit) - float(base_profit)) / abs(float(base_profit)) * 100
            fin_rows.append(
                {
                    "code": str(code),
                    "latest_roe_avg": pd.to_numeric(latest.get("roe_avg"), errors="coerce"),
                    "profit_growth_pct": growth,
                }
            )

        fin_enriched_df = pd.DataFrame(fin_rows)
        if fin_enriched_df.empty:
            return out.iloc[0:0]

        out = out.merge(fin_enriched_df, on="code", how="left")
        if roe_min is not None:
            out = out[out["latest_roe_avg"].fillna(-np.inf) >= float(roe_min)]
        if profit_growth_min is not None:
            out = out[out["profit_growth_pct"].fillna(-np.inf) >= float(profit_growth_min)]

    return out


def _normalize_query_text(text: str) -> str:
    return str(text or "").strip().replace(" ", "")


def resolve_stock_code_or_422(query: str) -> str:
    """
    支持输入：
    - 6位股票代码
    - 中文名称（模糊）
    - 代码片段（模糊）
    解析失败返回 422。
    """
    q = _normalize_query_text(query)
    if not q:
        raise HTTPException(status_code=422, detail="请输入股票代码或股票名称")
    if VALID_CODE_PATTERN.match(q):
        return q

    conn = get_db_connection()
    try:
        sql = """
            SELECT code, name
            FROM (
                SELECT code, name, date FROM daily_market
                UNION ALL
                SELECT code, name, NULL AS date FROM stock_basic
            ) t
            WHERE code LIKE ? OR name LIKE ?
            ORDER BY
                CASE WHEN name = ? THEN 0 ELSE 1 END,
                CASE WHEN code = ? THEN 0 ELSE 1 END,
                date DESC
            LIMIT 1
        """
        df = pd.read_sql(sql, conn, params=[f"%{q}%", f"%{q}%", q, q])
    finally:
        conn.close()

    if df.empty:
        raise HTTPException(status_code=422, detail=f"未找到与“{q}”匹配的股票")
    return str(df.iloc[0]["code"])


def _is_limit_up_by_code(code: str, change_pct: float) -> bool:
    cp = float(change_pct or 0)
    code = str(code or "")
    if code.startswith(("300", "301", "688")):
        return cp >= 19.5
    return cp >= 9.5


def _is_limit_down_by_code(code: str, change_pct: float) -> bool:
    cp = float(change_pct or 0)
    code = str(code or "")
    if code.startswith(("300", "301", "688")):
        return cp <= -19.5
    return cp <= -9.5


def _cache_get(key):
    hit = _ENDPOINT_CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _ENDPOINT_CACHE_TTL_SECONDS:
        _ENDPOINT_CACHE.pop(key, None)
        return None
    return value


def _cache_set(key, value):
    _ENDPOINT_CACHE[key] = (time.time(), value)
    if len(_ENDPOINT_CACHE) > 300:
        for k, _ in sorted(_ENDPOINT_CACHE.items(), key=lambda x: x[1][0])[:80]:
            _ENDPOINT_CACHE.pop(k, None)


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _has_today_market_data() -> bool:
    try:
        conn = get_db_connection()
        try:
            latest = pd.read_sql("SELECT MAX(date) AS d FROM daily_market", conn).iloc[0]["d"]
        finally:
            conn.close()
        return bool(latest) and str(latest) >= _today_str()
    except Exception:
        return False


def warmup_strategy_cache(market_scopes: Optional[List[str]] = None):
    """预热战法缓存，提升首次点击速度。"""
    scopes = market_scopes or ["all", "sh_main", "kcb", "sz_main", "cyb", "sh_main,limit_up", "kcb,limit_up", "cyb,limit_up"]
    single_topns = [3, 5, 10]
    multi_topns = [3, 5, 10]
    default_multi_ids = list(STRATEGIES.keys())[:5]
    for scope in scopes:
        normalized_scope = normalize_market_scope(scope, strict=False)
        for sid in STRATEGIES.keys():
            for n in single_topns:
                result = run_strategy(sid, top_n=n, market_scope=normalized_scope)
                _cache_set(("strategy", sid, n, normalized_scope), result)
        for n in multi_topns:
            multi_result = run_multi_strategies(default_multi_ids, top_n=n, market_scope=normalized_scope)
            _cache_set(("strategy_multi", tuple(default_multi_ids), n, 8, normalized_scope), multi_result)
            _cache_set(("strategy_multi", tuple(default_multi_ids), n, 10, normalized_scope), multi_result)
        rec_result = run_multi_strategies(list(STRATEGIES.keys()), top_n=10, market_scope=normalized_scope)
        _cache_set(("strategy_recommend", 10, 10, normalized_scope), {
            "date": _today_str(),
            "next_trading_day": "下一交易日",
            "total_analyzed": len(STRATEGIES),
            "recommendations": rec_result.get("recommendations", []),
            "market_scope": normalized_scope,
        })


def _acquire_startup_file_lock(max_age_sec: int = 900) -> bool:
    try:
        _STARTUP_FILE_LOCK.parent.mkdir(parents=True, exist_ok=True)
        if _STARTUP_FILE_LOCK.exists():
            try:
                age = time.time() - _STARTUP_FILE_LOCK.stat().st_mtime
                if age > max_age_sec:
                    _STARTUP_FILE_LOCK.unlink(missing_ok=True)
                else:
                    return False
            except Exception:
                return False
        fd = os.open(str(_STARTUP_FILE_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()}\nts={int(time.time())}\n")
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def _release_startup_file_lock():
    try:
        _STARTUP_FILE_LOCK.unlink(missing_ok=True)
    except Exception:
        pass


def run_startup_sync_and_warmup(force_sync: bool = False):
    """启动后后台执行：同步行情 + 预热战法缓存。"""
    with _STARTUP_LOCK:
        if _STARTUP_STATUS["running"]:
            return
        _STARTUP_STATUS["running"] = True
        _STARTUP_STATUS["last_error"] = None
    if not _acquire_startup_file_lock():
        _STARTUP_STATUS["running"] = False
        _STARTUP_STATUS["last_error"] = "startup warmup locked by another process"
        return
    try:
        need_sync = force_sync or (not _has_today_market_data())
        if need_sync:
            fetch_and_cache()
        _STARTUP_STATUS["synced_today"] = _has_today_market_data()
        warmup_strategy_cache()
        _STARTUP_STATUS["prewarmed"] = True
    except Exception as e:
        _STARTUP_STATUS["last_error"] = str(e)
    finally:
        _STARTUP_STATUS["running"] = False
        _STARTUP_STATUS["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _release_startup_file_lock()


def start_background_warmup(force_sync: bool = False):
    thread = threading.Thread(target=run_startup_sync_and_warmup, kwargs={"force_sync": force_sync}, daemon=True)
    thread.start()


def _check_source_health() -> dict:
    """检测主要行情源连通性。"""
    result = {"tencent_quote": {"ok": False, "detail": ""}, "baostock": {"ok": False, "detail": ""}}

    # 腾讯
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get("http://qt.gtimg.cn/q=sh600000", timeout=6)
        ok = r.status_code == 200 and "v_sh600000" in (r.text or "")
        result["tencent_quote"]["ok"] = bool(ok)
        result["tencent_quote"]["detail"] = f"HTTP {r.status_code}" if ok else "返回内容异常"
    except Exception as e:
        result["tencent_quote"]["detail"] = str(e)

    # Baostock
    try:
        import baostock as bs
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            lg = bs.login()
        if lg.error_code == "0":
            rs = bs.query_all_stock(day=datetime.now().strftime("%Y-%m-%d"))
            ok = rs.error_code == "0"
            result["baostock"]["ok"] = bool(ok)
            result["baostock"]["detail"] = "ok" if ok else rs.error_msg
            with redirect_stdout(buf), redirect_stderr(buf):
                bs.logout()
        else:
            result["baostock"]["detail"] = lg.error_msg
    except Exception as e:
        result["baostock"]["detail"] = str(e)

    return result


def _quick_source_health() -> dict:
    """快速源状态（不触发慢检查）。"""
    last = _cache_get(("runtime_source_health",))
    if last is not None:
        return last
    return {"tencent_quote": {"ok": None, "detail": "unknown"}, "baostock": {"ok": None, "detail": "unknown"}}


def _to_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _aggregate_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """把日线聚合为周线（按自然周结束日 W-FRI）。"""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")
    if out.empty:
        return pd.DataFrame()

    for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    agg_map = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "amount": "sum",
    }
    if "turnover_rate" in out.columns:
        agg_map["turnover_rate"] = "mean"

    weekly = (
        out.set_index("date")
        .resample("W-FRI")
        .agg({k: v for k, v in agg_map.items() if k in out.columns})
        .dropna(subset=["open", "high", "low", "close"], how="any")
        .reset_index()
    )
    if weekly.empty:
        return pd.DataFrame()

    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
    prev_close = pd.to_numeric(weekly["close"], errors="coerce").shift(1)
    weekly["change_pct"] = ((weekly["close"] - prev_close) / prev_close * 100).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    weekly["amplitude"] = ((weekly["high"] - weekly["low"]) / prev_close * 100).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    weekly["frequency"] = "weekly"
    return weekly


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """基于 K 线数据计算 MA/MACD/KDJ。"""
    out = df.copy()
    out["close"] = _to_numeric_series(out, "close")
    out["high"] = _to_numeric_series(out, "high")
    out["low"] = _to_numeric_series(out, "low")

    out["ma5"] = out["close"].rolling(window=5, min_periods=5).mean()
    out["ma10"] = out["close"].rolling(window=10, min_periods=10).mean()
    out["ma20"] = out["close"].rolling(window=20, min_periods=20).mean()

    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["dif"] = ema12 - ema26
    out["dea"] = out["dif"].ewm(span=9, adjust=False).mean()
    out["macd"] = (out["dif"] - out["dea"]) * 2

    low_min = out["low"].rolling(window=9).min()
    high_max = out["high"].rolling(window=9).max()
    denom = (high_max - low_min).replace(0, pd.NA)
    rsv = ((out["close"] - low_min) / denom * 100).fillna(50)
    out["k"] = rsv.ewm(com=2, adjust=False).mean()
    out["d"] = out["k"].ewm(com=2, adjust=False).mean()
    out["j"] = 3 * out["k"] - 2 * out["d"]
    return out


def _calculate_signal_streak(signal_mask: pd.Series) -> np.ndarray:
    """
    连续信号计数（参考 Stock_py 的计算思想）:
    - 当日命中为 1 时累积计数
    - 若相邻两段信号间隔 < 5，则把前段计数延续到后段
    """
    temp_df = pd.DataFrame({"signal": signal_mask.astype(int)})
    group_key = (temp_df["signal"] != 1).cumsum()
    temp_df["signal_output"] = temp_df.groupby(group_key).cumcount()

    so = temp_df["signal_output"].to_numpy()
    sig = temp_df["signal"].to_numpy()
    is1 = sig == 1
    start = np.flatnonzero(is1 & np.r_[True, ~is1[:-1]])
    end = np.flatnonzero(is1 & np.r_[~is1[1:], True])
    if len(start) <= 1:
        return so

    gap = start[1:] - end[:-1] - 1
    for i, g in enumerate(gap):
        if g < 5:
            so[start[i + 1]: end[i + 1] + 1] += so[end[i]]
    return so


def _compute_algo_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    算法信号计算：
    1) 基础指标（MA/MACD/KDJ）
    2) 量价结构特征
    3) 连续信号 + 买卖点 + 综合评分
    """
    out = _compute_indicators(df)
    out["open"] = _to_numeric_series(out, "open")
    out["close"] = _to_numeric_series(out, "close")
    out["high"] = _to_numeric_series(out, "high")
    out["low"] = _to_numeric_series(out, "low")
    out["volume"] = _to_numeric_series(out, "volume")

    if "change_pct" in out.columns:
        out["change_pct"] = _to_numeric_series(out, "change_pct")
    else:
        prev_close = out["close"].shift(1).replace(0, pd.NA)
        out["change_pct"] = ((out["close"] - prev_close) / prev_close * 100).fillna(0)

    high_vol_days = out.loc[out["change_pct"].abs() > 5, "volume"]
    vol_base = float(high_vol_days.mean()) if len(high_vol_days) else float(out["volume"].median())
    if not np.isfinite(vol_base) or vol_base <= 0:
        vol_base = 1.0
    out["volume_std"] = (out["volume"] / vol_base).replace([float("inf"), float("-inf")], 0).fillna(0)

    out["ret_1"] = out["close"].pct_change().fillna(0)
    out["ret_5"] = out["close"].pct_change(5).fillna(0)
    out["ret_10"] = out["close"].pct_change(10).fillna(0)
    out["drawdown_20"] = (out["close"] / out["close"].rolling(20, min_periods=1).max() - 1.0).fillna(0)
    out["volatility_20"] = out["ret_1"].rolling(20, min_periods=5).std().fillna(0)

    cond_volume = (out["volume_std"] > 0.9) & (out["volume_std"].rolling(10, min_periods=1).sum() >= 6)
    cond_trend = (out["close"] >= out["ma10"]) & (out["ma10"] >= out["ma20"])
    cond_momentum = (out["ret_5"] > -0.03) & (out["change_pct"].rolling(5, min_periods=1).max() > 0)
    cond_risk = (out["change_pct"].rolling(10, min_periods=1).min() > -9.8) & (out["drawdown_20"] > -0.15)
    cond_macd = (out["dif"] >= out["dea"]) | (out["macd"] > 0)

    signal_mask = cond_volume & cond_trend & cond_momentum & cond_risk & cond_macd
    out["signal_raw"] = signal_mask.astype(int)
    out["signal_streak"] = _calculate_signal_streak(signal_mask)

    out["buy_point"] = (
        (out["signal_raw"] == 1)
        & (out["signal_streak"] >= 1)
        & (out["close"] > out["ma5"])
        & (out["macd"] >= 0)
    ).astype(int)
    out["sell_point"] = (
        ((out["close"] < out["ma10"]) & (out["macd"] < 0))
        | (out["drawdown_20"] <= -0.08)
    ).astype(int)

    # 综合评分 0-100，兼顾趋势/动量/量能/风险
    trend_score = ((out["close"] / out["ma20"].replace(0, pd.NA)) - 1.0).clip(-0.2, 0.2).fillna(0)
    momentum_score = out["ret_10"].clip(-0.2, 0.2).fillna(0)
    volume_score = (out["volume_std"] - 1.0).clip(-1.0, 1.5).fillna(0)
    risk_penalty = out["volatility_20"].clip(0, 0.12).fillna(0) + out["drawdown_20"].abs().clip(0, 0.2).fillna(0)

    score = (
        60
        + trend_score * 120
        + momentum_score * 80
        + volume_score * 10
        - risk_penalty * 180
        + out["signal_raw"] * 5
        + out["signal_streak"].clip(0, 8) * 1.5
    )
    out["algo_score"] = score.clip(0, 100).round(2)
    return out


# ==================== 基础行情接口 ====================

@router.get("/health")
async def health_check():
    """健康检查接口。"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/search_stocks")
async def search_stocks(
    q: str = Query(..., description="关键词：股票代码/中文名称，支持模糊匹配"),
    limit: int = Query(20, ge=1, le=100, description="返回条数")
):
    """股票搜索建议：支持代码与中文名称模糊检索。"""
    q = _normalize_query_text(q)
    if not q:
        return {"query": q, "count": 0, "items": []}

    conn = get_db_connection()
    try:
        sql = """
            SELECT code, name, MAX(date) AS latest_date
            FROM (
                SELECT code, name, date FROM daily_market
                UNION ALL
                SELECT code, name, NULL AS date FROM stock_basic
            ) t
            WHERE code LIKE ? OR name LIKE ?
            GROUP BY code, name
            ORDER BY
                CASE WHEN name = ? THEN 0 ELSE 1 END,
                CASE WHEN code = ? THEN 0 ELSE 1 END,
                latest_date DESC,
                code
            LIMIT ?
        """
        df = pd.read_sql(sql, conn, params=[f"%{q}%", f"%{q}%", q, q, limit])
    finally:
        conn.close()

    return {"query": q, "count": len(df), "items": df.to_dict("records")}


@router.get("/resolve_stock")
async def resolve_stock(q: str = Query(..., description="股票代码或中文名称")):
    """将输入（代码/中文名称）解析为标准 6 位代码。"""
    code = resolve_stock_code_or_422(q)
    return {"query": q, "code": code}


@router.post("/refresh")
async def refresh_market_data():
    """手动刷新市场数据（实时行情）。"""
    try:
        df = fetch_and_cache(force_refresh=True)
        return {
            "status": "success",
            "message": "Market data refreshed successfully",
            "count": len(df),
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_market_stats(
    exclude_st: bool = Query(False, description="是否排除 ST/*ST")
):
    """获取市场统计信息。"""
    try:
        df = load_market_data()
        conn = get_db_connection()
        try:
            latest_meta = pd.read_sql(
                "SELECT MAX(date) AS latest_date, MAX(created_at) AS latest_refresh_at FROM daily_market",
                conn,
            ).iloc[0].to_dict()
        finally:
            conn.close()

        if exclude_st and "name" in df.columns:
            df = df[~df["name"].astype(str).str.contains("ST", case=False, na=False)]

        if df.empty:
            return {
                "total_stocks": 0,
                "avg_price": 0,
                "avg_pe": 0,
                "avg_turnover": 0,
                "date": None,
                "latest_refresh_at": latest_meta.get("latest_refresh_at"),
                "limit_up_count": 0,
                "limit_down_count": 0,
                "market_coverage_label": "沪深A股（当前数据源不含北交所）",
            }

        up_count = len(df[df['change_pct'] > 0]) if 'change_pct' in df.columns else 0
        down_count = len(df[df['change_pct'] < 0]) if 'change_pct' in df.columns else 0
        limit_up_count = int(sum(_is_limit_up_by_code(str(row.get("code", "")), float(row.get("change_pct") or 0)) for _, row in df.iterrows()))
        limit_down_count = int(sum(_is_limit_down_by_code(str(row.get("code", "")), float(row.get("change_pct") or 0)) for _, row in df.iterrows()))

        stats = {
            "total_stocks": len(df),
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": len(df) - up_count - down_count,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "avg_price": round(df['price'].mean(), 2),
            "median_price": round(df['price'].median(), 2),
            "avg_pe": round(df['pe'].dropna().mean(), 2) if df['pe'].notna().any() else 0,
            "median_pe": round(df['pe'].dropna().median(), 2) if df['pe'].notna().any() else 0,
            "avg_turnover": round(df['turnover'].mean(), 2),
            "median_turnover": round(df['turnover'].median(), 2),
            "price_range": {
                "min": round(df['price'].min(), 2),
                "max": round(df['price'].max(), 2)
            },
            "pe_range": {
                "min": round(df['pe'].dropna().min(), 2) if df['pe'].notna().any() else 0,
                "max": round(df['pe'].dropna().max(), 2) if df['pe'].notna().any() else 0
            },
            "date": df['date'].iloc[0] if len(df) > 0 else None,
            "latest_refresh_at": latest_meta.get("latest_refresh_at"),
            "market_coverage_label": "沪深A股（当前数据源不含北交所）",
        }

        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data_quality")
async def get_data_quality():
    """数据质量校验：用于判断行情是否异常。"""
    try:
        conn = get_db_connection()
        latest_date = pd.read_sql("SELECT MAX(date) AS d FROM daily_market", conn).iloc[0]["d"]
        if not latest_date:
            conn.close()
            return {"status": "empty", "issues": ["暂无行情数据"], "metrics": {}}

        q = """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS up_count,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS down_count,
                SUM(CASE WHEN change_pct = 0 OR change_pct IS NULL THEN 1 ELSE 0 END) AS flat_count,
                MIN(change_pct) AS min_change,
                MAX(change_pct) AS max_change,
                AVG(change_pct) AS avg_change
            FROM daily_market
            WHERE date = ?
        """
        m = pd.read_sql(q, conn, params=[latest_date]).iloc[0].to_dict()
        conn.close()

        total = int(m.get("total") or 0)
        up = int(m.get("up_count") or 0)
        down = int(m.get("down_count") or 0)
        issues = []

        if total < 1000:
            issues.append("样本数量偏少，可能抓取不完整")
        if total > 6500:
            issues.append("样本数量偏大，可能混入非股票品种")
        if total > 0 and up / total > 0.95:
            issues.append("上涨家数占比异常偏高，疑似涨跌幅字段异常")
        if down == 0 and total > 0:
            issues.append("无下跌股票，疑似数据异常")
        if (m.get("max_change") or 0) > 40 or (m.get("min_change") or 0) < -30:
            issues.append("存在异常涨跌幅，建议重新刷新行情")

        return {
            "status": "warning" if issues else "ok",
            "date": latest_date,
            "issues": issues,
            "metrics": {
                "total": total,
                "up_count": up,
                "down_count": down,
                "flat_count": int(m.get("flat_count") or 0),
                "up_ratio": round(up / total, 4) if total else 0,
                "min_change": round(float(m.get("min_change") or 0), 2),
                "max_change": round(float(m.get("max_change") or 0), 2),
                "avg_change": round(float(m.get("avg_change") or 0), 2),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runtime_status")
async def get_runtime_status():
    """运行状态：数据库模式、最近刷新时间、数据源可达性。"""
    try:
        cache_key = ("runtime_status",)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        conn = get_db_connection()
        latest = pd.read_sql(
            "SELECT MAX(date) AS latest_date, MAX(created_at) AS latest_refresh_at FROM daily_market",
            conn
        ).iloc[0].to_dict()
        conn.close()

        payload = {
            "time": datetime.now().isoformat(),
            "db": get_db_meta(),
            "latest_date": latest.get("latest_date"),
            "latest_refresh_at": latest.get("latest_refresh_at"),
            "sources": _quick_source_health(),
        }
        _cache_set(cache_key, payload)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/startup_status")
async def get_startup_status():
    """查看启动后台任务状态（自动同步/预热）。"""
    return dict(_STARTUP_STATUS)


@router.post("/runtime_status/refresh_sources")
async def refresh_runtime_sources():
    """主动刷新数据源连通性（慢检查）。"""
    try:
        health = _check_source_health()
        _cache_set(("runtime_source_health",), health)
        return {"status": "ok", "sources": health}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dates")
async def list_available_dates():
    """获取可用的数据日期列表。"""
    try:
        dates = dm_get_available_dates()
        return {
            "dates": dates,
            "count": len(dates)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks")
async def list_stocks(
    code: Optional[str] = Query(None, description="股票代码"),
    code_prefix: Optional[str] = Query(None, description="代码前缀筛选，如 60/68/00/30"),
    code_prefixes: Optional[str] = Query(None, description="多前缀筛选，逗号分隔，如 68,30"),
    name: Optional[str] = Query(None, description="股票名称（模糊搜索）"),
    exclude_st: bool = Query(False, description="是否排除 ST/*ST"),
    only_limit_up: bool = Query(False, description="仅涨停"),
    only_limit_down: bool = Query(False, description="仅跌停"),
    price_min: Optional[float] = Query(None, ge=0, description="最小价格"),
    price_max: Optional[float] = Query(None, ge=0, description="最大价格"),
    pe_min: Optional[float] = Query(None, ge=0, description="最小市盈率"),
    pe_max: Optional[float] = Query(None, ge=0, description="最大市盈率"),
    turnover_min: Optional[float] = Query(None, ge=0, description="最小换手率"),
    turnover_max: Optional[float] = Query(None, le=100, description="最大换手率"),
    change_pct_min: Optional[float] = Query(None, description="最小涨跌幅"),
    change_pct_max: Optional[float] = Query(None, description="最大涨跌幅"),
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    sort_by: str = Query("code", description="排序字段: code/name/price/change_pct/pe/pb/turnover/amount"),
    sort_order: str = Query("asc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量")
):
    """获取股票列表（支持筛选和分页）。"""
    try:
        conn = get_db_connection()
        query = f"SELECT * FROM daily_market WHERE 1=1"
        params = []

        if code:
            code_q = _normalize_query_text(code)
            if VALID_CODE_PATTERN.match(code_q):
                query += " AND code = ?"
                params.append(code_q)
            else:
                query += " AND (code LIKE ? OR name LIKE ?)"
                params.extend([f"%{code_q}%", f"%{code_q}%"])
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        if price_min is not None:
            query += " AND price >= ?"
            params.append(price_min)
        if price_max is not None:
            query += " AND price <= ?"
            params.append(price_max)
        if pe_min is not None:
            query += " AND pe >= ?"
            params.append(pe_min)
        if pe_max is not None:
            query += " AND pe <= ?"
            params.append(pe_max)
        if turnover_min is not None:
            query += " AND turnover >= ?"
            params.append(turnover_min)
        if turnover_max is not None:
            query += " AND turnover <= ?"
            params.append(turnover_max)
        if change_pct_min is not None:
            query += " AND change_pct >= ?"
            params.append(change_pct_min)
        if change_pct_max is not None:
            query += " AND change_pct <= ?"
            params.append(change_pct_max)
        if date:
            query += " AND date = ?"
            params.append(date)
        else:
            # 默认获取最新日期
            latest_date_query = "SELECT MAX(date) FROM daily_market"
            latest_date = pd.read_sql(latest_date_query, conn).iloc[0, 0]
            if latest_date:
                query += " AND date = ?"
                params.append(latest_date)

        sort_field_map = {
            "code": "code",
            "name": "name",
            "price": "price",
            "change_pct": "change_pct",
            "pe": "pe",
            "pb": "pb",
            "turnover": "turnover",
            "amount": "amount",
        }
        if sort_by not in sort_field_map:
            raise HTTPException(status_code=422, detail=f"不支持的排序字段: {sort_by}")
        sort_order = sort_order.lower()
        if sort_order not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="sort_order 仅支持 asc 或 desc")

        df = pd.read_sql(query, conn, params=params)
        conn.close()

        # 前缀组合筛选
        prefixes = []
        if code_prefix:
            prefixes.append(str(code_prefix).strip())
        if code_prefixes:
            prefixes.extend([x.strip() for x in str(code_prefixes).split(",") if x.strip()])
        if prefixes:
            df = df[df["code"].astype(str).apply(lambda c: any(str(c).startswith(p) for p in prefixes))]

        # ST 筛选
        if exclude_st and "name" in df.columns:
            nm = df["name"].astype(str)
            df = df[~nm.str.contains("ST", case=False, na=False)]

        # 涨跌停筛选（按板块阈值）
        if only_limit_up and only_limit_down:
            # 两者同时为 true 代表不过滤
            pass
        elif only_limit_up:
            df = df[df.apply(lambda r: _is_limit_up_by_code(r.get("code"), r.get("change_pct")), axis=1)]
        elif only_limit_down:
            df = df[df.apply(lambda r: _is_limit_down_by_code(r.get("code"), r.get("change_pct")), axis=1)]

        # 排序 + 分页（在组合筛选后执行）
        df = df.sort_values(by=sort_field_map[sort_by], ascending=(sort_order == "asc"), kind="stable")
        total = int(len(df))
        offset = (page - 1) * page_size
        df_page = df.iloc[offset: offset + page_size]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "data": df_page.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== K 线数据接口 ====================

@router.get("/kline/{code}")
async def get_kline(
    code: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    adjust_flag: str = Query("bfq", description="复权类型：bfq=不复权，qfq=前复权，hfq=后复权"),
    frequency: str = Query("daily", description="K 线频率：daily/weekly/5min/15min/30min/60min")
):
    """获取单只股票的 K 线历史数据。"""
    try:
        code = validate_stock_code(code)
        adjust_flag = normalize_adjust_flag_or_422(adjust_flag)
        baostock_adjust_flag = to_baostock_adjust_flag(adjust_flag)
        # 默认获取 5 年数据
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        freq = str(frequency or "daily").lower()
        if freq == "weekly":
            daily_df = get_kline_data(code, start_date, end_date, adjust_flag, "daily")
            if daily_df.empty:
                formatted_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
                daily_df = fetch_kline_history(formatted_code, start_date, end_date, baostock_adjust_flag)
                if daily_df is not None and not daily_df.empty:
                    daily_df["code"] = code
                    daily_df["adjust_flag"] = adjust_flag
            df = _aggregate_to_weekly(daily_df)
        else:
            df = get_kline_data(code, start_date, end_date, adjust_flag, freq)

        if df.empty:
            # 尝试从 baostock 实时获取
            formatted_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
            df = fetch_kline_history(formatted_code, start_date, end_date, baostock_adjust_flag)
            if df is not None and len(df) > 0:
                df['code'] = code
                df['adjust_flag'] = adjust_flag

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No K-line data found for {code}")

        # 清理 NaN 和 inf 值
        import math
        df = df.fillna(0).replace([float('inf'), float('-inf')], 0)

        return {
            "code": code,
            "count": len(df),
            "data": df.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}/chart")
async def get_kline_chart(
    code: str,
    days: int = Query(100, ge=1, le=1000, description="返回天数"),
    frequency: str = Query("daily", description="K 线频率：daily/weekly/5min/15min/30min/60min")
):
    """获取 K 线图表数据（支持分钟 K 线）。"""
    try:
        code = validate_stock_code(code)
        freq = str(frequency or "daily").lower()
        if freq in {'daily', 'weekly'}:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
        else:
            # 分钟 K 线不使用日期范围，直接返回最新 N 条
            start_date = None
            end_date = None

        if freq == "weekly":
            daily_df = get_kline_data(code, start_date, end_date, 'bfq', 'daily')
            df = _aggregate_to_weekly(daily_df)
        else:
            df = get_kline_data(code, start_date, end_date, 'bfq', freq)

        # 如果数据库没有数据，尝试实时获取
        if df.empty:
            if freq in {'daily', 'weekly'}:
                # 日 K 线从 baostock 获取
                from core.data_manager import fetch_kline_history
                formatted_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
                fetched = fetch_kline_history(formatted_code, start_date, end_date, '3')
                df = _aggregate_to_weekly(fetched) if freq == "weekly" else fetched
            else:
                # 分钟 K 线从新浪获取
                from core.data_manager import fetch_min_kline
                formatted_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
                df = fetch_min_kline(formatted_code, period=freq.replace('min', ''))

            if df is not None and not df.empty:
                # 保存到数据库
                conn = get_db_connection()
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount,
                         change_pct, amplitude, frequency, adjust_flag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        code, row['date'], row['open'], row['high'],
                        row['low'], row['close'], row['volume'], row['amount'],
                        row.get('change_pct'), row.get('amplitude'), freq, 'bfq'
                    ))
                conn.commit()
                conn.close()

        if df.empty:
            raise HTTPException(status_code=404, detail="No data available")

        # 清理 NaN 和 inf 值
        import math
        df = df.fillna(0).replace([float('inf'), float('-inf')], 0)

        # 返回图表需要的简化数据
        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                "date": row['date'],
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume']) if pd.notna(row['volume']) else 0
            })

        return {
            "code": code,
            "data": chart_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}/indicators")
async def get_kline_indicators(
    code: str,
    days: int = Query(120, ge=30, le=1000, description="返回最近数据条数"),
    frequency: str = Query("daily", description="K 线频率：daily/weekly/5min/15min/30min/60min")
):
    """获取 K 线技术指标（MA/MACD/KDJ）。"""
    try:
        code = validate_stock_code(code)

        freq = str(frequency or "daily").lower()
        if freq == "daily":
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            df = get_kline_data(code, start_date, end_date, "bfq", "daily")
        elif freq == "weekly":
            start_date = (datetime.now() - timedelta(days=days * 7)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            daily_df = get_kline_data(code, start_date, end_date, "bfq", "daily")
            if daily_df.empty:
                formatted_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
                daily_df = fetch_kline_history(formatted_code, start_date, end_date, "3")
            df = _aggregate_to_weekly(daily_df)
        else:
            period = freq.replace("min", "")
            from core.data_manager import fetch_min_kline
            df = get_kline_data(code, None, None, "bfq", freq)
            if df.empty:
                formatted_code = f"sh{code}" if code.startswith("6") else f"sz{code}"
                df = fetch_min_kline(formatted_code, period)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data available")

        df = _compute_indicators(df).tail(days)
        df = df.fillna(0).replace([float("inf"), float("-inf")], 0)

        data = []
        for _, row in df.iterrows():
            data.append({
                "date": row.get("date"),
                "close": float(row.get("close", 0)),
                "ma5": float(row.get("ma5", 0)),
                "ma10": float(row.get("ma10", 0)),
                "ma20": float(row.get("ma20", 0)),
                "dif": float(row.get("dif", 0)),
                "dea": float(row.get("dea", 0)),
                "macd": float(row.get("macd", 0)),
                "k": float(row.get("k", 0)),
                "d": float(row.get("d", 0)),
                "j": float(row.get("j", 0)),
            })

        return {"code": code, "frequency": freq, "count": len(data), "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}/algo_signals")
async def get_kline_algo_signals(
    code: str,
    days: int = Query(180, ge=30, le=1000, description="返回最近数据条数"),
    frequency: str = Query("daily", description="K 线频率：daily/weekly/5min/15min/30min/60min")
):
    """获取算法信号、评分和买卖点（参考 Stock_py 连续信号算法）。"""
    try:
        code = validate_stock_code(code)

        freq = str(frequency or "daily").lower()
        if freq == "daily":
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            df = get_kline_data(code, start_date, end_date, "bfq", "daily")
        elif freq == "weekly":
            start_date = (datetime.now() - timedelta(days=days * 14)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            daily_df = get_kline_data(code, start_date, end_date, "bfq", "daily")
            if daily_df.empty:
                formatted_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
                daily_df = fetch_kline_history(formatted_code, start_date, end_date, "3")
            df = _aggregate_to_weekly(daily_df)
        else:
            period = freq.replace("min", "")
            from core.data_manager import fetch_min_kline
            df = get_kline_data(code, None, None, "bfq", freq)
            if df.empty:
                formatted_code = f"sh{code}" if code.startswith("6") else f"sz{code}"
                df = fetch_min_kline(formatted_code, period)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data available")

        calc_df = _compute_algo_signals(df).tail(days).reset_index(drop=True)
        calc_df = calc_df.fillna(0).replace([float("inf"), float("-inf")], 0)

        data = []
        markers = []
        for _, row in calc_df.iterrows():
            date_value = row.get("date")
            rec = {
                "date": date_value,
                "close": float(row.get("close", 0)),
                "ma5": float(row.get("ma5", 0)),
                "ma10": float(row.get("ma10", 0)),
                "ma20": float(row.get("ma20", 0)),
                "dif": float(row.get("dif", 0)),
                "dea": float(row.get("dea", 0)),
                "macd": float(row.get("macd", 0)),
                "volume_std": float(row.get("volume_std", 0)),
                "drawdown_20": float(row.get("drawdown_20", 0)),
                "signal_raw": int(row.get("signal_raw", 0)),
                "signal_streak": int(row.get("signal_streak", 0)),
                "buy_point": int(row.get("buy_point", 0)),
                "sell_point": int(row.get("sell_point", 0)),
                "algo_score": float(row.get("algo_score", 0)),
            }
            data.append(rec)

            if rec["buy_point"] == 1:
                markers.append(
                    {
                        "time": date_value,
                        "position": "belowBar",
                        "color": "#16a34a",
                        "shape": "arrowUp",
                        "text": f"BUY {rec['algo_score']:.1f}",
                    }
                )
            if rec["sell_point"] == 1:
                markers.append(
                    {
                        "time": date_value,
                        "position": "aboveBar",
                        "color": "#dc2626",
                        "shape": "arrowDown",
                        "text": f"SELL {rec['algo_score']:.1f}",
                    }
                )

        latest = data[-1] if data else {}
        buy_count = sum(int(x["buy_point"]) for x in data)
        sell_count = sum(int(x["sell_point"]) for x in data)
        avg_score = round(float(np.mean([x["algo_score"] for x in data])) if data else 0.0, 2)
        summary = {
            "latest_score": latest.get("algo_score", 0),
            "latest_signal_streak": latest.get("signal_streak", 0),
            "latest_volume_std": latest.get("volume_std", 0),
            "latest_drawdown_20": latest.get("drawdown_20", 0),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "avg_score": avg_score,
            "trend_state": "bull" if float(latest.get("dif", 0)) >= float(latest.get("dea", 0)) else "bear",
        }

        return {
            "code": code,
            "frequency": freq,
            "count": len(data),
            "summary": summary,
            "markers": markers[-120:],
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}/min")
async def get_min_kline(
    code: str,
    period: str = Query("5", description="K 线周期：1/5/15/30/60 (分钟)"),
    refresh: bool = Query(False, description="是否强制刷新")
):
    """获取分钟 K 线数据（实时从新浪获取）。"""
    try:
        code = validate_stock_code(code)
        from core.data_manager import fetch_min_kline

        # 转换代码格式（000001 -> sz000001, 600000 -> sh600000）
        if code.startswith('6'):
            formatted_code = f"sh{code}"
        else:
            formatted_code = f"sz{code}"

        # 尝试从数据库获取
        from core.data_manager import get_kline_data
        df = get_kline_data(code, None, None, 'bfq', f"{period}min")
        if not df.empty and refresh:
            # 有旧数据时优先秒级返回，后台异步刷新，避免前端长时间等待。
            def _refresh_bg() -> None:
                try:
                    fresh = fetch_min_kline(formatted_code, period, timeout_sec=8.0, datalen=512)
                    if fresh.empty:
                        return
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    for _, row in fresh.iterrows():
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO kline_data
                            (code, date, open, high, low, close, volume, amount,
                             change_pct, amplitude, frequency, adjust_flag)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                code, row['date'], row['open'], row['high'],
                                row['low'], row['close'], row['volume'], row['amount'],
                                row.get('change_pct'), row.get('amplitude'), f"{period}min", 'bfq'
                            ),
                        )
                    conn.commit()
                    conn.close()
                except Exception:
                    return

            threading.Thread(target=_refresh_bg, name=f"min-kline-refresh-{code}-{period}", daemon=True).start()

        # 数据库没有则实时获取
        if df.empty:
            fail_key = f"{code}:{period}"
            now_ts = time.time()
            with _MIN_KLINE_FAIL_LOCK:
                last_fail = _MIN_KLINE_FAIL_CACHE.get(fail_key, 0.0)
            if (now_ts - last_fail) < _MIN_KLINE_BACKOFF_SECONDS and not refresh:
                raise HTTPException(
                    status_code=429,
                    detail=f"分钟K线源短时不可用，{_MIN_KLINE_BACKOFF_SECONDS}秒后再试",
                )

            df = fetch_min_kline(formatted_code, period, timeout_sec=6.0, datalen=512)

            if not df.empty:
                # 保存到数据库
                from core.data_manager import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO kline_data
                        (code, date, open, high, low, close, volume, amount,
                         change_pct, amplitude, frequency, adjust_flag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        code, row['date'], row['open'], row['high'],
                        row['low'], row['close'], row['volume'], row['amount'],
                        row.get('change_pct'), row.get('amplitude'), f"{period}min", 'bfq'
                    ))
                conn.commit()
                conn.close()
                with _MIN_KLINE_FAIL_LOCK:
                    _MIN_KLINE_FAIL_CACHE.pop(fail_key, None)
            else:
                with _MIN_KLINE_FAIL_LOCK:
                    _MIN_KLINE_FAIL_CACHE[fail_key] = now_ts

        if df.empty:
            raise HTTPException(status_code=404, detail="No minute K-line data available")

        # 清洗 NaN 和 inf 值
        df = df.fillna(0).replace([float('inf'), float('-inf')], 0)

        return {
            "code": code,
            "period": period,
            "count": len(df),
            "data": df.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kline/min/init")
async def init_min_kline(
    period: str = Query("5", description="K 线周期：1/5/15/30/60 (分钟)"),
    batch_size: int = Query(50, ge=10, le=200, description="每批处理的股票数量")
):
    """初始化分钟 K 线数据（后台任务）。"""
    try:
        from core.data_manager import save_min_kline_for_all_stocks
        import threading

        thread = threading.Thread(
            target=save_min_kline_for_all_stocks,
            args=(period, batch_size)
        )
        thread.start()

        return {
            "status": "started",
            "message": f"开始获取{period}分钟 K 线数据，每批{batch_size}只股票",
            "note": "每只股票约 1024 根 K 线，可能需要较长时间"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 基本面数据接口 ====================

@router.get("/basic/{code}")
async def get_stock_basic(code: str):
    """获取股票基本信息。"""
    try:
        code = validate_stock_code(code)
        conn = get_db_connection()
        query = "SELECT * FROM stock_basic WHERE code = ?"
        df = pd.read_sql(query, conn, params=[code])
        conn.close()

        def _need_refill(row_dict: dict) -> bool:
            return any(
                row_dict.get(k) in (None, "", 0, 0.0)
                for k in ("list_date", "industry", "total_shares", "float_shares")
            )

        if df.empty:
            # 尝试从 baostock 拉取
            fetch_stock_basic_info(code)
            conn = get_db_connection()
            df = pd.read_sql(query, conn, params=[code])
            conn.close()
        else:
            row0 = df.to_dict("records")[0]
            if _need_refill(row0):
                # 先补财务（用于股本），再补基础信息（用于上市日期/行业）
                now = datetime.now()
                y, q = now.year, (now.month - 1) // 3 + 1
                for _ in range(8):
                    try:
                        fin = fetch_financial_data(code, year=y, quarter=q)
                        p = (fin or {}).get("profit") or {}
                        if p.get("totalShare") or p.get("liqaShare"):
                            break
                    except Exception:
                        pass
                    q -= 1
                    if q <= 0:
                        q = 4
                        y -= 1
                try:
                    fetch_stock_basic_info(code)
                except Exception:
                    pass
                conn = get_db_connection()
                df = pd.read_sql(query, conn, params=[code])
                conn.close()

        if df.empty:
            # 兜底：从最新行情返回基础展示信息，避免数据中心完全空白
            conn = get_db_connection()
            fallback = pd.read_sql(
                """
                SELECT code, name, NULL AS list_date, NULL AS total_shares, NULL AS float_shares,
                       NULL AS industry, NULL AS area,
                       CASE
                         WHEN code LIKE '60%' OR code LIKE '00%' THEN '主板'
                         WHEN code LIKE '30%' THEN '创业板'
                         WHEN code LIKE '68%' THEN '科创板'
                         ELSE '未知'
                       END AS market
                FROM daily_market
                WHERE code = ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=[code],
            )
            conn.close()
            if fallback.empty:
                raise HTTPException(status_code=404, detail="Stock info not found")
            return fallback.to_dict("records")[0]

        return df.to_dict('records')[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financial/{code}")
async def get_financial_data(code: str, limit: int = Query(20, ge=1, le=100)):
    """获取股票财务指标数据（最新 N 期）。"""
    try:
        code = validate_stock_code(code)
        conn = get_db_connection()
        query = """
            SELECT * FROM financial_data
            WHERE code = ?
            ORDER BY report_date DESC
            LIMIT ?
        """
        df = pd.read_sql(query, conn, params=[code, limit])
        conn.close()

        if df.empty:
            # 兜底：回溯近12个季度逐季拉取，提升命中率
            now = datetime.now()
            y, q = now.year, (now.month - 1) // 3 + 1
            for _ in range(12):
                try:
                    fetch_financial_data(code, year=y, quarter=q)
                except Exception:
                    pass
                q -= 1
                if q <= 0:
                    q = 4
                    y -= 1

            conn = get_db_connection()
            df = pd.read_sql(query, conn, params=[code, limit])
            conn.close()

        return {
            "code": code,
            "count": len(df),
            "data": df.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/holder/{code}")
async def get_holder_data(code: str, limit: int = Query(8, ge=1, le=40)):
    """获取股东户数与前十大持仓信息。"""
    try:
        code = validate_stock_code(code)
        conn = get_db_connection()
        query = """
            SELECT
                report_date,
                holder_count,
                avg_holdings,
                top10_holder_ratio AS top10_ratio,
                top10_flow_ratio AS top10_flow_ratio
            FROM stock_holder
            WHERE code = ?
            ORDER BY report_date DESC
            LIMIT ?
        """
        df = pd.read_sql(query, conn, params=[code, limit])
        conn.close()

        if not df.empty:
            df["holder_change_ratio"] = df["holder_count"].pct_change(-1).fillna(0)

        return {
            "code": code,
            "count": len(df),
            "data": df.to_dict("records")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/basic/backfill")
async def backfill_basic_data(
    limit: int = Query(300, ge=50, le=3000, description="最多回填股票数量"),
    financial_quarters: int = Query(4, ge=1, le=12, description="每只股票回溯财务季度数")
):
    """批量回填基本信息与财务关键字段（上市日期/行业/股本）。"""
    try:
        import baostock as bs

        conn = get_db_connection()
        codes_df = pd.read_sql(
            """
            SELECT DISTINCT code
            FROM daily_market
            WHERE date = (SELECT MAX(date) FROM daily_market)
            ORDER BY code
            LIMIT ?
            """,
            conn,
            params=[limit],
        )
        conn.close()

        codes = [str(x) for x in codes_df["code"].tolist()]
        now = datetime.now()
        ok_basic = 0
        ok_fin = 0

        lg = _bs_login_silent(bs)
        if lg.error_code != "0":
            raise HTTPException(status_code=502, detail=f"Baostock 登录失败: {lg.error_msg}")

        try:
            for code in codes:
                try:
                    fetch_stock_basic_info(code, bs_module=bs)
                    ok_basic += 1
                except Exception:
                    pass

                y, q = now.year, (now.month - 1) // 3 + 1
                for _ in range(financial_quarters):
                    try:
                        fetch_financial_data(code, year=y, quarter=q, bs_module=bs)
                        ok_fin += 1
                    except Exception:
                        pass
                    q -= 1
                    if q <= 0:
                        q = 4
                        y -= 1
        finally:
            _bs_logout_silent(bs)

        return {
            "status": "ok",
            "codes": len(codes),
            "basic_updated": ok_basic,
            "financial_calls": ok_fin,
            "message": f"已回填 {len(codes)} 只股票的基础信息，财务回溯 {financial_quarters} 季度"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 选股器接口 ====================

@router.get("/screen")
async def screen_stocks(
    # 价格条件
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    # 市值条件
    mv_min: Optional[float] = Query(None, ge=0),
    mv_max: Optional[float] = Query(None, ge=0),
    # 估值条件
    pe_min: Optional[float] = Query(None, ge=0),
    pe_max: Optional[float] = Query(None, ge=0),
    pb_min: Optional[float] = Query(None, ge=0),
    pb_max: Optional[float] = Query(None, ge=50),
    # 换手率条件
    turnover_min: Optional[float] = Query(None, ge=0),
    turnover_max: Optional[float] = Query(None, le=100),
    # 涨跌幅条件
    change_pct_min: Optional[float] = Query(None),
    change_pct_max: Optional[float] = Query(None),
    # 技术形态条件
    ma5_above: Optional[bool] = Query(None, description="股价在 5 日线上"),
    volume_ratio_min: Optional[float] = Query(None, description="最小量比"),
    # 基本面条件
    roe_min: Optional[float] = Query(None, ge=0),
    profit_growth_min: Optional[float] = Query(None),
    # 其他
    exclude_st: bool = Query(True, description="排除 ST 股"),
    exclude_kcb: bool = Query(False, description="排除科创板"),
    date: Optional[str] = Query(None),
    sort_by: str = Query("change_pct", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """
    选股器 - 多条件组合筛选股票。
    支持价格、市值、估值、换手率、涨跌幅、技术形态、基本面等条件。
    """
    try:
        conn = get_db_connection()

        # 确定日期
        if not date:
            latest_query = "SELECT MAX(date) FROM daily_market"
            date = pd.read_sql(latest_query, conn).iloc[0, 0]

        query = "SELECT * FROM daily_market WHERE date = ?"
        params = [date]

        # 价格条件
        if price_min is not None:
            query += " AND price >= ?"
            params.append(price_min)
        if price_max is not None:
            query += " AND price <= ?"
            params.append(price_max)

        # 估值条件
        if pe_min is not None:
            query += " AND pe >= ?"
            params.append(pe_min)
        if pe_max is not None:
            query += " AND pe <= ?"
            params.append(pe_max)
        if pb_min is not None:
            query += " AND pb >= ?"
            params.append(pb_min)
        if pb_max is not None:
            query += " AND pb <= ?"
            params.append(pb_max)

        # 换手率条件
        if turnover_min is not None:
            query += " AND turnover >= ?"
            params.append(turnover_min)
        if turnover_max is not None:
            query += " AND turnover <= ?"
            params.append(turnover_max)

        # 涨跌幅条件
        if change_pct_min is not None:
            query += " AND change_pct >= ?"
            params.append(change_pct_min)
        if change_pct_max is not None:
            query += " AND change_pct <= ?"
            params.append(change_pct_max)

        # 排除 ST 股
        if exclude_st:
            query += " AND name NOT LIKE ? AND name NOT LIKE ?"
            params.extend(['%ST%', '%*ST%'])

        df = pd.read_sql(query, conn, params=params)

        # 科创板排除
        if exclude_kcb:
            df = df[~df['code'].str.startswith('688')]

        # 估算流通市值（亿元）
        if "amount" in df.columns and "turnover" in df.columns:
            def _calc_mv(row):
                t = row.get("turnover", 0)
                a = row.get("amount", 0)
                if pd.isna(t) or pd.isna(a) or t <= 0:
                    return 0
                return (a / t * 100) / 1e8
            df["float_mv"] = df.apply(_calc_mv, axis=1)
        else:
            df["float_mv"] = 0

        if mv_min is not None:
            df = df[df["float_mv"] >= mv_min]
        if mv_max is not None:
            df = df[df["float_mv"] <= mv_max]

        df = _apply_screener_enrichment_filters(
            df,
            date,
            conn,
            ma5_above=ma5_above,
            volume_ratio_min=volume_ratio_min,
            roe_min=roe_min,
            profit_growth_min=profit_growth_min,
        )

        sort_field_map = {
            "code": "code",
            "name": "name",
            "price": "price",
            "change_pct": "change_pct",
            "pe": "pe",
            "pb": "pb",
            "turnover": "turnover",
            "amount": "amount",
            "float_mv": "float_mv",
            "ma5": "ma5",
            "volume_ratio": "volume_ratio",
            "roe": "latest_roe_avg",
            "latest_roe_avg": "latest_roe_avg",
            "profit_growth": "profit_growth_pct",
            "profit_growth_pct": "profit_growth_pct",
        }
        if sort_by not in sort_field_map:
            raise HTTPException(status_code=422, detail=f"不支持的排序字段: {sort_by}")
        sort_order = sort_order.lower()
        if sort_order not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="sort_order 仅支持 asc 或 desc")

        sort_col = sort_field_map[sort_by]
        if sort_col not in df.columns:
            df[sort_col] = np.nan
        df = df.sort_values(by=sort_col, ascending=(sort_order == "asc"), kind="stable", na_position="last")
        total = len(df)
        offset = (page - 1) * page_size
        page_df = df.iloc[offset: offset + page_size]

        conn.close()

        return {
            "date": date,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "data": page_df.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 战法选股接口 ====================

@router.get("/strategies")
async def get_strategy_list():
    """获取所有可用的战法策略列表。"""
    strategies = []
    for key, value in STRATEGIES.items():
        strategies.append({
            'id': key,
            'name': value['name'],
            'desc': value['desc'],
            'risk': value['risk'],
            'suitable': value['suitable']
        })
    return {"strategies": strategies}


@router.get("/strategy/{strategy_id}")
async def run_strategy_api(
    strategy_id: str,
    top_n: int = Query(3, ge=1, le=20, description="返回推荐股票数量"),
    market_scope: str = Query("all", description="市场范围：all/sh_main/kcb/sz_main/cyb，可逗号组合")
):
    """
    运行战法选股策略

    可选策略：
    - jinfenghuang: 金凤凰涨停战法
    - longtou: 龙头战法
    - breakthrough: 突破战法
    - pullback_ma: 回踩均线战法
    - continuous_limit: 连板战法
    - first_limit: 首板挖掘战法
    - macd_golden: MACD 金叉战法
    - kdj_oversold: KDJ 超卖战法
    - volume_ratio: 量比战法
    - hot_money: 龙虎榜战法
    """
    try:
        try:
            market_scope = normalize_market_scope(market_scope, strict=True)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))

        cache_key = ("strategy", strategy_id, top_n, market_scope)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        result = run_strategy(strategy_id, top_n, market_scope=market_scope)

        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        _cache_set(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy_multi")
async def run_strategy_multi_api(
    strategy_ids: str = Query(..., description="逗号分隔策略ID，如 breakthrough,macd_golden"),
    top_n: int = Query(10, ge=1, le=50, description="返回推荐股票数量"),
    timeout_sec: int = Query(10, ge=2, le=30, description="完整战法计算超时秒数，超时自动降级快速推荐"),
    market_scope: str = Query("all", description="市场范围：all/sh_main/kcb/sz_main/cyb，可逗号组合")
):
    """多战法聚合选股接口。"""
    try:
        try:
            market_scope = normalize_market_scope(market_scope, strict=True)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))

        ids = [s.strip() for s in strategy_ids.split(",") if s.strip()]
        if not ids:
            # 前端可能尚未加载战法列表，直接给出快速推荐而不是报错
            return quick_recommend_market(top_n=top_n, preferred_ids=[], strategy_name="多战法快速兜底", market_scope=market_scope)

        cache_key = ("strategy_multi", tuple(ids), top_n, timeout_sec, market_scope)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            fut = _STRATEGY_EXECUTOR.submit(run_multi_strategies, ids, top_n, market_scope)
            result = fut.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            try:
                fut.cancel()
            except Exception:
                pass
            result = quick_recommend_market(
                top_n=top_n,
                preferred_ids=ids,
                strategy_name="多战法超时快速兜底",
                market_scope=market_scope,
            )
            result["fallback"] = True
            result["fallback_reason"] = f"完整战法计算超过 {timeout_sec}s，已降级快速推荐"

        _cache_set(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategycompare")
async def compare_strategies(
    top_n: int = Query(3, ge=1, le=10, description="每个策略返回股票数量"),
    market_scope: str = Query("all", description="市场范围：all/sh_main/kcb/sz_main/cyb，可逗号组合")
):
    """对比所有战法策略的选股结果。"""
    try:
        market_scope = normalize_market_scope(market_scope, strict=True)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))

    cache_key = ("strategy_compare", top_n, market_scope)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = {}
    for strategy_id in STRATEGIES.keys():
        result = run_strategy(strategy_id, top_n, market_scope=market_scope)
        if 'error' not in result:
            results[strategy_id] = {
                'name': result['strategy_name'],
                'count': result['total_found'],
                'native_count': result.get('native_total_found'),
                'backtest_summary': result.get('backtest_summary', {}),
                'recommendations': result['recommendations'],
                'fallback': result.get('fallback', False),
                'fallback_reason': result.get('fallback_reason'),
            }

    payload = {"strategies": results}
    _cache_set(cache_key, payload)
    return payload


@router.get("/strategy_recommend")
async def get_next_day_recommend(
    top_n: int = Query(10, ge=1, le=50, description="推荐股票数量"),
    timeout_sec: int = Query(10, ge=2, le=30, description="完整战法计算超时秒数"),
    market_scope: str = Query("all", description="市场范围：all/sh_main/kcb/sz_main/cyb，可逗号组合")
):
    """
    获取下一交易日推荐股票
    综合所有战法，给出评分最高的股票和推荐理由
    """
    try:
        market_scope = normalize_market_scope(market_scope, strict=True)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))

    cache_key = ("strategy_recommend", top_n, timeout_sec, market_scope)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        fut = _STRATEGY_EXECUTOR.submit(run_multi_strategies, list(STRATEGIES.keys()), top_n, market_scope)
        result = fut.result(timeout=timeout_sec)
    except FuturesTimeoutError:
        try:
            fut.cancel()
        except Exception:
            pass
        result = quick_recommend_market(
            top_n=top_n,
            preferred_ids=list(STRATEGIES.keys()),
            strategy_name="综合推荐超时快速兜底",
            market_scope=market_scope,
        )
        result["fallback"] = True
        result["fallback_reason"] = f"完整战法计算超过 {timeout_sec}s，已降级快速推荐"

    recs = result.get("recommendations", [])
    for rec in recs:
        if rec.get("strategy_count", 0) > 1:
            rec["full_reason"] = f"{rec['strategy_count']}个策略共同推荐 | {rec.get('summary_reason', '')}"
        else:
            rec["full_reason"] = rec.get("summary_reason", "")

    payload = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'next_trading_day': '下一交易日',
        'total_analyzed': len(STRATEGIES),
        'recommendations': recs,
        'market_scope': market_scope
    }
    _cache_set(cache_key, payload)
    return payload


@router.get("/strategy_leaderboard")
async def get_strategy_leaderboard(
    top_n: int = Query(5, ge=1, le=20, description="每个战法展示前N只"),
    sort_metric: str = Query("ret_20d", description="排序指标：ret_20d/ret_60d/mdd_20d/mdd_60d"),
    market_scope: str = Query("all", description="市场范围：all/sh_main/kcb/sz_main/cyb，可逗号组合")
):
    """战法榜单：按回测表现排序，便于快速选择策略。"""
    try:
        try:
            market_scope = normalize_market_scope(market_scope, strict=True)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))

        cache_key = ("strategy_leaderboard", top_n, sort_metric, market_scope)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        valid_metrics = {"ret_20d", "ret_60d", "mdd_20d", "mdd_60d"}
        if sort_metric not in valid_metrics:
            raise HTTPException(status_code=422, detail=f"sort_metric 仅支持: {','.join(sorted(valid_metrics))}")

        rows = []
        for sid, conf in STRATEGIES.items():
            result = run_strategy(sid, top_n=top_n, market_scope=market_scope)
            if "error" in result:
                continue
            summary = result.get("backtest_summary", {})
            rows.append({
                "strategy_id": sid,
                "strategy_name": conf["name"],
                "risk_level": conf["risk"],
                "description": conf["desc"],
                "avg_ret_20d": summary.get("avg_ret_20d"),
                "avg_ret_60d": summary.get("avg_ret_60d"),
                "avg_mdd_20d": summary.get("avg_mdd_20d"),
                "avg_mdd_60d": summary.get("avg_mdd_60d"),
                "coverage_20d": summary.get("coverage_20d", 0),
                "coverage_60d": summary.get("coverage_60d", 0),
                "sample_recommendations": result.get("recommendations", [])[:3],
            })

        reverse = sort_metric in {"ret_20d", "ret_60d"}
        sort_key = {
            "ret_20d": "avg_ret_20d",
            "ret_60d": "avg_ret_60d",
            "mdd_20d": "avg_mdd_20d",
            "mdd_60d": "avg_mdd_60d",
        }[sort_metric]
        rows.sort(key=lambda x: float(x.get(sort_key) or (-1e9 if reverse else 1e9)), reverse=reverse)

        payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sort_metric": sort_metric,
            "count": len(rows),
            "data": rows,
            "market_scope": market_scope
        }
        _cache_set(cache_key, payload)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据导出接口 ====================

@router.get("/export/{code}")
async def export_stock_data(code: str, export_type: str = Query("csv", description="导出类型：csv/xlsx")):
    """导出股票数据为 CSV 或 Excel 格式。"""
    try:
        code = validate_stock_code(code)
        export_type = export_type.lower()
        if export_type not in {"csv", "xlsx"}:
            raise HTTPException(status_code=422, detail="export_type 仅支持 csv 或 xlsx")
        # 获取 K 线数据
        start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        df = get_kline_data(code, start_date, end_date, 'bfq')

        if df.empty:
            raise HTTPException(status_code=404, detail="No data to export")

        # 导出文件
        if export_type == 'xlsx':
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='K 线数据')
            buffer.seek(0)
            return Response(
                content=buffer.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={code}_kline.xlsx"}
            )
        else:
            csv_data = df.to_csv(index=False)
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={code}_kline.csv"}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 历史数据初始化接口 ====================

@router.post("/history/init")
async def init_history_data(
    years: int = Query(5, ge=1, le=10, description="获取多少年的历史数据"),
    batch_size: int = Query(50, ge=10, le=200, description="每批处理的股票数量")
):
    """
    初始化历史 K 线数据。
    此操作会获取所有股票的历史 K 线数据，可能需要较长时间。
    """
    try:
        start_date = (datetime.now() - timedelta(days=365*years)).strftime("%Y-%m-%d")

        # 在后台执行数据获取任务
        import threading
        thread = threading.Thread(
            target=save_kline_for_all_stocks,
            args=(batch_size, start_date)
        )
        thread.start()

        return {
            "status": "started",
            "message": f"开始获取{years}年历史数据，共{batch_size}只股票每批次",
            "start_date": start_date,
            "end_date": datetime.now().strftime("%Y-%m-%d")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
