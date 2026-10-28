from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.screener import ScreenerService
from app.services.research_gate import research_contract

router = APIRouter()


@router.get("/latest")
def latest_candidates(db: Session = Depends(get_db)) -> dict:
    rows = ScreenerService(db).latest_candidates()
    return {**research_contract(), "items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}


@router.get("/top100")
def top100(db: Session = Depends(get_db)) -> dict:
    rows = ScreenerService(db).top100()
    return {**research_contract(), "items": [{"symbol": c.symbol, "base_score": c.base_score, "rank_no": c.rank_no} for c in rows], "count": len(rows)}

