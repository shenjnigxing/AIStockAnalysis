"""Run from the backend directory: python -m app.cli.market_data doctor|status|refresh.

Local operator CLI only. No HTTP admin token goes into a browser or shell
command line. It shares the same SQLite/DB URI as the API via Settings.
"""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.public_quote_cache import (
    QuoteBusy, QuoteUnavailable, QuoteIntegrityError,
    cached_quote, quote_status, refresh_quote, validate_identity,
)
from app.services.public_quote_sources import SOURCES


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not_installed"


def _describe_db() -> str:
    # Do not echo arbitrary connection URIs: these may contain DB credentials.
    if settings.database_url.startswith("sqlite"):
        return "本机 SQLite（文件路径已隐藏；可通过明确设置 DATABASE_URL 覆盖）"
    return "外部数据库（连接串/凭据不显示）"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.market_data",
        description="AIStock 本地数据诊断与受控刷新；无真实荐股/下单功能",
    )
    group = parser.add_subparsers(dest="operation", required=True)
    group.add_parser("doctor", help="检查本机依赖、数据源配置和缓存，不访问互联网")
    status = group.add_parser("status", help="查看指定标的已存缓存，不抓取外网")
    status.add_argument("--kind", required=True, choices=tuple(SOURCES))
    status.add_argument("--symbol", required=True)
    refresh = group.add_parser("refresh", help="明确触发一次公开行情抓取（可能联网）")
    refresh.add_argument("--kind", required=True, choices=tuple(SOURCES))
    refresh.add_argument("--symbol", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # This is intentionally restricted to local/operator invocation. A web user
    # must not be able to call it: only refresh API is gated by a server token.
    if args.operation in ("status", "refresh"):
        try:
            validate_identity(args.kind, args.symbol)
        except ValueError:
            print("输入错误：不支持的资产类型或代码", file=sys.stderr)
            return 2
    try:
        init_db()
        with SessionLocal() as db:
            if args.operation == "doctor":
                snapshot = quote_status(db)
                report = {
                    "application": "AIStock R1.2 local smoke",
                    "database": _describe_db(),
                    "market_data_mode": os.getenv("MARKET_DATA_MODE", "real"),
                    "akshare": _package_version("akshare"),
                    "yfinance": _package_version("yfinance"),
                    "providers": [
                        {"kind": p["kind"], "has_cached_snapshot": p["has_cached_snapshot"],
                         "cooldown_seconds": p["cooldown_seconds"]}
                        for p in snapshot["providers"]
                    ],
                    "can_generate_real_recommendations": False,
                    "broker_accounts_connected": False,
                }
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            if args.operation == "status":
                result = cached_quote(db, kind=args.kind, symbol=args.symbol)
                if result is None:
                    print("未发现本地行情缓存。先用 refresh 命令联网采集，或者更换标的。", file=sys.stderr)
                    return 3
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            result = refresh_quote(db, kind=args.kind, symbol=args.symbol)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except (QuoteBusy, QuoteUnavailable, QuoteIntegrityError) as exc:
        # Operator errors use bounded, normalized error types and no token dump.
        print("采集或校验失败：{}".format(type(exc).__name__), file=sys.stderr)
        return 4
    except Exception as exc:
        # Do not print traceback/DB URI, which may contain private credentials.
        print("本地服务初始化或存储失败：{}".format(type(exc).__name__), file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
