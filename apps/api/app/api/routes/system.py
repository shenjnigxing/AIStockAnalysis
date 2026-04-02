from fastapi import APIRouter
from sqlalchemy import desc, select

from app.db.models import SyncJob
from app.db.session import SessionLocal

from app.core.config import settings

router = APIRouter()


@router.get("/status")
def get_system_status() -> dict:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "broker_provider": settings.broker_provider,
        "llm_provider": settings.llm_provider,
    }


@router.get("/config-check")
def get_config_check() -> dict:
    return {
        "app_env": settings.app_env,
        "postgres": {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
        },
        "redis": {
            "host": settings.redis_host,
            "port": settings.redis_port,
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_openai_model,
            "base_url": settings.llm_openai_base_url,
            "api_key_configured": bool(settings.llm_openai_api_key),
        },
    }


@router.get("/data/status")
def get_data_status() -> dict:
    with SessionLocal() as db:
        last_job = db.scalar(select(SyncJob).order_by(desc(SyncJob.created_at)))
        return {
            "provider": settings.market_data_provider,
            "last_sync_job": {
                "id": last_job.id if last_job else None,
                "job_type": last_job.job_type if last_job else None,
                "status": last_job.status if last_job else "never_run",
            },
        }
