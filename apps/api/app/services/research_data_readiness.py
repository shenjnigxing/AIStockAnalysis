"""Read-only data-readiness diagnostics.

Legacy bars lack per-row provenance. We cannot promote them to verified prices
merely because a recent sync job reports a provider name.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DataQualityIssue, DailyBar, RealtimeQuote, StockMaster, SyncJob


def _safe_result(raw: str | None) -> dict[str, Any]:
    try:
        item = json.loads(raw or "{}")
        return item if isinstance(item, dict) else {}
    except (TypeError, ValueError):
        return {}


def research_data_readiness(db: Session, *, as_of: date | None = None) -> dict[str, Any]:
    """Only counts and timestamps; neither claims data quality nor computes signals."""
    today = as_of or date.today()
    masters = int(db.scalar(select(func.count()).select_from(StockMaster)) or 0)
    master_active = int(db.scalar(
        select(func.count()).select_from(StockMaster).where(StockMaster.is_active.is_(True))
    ) or 0)
    daily_bars = int(db.scalar(select(func.count()).select_from(DailyBar)) or 0)
    symbols_with_bars = int(db.scalar(select(func.count(func.distinct(DailyBar.symbol)))) or 0)
    quote_count = int(db.scalar(select(func.count()).select_from(RealtimeQuote)) or 0)
    issues = int(db.scalar(select(func.count()).select_from(DataQualityIssue)) or 0)
    latest_daily = db.scalar(select(func.max(DailyBar.trade_date)))
    last_quote_time = db.scalar(select(func.max(RealtimeQuote.quote_time)))
    last_daily_sync = db.scalar(
        select(SyncJob).where(SyncJob.job_type == "daily")
        .order_by(SyncJob.id.desc()).limit(1)
    )
    last_any_failure = db.scalar(
        select(SyncJob).where(SyncJob.status == "failed")
        .order_by(SyncJob.id.desc()).limit(1)
    )
    metadata = _safe_result(last_daily_sync.result_json) if last_daily_sync else {}
    last_mode = metadata.get("data_mode") if last_daily_sync and last_daily_sync.status == "completed" else None
    # Status describes whether this database is fit for V2 recommendations,
    # never the current broker or public markets.
    if daily_bars == 0 or masters == 0:
        state = "no_usable_dataset"
    elif last_mode == "mock":
        state = "synthetic_data_detected"
    else:
        state = "legacy_unverified"
    warnings = [
        "Historical daily bars have no per-row provider lineage or adjustment metadata.",
        "Legacy data may contain synthetic fallback rows from earlier app versions.",
        "Sector classification, financial disclosure dates and historic ST universe are missing.",
        "Readiness is diagnostic only; sector rotation and V2 stock recommendations stay disabled.",
    ]
    if last_mode == "mock":
        warnings.insert(0, "The last completed daily-sync job explicitly used synthetic demo mode.")
    if last_daily_sync and last_daily_sync.status == "failed":
        warnings.insert(0, "The latest daily-sync job failed; existing bars must not be treated as current.")
    if issues:
        warnings.append("The legacy data-quality issue log is non-empty; inspect its findings.")

    return {
        "state": state,
        "is_research_ready": False,
        "can_generate_v2_recommendations": False,
        "as_of": today.isoformat(),
        "stocks_total": masters,
        "stocks_active": master_active,
        "symbols_with_daily_bars": symbols_with_bars,
        "daily_bar_count": daily_bars,
        "latest_daily_bar": latest_daily.isoformat() if latest_daily else None,
        "latest_daily_age_calendar_days": max(0, (today - latest_daily).days) if latest_daily else None,
        "realtime_quote_count": quote_count,
        "latest_quote_timestamp": last_quote_time.isoformat() if last_quote_time else None,
        "quality_issue_count": issues,
        "last_daily_sync": (
            {
                "job_id": last_daily_sync.id,
                "status": last_daily_sync.status,
                "mode": last_mode or "unknown",
                "provider": metadata.get("data_provider", "unknown"),
                "completed_at": last_daily_sync.finished_at.isoformat() if last_daily_sync.finished_at else None,
            }
            if last_daily_sync else None
        ),
        "last_failure": (
            {"job_type": last_any_failure.job_type, "error": (last_any_failure.error_message or "")[:250]}
            if last_any_failure else None
        ),
        "provenance": "unverified_legacy_store",
        "warnings": warnings,
    }
