"""W45-01 match foundation: schedule column, lifecycle/result constraints, indexes

Revision ID: b45a01c0ffee
Revises: 7a1b2c3d4e5f
Create Date: 2026-11-04 10:00:00

Legacy rows are never rewritten here. If any existing match violates a new
constraint, the upgrade stops before any DDL and names the offending IDs.
Downgrade keeps every match row; only the W45 ``scheduled_at`` values are dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b45a01c0ffee'
down_revision: Union[str, Sequence[str], None] = '7a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECKS = (
    ('ck_matches_status', "status IN ('PENDING', 'ONGOING', 'COMPLETED', 'CANCELLED')"),
    ('ck_matches_round', 'round_no > 0'),
    ('ck_matches_scores', 'score_team1 >= 0 AND score_team2 >= 0'),
    ('ck_matches_distinct_teams', 'team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id'),
    ('ck_matches_winner_team', 'winner_id IS NULL OR winner_id = team1_id OR winner_id = team2_id'),
    ('ck_matches_result', "(status = 'COMPLETED' AND winner_id IS NOT NULL) OR "
                          "(status <> 'COMPLETED' AND winner_id IS NULL)"),
)
INDEXES = (
    ('ix_matches_tournament_stage', ['tournament_id', 'stage_id', 'round_no', 'match_id']),
    ('ix_matches_team1', ['team1_id']),
    ('ix_matches_team2', ['team2_id']),
)
# Each query returns the IDs of legacy matches that the new schema would reject.
LEGACY_RULES = (
    ('stage of another tournament', 'SELECT m.match_id FROM matches m JOIN stages s ON s.stage_id = m.stage_id '
                                    'WHERE s.tournament_id <> m.tournament_id'),
    *((name, f'SELECT match_id FROM matches WHERE NOT ({expression})') for name, expression in CHECKS),
)


def legacy_violations(bind) -> list[str]:
    problems = []
    for name, query in LEGACY_RULES:
        ids = list(bind.execute(sa.text(query + ' ORDER BY 1 LIMIT 20')).scalars())
        if ids:
            problems.append(f'{name}: match_id {ids}')
    return problems


def upgrade() -> None:
    bind = op.get_bind()
    problems = legacy_violations(bind)
    if problems:
        raise RuntimeError('Match migration blocked, fix legacy matches before retrying: ' + '; '.join(problems))
    # The initial revision builds live metadata, so a fresh install may already have these objects.
    inspector = sa.inspect(bind)
    if 'scheduled_at' not in {c['name'] for c in inspector.get_columns('matches')}:
        op.add_column('matches', sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
    drop_foundation(inspector, keep_column=True)
    op.create_unique_constraint('uq_stages_id_tournament', 'stages', ['stage_id', 'tournament_id'])
    op.create_foreign_key('fk_matches_stage_tournament', 'matches', 'stages',
                          ['stage_id', 'tournament_id'], ['stage_id', 'tournament_id'], ondelete='RESTRICT')
    for name, expression in CHECKS:
        op.create_check_constraint(name, 'matches', expression)
    for name, columns in INDEXES:
        op.create_index(name, 'matches', columns)


def downgrade() -> None:
    drop_foundation(sa.inspect(op.get_bind()), keep_column=False)


def drop_foundation(inspector, keep_column: bool) -> None:
    indexes = {i['name'] for i in inspector.get_indexes('matches')}
    for name, _ in INDEXES:
        if name in indexes:
            op.drop_index(name, table_name='matches')
    checks = {c['name'] for c in inspector.get_check_constraints('matches')}
    for name, _ in CHECKS:
        if name in checks:
            op.drop_constraint(name, 'matches', type_='check')
    if 'fk_matches_stage_tournament' in {f['name'] for f in inspector.get_foreign_keys('matches')}:
        op.drop_constraint('fk_matches_stage_tournament', 'matches', type_='foreignkey')
    if 'uq_stages_id_tournament' in {u['name'] for u in inspector.get_unique_constraints('stages')}:
        op.drop_constraint('uq_stages_id_tournament', 'stages', type_='unique')
    if not keep_column and 'scheduled_at' in {c['name'] for c in inspector.get_columns('matches')}:
        op.drop_column('matches', 'scheduled_at')
