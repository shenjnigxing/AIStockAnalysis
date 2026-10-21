from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.backtest import router as backtest_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.data import router as data_router
from app.api.routes.init import router as init_router
from app.api.routes.live import router as live_router
from app.api.routes.notifications import router as notification_router
from app.api.routes.paper import router as paper_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.research_v2 import router as research_v2_router
from app.api.routes.research_v3 import router as research_v3_router
from app.api.routes.dataset_releases import router as dataset_releases_router
from app.api.routes.public_market_data import router as public_market_data_router
from app.api.routes.account_sources import router as account_sources_router
from app.api.routes.replay import router as replay_router
from app.api.routes.risk import router as risk_router
from app.api.routes.screener import router as screener_router
from app.api.routes.settings import router as settings_router
from app.api.routes.strategy import router as strategy_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router, prefix="/api/system", tags=["system"])
api_router.include_router(data_router, prefix="/api/data", tags=["data"])
api_router.include_router(init_router, prefix="/api/init", tags=["init"])
api_router.include_router(screener_router, prefix="/api/screener", tags=["screener"])
api_router.include_router(candidates_router, prefix="/api/candidates", tags=["candidates"])
api_router.include_router(strategy_router, prefix="/api/strategy", tags=["strategy"])
api_router.include_router(recommendation_router, prefix="/api/recommendation", tags=["recommendation"])
api_router.include_router(research_v2_router, prefix="/api/research/v2", tags=["research-v2"])
api_router.include_router(research_v3_router, prefix="/api/research/v3", tags=["research-v3"])
api_router.include_router(dataset_releases_router, prefix="/api/research/v3/datasets", tags=["dataset-releases"])
api_router.include_router(public_market_data_router, prefix="/api/research/v3/market-data", tags=["public-quote-cache"])
api_router.include_router(account_sources_router, prefix="/api/research/v3/accounts", tags=["account-capabilities"])
api_router.include_router(backtest_router, prefix="/api/backtest", tags=["backtest"])
api_router.include_router(paper_router, prefix="/api/paper", tags=["paper"])
api_router.include_router(risk_router, prefix="/api/risk", tags=["risk"])
api_router.include_router(live_router, prefix="/api/live", tags=["live"])
api_router.include_router(notification_router, prefix="/api/notifications", tags=["notification"])
api_router.include_router(settings_router, prefix="/api/settings", tags=["settings"])
api_router.include_router(replay_router, prefix="/api/replay", tags=["replay"])
api_router.include_router(admin_router, prefix="/api/admin", tags=["admin"])
