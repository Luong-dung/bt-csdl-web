from sqlalchemy.orm import Session

from modules.identity.models import AuditLog


def record_audit(db: Session, user_id: int | None, action: str, resource: str, details: dict) -> None:
    """Queue an audit entry in the caller's transaction; never commit separately."""
    db.add(AuditLog(user_id=user_id, action=action, resource=resource, details=details))
