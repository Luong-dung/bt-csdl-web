"""Identity Module

Revision ID: 53bbc0801b4f
Revises: 
Create Date: 2026-10-05 12:27:00.387887

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53bbc0801b4f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # permissions
    op.create_table('permissions',
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('permission_name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('permission_id'),
    sa.UniqueConstraint('permission_name')
    )
    op.create_index(op.f('ix_permissions_permission_id'), 'permissions', ['permission_id'], unique=False)

    # role_assignments
    op.create_table('role_assignments',
    sa.Column('assignment_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('scope', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['role_id'], ['roles.role_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('assignment_id')
    )
    op.create_index(op.f('ix_role_assignments_assignment_id'), 'role_assignments', ['assignment_id'], unique=False)

    # audit_logs
    op.create_table('audit_logs',
    sa.Column('log_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('resource', sa.String(length=100), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('log_id')
    )
    op.create_index(op.f('ix_audit_logs_log_id'), 'audit_logs', ['log_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_log_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_role_assignments_assignment_id'), table_name='role_assignments')
    op.drop_table('role_assignments')
    op.drop_index(op.f('ix_permissions_permission_id'), table_name='permissions')
    op.drop_table('permissions')
