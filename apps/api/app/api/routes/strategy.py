import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import StrategyDefinition, StrategyParamVersion, StrategyRun, StrategySignal
from app.services.strategy_engine import StrategyRegistry

router = APIRouter()
registry = StrategyRegistry()


def _ensure_strategy_definitions(db: Session) -> None:
    count = db.scalar(select(StrategyDefinition).limit(1))
    if count is not None:
        return
    for s in registry.list_strategies():
        db.add(
            StrategyDefinition(
                strategy_key=s.strategy_key,
                strategy_name=s.strategy_name,
                category=s.category,
                version="1.0.0",
                enabled=True,
                default_params="{}",
                description=f"{s.strategy_name} rule template",
            )
        )
    db.commit()


@router.get("/list")
def strategy_list(db: Session = Depends(get_db)) -> dict:
    _ensure_strategy_definitions(db)
    rows = list(db.scalars(select(StrategyDefinition)).all())
    return {
        "items": [
            {
                "strategy_key": r.strategy_key,
                "strategy_name": r.strategy_name,
                "category": r.category,
                "enabled": r.enabled,
                "version": r.version,
            }
            for r in rows
        ]
    }


@router.get("/{strategy_key}")
def strategy_detail(strategy_key: str, db: Session = Depends(get_db)) -> dict:
    _ensure_strategy_definitions(db)
    row = db.scalar(select(StrategyDefinition).where(StrategyDefinition.strategy_key == strategy_key))
    if row is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return {
        "strategy_key": row.strategy_key,
        "strategy_name": row.strategy_name,
        "category": row.category,
        "default_params": json.loads(row.default_params),
        "enabled": row.enabled,
    }


@router.post("/evaluate")
def strategy_evaluate(payload: dict, db: Session = Depends(get_db)) -> dict:
    symbol = payload["symbol"]
    strategy_keys = payload.get("strategy_keys")
    context = payload.get("context", {})
    run = StrategyRun(scope="single" if symbol else "batch", symbol=symbol, status="completed")
    db.add(run)
    db.flush()

    results = registry.evaluate(symbol=symbol, strategy_keys=strategy_keys, context=context)
    for item in results:
        db.add(
            StrategySignal(
                strategy_run_id=run.id,
                symbol=item.symbol,
                strategy_key=item.strategy_key,
                hit=item.hit,
                score=item.score,
                confidence=item.confidence,
                reasons=json.dumps(item.reasons, ensure_ascii=True),
                risk_tags=json.dumps(item.risk_tags, ensure_ascii=True),
                feature_snapshot=json.dumps(item.feature_snapshot, ensure_ascii=True),
                market_fit_score=item.market_fit_score,
                conflict_tags=json.dumps(item.conflict_tags, ensure_ascii=True),
                created_at=datetime.utcnow(),
            )
        )
    db.commit()
    return {
        "strategy_run_id": run.id,
        "items": [
            {
                "symbol": i.symbol,
                "strategy_key": i.strategy_key,
                "hit": i.hit,
                "score": i.score,
                "confidence": i.confidence,
                "reasons": i.reasons,
                "risk_tags": i.risk_tags,
                "feature_snapshot": i.feature_snapshot,
                "market_fit_score": i.market_fit_score,
                "conflict_tags": i.conflict_tags,
            }
            for i in results
        ],
    }


@router.post("/toggle")
def strategy_toggle(payload: dict, db: Session = Depends(get_db)) -> dict:
    _ensure_strategy_definitions(db)
    row = db.scalar(select(StrategyDefinition).where(StrategyDefinition.strategy_key == payload["strategy_key"]))
    if row is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    row.enabled = bool(payload.get("enabled", True))
    db.commit()
    return {"strategy_key": row.strategy_key, "enabled": row.enabled}


@router.post("/params/update")
def strategy_params_update(payload: dict, db: Session = Depends(get_db)) -> dict:
    key = payload["strategy_key"]
    version = payload.get("version", "1.0.1")
    params = payload.get("params", {})
    db.add(StrategyParamVersion(strategy_key=key, version=version, params_json=json.dumps(params, ensure_ascii=True)))
    row = db.scalar(select(StrategyDefinition).where(StrategyDefinition.strategy_key == key))
    if row:
        row.version = version
        row.default_params = json.dumps(params, ensure_ascii=True)
    db.commit()
    return {"strategy_key": key, "version": version}

