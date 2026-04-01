from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import PaperAccount, PaperAsset, PaperOrder, PaperPosition, PaperTrade
from app.services.audit import write_audit
from app.services.risk import RiskService


class PaperTradingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.risk = RiskService(db)

    def ensure_account(self) -> PaperAccount:
        account = self.db.scalar(select(PaperAccount).order_by(PaperAccount.id))
        if account is None:
            account = PaperAccount(account_name="default")
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        return account

    def preview_order(self, symbol: str, side: str, price: float, quantity: int, recommendation_level: str = "C") -> dict:
        result = self.risk.evaluate_order(
            symbol=symbol, side=side, price=price, quantity=quantity, recommendation_level=recommendation_level
        )
        write_audit(
            self.db,
            action="paper.preview",
            detail=f"symbol={symbol}; side={side}; price={price}; quantity={quantity}; decision={result['decision']}",
        )
        self.db.commit()
        return result

    def place_order(self, symbol: str, side: str, price: float, quantity: int, recommendation_level: str = "C") -> PaperOrder:
        account = self.ensure_account()
        preview = self.preview_order(symbol, side, price, quantity, recommendation_level=recommendation_level)
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side=side.lower(),
            price=price,
            quantity=quantity,
            status="submitted",
        )
        self.db.add(order)
        self.db.flush()

        if preview["decision"] == "reject":
            order.status = "rejected"
            write_audit(self.db, action="paper.place", detail=f"order_id={order.id}; final_status=rejected")
            self.db.commit()
            self.db.refresh(order)
            return order

        filled = self._match(order)
        if not filled:
            order.status = "submitted"
            write_audit(self.db, action="paper.place", detail=f"order_id={order.id}; final_status=submitted")
            self.db.commit()
            self.db.refresh(order)
            return order

        order.status = "filled"
        write_audit(self.db, action="paper.place", detail=f"order_id={order.id}; final_status=filled")
        self.db.commit()
        self.db.refresh(order)
        return order

    def _match(self, order: PaperOrder) -> bool:
        account = self.ensure_account()
        trade = PaperTrade(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
        )
        cost = order.price * order.quantity

        position = self.db.scalar(
            select(PaperPosition).where(PaperPosition.account_id == account.id, PaperPosition.symbol == order.symbol)
        )
        if position is None:
            position = PaperPosition(account_id=account.id, symbol=order.symbol, quantity=0, avg_price=0)
            self.db.add(position)
            self.db.flush()

        if order.side == "buy":
            if account.cash < cost:
                return False
            new_qty = position.quantity + order.quantity
            new_avg = (position.quantity * position.avg_price + cost) / max(new_qty, 1)
            position.quantity = new_qty
            position.avg_price = round(new_avg, 4)
            account.cash -= cost
        else:
            if position.quantity < order.quantity:
                return False
            position.quantity -= order.quantity
            account.cash += cost
            if position.quantity == 0:
                position.avg_price = 0

        self.db.add(trade)
        self._recalc_account(account.id)
        return True

    def _recalc_account(self, account_id: int) -> None:
        account = self.db.get(PaperAccount, account_id)
        assert account is not None
        positions = list(self.db.scalars(select(PaperPosition).where(PaperPosition.account_id == account_id)).all())
        market_value = sum(p.quantity * p.avg_price for p in positions)
        account.market_value = round(market_value, 2)
        account.total_assets = round(account.cash + market_value, 2)
        account.total_pnl = round(account.total_assets - account.initial_cash, 2)
        asset = PaperAsset(
            account_id=account_id,
            snapshot_time=datetime.utcnow(),
            total_assets=account.total_assets,
            cash=account.cash,
            market_value=account.market_value,
        )
        self.db.add(asset)

    def cancel_order(self, order_id: int) -> PaperOrder | None:
        order = self.db.get(PaperOrder, order_id)
        if order is None:
            return None
        if order.status in {"filled", "cancelled", "rejected"}:
            return order
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        write_audit(self.db, action="paper.cancel", detail=f"order_id={order.id}; status=cancelled")
        self.db.commit()
        self.db.refresh(order)
        return order

    def list_orders(self) -> list[PaperOrder]:
        return list(self.db.scalars(select(PaperOrder).order_by(desc(PaperOrder.created_at))).all())

    def list_trades(self) -> list[PaperTrade]:
        return list(self.db.scalars(select(PaperTrade).order_by(desc(PaperTrade.trade_time))).all())

    def list_positions(self) -> list[PaperPosition]:
        account = self.ensure_account()
        return list(self.db.scalars(select(PaperPosition).where(PaperPosition.account_id == account.id)).all())

    def latest_asset(self) -> dict:
        account = self.ensure_account()
        return {
            "account_id": account.id,
            "cash": account.cash,
            "frozen_cash": account.frozen_cash,
            "market_value": account.market_value,
            "total_assets": account.total_assets,
            "daily_pnl": account.daily_pnl,
            "total_pnl": account.total_pnl,
        }
