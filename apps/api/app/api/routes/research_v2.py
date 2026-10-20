"""Read-only v2 research sandbox. Never routes to paper/live execution."""
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.research_v2 import ENGINE_VERSION, evaluate_batch

router = APIRouter()


class ResearchBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    as_of: date
    market_regime: Literal["strong", "neutral", "weak", "panic"]
    items: list[dict[str, Any]] = Field(min_length=1, max_length=500)


@router.get("/capabilities")
def research_capabilities() -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "mode": "research_only",
        "data_connection": "manual_point_in_time_snapshots",
        "can_execute_orders": False,
        "validated_alpha": False,
        "limitations": [
            "Current v2 score is a hypothesis, not statistically validated alpha.",
            "A point-in-time financial data integration is required before live screening.",
            "Do not infer probabilities of profit from the research score.",
        ],
    }


@router.post("/evaluate")
def evaluate_research(payload: ResearchBatchRequest) -> dict[str, Any]:
    if payload.as_of > date.today():
        raise HTTPException(status_code=422, detail="Research date cannot be in the future")
    try:
        return evaluate_batch(
            payload.items, evaluation_date=payload.as_of,
            market_regime=payload.market_regime,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
