from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean


@dataclass
class StrategySignalResult:
    symbol: str
    strategy_key: str
    hit: bool
    score: float
    confidence: float
    reasons: list[str]
    risk_tags: list[str]
    feature_snapshot: dict
    market_fit_score: float
    conflict_tags: list[str]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_up(value: float, low: float, high: float) -> float:
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return (value - low) / max(high - low, 1e-6) * 100.0


def _score_down(value: float, low: float, high: float) -> float:
    if value <= low:
        return 100.0
    if value >= high:
        return 0.0
    return (high - value) / max(high - low, 1e-6) * 100.0


def _avg(values: list[float], default: float = 0.0) -> float:
    cleaned = [v for v in values if math.isfinite(v)]
    return mean(cleaned) if cleaned else default


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result: list[float] = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def _extract_quote(context: dict) -> dict:
    quote = context.get("quote")
    if isinstance(quote, dict):
        return quote
    return {}


def _extract_bars(context: dict) -> list[dict]:
    source = context.get("daily_bars") or context.get("bars") or []
    rows = [row for row in source if isinstance(row, dict)]
    if len(rows) >= 2:
        first = str(rows[0].get("trade_date", ""))
        last = str(rows[-1].get("trade_date", ""))
        if first and last and first > last:
            rows.reverse()
    return rows


def _build_features(context: dict) -> dict[str, float | bool | str]:
    quote = _extract_quote(context)
    bars = _extract_bars(context)
    closes = [_safe_float(row.get("close"), 0.0) for row in bars if _safe_float(row.get("close"), 0.0) > 0]
    highs = [_safe_float(row.get("high"), 0.0) for row in bars if _safe_float(row.get("high"), 0.0) > 0]
    lows = [_safe_float(row.get("low"), 0.0) for row in bars if _safe_float(row.get("low"), 0.0) > 0]
    volumes = [_safe_float(row.get("volume"), 0.0) for row in bars if _safe_float(row.get("volume"), 0.0) > 0]
    amounts = [_safe_float(row.get("amount"), 0.0) for row in bars if _safe_float(row.get("amount"), 0.0) > 0]

    price = _safe_float(quote.get("price"), closes[-1] if closes else 0.0)
    close = _safe_float(quote.get("close"), price if price > 0 else (closes[-1] if closes else 0.0))
    open_price = _safe_float(quote.get("open"), close)
    high = _safe_float(quote.get("high"), max(open_price, close))
    low = _safe_float(quote.get("low"), min(open_price, close))
    change_pct = _safe_float(quote.get("change_pct"), context.get("change_pct", 0.0))
    prev_close = _safe_float(quote.get("prev_close"), closes[-2] if len(closes) >= 2 else close / max(1 + change_pct / 100.0, 1e-6))
    volume = _safe_float(quote.get("volume"), volumes[-1] if volumes else 0.0)
    amount = _safe_float(quote.get("amount"), amounts[-1] if amounts else max(close * volume, 0.0))
    turnover_rate = _safe_float(quote.get("turnover_rate"), context.get("turnover_rate", 0.0))
    vwap = _safe_float(quote.get("vwap"), close)
    main_inflow = _safe_float(quote.get("main_net_inflow"), context.get("main_net_inflow", 0.0))
    large_order_inflow = _safe_float(quote.get("large_order_net"), context.get("large_order_net", 0.0))

    ma5 = _avg(closes[-5:], close)
    ma10 = _avg(closes[-10:], close)
    ma20 = _avg(closes[-20:], close)
    ma60 = _avg(closes[-60:], close)
    avg_volume_5 = _avg(volumes[-5:], max(volume, 1.0))
    avg_amount_5 = _avg(amounts[-5:], max(amount, 1.0))

    prev_high_20 = max(highs[-21:-1], default=high if high > 0 else close)
    prev_close_5 = closes[-6] if len(closes) >= 6 else prev_close
    close_10_max = max(closes[-10:], default=close)
    close_10_min = min(closes[-10:], default=close)

    range_size = max(high - low, 1e-6)
    upper_shadow_ratio = max(0.0, high - max(open_price, close)) / range_size
    lower_shadow_ratio = max(0.0, min(open_price, close) - low) / range_size
    pullback_ratio = max(0.0, high - close) / range_size

    macd_hist = 0.0
    macd_hist_prev = 0.0
    if len(closes) >= 30:
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        diff = [a - b for a, b in zip(ema12, ema26)]
        dea = _ema(diff, 9)
        hist = [(d - s) * 2 for d, s in zip(diff, dea)]
        if hist:
            macd_hist = hist[-1]
            macd_hist_prev = hist[-2] if len(hist) >= 2 else 0.0

    market_state = str(context.get("market_state", "neutral")).lower()
    events = context.get("events", [])
    has_event = bool(context.get("has_event")) or bool(context.get("event_catalyst")) or (isinstance(events, list) and len(events) > 0)
    on_lhb = bool(context.get("on_lhb")) or bool(context.get("lhb_flag"))
    buyback = bool(context.get("buyback")) or bool(context.get("buyback_support"))
    earnings_growth = _safe_float(context.get("earnings_growth"), 0.0)

    return {
        "market_state": market_state,
        "price": close,
        "open": open_price,
        "high": high,
        "low": low,
        "change_pct": change_pct,
        "prev_close": prev_close,
        "open_gap_pct": (open_price - prev_close) / max(prev_close, 1e-6) * 100.0,
        "volume": volume,
        "amount": amount,
        "turnover_rate": turnover_rate,
        "vol_ratio": volume / max(avg_volume_5, 1.0),
        "amount_ratio": amount / max(avg_amount_5, 1.0),
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "trend_strength": (ma5 - ma20) / max(ma20, 1e-6) * 100.0,
        "breakout_pct": (close - prev_high_20) / max(prev_high_20, 1e-6) * 100.0,
        "momentum_5d": (close - prev_close_5) / max(prev_close_5, 1e-6) * 100.0,
        "close_10_max": close_10_max,
        "close_10_min": close_10_min,
        "upper_shadow_ratio": upper_shadow_ratio,
        "lower_shadow_ratio": lower_shadow_ratio,
        "pullback_ratio": pullback_ratio,
        "body_pct": (close - open_price) / max(open_price, 1e-6) * 100.0,
        "vwap_dev_pct": (close - vwap) / max(vwap, 1e-6) * 100.0,
        "macd_hist": macd_hist,
        "macd_hist_prev": macd_hist_prev,
        "near_limit_up": change_pct >= 9.2,
        "main_net_inflow": main_inflow,
        "large_order_net": large_order_inflow,
        "has_event": has_event,
        "on_lhb": on_lhb,
        "buyback": buyback,
        "earnings_growth": earnings_growth,
    }


