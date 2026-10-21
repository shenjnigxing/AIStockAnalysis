"""Public market adapters. No provider fallback, arbitrary URL or source promotion.

The returned source record is a *provider-transformed DataFrame row*, not signed
exchange data. Full timestamp (when present) is displayed update time, not
guaranteed exchange transaction time.
"""
from __future__ import annotations

from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import math
import os
from typing import Any

SHANGHAI = ZoneInfo("Asia/Shanghai")


class PublicQuoteSourceError(RuntimeError):
    pass


SOURCES = {
    "equity": {"source_id": "akshare_eastmoney_stock_bid_ask_em", "asset_class": "equity",
               "product_type": "common_stock", "metric": "price", "unit": "CNY/share",
               "currency": "CNY", "cooldown": 45},
    "etf": {"source_id": "akshare_eastmoney_fund_etf_spot_em", "asset_class": "fund",
            "product_type": "etf", "metric": "price", "unit": "CNY/share",
            "currency": "CNY", "cooldown": 90},
    "sge_gold": {"source_id": "akshare_sge_spot_quotations_sge", "asset_class": "precious_metal",
                 "product_type": "exchange_spot", "metric": "price", "unit": "CNY/g",
                 "currency": "CNY", "cooldown": 60},
    "futures": {"source_id": "akshare_sina_futures_zh_spot", "asset_class": "futures",
                "product_type": "contract", "metric": "price", "unit": "contract_quote",
                "currency": "CNY", "cooldown": 30},
    "treasury_10y": {"source_id": "akshare_sina_bond_gb_zh_sina", "asset_class": "treasury",
                     "product_type": "yield_curve_point", "metric": "yield_pct", "unit": "%",
                     "currency": "CNY", "cooldown": 3600},
}


def _number(value: Any) -> float:
    try:
        val = float(str(value).replace(",", "").strip())
    except (ValueError, TypeError, OverflowError) as exc:
        raise PublicQuoteSourceError("Source missing numeric price or yield") from exc
    if not math.isfinite(val) or val <= 0:
        raise PublicQuoteSourceError("Non-finite/nonpositive price or yield")
    return val


def _get(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and str(row[key]).strip() not in ("", "None", "nan", "NaN", "--", "-"):
            return row[key]
    raise PublicQuoteSourceError("Required source fields missing")


def _frame_rows(frame: Any, max_rows: int = 20000) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        raise PublicQuoteSourceError("Public provider returned no observations")
    if len(frame) > max_rows:
        raise PublicQuoteSourceError("Unexpectedly large source response")
    return [dict(v) for _, v in frame.iterrows()]


def _parse_display_update(text: str, *, day: str | None = None) -> datetime | None:
    """Only complete source-displayed date/time can produce a timestamp."""
    raw = str(text).strip().replace("年", "-").replace("月", "-").replace("日", "")
    if day and len(raw) <= 8:
        raw = f"{day} {raw}"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # A date-only value does NOT establish an exact quote update instant.
    if ":" not in raw:
        return None
    return parsed.replace(tzinfo=SHANGHAI) if parsed.tzinfo is None else parsed


def _choose(symbol: str, rows: list[dict[str, Any]], *, code_keys: tuple[str, ...]) -> dict[str, Any]:
    matched = []
    for row in rows:
        code = next((str(row[k]).strip() for k in code_keys if k in row), None)
        if code is not None and code.zfill(6) == symbol:
            matched.append(row)
    if len(matched) != 1:
        raise PublicQuoteSourceError("Source returned missing or ambiguous instrument identity")
    return matched[0]


def fetch_public_quote(kind: str, symbol: str) -> dict[str, Any]:
    """Fetch and normalize ONE observation (no implicit request retries).

    An outer multiprocessing supervisor terminates this function at its hard timeout.
    """
    if os.getenv("MARKET_DATA_MODE", "real").strip().lower() != "real":
        raise PublicQuoteSourceError("Mock data mode may not publish public quotes")
    try:
        import akshare as ak
    except ImportError as exc:
        raise PublicQuoteSourceError("AKShare not installed") from exc
    try:
        if kind == "equity":
            frame = ak.stock_bid_ask_em(symbol=symbol)
            pairs = _frame_rows(frame, 80)
            values = {}
            for pair in pairs:
                label = str(_get(pair, "item", "项目"))
                values[label] = _get(pair, "value", "数值")
            value = _number(_get(values, "最新", "最新价", "最新成交价"))
            record = {"field": "latest", "provider_fields": values}
            display = ""
            source_at = None
        elif kind == "etf":
            row = _choose(symbol, _frame_rows(ak.fund_etf_spot_em()),
                          code_keys=("代码", "基金代码"))
            value = _number(_get(row, "最新价"))
            day = str(row.get("数据日期", "")).strip()
            update = str(row.get("更新时间", "")).strip()
            display = (day + " " + update).strip()
            source_at = _parse_display_update(update, day=day or None)
            record = row
        elif kind == "sge_gold":
            rows = _frame_rows(ak.spot_quotations_sge(symbol=symbol), 2000)
            valid = [r for r in rows if str(r.get("品种", "")).strip() == symbol]
            if not valid:
                raise PublicQuoteSourceError("SGE returned unexpected instrument")
            row = valid[-1]
            value = _number(_get(row, "现价"))
            display = str(row.get("更新时间", "")).strip()
            source_at = _parse_display_update(display)
            record = row
        elif kind == "futures":
            rows = _frame_rows(ak.futures_zh_spot(symbol=symbol, market="CF", adjust="0"), 10)
            if len(rows) != 1:
                raise PublicQuoteSourceError("Futures provider did not return one contract")
            row = rows[0]
            value = _number(_get(row, "current_price"))
            # The provider often sends only an HHMMSS clock or Chinese contract label.
            # Do not invent the exchange trading date or assert exact contract identity.
            display = str(row.get("time", "")).strip()
            source_at = None
            record = row
        elif kind == "treasury_10y":
            if symbol != "CN10Y":
                raise PublicQuoteSourceError("Only CN10Y is supported")
            rows = _frame_rows(ak.bond_gb_zh_sina(symbol="中国10年期国债"), 1500)
            rows.sort(key=lambda r: str(r.get("date", "")))
            row = rows[-1]
            display = str(_get(row, "date"))
            if date.fromisoformat(display) > date.today():
                raise PublicQuoteSourceError("Future yield observation")
            value = _number(_get(row, "close"))
            source_at = None
            record = row
        else:
            raise PublicQuoteSourceError("Unsupported source kind")
    except PublicQuoteSourceError:
        raise
    except Exception as exc:
        raise PublicQuoteSourceError("Public source unavailable or response changed") from exc
    # Bound storage size, avoid persisting entire ETF universe or API debug fields.
    return {
        "value": value,
        "source_display_time": display[:96],
        "source_timestamp_utc": source_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None) if source_at else None,
        "time_quality": "provider_update_timestamp" if source_at else (
            "daily_observation" if kind == "treasury_10y" else "time_unverified"),
        "source_record": record,
    }
