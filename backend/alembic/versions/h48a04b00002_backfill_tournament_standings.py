"""W48-04 (b): backfill tournament_standings for tournaments COMPLETED before W48-04.

Revision ID: h48a04b00002
Revises: g48a04b00001

From W48-04 the final table is written when a tournament becomes COMPLETED. Tournaments that were
already COMPLETED with a managed bracket get the same table here, derived from their (frozen)
results. Tournaments that already have rows, have no bracket, or whose bracket is not fully
decided are skipped; the API keeps deriving for those. The ranking below is a frozen copy of
``core.standings.derive_standings`` at this revision. No audit row: this is not a user action.

Downgrade keeps the rows: the previous revision ignores the table, and app-written rows cannot be
told apart from backfilled ones.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = 'h48a04b00002'
down_revision = 'g48a04b00001'
branch_labels = None
depends_on = None


def final_table(team_order: list[int], round_count: int, rows) -> list[dict] | None:
    """Ranked rows for a fully decided bracket, else None (never guess)."""
    stats = {tid: {'rank': None, 'matches_played': 0, 'wins': 0, 'losses': 0} for tid in team_order}
    final_winner = None
    for round_index, status, team1_id, team2_id, winner_id in rows:
        if status != 'COMPLETED' or winner_id not in (team1_id, team2_id):
            return None
        loser = team2_id if winner_id == team1_id else team1_id
        if winner_id not in stats or loser not in stats:
            return None
        for tid in (winner_id, loser):
            stats[tid]['matches_played'] += 1
        stats[winner_id]['wins'] += 1
        stats[loser]['losses'] += 1
        stats[loser]['rank'] = (1 << (round_count-round_index))+1
        if round_index == round_count:
            final_winner = winner_id
    if final_winner is None:
        return None
    stats[final_winner]['rank'] = 1
    if any(s['rank'] is None for s in stats.values()):
        return None
    return [{'team_id': tid, **s} for tid, s in stats.items()]


def upgrade():
    bind = op.get_bind()
    brackets = bind.execute(sa.text(
        "SELECT b.bracket_id, b.tournament_id, b.round_count, b.team_count, b.team_order "
        "FROM tournament_brackets b JOIN tournaments t ON t.tournament_id = b.tournament_id "
        "WHERE t.status = 'COMPLETED' AND NOT EXISTS "
        "(SELECT 1 FROM tournament_standings s WHERE s.tournament_id = b.tournament_id) "
        "ORDER BY b.tournament_id")).all()
    insert = sa.text(
        "INSERT INTO tournament_standings (tournament_id, team_id, final_rank, matches_played, wins, losses, "
        "points, prize_money) VALUES (:tournament_id, :team_id, :rank, :matches_played, :wins, :losses, :wins, 0)")
    for bracket_id, tournament_id, round_count, team_count, team_order in brackets:
        order = json.loads(team_order) if isinstance(team_order, str) else list(team_order)
        rows = bind.execute(sa.text(
            "SELECT bm.round_index, m.status, m.team1_id, m.team2_id, m.winner_id "
            "FROM bracket_matches bm JOIN matches m ON m.match_id = bm.match_id "
            "WHERE bm.bracket_id = :bracket_id"), {'bracket_id': bracket_id}).all()
        table = final_table(order, round_count, rows) if len(rows) == team_count-1 else None
        if table:
            bind.execute(insert, [{'tournament_id': tournament_id, **row} for row in table])


def downgrade():
    pass
