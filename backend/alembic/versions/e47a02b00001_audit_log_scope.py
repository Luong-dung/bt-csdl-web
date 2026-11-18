"""W47-02 audit_logs tournament_id/resource_id columns and read indexes.

Revision ID: e47a02b00001
Revises: d47a01b00001

Legacy rows are backfilled from their own ``details`` with the same function the writer uses
(``core.audit.derive_ids``); ``details`` itself is never modified. Rows whose details carry no id stay NULL.
"""
from alembic import op
import sqlalchemy as sa

from core.audit import derive_ids

revision = 'e47a02b00001'
down_revision = 'd47a01b00001'
branch_labels = None
depends_on = None

INDEXES = {
    'ix_audit_logs_tournament_log': ['tournament_id', 'log_id'],
    'ix_audit_logs_resource_log': ['resource', 'resource_id', 'log_id'],
    'ix_audit_logs_user_log': ['user_id', 'log_id'],
}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('audit_logs')}
    with op.batch_alter_table('audit_logs') as batch:
        for name in ('tournament_id', 'resource_id'):
            if name not in existing:
                batch.add_column(sa.Column(name, sa.Integer, nullable=True))
    logs = sa.table('audit_logs', sa.column('log_id', sa.Integer), sa.column('resource', sa.String),
                    sa.column('details', sa.JSON), sa.column('tournament_id', sa.Integer),
                    sa.column('resource_id', sa.Integer))
    last = 0
    while True:
        rows = bind.execute(sa.select(logs.c.log_id, logs.c.resource, logs.c.details)
                            .where(logs.c.log_id > last, logs.c.tournament_id.is_(None), logs.c.resource_id.is_(None))
                            .order_by(logs.c.log_id).limit(1000)).all()
        if not rows:
            break
        for log_id, resource, details in rows:
            tournament_id, resource_id = derive_ids(resource, details)
            if tournament_id is not None or resource_id is not None:
                bind.execute(sa.update(logs).where(logs.c.log_id == log_id)
                             .values(tournament_id=tournament_id, resource_id=resource_id))
        last = rows[-1][0]
    present = {i['name'] for i in sa.inspect(bind).get_indexes('audit_logs')}
    for name, columns in INDEXES.items():
        if name not in present:
            op.create_index(name, 'audit_logs', columns)


def downgrade():
    # Both columns are derived from details, so dropping them loses nothing.
    for name in INDEXES:
        op.drop_index(name, table_name='audit_logs')
    with op.batch_alter_table('audit_logs') as batch:
        batch.drop_column('resource_id')
        batch.drop_column('tournament_id')
