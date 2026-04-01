import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import RecommendationResult, RecommendationRun
from app.services.recommendation import RecommendationService

router = APIRouter()


def _serialize(row: RecommendationResult) -> dict:
    return {
        "symbol": row.symbol,
        "final_rank": row.final_rank,
        "recommendation_level": row.recommendation_level,
        "total_score": row.total_score,
        "quant_score": row.quant_score,
        "risk_score": row.risk_score,
        "llm_score_adjustment": row.llm_score_adjustment,
        "hit_strategies": json.loads(row.hit_strategies),
        "reasons": json.loads(row.reasons),
        "llm_explanation": row.llm_explanation,
        "counter_arguments": json.loads(row.counter_arguments),
        "risk_tags": json.loads(row.risk_tags),
        "action_suggestion": row.action_suggestion,
        "confidence_level": row.confidence_level,
    }


@router.post("/run")
def run_recommendation(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = RecommendationService(db)
    run = service.run(market_state=payload.get("market_state", "neutral"), llm_enabled=bool(payload.get("llm_enabled", False)))
    return {"recommendation_run_id": run.id, "status": run.status}


@router.get("/latest")
def recommendation_latest(db: Session = Depends(get_db)) -> dict:
    service = RecommendationService(db)
    items = service.latest()
    return {"items": [_serialize(i) for i in items], "count": len(items)}


@router.get("/top")
def recommendation_top(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    service = RecommendationService(db)
    items = service.latest()[:limit]
    return {"items": [_serialize(i) for i in items], "count": len(items)}


@router.get("/history/list")
def recommendation_history(db: Session = Depends(get_db)) -> dict:
    runs = list(db.scalars(select(RecommendationRun).order_by(desc(RecommendationRun.created_at)).limit(20)).all())
    return {"items": [{"id": r.id, "status": r.status, "market_state": r.market_state, "created_at": r.created_at.isoformat()} for r in runs]}


@router.get("/history")
def recommendation_history_alias(db: Session = Depends(get_db)) -> dict:
    return recommendation_history(db)


@router.get("/{symbol}")
def recommendation_symbol(symbol: str, db: Session = Depends(get_db)) -> dict:
    run = db.scalar(select(RecommendationRun).order_by(desc(RecommendationRun.created_at)))
    if run is None:
        raise HTTPException(status_code=404, detail="no recommendation run")
    row = db.scalar(
        select(RecommendationResult).where(
            RecommendationResult.recommendation_run_id == run.id,
            RecommendationResult.symbol == symbol,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    return _serialize(row)
