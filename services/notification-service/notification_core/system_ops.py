from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import unquote
from datetime import date, datetime

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.models import AuditLog, KillSwitchStatus, Notification, ReplayRecord, RiskEvent, SyncJob, SystemConfig
from app.services.audit import write_audit


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, unread_only: bool = False) -> list[Notification]:
        stmt = select(Notification).order_by(desc(Notification.created_at))
        if unread_only:
            stmt = stmt.where(Notification.status == "unread")
        return list(self.db.scalars(stmt).all())

    def create(self, source_type: str, level: str, title: str, body: str, dedupe_key: str = "") -> Notification:
        if dedupe_key:
            existing = self.db.scalar(select(Notification).where(Notification.dedupe_key == dedupe_key))
            if existing is not None:
                write_audit(
                    self.db,
                    action="notification.dedupe_hit",
                    detail=f"dedupe_key={dedupe_key}; notification_id={existing.id}",
                )
                self.db.commit()
                return existing
        n = Notification(source_type=source_type, level=level, title=title, body=body, dedupe_key=dedupe_key)
        self.db.add(n)
        write_audit(
            self.db,
            action="notification.create",
            detail=f"source_type={source_type}; level={level}; title={title}; dedupe_key={dedupe_key}",
        )
        self.db.commit()
        self.db.refresh(n)
        return n

    def mark_read(self, ids: list[int]) -> int:
        count = 0
        for nid in ids:
            n = self.db.get(Notification, nid)
            if n is None:
                continue
            n.status = "read"
            count += 1
        write_audit(self.db, action="notification.mark_read", detail=f"ids={ids}; marked={count}")
        self.db.commit()
        return count


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[SystemConfig]:
        return list(self.db.scalars(select(SystemConfig).order_by(SystemConfig.config_key)).all())

    def update(self, config_key: str, config_value: dict) -> SystemConfig:
        row = self.db.scalar(select(SystemConfig).where(SystemConfig.config_key == config_key))
        if row is None:
            row = SystemConfig(config_key=config_key, config_value=json.dumps(config_value, ensure_ascii=True))
            self.db.add(row)
        else:
            row.config_value = json.dumps(config_value, ensure_ascii=True)
            row.updated_at = datetime.utcnow()
        write_audit(self.db, action="settings.update", detail=f"key={config_key}")
        self.db.commit()
        self.db.refresh(row)
        return row

    def reset_default(self) -> dict:
        defaults = {
            "notification": {"email": False, "in_app": True},
            "recommendation": {"llm_enabled": False, "market_state": "neutral"},
            "risk": {"max_single_order_amount": 100000},
        }
        for key, value in defaults.items():
            self.update(key, value)
        write_audit(self.db, action="settings.reset_default", detail="applied")
        self.db.commit()
        return defaults


class InitWizardService:
    STEPS = [
        "env_check",
        "data_source",
        "seed_data",
        "strategy_defaults",
        "risk_defaults",
        "llm_config",
        "broker_check",
    ]

    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self) -> dict:
        done = self.db.scalar(select(SystemConfig).where(SystemConfig.config_key == "init_steps_done"))
        done_steps = json.loads(done.config_value) if done else []
        return {"steps": self.STEPS, "done": done_steps, "finished": len(done_steps) == len(self.STEPS)}

    def run_step(self, step: str) -> dict:
        if step not in self.STEPS:
            raise ValueError("invalid step")
        st = self.status()
        done = st["done"]
        if step not in done:
            done.append(step)
            SettingsService(self.db).update("init_steps_done", done)
            write_audit(self.db, action="init.run_step", detail=f"step={step}; status=completed")
            self.db.commit()
        else:
            write_audit(self.db, action="init.run_step", detail=f"step={step}; status=already_done")
            self.db.commit()
        return {"step": step, "status": "completed", "done": done}

    def finish(self) -> dict:
        SettingsService(self.db).update("init_steps_done", self.STEPS)
        SettingsService(self.db).update("init_finished", {"finished_at": datetime.utcnow().isoformat()})
        write_audit(self.db, action="init.finish", detail="status=completed")
        self.db.commit()
        return {"status": "completed"}


