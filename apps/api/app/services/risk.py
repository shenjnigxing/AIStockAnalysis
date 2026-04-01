import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import KillSwitchStatus, PaperAccount, PaperOrder, PaperPosition, RiskConfig, RiskEvent
from app.services.audit import write_audit


DEFAULT_RISK_CONFIG = {
    "max_single_order_amount": 100000,
    "max_position_ratio": 0.3,
    "max_daily_loss": 20000,
    "max_daily_trade_count": 20,
    "min_recommendation_level": "B",
}


class RiskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_config(self) -> RiskConfig:
        conf = self.db.scalar(select(RiskConfig).order_by(desc(RiskConfig.updated_at)))
        if conf is None:
            conf = RiskConfig(config_json=json.dumps(DEFAULT_RISK_CONFIG, ensure_ascii=True))
            self.db.add(conf)
            self.db.commit()
            self.db.refresh(conf)
        return conf

    def update_config(self, payload: dict) -> RiskConfig:
        conf = self.get_config()
        conf.config_json = json.dumps(payload, ensure_ascii=True)
        conf.updated_at = datetime.utcnow()
        write_audit(self.db, action="risk.config_update", detail="updated=true")
        self.db.commit()
        self.db.refresh(conf)
        return conf

    def status(self) -> dict:
        ks = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        enabled = ks.enabled if ks else False
        return {"kill_switch_enabled": enabled}

    def _recommendation_rank(self, level: str) -> int:
        mapping = {"A": 4, "B": 3, "C": 2, "D": 1}
        return mapping.get(str(level).upper(), 0)

    def evaluate_order(self, symbol: str, side: str, price: float, quantity: int, recommendation_level: str = "C") -> dict:
        conf = json.loads(self.get_config().config_json)
        amount = price * quantity
        account = self.db.scalar(select(PaperAccount).order_by(PaperAccount.id))
        cash = float(account.cash) if account else 1_000_000.0
        total_assets = float(account.total_assets) if account else 1_000_000.0
        side = side.lower().strip()

        hard = []
        warnings = []
        manual = []

        ks = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        if ks and ks.enabled:
            hard.append("kill_switch_enabled")
        if quantity <= 0 or price <= 0:
            hard.append("invalid_order_params")
        if amount > float(conf.get("max_single_order_amount", 100000)):
            hard.append("single_order_amount_exceeded")
        if side not in {"buy", "sell"}:
            hard.append("invalid_side")
        if side == "buy" and amount > cash:
            hard.append("insufficient_cash")
        min_level = str(conf.get("min_recommendation_level", "B")).upper()
        if self._recommendation_rank(recommendation_level) < self._recommendation_rank(min_level):
            manual.append("recommendation_level_low")

        if account:
            position = self.db.scalar(
                select(PaperPosition)
                .where(PaperPosition.account_id == account.id, PaperPosition.symbol == symbol)
                .order_by(desc(PaperPosition.updated_at))
            )
        else:
            position = None
        current_qty = int(position.quantity) if position else 0
        current_position_value = current_qty * float(position.avg_price if position else 0)
        projected_position_value = current_position_value + amount if side == "buy" else max(0.0, current_position_value - amount)
        projected_ratio = projected_position_value / max(total_assets, 1e-6)
        if side == "buy" and projected_ratio > float(conf.get("max_position_ratio", 0.3)):
            hard.append("position_ratio_exceeded")
        if side == "sell" and current_qty < quantity:
            hard.append("insufficient_position")

        today = datetime.now(timezone.utc).date()
        today_start = datetime(today.year, today.month, today.day)
        today_orders = list(self.db.scalars(select(PaperOrder).where(PaperOrder.created_at >= today_start)).all())
        trade_count = len(today_orders)
        if trade_count >= int(conf.get("max_daily_trade_count", 20)):
            manual.append("daily_trade_count_limit")

        if account and account.daily_pnl <= -abs(float(conf.get("max_daily_loss", 20000))):
            hard.append("max_daily_loss_exceeded")
        if amount > cash * 0.2:
            warnings.append("large_order_warning")
        if projected_ratio > float(conf.get("max_position_ratio", 0.3)) * 0.8:
            warnings.append("position_ratio_warning")

        if hard:
            decision = "reject"
        elif manual:
            decision = "manual_review_required"
        elif warnings:
            decision = "pass_with_warning"
        else:
            decision = "pass"

        event = RiskEvent(
            event_type="order_preview",
            level="critical" if decision == "reject" else "warning" if warnings else "info",
            summary=f"decision={decision}",
            detail=json.dumps({"symbol": symbol, "side": side, "amount": amount}, ensure_ascii=True),
        )
        self.db.add(event)
        self.db.commit()
        return {
            "decision": decision,
            "summary": f"risk decision for {symbol}",
            "hard_reject_rules": hard,
            "warning_rules": warnings,
            "manual_review_rules": manual,
            "estimated_cost": round(amount, 2),
            "estimated_position_ratio": round(min(1.0, projected_ratio), 4),
            "recommendation_snapshot": {"recommendation_level": recommendation_level},
            "risk_context": {"cash": cash, "total_assets": total_assets, "position_qty": current_qty, "trade_count_today": trade_count},
            "requires_manual_ack": decision == "manual_review_required",
        }

    def list_events(self, limit: int = 100) -> list[RiskEvent]:
        return list(self.db.scalars(select(RiskEvent).order_by(desc(RiskEvent.created_at)).limit(limit)).all())

    def set_kill_switch(self, enabled: bool, reason: str = "") -> KillSwitchStatus:
        ks = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        if ks is None:
            ks = KillSwitchStatus(enabled=enabled, reason=reason)
            self.db.add(ks)
        else:
            ks.enabled = enabled
            ks.reason = reason
            ks.updated_at = datetime.utcnow()
        action = "risk.kill_switch_enable" if enabled else "risk.kill_switch_disable"
        write_audit(self.db, action=action, detail=f"enabled={enabled}; reason={reason}")
        self.db.commit()
        self.db.refresh(ks)
        return ks
