from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings


@dataclass
class BrokerOrderResult:
    status: str
    broker_order_id: str
    detail: dict


class BrokerBase:
    def preview_order(self, payload: dict) -> dict:
        raise NotImplementedError

    def place_order(self, payload: dict) -> BrokerOrderResult:
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str) -> dict:
        raise NotImplementedError

    def query_assets(self) -> dict:
        raise NotImplementedError

    def query_positions(self) -> list[dict]:
        raise NotImplementedError

    def query_orders(self) -> list[dict]:
        raise NotImplementedError

    def query_trades(self) -> list[dict]:
        raise NotImplementedError

    def ping(self) -> dict:
        return {"status": "ok", "time": datetime.utcnow().isoformat()}


class MockBroker(BrokerBase):
    def preview_order(self, payload: dict) -> dict:
        return {"status": "ok", "estimated_cost": round(payload["price"] * payload["quantity"], 2)}

    def place_order(self, payload: dict) -> BrokerOrderResult:
        return BrokerOrderResult(
            status="accepted",
            broker_order_id=f"mock-{int(datetime.utcnow().timestamp())}",
            detail={"payload": payload},
        )

    def cancel_order(self, broker_order_id: str) -> dict:
        return {"status": "cancelled", "broker_order_id": broker_order_id}

    def query_assets(self) -> dict:
        return {"cash": 500000.0, "market_value": 200000.0, "total_assets": 700000.0}

    def query_positions(self) -> list[dict]:
        return [{"symbol": "600519", "quantity": 100, "avg_price": 1600.0}]

    def query_orders(self) -> list[dict]:
        return []

    def query_trades(self) -> list[dict]:
        return []


class EastMoneyAdapter(BrokerBase):
    # Placeholder only for later integration.
    def preview_order(self, payload: dict) -> dict:
        return {"status": "not_implemented", "message": "eastmoney adapter placeholder"}

    def place_order(self, payload: dict) -> BrokerOrderResult:
        return BrokerOrderResult(status="rejected", broker_order_id="N/A", detail={"reason": "not_implemented"})

    def cancel_order(self, broker_order_id: str) -> dict:
        return {"status": "not_implemented", "broker_order_id": broker_order_id}

    def query_assets(self) -> dict:
        return {"status": "not_implemented"}

    def query_positions(self) -> list[dict]:
        return []

    def query_orders(self) -> list[dict]:
        return []

    def query_trades(self) -> list[dict]:
        return []


def get_broker(provider: str | None = None) -> BrokerBase:
    target = (provider or settings.broker_provider).lower().strip()
    if target == "eastmoney":
        return EastMoneyAdapter()
    return MockBroker()
