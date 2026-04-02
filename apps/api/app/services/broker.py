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
    provider: str = "base"

    def provider_name(self) -> str:
        return self.provider

    def capabilities(self) -> dict:
        return {
            "provider": self.provider_name(),
            "ready": False,
            "supports": {
                "preview_order": False,
                "place_order": False,
                "cancel_order": False,
                "query_assets": False,
                "query_positions": False,
                "query_orders": False,
                "query_trades": False,
            },
        }

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
    provider = "mock"

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

    def capabilities(self) -> dict:
        return {
            "provider": self.provider_name(),
            "ready": True,
            "supports": {
                "preview_order": True,
                "place_order": True,
                "cancel_order": True,
                "query_assets": True,
                "query_positions": True,
                "query_orders": True,
                "query_trades": True,
            },
            "note": "mock broker for local simulation",
        }


class EastMoneyAdapter(BrokerBase):
    provider = "eastmoney"

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

    def capabilities(self) -> dict:
        return {
            "provider": self.provider_name(),
            "ready": False,
            "supports": {
                "preview_order": True,
                "place_order": False,
                "cancel_order": False,
                "query_assets": False,
                "query_positions": False,
                "query_orders": False,
                "query_trades": False,
            },
            "required_fields": ["broker account", "session token", "signature config"],
            "note": "phase6 skeleton only, no private protocol implemented",
        }


def get_broker(provider: str | None = None) -> BrokerBase:
    target = (provider or settings.broker_provider).lower().strip()
    if target == "eastmoney":
        return EastMoneyAdapter()
    return MockBroker()
