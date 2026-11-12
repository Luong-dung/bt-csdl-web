"""W46-03: preview and create the managed single-elimination bracket. W46-04: public tree and standings.

Preview validates live input without locks or writes and signs a short-lived token. Create
locks the tournament, rechecks the actor, resolves an idempotent replay, then validates the
live input again (the token never replaces that) and writes header + N-1 matches + metadata
+ one audit row in a single transaction. Any failure rolls everything back.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.brackets import (PREVIEW_TTL_SECONDS, bracket_plan, ensure_bracket_input, get_bracket,
                           issue_preview_token, lock_bracket_context, verify_preview_token)
from core.matches import as_utc
from core.tournaments import get_tournament_or_404
from core.validation import INT_MAX, ResourceId
from middleware.auth import can_manage_tournament, get_current_user
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.bracket_schemas import (BracketCreate, BracketInput, BracketNodeRead, BracketPreviewRead,
                                                 BracketRead, BracketStandingRead, BracketStandingsRead, BracketTeam)
from modules.tournaments.match_schemas import match_reads
from modules.tournaments.models import BracketMatch, Match, Tournament, TournamentBracket

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}/bracket', tags=['Brackets'])


def bracket_read(db: Session, bracket: TournamentBracket) -> BracketRead:
    """Whole tree from metadata in one query; the caller decides the snapshot it reads in."""
    rows = db.execute(select(BracketMatch, Match).join(Match, Match.match_id == BracketMatch.match_id)
                      .where(BracketMatch.bracket_id == bracket.bracket_id)
                      .order_by(BracketMatch.round_index, BracketMatch.position)).all()
    positions = {(node.round_index, node.position): node.match_id for node, _ in rows}
    reads = match_reads(db, [match for _, match in rows])
    return BracketRead(
        bracket_id=bracket.bracket_id, tournament_id=bracket.tournament_id, stage_id=bracket.stage_id,
        team_count=bracket.team_count, round_count=bracket.round_count, team_ids=list(bracket.team_order),
        created_at=as_utc(bracket.created_at),
        matches=[BracketNodeRead(round_index=node.round_index, position=node.position, next_round=node.next_round,
                                 next_position=node.next_position, next_slot=node.next_slot,
                                 next_match_id=positions.get((node.next_round, node.next_position)), match=read)
                 for (node, _), read in zip(rows, reads)],
    )


def ensure_no_bracket(db: Session, tournament: Tournament) -> None:
    if get_bracket(db, tournament.tournament_id) is not None:
        raise HTTPException(409, 'Giải đã có bracket, không thể tạo thêm')


@router.post('/preview', response_model=BracketPreviewRead)
def preview_bracket(tournament_id: ResourceId, data: BracketInput,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        tournament = get_tournament_or_404(db, tournament_id)
        if not can_manage_tournament(tournament, user):
            raise HTTPException(403, 'Bạn không có quyền tạo bracket trong giải này')
        ensure_no_bracket(db, tournament)
        fingerprint = ensure_bracket_input(db, tournament, data)
        names = dict(db.execute(select(Team.team_id, Team.name).where(Team.team_id.in_(data.team_ids))).all())
        plan = bracket_plan(data)
        return BracketPreviewRead(
            tournament_id=tournament_id, stage_id=data.stage_id, team_ids=data.team_ids,
            teams=[BracketTeam(team_id=tid, name=names[tid]) for tid in data.team_ids],
            team_count=len(data.team_ids), round_count=plan[-1].round_index, matches=plan,
            preview_token=issue_preview_token(tournament_id, fingerprint), expires_in=PREVIEW_TTL_SECONDS,
        )
    finally:
        db.rollback()  # read-only: never leave a transaction open or write anything


def write_bracket(db: Session, tournament: Tournament, user: User, data: BracketInput) -> TournamentBracket:
    """Caller holds the tournament lock and has validated the live input."""
    plan = bracket_plan(data)
    tid, rounds = tournament.tournament_id, plan[-1].round_index
    bracket = TournamentBracket(tournament_id=tid, stage_id=data.stage_id, team_count=len(data.team_ids),
                                round_count=rounds, team_order=list(data.team_ids), created_by=user.user_id,
                                created_at=datetime.now(timezone.utc))
    db.add(bracket)
    matches = [Match(tournament_id=tid, stage_id=data.stage_id, round_no=item.round_index, team1_id=item.team1_id,
                     team2_id=item.team2_id, status='PENDING', score_team1=0, score_team2=0)
               for item in plan]
    db.add_all(matches)
    db.flush()
    # Destination rows must exist before their sources: insert later rounds first.
    for item, match in sorted(zip(plan, matches), key=lambda pair: -pair[0].round_index):
        db.add(BracketMatch(match_id=match.match_id, bracket_id=bracket.bracket_id, tournament_id=tid,
                            stage_id=data.stage_id, round_count=rounds, round_index=item.round_index,
                            position=item.position, next_round=item.next_round,
                            next_position=item.next_position, next_slot=item.next_slot))
        db.flush()
    record_audit(db, user.user_id, 'BRACKET_CREATED', 'bracket', {
        'tournament_id': tid, 'bracket_id': bracket.bracket_id, 'stage_id': data.stage_id,
        'team_ids': list(data.team_ids), 'team_count': bracket.team_count, 'round_count': rounds,
        'match_ids': [match.match_id for match in matches],
    })
    return bracket


@router.post('', response_model=BracketRead, status_code=201)
def create_bracket(tournament_id: ResourceId, data: BracketCreate, response: Response,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        tournament, user = lock_bracket_context(db, tournament_id, user)
        existing = get_bracket(db, tournament_id)
        if existing is not None:
            # Retry after a timeout returns the same bracket without writing, even with an expired token.
            if existing.stage_id != data.stage_id or list(existing.team_order) != data.team_ids:
                raise HTTPException(409, 'Giải đã có bracket với danh sách đội khác')
            result = bracket_read(db, existing)
            db.rollback()
            response.status_code = 200
            return result
        input_data = BracketInput(stage_id=data.stage_id, team_ids=data.team_ids)
        verify_preview_token(data.preview_token, tournament_id, ensure_bracket_input(db, tournament, input_data))
        bracket = write_bracket(db, tournament, user, input_data)
        result = bracket_read(db, bracket)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Bracket vi phạm ràng buộc dữ liệu hoặc đã thay đổi') from None
    except Exception:
        db.rollback()
        raise


def bracket_or_404(db: Session, tournament_id: int) -> TournamentBracket:
    get_tournament_or_404(db, tournament_id)
    bracket = get_bracket(db, tournament_id)
    if bracket is None:
        raise HTTPException(404, 'Giải chưa có bracket')
    return bracket


@router.get('', response_model=BracketRead)
def read_bracket(tournament_id: ResourceId, db: Session = Depends(get_db)):
    """Public. Header/metadata are immutable after creation; every match state comes from one SELECT."""
    try:
        return bracket_read(db, bracket_or_404(db, tournament_id))
    finally:
        db.rollback()


def derive_standings(bracket: TournamentBracket, rows) -> tuple[str, dict[int, dict]]:
    """Only COMPLETED managed matches count, each once. A loser in round r (2^(R-r+1) teams left)
    gets rank 2^(R-r)+1; the final's winner gets 1; nobody else is ranked yet. No 0-0 inference."""
    stats = {tid: {'rank': None, 'matches_played': 0, 'wins': 0, 'losses': 0} for tid in bracket.team_order}
    final_done = False
    for row in rows:
        if row.status != 'COMPLETED' or row.winner_id is None:
            continue
        loser = row.team2_id if row.winner_id == row.team1_id else row.team1_id
        for tid in (row.winner_id, loser):
            stats[tid]['matches_played'] += 1
        stats[row.winner_id]['wins'] += 1
        stats[loser]['losses'] += 1
        stats[loser]['rank'] = (1 << (bracket.round_count-row.round_index))+1
        if row.round_index == bracket.round_count:
            stats[row.winner_id]['rank'] = 1
            final_done = True
    cancelled = rows[0].tournament_status == 'CANCELLED' if rows else False
    return ('CANCELLED' if cancelled else 'FINAL' if final_done else 'PROVISIONAL'), stats


