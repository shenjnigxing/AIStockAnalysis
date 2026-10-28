from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
import os
from hashlib import sha256
import json
from app.db.models import PaperIdempotency, PaperOrder

from app.api.deps import get_db
from app.services.paper_trading import PaperTradingService

router = APIRouter()


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    side: Literal["buy", "sell"]
    price: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    quantity: int = Field(gt=0, le=10_000_000, strict=True)
    recommendation_level: Literal["A", "B", "C", "D"] = "C"


@router.post("/order/preview")
def paper_preview(payload: PaperOrderRequest, db: Session = Depends(get_db)) -> dict:
    return PaperTradingService(db).preview_order(**payload.model_dump())


@router.post("/orders")
def paper_place(payload: PaperOrderRequest, db: Session = Depends(get_db),
                idempotency_key: str | None = Header(default=None, min_length=1, max_length=128)) -> dict:
    if not idempotency_key and not (os.getenv('APP_ENV') == 'test' and os.getenv('MARKET_DATA_MODE') == 'mock'):
        raise HTTPException(422, 'Idempotency-Key required for paper order')
    values = payload.model_dump()
    digest = sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    def prior_result():
        previous = db.get(PaperIdempotency, idempotency_key)
        if previous is None:
            raise HTTPException(409, "Order reservation unavailable; inspect existing orders")
        if previous.request_sha256 != digest:
            raise HTTPException(409, "Idempotency key already used with different order")
        order = db.get(PaperOrder, previous.order_id) if previous.order_id else None
        if order is None:
            raise HTTPException(409, "Order outcome not yet available")
        return {"order_id": order.id, "status": order.status}
    if idempotency_key and db.get(PaperIdempotency, idempotency_key):
        return prior_result()
    try:
        reservation = None
        if idempotency_key:
            reservation = PaperIdempotency(key=idempotency_key, request_sha256=digest)
            db.add(reservation)
            try:
                db.flush()  # unique key serializes competing claims across workers
            except IntegrityError:
                db.rollback()
                return prior_result()
        order = PaperTradingService(db, atomic=True).place_order(**values)
        if reservation is not None:
            reservation.order_id = order.id
        db.commit()
        return {"order_id": order.id, "status": order.status}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/orders/{order_id}/cancel")
def paper_cancel(order_id: int, db: Session = Depends(get_db)) -> dict:
    service = PaperTradingService(db)
    order = service.cancel_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return {"order_id": order.id, "status": order.status}


@router.get("/orders")
def paper_orders(db: Session = Depends(get_db)) -> dict:
    rows = PaperTradingService(db).list_orders()
    return {"items": [{"order_id": o.id, "symbol": o.symbol, "side": o.side, "status": o.status, "price": o.price, "quantity": o.quantity} for o in rows]}


@router.get("/trades")
def paper_trades(db: Session = Depends(get_db)) -> dict:
    rows = PaperTradingService(db).list_trades()
    return {"items": [{"trade_id": t.id, "order_id": t.order_id, "symbol": t.symbol, "side": t.side, "price": t.price, "quantity": t.quantity} for t in rows]}


@router.get("/positions")
def paper_positions(db: Session = Depends(get_db)) -> dict:
    rows = PaperTradingService(db).list_positions()
    return {"items": [{"symbol": p.symbol, "quantity": p.quantity, "avg_price": p.avg_price} for p in rows]}


@router.get("/assets")
def paper_assets(db: Session = Depends(get_db)) -> dict:
    return PaperTradingService(db).latest_asset()


@router.get("/pnl")
def paper_pnl(db: Session = Depends(get_db)) -> dict:
    asset = PaperTradingService(db).latest_asset()
    return {"daily_pnl": asset["daily_pnl"], "total_pnl": asset["total_pnl"]}

