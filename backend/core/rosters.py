"""Roster building blocks. Callers own commit/rollback and audit in one transaction.

Order: tournament -> teams (ascending ID) -> memberships (ascending ID) -> roster.
Membership writers also lock the team; this covers inserts as well as existing rows.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.tournament_policy import roster_editable
from core.tournaments import get_tournament_or_404, lock_tournament_as
from middleware.auth import can_manage_team
from modules.identity.models import User
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration, TournamentRoster


def approved_team(db: Session, tournament_id: int, team_id: int) -> bool:
    return db.scalar(select(TournamentRegistration.registration_id).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.team_id == team_id,
        TournamentRegistration.status == 'APPROVED',
    )) is not None



def approved_team_ids(db: Session, tournament_id: int) -> list[int]:
    return list(db.scalars(select(TournamentRegistration.team_id).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.status == 'APPROVED',
    ).order_by(TournamentRegistration.team_id)))


def approved_teams_without_player(db: Session, tournament_id: int) -> list[int]:
    with_player = set(db.scalars(select(TournamentRoster.team_id).where(
        TournamentRoster.tournament_id == tournament_id, TournamentRoster.role_in_team == 'PLAYER')))
    return [team_id for team_id in approved_team_ids(db, tournament_id) if team_id not in with_player]

def ensure_roster_editable(tournament: Tournament) -> None:
    if not roster_editable(tournament):
        raise HTTPException(status_code=409, detail="Đội hình đã khóa hoặc giải không còn UPCOMING")


def roster_permissions(db: Session, tournament: Tournament, team_id: int, user: User,
                       manages_tournament: bool) -> tuple[bool, bool]:
    accepted = approved_team(db, tournament.tournament_id, team_id)
    manages_team = can_manage_team(db, team_id, user)
    can_view = accepted and (tournament.roster_locked_at is not None or manages_team or manages_tournament)
    return can_view, accepted and manages_team and roster_editable(tournament)


def lock_roster_teams(db: Session, team_ids: list[int]) -> list[Team]:
    """Caller already holds tournament lock. No commit, including for an empty list."""
    teams = list(db.scalars(select(Team).where(Team.team_id.in_(set(team_ids)))
                           .order_by(Team.team_id).with_for_update()
                           .execution_options(populate_existing=True)))
    if len(teams) != len(set(team_ids)):
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    return teams


def lock_roster_memberships(db: Session, team_ids: list[int]) -> list[TeamMembership]:
    """Lock teams first so membership inserts/changes cannot race this validation."""
    lock_roster_teams(db, team_ids)
    return list(db.scalars(select(TeamMembership).where(TeamMembership.team_id.in_(team_ids))
                           .order_by(TeamMembership.membership_id).with_for_update()
                           .execution_options(populate_existing=True)))


def lock_roster_rows(db: Session, tournament_id: int) -> list[TournamentRoster]:
    return list(db.scalars(select(TournamentRoster).where(TournamentRoster.tournament_id == tournament_id)
                           .order_by(TournamentRoster.roster_id).with_for_update()
                           .execution_options(populate_existing=True)))


def lock_membership_team(db: Session, team_id: int, user: User) -> User:
    """Membership-only writers lock team, never acquire a tournament afterwards."""
    lock_roster_teams(db, [team_id])
    if isinstance(user, User):
        user = db.get(User, user.user_id, populate_existing=True)
        if user is None:
            raise HTTPException(status_code=401, detail='Tài khoản không tồn tại',
                                headers={'WWW-Authenticate': 'Bearer'})
        db.expire(user, ['role', 'assignments'])
    return user


def get_editable_roster_context(db: Session, tournament_id: int, team_id: int,
                               user: User) -> tuple[Tournament, User]:
    """For W44-2-03: reject before queuing, then recheck refreshed rights after locks."""
    get_tournament_or_404(db, tournament_id)
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    if not can_manage_team(db, team_id, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản lý đội này")
    tournament, user = lock_tournament_as(db, tournament_id, user)
    lock_roster_teams(db, [team_id])
    if not can_manage_team(db, team_id, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản lý đội này")
    ensure_roster_editable(tournament)
    if not approved_team(db, tournament_id, team_id):
        raise HTTPException(status_code=409, detail="Đội chưa được duyệt tham gia giải")
    return tournament, user
