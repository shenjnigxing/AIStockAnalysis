from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import ReplayService

router = APIRouter()


@router.get("/days")
def replay_days(db: Session = Depends(get_db)) -> dict:
    return {"items": ReplayService(db).days()}


@router.get("/day/{trade_date}")
def replay_day(trade_date: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_day(date.fromisoformat(trade_date))
    return {"items": [{"symbol": r.symbol, "strategy_key": r.strategy_key, "recommendation_level": r.recommendation_level, "record_json": r.record_json} for r in rows]}


@router.get("/symbol/{symbol}")
def replay_symbol(symbol: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_symbol(symbol)
    return {"items": [{"trade_date": r.trade_date.isoformat(), "strategy_key": r.strategy_key, "recommendation_level": r.recommendation_level, "record_json": r.record_json} for r in rows]}


@router.get("/strategy/{strategy_key}")
def replay_strategy(strategy_key: str, db: Session = Depends(get_db)) -> dict:
    rows = ReplayService(db).by_strategy(strategy_key)
    return {"items": [{"trade_date": r.trade_date.isoformat(), "symbol": r.symbol, "recommendation_level": r.recommendation_level, "record_json": r.record_json} for r in rows]}

