from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

from app.api.deps import get_db
from app.api.admin_auth import require_admin
from app.services.system_ops import SettingsService

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("")
def settings_get(db: Session = Depends(get_db)) -> dict:
    rows = SettingsService(db).get_all()
    items = [{"config_key": r.config_key, "config_value": r.config_value} for r in rows]
    return {"count": len(items), "items": items}


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    config_value: dict[str, Any] = Field(default_factory=dict)


@router.post("/update")
def settings_update(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    row = SettingsService(db).update(payload.config_key, payload.config_value)
    return {"config_key": row.config_key, "config_value": row.config_value}


@router.post("/reset-default")
def settings_reset(db: Session = Depends(get_db)) -> dict:
    defaults = SettingsService(db).reset_default()
    return {"defaults": defaults}
