"""A 股多战法策略引擎。"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd

from core.data_manager import get_db_connection

_KLINE_CACHE: Dict[Tuple[str, int], Tuple[float, pd.DataFrame]] = {}
_MARKET_CACHE: Tuple[float, pd.DataFrame] | None = None
_CACHE_TTL_SECONDS = 30
_MARKET_SCOPE_ALIAS = {
    "all": "all",
    "a": "all",
    "full": "all",
    "sh_main": "sh_main",
    "sh": "sh_main",
    "main_sh": "sh_main",
    "kcb": "kcb",
    "kc": "kcb",
    "sci": "kcb",
    "sz_main": "sz_main",
    "sz": "sz_main",
    "main_sz": "sz_main",
    "cyb": "cyb",
    "gem": "cyb",
    "up": "limit_up",
    "limit_up": "limit_up",
    "zt": "limit_up",
    "down": "limit_down",
    "limit_down": "limit_down",
    "dt": "limit_down",
}
_MARKET_SCOPE_ORDER = ["sh_main", "kcb", "sz_main", "cyb", "limit_up", "limit_down"]
_COVERAGE_CACHE: Tuple[float, Dict] | None = None


def _safe_float(v, default: float = 0.0) -> float:
    if pd.isna(v):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def normalize_market_scope(scope: str | None, strict: bool = False) -> str:
    text = str(scope or "all").strip().lower()
    if not text:
        return "all"

    raw_parts = [x.strip() for x in text.split(",") if x.strip()]
    normalized = []
    unknown = []
    for part in raw_parts:
        mapped = _MARKET_SCOPE_ALIAS.get(part)
        if mapped is None:
            unknown.append(part)
            continue
        normalized.append(mapped)

    if strict and unknown:
        raise ValueError(f"不支持的 market_scope: {','.join(unknown)}")

    if not normalized:
        return "all"
    if "all" in normalized:
        return "all"

    uniq = []
    for part in _MARKET_SCOPE_ORDER:
        if part in normalized and part not in uniq:
            uniq.append(part)
    return ",".join(uniq) if uniq else "all"


def _apply_market_scope(df: pd.DataFrame, market_scope: str = "all") -> pd.DataFrame:
    if df is None or df.empty:
        return df

    scope = normalize_market_scope(market_scope, strict=False)
    if scope in {"", "all"}:
        return df

    out = df.copy()
    code_s = out["code"].astype(str)
    cp_s = pd.to_numeric(out.get("change_pct", 0), errors="coerce").fillna(0.0)
    parts = [x for x in scope.split(",") if x]

    board_masks = []
    limit_masks = []
    for part in parts:
        if part == "sh_main":
            board_masks.append(code_s.str.startswith("60"))
        elif part == "kcb":
            board_masks.append(code_s.str.startswith("688"))
        elif part == "sz_main":
            board_masks.append(code_s.str.startswith(("00", "001", "002", "003")))
        elif part == "cyb":
            board_masks.append(code_s.str.startswith(("300", "301")))
        elif part == "limit_up":
            mask = pd.Series(False, index=out.index)
            mask = mask | (code_s.str.startswith(("300", "301", "688")) & (cp_s >= 19.5))
            mask = mask | (~code_s.str.startswith(("300", "301", "688")) & (cp_s >= 9.5))
            limit_masks.append(mask)
        elif part == "limit_down":
            mask = pd.Series(False, index=out.index)
            mask = mask | (code_s.str.startswith(("300", "301", "688")) & (cp_s <= -19.5))
            mask = mask | (~code_s.str.startswith(("300", "301", "688")) & (cp_s <= -9.5))
            limit_masks.append(mask)

    if board_masks:
        board_mask = pd.Series(False, index=out.index)
        for m in board_masks:
            board_mask = board_mask | m
        out = out[board_mask]
    if limit_masks:
        limit_mask = pd.Series(True, index=out.index)
        for m in limit_masks:
            limit_mask = limit_mask & m
        out = out[limit_mask]
    return out


def _query_dataframe(query: str, params: List | Tuple | None = None) -> pd.DataFrame:
    conn = get_db_connection()
    try:
        return pd.read_sql(query, conn, params=params or [])
    finally:
        conn.close()


def get_strategy_data_coverage() -> Dict:
    """返回策略引擎关键依赖数据的覆盖情况，便于判断结果是否可信。"""
    global _COVERAGE_CACHE
    now = time.time()
    if _COVERAGE_CACHE and (now - _COVERAGE_CACHE[0]) <= _CACHE_TTL_SECONDS:
        return dict(_COVERAGE_CACHE[1])

    conn = get_db_connection()
    try:
        latest_total = int(
            pd.read_sql(
                "SELECT COUNT(*) AS c FROM daily_market WHERE date = (SELECT MAX(date) FROM daily_market)",
                conn,
            ).iloc[0]["c"]
            or 0
        )
        kline_counts = pd.read_sql(
            """
            SELECT code, COUNT(*) AS cnt
            FROM kline_data
            WHERE frequency = 'daily' AND adjust_flag = 'bfq'
            GROUP BY code
            """,
            conn,
        )
        basic_cov = int(pd.read_sql("SELECT COUNT(DISTINCT code) AS c FROM stock_basic", conn).iloc[0]["c"] or 0)
        financial_cov = int(pd.read_sql("SELECT COUNT(DISTINCT code) AS c FROM financial_data", conn).iloc[0]["c"] or 0)
    finally:
        conn.close()

    counts = pd.to_numeric(kline_counts.get("cnt"), errors="coerce").fillna(0) if not kline_counts.empty else pd.Series(dtype=float)
    payload = {
        "latest_total": latest_total,
        "kline_5d": int((counts >= 5).sum()) if not counts.empty else 0,
        "kline_10d": int((counts >= 10).sum()) if not counts.empty else 0,
        "kline_20d": int((counts >= 20).sum()) if not counts.empty else 0,
        "kline_40d": int((counts >= 40).sum()) if not counts.empty else 0,
        "kline_60d": int((counts >= 60).sum()) if not counts.empty else 0,
        "basic": basic_cov,
        "financial": financial_cov,
    }
    _COVERAGE_CACHE = (now, payload)
    return dict(payload)


def _coverage_hint_for_strategy(strategy_id: str) -> str:
    cov = get_strategy_data_coverage()
    total = max(int(cov.get("latest_total") or 0), 1)
    required_days = {
        "jinfenghuang": 8,
        "longtou": 6,
        "breakthrough": 22,
        "pullback_ma": 15,
        "continuous_limit": 5,
        "first_limit": 60,
        "macd_golden": 26,
        "kdj_oversold": 9,
        "volume_ratio": 5,
        "hot_money": 5,
        "trend_acceleration": 20,
        "value_quality": 1,
    }
    need_days = required_days.get(strategy_id, 5)
    if need_days >= 60:
        covered = int(cov.get("kline_60d") or 0)
    elif need_days >= 40:
        covered = int(cov.get("kline_40d") or 0)
    elif need_days >= 20:
        covered = int(cov.get("kline_20d") or 0)
    elif need_days >= 10:
        covered = int(cov.get("kline_10d") or 0)
    else:
        covered = int(cov.get("kline_5d") or 0)

    parts = [f"{covered}/{total} 只股票具备≥{need_days}日K线"]
    if strategy_id == "value_quality":
        parts.append(f"{int(cov.get('financial') or 0)}/{total} 只有财务数据")
    return "；".join(parts)


def get_kline_data(code: str, days: int = 80) -> pd.DataFrame:
    """读取个股近 N 天 K 线，若历史表缺失则回退到日行情快照表。"""
    now = time.time()
    key = (str(code), int(days))
    hit = _KLINE_CACHE.get(key)
    if hit and (now - hit[0]) <= _CACHE_TTL_SECONDS:
        return hit[1].copy()

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    kline_query = """
        SELECT date, open, high, low, close, volume, amount,
               COALESCE(change_pct, 0) AS change_pct,
               COALESCE(turnover_rate, 0) AS turnover_rate
        FROM kline_data
        WHERE code = ? AND date >= ? AND frequency = 'daily' AND adjust_flag = 'bfq'
        ORDER BY date
    """
    df = _query_dataframe(kline_query, [code, start_date])

    if df.empty:
        fallback_query = """
            SELECT date,
                   price AS close,
                   price AS open,
                   price AS high,
                   price AS low,
                   COALESCE(volume, 0) AS volume,
                   COALESCE(amount, 0) AS amount,
                   COALESCE(change_pct, 0) AS change_pct,
                   COALESCE(turnover, 0) AS turnover_rate
            FROM daily_market
            WHERE code = ? AND date >= ?
            ORDER BY date
        """
        df = _query_dataframe(fallback_query, [code, start_date])

    if df.empty:
        return df

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "change_pct",
        "turnover_rate",
    ]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    _KLINE_CACHE[key] = (now, df.copy())
    if len(_KLINE_CACHE) > 500:
        # 简单淘汰最老的一批，避免缓存无限增长
        for k, _ in sorted(_KLINE_CACHE.items(), key=lambda x: x[1][0])[:100]:
            _KLINE_CACHE.pop(k, None)
    return df


def get_latest_market_data() -> pd.DataFrame:
    """获取最新一日行情，并补齐基础信息。"""
    global _MARKET_CACHE
    now = time.time()
    if _MARKET_CACHE and (now - _MARKET_CACHE[0]) <= _CACHE_TTL_SECONDS:
        return _MARKET_CACHE[1].copy()

    query = """
        SELECT dm.*, sb.industry, sb.area, sb.market
        FROM daily_market dm
        LEFT JOIN stock_basic sb ON dm.code = sb.code
        WHERE dm.date = (SELECT MAX(date) FROM daily_market)
    """
    df = _query_dataframe(query)
    if df.empty:
        return df

    numeric_columns = ["price", "pe", "pb", "turnover", "volume", "amount", "change_pct"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    _MARKET_CACHE = (now, df.copy())
    return df


def calculate_ma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def calculate_macd(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    exp1 = df["close"].ewm(span=12, adjust=False).mean()
    exp2 = df["close"].ewm(span=26, adjust=False).mean()
    dif = exp1 - exp2
    dea = dif.ewm(span=9, adjust=False).mean()
    bar = dif - dea
    return dif, dea, bar


def calculate_kdj(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    low_min = df["low"].rolling(window=9).min()
    high_max = df["high"].rolling(window=9).max()
    denom = (high_max - low_min).replace(0, np.nan)
    rsv = ((df["close"] - low_min) / denom * 100).fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def _is_limit_up(code: str, change_pct: float) -> bool:
    cp = _safe_float(change_pct)
    if code.startswith(("300", "301", "688")):
        return cp >= 19.5
    return cp >= 9.5


def strategy_jinfenghuang(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=30)
        if len(hist) < 8:
            continue

        recent = hist.tail(8).reset_index(drop=True)
        limit_idx = [i for i, cp in enumerate(recent["change_pct"].tolist()) if _is_limit_up(code, cp)]
        if not limit_idx:
            continue

        first_idx = limit_idx[0]
        pullback_days = len(recent) - first_idx - 1
        if pullback_days < 2 or pullback_days > 5:
            continue

        pullback = recent.iloc[first_idx + 1 : -1]
        if pullback.empty:
            continue

        first_close = _safe_float(recent.iloc[first_idx]["close"], 1)
        max_draw = (_safe_float(pullback["close"].min()) - first_close) / first_close
        today_cp = _safe_float(row.get("change_pct"))

        if max_draw >= -0.08 and today_cp >= 3:
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": today_cp,
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"涨停后回调{pullback_days}天并再启动",
                    "score": 80 + today_cp,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_longtou(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        name = str(row.get("name", ""))
        if "ST" in name:
            continue

        code = str(row["code"])
        hist = get_kline_data(code, days=12)
        if len(hist) < 6:
            continue

        first = _safe_float(hist["close"].iloc[0], 0)
        last = _safe_float(hist["close"].iloc[-1], 0)
        if first <= 0:
            continue

        five_day_return = (last - first) / first * 100
        avg_turnover = _safe_float(hist["turnover_rate"].tail(5).mean())
        amount = _safe_float(row.get("amount"))

        if five_day_return >= 12 and 4 <= avg_turnover <= 30 and amount >= 300_000_000:
            results.append(
                {
                    "code": code,
                    "name": name,
                    "price": _safe_float(row.get("price")),
                    "change_pct": _safe_float(row.get("change_pct")),
                    "turnover": avg_turnover,
                    "reason": f"近5日涨幅{five_day_return:.2f}%",
                    "score": 75 + five_day_return / 3,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_breakthrough(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=40)
        if len(hist) < 22:
            continue

        today = hist.iloc[-1]
        prev_20_high = _safe_float(hist["high"].iloc[-21:-1].max())
        today_close = _safe_float(today["close"])
        vol5 = _safe_float(hist["volume"].tail(5).mean(), 1)
        today_vol = _safe_float(today["volume"])
        cp = _safe_float(row.get("change_pct"))

        if today_close > prev_20_high and today_vol >= vol5 * 1.5 and cp > 2:
            ratio = today_vol / vol5 if vol5 > 0 else 1
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": cp,
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"突破20日高点，量比{ratio:.2f}",
                    "score": 72 + cp + min(ratio * 3, 12),
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_pullback_ma(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=35)
        if len(hist) < 15:
            continue

        ma5 = _safe_float(calculate_ma(hist["close"], 5).iloc[-1], 0)
        ma10 = _safe_float(calculate_ma(hist["close"], 10).iloc[-1], 0)
        close = _safe_float(hist["close"].iloc[-1], 0)
        cp = _safe_float(row.get("change_pct"))

        if ma10 <= 0:
            continue

        d5 = abs(close - ma5) / ma5 * 100 if ma5 > 0 else 99
        d10 = abs(close - ma10) / ma10 * 100
        vol5 = _safe_float(hist["volume"].tail(5).mean(), 1)
        v_today = _safe_float(hist["volume"].iloc[-1])

        if min(d5, d10) <= 2.2 and close >= ma10 and -4 <= cp <= 2 and v_today <= vol5 * 1.1:
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": cp,
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"回踩均线，距离MA10 {d10:.2f}%",
                    "score": 68 + max(0, 5 - min(d5, d10)) * 4,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_continuous_limit(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        cp = _safe_float(row.get("change_pct"))
        if not _is_limit_up(code, cp):
            continue

        hist = get_kline_data(code, days=12)
        if len(hist) < 3:
            continue

        streak = 0
        for v in reversed(hist["change_pct"].tolist()):
            if _is_limit_up(code, _safe_float(v)):
                streak += 1
            else:
                break

        if streak >= 2 and _safe_float(row.get("turnover")) <= 32:
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": cp,
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"{streak}连板强势",
                    "score": 88 + streak * 6,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_first_limit(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        cp = _safe_float(row.get("change_pct"))
        if not _is_limit_up(code, cp):
            continue

        hist = get_kline_data(code, days=140)
        # 这里需要近 60 个交易日来判断“低位首板”，90 个自然日经常不够覆盖 60 个交易日
        if len(hist) < 60:
            continue

        today = _safe_float(hist["close"].iloc[-1], 0)
        low60 = _safe_float(hist["close"].tail(60).min(), 0)
        if low60 <= 0 or today > low60 * 1.35:
            continue

        prev10 = hist.iloc[:-1].tail(10)
        if prev10.empty or any(_is_limit_up(code, _safe_float(x)) for x in prev10["change_pct"].tolist()):
            continue

        results.append(
            {
                "code": code,
                "name": row.get("name", ""),
                "price": _safe_float(row.get("price")),
                "change_pct": cp,
                "turnover": _safe_float(row.get("turnover")),
                "reason": "低位首板启动",
                "score": 82 + cp,
            }
        )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_macd_golden(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=70)
        if len(hist) < 35:
            continue

        dif, dea, _ = calculate_macd(hist)
        if dif.iloc[-2] <= dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            ratio = _safe_float(hist["volume"].iloc[-1]) / max(_safe_float(hist["volume"].tail(5).mean()), 1)
            score = 70 + (_safe_float(row.get("change_pct")) / 2)
            if dif.iloc[-1] > 0:
                score += 8
            if ratio > 1.3:
                score += 10
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": _safe_float(row.get("change_pct")),
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"MACD金叉，量比{ratio:.2f}",
                    "score": score,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_kdj_oversold(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=45)
        if len(hist) < 20:
            continue

        k, d, j = calculate_kdj(hist)
        if k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 30 and d.iloc[-1] < 30:
            cp = _safe_float(row.get("change_pct"))
            results.append(
                {
                    "code": code,
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": cp,
                    "turnover": _safe_float(row.get("turnover")),
                    "reason": f"KDJ超卖金叉 (K={k.iloc[-1]:.1f}, D={d.iloc[-1]:.1f}, J={j.iloc[-1]:.1f})",
                    "score": 66 + cp,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_volume_ratio(df: pd.DataFrame) -> List[Dict]:
    results = []
    for _, row in df.iterrows():
        turnover = _safe_float(row.get("turnover"))
        cp = _safe_float(row.get("change_pct"))
        amount = _safe_float(row.get("amount"))
        if turnover >= 8 and cp >= 2 and amount >= 200_000_000:
            results.append(
                {
                    "code": row.get("code"),
                    "name": row.get("name", ""),
                    "price": _safe_float(row.get("price")),
                    "change_pct": cp,
                    "turnover": turnover,
                    "reason": f"放量活跃，换手{turnover:.1f}%",
                    "score": 62 + cp + min(turnover, 20),
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_hot_money(df: pd.DataFrame) -> List[Dict]:
    hot_words = ["芯片", "半导体", "算力", "AI", "机器人", "医药", "电池", "光伏", "军工", "华为"]
    results = []
    for _, row in df.iterrows():
        code = str(row.get("code", ""))
        name = str(row.get("name", ""))
        amount = _safe_float(row.get("amount"))
        turnover = _safe_float(row.get("turnover"))
        cp = _safe_float(row.get("change_pct"))
        price = _safe_float(row.get("price"))

        float_mv = amount / turnover * 100 if turnover > 0 else 0
        float_mv_yi = float_mv / 1e8

        conds = {
            "mv": 30 <= float_mv_yi <= 300,
            "turnover": 8 <= turnover <= 30,
            "amount": amount >= 300_000_000,
            "change": 2 <= cp <= 9.5,
            "hot": any(w in name for w in hot_words),
        }
        score = 0
        if conds["mv"]:
            score += 18
        if conds["turnover"]:
            score += 16
        if conds["amount"]:
            score += 16
        if conds["change"]:
            score += 15
        if conds["hot"]:
            score += 15

        if sum(conds.values()) >= 3 and score >= 50:
            expect = "延续强势" if cp >= 5 else "有望补涨"
            results.append(
                {
                    "code": code,
                    "name": name,
                    "price": price,
                    "change_pct": cp,
                    "turnover": turnover,
                    "amount": amount / 1e8,
                    "float_mv": float_mv_yi,
                    "reason": f"游资偏好形态，成交额{amount/1e8:.1f}亿",
                    "next_day_expect": expect,
                    "score": score + cp,
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_trend_acceleration(df: pd.DataFrame) -> List[Dict]:
    """趋势加速：MA20上方并连续走强。"""
    results = []
    for _, row in df.iterrows():
        code = str(row["code"])
        hist = get_kline_data(code, days=50)
        if len(hist) < 25:
            continue

        ma20 = calculate_ma(hist["close"], 20)
        if ma20.isna().iloc[-1]:
            continue

        close = _safe_float(hist["close"].iloc[-1])
        close_prev = _safe_float(hist["close"].iloc[-2], close)
        ma20_v = _safe_float(ma20.iloc[-1])
        cp = _safe_float(row.get("change_pct"))

        if close > ma20_v and close >= close_prev and cp >= 1:
            slope = (_safe_float(ma20.iloc[-1]) - _safe_float(ma20.iloc[-5])) / max(_safe_float(ma20.iloc[-5], 1), 1) * 100
            if slope > 0:
                results.append(
                    {
                        "code": code,
                        "name": row.get("name", ""),
                        "price": _safe_float(row.get("price")),
                        "change_pct": cp,
                        "turnover": _safe_float(row.get("turnover")),
                        "reason": f"MA20上行加速，斜率{slope:.2f}%",
                        "score": 65 + slope + cp,
                    }
                )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def strategy_value_quality(df: pd.DataFrame) -> List[Dict]:
    """价值质量：低估值+稳定换手。"""
    target = df.copy()
    target = target[(target["pe"] > 0) & (target["pe"] <= 25) & (target["pb"] > 0) & (target["pb"] <= 3.5)]
    target = target[(target["turnover"] >= 1) & (target["turnover"] <= 8)]

    results = []
    for _, row in target.iterrows():
        pe = _safe_float(row.get("pe"))
        pb = _safe_float(row.get("pb"))
        cp = _safe_float(row.get("change_pct"))
        score = 70 + max(0, (25 - pe) * 0.7) + max(0, (3.5 - pb) * 3)
        results.append(
            {
                "code": row.get("code"),
                "name": row.get("name", ""),
                "price": _safe_float(row.get("price")),
                "change_pct": cp,
                "turnover": _safe_float(row.get("turnover")),
                "reason": f"低估值组合 PE={pe:.1f}, PB={pb:.2f}",
                "score": score,
            }
        )

    return sorted(results, key=lambda x: x["score"], reverse=True)


STRATEGIES: Dict[str, Dict[str, str | Callable]] = {
    "jinfenghuang": {"name": "金凤凰涨停战法", "func": strategy_jinfenghuang, "desc": "涨停回调再启动", "risk": "高风险", "suitable": "激进短线"},
    "longtou": {"name": "龙头战法", "func": strategy_longtou, "desc": "强势板块龙头", "risk": "高风险", "suitable": "趋势交易者"},
    "breakthrough": {"name": "突破战法", "func": strategy_breakthrough, "desc": "平台突破放量", "risk": "中高风险", "suitable": "突破交易者"},
    "pullback_ma": {"name": "回踩均线战法", "func": strategy_pullback_ma, "desc": "回踩 MA5/MA10", "risk": "中风险", "suitable": "稳健交易者"},
    "continuous_limit": {"name": "连板战法", "func": strategy_continuous_limit, "desc": "连板强势股", "risk": "极高风险", "suitable": "超短高手"},
    "first_limit": {"name": "首板挖掘战法", "func": strategy_first_limit, "desc": "低位首板启动", "risk": "中高风险", "suitable": "题材跟踪"},
    "macd_golden": {"name": "MACD 金叉战法", "func": strategy_macd_golden, "desc": "MACD 金叉配量能", "risk": "中风险", "suitable": "技术交易者"},
    "kdj_oversold": {"name": "KDJ 超卖战法", "func": strategy_kdj_oversold, "desc": "超卖区反弹信号", "risk": "中风险", "suitable": "反转交易者"},
    "volume_ratio": {"name": "量比战法", "func": strategy_volume_ratio, "desc": "放量活跃资金入场", "risk": "中风险", "suitable": "量价交易者"},
    "hot_money": {"name": "龙虎榜战法", "func": strategy_hot_money, "desc": "游资偏好题材形态", "risk": "高风险", "suitable": "游资风格"},
    "trend_acceleration": {"name": "趋势加速战法", "func": strategy_trend_acceleration, "desc": "MA20上行加速", "risk": "中风险", "suitable": "波段交易者"},
    "value_quality": {"name": "价值质量战法", "func": strategy_value_quality, "desc": "低估值+稳定换手", "risk": "中低风险", "suitable": "价值投资者"},
}


def _calc_return(prices: pd.Series, lookback: int) -> float | None:
    if len(prices) <= lookback:
        return None
    latest = _safe_float(prices.iloc[-1], 0)
    base = _safe_float(prices.iloc[-1 - lookback], 0)
    if latest <= 0 or base <= 0:
        return None
    return (latest - base) / base * 100


def _calc_max_drawdown(prices: pd.Series, lookback: int) -> float | None:
    if len(prices) <= lookback:
        return None
    window = prices.iloc[-lookback:].astype(float)
    rolling_peak = window.cummax()
    drawdown = (window - rolling_peak) / rolling_peak * 100
    return float(drawdown.min()) if not drawdown.empty else None


def enrich_with_backtest_metrics(stocks: List[Dict], lookbacks: Tuple[int, int] = (20, 60)) -> Dict:
    """为推荐结果附加近20/60日收益与回撤，并返回汇总统计。"""
    enriched = []
    for stock in stocks:
        code = str(stock.get("code", ""))
        row = dict(stock)
        hist = get_kline_data(code, days=max(lookbacks) + 40)
        if not hist.empty and "close" in hist.columns:
            closes = hist["close"]
            for lb in lookbacks:
                row[f"ret_{lb}d"] = _calc_return(closes, lb)
                row[f"mdd_{lb}d"] = _calc_max_drawdown(closes, lb)
        else:
            for lb in lookbacks:
                row[f"ret_{lb}d"] = None
                row[f"mdd_{lb}d"] = None
        enriched.append(row)

    summary = {
        "avg_ret_20d": None,
        "avg_ret_60d": None,
        "avg_mdd_20d": None,
        "avg_mdd_60d": None,
        "coverage_20d": 0,
        "coverage_60d": 0,
    }
    if enriched:
        for lb in lookbacks:
            ret_key = f"ret_{lb}d"
            mdd_key = f"mdd_{lb}d"
            valid_ret = [v for v in (x.get(ret_key) for x in enriched) if v is not None]
            valid_mdd = [v for v in (x.get(mdd_key) for x in enriched) if v is not None]
            if valid_ret:
                summary[f"avg_{ret_key}"] = float(np.mean(valid_ret))
                summary[f"coverage_{lb}d"] = len(valid_ret)
            if valid_mdd:
                summary[f"avg_{mdd_key}"] = float(np.mean(valid_mdd))
    return {"rows": enriched, "summary": summary}


def _quick_rank_market(
    market_data: pd.DataFrame,
    top_n: int = 10,
    preferred_ids: List[str] | None = None,
    strategy_name: str = "快速行情评分",
) -> List[Dict]:
    """
    快速兜底推荐（无需逐股回看 K 线）：
    用于完整战法计算为空/超时时，保证前端可返回结果。
    """
    if market_data is None or market_data.empty:
        return []

    df = market_data.copy()
    if "name" in df.columns:
        df = df[~df["name"].astype(str).str.contains("ST", case=False, na=False)]
    if "price" in df.columns:
        df = df[pd.to_numeric(df["price"], errors="coerce").fillna(0) > 0]

    for col in ["change_pct", "turnover", "amount", "price", "pe", "pb"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 限制极端值，避免异常数据主导排序
    cp = df["change_pct"].clip(-12, 12)
    turnover = df["turnover"].clip(0, 40)
    amount_yi = (df["amount"] / 1e8).clip(0, 120)
    pe_bonus = (30 - df["pe"].clip(0, 80)).clip(-20, 30) * 0.2
    pb_bonus = (4 - df["pb"].clip(0, 12)).clip(-8, 4) * 0.8

    df["quick_score"] = (
        55
        + cp * 2.4
        + np.log1p(turnover) * 7.0
        + np.log1p(amount_yi) * 6.5
        + pe_bonus
        + pb_bonus
    ).clip(0, 100)

    df = df.sort_values(["quick_score", "change_pct", "turnover"], ascending=[False, False, False], kind="stable")
    df = df.head(max(1, top_n))

    strategies = []
    if preferred_ids:
        strategies = [STRATEGIES[x]["name"] for x in preferred_ids if x in STRATEGIES][:3]
    if not strategies:
        strategies = [strategy_name]

    rows: List[Dict] = []
    for _, row in df.iterrows():
        cpv = _safe_float(row.get("change_pct"))
        exp = "震荡偏强" if cpv >= 0 else "关注企稳"
        rows.append(
            {
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "price": _safe_float(row.get("price")),
                "change_pct": cpv,
                "turnover": _safe_float(row.get("turnover")),
                "amount": _safe_float(row.get("amount")) / 1e8,
                "float_mv": (_safe_float(row.get("amount")) / _safe_float(row.get("turnover")) * 100 / 1e8)
                if _safe_float(row.get("turnover")) > 0
                else 0,
                "strategy_count": max(1, len(strategies)),
                "strategies": strategies,
                "reason": "基于涨跌幅、换手率、成交额与估值的快速综合评分",
                "summary_reason": "快速评分兜底推荐",
                "next_day_expect": exp,
                "score": float(row.get("quick_score", 0)),
                "composite_score": float(row.get("quick_score", 0)),
            }
        )
    return rows


def quick_recommend_market(
    top_n: int = 10,
    preferred_ids: List[str] | None = None,
    strategy_name: str = "快速行情评分",
    market_scope: str = "all",
) -> Dict:
    """对外快速推荐接口。"""
    market_data = _apply_market_scope(get_latest_market_data(), market_scope)
    rows = _quick_rank_market(
        market_data=market_data,
        top_n=top_n,
        preferred_ids=preferred_ids or [],
        strategy_name=strategy_name,
    )
    stats = enrich_with_backtest_metrics(rows)
    return {
        "strategies": preferred_ids or [],
        "total_found": len(stats["rows"]),
        "backtest_summary": stats["summary"],
        "recommendations": stats["rows"],
        "fallback": True,
        "fallback_reason": "使用快速行情评分引擎",
        "market_scope": normalize_market_scope(market_scope, strict=False),
    }


def run_strategy(
    strategy_id: str,
    top_n: int = 3,
    market_data: pd.DataFrame | None = None,
    market_scope: str = "all",
) -> Dict:
    if strategy_id not in STRATEGIES:
        return {"error": f"未知策略：{strategy_id}"}

    normalized_scope = normalize_market_scope(market_scope, strict=False)
    market_data = market_data if market_data is not None else get_latest_market_data()
    market_data = _apply_market_scope(market_data, normalized_scope)
    if market_data.empty:
        return {"error": f"当前市场范围({normalized_scope})暂无数据"}

    strategy = STRATEGIES[strategy_id]
    try:
        native_rows = strategy["func"](market_data)
        native_count = len(native_rows)
        rows = native_rows[: max(1, top_n)]
        fallback = False
        fallback_reason = None
        if not rows:
            fallback = True
            fallback_reason = f"原始战法未命中，已降级为快速评分；当前数据覆盖：{_coverage_hint_for_strategy(strategy_id)}"
            rows = _quick_rank_market(
                market_data=market_data,
                top_n=top_n,
                preferred_ids=[strategy_id],
                strategy_name=f"{strategy['name']}-快速兜底",
            )
        stats = enrich_with_backtest_metrics(rows)
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy["name"],
            "description": strategy["desc"],
            "risk_level": strategy["risk"],
            "native_total_found": native_count,
            "total_found": len(stats["rows"]),
            "backtest_summary": stats["summary"],
            "recommendations": stats["rows"],
            "market_scope": normalized_scope,
            "fallback": fallback,
            "fallback_reason": fallback_reason,
            "data_coverage": get_strategy_data_coverage(),
        }
    except Exception as exc:
        fallback_rows = _quick_rank_market(
            market_data=market_data,
            top_n=top_n,
            preferred_ids=[strategy_id],
            strategy_name=f"{strategy['name']}-异常兜底",
        )
        stats = enrich_with_backtest_metrics(fallback_rows)
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy["name"],
            "description": strategy["desc"],
            "risk_level": strategy["risk"],
            "native_total_found": 0,
            "total_found": len(stats["rows"]),
            "backtest_summary": stats["summary"],
            "recommendations": stats["rows"],
            "fallback": True,
            "fallback_reason": f"策略执行失败，已使用快速兜底：{exc}；当前数据覆盖：{_coverage_hint_for_strategy(strategy_id)}",
            "market_scope": normalized_scope,
            "data_coverage": get_strategy_data_coverage(),
        }


def run_multi_strategies(strategy_ids: List[str], top_n: int = 10, market_scope: str = "all") -> Dict:
    """多战法聚合，输出共识结果。"""
    all_rows: List[Dict] = []
    used = []
    empty_summary = {
        "avg_ret_20d": None,
        "avg_ret_60d": None,
        "avg_mdd_20d": None,
        "avg_mdd_60d": None,
        "coverage_20d": 0,
        "coverage_60d": 0,
    }

    normalized_scope = normalize_market_scope(market_scope, strict=False)
    market_data = _apply_market_scope(get_latest_market_data(), normalized_scope)
    if market_data.empty:
        return {
            "strategies": [],
            "total_found": 0,
            "backtest_summary": empty_summary,
            "recommendations": [],
            "market_scope": normalized_scope,
        }

    for sid in strategy_ids:
        if sid not in STRATEGIES:
            continue
        result = run_strategy(sid, top_n=max(8, top_n), market_data=market_data, market_scope=normalized_scope)
        if "error" in result:
            continue
        used.append(sid)
        for stock in result.get("recommendations", []):
            enriched = dict(stock)
            enriched["strategy_id"] = sid
            enriched["strategy_name"] = STRATEGIES[sid]["name"]
            all_rows.append(enriched)

    if not all_rows:
        fallback_rows = _quick_rank_market(
            market_data=market_data,
            top_n=top_n,
            preferred_ids=used or strategy_ids,
            strategy_name="多战法快速兜底",
        )
        stats = enrich_with_backtest_metrics(fallback_rows)
        return {
            "strategies": used,
            "total_found": len(stats["rows"]),
            "backtest_summary": stats["summary"],
            "recommendations": stats["rows"],
            "fallback": True,
            "fallback_reason": "完整战法无命中，返回快速评分结果",
            "market_scope": normalized_scope,
        }

    merged: Dict[str, Dict] = {}
    for row in all_rows:
        code = row.get("code")
        if code not in merged:
            merged[code] = {
                "code": code,
                "name": row.get("name"),
                "price": row.get("price"),
                "change_pct": row.get("change_pct"),
                "turnover": row.get("turnover"),
                "strategy_count": 0,
                "strategies": [],
                "reasons": [],
                "composite_score": 0.0,
            }
        merged[code]["strategy_count"] += 1
        merged[code]["strategies"].append(row.get("strategy_name"))
        if row.get("reason"):
            merged[code]["reasons"].append(row.get("reason"))
        merged[code]["composite_score"] += _safe_float(row.get("score"), 50)

    ranked = []
    for item in merged.values():
        item["composite_score"] += item["strategy_count"] * 6
        item["summary_reason"] = " | ".join(item["reasons"][:2])
        ranked.append(item)

    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    ranked = ranked[:top_n]
    stats = enrich_with_backtest_metrics(ranked)

    return {
        "strategies": used,
        "total_found": len(stats["rows"]),
        "backtest_summary": stats["summary"],
        "recommendations": stats["rows"],
        "market_scope": normalized_scope,
    }
