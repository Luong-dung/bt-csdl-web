"""W47-04 migration: competition_areas.country_code FK/index; areas survive downgrade/upgrade."""
import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from test_catalog_api import session_factory
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = 'e47a02b00001'


def test_area_country_upgrade_downgrade(request, session_factory):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        assert 'country_code' not in {c['name'] for c in inspect(connection).get_columns('competition_areas')}
        areas = connection.execute(text('SELECT area_id, code, parent_id FROM competition_areas ORDER BY area_id')).all()
        command.upgrade(config, 'head')
        inspector = inspect(connection)
        assert 'country_code' in {c['name'] for c in inspector.get_columns('competition_areas')}
        [fk] = [fk for fk in inspector.get_foreign_keys('competition_areas') if fk['constrained_columns'] == ['country_code']]
        assert (fk['referred_table'], fk['options'].get('ondelete')) == ('countries', 'RESTRICT')
        assert any(ix['column_names'] == ['country_code'] for ix in inspector.get_indexes('competition_areas'))
        assert connection.execute(text('SELECT area_id, code, parent_id FROM competition_areas '
                                       'ORDER BY area_id')).all() == areas
        assert connection.scalar(text('SELECT count(*) FROM competition_areas WHERE country_code IS NOT NULL')) == 0
        # The FK rejects unknown countries and protects a country in use.
        connection.execute(text("INSERT INTO countries (country_code, name) VALUES ('ZZ', 'Test land')"))
        connection.execute(text("UPDATE competition_areas SET country_code = 'ZZ' WHERE code = 'VN'"))
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(text("DELETE FROM countries WHERE country_code = 'ZZ'"))
        savepoint.rollback()
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE competition_areas SET country_code = 'QQ' WHERE code = 'VN'"))
        savepoint.rollback()
        command.downgrade(config, PREVIOUS)
        command.upgrade(config, 'head')
