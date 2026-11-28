"""W48-04: role_permissions join table and default global permissions.

Revision ID: g48a04b00001
Revises: f47a04b00001

The identity migration builds tables from the current models, so a fresh database may already have
``role_permissions``; it is created only when missing. Default permissions/grants are written here
only when the roles they target already exist (an upgraded database). On a fresh database the roles
do not exist yet and ``seed.py`` writes permissions together with their grants. The data below is a
frozen copy of ``core.permissions`` at this revision.
"""
from alembic import op
import sqlalchemy as sa

revision = 'g48a04b00001'
down_revision = 'f47a04b00001'
branch_labels = None
depends_on = None

INDEX = 'ix_role_permissions_permission_id'
PERMISSIONS = (
    ('CATALOG_MANAGE', 'Tạo/sửa/xóa publisher, game, khu vực và quốc gia'),
    ('ORGANIZATION_CREATE', 'Tạo tổ chức mới'),
    ('TOURNAMENT_CREATE', 'Tạo giải đấu mới'),
    ('AUDIT_LOG_VIEW_ALL', 'Xem nhật ký audit toàn hệ thống'),
    ('ROLE_ASSIGNMENT_MANAGE', 'Cấp/thu hồi vai trò theo phạm vi cho mọi người dùng'),
)
ROLE_PERMISSIONS = {
    'ADMIN': ('CATALOG_MANAGE', 'ORGANIZATION_CREATE', 'TOURNAMENT_CREATE', 'AUDIT_LOG_VIEW_ALL', 'ROLE_ASSIGNMENT_MANAGE'),
    'ORGANIZER': ('TOURNAMENT_CREATE',),
}


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('role_permissions'):
        op.create_table(
            'role_permissions',
            sa.Column('role_id', sa.Integer, sa.ForeignKey('roles.role_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('permission_id', sa.Integer, sa.ForeignKey('permissions.permission_id', ondelete='CASCADE'),
                      primary_key=True),
        )
    if not any(ix['name'] == INDEX for ix in sa.inspect(bind).get_indexes('role_permissions')):
        op.create_index(INDEX, 'role_permissions', ['permission_id'])

    role_ids = dict(bind.execute(sa.text('SELECT role_name, role_id FROM roles')).all())
    if not set(ROLE_PERMISSIONS) <= set(role_ids):
        return
    for name, description in PERMISSIONS:
        if bind.scalar(sa.text('SELECT 1 FROM permissions WHERE permission_name = :n'), {'n': name}):
            continue  # Existing permission: its grants are someone's decision, leave them.
        bind.execute(sa.text('INSERT INTO permissions (permission_name, description) VALUES (:n, :d)'),
                     {'n': name, 'd': description})
        permission_id = bind.scalar(sa.text('SELECT permission_id FROM permissions WHERE permission_name = :n'),
                                    {'n': name})
        for role_name, granted in ROLE_PERMISSIONS.items():
            if name in granted:
                bind.execute(sa.text('INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)'),
                             {'r': role_ids[role_name], 'p': permission_id})


def downgrade():
    op.drop_table('role_permissions')
    bind = op.get_bind()
    bind.execute(sa.text('DELETE FROM permissions WHERE permission_name IN :names').bindparams(
        sa.bindparam('names', expanding=True)), {'names': [name for name, _ in PERMISSIONS]})
