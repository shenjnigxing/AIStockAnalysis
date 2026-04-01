import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
if settings.database_url.startswith("sqlite:///"):
    db_file = settings.database_url.replace("sqlite:///", "", 1)
    db_dir = os.path.dirname(db_file)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
