"""W47-01 role assignment grant/revoke history and one ACTIVE assignment per user/role/scope.

Revision ID: d47a01b00001
Revises: c46a01b00001
"""
from alembic import op
import sqlalchemy as sa

revision = 'd47a01b00001'
down_revision = 'c46a01b00001'
branch_labels = None
depends_on = None

INDEX = 'uq_role_assignments_active'
COLUMNS = ('granted_by', 'granted_at', 'revoked_by', 'revoked_at')


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # The initial revision builds live metadata, so a fresh install already has these.
    existing = {c['name'] for c in inspector.get_columns('role_assignments')}
    with op.batch_alter_table('role_assignments') as batch:
        for name in ('granted_by', 'revoked_by'):
            if name not in existing:
                batch.add_column(sa.Column(name, sa.Integer, sa.ForeignKey(
                    'users.user_id', name=f'fk_role_assignments_{name}', ondelete='SET NULL'), nullable=True))
        for name in ('granted_at', 'revoked_at'):
            if name not in existing:
                batch.add_column(sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    if INDEX in {i['name'] for i in sa.inspect(bind).get_indexes('role_assignments')}:
        return
    # Never merge or delete legacy duplicates silently: stop and let the team resolve them explicitly.
    duplicates = bind.execute(sa.text(
        'SELECT user_id, role_id, scope_type, scope_id, count(*) FROM role_assignments '
        'WHERE revoked_at IS NULL GROUP BY user_id, role_id, scope_type, scope_id HAVING count(*) > 1')).all()
    if duplicates:
        raise RuntimeError(f'W47-01 upgrade blocked: duplicate active role assignments {duplicates[:10]}; '
                           'revoke or remove them explicitly before upgrading')
    op.create_index(INDEX, 'role_assignments',
                    ['user_id', 'role_id', 'scope_type', sa.text('coalesce(scope_id, 0)')], unique=True,
                    postgresql_where=sa.text('revoked_at IS NULL'), sqlite_where=sa.text('revoked_at IS NULL'))


def downgrade():
    bind = op.get_bind()
    # Dropping revoked_at would silently re-activate every revoked assignment.
    if bind.scalar(sa.text('SELECT count(*) FROM role_assignments WHERE revoked_at IS NOT NULL')):
        raise RuntimeError('W47-01 downgrade blocked: revoked assignments exist and would become active again')
    op.drop_index(INDEX, table_name='role_assignments')
    with op.batch_alter_table('role_assignments') as batch:
        for name in ('granted_by', 'revoked_by'):
            batch.drop_constraint(f'fk_role_assignments_{name}', type_='foreignkey')
        for name in COLUMNS:
            batch.drop_column(name)
