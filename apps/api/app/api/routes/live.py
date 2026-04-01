from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.live_trading import LiveTradingService

router = APIRouter()


@router.post("/order/preview")
def live_preview(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = LiveTradingService(db).preview(
        symbol=payload["symbol"],
        side=payload["side"],
        price=float(payload["price"]),
        quantity=int(payload["quantity"]),
        recommendation_level=payload.get("recommendation_level", "C"),
    )
    return {"preview_id": row.id, "decision": row.decision, "summary": row.summary}


@router.post("/order")
def live_place(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = LiveTradingService(db).place(
        symbol=payload["symbol"],
        side=payload["side"],
        price=float(payload["price"]),
        quantity=int(payload["quantity"]),
        recommendation_level=payload.get("recommendation_level", "C"),
    )
    return {"order_id": row.id, "status": row.status}


@router.post("/order/{order_id}/cancel")
def live_cancel(order_id: int, db: Session = Depends(get_db)) -> dict:
    row = LiveTradingService(db).cancel(order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return {"order_id": row.id, "status": row.status}


@router.get("/orders")
def live_orders(db: Session = Depends(get_db)) -> dict:
    rows = LiveTradingService(db).orders()
    return {"items": [{"order_id": o.id, "symbol": o.symbol, "side": o.side, "price": o.price, "quantity": o.quantity, "status": o.status} for o in rows]}


@router.get("/trades")
def live_trades(db: Session = Depends(get_db)) -> dict:
    rows = LiveTradingService(db).trades()
    return {"items": [{"trade_id": t.id, "order_id": t.order_id, "symbol": t.symbol, "side": t.side, "price": t.price, "quantity": t.quantity} for t in rows]}


@router.get("/positions")
def live_positions(db: Session = Depends(get_db)) -> dict:
    rows = LiveTradingService(db).positions()
    return {"items": [{"symbol": p.symbol, "quantity": p.quantity, "avg_price": p.avg_price} for p in rows]}


@router.get("/assets")
def live_assets(db: Session = Depends(get_db)) -> dict:
    rows = LiveTradingService(db).assets()
    return {"items": [{"snapshot_time": a.snapshot_time.isoformat(), "cash": a.cash, "market_value": a.market_value, "total_assets": a.total_assets} for a in rows]}


@router.post("/sync/account")
def live_sync(db: Session = Depends(get_db)) -> dict:
    return LiveTradingService(db).sync_account()


@router.get("/broker/status")
def live_broker_status(db: Session = Depends(get_db)) -> dict:
    return LiveTradingService(db).broker_status()

