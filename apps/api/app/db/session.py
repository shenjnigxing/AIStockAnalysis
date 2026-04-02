import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs: dict = {"future": True, "connect_args": connect_args}

if settings.database_url.startswith("sqlite:///:memory:"):
    # Use a single shared in-memory connection so tests and app sessions see the same schema/data.
    engine_kwargs["poolclass"] = StaticPool
elif settings.database_url.startswith("sqlite:///"):
    db_file = settings.database_url.replace("sqlite:///", "", 1)
    db_dir = os.path.dirname(db_file)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
