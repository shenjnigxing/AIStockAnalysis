from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_db
from app.api.admin_auth import require_admin
from app.services.system_ops import InitWizardService

router = APIRouter()

class InitStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step: str = Field(min_length=1, max_length=64)


@router.get("/status")
def init_status(db: Session = Depends(get_db)) -> dict:
    return InitWizardService(db).status()


@router.post("/run-step", dependencies=[Depends(require_admin)])
def init_run_step(payload: InitStep, db: Session = Depends(get_db)) -> dict:
    try:
        return InitWizardService(db).run_step(payload.step)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid step")


@router.post("/finish", dependencies=[Depends(require_admin)])
def init_finish(db: Session = Depends(get_db)) -> dict:
    return InitWizardService(db).finish()

