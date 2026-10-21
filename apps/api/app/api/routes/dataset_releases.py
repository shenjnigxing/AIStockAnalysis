"""Admin-only, fail-closed ingestion and read-only release provenance APIs."""
from datetime import date, datetime
import hmac
import os
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.dataset_releases import (
    DatasetIntegrityError, DatasetValidationError,
    dataset_readiness, get_dataset_release, ingest_equity_or_etf_daily, list_dataset_releases,
)
from app.services.dataset_sources import UpstreamDataError

router = APIRouter()


class DailyIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["equity", "etf"]
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_window(self):
        if self.kind == "equity" and self.symbol[0] not in "03468":
            raise ValueError("Not an allowed A-share symbol")
        if self.kind == "etf" and self.symbol[0] not in "15":
            raise ValueError("Not an allowed listed ETF symbol")
        last_complete_day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if self.start_date > self.end_date or self.end_date >= last_complete_day:
            raise ValueError("Only closed historical dates strictly before today are supported")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Request window exceeds 366 days")
        return self


def _require_admin(token: str | None = Header(default=None, alias="X-Research-Admin-Token")) -> None:
    secret = os.getenv("AISTOCK_RESEARCH_INGEST_TOKEN", "")
    if not secret or len(secret) < 20:
        raise HTTPException(status_code=503, detail="Research ingestion disabled by server configuration")
    if token is None or not hmac.compare_digest(token.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="Research ingestion not authorized")


@router.post("/equity-daily/sync", dependencies=[Depends(_require_admin)])
def ingest_daily(payload: DailyIngestRequest, db: Session = Depends(get_db)):
    try:
        return ingest_equity_or_etf_daily(db, kind=payload.kind, symbol=payload.symbol,
                                           start=payload.start_date, end=payload.end_date)
    except (UpstreamDataError, DatasetValidationError) as exc:
        # Never expose provider errors containing credentials, hosts or tracebacks.
        raise HTTPException(status_code=422 if isinstance(exc, DatasetValidationError) else 502,
                            detail="Provider response rejected or unavailable; no dataset released") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Recorded release integrity violation") from exc


@router.get("/readiness")
def readiness(db: Session = Depends(get_db)):
    return dataset_readiness(db)


@router.get("/releases")
def releases(limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db)):
    return list_dataset_releases(db, limit=limit)


@router.get("/releases/{release_id}")
def release_detail(release_id: int, db: Session = Depends(get_db)):
    if release_id < 1:
        raise HTTPException(status_code=404, detail="Release not found")
    try:
        return get_dataset_release(db, release_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Release not found") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Recorded release integrity violation") from exc
