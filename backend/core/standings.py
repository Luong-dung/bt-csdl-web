"""W46-04 standings derived from bracket results; W48-04 (b) final snapshot in tournament_standings.

While a tournament is running, standings are derived on read from COMPLETED managed matches.
When it becomes COMPLETED (results are then frozen: ``match_result_open`` needs ONGOING), the
final table is written once to ``tournament_standings`` in the status-change transaction, with
an audit row. Reads of a COMPLETED tournament use that snapshot and fall back to deriving when
it has no rows (e.g. finished before the backfill ran).
"""
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.audit import record_audit
from core.brackets import get_bracket
from modules.identity.models import User
from modules.tournaments.models import BracketMatch, Match, Tournament, TournamentBracket, TournamentStanding

logger = logging.getLogger('esports_tournament')

STANDINGS_FINALIZED = 'TOURNAMENT_STANDINGS_FINALIZED'


def bracket_result_rows(db: Session, bracket: TournamentBracket):
    """Tournament status and every managed match result in a single SELECT (one snapshot)."""
    return db.execute(select(Tournament.status.label('tournament_status'), BracketMatch.round_index,
                             Match.status, Match.team1_id, Match.team2_id, Match.winner_id)
                      .join(Match, Match.match_id == BracketMatch.match_id)
                      .join(Tournament, Tournament.tournament_id == BracketMatch.tournament_id)
                      .where(BracketMatch.bracket_id == bracket.bracket_id)).all()


def derive_standings(bracket: TournamentBracket, rows) -> tuple[str, dict[int, dict]]:
    """Only COMPLETED managed matches count, each once. A loser in round r (2^(R-r+1) teams left)
    gets rank 2^(R-r)+1; the final's winner gets 1; nobody else is ranked yet. No 0-0 inference."""
    stats = {tid: {'rank': None, 'matches_played': 0, 'wins': 0, 'losses': 0} for tid in bracket.team_order}
    final_done = False
    for row in rows:
        if row.status != 'COMPLETED' or row.winner_id is None:
            continue
        loser = row.team2_id if row.winner_id == row.team1_id else row.team1_id
        if row.winner_id not in (row.team1_id, row.team2_id) or row.winner_id not in stats or loser not in stats:
            # The DB CHECK forbids this; never guess a loser from broken data.
            logger.warning('Bỏ qua trận bracket %s có winner/đội không hợp lệ', bracket.bracket_id)
            continue
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


def standing_order(bracket: TournamentBracket, stats: dict[int, dict]) -> list[int]:
    """Teams still alive (rank null) first, by wins desc; then eliminated teams by rank asc.
    Ties keep the confirmed team_order."""
    order = {tid: index for index, tid in enumerate(bracket.team_order)}
    return sorted(stats, key=lambda tid: (stats[tid]['rank'] is not None, stats[tid]['rank'] or 0,
                                          -stats[tid]['wins'], order[tid]))


def stored_standings(db: Session, bracket: TournamentBracket) -> dict[int, dict] | None:
    """The snapshot written at completion, or None when it is missing or does not cover the bracket."""
    rows = db.scalars(select(TournamentStanding)
                      .where(TournamentStanding.tournament_id == bracket.tournament_id)).all()
    if not rows:
        return None
    stats = {row.team_id: {'rank': row.final_rank, 'matches_played': row.matches_played,
                           'wins': row.wins, 'losses': row.losses} for row in rows}
    if set(stats) != set(bracket.team_order):
        logger.warning('Bảng xếp hạng lưu của giải %s không khớp bracket; tính lại từ kết quả', bracket.tournament_id)
        return None
    return stats


def finalize_standings(db: Session, tournament: Tournament, user: User) -> int:
    """Write the final table in the caller's transaction (tournament already locked and checked by
    ``tournament_completion_error``). No bracket → nothing to rank, nothing written. Idempotent."""
    bracket = get_bracket(db, tournament.tournament_id)
    if bracket is None:
        return 0
    if db.scalar(select(TournamentStanding.team_id)
                 .where(TournamentStanding.tournament_id == tournament.tournament_id).limit(1)) is not None:
        return 0
    status, stats = derive_standings(bracket, bracket_result_rows(db, bracket))
    if status != 'FINAL' or any(s['rank'] is None for s in stats.values()):
        raise HTTPException(409, 'Bracket chưa đầy đủ hoặc chưa có kết quả chung kết hợp lệ')
    order = standing_order(bracket, stats)
    db.add_all(TournamentStanding(tournament_id=tournament.tournament_id, team_id=tid, final_rank=stats[tid]['rank'],
                                  matches_played=stats[tid]['matches_played'], wins=stats[tid]['wins'],
                                  losses=stats[tid]['losses'], points=stats[tid]['wins'], prize_money=0)
               for tid in order)
    record_audit(db, user.user_id, STANDINGS_FINALIZED, 'tournament', {
        'tournament_id': tournament.tournament_id, 'bracket_id': bracket.bracket_id,
        'standings': [{'team_id': tid, 'rank': stats[tid]['rank']} for tid in order],
    })
    return len(order)
