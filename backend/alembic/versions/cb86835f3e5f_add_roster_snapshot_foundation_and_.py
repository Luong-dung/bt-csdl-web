"""Add roster snapshot foundation and tournament lock state

Revision ID: cb86835f3e5f
Revises: 1d9de90694b3
Create Date: 2026-10-26 21:23:45.040668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb86835f3e5f'
down_revision: Union[str, Sequence[str], None] = '1d9de90694b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Never silently discard legacy duplicates or manufacture locked snapshots.
    duplicate = bind.execute(sa.text('SELECT tournament_id, user_id FROM tournament_rosters '
                                    'GROUP BY tournament_id, user_id HAVING count(*) > 1 LIMIT 1')).first()
    invalid = bind.execute(sa.text("SELECT roster_id FROM tournament_rosters "
                                  "WHERE role_in_team NOT IN ('PLAYER', 'SUBSTITUTE') LIMIT 1")).first()
    if duplicate or invalid:
        raise RuntimeError('Roster migration blocked: reconcile duplicate users or unsupported roster roles before retrying')

    columns = {c['name'] for c in sa.inspect(bind).get_columns('tournaments')}
    if 'roster_locked_at' not in columns:
        op.add_column('tournaments', sa.Column('roster_locked_at', sa.DateTime(timezone=True), nullable=True))
    if 'roster_locked_by' not in columns:
        op.add_column('tournaments', sa.Column('roster_locked_by', sa.Integer(), nullable=True))
    replace_fk('tournaments', 'roster_locked_by', 'users', 'user_id',
               'fk_tournaments_roster_locked_by', 'SET NULL')
    replace_check('tournaments', 'ck_tournaments_roster_lock',
                  'roster_locked_at IS NOT NULL OR roster_locked_by IS NULL')

    if 'display_name' not in {c['name'] for c in sa.inspect(bind).get_columns('tournament_rosters')}:
        op.add_column('tournament_rosters', sa.Column('display_name', sa.String(100), nullable=True))
    # NULL explicitly means no display snapshot was captured. Existing historical
    # rows are preserved as-is; the W44-2-04 writer fills names when it locks.
    replace_fk('tournament_rosters', 'team_id', 'teams', 'team_id', 'fk_rosters_team', 'RESTRICT')
    replace_fk('tournament_rosters', 'user_id', 'users', 'user_id', 'fk_rosters_user', 'RESTRICT')
    uniques = sa.inspect(bind).get_unique_constraints('tournament_rosters')
    for constraint in uniques:
        if set(constraint['column_names']) == {'tournament_id', 'user_id'}:
            op.drop_constraint(constraint['name'], 'tournament_rosters', type_='unique')
    op.create_unique_constraint('uq_rosters_tournament_user', 'tournament_rosters', ['tournament_id', 'user_id'])
    replace_check('tournament_rosters', 'ck_rosters_role', "role_in_team IN ('PLAYER', 'SUBSTITUTE')")
    replace_check('tournament_rosters', 'ck_rosters_display_name',
                  'display_name IS NULL OR length(trim(display_name)) > 0')
    if 'ix_rosters_tournament_team' not in {i['name'] for i in sa.inspect(bind).get_indexes('tournament_rosters')}:
        op.create_index('ix_rosters_tournament_team', 'tournament_rosters', ['tournament_id', 'team_id'])


def downgrade() -> None:
    op.drop_index('ix_rosters_tournament_team', table_name='tournament_rosters')
    for name in ('uq_rosters_tournament_user', 'ck_rosters_role', 'ck_rosters_display_name'):
        op.drop_constraint(name, 'tournament_rosters')
    replace_fk('tournament_rosters', 'team_id', 'teams', 'team_id', 'fk_rosters_team', 'CASCADE')
    replace_fk('tournament_rosters', 'user_id', 'users', 'user_id', 'fk_rosters_user', 'CASCADE')
    op.drop_column('tournament_rosters', 'display_name')
    op.drop_constraint('ck_tournaments_roster_lock', 'tournaments', type_='check')
    op.drop_constraint('fk_tournaments_roster_locked_by', 'tournaments', type_='foreignkey')
    op.drop_column('tournaments', 'roster_locked_by')
    op.drop_column('tournaments', 'roster_locked_at')


def replace_fk(table, column, target, target_column, name, ondelete):
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(table):
        if fk['constrained_columns'] == [column]:
            op.drop_constraint(fk['name'], table, type_='foreignkey')
    op.create_foreign_key(name, table, target, [column], [target_column], ondelete=ondelete)


def replace_check(table, name, expression):
    if name in {c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}:
        op.drop_constraint(name, table, type_='check')
    op.create_check_constraint(name, table, expression)
