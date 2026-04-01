from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import BrokerSessionStatus, LiveAsset, LiveOrder, LivePosition, LiveTrade, OrderPreview
from app.services.audit import write_audit
from app.services.broker import get_broker
from app.services.risk import RiskService


class LiveTradingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.broker = get_broker()
        self.risk = RiskService(db)

    def preview(self, symbol: str, side: str, price: float, quantity: int, recommendation_level: str = "C") -> OrderPreview:
        risk = self.risk.evaluate_order(symbol, side, price, quantity, recommendation_level=recommendation_level)
        preview = OrderPreview(
            symbol=symbol,
            side=side.lower(),
            price=price,
            quantity=quantity,
            decision=risk["decision"],
            summary=risk["summary"],
        )
        self.db.add(preview)
        write_audit(
            self.db,
            action="live.preview",
            detail=f"symbol={symbol}; side={side}; price={price}; quantity={quantity}; decision={preview.decision}",
        )
        self.db.commit()
        self.db.refresh(preview)
        return preview

    def place(self, symbol: str, side: str, price: float, quantity: int, recommendation_level: str = "C") -> LiveOrder:
        preview = self.preview(symbol, side, price, quantity, recommendation_level=recommendation_level)
        order = LiveOrder(symbol=symbol, side=side.lower(), price=price, quantity=quantity, status="previewed")
        self.db.add(order)
        self.db.flush()
        if preview.decision == "reject":
            order.status = "rejected"
            write_audit(self.db, action="live.place", detail=f"order_id={order.id}; rejected_by_preview=true")
            self.db.commit()
            self.db.refresh(order)
            return order

        broker_result = self.broker.place_order({"symbol": symbol, "side": side, "price": price, "quantity": quantity})
        order.status = broker_result.status
        if order.status == "accepted":
            order.status = "filled"
            trade = LiveTrade(order_id=order.id, symbol=symbol, side=side.lower(), price=price, quantity=quantity)
            self.db.add(trade)
            self._update_position(symbol, side.lower(), price, quantity)
        write_audit(self.db, action="live.place", detail=f"order_id={order.id}; final_status={order.status}")
        self.db.commit()
        self.db.refresh(order)
        return order

    def _update_position(self, symbol: str, side: str, price: float, quantity: int) -> None:
        position = self.db.scalar(select(LivePosition).where(LivePosition.symbol == symbol))
        if position is None:
            position = LivePosition(symbol=symbol, quantity=0, avg_price=0)
            self.db.add(position)
            self.db.flush()

        if side == "buy":
            new_qty = position.quantity + quantity
            position.avg_price = (position.avg_price * position.quantity + price * quantity) / max(new_qty, 1)
            position.quantity = new_qty
        else:
            position.quantity = max(0, position.quantity - quantity)
            if position.quantity == 0:
                position.avg_price = 0
        position.updated_at = datetime.utcnow()

    def cancel(self, order_id: int) -> LiveOrder | None:
        order = self.db.get(LiveOrder, order_id)
        if order is None:
            return None
        if order.status in {"filled", "cancelled", "rejected"}:
            return order
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        write_audit(self.db, action="live.cancel", detail=f"order_id={order.id}; status=cancelled")
        self.db.commit()
        self.db.refresh(order)
        return order

    def sync_account(self) -> dict:
        assets = self.broker.query_assets()
        snapshot = LiveAsset(
            snapshot_time=datetime.utcnow(),
            total_assets=float(assets.get("total_assets", 0)),
            cash=float(assets.get("cash", 0)),
            market_value=float(assets.get("market_value", 0)),
        )
        self.db.add(snapshot)
        write_audit(self.db, action="live.sync_account", detail=f"total_assets={snapshot.total_assets}")
        self.db.commit()
        return assets

    def broker_status(self) -> dict:
        status = self.broker.ping()
        self.db.add(BrokerSessionStatus(status=status.get("status", "unknown"), detail=str(status)))
        write_audit(self.db, action="live.broker_status", detail=f"status={status.get('status', 'unknown')}")
        self.db.commit()
        return status

    def orders(self) -> list[LiveOrder]:
        return list(self.db.scalars(select(LiveOrder).order_by(desc(LiveOrder.created_at))).all())

    def trades(self) -> list[LiveTrade]:
        return list(self.db.scalars(select(LiveTrade).order_by(desc(LiveTrade.trade_time))).all())

    def positions(self) -> list[LivePosition]:
        return list(self.db.scalars(select(LivePosition).order_by(desc(LivePosition.updated_at))).all())

    def assets(self) -> list[LiveAsset]:
        return list(self.db.scalars(select(LiveAsset).order_by(desc(LiveAsset.snapshot_time)).limit(30)).all())
