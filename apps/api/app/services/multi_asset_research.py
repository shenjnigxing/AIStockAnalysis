"""V3 multi-asset *experimental* research. Pure, offline, deterministic.

These scores are hypothesis diagnostics, NOT validated alpha, investment advice,
price targets, probabilities, or instructions to trade. Never send orders or alerts.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json
import math
from typing import Any

VERSION = "multi-asset-research-0.1.0"
ASSET_CLASSES = ("equity", "precious_metal", "fund", "futures", "treasury")
HORIZONS = ("short", "medium_long")
SOURCES = ("synthetic_demo", "manual_unverified")


def _clip(n: float) -> float:
    return max(0.0, min(100.0, n))


def _pct(values: list[float], window: int) -> float:
    return 100 * (values[-1] / values[-window - 1] - 1)


def _volatility(values: list[float]) -> float:
    returns = [values[i] / values[i-1] - 1 for i in range(len(values)-20, len(values))]
    average = sum(returns) / len(returns)
    return 100 * math.sqrt(sum((r - average) ** 2 for r in returns) / len(returns))


def _features(values: list[float]) -> dict[str, float]:
    peak = max(values[-61:])
    return {
        "return_5_pct": round(_pct(values, 5), 6),
        "return_20_pct": round(_pct(values, 20), 6),
        "return_60_pct": round(_pct(values, 60), 6) if len(values) >= 61 else None,
        "return_120_pct": round(_pct(values, 120), 6) if len(values) >= 121 else None,
        "realized_volatility_20_pct_per_obs": round(_volatility(values), 6),
        "drawdown_60_pct": round(max(0.0, 100 * (1 - values[-1] / peak)), 6),
    }


def _base_score(f: dict[str, float], horizon: str) -> tuple[float, dict[str, float]]:
    if horizon == "short":
        terms = {
            "trend_5": _clip(50 + f["return_5_pct"] * 7),
            "trend_20": _clip(50 + f["return_20_pct"] * 3),
            "stability": _clip(100 - f["realized_volatility_20_pct_per_obs"] * 12),
            "drawdown_control": _clip(100 - f["drawdown_60_pct"] * 3),
        }
        weights = {"trend_5": .35, "trend_20": .30, "stability": .20, "drawdown_control": .15}
    else:
        terms = {
            "trend_20": _clip(50 + f["return_20_pct"] * 2),
            "trend_60": _clip(50 + f["return_60_pct"] * 1.5),
            "trend_120": _clip(50 + f["return_120_pct"] * .85),
            "stability": _clip(100 - f["realized_volatility_20_pct_per_obs"] * 14),
            "drawdown_control": _clip(100 - f["drawdown_60_pct"] * 3),
        }
        weights = {"trend_20": .20, "trend_60": .25, "trend_120": .20, "stability": .20, "drawdown_control": .15}
    return sum(terms[k] * w for k, w in weights.items()), {k: round(v, 2) for k, v in terms.items()}


def _asset_risks(item: dict[str, Any], as_of: date) -> tuple[float, list[str], list[str]]:
    cls, kind = item["asset_class"], item["product_type"]
    meta = item["metadata"]
    penalty, warnings, blocks = 0.0, [], []
    if cls == "equity":
        if meta["is_st"] or meta["suspended"]:
            blocks.append("ST/停牌证券不能进入研究候选")
        if meta["turnover_amount_yi"] < .3:
            penalty += 18
            warnings.append("日均成交额过低，实际执行成本可能很高")
    elif cls == "precious_metal":
        if kind == "bank_paper":
            spread = meta["bid_ask_spread_bps"]
            penalty += min(30, spread / 5)
            if spread > 150:
                blocks.append("纸贵金属报价买卖价差过大")
            warnings.append("纸贵金属报价不等于交易所现货，需核对银行产品规则")
        if kind == "leveraged_deferred":
            blocks.append("贵金属延期合约暂未经过保证金与强平模型验证")
    elif cls == "fund":
        if kind == "open_end":
            released = meta["nav_published_on"]
            latest = item["prices"][-1]["date"]
            if released < latest or released > as_of:
                blocks.append("基金净值披露日期不符合研究时点")
            elif (as_of - released).days > 10:
                blocks.append("场外基金净值超过10个自然日未更新")
            warnings.append("场外基金净值不是可交易的盘中实时成交价")
        else:
            premium = meta["premium_discount_pct"]
            if abs(premium) > 4:
                penalty += 15
                warnings.append("场内基金折溢价过高")
        if meta["annual_fee_pct"] > 2:
            penalty += 10
            warnings.append("基金综合费率偏高")
    elif cls == "futures":
        days = (meta["expiry"] - as_of).days
        if days <= 10:
            blocks.append("期货合约临近到期或已到期，禁止生成候选")
        blocks.append("期货尚无头寸、账户权益与压力损失模型，暂不生成研究候选")
        if kind == "continuous":
            blocks.append("连续主力价格不能作为实际可交易合约")
        # Margin percentage alone is not a monotonic measure of position risk.
        warnings.append("期货存在杠杆、逐日盯市、移仓及跳空强平风险，未计入真实成本")
    elif cls == "treasury":
        duration = meta["modified_duration"]
        if duration > 7:
            penalty += 12
            warnings.append("长久期国债对利率上行敏感")
        warnings.append("当前仅为价格趋势实验，国债实际总回报需计入票息、应计利息与到期现金流")
    return penalty, warnings, blocks


def evaluate_multi_asset(*, as_of: date, horizon: str, source: str, instruments: list[dict[str, Any]]) -> dict[str, Any]:
    if horizon not in HORIZONS or source not in SOURCES:
        raise ValueError("Unsupported research horizon or source")
    minimum = 26 if horizon == "short" else 121
    seen: set[tuple[str, str, str]] = set()
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in instruments:
        cls, kind, currency = item["asset_class"], item["product_type"], item["currency"]
        if cls not in ASSET_CLASSES:
            raise ValueError("Unknown asset class")
        ident = (cls, item["symbol"], kind)
        if ident in seen:
            raise ValueError("Duplicate instrument")
        seen.add(ident)
        if len(item["prices"]) < minimum:
            raise ValueError("Insufficient point-in-time observations for selected horizon")
        values = [point["close"] for point in item["prices"]]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Close prices must be positive and finite")
        factors = _features(values)
        raw, components = _base_score(factors, horizon)
        penalty, warnings, blocks = _asset_risks(item, as_of)
        if factors["realized_volatility_20_pct_per_obs"] > 5:
            penalty += 10
            warnings.append("近期单观测收益波动较高")
        row = {
            "symbol": item["symbol"], "name": item["name"],
            "asset_class": cls, "product_type": kind, "currency": currency,
            "status": "blocked" if blocks else "experimental",
            "research_priority": "blocked" if blocks else "inspect" if raw - penalty >= 70 else "watch",
            "score": None if blocks else round(_clip(raw - penalty), 2),
            "features": factors, "components": components,
            "penalty_points": round(penalty, 2), "risk_flags": warnings,
            "blocked_reasons": blocks,
            "source_grade": source,
            "validated_alpha": False,
        }
        if cls == "treasury":
            row["rate_up_50bps_price_sensitivity_pct"] = round(-item["metadata"]["modified_duration"] * 0.5, 2)
        # Comparable ONLY within the same class, vehicle and currency and horizon.
        groups.setdefault((cls, kind, currency), []).append(row)
    data = {"as_of": as_of.isoformat(), "horizon": horizon, "source": source, "instruments": [
        {**item, "prices": [{"date": p["date"].isoformat(), "close": p["close"]} for p in item["prices"]],
         "metadata": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in item["metadata"].items()}}
        for item in sorted(instruments, key=lambda i: (i["asset_class"], i["product_type"], i["symbol"]))
    ]}
    digest = sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
    results = []
    for (cls, kind, currency), rows in sorted(groups.items()):
        rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0), row["symbol"]))
        results.append({"asset_class": cls, "product_type": kind, "currency": currency, "items": rows})
    return {
        "model_version": VERSION, "horizon": horizon, "as_of": as_of.isoformat(),
        "source_grade": source, "validated_alpha": False,
        "model_validation": "not_backtested", "can_trade": False,
        "can_deliver": False, "input_sha256": digest, "groups": results,
        "count": len(instruments),
        "warning": "数据未验证、策略未做样本外与成本检验；不同资产/币种/交易载体不做跨组分数排名，不构成买卖指令。",
    }
