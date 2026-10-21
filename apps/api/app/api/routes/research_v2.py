"""Read-only v2 research sandbox. Never routes to paper/live execution."""
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.research_data_readiness import research_data_readiness
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.research_v2 import ENGINE_VERSION, evaluate_batch
from app.services.sector_rotation import evaluate_sectors

router = APIRouter()


class ResearchBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: date
    market_regime: Literal["strong", "neutral", "weak", "panic"]
    items: list[dict[str, Any]] = Field(min_length=1, max_length=500)



class SectorPricePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    close: float = Field(gt=0, allow_inf_nan=False)


class SectorSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sector_id: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    sector_name: str = Field(min_length=1, max_length=80)
    prices: list[SectorPricePoint] = Field(min_length=61, max_length=260)


class SectorResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: date
    model: Literal["recovery", "trend"]
    source: Literal["synthetic_demo", "manual_unverified"]
    benchmark_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    benchmark_prices: list[SectorPricePoint] = Field(min_length=61, max_length=260)
    sectors: list[SectorSeries] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def validate_time_axis(self):
        if self.as_of > date.today():
            raise ValueError("as_of is in the future")
        benchmark_dates = [p.date for p in self.benchmark_prices]
        if benchmark_dates != sorted(set(benchmark_dates)):
            raise ValueError("benchmark dates must be strictly increasing and unique")
        if benchmark_dates[-1] != self.as_of:
            raise ValueError("last benchmark date must equal as_of")
        identifiers = [item.sector_id for item in self.sectors]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("sector_id must be unique")
        names = [item.sector_name for item in self.sectors]
        if len(set(names)) != len(names):
            raise ValueError("sector_name must be unique")
        for sector in self.sectors:
            dates = [point.date for point in sector.prices]
            if dates != benchmark_dates:
                raise ValueError(f"date axis mismatch for sector {sector.sector_id}")
        return self


@router.post("/sectors/evaluate")
def evaluate_sector_research(payload: SectorResearchRequest) -> dict[str, Any]:
    return evaluate_sectors(
        as_of=payload.as_of,
        model=payload.model,
        benchmark_id=payload.benchmark_id,
        benchmark=[point.model_dump() for point in payload.benchmark_prices],
        sectors=[series.model_dump() for series in payload.sectors],
        source=payload.source,
    )


@router.get("/data-readiness")
def get_data_readiness(db: Session = Depends(get_db)) -> dict[str, Any]:
    return research_data_readiness(db)


@router.get("/capabilities")
def research_capabilities() -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "mode": "research_only",
        "data_connection": "manual_point_in_time_snapshots",
        "can_execute_orders": False,
        "validated_alpha": False,
        "verified_point_in_time_data": False,
        "iteration": "review_cycle_3_data_integrity",
        "data_readiness_endpoint": "/api/research/v2/data-readiness",
        "limitations": [
            "Current v2 score is a hypothesis, not statistically validated alpha.",
            "A point-in-time financial data integration is required before live screening.",
            "Do not infer probabilities of profit from the research score.",
            "Manually entered snapshots cannot establish provenance or reliability.",
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
