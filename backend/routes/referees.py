"""W47-01 tournament referees: managers grant/revoke REFEREE scoped to their own tournament."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.database import get_db
from core.role_assignments import (
    grant, lock_assignment, plays_in_tournament, referees_grantable, revoke, role_id,
)
from core.tournaments import ensure_tournament_manager, get_managed_tournament, get_tournament_or_404
from core.validation import INT_MAX, ResourceId
from middleware.auth import get_current_user
from modules.identity.models import RoleAssignment, User
from routes.tournaments import TOTAL_COUNT_HEADER

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}/referees', tags=['Tournament referees'])


class RefereeGrant(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    user_id: ResourceId


class RefereeRead(BaseModel):
    """No email: managers identify referees by username/real name only."""
    assignment_id: int
    tournament_id: int
    user_id: int
    username: str
    real_name: str | None
    granted_by: int | None
    granted_at: datetime | None
    revoked_by: int | None
    revoked_at: datetime | None
    active: bool


def to_read(a: RoleAssignment, user: User) -> RefereeRead:
    return RefereeRead(assignment_id=a.assignment_id, tournament_id=a.scope_id, user_id=a.user_id,
                       username=user.username, real_name=user.real_name, granted_by=a.granted_by,
                       granted_at=a.granted_at, revoked_by=a.revoked_by, revoked_at=a.revoked_at,
                       active=a.revoked_at is None)


def referee_rows(db: Session, tournament_id: int):
    return (select(RoleAssignment, User).join(User, User.user_id == RoleAssignment.user_id)
            .where(RoleAssignment.role_id == role_id(db, 'REFEREE'), RoleAssignment.scope_type == 'TOURNAMENT',
                   RoleAssignment.scope_id == tournament_id))


@router.get('', response_model=list[RefereeRead])
def list_referees(
    tournament_id: ResourceId,
    response: Response,
    include_revoked: bool = False,
    offset: int = Query(0, ge=0, le=INT_MAX),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_tournament_manager(get_tournament_or_404(db, tournament_id), user)
    query = referee_rows(db, tournament_id)
    if not include_revoked:
        query = query.where(RoleAssignment.revoked_at.is_(None))
    query = query.order_by(RoleAssignment.assignment_id)
    response.headers[TOTAL_COUNT_HEADER] = str(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())))
    return [to_read(a, u) for a, u in db.execute(query.offset(offset).limit(limit)).all()]


@router.post('', response_model=RefereeRead, status_code=201)
def grant_referee(
    tournament_id: ResourceId,
    data: RefereeGrant,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Locks the tournament and rechecks the actor's permission after waiting.
        tournament = get_managed_tournament(db, tournament_id, user)
        if not referees_grantable(tournament):
            raise HTTPException(status_code=409, detail='Giải đã kết thúc hoặc bị hủy, không thể cấp trọng tài')
        if data.user_id != user.user_id and plays_in_tournament(db, tournament_id, data.user_id):
            raise HTTPException(status_code=409, detail='Người dùng đang thi đấu trong giải, không thể làm trọng tài')
        assignment = grant(db, user, data.user_id, 'REFEREE', 'TOURNAMENT', tournament_id, tournament_id)
        target = db.get(User, data.user_id)
        result = to_read(assignment, target)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.delete('/{assignment_id}', response_model=RefereeRead)
def revoke_referee(
    tournament_id: ResourceId,
    assignment_id: ResourceId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Revoking removes access, so it stays allowed in every tournament status.
        get_managed_tournament(db, tournament_id, user)
        assignment = lock_assignment(db, assignment_id)
        if (assignment is None or assignment.scope_type != 'TOURNAMENT' or assignment.scope_id != tournament_id
                or assignment.role_id != role_id(db, 'REFEREE')):
            raise HTTPException(status_code=404, detail='Không tìm thấy trọng tài của giải này')
        revoke(db, user, assignment, 'REFEREE', tournament_id)
        result = to_read(assignment, db.get(User, assignment.user_id))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
