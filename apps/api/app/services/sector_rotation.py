"""Deterministic sector-rotation hypotheses for offline research only.

No DB, network, LLM, or brokerage dependencies; no expected-return forecasts.
Inputs must be vetted by the API contract before use.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from math import isfinite
from typing import Any

VERSION = "sector-research-0.1.0"
WEIGHTS = {
    "recovery": {"neglect": .27, "acceleration": .33, "recent_strength": .23, "stability": .17},
    "trend": {"strength_20d": .35, "strength_60d": .30, "consistency": .20, "stability": .15},
}


def _clip(n: float) -> float:
    return max(0.0, min(100.0, n))


def _relative_return(sector: list[float], bench: list[float], end: int, window: int) -> float:
    return 100.0 * ((sector[end] / sector[end - window]) / (bench[end] / bench[end - window]) - 1.0)


def features(sector: list[float], benchmark: list[float]) -> dict[str, float]:
    """All indices are <= last known observation; 60 + 1 points required."""
    if len(sector) != len(benchmark) or len(sector) < 61:
        raise ValueError("Sector and benchmark require at least 61 aligned observations")
    if any(not isfinite(v) or v <= 0 for v in sector + benchmark):
        raise ValueError("All close prices must be positive and finite")
    end = len(sector) - 1
    rel20 = _relative_return(sector, benchmark, end, 20)
    rel60 = _relative_return(sector, benchmark, end, 60)
    prev20 = _relative_return(sector, benchmark, end - 20, 20)
    peak = max(sector[-61:])
    dd = 100.0 * (1.0 - sector[-1] / peak)
    return {
        "rel_20d_pct": round(rel20, 6),
        "rel_60d_pct": round(rel60, 6),
        "prior_rel_20d_pct": round(prev20, 6),
        "acceleration_pp": round(rel20 - prev20, 6),
        "drawdown_60d_pct": round(max(0.0, dd), 6),
    }


def score_features(f: dict[str, float], model: str) -> tuple[float, dict[str, float], float, list[str]]:
    """Explicit, untrained hypotheses; scores are not probabilities."""
    if model not in WEIGHTS:
        raise ValueError("Unsupported model")
    r20, r60, accel, dd = (f[k] for k in ("rel_20d_pct", "rel_60d_pct", "acceleration_pp", "drawdown_60d_pct"))
    risks: list[str] = []
    penalty = 0.0
    if model == "recovery":
        parts = {
            "neglect": _clip(55 - r60 * 3.5),
            "acceleration": _clip(50 + accel * 6),
            "recent_strength": _clip(50 + r20 * 5),
            "stability": _clip(100 - dd * 4),
        }
        # Recovery requires observable improvement, not merely deep weakness.
        # A stagnant loser must not rank highly just because its 60d return is bad.
        if accel < 1.5 or r20 <= -3:
            penalty += 24
            risks.append("相对改善尚未确认：近期强弱/加速度未达到门槛")
        if r60 > 10:
            penalty += 15
            risks.append("60日已相对跑赢较多：不属于低位修复阶段")
        if r20 < -5:
            penalty += 14
            risks.append("近20日持续弱势：可能不是修复")
        if r20 > 14:
            penalty += 12
            risks.append("近期过度反弹：可能已经拥挤")
        if r60 < -25:
            penalty += 10
            risks.append("长期相对弱势：存在价值陷阱可能")
    else:
        parts = {
            "strength_20d": _clip(50 + r20 * 5),
            "strength_60d": _clip(50 + r60 * 3),
            "consistency": _clip(75 - abs(r20 - r60 / 3) * 5),
            "stability": _clip(100 - dd * 4),
        }
        if r20 > 18:
            penalty += 12
            risks.append("短期过热：高位追涨风险")
        if r60 < 0:
            penalty += 9
            risks.append("60日相对趋势尚未确认")
    if dd > 25:
        penalty += 8
        risks.append("行业自高点回撤过大")
    rounded_parts = {k: round(v, 4) for k, v in parts.items()}
    score = _clip(sum(parts[k] * weight for k, weight in WEIGHTS[model].items()) - penalty)
    return round(score, 2), rounded_parts, round(penalty, 2), risks


def _fingerprint(as_of: date, benchmark: str, dates: list[str], prices: list[float],
                 sectors: list[dict[str, Any]], source: str) -> str:
    normalized = {
        "as_of": as_of.isoformat(), "benchmark": benchmark, "dates": dates,
        "prices": prices, "source": source,
        "sectors": [
            {
                "sector_id": sector["sector_id"],
                "sector_name": sector["sector_name"],
                "prices": [
                    {"date": point["date"].isoformat() if isinstance(point["date"], date) else str(point["date"]),
                     "close": float(point["close"])}
                    for point in sector["prices"]
                ],
            }
            for sector in sorted(sectors, key=lambda row: row["sector_id"])
        ],
    }
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_sectors(*, as_of: date, model: str, benchmark_id: str, benchmark: list[dict[str, Any]],
                     sectors: list[dict[str, Any]], source: str) -> dict[str, Any]:
    if model not in WEIGHTS:
        raise ValueError("Unsupported model")
    if source not in ("synthetic_demo", "manual_unverified"):
        raise ValueError("Source is not an accepted unverified data grade")
    dates = [p["date"].isoformat() if isinstance(p["date"], date) else str(p["date"]) for p in benchmark]
    prices = [float(p["close"]) for p in benchmark]
    rows: list[dict[str, Any]] = []
    for sector in sectors:
        closes = [float(p["close"]) for p in sector["prices"]]
        feats = features(closes, prices)
        score, breakdown, penalty, risk_flags = score_features(feats, model)
        rows.append({
            "sector_id": sector["sector_id"],
            "sector_name": sector["sector_name"],
            "status": "experimental",
            "score": score,
            "research_priority": "inspect" if score >= 70 else "watch",
            "features": feats,
            "factors": breakdown,
            "penalty_points": penalty,
            "risk_flags": risk_flags,
            "model_validation": "not_backtested",
            "evidence_grade": source,
        })
    rows.sort(key=lambda row: (-row["score"], row["sector_id"]))
    return {
        "model_version": VERSION, "model": model,
        "benchmark_id": benchmark_id, "as_of": as_of.isoformat(),
        "observations": len(dates), "sector_count": len(rows),
        "source_grade": source, "model_validation": "not_backtested",
        "validated_alpha": False, "input_sha256": _fingerprint(
            as_of, benchmark_id, dates, prices, sectors, source),
        "items": rows,
        "warning": "仅为实验性行业研究排序；来源未验证、无样本外收益证据，不构成股票推荐或买卖指令。",
    }
