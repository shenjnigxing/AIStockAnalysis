from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import os
import sys

from fastapi import FastAPI
from fastapi import Request

try:
    from app.api.routes import api_router
    from app.core.config import settings
    from app.core.request_context import set_request_id
    from app.db.init_db import init_db
except ModuleNotFoundError as exc:
    # Support direct execution: `python app/main.py`
    if exc.name and exc.name.startswith("app"):
        api_root = Path(__file__).resolve().parents[1]
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))
        from app.api.routes import api_router
        from app.core.config import settings
        from app.core.request_context import set_request_id
        from app.db.init_db import init_db
    else:
        raise

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(api_router)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    return {"version": settings.app_version}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
