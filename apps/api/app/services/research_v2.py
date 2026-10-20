"""AIStock v2 research-priority scorer.

No LLM influence, no order execution, no hidden network access. Scores are
research *priorities*, not return forecasts or win probabilities.
"""
from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any

ENGINE_VERSION = "2.0.0-rc2"
WEIGHTS = {"sector": 0.27, "quality": 0.23, "position": 0.22, "valuation": 0.13, "liquidity": 0.15}
REQUIRED_NUMERIC = (
    "float_cap_yi", "sector_excess_20d_pct", "sector_excess_60d_pct",
    "revenue_yoy_pct", "roe_ttm_pct", "net_profit_ttm_yi", "ocf_ttm_yi",
    "drawdown_120d_pct", "return_20d_pct", "valuation_percentile_3y",
    "relative_volume_20d", "turnover_amount_20d_yi", "volatility_20d_pct",
)
REQUIRED_TEXT = ("symbol", "sector", "source", "as_of", "fundamentals_published_on")
VALID_REGIMES = ("strong", "neutral", "weak", "panic")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def invalid_result(item: dict[str, Any], reasons: list[str], status: str) -> dict[str, Any]:
    return {
        "symbol": str(item.get("symbol") or ""), "sector": str(item.get("sector") or ""),
        "as_of": item.get("as_of"), "data_source": item.get("source"),
        "engine_version": ENGINE_VERSION, "status": status, "score": None,
        "factors": {}, "reasons": [], "risk_flags": [],
        "blocked_reasons": reasons, "research_priority": "none",
        "evidence_grade": "unverified_manual_input", "model_validation": "not_backtested",
    }


