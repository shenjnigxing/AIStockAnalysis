"""Local research notebook. Notes never become numerical signals or orders."""
import os
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.db.models import ResearchWatchItem
from app.services.public_quote_cache import validate_identity

router = APIRouter()


def local_request(request: Request):
    origin = request.headers.get('origin')
    host = request.headers.get('host', '')
    try:
        parsed_host = urlparse('http://' + host)
        hostname = parsed_host.hostname
        parsed_origin = urlparse(origin) if origin else None
        if parsed_origin:
            _ = parsed_origin.port
    except ValueError:
        raise HTTPException(403, 'Invalid host or origin')
    allowed_hosts = {'localhost', '127.0.0.1', '::1'}
    allowed_hosts.update(x.strip() for x in os.getenv('AISTOCK_NOTEBOOK_HOSTS', '').split(',') if x.strip())
    if os.getenv('APP_ENV') == 'test': allowed_hosts.add('testserver')
    if hostname not in allowed_hosts:
        raise HTTPException(403, 'Notebook is local-only')
    expected_origins = {x.strip() for x in os.getenv('AISTOCK_WEB_ORIGIN', 'http://localhost:3000,http://127.0.0.1:3000').split(',')}
    if parsed_origin and (parsed_origin.scheme not in ('http', 'https') or
            (origin not in expected_origins and parsed_origin.netloc != host)):
        raise HTTPException(403, 'Cross-origin notebook access rejected')
    if request.method != 'GET':
        if not origin or request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise HTTPException(403, 'Same-origin JSON required')


class WatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=32)
    thesis: str = Field(default='', max_length=8000)
    counter_thesis: str = Field(default='', max_length=8000)
    invalidation: str = Field(default='', max_length=8000)
    sector: str = Field(default='', max_length=100)
    horizon: Literal['short', 'medium_long'] = 'medium_long'


class WatchPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    thesis: str | None = Field(default=None, max_length=8000)
    counter_thesis: str | None = Field(default=None, max_length=8000)
    invalidation: str | None = Field(default=None, max_length=8000)
    sector: str | None = Field(default=None, max_length=100)
    horizon: Literal['short', 'medium_long'] | None = None


def output(row):
    return {**{k: getattr(row, k) for k in ('id','kind','symbol','thesis','counter_thesis','invalidation','sector','horizon')},
            'updated_at': row.updated_at.isoformat()+'Z', 'source_grade': 'user_note_unverified', 'can_trade': False}


@router.get('', dependencies=[Depends(local_request)])
def items(db: Session = Depends(get_db)):
    return {'items': [output(r) for r in db.scalars(select(ResearchWatchItem).order_by(ResearchWatchItem.updated_at.desc()).limit(500))]}


@router.post('', dependencies=[Depends(local_request)], status_code=201)
def create(payload: WatchInput, db: Session = Depends(get_db)):
    try: validate_identity(payload.kind, payload.symbol)
    except ValueError as exc: raise HTTPException(422, 'Unsupported instrument') from exc
    if db.scalar(select(func.count()).select_from(ResearchWatchItem)) >= 500:
        raise HTTPException(409, 'Notebook limit is 500 records')
    row = ResearchWatchItem(**payload.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return output(row)


@router.patch('/{item_id}', dependencies=[Depends(local_request)])
def update(item_id: int, payload: WatchPatch, db: Session = Depends(get_db)):
    row = db.get(ResearchWatchItem, item_id)
    if row is None: raise HTTPException(404, 'Note not found')
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()): raise HTTPException(422, 'Note fields cannot be null')
    for key, value in values.items(): setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit(); db.refresh(row)
    return output(row)


@router.delete('/{item_id}', dependencies=[Depends(local_request)])
def delete(item_id: int, db: Session = Depends(get_db)):
    row = db.get(ResearchWatchItem, item_id)
    if row is None: raise HTTPException(404, 'Note not found')
    db.delete(row); db.commit()
    return {'deleted': True}