@router.get('/standings', response_model=BracketStandingsRead)
def read_bracket_standings(tournament_id: ResourceId, response: Response, db: Session = Depends(get_db),
                           offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
                           limit: Annotated[int, Query(ge=1, le=100)] = 50):
    """Public. Tournament status and every match result are read in a single SELECT (one snapshot)."""
    try:
        bracket = bracket_or_404(db, tournament_id)
        rows = db.execute(select(Tournament.status.label('tournament_status'), BracketMatch.round_index,
                                 Match.status, Match.team1_id, Match.team2_id, Match.winner_id)
                          .join(Match, Match.match_id == BracketMatch.match_id)
                          .join(Tournament, Tournament.tournament_id == BracketMatch.tournament_id)
                          .where(BracketMatch.bracket_id == bracket.bracket_id)).all()
        status, stats = derive_standings(bracket, rows)
        order = {tid: index for index, tid in enumerate(bracket.team_order)}
        ranked = sorted(stats, key=lambda tid: (stats[tid]['rank'] is None, stats[tid]['rank'] or 0, order[tid]))
        page = ranked[offset:offset+limit]
        names = dict(db.execute(select(Team.team_id, Team.name).where(Team.team_id.in_(page))).all()) if page else {}
        response.headers['X-Total-Count'] = str(len(ranked))
        return BracketStandingsRead(
            bracket_id=bracket.bracket_id, status=status, total=len(ranked), offset=offset, limit=limit,
            items=[BracketStandingRead(team=BracketTeam(team_id=tid, name=names[tid]), **stats[tid]) for tid in page],
        )
    finally:
        db.rollback()
