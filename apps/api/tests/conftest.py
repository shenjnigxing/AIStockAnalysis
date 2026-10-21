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

