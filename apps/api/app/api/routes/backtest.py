import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.backtest import BacktestService

router = APIRouter()


@router.post("/run")
def run_backtest(payload: dict, db: Session = Depends(get_db)) -> dict:
    service = BacktestService(db)
    job = service.run(payload)
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs")
def backtest_jobs(db: Session = Depends(get_db)) -> dict:
    rows = BacktestService(db).jobs()
    return {"items": [{"job_id": j.id, "name": j.name, "status": j.status, "type": j.job_type} for j in rows]}


@router.get("/report/{job_id}")
def backtest_report(job_id: int, db: Session = Depends(get_db)) -> dict:
    row = BacktestService(db).report(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "metrics": json.loads(row.metrics_json)}


@router.get("/report/{job_id}/detail")
def backtest_report_detail(job_id: int, db: Session = Depends(get_db)) -> dict:
    detail = BacktestService(db).report_detail(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **detail}


@router.get("/trades/{job_id}")
def backtest_trades(job_id: int, db: Session = Depends(get_db)) -> dict:
    rows = BacktestService(db).trades(job_id)
    return {"items": [{"symbol": t.symbol, "side": t.side, "price": t.price, "quantity": t.quantity} for t in rows]}


@router.get("/equity/{job_id}")
def backtest_equity(job_id: int, db: Session = Depends(get_db)) -> dict:
    rows = BacktestService(db).equity(job_id)
    return {"items": [{"point_time": e.point_time.isoformat(), "equity": e.equity} for e in rows]}


@router.post("/compare")
def backtest_compare(payload: dict, db: Session = Depends(get_db)) -> dict:
    left = payload.get("left_job_id")
    right = payload.get("right_job_id")
    service = BacktestService(db)
    left_report = service.report(left)
    right_report = service.report(right)
    if left_report is None or right_report is None:
        raise HTTPException(status_code=404, detail="report not found")
    l = json.loads(left_report.metrics_json)
    r = json.loads(right_report.metrics_json)
    return {"left": l, "right": r}
