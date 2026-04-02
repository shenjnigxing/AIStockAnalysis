from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import SettingsService

router = APIRouter()


@router.get("")
def settings_get(db: Session = Depends(get_db)) -> dict:
    rows = SettingsService(db).get_all()
    items = [{"config_key": r.config_key, "config_value": r.config_value} for r in rows]
    return {"count": len(items), "items": items}


@router.post("/update")
def settings_update(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = SettingsService(db).update(payload["config_key"], payload.get("config_value", {}))
    return {"config_key": row.config_key, "config_value": row.config_value}


@router.post("/reset-default")
def settings_reset(db: Session = Depends(get_db)) -> dict:
    defaults = SettingsService(db).reset_default()
    return {"defaults": defaults}
