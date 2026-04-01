import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestEquityCurve, BacktestJob, BacktestReport, BacktestTrade
from app.services.audit import write_audit


class BacktestService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, payload: dict) -> BacktestJob:
        name = payload.get("name", f"backtest-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        job = BacktestJob(name=name, job_type=payload.get("type", "strategy"), params_json=json.dumps(payload, ensure_ascii=True))
        self.db.add(job)
        self.db.flush()

        init_cash = float(payload.get("initial_cash", 1_000_000))
        trade = BacktestTrade(job_id=job.id, symbol="000001", side="buy", price=10.0, quantity=1000)
        self.db.add(trade)

        equities = [init_cash, init_cash * 1.01, init_cash * 1.015, init_cash * 1.008, init_cash * 1.02]
        now = datetime.utcnow()
        for i, val in enumerate(equities):
            self.db.add(BacktestEquityCurve(job_id=job.id, point_time=now + timedelta(days=i), equity=round(val, 2)))

        total_return = (equities[-1] - equities[0]) / equities[0]
        metrics = {
            "total_return": round(total_return, 4),
            "annual_return": round(total_return * 12, 4),
            "max_drawdown": 0.007,
            "sharpe": 1.1,
            "win_rate": 0.6,
            "total_trades": 1,
        }
        report = BacktestReport(job_id=job.id, metrics_json=json.dumps(metrics, ensure_ascii=True))
        self.db.add(report)
        write_audit(
            self.db,
            action="backtest.run",
            detail=f"job_id={job.id}; name={name}; total_return={metrics['total_return']}",
        )
        self.db.commit()
        self.db.refresh(job)
        return job

    def jobs(self) -> list[BacktestJob]:
        return list(self.db.scalars(select(BacktestJob).order_by(BacktestJob.created_at.desc())).all())

    def report(self, job_id: int) -> BacktestReport | None:
        return self.db.scalar(select(BacktestReport).where(BacktestReport.job_id == job_id))

    def trades(self, job_id: int) -> list[BacktestTrade]:
        return list(self.db.scalars(select(BacktestTrade).where(BacktestTrade.job_id == job_id)).all())

    def equity(self, job_id: int) -> list[BacktestEquityCurve]:
        return list(self.db.scalars(select(BacktestEquityCurve).where(BacktestEquityCurve.job_id == job_id)).all())
