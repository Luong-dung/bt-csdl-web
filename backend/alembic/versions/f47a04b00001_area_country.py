"""W47-04 (W03-02): link competition areas to countries.

Revision ID: f47a04b00001
Revises: e47a02b00001

Adds nullable ``competition_areas.country_code`` (FK countries, ON DELETE RESTRICT) with an index.
The identity migration builds tables from the current models, so a fresh database may already have
the column/FK/index; each piece is created only when missing. Existing areas keep NULL;
``seed.py`` fills links only where still NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f47a04b00001'
down_revision = 'e47a02b00001'
branch_labels = None
depends_on = None

FK = 'fk_competition_areas_country'
INDEX = 'ix_competition_areas_country_code'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('competition_areas')}
    foreign_keys = inspector.get_foreign_keys('competition_areas')
    has_fk = any(fk['constrained_columns'] == ['country_code'] for fk in foreign_keys)
    has_index = any(ix['column_names'] == ['country_code'] for ix in inspector.get_indexes('competition_areas'))
    with op.batch_alter_table('competition_areas') as batch:
        if 'country_code' not in columns:
            batch.add_column(sa.Column('country_code', sa.String(2), nullable=True))
        if not has_fk:
            batch.create_foreign_key(FK, 'countries', ['country_code'], ['country_code'], ondelete='RESTRICT')
        if not has_index:
            batch.create_index(INDEX, ['country_code'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    with op.batch_alter_table('competition_areas') as batch:
        for ix in inspector.get_indexes('competition_areas'):
            if ix['column_names'] == ['country_code']:
                batch.drop_index(ix['name'])
        for fk in inspector.get_foreign_keys('competition_areas'):
            if fk['constrained_columns'] == ['country_code']:
                batch.drop_constraint(fk['name'], type_='foreignkey')
        batch.drop_column('country_code')
