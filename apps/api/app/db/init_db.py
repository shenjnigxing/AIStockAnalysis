from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    # Import models before metadata create_all.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