class ReplayService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_seed(self) -> None:
        exist = self.db.scalar(select(ReplayRecord).limit(1))
        if exist is not None:
            return
        self.db.add(
            ReplayRecord(
                trade_date=date.today(),
                symbol="000001",
                strategy_key="platform_breakout",
                recommendation_level="B",
                record_json=json.dumps({"result": "paper_win"}, ensure_ascii=True),
            )
        )
        self.db.commit()

    def days(self) -> list[str]:
        self.ensure_seed()
        rows = self.db.scalars(select(ReplayRecord.trade_date).distinct().order_by(desc(ReplayRecord.trade_date))).all()
        return [r.isoformat() for r in rows]

    def by_day(self, trade_date: date) -> list[ReplayRecord]:
        self.ensure_seed()
        return list(self.db.scalars(select(ReplayRecord).where(ReplayRecord.trade_date == trade_date)).all())

    def by_symbol(self, symbol: str) -> list[ReplayRecord]:
        self.ensure_seed()
        return list(self.db.scalars(select(ReplayRecord).where(ReplayRecord.symbol == symbol)).all())

    def by_strategy(self, strategy_key: str) -> list[ReplayRecord]:
        self.ensure_seed()
        return list(self.db.scalars(select(ReplayRecord).where(ReplayRecord.strategy_key == strategy_key)).all())


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _audit_best_effort(self, action: str, detail: str) -> str | None:
        try:
            write_audit(self.db, action=action, detail=detail)
            self.db.commit()
            return None
        except SQLAlchemyError as exc:
            self.db.rollback()
            return str(exc)

    def _resolve_sqlite_path(self) -> Path | None:
        url = settings.database_url
        if not url.startswith("sqlite:"):
            return None
        if url.startswith("sqlite:///"):
            raw_path = url[len("sqlite:///") :]
        elif url.startswith("sqlite://"):
            raw_path = url[len("sqlite://") :]
        else:
            return None
        # `sqlite:///:memory:` and similar URI-based in-memory DBs are not file-backed.
        normalized = raw_path.strip().lower()
        if not normalized or ":memory:" in normalized:
            return None
        return Path(unquote(raw_path)).expanduser().resolve()

    def _backup_root(self) -> Path:
        root = Path(__file__).resolve().parents[4]
        target = root / "data" / "backups"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def list_backups(self) -> list[dict]:
        backup_root = self._backup_root()
        files = sorted(backup_root.glob("stock_assistant_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [
            {
                "marker": file.stem.replace("stock_assistant_", ""),
                "path": str(file),
                "size_bytes": file.stat().st_size,
                "updated_at": datetime.utcfromtimestamp(file.stat().st_mtime).isoformat(),
            }
            for file in files
        ]

    def audit_logs(self) -> list[AuditLog]:
        return list(self.db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(200)).all())

    def metrics(self) -> dict:
        db_status = "ok"
        try:
            self.db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db_status = "degraded"
        unread_count = len(self.db.scalars(select(Notification).where(Notification.status == "unread")).all())
        risk_recent = len(self.db.scalars(select(RiskEvent).order_by(desc(RiskEvent.created_at)).limit(50)).all())
        latest_sync = self.db.scalar(select(SyncJob).order_by(desc(SyncJob.created_at)))
        kill_switch = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        backups = self.list_backups()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "ok",
                "db": db_status,
            },
            "overview": {
                "unread_notifications": unread_count,
                "recent_risk_events": risk_recent,
                "kill_switch_enabled": bool(kill_switch.enabled) if kill_switch else False,
                "latest_sync_job_status": latest_sync.status if latest_sync else "never_run",
                "backup_count": len(backups),
            },
        }

    def runtime_health(self) -> dict:
        metrics = self.metrics()
        backups = self.list_backups()
        latest_backup_at = backups[0]["updated_at"] if backups else ""
        fresh_backup = False
        if backups:
            try:
                backup_dt = datetime.fromisoformat(str(backups[0]["updated_at"]))
                fresh_backup = (datetime.utcnow() - backup_dt).total_seconds() <= 24 * 3600
            except ValueError:
                fresh_backup = False
        degraded_reasons: list[str] = []
        if metrics["services"].get("db") != "ok":
            degraded_reasons.append("db_unavailable")
        if not fresh_backup:
            degraded_reasons.append("backup_not_fresh")
        return {
            "status": "degraded" if degraded_reasons else "ok",
            "degraded_reasons": degraded_reasons,
            "services": metrics["services"],
            "resilience": {
                "latest_backup_at": latest_backup_at,
                "fresh_backup_within_24h": fresh_backup,
                "backup_count": len(backups),
            },
            "timestamp": metrics["timestamp"],
        }

    def disaster_recovery_readiness(self) -> dict:
        backups = self.list_backups()
        kill_switch = self.db.scalar(select(KillSwitchStatus).order_by(desc(KillSwitchStatus.updated_at)))
        can_restore = len(backups) > 0
        checklist = {
            "backup_available": can_restore,
            "kill_switch_control_ready": bool(kill_switch is not None),
            "audit_log_writable": True,
        }
        score = int(sum(1 for _, passed in checklist.items() if passed) / max(len(checklist), 1) * 100)
        return {
            "score": score,
            "status": "ready" if score >= 80 else "partial",
            "checklist": checklist,
            "latest_backup_marker": backups[0]["marker"] if backups else "",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def backup(self) -> dict:
        marker = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        source_db = self._resolve_sqlite_path()
        if source_db is None:
            self._audit_best_effort(action="admin.backup", detail=f"marker={marker}; status=skipped_non_sqlite")
            return {"status": "skipped", "message": "non-sqlite database is not handled by local file backup", "marker": marker}
        if not source_db.exists():
            self._audit_best_effort(action="admin.backup", detail=f"marker={marker}; status=source_missing")
            return {"status": "failed", "message": "source database file not found", "marker": marker}

        backup_file = self._backup_root() / f"stock_assistant_{marker}.db"
        # Log backup intent before file copy so restore keeps an admin.backup trace.
        self._audit_best_effort(
            action="admin.backup",
            detail=f"marker={marker}; status=started; source={source_db}; target={backup_file}",
        )
        shutil.copy2(source_db, backup_file)
        audit_error = self._audit_best_effort(
            action="admin.backup",
            detail=f"marker={marker}; status=completed; source={source_db}; target={backup_file}",
        )
        payload: dict[str, object] = {
            "status": "ok",
            "message": "backup created",
            "marker": marker,
            "source": str(source_db),
            "target": str(backup_file),
            "size_bytes": backup_file.stat().st_size,
        }
        if audit_error:
            payload["audit_error"] = audit_error
        return payload

    def restore(self, marker: str | None = None) -> dict:
        source_db = self._resolve_sqlite_path()
        if source_db is None:
            self._audit_best_effort(action="admin.restore", detail=f"marker={marker or ''}; status=skipped_non_sqlite")
            return {"status": "skipped", "message": "non-sqlite database is not handled by local file restore"}

        backups = self.list_backups()
        if not backups:
            self._audit_best_effort(action="admin.restore", detail="status=failed; reason=no_backup")
            return {"status": "failed", "message": "no backup file found"}

        selected = backups[0]
        if marker:
            matched = next((item for item in backups if item["marker"] == marker), None)
            if matched is None:
                self._audit_best_effort(action="admin.restore", detail=f"marker={marker}; status=failed; reason=not_found")
                return {"status": "failed", "message": f"backup marker {marker} not found"}
            selected = matched

        backup_file = Path(selected["path"])
        if not backup_file.exists():
            self._audit_best_effort(
                action="admin.restore",
                detail=f"marker={selected['marker']}; status=failed; reason=file_missing",
            )
            return {"status": "failed", "message": "backup file missing on disk"}

        source_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, source_db)
        audit_error = self._audit_best_effort(
            action="admin.restore",
            detail=f"marker={selected['marker']}; status=completed; source={backup_file}; target={source_db}",
        )
        payload: dict[str, object] = {
            "status": "ok",
            "message": "restore completed",
            "marker": selected["marker"],
            "source": str(backup_file),
            "target": str(source_db),
        }
        if audit_error:
            payload["audit_error"] = audit_error
        return payload
