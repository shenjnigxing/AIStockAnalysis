from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import InitWizardService

router = APIRouter()


@router.get("/status")
def init_status(db: Session = Depends(get_db)) -> dict:
    return InitWizardService(db).status()


@router.post("/run-step")
def init_run_step(payload: dict, db: Session = Depends(get_db)) -> dict:
    try:
        return InitWizardService(db).run_step(payload["step"])
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid step")


@router.post("/finish")
def init_finish(db: Session = Depends(get_db)) -> dict:
    return InitWizardService(db).finish()

