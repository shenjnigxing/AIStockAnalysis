"""Public market adapters. No provider fallback, arbitrary URL or source promotion.

The returned source record is a *provider-transformed DataFrame row*, not signed
exchange data. Full timestamp (when present) is displayed update time, not
guaranteed exchange transaction time.
"""
from __future__ import annotations

from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo
import math
import os
import re
import urllib.parse
import urllib.request
import json
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
    "us_equity": {"source_id": "yfinance_yahoo_us_equity_1m", "asset_class": "us_equity",
                  "product_type": "common_stock", "metric": "bar_close", "unit": "USD/share",
                  "currency": "USD", "cooldown": 90},
    "us_etf": {"source_id": "yfinance_yahoo_us_etf_1m", "asset_class": "fund",
               "product_type": "us_etf", "metric": "bar_close", "unit": "USD/share",
               "currency": "USD", "cooldown": 120},
    "okx_stock_token": {"source_id": "okx_public_unified_tokenized_stock_spot", "asset_class": "tokenized_equity",
                        "product_type": "tokenized_stock", "metric": "last", "unit": "USDT/tokenized_share",
                        "currency": "USDT", "cooldown": 20},
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
    # Yahoo and OKX adapters must not require the domestic AKShare dependency.
    if kind in ("equity", "etf", "sge_gold", "futures", "treasury_10y"):
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
            rows = _frame_rows(ak.futures_zh_spot(symbol=symbol, market=("FF" if re.match(r"^[A-Z]+", symbol).group() in {"IF", "IH", "IC", "IM", "T", "TF", "TS", "TL"} else "CF"), adjust="0"), 10)
            if len(rows) != 1:
                raise PublicQuoteSourceError("Futures provider did not return one contract")
            row = rows[0]
            value = _number(_get(row, "current_price"))
            # The provider often sends only an HHMMSS clock or Chinese contract label.
            # Do not invent the exchange trading date or assert exact contract identity.
            display = str(row.get("time", "")).strip()
            source_at = None
            record = row
        elif kind in ("us_equity", "us_etf"):
            # Unofficial Yahoo source: research/personal data, NOT licensed consolidated SIP.
            import yfinance as yf
            frame = yf.Ticker(symbol).history(
                period="5d", interval="1m", prepost=True, auto_adjust=False)
            if frame is None or frame.empty:
                raise PublicQuoteSourceError("Yahoo returned no one-minute bars")
            if len(frame) > 5000:
                raise PublicQuoteSourceError("Unexpectedly large Yahoo quote response")
            final = frame.iloc[-1]
            index_ts = frame.index[-1]
            if index_ts.tzinfo is None:
                raise PublicQuoteSourceError("Yahoo bar lacks timezone")
            at = index_ts.to_pydatetime() if hasattr(index_ts, "to_pydatetime") else index_ts
            value = _number(final["Close"])
            display = at.isoformat()
            source_at = at
            record = {"symbol": symbol, "bar_start": display, "bar_interval": "1m",
                      "close": value, "prepost_included": True,
                      "session": "regular_or_extended_not_individually_verified"}
        elif kind == "okx_stock_token":
            # Fixed public endpoint, tokenized assets are not common-share ownership.
            if not re.fullmatch(r"X[A-Z]{1,10}-USDT", symbol):
                raise PublicQuoteSourceError("Unexpected tokenized stock symbol")
            # Official public instruments endpoint classifies stocks with instCategory=3.
            # A leading X alone does not prove that the asset is a tokenized equity.
            instrument_query = urllib.parse.urlencode({"instType": "SPOT", "instId": symbol})
            instrument_req = urllib.request.Request(
                "https://www.okx.com/api/v5/public/instruments?" + instrument_query,
                headers={"Accept": "application/json", "User-Agent": "AIStock-Research/0.1"})
            with urllib.request.urlopen(instrument_req, timeout=4) as response:
                instruments = json.load(response)
            listed = instruments.get("data", [])
            if instruments.get("code") != "0" or len(listed) != 1:
                raise PublicQuoteSourceError("OKX stock instrument was not verified")
            contract = listed[0]
            if (contract.get("instId") != symbol or contract.get("instType") != "SPOT"
                    or str(contract.get("instCategory")) != "3"
                    or contract.get("state") != "live"):
                raise PublicQuoteSourceError("Not a listed live stock-token SPOT instrument")
            query = urllib.parse.urlencode({"instId": symbol})
            req = urllib.request.Request(
                "https://www.okx.com/api/v5/market/ticker?" + query,
                headers={"Accept": "application/json", "User-Agent": "AIStock-Research/0.1"})
            with urllib.request.urlopen(req, timeout=4) as response:
                payload = json.load(response)
            if payload.get("code") != "0" or len(payload.get("data", [])) != 1:
                raise PublicQuoteSourceError("OKX ticker unavailable")
            row = payload["data"][0]
            if row.get("instId") != symbol or row.get("instType") != "SPOT":
                raise PublicQuoteSourceError("OKX returned unexpected instrument")
            value = _number(_get(row, "last"))
            millis = int(_get(row, "ts"))
            source_at = datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
            display = source_at.isoformat()
            record = {k: row.get(k) for k in
                      ("instId", "instType", "last", "bidPx", "askPx", "ts")}
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
        "time_quality": ("bar_timestamp" if kind in ("us_equity", "us_etf") else "provider_update_timestamp") if source_at else (
            "daily_observation" if kind == "treasury_10y" else "time_unverified"),
        "source_record": record,
    }
