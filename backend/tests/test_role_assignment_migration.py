"""W47-01 migration keeps legacy assignments active, refuses duplicates and never re-activates revoked grants."""
import pytest
from alembic import command
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_permissions import access
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = 'c46a01b00001'
HEAD = 'd47a01b00001'
NEW_COLUMNS = {'granted_by', 'granted_at', 'revoked_by', 'revoked_at'}


def columns(connection):
    return {c['name'] for c in inspect(connection).get_columns('role_assignments')}


def insert(connection, users, roles, user='referee', scope=7):
    connection.execute(text('INSERT INTO role_assignments (user_id, role_id, scope_type, scope_id) '
                            "VALUES (:u, :r, 'TOURNAMENT', :s)"), {'u': users[user], 'r': roles['REFEREE'], 's': scope})


def test_upgrade_keeps_legacy_rows_active_without_inventing_history(request, session_factory, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, roles = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        assert not NEW_COLUMNS & columns(connection)
        insert(connection, users, roles)
        before = connection.execute(text('SELECT assignment_id, user_id, role_id, scope_type, scope_id '
                                         'FROM role_assignments ORDER BY assignment_id')).all()
        command.upgrade(config, 'head')
        assert NEW_COLUMNS <= columns(connection)
        assert connection.execute(text('SELECT assignment_id, user_id, role_id, scope_type, scope_id '
                                       'FROM role_assignments ORDER BY assignment_id')).all() == before
        assert connection.scalar(text('SELECT count(*) FROM role_assignments WHERE granted_at IS NOT NULL '
                                      'OR revoked_at IS NOT NULL')) == 0
        command.downgrade(config, PREVIOUS)
        command.upgrade(config, 'head')


def test_upgrade_with_duplicate_active_assignments_stops(request, session_factory, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, roles = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        insert(connection, users, roles)
        insert(connection, users, roles)
        with pytest.raises(RuntimeError, match='duplicate active role assignments'):
            command.upgrade(config, 'head')
        # Nothing was merged or deleted.
        assert connection.scalar(text('SELECT count(*) FROM role_assignments WHERE scope_id = 7')) == 2


def test_downgrade_with_revoked_assignment_stops(request, session_factory, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, roles = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        insert(connection, users, roles)
        connection.execute(text('UPDATE role_assignments SET revoked_at = now()'))
        with pytest.raises(RuntimeError, match='W47-01 downgrade blocked'):
            command.downgrade(config, PREVIOUS)
        assert NEW_COLUMNS <= columns(connection)
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == HEAD


def test_upgrade_drops_legacy_full_unique_from_sql_schema(request, session_factory, access):
    """database/schema_postgres.sql installs had UNIQUE(user_id, role_id, scope_type, scope_id)."""
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, roles = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        connection.execute(text('ALTER TABLE role_assignments ADD CONSTRAINT legacy_ra_unique '
                                'UNIQUE (user_id, role_id, scope_type, scope_id)'))
        command.upgrade(config, 'head')
        assert 'legacy_ra_unique' not in {c['name'] for c in inspect(connection).get_unique_constraints('role_assignments')}
        # Revoke then grant again must be possible: history row + new active row.
        insert(connection, users, roles)
        connection.execute(text('UPDATE role_assignments SET revoked_at = now()'))
        insert(connection, users, roles)
        assert connection.scalar(text('SELECT count(*) FROM role_assignments WHERE scope_id = 7')) == 2
