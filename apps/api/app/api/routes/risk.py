import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.risk import RiskService

router = APIRouter()


@router.get("/config")
def risk_config(db: Session = Depends(get_db)) -> dict:
    row = RiskService(db).get_config()
    return {"config": json.loads(row.config_json)}


@router.post("/config")
def risk_update(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = RiskService(db).update_config(payload)
    return {"config": json.loads(row.config_json)}


@router.get("/live-gray/config")
def risk_live_gray_get(db: Session = Depends(get_db)) -> dict:
    return {"config": RiskService(db).get_live_gray_config()}


@router.post("/live-gray/config")
def risk_live_gray_update(payload: dict, db: Session = Depends(get_db)) -> dict:
    return {"config": RiskService(db).update_live_gray_config(payload)}


@router.get("/status")
def risk_status(db: Session = Depends(get_db)) -> dict:
    return RiskService(db).status()


@router.get("/events")
def risk_events(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    rows = RiskService(db).list_events(limit=limit)
    return {"items": [{"id": r.id, "event_type": r.event_type, "level": r.level, "summary": r.summary, "created_at": r.created_at.isoformat()} for r in rows]}


@router.post("/kill-switch/enable")
def risk_enable(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = RiskService(db).set_kill_switch(True, payload.get("reason", "manual_enable"))
    return {"enabled": row.enabled, "reason": row.reason}


@router.post("/kill-switch/disable")
def risk_disable(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = RiskService(db).set_kill_switch(False, payload.get("reason", "manual_disable"))
    return {"enabled": row.enabled, "reason": row.reason}