def _base_risk_tags(features: dict[str, float | bool | str]) -> list[str]:
    tags: list[str] = []
    change_pct = float(features["change_pct"])
    if abs(change_pct) >= 8.0:
        tags.append("high_volatility")
    if float(features["vol_ratio"]) < 0.6:
        tags.append("weak_volume")
    if float(features["amount"]) < 2_000_000:
        tags.append("low_liquidity")
    if float(features["pullback_ratio"]) > 0.75:
        tags.append("sell_pressure")
    return tags


class StrategyBase:
    strategy_key: str = "base"
    strategy_name: str = "Base Strategy"
    category: str = "generic"
    risk_level: str = "medium"

    def evaluate(self, symbol: str, context: dict) -> StrategySignalResult:
        raise NotImplementedError


class HeuristicStrategy(StrategyBase):
    def __init__(self, strategy_key: str, strategy_name: str, category: str, risk_level: str, evaluator) -> None:
        self.strategy_key = strategy_key
        self.strategy_name = strategy_name
        self.category = category
        self.risk_level = risk_level
        self._evaluator = evaluator

    def _market_fit_factor(self, market_state: str) -> float:
        fit_map = {
            "emotion": {"bullish": 1.08, "neutral": 0.95, "weak": 0.78, "panic": 0.62},
            "trend": {"bullish": 1.05, "neutral": 1.0, "weak": 0.82, "panic": 0.68},
            "volume_price": {"bullish": 1.02, "neutral": 1.0, "weak": 0.9, "panic": 0.8},
            "fund": {"bullish": 1.06, "neutral": 1.0, "weak": 0.88, "panic": 0.74},
            "event": {"bullish": 1.04, "neutral": 1.02, "weak": 0.92, "panic": 0.83},
        }
        return fit_map.get(self.category, {}).get(market_state, 1.0)

    def evaluate(self, symbol: str, context: dict) -> StrategySignalResult:
        features = _build_features(context)
        market_state = str(features["market_state"])
        base_score, reasons, risk_tags = self._evaluator(features)
        market_factor = self._market_fit_factor(market_state)
        score = round(_clip(base_score * market_factor, 0.0, 100.0), 2)

        hit_threshold = 64.0 if market_state == "panic" and self.category in {"emotion", "trend"} else 60.0
        hit = score >= hit_threshold
        confidence = round(_clip(0.25 + score / 120.0 + (0.1 if hit else 0.0), 0.0, 1.0), 2)

        all_risks = sorted(set(_base_risk_tags(features) + risk_tags))
        conflict_tags: list[str] = []
        if self.category in {"emotion", "trend"} and market_state in {"weak", "panic"}:
            conflict_tags.append("market_state_conflict")
        if self.strategy_key == "vwap_reversion" and abs(float(features["change_pct"])) >= 7:
            conflict_tags.append("momentum_conflict")
        if "low_liquidity" in all_risks and self.category in {"emotion", "fund"}:
            conflict_tags.append("liquidity_conflict")

        feature_snapshot = {
            "change_pct": round(float(features["change_pct"]), 4),
            "vol_ratio": round(float(features["vol_ratio"]), 4),
            "amount_ratio": round(float(features["amount_ratio"]), 4),
            "breakout_pct": round(float(features["breakout_pct"]), 4),
            "trend_strength": round(float(features["trend_strength"]), 4),
            "macd_hist": round(float(features["macd_hist"]), 6),
        }
        return StrategySignalResult(
            symbol=symbol,
            strategy_key=self.strategy_key,
            hit=hit,
            score=score,
            confidence=confidence,
            reasons=reasons[:4] or [f"{self.strategy_name} score={score}"],
            risk_tags=all_risks,
            feature_snapshot=feature_snapshot,
            market_fit_score=round(_clip(score / 100.0, 0.0, 1.0), 2),
            conflict_tags=conflict_tags,
        )


