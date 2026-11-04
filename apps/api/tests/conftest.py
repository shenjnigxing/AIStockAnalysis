# Test database policy must run before importing any application engine.
import os
import sys

_requested_url = os.environ.get("DATABASE_URL")
if _requested_url not in (None, "", "sqlite:///:memory:"):
    raise RuntimeError("Refusing destructive tests: DATABASE_URL must be sqlite:///:memory:")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
if "app.db.session" in sys.modules:
    _existing = sys.modules["app.db.session"].engine
    if str(_existing.url) != "sqlite:///:memory:":
        raise RuntimeError("Application database was imported before test isolation; refusing tests")

import pytest

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.init_db import init_db


@pytest.fixture(autouse=True)
def reset_db(monkeypatch) -> None:
    # Legacy tests explicitly exercise the original deterministic demo pipeline.
    # Production/default mode must never silently synthesize market data.
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    monkeypatch.setenv("APP_ENV", "test")
    init_db()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

