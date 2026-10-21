"""No private account API; test strictly private normalized statement boundaries."""
from datetime import date
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.account_import_contracts import (
    AccountContractError, normalize_private_positions,
)

client=TestClient(app)

def row(kind="cn_equity", **extra):
    base={"instrument_id":"600000", "product_class":kind, "side":"long",
          "quantity":"100", "price_currency":"CNY", "as_of":"2026-10-20"}
    if kind in ("cn_commodity_future","cn_financial_future"):
        base.update(instrument_id="AU2612",contract_multiplier="1000",margin_amount="23000")
    base.update(extra)
    return base

def test_account_catalog_has_no_live_connection_or_user_identity():
    response=client.get("/api/research/v3/accounts/capabilities")
    assert response.status_code==200,response.text
    body=response.json()
    assert {p["provider"] for p in body["providers"]}=={
        "eastmoney_securities","eastmoney_futures","okx"}
    assert body["private_positions_endpoint_enabled"] is False
    assert body["can_import_statements"] is False
    assert all(not p["automatic_connection"] for p in body["providers"])
    assert "account_number" not in str(body).lower()

def test_eastmoney_equity_and_futures_stay_separate():
    h,eq=normalize_private_positions("eastmoney_securities",[row()])
    assert len(h)==64 and eq[0].quantity_unit=="shares"
    f,fu=normalize_private_positions("eastmoney_futures",
        [row("cn_commodity_future")])
    assert len(f)==64 and fu[0].quantity_unit=="contracts"
    assert fu[0].margin_amount=="23000"
    assert h!=f

def test_okx_tokenized_equity_distinct_from_us_common_share():
    h,positions=normalize_private_positions("okx",[{
        "instrument_id":"XTSLA-USDT","product_class":"tokenized_equity",
        "side":"long","quantity":"2.4","price_currency":"USDT",
        "as_of":"2026-10-20"}])
    assert len(h)==64
    assert positions[0].product_class=="tokenized_equity"
    assert positions[0].quantity_unit=="token"
    with pytest.raises(AccountContractError):
        normalize_private_positions("eastmoney_securities",[row("tokenized_equity")])

@pytest.mark.parametrize("change",[
    {"account_number":"123456"},
    {"password":"secret"},
    {"quantity":"NaN"},
    {"quantity":"-12"},
    {"side":"short"},
    {"price_currency":"USD"},
    {"as_of":"2099-01-01"},
    {"instrument_id":"../../foo"},
])
def test_private_sensitive_or_invalid_fields_rejected(change):
    with pytest.raises(AccountContractError):
        normalize_private_positions("eastmoney_securities",[row(**change)])

def test_derivative_needs_margin_and_multiplier():
    with pytest.raises(AccountContractError):
        normalize_private_positions("eastmoney_futures",[row("cn_commodity_future",margin_amount=None)])
    with pytest.raises(AccountContractError):
        normalize_private_positions("eastmoney_futures",[row("cn_commodity_future",contract_multiplier=0)])

def test_fingerprint_deterministic_independent_of_row_order():
    a=row()
    b=row(instrument_id="159915",product_class="cn_etf")
    digest1,_=normalize_private_positions("eastmoney_securities",[a,b])
    digest2,_=normalize_private_positions("eastmoney_securities",[b,a])
    assert digest1==digest2
    with pytest.raises(AccountContractError):
        normalize_private_positions("eastmoney_securities",[a,a])
