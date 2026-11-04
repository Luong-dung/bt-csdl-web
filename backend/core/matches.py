"""W45 match building blocks shared by the result (W45-02) and lifecycle (W45-03) APIs.

Lock order: tournament -> match -> (teams by ascending ID, only if a caller needs them).
Callers own commit/rollback and write the audit row in the same transaction.
After waiting for a lock, always recheck permission, tournament and match state.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.rosters import approved_team
from core.tournaments import get_tournament_or_404, lock_tournament_as
from middleware.auth import can_manage_tournament
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import Match, Stage, Tournament, TournamentRoster

MATCH_STATUSES = ('PENDING', 'ONGOING', 'COMPLETED', 'CANCELLED')


# ---------- permission checkers (single policy for API enforcement and capabilities) ----------

def is_tournament_referee(tournament: Tournament, user: User) -> bool:
    """Only a REFEREE assignment scoped to THIS tournament counts.

    A REFEREE role on the user, a GLOBAL assignment or one for another tournament grants nothing.
    """
    return any(
        a.role.role_name == 'REFEREE' and a.scope_type == 'TOURNAMENT'
        and a.scope_id == tournament.tournament_id
        for a in user.assignments
    )


def can_manage_matches(tournament: Tournament, user: User) -> bool:
    """Create/edit/delete/cancel: tournament managers only (existing policy)."""
    return can_manage_tournament(tournament, user)


def can_start_match(db: Session, tournament: Tournament, match: Match, user: User) -> bool:
    """Permission only; lifecycle is checked by ``ensure_match_startable``."""
    return can_manage_tournament(tournament, user) or is_tournament_referee(tournament, user)


def can_submit_result(db: Session, tournament: Tournament, match: Match, user: User) -> bool:
    """Permission only; lifecycle is checked by ``ensure_result_submittable``."""
    return can_manage_tournament(tournament, user) or is_tournament_referee(tournament, user)


def can_cancel_match(db: Session, tournament: Tournament, match: Match, user: User) -> bool:
    return can_manage_matches(tournament, user)


# ---------- lifecycle rules ----------

def match_editable(tournament: Tournament, match: Match) -> bool:
    """Schedule/round/stage/teams can change, or the match can be deleted."""
    return (match.status == 'PENDING' and tournament.status in ('UPCOMING', 'ONGOING')
            and tournament.roster_locked_at is not None)


def match_startable(tournament: Tournament, match: Match) -> bool:
    return (match.status == 'PENDING' and tournament.status == 'ONGOING'
            and tournament.roster_locked_at is not None
            and match.team1_id is not None and match.team2_id is not None)


def match_result_open(tournament: Tournament, match: Match) -> bool:
    return match.status == 'ONGOING' and tournament.status == 'ONGOING'


def match_cancellable(tournament: Tournament, match: Match) -> bool:
    return match.status in ('PENDING', 'ONGOING') and tournament.status in ('UPCOMING', 'ONGOING')


def ensure_match_writable_tournament(tournament: Tournament) -> None:
    if tournament.status not in ('UPCOMING', 'ONGOING'):
        raise HTTPException(status_code=409, detail='Giải đã kết thúc hoặc bị hủy, không thể ghi trận')
    if tournament.roster_locked_at is None:
        raise HTTPException(status_code=409, detail='Cần khóa đội hình giải trước khi quản lý trận')


# ---------- reads and locks ----------

def get_match_or_404(db: Session, tournament_id: int, match_id: int) -> Match:
    match = db.scalar(select(Match).where(Match.tournament_id == tournament_id, Match.match_id == match_id))
    if match is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy trận đấu trong giải')
    return match


def lock_match(db: Session, tournament_id: int, match_id: int) -> Match:
    """Caller must already hold the tournament lock (see ``lock_match_context``)."""
    match = db.scalar(select(Match).where(Match.tournament_id == tournament_id, Match.match_id == match_id)
                      .with_for_update().execution_options(populate_existing=True))
    if match is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy trận đấu trong giải')
    return match


def lock_match_context(db: Session, tournament_id: int, match_id: int, user: User,
                       checker) -> tuple[Tournament, Match, User]:
    """Reject before queuing, lock tournament -> match, reload the actor and recheck.

    ``checker`` is one of the ``can_*(db, tournament, match, user)`` functions above.
    Raises 404/403; lifecycle (409) stays with the caller so idempotent replays work.
    """
    tournament = get_tournament_or_404(db, tournament_id)
    match = get_match_or_404(db, tournament_id, match_id)
    if not checker(db, tournament, match, user):
        raise HTTPException(status_code=403, detail='Bạn không có quyền thao tác trận đấu này')
    tournament, user = lock_tournament_as(db, tournament_id, user)
    match = lock_match(db, tournament_id, match_id)
    if not checker(db, tournament, match, user):
        raise HTTPException(status_code=403, detail='Bạn không có quyền thao tác trận đấu này')
    return tournament, match, user


# ---------- link validation for create/edit (caller holds the tournament lock) ----------

def ensure_stage_in_tournament(db: Session, tournament_id: int, stage_id: int) -> Stage:
    stage = db.scalar(select(Stage).where(Stage.stage_id == stage_id, Stage.tournament_id == tournament_id))
    if stage is None:
        raise HTTPException(status_code=422, detail='Vòng đấu không thuộc giải này')
    return stage


def ensure_match_teams(db: Session, tournament: Tournament, team1_id: int, team2_id: int) -> None:
    """Two distinct APPROVED teams of the tournament's game, each with a locked PLAYER snapshot."""
    if team1_id == team2_id:
        raise HTTPException(status_code=422, detail='Hai đội của trận phải khác nhau')
    tid = tournament.tournament_id
    for team_id in sorted((team1_id, team2_id)):
        team = db.get(Team, team_id)
        if team is None or team.game_id != tournament.game_id or not approved_team(db, tid, team_id):
            raise HTTPException(status_code=422, detail='Đội không được duyệt tham gia giải này')
        has_player = db.scalar(select(TournamentRoster.roster_id).where(
            TournamentRoster.tournament_id == tid, TournamentRoster.team_id == team_id,
            TournamentRoster.role_in_team == 'PLAYER').limit(1)) is not None
        if not has_player:
            raise HTTPException(status_code=422, detail='Đội chưa có tuyển thủ PLAYER trong đội hình đã khóa')


def to_utc(value: datetime | None) -> datetime | None:
    """Writers must store UTC: SQLite drops offsets, so never persist a non-UTC aware value."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=422, detail='Giờ thi đấu phải kèm múi giờ (offset)')
    return value.astimezone(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Read side: PostgreSQL returns aware UTC, SQLite returns naive values stored as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def match_state(match: Match) -> dict:
    """Audit snapshot (before/after)."""
    return {
        'match_id': match.match_id, 'stage_id': match.stage_id, 'round_no': match.round_no,
        'team1_id': match.team1_id, 'team2_id': match.team2_id,
        'score_team1': match.score_team1, 'score_team2': match.score_team2,
        'winner_id': match.winner_id, 'status': match.status,
        'scheduled_at': as_utc(match.scheduled_at).isoformat() if match.scheduled_at else None,
    }
