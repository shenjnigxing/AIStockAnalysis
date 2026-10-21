"""R1 append-only release store, full-batch validation and independently checkable hashes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DatasetPriceObservation, DatasetRelease
from app.services.dataset_sources import REGISTRY, UpstreamDataError, fetch_akshare_daily


class DatasetValidationError(ValueError):
    pass


class DatasetIntegrityError(RuntimeError):
    pass


def _hash(s: str) -> str:
    return sha256(s.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _bars_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"date": r["obs_date"].isoformat() if isinstance(r["obs_date"], date) else str(r["obs_date"]),
         **{k: float(r[k]) for k in ("open", "high", "low", "close", "volume", "amount")}}
        for r in rows
    ]


def validate_bars(rows: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    if not 1 <= len(rows) <= 370:
        raise DatasetValidationError("Batch must contain 1–370 bars")
    normalized: list[dict[str, Any]] = []
    previous: date | None = None
    for r in rows:
        try:
            day = r["obs_date"]
            if not isinstance(day, date) or isinstance(day, datetime):
                raise ValueError("Date required")
            values = {k: float(r[k]) for k in ("open", "high", "low", "close", "volume", "amount")}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError("Non-finite field")
            op, hi, lo, cl, vol, amount = (values[k] for k in
                ("open", "high", "low", "close", "volume", "amount"))
            if not (0 < lo <= min(op, cl) and max(op, cl) <= hi and vol >= 0 and amount >= 0):
                raise ValueError("Invalid OHLCV")
            if not (start <= day <= end) or (previous is not None and day <= previous):
                raise ValueError("Date out of range, duplicate or unordered")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise DatasetValidationError("Entire provider window rejected: invalid price/date row") from exc
        previous = day
        normalized.append({"obs_date": day, **values})
    return normalized


def _manifest(*, kind: str, symbol: str, start: date, end: date,
              source_id: str, raw_hash: str, rows_hash: str) -> dict[str, str]:
    return {
        "asset_class": REGISTRY[kind]["asset_class"], "product_type": REGISTRY[kind]["product_type"],
        "source_id": source_id, "symbol": symbol, "adjustment": "none",
        "date_from": start.isoformat(), "date_to": end.isoformat(),
        "raw_sha256": raw_hash, "rows_sha256": rows_hash, "schema_version": "r1.0",
    }


def _summary(r: DatasetRelease) -> dict[str, Any]:
    return {
        "id": r.id, "fingerprint": r.fingerprint,
        "source_id": r.source_id, "asset_class": r.asset_class,
        "product_type": r.product_type, "symbol": r.symbol, "venue": r.venue,
        "currency": r.currency, "adjustment": r.adjustment, "volume_unit": r.volume_unit,
        "date_from": r.date_from.isoformat(), "date_to": r.date_to.isoformat(),
        "collected_at_utc": r.collected_at_utc.isoformat() + "Z",
        "row_count": r.row_count, "raw_sha256": r.raw_sha256,
        "rows_sha256": r.rows_sha256, "status": r.status,
        "quality_state": r.quality_state, "schema_version": r.schema_version,
        "pit_verified": False, "research_eligible": False,
        "warning": "Recorded supplier snapshot is NOT historical PIT-verified; no real recommendations or delivery.",
    }


def ingest_equity_or_etf_daily(db: Session, *, kind: str, symbol: str,
                               start: date, end: date) -> dict[str, Any]:
    # Fetch outside DB transaction. No legacy fallback and no supplied source labels.
    raw, supplied = fetch_akshare_daily(kind, symbol, start, end)
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 2_000_000:
        raise DatasetValidationError("Empty or excessive provider snapshot")
    clean = validate_bars(supplied, start, end)
    rows_hash = _hash(_canonical(_bars_payload(clean)))
    raw_hash = _hash(raw)
    spec = REGISTRY[kind]
    manifest = _manifest(kind=kind, symbol=symbol, start=start, end=end,
                         source_id=spec["source_id"], raw_hash=raw_hash, rows_hash=rows_hash)
    fingerprint = _hash(_canonical(manifest))
    existing = db.scalar(select(DatasetRelease).where(DatasetRelease.fingerprint == fingerprint))
    if existing is not None:
        return {"created": False, "release": get_dataset_release(db, existing.id)["release"]}
    venue = ("SSE" if symbol.startswith(("6", "5")) else
             "SZSE" if symbol.startswith(("0", "1", "3")) else "BSE")
    release = DatasetRelease(
        fingerprint=fingerprint, source_id=spec["source_id"],
        asset_class=spec["asset_class"], product_type=spec["product_type"],
        symbol=symbol, venue=venue, currency="CNY",
        adjustment="none", volume_unit=spec["volume_unit"],
        date_from=start, date_to=end,
        collected_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
        raw_sha256=raw_hash, rows_sha256=rows_hash, row_count=len(clean),
        status="provider_recorded", quality_state="schema_validated_only",
        schema_version="r1.0", raw_payload_json=raw,
    )
    try:
        db.add(release)
        db.flush()
        for p in clean:
            db.add(DatasetPriceObservation(release_id=release.id, **p))
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent request may have published the same content.
        duplicate = db.scalar(select(DatasetRelease).where(DatasetRelease.fingerprint == fingerprint))
        if duplicate is None:
            raise
        return {"created": False, "release": get_dataset_release(db, duplicate.id)["release"]}
    except Exception:
        db.rollback()
        raise
    return {"created": True, "release": get_dataset_release(db, release.id)["release"]}


def list_dataset_releases(db: Session, limit: int = 30) -> dict[str, Any]:
    rows = db.scalars(select(DatasetRelease).order_by(DatasetRelease.id.desc()).limit(limit)).all()
    return {"items": [_summary(row) for row in rows], "count": len(rows),
            "pit_verified_releases": 0, "can_recommend": False}


def get_dataset_release(db: Session, release_id: int) -> dict[str, Any]:
    release = db.get(DatasetRelease, release_id)
    if release is None:
        raise LookupError("Release not found")
    observations = db.scalars(
        select(DatasetPriceObservation).where(DatasetPriceObservation.release_id == release_id)
        .order_by(DatasetPriceObservation.obs_date.asc())
    ).all()
    bars = [
        {"obs_date": row.obs_date,
         **{key: getattr(row, key) for key in ("open", "high", "low", "close", "volume", "amount")}}
        for row in observations
    ]
    try:
        validated = validate_bars(bars, release.date_from, release.date_to)
        persisted_hash = _hash(_canonical(_bars_payload(validated)))
        manifest = _manifest(
            kind="equity" if release.asset_class == "equity" else "etf",
            symbol=release.symbol, start=release.date_from, end=release.date_to,
            source_id=release.source_id, raw_hash=release.raw_sha256, rows_hash=release.rows_sha256,
        )
        verified = (
            len(bars) == release.row_count and persisted_hash == release.rows_sha256
            and _hash(release.raw_payload_json) == release.raw_sha256
            and _hash(_canonical(manifest)) == release.fingerprint
            and release.source_id in {item["source_id"] for item in REGISTRY.values()}
            and release.status == "provider_recorded"
        )
    except (DatasetValidationError, KeyError, ValueError, TypeError):
        verified = False
    if not verified:
        raise DatasetIntegrityError("Stored release content and manifest do not match")
    return {
        "release": _summary(release),
        "observations": _bars_payload(validated),
        "integrity": "content_hash_consistent",
        "warning": "This only verifies stored content consistency, NOT original exchange truth or PIT publication history.",
    }


def dataset_readiness(db: Session) -> dict[str, Any]:
    rows = int(db.scalar(select(func.count()).select_from(DatasetRelease)) or 0)
    obs = int(db.scalar(select(func.count()).select_from(DatasetPriceObservation)) or 0)
    latest = db.scalar(select(DatasetRelease).order_by(DatasetRelease.id.desc()).limit(1))
    return {
        "recorded_release_count": rows, "recorded_observation_count": obs,
        "latest_release": _summary(latest) if latest is not None else None,
        "can_generate_real_recommendations": False,
        "historical_pit_verified": False,
        "data_state": "provider_recorded_not_pit_verified" if rows else "no_provider_releases",
        "missing": [
            "Historical as-of publication and revision history",
            "Official trading-calendar and corporate-action adjustments",
            "Historical listing/ST/delisting/sector membership",
            "Provider data licensing verification and OOS model validation",
        ],
    }
