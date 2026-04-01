from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.system_ops import NotificationService, SettingsService

router = APIRouter()


@router.get("")
def notifications(unread_only: bool = False, db: Session = Depends(get_db)) -> dict:
    rows = NotificationService(db).list(unread_only=unread_only)
    return {
        "items": [
            {
                "id": n.id,
                "source_type": n.source_type,
                "level": n.level,
                "title": n.title,
                "body": n.body,
                "status": n.status,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ]
    }


@router.post("/mark-read")
def mark_read(payload: dict, db: Session = Depends(get_db)) -> dict:
    ids = payload.get("ids", [])
    count = NotificationService(db).mark_read(ids)
    return {"marked": count}


@router.post("/test")
def notify_test(payload: dict, db: Session = Depends(get_db)) -> dict:
    n = NotificationService(db).create(
        source_type=payload.get("source_type", "system"),
        level=payload.get("level", "info"),
        title=payload.get("title", "test notification"),
        body=payload.get("body", "test"),
        dedupe_key=payload.get("dedupe_key", ""),
    )
    return {"id": n.id}


@router.get("/settings")
def notification_settings(db: Session = Depends(get_db)) -> dict:
    all_settings = SettingsService(db).get_all()
    target = [s for s in all_settings if s.config_key == "notification"]
    if not target:
        return {"notification": {"in_app": True, "email": False}}
    return {"notification": target[0].config_value}


@router.post("/settings")
def notification_settings_update(payload: dict, db: Session = Depends(get_db)) -> dict:
    row = SettingsService(db).update("notification", payload.get("notification", {}))
    return {"config_key": row.config_key, "config_value": row.config_value}

