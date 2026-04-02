import json
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import ReplayService

router = APIRouter()


def _safe_loads(raw: str) -> dict:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


@router.get("/days")
def replay_days(db: Session = Depends(get_db)) -> dict:
    return {"items": ReplayService(db).days()}


@router.get("/day/{trade_date}")
def replay_day(
    trade_date: str,
    source_type: str = "",
    recommendation_level: str = "",
    outcome: str = "",
    db: Session = Depends(get_db),
) -> dict:
    rows = ReplayService(db).by_day(date.fromisoformat(trade_date))
    items = []
    for row in rows:
        record = _safe_loads(row.record_json)
        source = str(record.get("source_type", ""))
        result = str(record.get("status", record.get("decision", "")))
        if source_type and source != source_type:
            continue
        if recommendation_level and row.recommendation_level.upper() != recommendation_level.upper():
            continue
        if outcome and result != outcome:
            continue
        items.append(
            {
                "symbol": row.symbol,
                "strategy_key": row.strategy_key,
                "recommendation_level": row.recommendation_level,
                "record_json": row.record_json,
                "record": record,
                "source_type": source,
                "outcome": result,
            }
        )
    return {"items": items, "count": len(items)}


@router.get("/symbol/{symbol}")
def replay_symbol(symbol: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_symbol(symbol)
    return {
        "items": [
            {
                "trade_date": r.trade_date.isoformat(),
                "strategy_key": r.strategy_key,
                "recommendation_level": r.recommendation_level,
                "record_json": r.record_json,
                "record": _safe_loads(r.record_json),
            }
            for r in rows
        ]
    }


@router.get("/strategy/{strategy_key}")
def replay_strategy(strategy_key: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_strategy(strategy_key)
    return {
        "items": [
            {
                "trade_date": r.trade_date.isoformat(),
                "symbol": r.symbol,
                "recommendation_level": r.recommendation_level,
                "record_json": r.record_json,
                "record": _safe_loads(r.record_json),
            }
            for r in rows
        ]
    }


@router.get("/summary/{trade_date}")
def replay_summary(trade_date: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_day(date.fromisoformat(trade_date))
    by_source: dict[str, int] = {}
    by_level: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for row in rows:
        record = _safe_loads(row.record_json)
        source = str(record.get("source_type", "unknown"))
        outcome = str(record.get("status", record.get("decision", "unknown")))
        by_source[source] = by_source.get(source, 0) + 1
        by_level[row.recommendation_level] = by_level.get(row.recommendation_level, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
    return {"trade_date": trade_date, "by_source": by_source, "by_level": by_level, "by_outcome": by_outcome}
