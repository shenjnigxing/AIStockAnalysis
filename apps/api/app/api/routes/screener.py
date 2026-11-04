import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.screener import ScreenerService, ScreenerFilters
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from app.services.research_gate import research_contract


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: ScreenerFilters = Field(default_factory=ScreenerFilters)
    mode: Literal["intraday", "daily"] = "intraday"


class PresetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    params: ScreenerFilters = Field(default_factory=ScreenerFilters)


class PresetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    params: ScreenerFilters = Field(default_factory=ScreenerFilters)


router = APIRouter()


@router.post("/run")
def run_screener(payload: RunRequest, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    run = service.run(filters=payload.filters.model_dump(), mode=payload.mode)
    return {**research_contract(), "screener_run_id": run.id, "status": run.status}


@router.get("/presets")
def list_presets(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.list_presets()
    return {
        "items": [{"id": p.id, "name": p.name, "params": json.loads(p.params_json)} for p in rows],
        "count": len(rows),
    }


@router.post("/presets")
def create_preset(payload: PresetCreate, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    p = service.create_preset(name=payload.name, params=payload.params.model_dump())
    return {"id": p.id, "name": p.name}


@router.post("/presets/{preset_id}/update")
def update_preset(preset_id: int, payload: PresetUpdate, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    p = service.update_preset(preset_id, payload.params.model_dump())
    if p is None:
        raise HTTPException(status_code=404, detail="preset not found")
    return {"id": p.id, "name": p.name}


@router.get("/candidates/latest")
def latest_candidates(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.latest_candidates()
    return {**research_contract(), "items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}


@router.get("/candidates/top100")
def top100(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.top100()
    return {**research_contract(), "items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}

