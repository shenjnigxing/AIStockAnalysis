from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.paper_trading import PaperTradingService

router = APIRouter()


@router.post("/order/preview")
def paper_preview(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = PaperTradingService(db)
    return service.preview_order(
        symbol=payload["symbol"],
        side=payload["side"],
        price=float(payload["price"]),
        quantity=int(payload["quantity"]),
        recommendation_level=payload.get("recommendation_level", "C"),
    )


@router.post("/orders")
def paper_place(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = PaperTradingService(db)
    order = service.place_order(
        symbol=payload["symbol"],
        side=payload["side"],
        price=float(payload["price"]),
        quantity=int(payload["quantity"]),
        recommendation_level=payload.get("recommendation_level", "C"),
    )
    return {"order_id": order.id, "status": order.status}


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

