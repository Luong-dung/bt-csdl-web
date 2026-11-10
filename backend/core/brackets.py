"""Shared W46 contract. Callers own transactions; helpers never commit or write audit."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.matches import as_utc, ensure_stage_in_tournament, get_match_or_404, match_state
from core.tournaments import get_tournament_or_404, lock_tournament_as
from middleware.auth import can_manage_tournament
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.bracket_schemas import BracketInput, BracketPlanMatch
from modules.tournaments.models import BracketMatch, Match, Tournament, TournamentBracket, TournamentRegistration, TournamentRoster

PREVIEW_TTL_SECONDS = 900
PREVIEW_AUDIENCE = 'bracket-preview'


def get_bracket(db: Session, tournament_id: int) -> TournamentBracket | None:
    return db.scalar(select(TournamentBracket).where(TournamentBracket.tournament_id == tournament_id))


def managed_match(db: Session, match_id: int) -> BracketMatch | None:
    """Do not infer managed membership from legacy next_match_id."""
    return db.get(BracketMatch, match_id)


def ensure_manual_stage(db: Session, stage_id: int) -> None:
    if db.scalar(select(TournamentBracket.bracket_id).where(TournamentBracket.stage_id == stage_id)) is not None:
        raise HTTPException(409, 'Không thêm hoặc chuyển trận thủ công vào stage của bracket')


def advance_bracket_winner(db: Session, match: Match, destination: Match | None, winner_id: int,
                           replay: bool = False) -> dict | None:
    """Caller holds tournament and both match locks. Replay verifies, never repairs a slot."""
    node = managed_match(db, match.match_id)
    if node is None or node.next_round is None:
        return None
    if destination is None:
        raise HTTPException(409, 'Bracket thiếu trận đích')
    field = 'team1_id' if node.next_slot == 1 else 'team2_id'
    existing = getattr(destination, field)
    if replay:
        if existing != winner_id:
            raise HTTPException(409, 'Kết quả và đội ở trận sau không nhất quán')
        return None
    other = destination.team2_id if node.next_slot == 1 else destination.team1_id
    if destination.status != 'PENDING' or existing not in (None, winner_id) or other == winner_id:
        raise HTTPException(409, 'Không thể điền đội thắng vào trận sau đã thay đổi')
    before = match_state(destination)
    setattr(destination, field, winner_id)
    return {'match_id': destination.match_id, 'slot': node.next_slot,
            'before': before, 'after': match_state(destination)}


def tournament_completion_error(db: Session, tournament: Tournament) -> str | None:
    """Shared by the status mutation and its capability, after parent lock on writes."""
    tid = tournament.tournament_id
    if db.scalar(select(Match.match_id).where(Match.tournament_id == tid,
                                             Match.status.in_(['PENDING', 'ONGOING'])).limit(1)) is not None:
        return 'Cần xử lý hết các trận chưa kết thúc trước khi hoàn tất giải'
    bracket = get_bracket(db, tid)
    if bracket is not None:
        rows = db.execute(select(BracketMatch.round_index, Match.status, Match.winner_id, Match.team1_id, Match.team2_id)
                          .join(Match, Match.match_id == BracketMatch.match_id)
                          .where(BracketMatch.bracket_id == bracket.bracket_id)).all()
        finals = [r for r in rows if r.round_index == bracket.round_count]
        if (len(rows) != bracket.team_count-1 or any(r.status != 'COMPLETED' for r in rows)
                or len(finals) != 1 or finals[0].winner_id is None
                or finals[0].winner_id not in (finals[0].team1_id, finals[0].team2_id)):
            return 'Bracket chưa đầy đủ hoặc chưa có kết quả chung kết hợp lệ'
    return None


def can_create_bracket(db: Session, tournament: Tournament, user: User) -> bool:
    """Lifecycle/permission hint; input eligibility still needs validation under the lock."""
    return (can_manage_tournament(tournament, user) and tournament.status == 'UPCOMING'
            and tournament.format == 'SINGLE_ELIM' and tournament.roster_locked_at is not None
            and get_bracket(db, tournament.tournament_id) is None)


def lock_bracket_context(db: Session, tournament_id: int, user: User) -> tuple[Tournament, User]:
    """Serialize writers on tournament, reloading the actor/assignments after the wait.

    Does not reject an existing bracket: create must resolve idempotent replay first.
    After this lock, lock any affected Matches in ascending match_id, then recheck policy/state.
    """
    tournament = get_tournament_or_404(db, tournament_id)
    if not can_manage_tournament(tournament, user):
        raise HTTPException(403, 'Bạn không có quyền tạo bracket trong giải này')
    tournament, user = lock_tournament_as(db, tournament_id, user)
    if not can_manage_tournament(tournament, user):
        raise HTTPException(403, 'Bạn không còn quyền tạo bracket trong giải này')
    return tournament, user


def ensure_bracket_input(db: Session, tournament: Tournament, data: BracketInput) -> str:
    """Return a fingerprint of validated live input. Create calls this after taking the tournament lock.

    Preview may run without locks, but its token never replaces this validation on create.
    Reject existing bracket/replay separately before invoking this helper.
    """
    if (tournament.status != 'UPCOMING' or tournament.roster_locked_at is None
            or tournament.format != 'SINGLE_ELIM'):
        raise HTTPException(409, 'Cần giải SINGLE_ELIM sắp diễn ra và đã khóa đội hình')
    stage = ensure_stage_in_tournament(db, tournament.tournament_id, data.stage_id)
    if db.scalar(select(Match.match_id).where(Match.stage_id == stage.stage_id).limit(1)) is not None:
        raise HTTPException(409, 'Stage đã có trận, không thể tạo bracket')
    tid = tournament.tournament_id
    approved = list(db.execute(select(TournamentRegistration.team_id, Team.game_id)
                              .join(Team, Team.team_id == TournamentRegistration.team_id)
                              .where(TournamentRegistration.tournament_id == tid,
                                     TournamentRegistration.status == 'APPROVED')
                              .order_by(TournamentRegistration.team_id)).all())
    if ({row.team_id for row in approved} != set(data.team_ids)
            or any(row.game_id != tournament.game_id for row in approved)):
        raise HTTPException(422, 'Cần đủ toàn bộ đội APPROVED cùng game của giải')
    roster = list(db.execute(select(TournamentRoster.team_id, TournamentRoster.user_id, TournamentRoster.role_in_team)
                            .where(TournamentRoster.tournament_id == tid,
                                   TournamentRoster.team_id.in_(data.team_ids))
                            .order_by(TournamentRoster.team_id, TournamentRoster.user_id)).all())
    players = {row.team_id for row in roster if row.role_in_team == 'PLAYER'}
    if players != set(data.team_ids):
        raise HTTPException(422, 'Mỗi đội cần PLAYER trong snapshot đội hình đã khóa')
    snapshot = {'v': 1, 'tid': tid, 'game_id': tournament.game_id, 'stage_id': data.stage_id,
                'team_ids': data.team_ids, 'locked_at': as_utc(tournament.roster_locked_at).isoformat(),
                'roster': [list(row) for row in roster]}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def lock_bracket_match_context(db: Session, tournament_id: int, match_id: int, user: User, checker):
    """For W46-02: lock tournament -> source/destination in ID order; recheck current actor.

    Works for manual/legacy matches too (destination=None). Never traverse legacy next_match_id.
    checker has the same signature as W45 can_submit_result/can_start_match. Caller validates
    lifecycle, writes source/slot/audit and owns commit/rollback, including idempotent replays.
    """
    tournament = get_tournament_or_404(db, tournament_id)
    match = get_match_or_404(db, tournament_id, match_id)
    if not checker(db, tournament, match, user):
        raise HTTPException(403, 'Bạn không có quyền thao tác trận đấu này')
    tournament, user = lock_tournament_as(db, tournament_id, user)
    # Metadata is immutable after creation; read after taking the shared parent lock.
    node = db.get(BracketMatch, match_id, populate_existing=True)
    destination_id = None
    if node is not None and node.next_round is not None:
        destination_id = db.scalar(select(BracketMatch.match_id).where(
            BracketMatch.bracket_id == node.bracket_id, BracketMatch.round_index == node.next_round,
            BracketMatch.position == node.next_position))
        if destination_id is None:
            raise HTTPException(409, 'Bracket thiếu trận đích, không thể ghi kết quả')
    ids = [match_id] if destination_id is None else [match_id, destination_id]
    locked = {m.match_id: m for m in db.scalars(select(Match).where(
        Match.tournament_id == tournament_id, Match.match_id.in_(ids)).order_by(Match.match_id)
        .with_for_update().execution_options(populate_existing=True))}
    if match_id not in locked:
        raise HTTPException(404, 'Không tìm thấy trận đấu trong giải')
    if len(locked) != len(ids):
        raise HTTPException(409, 'Bracket liên kết trận đích không hợp lệ')
    match = locked[match_id]
    if not checker(db, tournament, match, user):
        raise HTTPException(403, 'Bạn không còn quyền thao tác trận đấu này')
    return tournament, match, locked.get(destination_id), user


def bracket_plan(data: BracketInput) -> list[BracketPlanMatch]:
    """Stable round/position order, adjacent input pairs, explicit destination slot, no IDs invented."""
    count = len(data.team_ids)
    rounds = count.bit_length()-1
    plan = []
    for round_index in range(1, rounds+1):
        for position in range(1, (count >> round_index)+1):
            final = round_index == rounds
            plan.append(BracketPlanMatch(
                round_index=round_index, position=position,
                team1_id=data.team_ids[2*(position-1)] if round_index == 1 else None,
                team2_id=data.team_ids[2*(position-1)+1] if round_index == 1 else None,
                next_round=None if final else round_index+1,
                next_position=None if final else (position+1)//2,
                next_slot=None if final else 1+(position-1)%2,
            ))
    return plan


def issue_preview_token(tournament_id: int, fingerprint: str) -> str:
    return jwt.encode({'purpose': 'bracket-preview-v1', 'aud': PREVIEW_AUDIENCE,
                       'tid': tournament_id, 'fingerprint': fingerprint,
                       'exp': datetime.now(timezone.utc)+timedelta(seconds=PREVIEW_TTL_SECONDS)},
                      get_settings().JWT_SECRET, algorithm='HS256')


def verify_preview_token(token: str, tournament_id: int, fingerprint: str) -> None:
    try:
        payload = jwt.decode(token, get_settings().JWT_SECRET, algorithms=['HS256'],
                             audience=PREVIEW_AUDIENCE,
                             options={'require': ['purpose', 'aud', 'tid', 'fingerprint', 'exp']})
    except jwt.InvalidTokenError:
        raise HTTPException(409, 'Preview hết hạn hoặc không hợp lệ, hãy xem lại bracket') from None
    if (payload['purpose'] != 'bracket-preview-v1' or payload['tid'] != tournament_id
            or payload['fingerprint'] != fingerprint):
        raise HTTPException(409, 'Dữ liệu preview đã thay đổi, hãy xem lại bracket')
