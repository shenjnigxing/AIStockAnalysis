from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import AdminService

router = APIRouter()


@router.get("/audit-logs")
def admin_audit_logs(db: Session = Depends(get_db)) -> dict:
    rows = AdminService(db).audit_logs()
    return {"items": [{"id": r.id, "action": r.action, "actor": r.actor, "detail": r.detail, "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/metrics")
def admin_metrics(db: Session = Depends(get_db)) -> dict:
    return AdminService(db).metrics()


@router.post("/backup")
def admin_backup(db: Session = Depends(get_db)) -> dict:
    return AdminService(db).backup()


@router.get("/backup/list")
def admin_backup_list(db: Session = Depends(get_db)) -> dict:
    return {"items": AdminService(db).list_backups()}


@router.post("/restore")
def admin_restore(payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    marker = (payload or {}).get("marker")
    return AdminService(db).restore(marker=marker)


@router.get("/system-health")
def admin_system_health(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok", "components": {"api": "ok", "db": "ok"}}
