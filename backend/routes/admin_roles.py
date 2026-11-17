"""W47-01 ADMIN-only management of role assignments in every scope."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.database import get_db
from core.role_assignments import grant, lock_assignment, revoke
from core.tournaments import lock_tournament_as
from core.validation import INT_MAX, ResourceId
from middleware.auth import get_current_user, has_role, require_role
from modules.identity.models import Role, RoleAssignment, User
from modules.teams.models import Organization, Team
from modules.tournaments.models import Tournament
from routes.tournaments import TOTAL_COUNT_HEADER

router = APIRouter(prefix='/api/v1/admin/role-assignments', tags=['Admin role assignments'],
                   dependencies=[Depends(require_role('ADMIN'))])

RoleName = Literal['ADMIN', 'ORGANIZER', 'TEAM_MANAGER', 'REFEREE', 'VIEWER']
ScopeType = Literal['GLOBAL', 'TOURNAMENT', 'TEAM', 'ORGANIZATION']
SCOPE_MODELS = {'TOURNAMENT': Tournament, 'TEAM': Team, 'ORGANIZATION': Organization}


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    user_id: ResourceId
    role: RoleName
    scope_type: ScopeType
    scope_id: ResourceId | None = None

    @model_validator(mode='after')
    def scope_shape(self):
        if (self.scope_type == 'GLOBAL') != (self.scope_id is None):
            raise ValueError('scope_id phải null khi GLOBAL và bắt buộc với scope khác')
        return self


class AssignmentRead(BaseModel):
    assignment_id: int
    user_id: int
    username: str
    role: str
    scope_type: str
    scope_id: int | None
    granted_by: int | None
    granted_at: datetime | None
    revoked_by: int | None
    revoked_at: datetime | None
    active: bool


def to_read(a: RoleAssignment, user: User, role: str) -> AssignmentRead:
    return AssignmentRead(assignment_id=a.assignment_id, user_id=a.user_id, username=user.username, role=role,
                          scope_type=a.scope_type, scope_id=a.scope_id, granted_by=a.granted_by,
                          granted_at=a.granted_at, revoked_by=a.revoked_by, revoked_at=a.revoked_at,
                          active=a.revoked_at is None)


def ensure_admin(db: Session, user: User, tournament_id: int | None) -> User:
    """Serialize with tournament writers when the scope is a tournament, then recheck ADMIN."""
    if tournament_id is not None:
        _, user = lock_tournament_as(db, tournament_id, user)
    else:
        user = db.get(User, user.user_id, populate_existing=True)
        db.expire(user, ['role', 'assignments'])
    if not has_role(user, 'ADMIN'):
        raise HTTPException(status_code=403, detail='Bạn không có quyền thực hiện thao tác này')
    return user


@router.get('', response_model=list[AssignmentRead])
def list_assignments(
    response: Response,
    user_id: int | None = Query(None, gt=0, le=INT_MAX),
    scope_type: ScopeType | None = None,
    scope_id: int | None = Query(None, gt=0, le=INT_MAX),
    include_revoked: bool = False,
    offset: int = Query(0, ge=0, le=INT_MAX),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (select(RoleAssignment, User, Role.role_name).join(User, User.user_id == RoleAssignment.user_id)
             .join(Role, Role.role_id == RoleAssignment.role_id))
    for column, value in ((RoleAssignment.user_id, user_id), (RoleAssignment.scope_type, scope_type),
                          (RoleAssignment.scope_id, scope_id)):
        if value is not None:
            query = query.where(column == value)
    if not include_revoked:
        query = query.where(RoleAssignment.revoked_at.is_(None))
    query = query.order_by(RoleAssignment.assignment_id)
    response.headers[TOTAL_COUNT_HEADER] = str(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())))
    return [to_read(a, u, r) for a, u, r in db.execute(query.offset(offset).limit(limit)).all()]


@router.post('', response_model=AssignmentRead, status_code=201)
def create_assignment(data: AssignmentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if data.scope_type in SCOPE_MODELS and db.get(SCOPE_MODELS[data.scope_type], data.scope_id) is None:
            raise HTTPException(status_code=422, detail='Phạm vi (scope) không tồn tại')
        tournament_id = data.scope_id if data.scope_type == 'TOURNAMENT' else None
        user = ensure_admin(db, user, tournament_id)
        # Locked by ensure_admin; REFEREE rules (closed tournament, conflict of interest) apply here too.
        tournament = db.get(Tournament, tournament_id) if tournament_id is not None else None
        assignment = grant(db, user, data.user_id, data.role, data.scope_type, data.scope_id, tournament)
        result = to_read(assignment, db.get(User, data.user_id), data.role)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.delete('/{assignment_id}', response_model=AssignmentRead)
def delete_assignment(assignment_id: ResourceId, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        current = db.get(RoleAssignment, assignment_id)
        if current is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy phân quyền')
        tournament_id = current.scope_id if current.scope_type == 'TOURNAMENT' else None
        user = ensure_admin(db, user, tournament_id)
        assignment = lock_assignment(db, assignment_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy phân quyền')
        if assignment.user_id == user.user_id:
            raise HTTPException(status_code=422, detail='Không thể tự thu hồi quyền của chính mình')
        role = db.get(Role, assignment.role_id).role_name
        revoke(db, user, assignment, role, tournament_id)
        result = to_read(assignment, db.get(User, assignment.user_id), role)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
