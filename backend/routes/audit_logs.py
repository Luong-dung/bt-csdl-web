"""W47-02 read-only audit log API. Reads never write audit rows or change data."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.database import get_db
from core.tournaments import ensure_tournament_manager, get_tournament_or_404
from core.validation import INT_MAX, ResourceId
from core.permissions import AUDIT_LOG_VIEW_ALL
from middleware.auth import get_current_user, require_permission
from modules.identity.models import AuditLog, User
from routes.tournaments import TOTAL_COUNT_HEADER

router = APIRouter(tags=['Audit logs'])

# Never returned, at any depth, even if an old writer stored them in details.
SENSITIVE_KEYS = {'email', 'password', 'password_hash', 'token', 'access_token', 'preview_token', 'secret'}


class Actor(BaseModel):
    user_id: int
    username: str


class AuditLogRead(BaseModel):
    log_id: int
    created_at: datetime | None
    action: str
    resource: str
    resource_id: int | None
    tournament_id: int | None
    actor: Actor | None
    details: Any


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if str(k).lower() not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class Filters:
    def __init__(
        self,
        resource: str | None = Query(None, min_length=1, max_length=100),
        action: str | None = Query(None, min_length=1, max_length=100),
        actor_id: int | None = Query(None, gt=0, le=INT_MAX),
        resource_id: int | None = Query(None, gt=0, le=INT_MAX),
        since: datetime | None = None,
        until: datetime | None = None,
        offset: int = Query(0, ge=0, le=INT_MAX),
        limit: int = Query(50, ge=1, le=100),
    ):
        if any(value is not None and value.tzinfo is None for value in (since, until)):
            raise HTTPException(status_code=422, detail='since/until phải có múi giờ (ví dụ 2026-11-17T00:00:00Z)')
        if since and until and since > until:
            raise HTTPException(status_code=422, detail='since phải trước until')
        self.resource, self.action, self.actor_id, self.resource_id = resource, action, actor_id, resource_id
        self.since, self.until, self.offset, self.limit = since, until, offset, limit


def read_logs(db: Session, response: Response, filters: Filters, tournament_id: int | None = None):
    query = select(AuditLog, User.username).outerjoin(User, User.user_id == AuditLog.user_id)
    conditions = [
        (AuditLog.tournament_id, tournament_id), (AuditLog.resource, filters.resource),
        (AuditLog.action, filters.action), (AuditLog.user_id, filters.actor_id),
        (AuditLog.resource_id, filters.resource_id),
    ]
    for column, value in conditions:
        if value is not None:
            query = query.where(column == value)
    if filters.since is not None:
        query = query.where(AuditLog.created_at >= filters.since)
    if filters.until is not None:
        query = query.where(AuditLog.created_at <= filters.until)
    response.headers[TOTAL_COUNT_HEADER] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    # Newest first; log_id is unique so pages never overlap or skip.
    rows = db.execute(query.order_by(AuditLog.log_id.desc()).offset(filters.offset).limit(filters.limit)).all()
    return [AuditLogRead(
        log_id=log.log_id, created_at=log.created_at, action=log.action, resource=log.resource,
        resource_id=log.resource_id, tournament_id=log.tournament_id,
        actor=Actor(user_id=log.user_id, username=username) if log.user_id is not None and username else None,
        details=scrub(log.details),
    ) for log, username in rows]


@router.get('/api/v1/tournaments/{tournament_id}/audit-logs', response_model=list[AuditLogRead])
def tournament_audit_logs(
    tournament_id: ResourceId,
    response: Response,
    filters: Filters = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_tournament_manager(get_tournament_or_404(db, tournament_id), user)
    return read_logs(db, response, filters, tournament_id)


@router.get('/api/v1/admin/audit-logs', response_model=list[AuditLogRead],
            dependencies=[Depends(require_permission(AUDIT_LOG_VIEW_ALL))])
def admin_audit_logs(
    response: Response,
    filters: Filters = Depends(),
    tournament_id: int | None = Query(None, gt=0, le=INT_MAX),
    db: Session = Depends(get_db),
):
    return read_logs(db, response, filters, tournament_id)
