from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from test_catalog_api import session_factory

pytestmark = pytest.mark.postgres


def test_registration_upgrade_downgrade_and_constraints(request, session_factory):
    if not request.config.getoption('--postgres'):
        pytest.skip('migration verification requires PostgreSQL')
    with session_factory() as db:
        connection = db.connection()
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.attributes['connection'] = connection
        config.attributes['version_table_schema'] = connection.scalar(text('SELECT current_schema()'))
        assert inspect(connection).has_table('tournament_registrations')
        # Remove the table to exercise a real W43 -> W44 upgrade, rather than
        # only the fresh-install path where the initial revision creates it.
        command.downgrade(config, '20261021_1200')
        assert not inspect(connection).has_table('tournament_registrations')
        assert inspect(connection).has_table('tournaments')
        command.upgrade(config, 'head')
        inspector = inspect(connection)
        assert inspector.has_table('tournament_registrations')
        assert {'uq_registration_tournament_team'} <= {c['name'] for c in inspector.get_unique_constraints('tournament_registrations')}
        assert {'ck_registration_status', 'ck_registration_timestamps', 'ck_registration_reason'} <= {
            c['name'] for c in inspector.get_check_constraints('tournament_registrations')
        }
        assert {'tournament_id', 'team_id', 'submitted_by', 'reviewed_by', 'cancelled_by'} == {
            fk['constrained_columns'][0] for fk in inspector.get_foreign_keys('tournament_registrations')
        }
        assert connection.scalar(text('SELECT count(*) FROM roles')) == 6
