"""FastAPI 主应用入口。"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.api_routes import router as market_router, start_background_warmup
from core.compat_routes import router as compat_router
from core.data_manager import init_db

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]


def _get_allowed_origins() -> list[str]:
    raw = str(os.environ.get("ASTOCK_ALLOWED_ORIGINS", "")).strip()
    if not raw:
        return list(DEFAULT_ALLOWED_ORIGINS)
    if raw == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.environ.get("DISABLE_STARTUP_JOBS") != "1":
        start_background_warmup(force_sync=False)
    yield



def create_app() -> FastAPI:
    app = FastAPI(
        title="A 股数据引擎 API",
        description="基于 SQLite 缓存的 A 股市场数据服务，支持历史 K 线、基本面数据、选股器等功能",
        version="2.0.0",
        lifespan=lifespan,
    )

    allowed_origins = _get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=(allowed_origins != ["*"]),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(market_router)
    app.include_router(compat_router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def root():
        """首页 - 返回管理页面。"""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/quote")
    async def quote_page():
        """行情中心页面。"""
        return FileResponse(STATIC_DIR / "quote.html")

    @app.get("/chart")
    async def chart_page():
        """K 线图页面。"""
        return FileResponse(STATIC_DIR / "chart.html")

    @app.get("/screener")
    async def screener_page():
        """选股器页面。"""
        return FileResponse(STATIC_DIR / "screener.html")

    @app.get("/strategy")
    async def strategy_page():
        """战法选股页面。"""
        return FileResponse(STATIC_DIR / "strategy.html")

    @app.get("/data")
    async def data_page():
        """数据中心页面。"""
        return FileResponse(STATIC_DIR / "data.html")

    @app.get("/ops")
    async def ops_page():
        """系统维护页面。"""
        return FileResponse(STATIC_DIR / "ops.html")

    @app.get("/api/health")
    async def health_check():
        """健康检查接口。"""
        return {"status": "healthy", "service": "a-share-data-engine"}

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("ASTOCK_HOST", "0.0.0.0")
    port = int(os.environ.get("ASTOCK_PORT", "8080"))
    reload_enabled = os.environ.get("ASTOCK_RELOAD", "0") == "1"
    uvicorn.run("core.main:app", host=host, port=port, reload=reload_enabled)
