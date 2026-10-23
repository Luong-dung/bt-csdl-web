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


def upgrade() -> None:
    # The initial revision calls current Base.metadata.create_all. A fresh install
    # can therefore already contain this table; an existing W43 DB will not.
    if sa.inspect(op.get_bind()).has_table('tournament_registrations'):
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
            "(status = 'CANCELLED' AND reviewed_at IS NULL AND cancelled_at IS NOT NULL)",
            name='ck_registration_timestamps',
        ),
        sa.CheckConstraint("status = 'REJECTED' OR rejection_reason IS NULL", name='ck_registration_reason'),
    )


def downgrade() -> None:
    op.drop_table('tournament_registrations')