def evaluate_one(item: dict[str, Any], *, evaluation_date: date, market_regime: str) -> dict[str, Any]:
    """Use point-in-time inputs only. Never replace missing financial data with zero."""
    if market_regime not in VALID_REGIMES:
        raise ValueError("market_regime must be strong/neutral/weak/panic")

    missing = [key for key in REQUIRED_TEXT if not isinstance(item.get(key), str) or not item[key].strip()]
    missing += [key for key in ("is_st", "suspended") if type(item.get(key)) is not bool]
    for key in REQUIRED_NUMERIC:
        value = item.get(key)
        if type(value) not in (int, float) or not isfinite(value):
            missing.append(key)
    if missing:
        return invalid_result(item, ["缺少或非法字段：" + ", ".join(sorted(set(missing)))], "insufficient_data")

    try:
        as_of = date.fromisoformat(item["as_of"])
        disclosure = date.fromisoformat(item["fundamentals_published_on"])
    except ValueError:
        return invalid_result(item, ["日期格式必须为 YYYY-MM-DD"], "insufficient_data")

    if as_of > evaluation_date or disclosure > as_of:
        return invalid_result(item, ["数据或财报发布时间晚于研究时点，存在未来函数风险"], "insufficient_data")
    if (as_of - disclosure).days > 210:
        return invalid_result(item, ["财务报告最近披露日超过 210 天，无法确认当前财务质量"], "stale_fundamentals")
    if (evaluation_date - as_of).days > 14:
        return invalid_result(item, ["数据超过 14 个日历日，请刷新；长假需结合交易日历人工核实"], "stale_data")

    if not 0 <= item["drawdown_120d_pct"] <= 100 or not 0 <= item["valuation_percentile_3y"] <= 100:
        return invalid_result(item, ["回撤与历史估值分位应在 0 到 100 之间"], "insufficient_data")
    if item["relative_volume_20d"] < 0 or item["turnover_amount_20d_yi"] < 0 or item["volatility_20d_pct"] < 0:
        return invalid_result(item, ["成交量、成交额、波动率不可为负"], "insufficient_data")

    excluded = []
    if item["is_st"]:
        excluded.append("ST / *ST")
    if item["suspended"]:
        excluded.append("当前停牌")
    if not 30 <= item["float_cap_yi"] <= 500:
        excluded.append("流通市值不在 30～500 亿元研究范围")
    if item["net_profit_ttm_yi"] <= 0:
        excluded.append("最近十二个月净利润非正")
    if item["ocf_ttm_yi"] <= 0:
        excluded.append("最近十二个月经营现金流非正")
    if item["roe_ttm_pct"] < 0:
        excluded.append("ROE 为负")
    if excluded:
        return invalid_result(item, excluded, "excluded")

    sector20 = item["sector_excess_20d_pct"]
    sector60 = item["sector_excess_60d_pct"]
    # Experimental thesis: improving relative strength after a neglected period.
    sector = clamp(62 - abs(sector20 + 1.5) * 3 - abs(sector60) * 0.8)
    if sector60 < -2 and sector20 > sector60:
        sector = clamp(sector + 8)
    if -6 <= sector20 <= 4:
        sector = clamp(sector + 13)
    # Prefer recovering/ignored sectors, not necessarily the weakest outright.
    quality = clamp(48 + item["roe_ttm_pct"] * 1.4 + clamp(item["revenue_yoy_pct"], -30, 30) * 0.5)
    dd = item["drawdown_120d_pct"]
    position = clamp(87 - abs(dd - 28) * 2.0 - abs(item["return_20d_pct"] - 1) * 0.7)
    valuation = clamp(100 - item["valuation_percentile_3y"])
    volume = item["relative_volume_20d"]
    liquidity = clamp(65 - abs(volume - 1.12) * 28 + min(item["turnover_amount_20d_yi"], 8) * 2)
    factors = {"sector": sector, "quality": quality, "position": position, "valuation": valuation, "liquidity": liquidity}

    risk_flags = []
    penalty = 0.0
    if item["volatility_20d_pct"] > 5:
        penalty += min(18, (item["volatility_20d_pct"] - 5) * 3)
        risk_flags.append("波动过高")
    if item["return_20d_pct"] < -18:
        penalty += 15
        risk_flags.append("近期持续下行，警惕价值陷阱")
    if item["float_cap_yi"] > 300:
        penalty += 3
        risk_flags.append("市值处于放宽区间")
    if market_regime == "weak":
        penalty += 8
        risk_flags.append("弱势市场：仅观察")
    if market_regime == "panic":
        penalty += 18
        risk_flags.append("恐慌市场：暂停新增研究优先级")

    score = round(clamp(sum(factors[k] * v for k, v in WEIGHTS.items()) - penalty), 2)
    # Inputs arrive from a user-controlled endpoint, never a verified ETL chain.
    # Ranking is only a shortlist for evidence verification, not a buy signal.
    priority = "verify_first" if score >= 72 and market_regime not in ("weak", "panic") else "watch"
    reasons = [
        f"板块相对表现：20 日 {sector20:+.1f}%，60 日 {sector60:+.1f}%",
        f"盈利质量：ROE {item['roe_ttm_pct']:.1f}%，营收同比 {item['revenue_yoy_pct']:+.1f}%",
        f"位置与估值：120 日高点回撤 {dd:.1f}%，三年估值分位 {item['valuation_percentile_3y']:.1f}%",
    ]
    return {
        "symbol": item["symbol"], "sector": item["sector"], "as_of": item["as_of"],
        "data_source": item["source"], "engine_version": ENGINE_VERSION,
        "status": "research_candidate", "score": score,
        "factors": {k: round(v, 2) for k, v in factors.items()},
        "reasons": reasons, "risk_flags": risk_flags, "blocked_reasons": [],
        "research_priority": priority,
        "evidence_grade": "unverified_manual_input", "model_validation": "not_backtested",
        "score_components": {k: round(factors[k] * weight, 2) for k, weight in WEIGHTS.items()},
        "penalty_points": round(penalty, 2),
    }


def evaluate_batch(items: list[dict[str, Any]], *, evaluation_date: date, market_regime: str) -> dict[str, Any]:
    if not 1 <= len(items) <= 500:
        raise ValueError("items length must be 1..500")
    if len({item.get("symbol") for item in items}) != len(items):
        raise ValueError("duplicate symbols are not allowed within a research batch")
    results = [evaluate_one(item, evaluation_date=evaluation_date, market_regime=market_regime) for item in items]
    results.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), x["symbol"]))
    by_sector: dict[str, dict[str, Any]] = {}
    for row in results:
        if row["score"] is None:
            continue
        sector = row["sector"]
        state = by_sector.setdefault(sector, {"sector": sector, "sum": 0.0, "count": 0})
        state["sum"] += row["score"]
        state["count"] += 1
    sector_overview = sorted(
        ({"sector": val["sector"], "count": val["count"],
          "average_research_score": round(val["sum"] / val["count"], 2),
          "coverage": "insufficient" if val["count"] < 3 else "sample_only"}
         for val in by_sector.values()),
        key=lambda x: (-x["average_research_score"], x["sector"]),
    )
    return {
        "engine_version": ENGINE_VERSION, "market_regime": market_regime,
        "evaluated_as_of": evaluation_date.isoformat(), "count": len(results),
        "items": results, "sector_overview": sector_overview,
        "input_validation": "manual_unverified", "model_validation": "not_backtested",
        "warning": "仅按手工输入快照排序，不能证明时点真实、收益或胜率；行业比较只代表本批样本，不能代表全市场。"
    }
