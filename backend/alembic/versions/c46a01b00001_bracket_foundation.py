"""W46 managed bracket metadata; no legacy match is adopted or rewritten.

Revision ID: c46a01b00001
Revises: b45a01c0ffee
"""
from alembic import op
import sqlalchemy as sa

revision = 'c46a01b00001'
down_revision = 'b45a01c0ffee'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # The initial revision creates live metadata, including these tables on a fresh install.
    if 'uq_matches_bracket_identity' not in {c['name'] for c in inspector.get_unique_constraints('matches')}:
        op.create_unique_constraint('uq_matches_bracket_identity', 'matches', ['match_id', 'tournament_id', 'stage_id'])
    if 'tournament_brackets' not in inspector.get_table_names():
        op.create_table(
            'tournament_brackets',
            sa.Column('bracket_id', sa.Integer, primary_key=True),
            sa.Column('tournament_id', sa.Integer, sa.ForeignKey('tournaments.tournament_id', ondelete='RESTRICT'), nullable=False),
            sa.Column('stage_id', sa.Integer, sa.ForeignKey('stages.stage_id', ondelete='RESTRICT'), nullable=False),
            sa.Column('team_count', sa.Integer, nullable=False),
            sa.Column('round_count', sa.Integer, nullable=False),
            sa.Column('team_order', sa.JSON, nullable=False),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint('tournament_id', name='uq_bracket_tournament'),
            sa.UniqueConstraint('stage_id', name='uq_bracket_stage'),
            sa.UniqueConstraint('bracket_id', 'tournament_id', 'stage_id', 'round_count', name='uq_bracket_identity'),
            sa.CheckConstraint('team_count IN (2,4,8,16,32,64) AND team_count = (1 << round_count) '
                               'AND round_count BETWEEN 1 AND 6', name='ck_bracket_size'),
        )
    if 'bracket_matches' not in inspector.get_table_names():
        op.create_table(
            'bracket_matches',
            sa.Column('match_id', sa.Integer, primary_key=True),
            sa.Column('bracket_id', sa.Integer, nullable=False),
            sa.Column('tournament_id', sa.Integer, nullable=False),
            sa.Column('stage_id', sa.Integer, nullable=False),
            sa.Column('round_count', sa.Integer, nullable=False),
            sa.Column('round_index', sa.Integer, nullable=False),
            sa.Column('position', sa.Integer, nullable=False),
            sa.Column('next_round', sa.Integer), sa.Column('next_position', sa.Integer), sa.Column('next_slot', sa.Integer),
            sa.ForeignKeyConstraint(['match_id', 'tournament_id', 'stage_id'],
                                    ['matches.match_id', 'matches.tournament_id', 'matches.stage_id'],
                                    name='fk_bracket_match_identity', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['bracket_id', 'tournament_id', 'stage_id', 'round_count'],
                                    ['tournament_brackets.bracket_id', 'tournament_brackets.tournament_id',
                                     'tournament_brackets.stage_id', 'tournament_brackets.round_count'],
                                    name='fk_bracket_match_bracket', ondelete='RESTRICT'),
            sa.UniqueConstraint('bracket_id', 'round_index', 'position', name='uq_bracket_match_position'),
            sa.ForeignKeyConstraint(['bracket_id', 'next_round', 'next_position'],
                                    ['bracket_matches.bracket_id', 'bracket_matches.round_index', 'bracket_matches.position'],
                                    name='fk_bracket_match_destination', ondelete='RESTRICT'),
            sa.CheckConstraint('round_count BETWEEN 1 AND 6 AND round_index BETWEEN 1 AND round_count '
                               'AND position BETWEEN 1 AND (1 << (round_count-round_index))', name='ck_bracket_match_position'),
            sa.CheckConstraint('(round_index = round_count AND next_round IS NULL AND next_position IS NULL AND next_slot IS NULL) '
                               'OR (round_index < round_count AND next_round IS NOT NULL AND next_position IS NOT NULL '
                               'AND next_slot IS NOT NULL AND next_round = round_index+1 '
                               'AND next_position = (position+1)/2 AND next_slot = 1+((position-1)%2))',
                               name='ck_bracket_match_destination'),
        )


def downgrade():
    bind = op.get_bind()
    # Metadata is the only proof that a match is managed. Never silently turn live brackets into manual matches.
    if bind.scalar(sa.text('SELECT count(*) FROM tournament_brackets')):
        raise RuntimeError('Bracket downgrade blocked: managed brackets exist; export and resolve explicitly before downgrading')
    op.drop_table('bracket_matches')
    op.drop_table('tournament_brackets')
    op.drop_constraint('uq_matches_bracket_identity', 'matches', type_='unique')
