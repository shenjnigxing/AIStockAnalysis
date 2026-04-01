from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Notification, ReplayRecord, SystemConfig
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

    def audit_logs(self) -> list[AuditLog]:
        return list(self.db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(200)).all())

    def metrics(self) -> dict:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {"api": "ok"},
            "note": "basic phase metrics",
        }

    def backup(self) -> dict:
        marker = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        write_audit(self.db, action="admin.backup", detail=f"marker={marker}; mode=placeholder")
        self.db.commit()
        return {"status": "ok", "message": "backup placeholder", "marker": marker}

    def restore(self) -> dict:
        marker = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        write_audit(self.db, action="admin.restore", detail=f"marker={marker}; mode=placeholder")
        self.db.commit()
        return {"status": "ok", "message": "restore placeholder", "marker": marker}
