from datetime import date, datetime, timedelta

class AkshareMarketDataAdapter:
    def __init__(self) -> None:
        self._ak = None
        try:
            import akshare as ak  # type: ignore

            self._ak = ak
        except Exception:
            self._ak = None

    def fetch_stock_master(self) -> list[dict]:
        if self._ak is not None:
            try:
                df = self._ak.stock_zh_a_spot_em()
                if not df.empty:
                    return [
                        {
                            "symbol": str(row["代码"]).zfill(6),
                            "name": str(row["名称"]),
                            "market": "A",
                            "is_active": True,
                        }
                        for _, row in df.iterrows()
                    ]
            except Exception:
                pass
        return [
            {"symbol": "000001", "name": "PingAnBank", "market": "SZ", "is_active": True},
            {"symbol": "600000", "name": "SPDBank", "market": "SH", "is_active": True},
            {"symbol": "600519", "name": "KweichowMoutai", "market": "SH", "is_active": True},
        ]

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[dict]:
        if self._ak is not None:
            try:
                df = self._ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="",
                )
                if not df.empty:
                    return [
                        {
                            "symbol": symbol,
                            "trade_date": datetime.fromisoformat(str(row["日期"]).split(" ")[0]).date(),
                            "open": float(row["开盘"]),
                            "high": float(row["最高"]),
                            "low": float(row["最低"]),
                            "close": float(row["收盘"]),
                            "volume": float(row["成交量"]),
                            "amount": float(row["成交额"]),
                        }
                        for _, row in df.iterrows()
                    ]
            except Exception:
                pass
        rows = []
        cursor = start_date
        px = 10.0 + (int(symbol[-2:]) / 100)
        while cursor <= end_date:
            open_px = round(px, 2)
            close_px = round(px * 1.01, 2)
            high_px = round(max(open_px, close_px) * 1.01, 2)
            low_px = round(min(open_px, close_px) * 0.99, 2)
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": cursor,
                    "open": open_px,
                    "high": high_px,
                    "low": low_px,
                    "close": close_px,
                    "volume": 100000.0,
                    "amount": close_px * 100000.0,
                }
            )
            cursor += timedelta(days=1)
            px = close_px
        return rows

    def fetch_minute_bars(self, symbol: str, start_time: datetime, end_time: datetime) -> list[dict]:
        rows = []
        cursor = start_time.replace(second=0, microsecond=0)
        base_price = 10.0 + (int(symbol[-2:]) / 100)
        i = 0
        while cursor <= end_time:
            open_px = round(base_price + i * 0.01, 2)
            close_px = round(open_px + 0.01, 2)
            rows.append(
                {
                    "symbol": symbol,
                    "bar_time": cursor,
                    "open": open_px,
                    "high": round(close_px * 1.001, 2),
                    "low": round(open_px * 0.999, 2),
                    "close": close_px,
                    "volume": 1000.0,
                    "amount": close_px * 1000.0,
                }
            )
            cursor += timedelta(minutes=1)
            i += 1
        return rows

    def fetch_realtime_quotes(self, symbols: list[str]) -> list[dict]:
        now = datetime.utcnow().replace(microsecond=0)
        if self._ak is not None:
            try:
                df = self._ak.stock_zh_a_spot_em()
                if not df.empty:
                    mapped = df[df["代码"].astype(str).isin(symbols)] if symbols else df.head(50)
                    return [
                        {
                            "symbol": str(row["代码"]).zfill(6),
                            "quote_time": now,
                            "price": float(row["最新价"]) if row["最新价"] is not None else 0.0,
                            "change_pct": float(row["涨跌幅"]) if row["涨跌幅"] is not None else 0.0,
                            "volume": float(row["成交量"]) if row["成交量"] is not None else 0.0,
                            "amount": float(row["成交额"]) if row["成交额"] is not None else 0.0,
                        }
                        for _, row in mapped.iterrows()
                    ]
            except Exception:
                pass
        symbols = symbols or ["000001", "600000", "600519"]
        return [
            {
                "symbol": s,
                "quote_time": now,
                "price": 10.0 + idx,
                "change_pct": 0.5,
                "volume": 3000.0 + idx * 100.0,
                "amount": (10.0 + idx) * (3000.0 + idx * 100.0),
            }
            for idx, s in enumerate(symbols)
        ]
