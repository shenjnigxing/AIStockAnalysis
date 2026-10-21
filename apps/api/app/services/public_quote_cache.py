"""Persistent read-side quote cache and controlled, hard-deadline refresh.

The latest public provider snapshot is never PIT-verified or trade-eligible.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import math
import multiprocessing
import os
import re
import threading
import time
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import PublicQuoteSnapshot, PublicQuoteFetchAttempt
from app.services.public_quote_sources import SOURCES, PublicQuoteSourceError, fetch_public_quote


REFRESH_LOCK = threading.Lock()
HARD_TIMEOUT_SECONDS = 12
VALID_PATTERNS = {
    "equity": r"^[0-9]{6}$",
    "etf": r"^[0-9]{6}$",
    "sge_gold": r"^(Au99\.99|Au99\.95|Ag99\.99)$",
    "futures": r"^[A-Z]{1,2}[0-9]{3,4}$",
    "treasury_10y": r"^CN10Y$",
    "us_equity": r"^[A-Z]{1,5}(?:[.-][A-Z])?$",
    "us_etf": r"^[A-Z]{1,5}$",
    "okx_stock_token": r"^X[A-Z]{1,10}-USDT$",
}


class QuoteBusy(RuntimeError):
    pass


class QuoteUnavailable(RuntimeError):
    pass


class QuoteIntegrityError(RuntimeError):
    pass


def validate_identity(kind: str, symbol: str) -> None:
    pattern = VALID_PATTERNS.get(kind)
    if pattern is None or re.fullmatch(pattern, symbol) is None:
        raise ValueError("Unsupported kind or instrument code")
    if kind == "equity" and symbol[0] not in "03468":
        raise ValueError("Unrecognized equity code prefix")
    if kind == "etf" and symbol[0] not in "15":
        raise ValueError("Unrecognized ETF code prefix")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      default=str, separators=(",", ":"))


def _sha(data: str) -> str:
    return sha256(data.encode("utf-8")).hexdigest()


def _quote_worker(connection: Any, kind: str, symbol: str) -> None:
    try:
        result = fetch_public_quote(kind, symbol)
        connection.send(("ok", result))
    except Exception:
        # Do not relay exception details, URLs or provider environment values.
        connection.send(("error", "provider_failed"))
    finally:
        connection.close()


def fetch_supervised(kind: str, symbol: str) -> dict[str, Any]:
    """Child process provides a true wall-clock deadline, including stuck HTTP calls.

    Spawn works across Windows/Linux. Production should use a dedicated worker pool
    rather than launching a new process for every collection.
    """
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_quote_worker, args=(child, kind, symbol), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(HARD_TIMEOUT_SECONDS):
            raise QuoteUnavailable("provider_timeout")
        try:
            state, result = parent.recv()
        except (EOFError, OSError) as exc:
            raise QuoteUnavailable("provider_worker_crashed") from exc
        if state != "ok":
            raise QuoteUnavailable("provider_failed")
        if not isinstance(result, dict):
            raise QuoteUnavailable("provider_invalid_response")
        return result
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        parent.close()


def _last(db: Session, kind: str, symbol: str) -> PublicQuoteSnapshot | None:
    return db.scalar(select(PublicQuoteSnapshot).where(
        PublicQuoteSnapshot.kind == kind, PublicQuoteSnapshot.symbol == symbol
    ).order_by(PublicQuoteSnapshot.id.desc()).limit(1))


def _last_attempt(db: Session, kind: str, symbol: str) -> PublicQuoteFetchAttempt | None:
    return db.scalar(select(PublicQuoteFetchAttempt).where(
        PublicQuoteFetchAttempt.kind == kind, PublicQuoteFetchAttempt.symbol == symbol
    ).order_by(PublicQuoteFetchAttempt.id.desc()).limit(1))


def _verify(row: PublicQuoteSnapshot) -> None:
    """Detect accidental data/metadata edits before a cache value is exposed."""
    spec = SOURCES.get(row.kind)
    if not spec or row.source_id != spec["source_id"] or row.asset_class != spec["asset_class"] or row.product_type != spec["product_type"]:
        raise QuoteIntegrityError("Quote source identity changed")
    if row.metric != spec["metric"] or row.unit != spec["unit"] or row.currency != spec["currency"]:
        raise QuoteIntegrityError("Quote metric or units changed")
    if _sha(row.source_record_json) != row.source_record_sha256:
        raise QuoteIntegrityError("Provider record content changed")
    payload = {
        "kind": row.kind, "symbol": row.symbol, "source_id": row.source_id,
        "metric": row.metric, "unit": row.unit, "currency": row.currency,
        "value": row.value, "source_display_time": row.source_display_time,
        "source_timestamp_utc": row.source_timestamp_utc.isoformat() if row.source_timestamp_utc else None,
        "source_record_sha256": row.source_record_sha256,
    }
    if _sha(_canonical(payload)) != row.observation_sha256:
        raise QuoteIntegrityError("Quote observation changed")


def _output(row: PublicQuoteSnapshot, now: datetime) -> dict[str, Any]:
    _verify(row)
    age = max(0, (now - row.collected_at_utc).total_seconds())
    threshold = SOURCES[row.kind]["cooldown"] * 3
    source_age = None
    if row.source_timestamp_utc is not None:
        source_age = max(0, int((now - row.source_timestamp_utc).total_seconds()))
    freshness = (
        "stale_cache" if age > threshold else
        "stale_source" if source_age is not None and source_age > max(threshold, 300) else
        "time_unverified" if row.time_quality == "time_unverified" else
        "daily_observation" if row.time_quality == "daily_observation" else
        "bar_timestamped" if row.time_quality == "bar_timestamp" else "provider_timestamped"
    )
    return {
        "id": row.id, "kind": row.kind, "symbol": row.symbol,
        "source_id": row.source_id, "asset_class": row.asset_class,
        "product_type": row.product_type, "metric": row.metric,
        "value": row.value, "currency": row.currency, "unit": row.unit,
        "collected_at_utc": row.collected_at_utc.isoformat() + "Z",
        "source_display_time": row.source_display_time,
        "source_timestamp_utc": row.source_timestamp_utc.isoformat() + "Z"
                                if row.source_timestamp_utc else None,
        "time_quality": row.time_quality, "source_age_seconds": source_age,
        "cache_age_seconds": int(age), "request_duration_ms": row.request_duration_ms,
        "freshness": freshness,
        "source_record_sha256": row.source_record_sha256,
        "observation_sha256": row.observation_sha256,
        "research_eligible": False, "can_trade": False, "can_deliver": False,
        "warning": "Unverified public quote; collection time is NOT market-time latency and the value is not a tradeable recommendation.",
    }


def cached_quote(db: Session, *, kind: str, symbol: str) -> dict[str, Any] | None:
    validate_identity(kind, symbol)
    item = _last(db, kind, symbol)
    return _output(item, _now()) if item else None


def quote_status(db: Session) -> dict[str, Any]:
    result = []
    for kind, spec in SOURCES.items():
        row = db.scalar(select(PublicQuoteSnapshot).where(
            PublicQuoteSnapshot.kind == kind).order_by(PublicQuoteSnapshot.id.desc()).limit(1))
        result.append({
            "kind": kind, "source_id": spec["source_id"],
            "metric": spec["metric"], "cooldown_seconds": spec["cooldown"],
            "has_cached_snapshot": row is not None,
            "last_collected_at_utc": row.collected_at_utc.isoformat() + "Z" if row else None,
        })
    return {"providers": result, "provider_verified": False,
            "research_eligible": False, "notifications_enabled": False,
            "note": "Quote cache is read-only for users; updates require server administration."}


def refresh_quote(db: Session, *, kind: str, symbol: str) -> dict[str, Any]:
    validate_identity(kind, symbol)
    if os.getenv("MARKET_DATA_MODE", "real").strip().lower() != "real":
        raise QuoteUnavailable("real_provider_only")
    if not REFRESH_LOCK.acquire(blocking=False):
        raise QuoteBusy("another_quote_refresh_active")
    start = time.monotonic()
    try:
        now = _now()
        latest = _last(db, kind, symbol)
        last_attempt = _last_attempt(db, kind, symbol)
        newest = max(
            (x for x in (latest.collected_at_utc if latest else None,
                         last_attempt.attempted_at_utc if last_attempt else None) if x), default=None)
        if newest and (now - newest).total_seconds() < SOURCES[kind]["cooldown"]:
            if latest:
                return {"cached": True, "quote": _output(latest, now),
                        "cooldown_seconds": SOURCES[kind]["cooldown"]}
            raise QuoteBusy("cooldown_after_recent_failure")
        try:
            data = fetch_supervised(kind, symbol)
            spec = SOURCES[kind]
            value = float(data["value"])
            if not (0 < value < 1_000_000_000) or not math.isfinite(value):
                raise QuoteUnavailable("invalid_quote_value")
            source_at = data.get("source_timestamp_utc")
            if source_at is not None and (not isinstance(source_at, datetime)
                                          or source_at > now + timedelta(minutes=2)):
                raise QuoteUnavailable("invalid_source_time")
            quality = data["time_quality"]
            if quality not in ("time_unverified", "daily_observation", "provider_update_timestamp", "bar_timestamp"):
                raise QuoteUnavailable("unknown_timestamp_quality")
            source_text = str(data.get("source_display_time", ""))[:96]
            record = _canonical(data["source_record"])
            if len(record.encode("utf-8")) > 32_000:
                raise QuoteUnavailable("oversized_source_record")
            source_hash = _sha(record)
            payload = {
                "kind": kind, "symbol": symbol, "source_id": spec["source_id"],
                "metric": spec["metric"], "unit": spec["unit"], "currency": spec["currency"],
                "value": value, "source_display_time": source_text,
                "source_timestamp_utc": source_at.isoformat() if source_at else None,
                "source_record_sha256": source_hash,
            }
            duration = max(0, int((time.monotonic() - start) * 1000))
            row = PublicQuoteSnapshot(
                kind=kind, symbol=symbol, source_id=spec["source_id"],
                asset_class=spec["asset_class"], product_type=spec["product_type"],
                metric=spec["metric"], value=value, unit=spec["unit"],
                currency=spec["currency"], collected_at_utc=_now(),
                source_display_time=source_text, source_timestamp_utc=source_at,
                time_quality=quality, request_duration_ms=duration,
                source_record_sha256=source_hash, source_record_json=record,
                observation_sha256=_sha(_canonical(payload)),
            )
            db.add(row)
            db.add(PublicQuoteFetchAttempt(
                kind=kind, symbol=symbol, attempted_at_utc=now,
                duration_ms=duration, state="success", error_code=""))
            db.commit()
            return {"cached": False, "quote": _output(row, _now()),
                    "cooldown_seconds": spec["cooldown"]}
        except Exception as exc:
            db.rollback()
            duration = max(0, int((time.monotonic() - start) * 1000))
            db.add(PublicQuoteFetchAttempt(
                kind=kind, symbol=symbol, attempted_at_utc=now,
                duration_ms=duration, state="failure",
                error_code=(str(exc) if isinstance(exc, QuoteUnavailable) else "provider_failed")[:64]))
            db.commit()
            raise QuoteUnavailable("refresh_failed") from exc
    finally:
        REFRESH_LOCK.release()
