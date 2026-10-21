"""V3 experimental multi-asset REST contract. No brokerage, outbound HTTP or email."""
from datetime import date
from typing import Any, Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.multi_asset_research import VERSION, evaluate_multi_asset

router = APIRouter()

VEHICLES: dict[str, set[str]] = {
    "equity": {"common_stock"},
    "precious_metal": {"physical", "exchange_spot", "bank_paper", "leveraged_deferred"},
    "fund": {"etf", "open_end"},
    "futures": {"commodity_future", "financial_future", "treasury_future", "continuous"},
    "treasury": {"cash_bond"},
}


class ResearchPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    close: float = Field(gt=0, allow_inf_nan=False)


class InstrumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_st: bool | None = None
    suspended: bool | None = None
    turnover_amount_yi: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    bid_ask_spread_bps: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    annual_fee_pct: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    premium_discount_pct: float | None = Field(default=None, ge=-100, le=100, allow_inf_nan=False)
    nav_published_on: date | None = None
    expiry: date | None = None
    contract_multiplier: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    margin_ratio: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    yield_to_maturity_pct: float | None = Field(default=None, ge=-10, le=30, allow_inf_nan=False)
    modified_duration: float | None = Field(default=None, ge=0, le=40, allow_inf_nan=False)


class InstrumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=36, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=80)
    asset_class: Literal["equity", "precious_metal", "fund", "futures", "treasury"]
    product_type: str = Field(min_length=1, max_length=40)
    currency: Literal["CNY", "USD", "HKD", "EUR"]
    prices: list[ResearchPrice] = Field(min_length=26, max_length=300)
    metadata: InstrumentMetadata

    @model_validator(mode="after")
    def validate_vehicle(self):
        if self.product_type not in VEHICLES[self.asset_class]:
            raise ValueError("Invalid product_type for asset_class")
        m = self.metadata
        requirements = {
            "equity": {"is_st", "suspended", "turnover_amount_yi"},
            "fund": {"annual_fee_pct", "nav_published_on"} if self.product_type == "open_end"
                    else {"annual_fee_pct", "premium_discount_pct"},
            "futures": {"expiry", "contract_multiplier", "margin_ratio"},
            "treasury": {"yield_to_maturity_pct", "modified_duration"},
        }
        required = requirements.get(self.asset_class, set())
        if self.asset_class == "precious_metal" and self.product_type == "bank_paper":
            required = {"bid_ask_spread_bps"}
        missing = [key for key in required if getattr(m, key) is None]
        if missing:
            raise ValueError("Missing asset-specific metadata: " + ", ".join(sorted(missing)))
        return self


class MultiAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: date
    horizon: Literal["short", "medium_long"]
    source: Literal["synthetic_demo", "manual_unverified"]
    instruments: list[InstrumentInput] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_snapshots(self):
        if self.as_of > date.today():
            raise ValueError("Research as_of cannot be in the future")
        minimum = 26 if self.horizon == "short" else 121
        seen = set()
        for item in self.instruments:
            key = (item.asset_class, item.product_type, item.symbol)
            if key in seen:
                raise ValueError("Duplicate asset identity in request")
            seen.add(key)
            if len(item.prices) < minimum:
                raise ValueError("Insufficient observations for selected horizon")
            dates = [p.date for p in item.prices]
            if dates != sorted(set(dates)):
                raise ValueError("Price dates must be unique and strictly increasing")
            if dates[-1] > self.as_of:
                raise ValueError("Historical prices cannot be later than as_of")
            if item.asset_class == "fund" and item.product_type == "open_end":
                published = item.metadata.nav_published_on
                if published is None or published < dates[-1] or published > self.as_of:
                    raise ValueError("Fund NAV must be publicly available by as_of")
            elif dates[-1] != self.as_of:
                raise ValueError("Last price date must equal as_of for this asset")
        return self


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "engine_version": VERSION, "mode": "read_only_experimental",
        "asset_classes": list(VEHICLES), "horizons": ["short", "medium_long"],
        "verified_market_data": False, "validated_alpha": False,
        "notifications_enabled": False, "can_trade": False,
        "source_modes": ["synthetic_demo", "manual_unverified"],
        "warning": "No real market-data recommendation or external delivery until PIT and OOS gates pass.",
    }


@router.post("/evaluate")
def evaluate(payload: MultiAssetRequest) -> dict[str, Any]:
    return evaluate_multi_asset(
        as_of=payload.as_of, horizon=payload.horizon, source=payload.source,
        instruments=[item.model_dump() for item in payload.instruments],
    )


class ReportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research: MultiAssetRequest
    channels: list[Literal["wecom", "email"]] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def unique_channels(self):
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("Duplicate preview channels")
        return self


@router.post("/notifications/preview")
def preview_report(payload: ReportPreviewRequest) -> dict[str, Any]:
    study = evaluate_multi_asset(
        as_of=payload.research.as_of, horizon=payload.research.horizon,
        source=payload.research.source,
        instruments=[item.model_dump() for item in payload.research.instruments],
    )
    rows = sum(len(g["items"]) for g in study["groups"])
    blocked = sum(item["status"] == "blocked" for group in study["groups"] for item in group["items"])
    summary = (
        f"AIStock 多资产研究预览｜{study['as_of']}｜{study['horizon']}\n"
        f"数据等级：{study['source_grade']}，模型尚未样本外验证。\n"
        f"涉及 {len(study['groups'])} 类可比小组、{rows} 个样本，风险阻断 {blocked} 个。\n"
        "只用于演示研究流程，不能据此买卖或发送真实市场提醒。"
    )
    return {
        "report_fingerprint": study["input_sha256"],
        "delivery_allowed": False,
        "channels": [{"channel": name, "status": "preview_only", "message": summary}
                     for name in payload.channels],
        "reason": "Data is unverified and strategy is not OOS validated; no recipient, credential or send operation is accepted.",
    }
