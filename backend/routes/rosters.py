"""Roster reads and draft replacement. Locking the roster is W44-2-04."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.rosters import (
    approved_team, get_editable_roster_context, lock_roster_memberships, lock_roster_rows, roster_permissions,
)
from core.tournaments import get_tournament_or_404
from core.validation import ResourceId
from middleware.auth import can_manage_tournament, get_current_user, get_optional_user
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import TournamentRoster
from modules.tournaments.roster_schemas import (
    RosterCapabilities, RosterLockRead, RosterMemberRead, RosterRead, RosterReplace,
)

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}', tags=['Tournament rosters'])


def ensure_team(db: Session, team_id: int) -> None:
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy đội tuyển')


def roster_read(tournament_id: int, team_id: int, locked: bool, rows) -> RosterRead:
    members = sorted((RosterMemberRead.model_validate(row) for row in rows), key=lambda m: m.user_id)
    return RosterRead(tournament_id=tournament_id, team_id=team_id, locked=locked, members=members)


def snapshot(rows) -> list[dict]:
    return [{'user_id': row.user_id, 'role_in_team': row.role_in_team, 'display_name': row.display_name}
            for row in sorted(rows, key=lambda row: row.user_id)]


@router.get('/roster-lock', response_model=RosterLockRead)
def roster_lock_state(tournament_id: ResourceId, db: Session = Depends(get_db)):
    tournament = get_tournament_or_404(db, tournament_id)
    return RosterLockRead(tournament_id=tournament_id, locked=tournament.roster_locked_at is not None,
                          locked_at=tournament.roster_locked_at)


@router.get('/teams/{team_id}/roster/capabilities', response_model=RosterCapabilities)
def roster_capabilities(tournament_id: ResourceId, team_id: ResourceId,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tournament = get_tournament_or_404(db, tournament_id)
    ensure_team(db, team_id)
    view, edit = roster_permissions(db, tournament, team_id, user, can_manage_tournament(tournament, user))
    return RosterCapabilities(tournament_id=tournament_id, team_id=team_id,
                              can_view_roster=view, can_edit_roster=edit)


@router.get('/teams/{team_id}/roster', response_model=RosterRead)
def get_roster(tournament_id: ResourceId, team_id: ResourceId,
               user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    tournament = get_tournament_or_404(db, tournament_id)
    ensure_team(db, team_id)
    if not approved_team(db, tournament_id, team_id):
        raise HTTPException(status_code=404, detail='Đội chưa được duyệt tham gia giải')
    locked = tournament.roster_locked_at is not None
    if not locked:
        # Drafts are private: anonymous callers must log in, others need team/tournament rights.
        if user is None:
            raise HTTPException(status_code=401, detail='Cần đăng nhập để xem đội hình nháp',
                                headers={'WWW-Authenticate': 'Bearer'})
        can_view, _ = roster_permissions(db, tournament, team_id, user, can_manage_tournament(tournament, user))
        if not can_view:
            raise HTTPException(status_code=403, detail='Bạn không có quyền xem đội hình nháp này')
    rows = db.scalars(select(TournamentRoster).where(TournamentRoster.tournament_id == tournament_id,
                                                     TournamentRoster.team_id == team_id))
    return roster_read(tournament_id, team_id, locked, rows)


@router.put('/teams/{team_id}/roster', response_model=RosterRead)
def replace_roster(tournament_id: ResourceId, team_id: ResourceId, data: RosterReplace,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Lock order: tournament -> team -> memberships -> roster rows (see core.rosters).
    _, actor = get_editable_roster_context(db, tournament_id, team_id, user)
    eligible = {m.user_id: m for m in lock_roster_memberships(db, [team_id])
                if m.status == 'ACTIVE' and m.left_date is None and m.role_in_team in ('PLAYER', 'SUBSTITUTE')}
    for member in data.members:
        membership = eligible.get(member.user_id)
        if membership is None:
            raise HTTPException(status_code=422,
                                detail=f'User {member.user_id} không phải tuyển thủ/dự bị đang hoạt động của đội')
        if membership.role_in_team != member.role_in_team:
            raise HTTPException(status_code=422,
                                detail=f'Vai trò của user {member.user_id} không khớp vai trò trong đội')
    rows = lock_roster_rows(db, tournament_id)
    requested = {member.user_id: member.role_in_team for member in data.members}
    if any(row.team_id != team_id and row.user_id in requested for row in rows):
        raise HTTPException(status_code=409, detail='Tuyển thủ đã có trong đội hình của đội khác trong giải')
    current = {row.user_id: row for row in rows if row.team_id == team_id}
    before = snapshot(current.values())
    try:
        for user_id, row in current.items():
            if user_id not in requested:
                db.delete(row)
        for user_id, role in requested.items():
            # Display name is a snapshot of the username when saved; W44-2-04 retakes it at lock time.
            name = eligible[user_id].user.username
            row = current.get(user_id)
            if row is None:
                row = TournamentRoster(tournament_id=tournament_id, team_id=team_id, user_id=user_id)
                db.add(row)
                current[user_id] = row
            row.role_in_team, row.display_name = role, name
        db.flush()
        saved = [row for user_id, row in current.items() if user_id in requested]
        after = snapshot(saved)
        result = roster_read(tournament_id, team_id, False, saved)
        if before == after:
            db.rollback()  # nothing changed; release locks without a duplicate audit
            return result
        record_audit(db, actor.user_id, 'TOURNAMENT_ROSTER_UPDATED', 'tournament_roster', {
            'tournament_id': tournament_id, 'team_id': team_id, 'before': before, 'after': after,
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Đội hình vi phạm ràng buộc dữ liệu, vui lòng tải lại')
    except Exception:
        db.rollback()
        raise
    return result
