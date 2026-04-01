import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.screener import ScreenerService

router = APIRouter()


@router.post("/run")
def run_screener(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    run = service.run(filters=payload.get("filters", {}), mode=payload.get("mode", "intraday"))
    return {"screener_run_id": run.id, "status": run.status}


@router.get("/presets")
def list_presets(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.list_presets()
    return {
        "items": [{"id": p.id, "name": p.name, "params": json.loads(p.params_json)} for p in rows],
        "count": len(rows),
    }


@router.post("/presets")
def create_preset(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    p = service.create_preset(name=payload["name"], params=payload.get("params", {}))
    return {"id": p.id, "name": p.name}


@router.post("/presets/{preset_id}/update")
def update_preset(preset_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    p = service.update_preset(preset_id, payload.get("params", {}))
    if p is None:
        raise HTTPException(status_code=404, detail="preset not found")
    return {"id": p.id, "name": p.name}


@router.get("/candidates/latest")
def latest_candidates(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.latest_candidates()
    return {"items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}


@router.get("/candidates/top100")
def top100(db: Session = Depends(get_db)) -> dict:
    service = ScreenerService(db)
    rows = service.top100()
    return {"items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}

