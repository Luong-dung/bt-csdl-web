"""W47-01 role assignment grant/revoke shared by the referee and admin APIs.

Lock order: tournament (only for TOURNAMENT scope) -> assignment rows. Callers own commit/rollback
and write audit in the same transaction. Revocation keeps the row (revoked_at) as history; only
active rows reach ``User.assignments`` so every existing checker ignores revoked grants.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.audit import record_audit
from modules.identity.models import Role, RoleAssignment, User
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import TournamentRegistration, TournamentRoster

GRANT_CLOSED_STATUSES = ('COMPLETED', 'CANCELLED')
# Teams still in the tournament: their members may not referee it (conflict of interest).
ACTIVE_REGISTRATION_STATUSES = ('PENDING', 'APPROVED')


# Only combinations some checker honours; anything else would be shown as a permission but grant nothing.
ALLOWED_SCOPES = {
    'ADMIN': {'GLOBAL'},
    'ORGANIZER': {'GLOBAL', 'TOURNAMENT'},
    'REFEREE': {'TOURNAMENT'},
    'TEAM_MANAGER': {'TEAM', 'ORGANIZATION'},
    'VIEWER': {'GLOBAL'},
}


def referees_grantable(tournament) -> bool:
    return tournament.status not in GRANT_CLOSED_STATUSES


def role_id(db: Session, name: str) -> int:
    value = db.scalar(select(Role.role_id).where(Role.role_name == name))
    if value is None:
        raise HTTPException(status_code=422, detail=f'Vai trò {name} không tồn tại')
    return value


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy người dùng')
    return user


def plays_in_tournament(db: Session, tournament_id: int, user_id: int) -> bool:
    """Conflict of interest: in the roster snapshot, an active member of a team still registered,
    or a scoped TEAM_MANAGER of such a team (TEAM scope) or of its organization (ORGANIZATION scope)."""
    registered = select(TournamentRegistration.team_id).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.status.in_(ACTIVE_REGISTRATION_STATUSES))
    in_roster = exists().where(TournamentRoster.tournament_id == tournament_id, TournamentRoster.user_id == user_id)
    in_team = exists().where(
        TeamMembership.user_id == user_id, TeamMembership.status == 'ACTIVE', TeamMembership.left_date.is_(None),
        TeamMembership.team_id.in_(registered))
    manages = exists().where(
        RoleAssignment.user_id == user_id, RoleAssignment.revoked_at.is_(None),
        RoleAssignment.role_id == select(Role.role_id).where(Role.role_name == 'TEAM_MANAGER').scalar_subquery(),
        or_(and_(RoleAssignment.scope_type == 'TEAM', RoleAssignment.scope_id.in_(registered)),
            and_(RoleAssignment.scope_type == 'ORGANIZATION', RoleAssignment.scope_id.in_(
                select(Team.organization_id).where(Team.team_id.in_(registered)))))
    )
    return bool(db.scalar(select(in_roster | in_team | manages)))


def active_assignment(db: Session, user_id: int, role: int, scope_type: str, scope_id: int | None):
    query = select(RoleAssignment).where(
        RoleAssignment.user_id == user_id, RoleAssignment.role_id == role,
        RoleAssignment.scope_type == scope_type, RoleAssignment.revoked_at.is_(None))
    query = query.where(RoleAssignment.scope_id.is_(None) if scope_id is None else RoleAssignment.scope_id == scope_id)
    return db.scalar(query.with_for_update())


def snapshot(a: RoleAssignment) -> dict:
    return {'assignment_id': a.assignment_id, 'user_id': a.user_id, 'role_id': a.role_id,
            'scope_type': a.scope_type, 'scope_id': a.scope_id,
            'revoked_at': a.revoked_at.isoformat() if a.revoked_at else None}


def grant(db: Session, actor: User, target_id: int, role_name: str, scope_type: str, scope_id: int | None,
          tournament=None) -> RoleAssignment:
    """Single grant path for every API. ``tournament`` must be the locked row when scope_type is TOURNAMENT."""
    if scope_type not in ALLOWED_SCOPES.get(role_name, ()):
        raise HTTPException(status_code=422, detail=f'Vai trò {role_name} không dùng được với phạm vi {scope_type}')
    if role_name == 'REFEREE':
        if not referees_grantable(tournament):
            raise HTTPException(status_code=409, detail='Giải đã kết thúc hoặc bị hủy, không thể cấp trọng tài')
        if target_id != actor.user_id and plays_in_tournament(db, tournament.tournament_id, target_id):
            raise HTTPException(status_code=409, detail='Người dùng đang thi đấu hoặc quản lý đội trong giải, không thể làm trọng tài')
    if target_id == actor.user_id:
        raise HTTPException(status_code=422, detail='Không thể tự cấp quyền cho chính mình')
    get_user_or_404(db, target_id)
    role = role_id(db, role_name)
    if active_assignment(db, target_id, role, scope_type, scope_id) is not None:
        raise HTTPException(status_code=409, detail='Người dùng đã có quyền này')
    assignment = RoleAssignment(user_id=target_id, role_id=role, scope_type=scope_type, scope_id=scope_id,
                                granted_by=actor.user_id, granted_at=datetime.now(timezone.utc))
    db.add(assignment)
    try:
        # Backstop for a concurrent grant that is not serialized by a tournament lock.
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail='Người dùng đã có quyền này') from None
    record_audit(db, actor.user_id, 'ROLE_ASSIGNMENT_GRANTED', 'role_assignment', {
        'tournament_id': tournament.tournament_id if tournament is not None else None, 'role': role_name, 'before': None, 'after': snapshot(assignment)})
    return assignment


def revoke(db: Session, actor: User, assignment: RoleAssignment, role_name: str,
           tournament_id: int | None = None) -> RoleAssignment:
    if assignment.revoked_at is not None:
        raise HTTPException(status_code=409, detail='Quyền này đã bị thu hồi')
    before = snapshot(assignment)
    assignment.revoked_at, assignment.revoked_by = datetime.now(timezone.utc), actor.user_id
    db.flush()
    record_audit(db, actor.user_id, 'ROLE_ASSIGNMENT_REVOKED', 'role_assignment', {
        'tournament_id': tournament_id, 'role': role_name, 'before': before, 'after': snapshot(assignment)})
    return assignment


def lock_assignment(db: Session, assignment_id: int) -> RoleAssignment | None:
    return db.scalar(select(RoleAssignment).where(RoleAssignment.assignment_id == assignment_id)
                     .with_for_update().execution_options(populate_existing=True))
