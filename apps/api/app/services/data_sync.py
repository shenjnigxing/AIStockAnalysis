import json
from datetime import date, datetime, timedelta
from typing import Any, Callable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    DailyBar,
    DataQualityIssue,
    MinuteBar,
    RealtimeQuote,
    StockMaster,
    SyncCheckpoint,
    SyncJob,
)
from app.services.audit import write_audit
from app.services.adapters.market_data import AkshareMarketDataAdapter


def _upsert_stock_master(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        item = db.scalar(select(StockMaster).where(StockMaster.symbol == row["symbol"]))
        if item is None:
            db.add(StockMaster(**row))
        else:
            item.name = row["name"]
            item.market = row["market"]
            item.is_active = row["is_active"]
        count += 1
    return count


def _upsert_daily_bars(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        item = db.scalar(
            select(DailyBar).where(
                DailyBar.symbol == row["symbol"],
                DailyBar.trade_date == row["trade_date"],
            )
        )
        if item is None:
            db.add(DailyBar(**row))
        else:
            item.open = row["open"]
            item.high = row["high"]
            item.low = row["low"]
            item.close = row["close"]
            item.volume = row["volume"]
            item.amount = row["amount"]
        count += 1
    return count


def _upsert_minute_bars(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        item = db.scalar(
            select(MinuteBar).where(
                MinuteBar.symbol == row["symbol"],
                MinuteBar.bar_time == row["bar_time"],
            )
        )
        if item is None:
            db.add(MinuteBar(**row))
        else:
            item.open = row["open"]
            item.high = row["high"]
            item.low = row["low"]
            item.close = row["close"]
            item.volume = row["volume"]
            item.amount = row["amount"]
        count += 1
    return count


def _upsert_realtime_quotes(db: Session, rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        item = db.scalar(
            select(RealtimeQuote).where(
                RealtimeQuote.symbol == row["symbol"],
                RealtimeQuote.quote_time == row["quote_time"],
            )
        )
        if item is None:
            db.add(RealtimeQuote(**row))
        else:
            item.price = row["price"]
            item.change_pct = row["change_pct"]
            item.volume = row["volume"]
            item.amount = row["amount"]
        count += 1
    return count


def _get_or_create_checkpoint(db: Session, job_type: str, scope_key: str) -> SyncCheckpoint:
    cp = db.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.job_type == job_type,
            SyncCheckpoint.scope_key == scope_key,
        )
    )
    if cp is None:
        cp = SyncCheckpoint(job_type=job_type, scope_key=scope_key, checkpoint_value="")
        db.add(cp)
        db.flush()
    return cp


def _list_symbols(db: Session) -> list[str]:
    symbols = db.scalars(select(StockMaster.symbol).where(StockMaster.is_active.is_(True)).limit(200)).all()
    return list(symbols) if symbols else ["000001", "600000", "600519"]


def _validate_ohlc_row(row: dict[str, Any]) -> bool:
    if row["open"] < 0 or row["high"] < 0 or row["low"] < 0 or row["close"] < 0:
        return False
    if row["high"] < row["low"]:
        return False
    return True


class DataSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.adapter = AkshareMarketDataAdapter()

    def _run_job(self, job_type: str, params: dict[str, Any], runner: Callable[[SyncJob], dict[str, Any]]) -> SyncJob:
        job = SyncJob(
            job_type=job_type,
            status="running",
            params_json=json.dumps(params, ensure_ascii=True, default=str),
            started_at=datetime.utcnow(),
        )
        self.db.add(job)
        write_audit(self.db, action="data.sync.start", detail=f"job_type={job_type}; params={json.dumps(params, ensure_ascii=True, default=str)}")
        self.db.commit()
        self.db.refresh(job)
        try:
            result = runner(job)
            job.status = "completed"
            job.result_json = json.dumps(result, ensure_ascii=True, default=str)
            job.finished_at = datetime.utcnow()
            write_audit(self.db, action="data.sync.completed", detail=f"job_id={job.id}; job_type={job_type}")
            self.db.commit()
            self.db.refresh(job)
            return job
        except Exception as exc:
            self.db.rollback()
            job = self.db.get(SyncJob, job.id)
            assert job is not None
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            write_audit(self.db, action="data.sync.failed", detail=f"job_id={job.id}; job_type={job_type}; error={str(exc)}")
            self.db.commit()
            self.db.refresh(job)
            return job

    def sync_master(self, force_full: bool = False) -> SyncJob:
        def runner(_: SyncJob) -> dict[str, Any]:
            rows = self.adapter.fetch_stock_master()
            written = _upsert_stock_master(self.db, rows)
            cp = _get_or_create_checkpoint(self.db, "master", "all")
            cp.checkpoint_value = datetime.utcnow().isoformat()
            self.db.commit()
            return {"rows": written, "force_full": force_full}

        return self._run_job("master", {"force_full": force_full}, runner)

    def sync_daily(self, symbols: list[str] | None, start_date: date | None, end_date: date | None) -> SyncJob:
        def runner(_: SyncJob) -> dict[str, Any]:
            target_symbols = symbols or _list_symbols(self.db)
            end = end_date or date.today()
            total_rows = 0
            for symbol in target_symbols:
                cp = _get_or_create_checkpoint(self.db, "daily", symbol)
                default_start = date.today() - timedelta(days=7)
                from_cp = date.fromisoformat(cp.checkpoint_value) + timedelta(days=1) if cp.checkpoint_value else default_start
                start = start_date or from_cp
                if start > end:
                    continue
                fetched_rows = self.adapter.fetch_daily_bars(symbol=symbol, start_date=start, end_date=end)
                rows = []
                for row in fetched_rows:
                    if not _validate_ohlc_row(row):
                        self.db.add(
                            DataQualityIssue(
                                issue_type="invalid_ohlc",
                                symbol=symbol,
                                detail=f"date={row['trade_date']}",
                            )
                        )
                        continue
                    rows.append(row)
                total_rows += _upsert_daily_bars(self.db, rows)
                cp.checkpoint_value = end.isoformat()
                self.db.commit()
            return {"rows": total_rows, "symbols": len(target_symbols)}

        params = {"symbols": symbols, "start_date": start_date, "end_date": end_date}
        return self._run_job("daily", params, runner)

    def sync_minute(self, symbols: list[str] | None, start_time: datetime | None, end_time: datetime | None) -> SyncJob:
        def runner(_: SyncJob) -> dict[str, Any]:
            target_symbols = symbols or _list_symbols(self.db)
            end = end_time or datetime.utcnow().replace(second=0, microsecond=0)
            total_rows = 0
            for symbol in target_symbols:
                cp = _get_or_create_checkpoint(self.db, "minute", symbol)
                default_start = end - timedelta(minutes=30)
                from_cp = (
                    datetime.fromisoformat(cp.checkpoint_value) + timedelta(minutes=1)
                    if cp.checkpoint_value
                    else default_start
                )
                start = start_time or from_cp
                if start > end:
                    continue
                rows = self.adapter.fetch_minute_bars(symbol=symbol, start_time=start, end_time=end)
                total_rows += _upsert_minute_bars(self.db, rows)
                cp.checkpoint_value = end.isoformat()
                self.db.commit()
            return {"rows": total_rows, "symbols": len(target_symbols)}

        params = {"symbols": symbols, "start_time": start_time, "end_time": end_time}
        return self._run_job("minute", params, runner)

    def sync_realtime(self, symbols: list[str] | None) -> SyncJob:
        def runner(_: SyncJob) -> dict[str, Any]:
            target_symbols = symbols or _list_symbols(self.db)
            rows = self.adapter.fetch_realtime_quotes(target_symbols)
            written = _upsert_realtime_quotes(self.db, rows)
            cp = _get_or_create_checkpoint(self.db, "realtime", "all")
            cp.checkpoint_value = datetime.utcnow().isoformat()
            self.db.commit()
            return {"rows": written, "symbols": len(target_symbols)}

        return self._run_job("realtime", {"symbols": symbols}, runner)

    def list_jobs(self, limit: int = 50) -> list[SyncJob]:
        stmt = select(SyncJob).order_by(desc(SyncJob.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_job(self, job_id: int) -> SyncJob | None:
        return self.db.get(SyncJob, job_id)

    def list_quality_issues(self, limit: int = 100) -> list[DataQualityIssue]:
        stmt = select(DataQualityIssue).order_by(desc(DataQualityIssue.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def retry_job(self, job_id: int) -> SyncJob | None:
        old_job = self.get_job(job_id)
        if old_job is None:
            return None
        params = json.loads(old_job.params_json or "{}")
        if old_job.job_type == "master":
            return self.sync_master(force_full=bool(params.get("force_full", False)))
        if old_job.job_type == "daily":
            start_date = date.fromisoformat(params["start_date"]) if params.get("start_date") else None
            end_date = date.fromisoformat(params["end_date"]) if params.get("end_date") else None
            return self.sync_daily(symbols=params.get("symbols"), start_date=start_date, end_date=end_date)
        if old_job.job_type == "minute":
            start_time = datetime.fromisoformat(params["start_time"]) if params.get("start_time") else None
            end_time = datetime.fromisoformat(params["end_time"]) if params.get("end_time") else None
            return self.sync_minute(symbols=params.get("symbols"), start_time=start_time, end_time=end_time)
        if old_job.job_type == "realtime":
            return self.sync_realtime(symbols=params.get("symbols"))
        raise ValueError(f"Unsupported job_type: {old_job.job_type}")
