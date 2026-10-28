"""Local administrator boundary, separate from market-data ingestion authority."""
import hmac
import os
from fastapi import Header, HTTPException


def require_admin(x_aistock_admin_token: str | None = Header(default=None)) -> None:
    if (os.getenv('APP_ENV', 'dev').lower() == 'test'
            and os.getenv('MARKET_DATA_MODE', 'real').lower() == 'mock'):
        return
    expected = os.getenv('AISTOCK_ADMIN_TOKEN', '')
    if len(expected) < 32:
        raise HTTPException(503, 'Local administration is not configured')
    supplied = x_aistock_admin_token or ''
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(403, 'Administrator authorization required')
