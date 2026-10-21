"""A narrow R1 provider registry: only explicit AKShare/Eastmoney daily endpoints.

Provider evidence is NOT point-in-time verification of historical observability.
No legacy mock fallback, arbitrary URL, user-supplied provenance or background jobs.
"""
from __future__ import annotations

from datetime import date
import os
from typing import Any


class UpstreamDataError(ValueError):
    pass


REGISTRY: dict[str, dict[str, str]] = {
    "equity": {
        "source_id": "akshare_eastmoney_equity_daily",
        "method": "stock_zh_a_hist",
        "asset_class": "equity",
        "product_type": "common_stock",
        "volume_unit": "source_reported_lots",
    },
    "etf": {
        "source_id": "akshare_eastmoney_etf_daily",
        "method": "fund_etf_hist_em",
        "asset_class": "fund",
        "product_type": "etf",
        "volume_unit": "source_reported_lots",
    },
}


def fetch_akshare_daily(kind: str, symbol: str, start: date, end: date) -> tuple[str, list[dict[str, Any]]]:
    """Return a provider-returned tabular snapshot string and normalized records.

    The snapshot is serialized from the DataFrame, NOT original HTTP response bytes.
    """
    if os.getenv("MARKET_DATA_MODE", "real").strip().lower() != "real":
        raise UpstreamDataError("Real provider mode required; mock mode cannot publish a release")
    spec = REGISTRY.get(kind)
    if spec is None:
        raise UpstreamDataError("Unsupported fixed provider type")
    try:
        import akshare as ak
    except ImportError as exc:
        raise UpstreamDataError("AKShare unavailable") from exc

    func = getattr(ak, spec["method"], None)
    if func is None:
        raise UpstreamDataError("Provider method unavailable")
    try:
        df = func(symbol=symbol, period="daily", start_date=start.strftime("%Y%m%d"),
                  end_date=end.strftime("%Y%m%d"), adjust="")
    except Exception as exc:
        raise UpstreamDataError("Upstream provider failed, no fallback permitted") from exc
    if df is None or df.empty:
        raise UpstreamDataError("Provider returned no daily bars")
    required = {"日期", "开盘", "最高", "最低", "收盘", "成交量", "成交额"}
    if not required.issubset(set(df.columns)):
        raise UpstreamDataError("Provider schema changed: expected price columns missing")
    try:
        raw_json = df.to_json(orient="records", date_format="iso", force_ascii=False)
        records = []
        for _, row in df.iterrows():
            code = row.get("股票代码", row.get("代码"))
            if code is not None and str(code).strip() not in ("", symbol, str(int(symbol))):
                raise UpstreamDataError("Provider returned different symbol")
            parsed_date = date.fromisoformat(str(row["日期"]).split(" ")[0][:10])
            records.append({
                "obs_date": parsed_date, "open": float(row["开盘"]),
                "high": float(row["最高"]), "low": float(row["最低"]),
                "close": float(row["收盘"]), "volume": float(row["成交量"]),
                "amount": float(row["成交额"]),
            })
    except UpstreamDataError:
        raise
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise UpstreamDataError("Provider response could not be normalized") from exc
    return raw_json, records
