from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_permissions import access
from test_roster_foundation import accepted

pytestmark = pytest.mark.postgres


def migration_config(connection):
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.attributes['connection'] = connection
    config.attributes['version_table_schema'] = connection.scalar(text('SELECT current_schema()'))
    return config


def test_roster_upgrade_downgrade_preserves_legacy_data(request, session_factory, access, accepted):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    _, _, users, teams, _ = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        # Fixture first upgraded a fresh install, whose initial revision uses live metadata.
        assert 'roster_locked_at' in {c['name'] for c in inspect(connection).get_columns('tournaments')}
        command.downgrade(config, '1d9de90694b3')
        inspector = inspect(connection)
        assert 'display_name' not in {c['name'] for c in inspector.get_columns('tournament_rosters')}
        assert 'roster_locked_at' not in {c['name'] for c in inspector.get_columns('tournaments')}
        connection.execute(text('INSERT INTO tournament_rosters (tournament_id, team_id, user_id, role_in_team) '
                                "VALUES (:tid, :team, :user, 'PLAYER')"),
                           {'tid': accepted, 'team': teams['Alpha'], 'user': users['viewer']})
        connection.execute(text("UPDATE tournaments SET status='ONGOING' WHERE tournament_id=:id"), {'id': accepted})
        command.upgrade(config, 'head')
        inspector = inspect(connection)
        assert 'uq_rosters_tournament_user' in {c['name'] for c in inspector.get_unique_constraints('tournament_rosters')}
        assert 'ix_rosters_tournament_team' in {i['name'] for i in inspector.get_indexes('tournament_rosters')}
        assert {'ck_rosters_role', 'ck_rosters_display_name'} <= {c['name'] for c in inspector.get_check_constraints('tournament_rosters')}
        foreign = {fk['constrained_columns'][0]: fk for fk in inspector.get_foreign_keys('tournament_rosters')}
        assert foreign['user_id']['options']['ondelete'] == 'RESTRICT'
        assert foreign['team_id']['options']['ondelete'] == 'RESTRICT'
        assert foreign['tournament_id']['options']['ondelete'] == 'CASCADE'
        row = connection.execute(text('SELECT user_id, display_name FROM tournament_rosters')).one()
        assert row == (users['viewer'], None)
        assert connection.execute(text('SELECT roster_locked_at, roster_locked_by FROM tournaments WHERE tournament_id=:id'),
                                  {'id': accepted}).one() == (None, None)
        # Round trip keeps rows; no fictitious locked historical roster is created.
        command.downgrade(config, '1d9de90694b3')
        command.upgrade(config, 'head')
        assert connection.scalar(text('SELECT count(*) FROM tournament_rosters')) == 1


@pytest.mark.parametrize('bad_data', ['duplicate', 'role'])
def test_invalid_legacy_rosters_fail_before_any_schema_change(request, session_factory, access, accepted, bad_data):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    _, _, users, teams, _ = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, '1d9de90694b3')
        values = {'tid': accepted, 'team': teams['Alpha'], 'user': users['viewer'],
                  'role': 'MANAGER' if bad_data == 'role' else 'PLAYER'}
        for _ in range(2 if bad_data == 'duplicate' else 1):
            connection.execute(text('INSERT INTO tournament_rosters (tournament_id, team_id, user_id, role_in_team) '
                                    'VALUES (:tid, :team, :user, :role)'), values)
        with pytest.raises(RuntimeError, match='reconcile duplicate users or unsupported roster roles'):
            command.upgrade(config, 'head')
        assert 'roster_locked_at' not in {c['name'] for c in inspect(connection).get_columns('tournaments')}
        assert connection.scalar(text('SELECT count(*) FROM tournament_rosters')) == (2 if bad_data == 'duplicate' else 1)
