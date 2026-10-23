"""Add tournament registration foundation for decisions

Revision ID: 1d9de90694b3
Revises: 20261021_1200
Create Date: 2026-10-23 16:27:53.041615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d9de90694b3'
down_revision: Union[str, Sequence[str], None] = '20261021_1200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECKS = {
    'ck_registration_status': "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
    'ck_registration_timestamps': (
        "(status = 'PENDING' AND reviewed_at IS NULL AND cancelled_at IS NULL) OR "
        "(status IN ('APPROVED', 'REJECTED') AND reviewed_at IS NOT NULL AND cancelled_at IS NULL) OR "
        "(status = 'CANCELLED' AND cancelled_at IS NOT NULL)"
    ),
    'ck_registration_reason': "status IN ('REJECTED', 'CANCELLED') OR rejection_reason IS NULL",
}


def ensure_registration_constraints() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('tournament_registrations')}
    required = {'registration_id', 'tournament_id', 'team_id', 'status', 'submitted_by', 'submitted_at',
                'reviewed_by', 'reviewed_at', 'rejection_reason', 'cancelled_by', 'cancelled_at'}
    if not required <= columns:
        raise RuntimeError('Existing tournament_registrations table is missing required columns')
    uniques = {constraint['name'] for constraint in inspector.get_unique_constraints('tournament_registrations')}
    if 'uq_registration_tournament_team' not in uniques:
        op.create_unique_constraint('uq_registration_tournament_team', 'tournament_registrations', ['tournament_id', 'team_id'])
    checks = {constraint['name'] for constraint in inspector.get_check_constraints('tournament_registrations')}
    for name, expression in CHECKS.items():
        # Also reconcile an earlier create_all table carrying the old CHECK text.
        if name in checks:
            op.drop_constraint(name, 'tournament_registrations', type_='check')
        op.create_check_constraint(name, 'tournament_registrations', expression)
    indexes = {index['name'] for index in inspector.get_indexes('tournament_registrations')}
    if 'ix_tournament_registrations_team_id' not in indexes:
        op.create_index('ix_tournament_registrations_team_id', 'tournament_registrations', ['team_id'])


def upgrade() -> None:
    # The initial revision calls current Base.metadata.create_all. A fresh install
    # can therefore already contain this table; an existing W43 DB will not.
    if sa.inspect(op.get_bind()).has_table('tournament_registrations'):
        ensure_registration_constraints()
        return
    op.create_table(
        'tournament_registrations',
        sa.Column('registration_id', sa.Integer(), primary_key=True),
        sa.Column('tournament_id', sa.Integer(), sa.ForeignKey('tournaments.tournament_id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.team_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(20), server_default='PENDING', nullable=False),
        sa.Column('submitted_by', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(500), nullable=True),
        sa.Column('cancelled_by', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('tournament_id', 'team_id', name='uq_registration_tournament_team'),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')", name='ck_registration_status'),
        sa.CheckConstraint(
            "(status = 'PENDING' AND reviewed_at IS NULL AND cancelled_at IS NULL) OR "
            "(status IN ('APPROVED', 'REJECTED') AND reviewed_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL)",
            name='ck_registration_timestamps',
        ),
        sa.CheckConstraint(CHECKS['ck_registration_reason'], name='ck_registration_reason'),
    )
    op.create_index('ix_tournament_registrations_team_id', 'tournament_registrations', ['team_id'])


def downgrade() -> None:
    op.drop_table('tournament_registrations')
