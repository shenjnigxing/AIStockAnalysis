"""Account integration *contract*, without accounts, credentials, persistence or HTTP.

This file is safe to use during statement-adapter development. It deliberately
does not claim any Eastmoney broker API, CSV column mapping or live connection.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Literal

ACCOUNT_PROVIDERS = {
    "eastmoney_securities": {
        "display_name": "东方财富证券", "type": "securities",
        "connection_mode": "statement_schema_pending", "automatic_connection": False,
        "positions_supported": ("cn_equity", "cn_etf", "cn_fund"),
        "currency": "CNY",
    },
    "eastmoney_futures": {
        "display_name": "东方财富期货", "type": "futures",
        "connection_mode": "statement_schema_pending", "automatic_connection": False,
        "positions_supported": ("cn_commodity_future", "cn_financial_future"),
        "currency": "CNY",
    },
    "okx": {
        "display_name": "欧易 OKX", "type": "digital_assets",
        "connection_mode": "private_api_not_connected", "automatic_connection": False,
        "positions_supported": ("crypto_spot", "tokenized_equity", "crypto_derivative"),
        "currency": "MIXED",
    },
}

PRODUCT_CLASSES = {name: set(provider["positions_supported"])
                   for name, provider in ACCOUNT_PROVIDERS.items()}
QUANTITY_UNITS = {
    "cn_equity": "shares", "cn_etf": "shares", "cn_fund": "shares",
    "cn_commodity_future": "contracts", "cn_financial_future": "contracts",
    "crypto_spot": "token", "tokenized_equity": "token",
    "crypto_derivative": "contracts",
}
DERIVATIVES = {"cn_commodity_future", "cn_financial_future", "crypto_derivative"}


class AccountContractError(ValueError):
    pass


@dataclass(frozen=True)
class AccountPositionObservation:
    provider: str
    instrument_id: str
    product_class: str
    side: Literal["long", "short"]
    quantity: str
    quantity_unit: str
    price_currency: str
    as_of: str
    contract_multiplier: str | None
    margin_amount: str | None


def account_provider_capabilities() -> dict[str, Any]:
    """Public catalog contains *no identity, account number or secret*."""
    return {
        "providers": [
            {"provider": p, "display_name": spec["display_name"],
             "account_type": spec["type"],
             "connection_mode": spec["connection_mode"],
             "automatic_connection": False,
             "supported_product_classes": list(spec["positions_supported"])}
            for p, spec in ACCOUNT_PROVIDERS.items()
        ],
        "has_connected_accounts": False,
        "can_import_statements": False,  # broker-specific schemas still unverified
        "private_positions_endpoint_enabled": False,
        "warnings": [
            "No broker account read-only API has been verified for Eastmoney retail users.",
            "Account credentials, security codes and account statements are not collected.",
            "US market observation does not imply a US brokerage account.",
        ],
    }


def _decimal(value: Any, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AccountContractError("Invalid numeric position field") from exc
    if not result.is_finite() or (positive and result <= 0) or (not positive and result < 0):
        raise AccountContractError("Negative/non-finite position field")
    return result


def normalize_private_positions(provider: str, rows: list[dict[str, Any]]) -> tuple[str, list[AccountPositionObservation]]:
    """For offline/private adapters only. No broker-specific CSV column guessing.

    Accepts already-mapped anonymous normalized rows, not raw statements.
    Output excludes account number, full name, IDs and any unrecognized metadata.
    """
    if provider not in ACCOUNT_PROVIDERS:
        raise AccountContractError("Unsupported account provider")
    if not (1 <= len(rows) <= 500):
        raise AccountContractError("Invalid position count")
    accepted_keys = {
        "instrument_id", "product_class", "side", "quantity",
        "price_currency", "as_of", "contract_multiplier", "margin_amount",
    }
    normalized: list[AccountPositionObservation] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - accepted_keys:
            raise AccountContractError("Unrecognized field; never accept identity or credentials")
        pclass = row.get("product_class")
        if pclass not in PRODUCT_CLASSES[provider]:
            raise AccountContractError("Product is incompatible with the selected account")
        symbol = row.get("instrument_id")
        if not isinstance(symbol, str) or not (1 <= len(symbol) <= 40) or not all(
            c.isascii() and (c.isalnum() or c in "_-.") for c in symbol
        ):
            raise AccountContractError("Invalid instrument identifier")
        side = row.get("side")
        if side not in ("long", "short"):
            raise AccountContractError("Explicit long/short side required")
        if pclass not in DERIVATIVES and side == "short":
            raise AccountContractError("Short cash holdings require separately verified margin permissions")
        currency = row.get("price_currency")
        if currency not in ("CNY", "USD", "HKD", "USDT", "USDC"):
            raise AccountContractError("Unsupported currency")
        if provider != "okx" and currency != "CNY":
            raise AccountContractError("Domestic account currency mismatch")
        asof = row.get("as_of")
        if not isinstance(asof, str):
            raise AccountContractError("Missing statement as_of")
        try:
            from datetime import date
            if date.fromisoformat(asof) > date.today():
                raise ValueError("Future statement")
        except ValueError as exc:
            raise AccountContractError("Invalid or future statement date") from exc
        quantity = _decimal(row.get("quantity"), positive=True)
        multiplier, margin = row.get("contract_multiplier"), row.get("margin_amount")
        if pclass in DERIVATIVES:
            multiplier = _decimal(multiplier, positive=True)
            margin = _decimal(margin)
        elif multiplier is not None or margin is not None:
            raise AccountContractError("Non-derivative holding must not have futures margin fields")
        identity = (provider, pclass, symbol, side, asof)
        if identity in seen:
            raise AccountContractError("Duplicate normalized position")
        seen.add(identity)
        normalized.append(AccountPositionObservation(
            provider=provider, instrument_id=symbol, product_class=pclass,
            side=side, quantity=str(quantity), quantity_unit=QUANTITY_UNITS[pclass],
            price_currency=currency, as_of=asof,
            contract_multiplier=str(multiplier) if multiplier is not None else None,
            margin_amount=str(margin) if margin is not None else None,
        ))
    payload = [x.__dict__ for x in sorted(normalized, key=lambda x: (x.as_of, x.product_class, x.instrument_id, x.side))]
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, normalized
