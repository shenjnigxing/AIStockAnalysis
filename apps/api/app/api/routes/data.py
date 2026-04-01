import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.data_sync import (
    JobResponse,
    SyncDailyRequest,
    SyncMasterRequest,
    SyncMinuteRequest,
    SyncRealtimeRequest,
)
from app.services.data_sync import DataSyncService

router = APIRouter()


def _job_to_response(job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        result=json.loads(job.result_json or "{}"),
        error_message=job.error_message or None,
    )


@router.post("/sync/master", response_model=JobResponse)
def sync_master(payload: SyncMasterRequest, db: Session = Depends(get_db)) -> JobResponse:
    service = DataSyncService(db)
    job = service.sync_master(force_full=payload.force_full)
    return _job_to_response(job)


@router.post("/sync/daily", response_model=JobResponse)
def sync_daily(payload: SyncDailyRequest, db: Session = Depends(get_db)) -> JobResponse:
    service = DataSyncService(db)
    job = service.sync_daily(symbols=payload.symbols, start_date=payload.start_date, end_date=payload.end_date)
    return _job_to_response(job)


@router.post("/sync/minute", response_model=JobResponse)
def sync_minute(payload: SyncMinuteRequest, db: Session = Depends(get_db)) -> JobResponse:
    service = DataSyncService(db)
    job = service.sync_minute(symbols=payload.symbols, start_time=payload.start_time, end_time=payload.end_time)
    return _job_to_response(job)


@router.post("/sync/realtime", response_model=JobResponse)
def sync_realtime(payload: SyncRealtimeRequest, db: Session = Depends(get_db)) -> JobResponse:
    service = DataSyncService(db)
    job = service.sync_realtime(symbols=payload.symbols)
    return _job_to_response(job)


@router.get("/jobs")
def list_jobs(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    service = DataSyncService(db)
    jobs = [_job_to_response(job).model_dump() for job in service.list_jobs(limit=limit)]
    return {"items": jobs, "count": len(jobs)}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    service = DataSyncService(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_response(job).model_dump()


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    service = DataSyncService(db)
    job = service.retry_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_response(job).model_dump()


@router.get("/quality/issues")
def list_quality_issues(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    service = DataSyncService(db)
    items = [
        {
            "id": issue.id,
            "issue_type": issue.issue_type,
            "symbol": issue.symbol,
            "detail": issue.detail,
            "created_at": issue.created_at.isoformat(),
        }
        for issue in service.list_quality_issues(limit=limit)
    ]
    return {"items": items, "count": len(items)}

