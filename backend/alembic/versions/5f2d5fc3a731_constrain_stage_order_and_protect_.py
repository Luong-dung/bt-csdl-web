"""Constrain stage order and protect stages with matches

Revision ID: 5f2d5fc3a731
Revises: cb86835f3e5f
Create Date: 2026-10-27 11:05:42.522531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f2d5fc3a731'
down_revision: Union[str, Sequence[str], None] = 'cb86835f3e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(sa.text('SELECT tournament_id, sequence_order FROM stages '
                                    'GROUP BY tournament_id, sequence_order HAVING count(*) > 1 LIMIT 1')).first()
    invalid = bind.execute(sa.text('SELECT stage_id FROM stages WHERE sequence_order <= 0 '
                                  'OR length(trim(name)) NOT BETWEEN 1 AND 80 LIMIT 1')).first()
    if duplicate or invalid:
        raise RuntimeError('Stage migration blocked: reconcile duplicate/non-positive orders or blank names before retrying')
    # Initial revision uses live metadata, so a fresh install can already have these.
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints('stages'):
        if set(constraint['column_names']) == {'tournament_id', 'sequence_order'}:
            op.drop_constraint(constraint['name'], 'stages', type_='unique')
    op.create_unique_constraint('uq_stages_tournament_order', 'stages', ['tournament_id', 'sequence_order'])
    checks = {c['name'] for c in inspector.get_check_constraints('stages')}
    for name, expression in (
        ('ck_stages_positive_order', 'sequence_order > 0'),
        ('ck_stages_name', 'length(trim(name)) BETWEEN 1 AND 80'),
    ):
        if name in checks:
            op.drop_constraint(name, 'stages', type_='check')
        op.create_check_constraint(name, 'stages', expression)
    replace_match_fk('RESTRICT')


def downgrade() -> None:
    replace_match_fk('CASCADE')
    op.drop_constraint('uq_stages_tournament_order', 'stages', type_='unique')
    op.drop_constraint('ck_stages_positive_order', 'stages', type_='check')
    op.drop_constraint('ck_stages_name', 'stages', type_='check')


def replace_match_fk(ondelete):
    for fk in sa.inspect(op.get_bind()).get_foreign_keys('matches'):
        if fk['constrained_columns'] == ['stage_id']:
            op.drop_constraint(fk['name'], 'matches', type_='foreignkey')
    op.create_foreign_key('fk_matches_stage', 'matches', 'stages', ['stage_id'], ['stage_id'], ondelete=ondelete)
