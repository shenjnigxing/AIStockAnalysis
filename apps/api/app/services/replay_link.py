from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import ReplayRecord


def append_replay_record(
    db: Session,
    *,
    symbol: str,
    strategy_key: str,
    recommendation_level: str,
    source_type: str,
    payload: dict,
) -> None:
    record = {
        "source_type": source_type,
        **payload,
    }
    db.add(
        ReplayRecord(
            trade_date=date.today(),
            symbol=symbol,
            strategy_key=strategy_key or "",
            recommendation_level=(recommendation_level or "C").upper(),
            record_json=json.dumps(record, ensure_ascii=True),
        )
    )

