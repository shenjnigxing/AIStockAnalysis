"""Bounded public quote collection: python -m app.cli.quotes --help."""
import argparse
import json
import time
from pathlib import Path

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.public_quote_cache import (
    QuoteBusy, QuoteUnavailable, QuoteIntegrityError, refresh_quote, validate_identity,
)


def load_watchlist(path: Path) -> list[tuple[str, str]]:
    if path.stat().st_size > 16_384:
        raise ValueError("Watchlist exceeds 16 KiB")
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
        raise ValueError("Watchlist must contain 1 to 30 instruments")
    result = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"kind", "symbol"}:
            raise ValueError("Each watchlist item needs only kind and symbol")
        kind, symbol = row["kind"], row["symbol"]
        if not isinstance(kind, str) or not isinstance(symbol, str):
            raise ValueError("Instrument kind and symbol must be strings")
        validate_identity(kind, symbol)
        if (kind, symbol) in result:
            raise ValueError("Duplicate watchlist instrument")
        result.append((kind, symbol))
    return result


def collect_once(items: list[tuple[str, str]]) -> int:
    failures = 0
    for kind, symbol in items:
        with SessionLocal() as db:
            try:
                result = refresh_quote(db, kind=kind, symbol=symbol)
                print(json.dumps({"kind": kind, "symbol": symbol, "state": "cached" if result["cached"] else "collected",
                                  "quote": result["quote"]}, ensure_ascii=True), flush=True)
            except (QuoteBusy, QuoteUnavailable, QuoteIntegrityError) as exc:
                failures += 1
                print(json.dumps({"kind": kind, "symbol": symbol, "state": "unavailable",
                                  "error": type(exc).__name__}), flush=True)
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect real public quotes into the local cache; no account or browser token needed.")
    parser.add_argument("--watchlist", type=Path, help="JSON array of kind/symbol objects, at most 30")
    parser.add_argument("--kind")
    parser.add_argument("--symbol")
    parser.add_argument("--interval", type=int, default=0, help="Seconds between cycles; 0 runs once, otherwise 20..86400")
    parser.add_argument("--cycles", type=int, default=1, help="Finite cycles (1..10000); Ctrl+C stops early")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.cycles <= 10000 or (args.interval != 0 and not 20 <= args.interval <= 86400):
            raise ValueError("Invalid cycle count or interval")
        if args.cycles > 1 and args.interval == 0:
            raise ValueError("Multiple cycles require --interval")
        if args.watchlist:
            if args.kind or args.symbol:
                raise ValueError("Choose watchlist OR kind/symbol")
            items = load_watchlist(args.watchlist)
        else:
            if not args.kind or not args.symbol:
                raise ValueError("Provide --watchlist or both --kind and --symbol")
            validate_identity(args.kind, args.symbol)
            items = [(args.kind, args.symbol)]
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    init_db()
    failures = 0
    try:
        for cycle in range(args.cycles):
            failures += collect_once(items)
            if cycle + 1 < args.cycles:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
