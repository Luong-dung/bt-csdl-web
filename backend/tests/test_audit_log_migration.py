"""W47-02 migration backfills scope columns from details and never rewrites details."""
import json

import pytest
from alembic import command
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_permissions import access
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = 'd47a01b00001'
INDEXES = {'ix_audit_logs_tournament_log', 'ix_audit_logs_resource_log', 'ix_audit_logs_user_log'}


def test_upgrade_backfills_from_details_and_downgrade_is_lossless(request, session_factory, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, _ = access
    legacy = [
        ('MATCH_STARTED', 'match', {'tournament_id': 5, 'match_id': 11, 'before': {}, 'after': {}}),
        ('ROLE_ASSIGNMENT_GRANTED', 'role_assignment', {'tournament_id': None, 'after': {'assignment_id': 3}}),
        ('TEAM_MEMBER_ADDED', 'team_membership', {'team_id': 1, 'membership_id': 9}),
        ('ODD', 'something', {'note': 'no ids'}),
    ]
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        assert not {'tournament_id', 'resource_id'} & {c['name'] for c in inspect(connection).get_columns('audit_logs')}
        for action, resource, details in legacy:
            connection.execute(text('INSERT INTO audit_logs (user_id, action, resource, details) '
                                    'VALUES (:u, :a, :r, CAST(:d AS JSONB))'),
                               {'u': users['admin'], 'a': action, 'r': resource, 'd': json.dumps(details)})
        before = connection.execute(text('SELECT log_id, action, resource, details FROM audit_logs ORDER BY log_id')).all()
        command.upgrade(config, 'head')
        assert INDEXES <= {i['name'] for i in inspect(connection).get_indexes('audit_logs')}
        rows = connection.execute(text('SELECT action, tournament_id, resource_id FROM audit_logs ORDER BY log_id')).all()
        assert [tuple(r) for r in rows] == [('MATCH_STARTED', 5, 11), ('ROLE_ASSIGNMENT_GRANTED', None, 3),
                                            ('TEAM_MEMBER_ADDED', None, 9), ('ODD', None, None)]
        assert connection.execute(text('SELECT log_id, action, resource, details FROM audit_logs '
                                       'ORDER BY log_id')).all() == before
        command.downgrade(config, PREVIOUS)
        assert connection.execute(text('SELECT log_id, action, resource, details FROM audit_logs '
                                       'ORDER BY log_id')).all() == before
        command.upgrade(config, 'head')