def _score_first_board_breakout(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    score = (
        _score_up(float(f["change_pct"]), 4.0, 9.8) * 0.4
        + _score_up(float(f["vol_ratio"]), 1.1, 2.2) * 0.35
        + _score_up(float(f["breakout_pct"]), 0.4, 3.0) * 0.25
    )
    return score, ["涨速、量比和平台突破共同确认首板机会"], ["chase_risk"] if float(f["change_pct"]) > 9.0 else []


def _score_second_board_follow(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    gap_score = _score_up(float(f["open_gap_pct"]), 1.0, 5.0)
    score = _score_up(float(f["change_pct"]), 5.0, 9.5) * 0.45 + _score_up(float(f["vol_ratio"]), 1.0, 1.9) * 0.35 + gap_score * 0.2
    return score, ["强势高开叠加放量，适合二板接力节奏"], ["gap_risk"] if float(f["open_gap_pct"]) >= 4.5 else []


def _score_broken_board_recover(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    reclaim = _score_up(float(f["body_pct"]), 0.5, 4.5)
    pressure = _score_down(float(f["pullback_ratio"]), 0.18, 0.6)
    score = _score_up(float(f["change_pct"]), 2.0, 8.5) * 0.35 + reclaim * 0.35 + pressure * 0.3
    return score, ["回封力度与抛压回落改善，炸板修复信号增强"], ["intraday_reversal"]


def _score_platform_breakout(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    score = _score_up(float(f["breakout_pct"]), 0.2, 4.2) * 0.42 + _score_up(float(f["trend_strength"]), 0.1, 3.0) * 0.33 + _score_up(float(f["vol_ratio"]), 0.9, 1.8) * 0.25
    return score, ["突破幅度、趋势强度和成交配合满足平台突破条件"], []


def _score_volume_breakout(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    score = _score_up(float(f["vol_ratio"]), 1.4, 2.8) * 0.45 + _score_up(float(f["amount_ratio"]), 1.2, 2.3) * 0.35 + _score_up(float(f["breakout_pct"]), 0.0, 3.0) * 0.2
    return score, ["量比与成交额同步放大，突破可信度提升"], ["crowded_trade"] if float(f["vol_ratio"]) > 2.6 else []


def _score_n_shape_breakout(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    box_strength = _score_up(float(f["price"]) - float(f["close_10_min"]), 0.0, max(0.01, float(f["close_10_max"]) - float(f["close_10_min"])))
    score = _score_up(float(f["momentum_5d"]), 1.0, 8.0) * 0.4 + _score_up(float(f["breakout_pct"]), -0.2, 2.5) * 0.3 + box_strength * 0.3
    return score, ["近端回踩后再突破，N 字结构正在形成"], []


def _score_macd_second_cross(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    cross_bonus = 100.0 if float(f["macd_hist"]) > 0 and float(f["macd_hist_prev"]) <= 0 else _score_up(float(f["macd_hist"]), 0.0, 0.8)
    score = cross_bonus * 0.42 + _score_up(float(f["trend_strength"]), -0.5, 2.4) * 0.3 + _score_up(float(f["vol_ratio"]), 0.8, 1.8) * 0.28
    return score, ["MACD 柱线翻红并配合趋势修复"], ["indicator_lag"]


def _score_vwap_reversion(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    vwap_fit = _score_down(abs(float(f["vwap_dev_pct"])), 0.0, 2.2)
    rebound = _score_up(float(f["lower_shadow_ratio"]), 0.08, 0.45)
    score = vwap_fit * 0.45 + rebound * 0.3 + _score_down(abs(float(f["change_pct"])), 0.0, 5.5) * 0.25
    return score, ["偏离 VWAP 后回归，尾盘承接改善"], ["mean_reversion_fail"]


def _score_main_fund_inflow(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    inflow_ratio = float(f["main_net_inflow"]) / max(float(f["amount"]), 1.0)
    score = _score_up(inflow_ratio, 0.02, 0.15) * 0.55 + _score_up(float(f["amount"]), 5_000_000, 80_000_000) * 0.25 + _score_up(float(f["change_pct"]), 0.0, 5.0) * 0.2
    return score, ["主力资金净流入占比提升"], ["fund_turnover_risk"] if inflow_ratio < 0.03 else []


def _score_event_catalyst(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    event_score = 100.0 if bool(f["has_event"]) else 30.0
    score = event_score * 0.48 + _score_up(float(f["change_pct"]), -1.0, 6.0) * 0.28 + _score_up(float(f["vol_ratio"]), 0.9, 1.8) * 0.24
    return score, ["公告/事件催化与资金响应形成共振"], ["event_uncertainty"] if not bool(f["has_event"]) else []


def _score_reverse_wrap_board(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    score = _score_up(float(f["change_pct"]), 3.0, 9.0) * 0.45 + _score_up(float(f["body_pct"]), 1.0, 6.0) * 0.35 + _score_up(float(f["vol_ratio"]), 1.0, 2.0) * 0.2
    return score, ["日内反包幅度与实体强度同时改善"], ["false_breakout_risk"]


def _score_dragon_return(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    retrace_quality = _score_down(float(f["pullback_ratio"]), 0.12, 0.7)
    score = _score_up(float(f["momentum_5d"]), 1.5, 10.0) * 0.38 + _score_up(float(f["trend_strength"]), -0.3, 3.2) * 0.34 + retrace_quality * 0.28
    return score, ["龙头回踩后再次转强"], ["leader_volatility"]


def _score_golden_phoenix_limitup(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    limit_bonus = 100.0 if bool(f["near_limit_up"]) else _score_up(float(f["change_pct"]), 4.0, 9.8)
    score = limit_bonus * 0.44 + _score_up(float(f["vol_ratio"]), 1.1, 2.4) * 0.3 + _score_up(float(f["turnover_rate"]), 1.0, 8.0) * 0.26
    return score, ["强换手叠加涨停强度，金凤凰形态触发"], ["chase_risk"]


def _score_low_volume_pullback(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    trend_ok = _score_up(float(f["trend_strength"]), 0.1, 3.0)
    volume_calm = _score_down(float(f["vol_ratio"]), 0.55, 1.0)
    near_ma = _score_down(abs(float(f["price"]) - float(f["ma10"])) / max(float(f["ma10"]), 1e-6) * 100.0, 0.0, 3.0)
    score = trend_ok * 0.42 + volume_calm * 0.3 + near_ma * 0.28
    return score, ["趋势维持下的缩量回踩，有利于二次启动"], ["trend_break_risk"] if float(f["price"]) < float(f["ma20"]) else []


def _score_ma_bullish_align(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    align = 100.0 if float(f["ma5"]) > float(f["ma10"]) > float(f["ma20"]) else 35.0
    score = align * 0.55 + _score_up(float(f["trend_strength"]), 0.0, 2.8) * 0.25 + _score_up(float(f["vol_ratio"]), 0.8, 1.7) * 0.2
    return score, ["5/10/20 均线呈多头排列"], []


def _score_ma_expand(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    spread = (float(f["ma5"]) - float(f["ma20"])) / max(float(f["ma20"]), 1e-6) * 100.0
    long_base = _score_down(abs(float(f["ma20"]) - float(f["ma60"])) / max(float(f["ma60"]), 1e-6) * 100.0, 0.0, 6.0)
    score = _score_up(spread, 0.2, 2.8) * 0.56 + long_base * 0.24 + _score_up(float(f["change_pct"]), -0.5, 4.5) * 0.2
    return score, ["中短均线由粘合转发散，趋势扩散中"], ["late_trend_risk"] if spread > 2.5 else []


def _score_amount_expand(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    score = _score_up(float(f["amount_ratio"]), 1.2, 2.8) * 0.5 + _score_up(float(f["amount"]), 10_000_000, 120_000_000) * 0.32 + _score_up(float(f["change_pct"]), 0.0, 6.0) * 0.18
    return score, ["成交额放大且价格正反馈"], ["turnover_spike"]


def _score_lhb_resonance(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    lhb_score = 100.0 if bool(f["on_lhb"]) else 20.0
    inflow_ratio = float(f["main_net_inflow"]) / max(float(f["amount"]), 1.0)
    score = lhb_score * 0.5 + _score_up(inflow_ratio, 0.01, 0.12) * 0.32 + _score_up(float(f["change_pct"]), 0.5, 7.0) * 0.18
    return score, ["龙虎榜资金与主力净流入形成共振"], ["hot_money_volatility"] if bool(f["on_lhb"]) else ["missing_lhb_confirmation"]


def _score_large_order_netbuy(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    large_ratio = float(f["large_order_net"]) / max(float(f["amount"]), 1.0)
    score = _score_up(large_ratio, 0.005, 0.08) * 0.55 + _score_up(float(f["vol_ratio"]), 0.9, 1.8) * 0.25 + _score_up(float(f["change_pct"]), -0.5, 5.0) * 0.2
    return score, ["大单净买入占比提升，短线资金偏多"], []


def _score_buyback_support(f: dict[str, float | bool | str]) -> tuple[float, list[str], list[str]]:
    support = 100.0 if bool(f["buyback"]) else _score_up(float(f["earnings_growth"]), 5.0, 30.0)
    score = support * 0.5 + _score_down(abs(float(f["change_pct"])), 0.0, 5.0) * 0.3 + _score_up(float(f["trend_strength"]), -1.0, 2.0) * 0.2
    return score, ["回购/业绩信号对估值形成支撑"], ["event_lag_risk"] if not bool(f["buyback"]) else []


STRATEGY_SPECS = [
    ("first_board_breakout", "首板打板", "emotion", "high", _score_first_board_breakout),
    ("second_board_follow", "二板接力", "emotion", "high", _score_second_board_follow),
    ("broken_board_recover", "炸板回封", "emotion", "high", _score_broken_board_recover),
    ("platform_breakout", "平台突破", "trend", "medium", _score_platform_breakout),
    ("volume_breakout", "放量突破", "trend", "medium", _score_volume_breakout),
    ("n_shape_breakout", "N 字突破", "trend", "medium", _score_n_shape_breakout),
    ("macd_second_cross", "MACD 二次金叉", "volume_price", "medium", _score_macd_second_cross),
    ("vwap_reversion", "VWAP 回归", "volume_price", "medium", _score_vwap_reversion),
    ("main_fund_inflow", "主力净流入增强", "fund", "high", _score_main_fund_inflow),
    ("event_catalyst", "公告催化", "event", "medium", _score_event_catalyst),
    ("reverse_wrap_board", "反包板", "emotion", "high", _score_reverse_wrap_board),
    ("dragon_return", "龙回头", "emotion", "high", _score_dragon_return),
    ("golden_phoenix_limitup", "金凤凰涨停", "emotion", "high", _score_golden_phoenix_limitup),
    ("low_volume_pullback", "缩量回踩", "trend", "medium", _score_low_volume_pullback),
    ("ma_bullish_align", "均线多头排列", "trend", "medium", _score_ma_bullish_align),
    ("ma_expand", "均线粘合发散", "trend", "medium", _score_ma_expand),
    ("amount_expand", "成交额放大", "volume_price", "medium", _score_amount_expand),
    ("lhb_resonance", "龙虎榜游资共振", "fund", "high", _score_lhb_resonance),
    ("large_order_netbuy", "大单净买入", "fund", "medium", _score_large_order_netbuy),
    ("buyback_support", "回购增持", "event", "low", _score_buyback_support),
]


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategyBase] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for key, name, category, risk_level, evaluator in STRATEGY_SPECS:
            self._strategies[key] = HeuristicStrategy(
                strategy_key=key,
                strategy_name=name,
                category=category,
                risk_level=risk_level,
                evaluator=evaluator,
            )

    def list_strategies(self) -> list[StrategyBase]:
        return list(self._strategies.values())

    def get(self, strategy_key: str) -> StrategyBase | None:
        return self._strategies.get(strategy_key)

    def evaluate(self, symbol: str, strategy_keys: list[str] | None, context: dict) -> list[StrategySignalResult]:
        targets = [self._strategies[k] for k in strategy_keys if k in self._strategies] if strategy_keys else self.list_strategies()
        return [strategy.evaluate(symbol=symbol, context=context) for strategy in targets]
