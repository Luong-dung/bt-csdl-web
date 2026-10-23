from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config.database import get_db
from core.security import decode_access_token
from modules.identity.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if (
        not isinstance(user_id, str) or not user_id.isascii()
        or not user_id.isdecimal() or len(user_id) > 10
        or not 0 < int(user_id) <= 2147483647
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không tồn tại", headers={"WWW-Authenticate": "Bearer"})
    return user


def has_role(user: User, *role_names: str, scope_type: str = "GLOBAL", scope_id: int | None = None) -> bool:
    """Global roles apply everywhere; scoped assignments match only their resource."""
    if user.role and user.role.role_name in role_names:
        return True
    return any(
        assignment.role.role_name in role_names
        and (
            (assignment.scope_type == "GLOBAL" and assignment.scope_id is None)
            or (scope_type != "GLOBAL" and scope_id is not None
                and assignment.scope_type == scope_type and assignment.scope_id == scope_id)
        )
        for assignment in user.assignments
    )


def require_role(*role_names: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_role(user, *role_names):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thực hiện thao tác này")
        return user

    return checker


def managed_teams_query(user: User):
    """One policy for team writes, capability reads and the managed-team picker."""
    from sqlalchemy import false, or_, select
    from modules.teams.models import Team, TeamMembership

    if has_role(user, "ADMIN"):
        return select(Team)
    membership = select(TeamMembership.membership_id).where(
        TeamMembership.team_id == Team.team_id,
        TeamMembership.user_id == user.user_id,
        TeamMembership.role_in_team == "MANAGER",
        TeamMembership.status == "ACTIVE",
        TeamMembership.left_date.is_(None),
    ).exists()
    team_ids, organization_ids = set(), set()
    for assignment in user.assignments:
        if assignment.role.role_name != 'TEAM_MANAGER' or assignment.scope_id is None:
            continue
        if assignment.scope_type == 'TEAM':
            team_ids.add(assignment.scope_id)
        elif assignment.scope_type == 'ORGANIZATION':
            organization_ids.add(assignment.scope_id)
    return select(Team).where(or_(
        membership,
        Team.team_id.in_(team_ids) if team_ids else false(),
        Team.organization_id.in_(organization_ids) if organization_ids else false(),
    ))


def can_manage_team(db: Session, team_id: int, user: User) -> bool:
    from modules.teams.models import Team

    # Existence remains the caller's responsibility, as in the original checker.
    if has_role(user, 'ADMIN'):
        return True
    return db.scalar(managed_teams_query(user).where(Team.team_id == team_id)) is not None


def can_manage_tournament(tournament, user: User) -> bool:
    """ADMIN, the ORGANIZER who created the tournament, or ORGANIZER assigned to it.

    Tournaments without a recorded creator are ADMIN-only.
    """
    if has_role(user, "ADMIN"):
        return True
    if tournament.created_by is None:
        return False
    if tournament.created_by == user.user_id and has_role(user, "ORGANIZER"):
        return True
    return any(
        a.role.role_name == "ORGANIZER" and a.scope_type == "TOURNAMENT" and a.scope_id == tournament.tournament_id
        for a in user.assignments
    )


def ensure_team_manager(db: Session, team_id: int, user: User) -> None:
    if not can_manage_team(db, team_id, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền quản lý đội này")
