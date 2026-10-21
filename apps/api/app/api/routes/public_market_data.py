"""Read-only quote cache API and separately authenticated, bounded refresh."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.api.routes.dataset_releases import _require_admin
from app.services.public_quote_cache import (
    QuoteBusy, QuoteUnavailable, QuoteIntegrityError, cached_quote, quote_status, refresh_quote,
)
router = APIRouter()
QuoteKind = Literal["equity","etf","sge_gold","futures","treasury_10y","us_equity","us_etf","okx_stock_token"]


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: QuoteKind
    symbol: str = Field(min_length=1, max_length=32)


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    return quote_status(db)


@router.get("/quote")
def quote(kind: QuoteKind = Query(), symbol: str = Query(min_length=1,max_length=32),
          db: Session=Depends(get_db)):
    try:
        result = cached_quote(db, kind=kind, symbol=symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported quote instrument") from exc
    except QuoteIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Cached quote integrity violation") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="No cached source quote; admin refresh required")
    return result


@router.post("/refresh", dependencies=[Depends(_require_admin)])
def refresh(payload: RefreshRequest, db: Session=Depends(get_db)):
    try:
        return refresh_quote(db, kind=payload.kind, symbol=payload.symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported quote instrument") from exc
    except QuoteIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Cached quote integrity violation") from exc
    except QuoteBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except QuoteUnavailable as exc:
        raise HTTPException(status_code=502, detail="Public provider failed or exceeded timeout; no new quote was published") from exc
