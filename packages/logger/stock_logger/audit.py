from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.db.models import AuditLog


def write_audit(db: Session, action: str, detail: str, actor: str = "system") -> None:
    request_id = get_request_id()
    payload = f"request_id={request_id}; {detail}" if detail else f"request_id={request_id}"
    db.add(AuditLog(action=action, actor=actor, detail=payload))

