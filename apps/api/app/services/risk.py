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
    "live_gray_mode_enabled": True,
    "live_gray_max_notional": 50000,
    "live_gray_whitelist": ["000001", "600000", "600519"],
    "live_gray_blocklist": [],
    "live_auto_submit": False,
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

    def get_live_gray_config(self) -> dict:
        conf = json.loads(self.get_config().config_json)
        return {
            "live_gray_mode_enabled": bool(conf.get("live_gray_mode_enabled", True)),
            "live_gray_max_notional": float(conf.get("live_gray_max_notional", 50000)),
            "live_gray_whitelist": conf.get("live_gray_whitelist", []),
            "live_gray_blocklist": conf.get("live_gray_blocklist", []),
            "live_auto_submit": bool(conf.get("live_auto_submit", False)),
        }

    def update_live_gray_config(self, payload: dict) -> dict:
        conf = json.loads(self.get_config().config_json)
        conf["live_gray_mode_enabled"] = bool(payload.get("live_gray_mode_enabled", conf.get("live_gray_mode_enabled", True)))
        conf["live_gray_max_notional"] = float(payload.get("live_gray_max_notional", conf.get("live_gray_max_notional", 50000)))
        conf["live_gray_whitelist"] = payload.get("live_gray_whitelist", conf.get("live_gray_whitelist", []))
        conf["live_gray_blocklist"] = payload.get("live_gray_blocklist", conf.get("live_gray_blocklist", []))
        conf["live_auto_submit"] = bool(payload.get("live_auto_submit", conf.get("live_auto_submit", False)))
        row = self.update_config(conf)
        write_audit(self.db, action="risk.live_gray_update", detail="updated=true")
        self.db.commit()
        return json.loads(row.config_json)

    def status(self) -> dict:
        ks = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        enabled = ks.enabled if ks else False
        return {"kill_switch_enabled": enabled}

    def _recommendation_rank(self, level: str) -> int:
        mapping = {"A": 4, "B": 3, "C": 2, "D": 1}
        return mapping.get(str(level).upper(), 0)

    def _to_symbol_set(self, value: object) -> set[str]:
        if isinstance(value, list):
            return {str(item).strip() for item in value if str(item).strip()}
        return set()

    def evaluate_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: int,
        recommendation_level: str = "C",
        channel: str = "paper",
        manual_ack: bool = False,
        auto_submit: bool = False,
    ) -> dict:
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
        if self._recommendation_rank(recommendation_level) < self._recommendation_rank(min_level) and not manual_ack:
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
        if trade_count >= int(conf.get("max_daily_trade_count", 20)) and not manual_ack:
            manual.append("daily_trade_count_limit")

        if account and account.daily_pnl <= -abs(float(conf.get("max_daily_loss", 20000))):
            hard.append("max_daily_loss_exceeded")
        if amount > cash * 0.2:
            warnings.append("large_order_warning")
        if projected_ratio > float(conf.get("max_position_ratio", 0.3)) * 0.8:
            warnings.append("position_ratio_warning")

        if channel == "live":
            live_gray = bool(conf.get("live_gray_mode_enabled", True))
            if auto_submit and not bool(conf.get("live_auto_submit", False)):
                manual.append("auto_submit_disabled")
            if live_gray:
                whitelist = self._to_symbol_set(conf.get("live_gray_whitelist"))
                blocklist = self._to_symbol_set(conf.get("live_gray_blocklist"))
                gray_max = float(conf.get("live_gray_max_notional", 50000))
                if symbol in blocklist:
                    hard.append("live_gray_blocklist_symbol")
                if whitelist and symbol not in whitelist:
                    manual.append("live_gray_symbol_not_whitelisted")
                if side == "buy" and amount > gray_max:
                    manual.append("live_gray_notional_exceeded")

        if hard:
            decision = "reject"
        elif manual:
            decision = "manual_review_required"
        elif warnings:
            decision = "pass_with_warning"
        else:
            decision = "pass"

        event = RiskEvent(
            event_type=f"{channel}_order_preview",
            level="critical" if decision == "reject" else "warning" if warnings else "info",
            summary=f"decision={decision}",
            detail=json.dumps(
                {"symbol": symbol, "side": side, "amount": amount, "channel": channel, "manual_ack": manual_ack},
                ensure_ascii=True,
            ),
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
            "risk_context": {
                "cash": cash,
                "total_assets": total_assets,
                "position_qty": current_qty,
                "trade_count_today": trade_count,
                "channel": channel,
                "manual_ack": manual_ack,
                "auto_submit": auto_submit,
            },
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
