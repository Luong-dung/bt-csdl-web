"""W45-01 migration b45a01c0ffee: upgrade from W44(2), downgrade keeps rows, stops on bad legacy data."""

import pytest
from alembic import command
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = '7a1b2c3d4e5f'
CHECKS = {'ck_matches_status', 'ck_matches_round', 'ck_matches_scores', 'ck_matches_distinct_teams',
          'ck_matches_winner_team', 'ck_matches_result'}


def schema(connection):
    inspector = inspect(connection)
    return ({c['name'] for c in inspector.get_columns('matches')},
            {c['name'] for c in inspector.get_check_constraints('matches')},
            {f['name'] for f in inspector.get_foreign_keys('matches')},
            {i['name'] for i in inspector.get_indexes('matches')})


def test_match_upgrade_downgrade_preserves_rows(request, session_factory, match_case):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        columns, checks, fks, indexes = schema(connection)
        assert 'scheduled_at' in columns and CHECKS <= checks and 'fk_matches_stage_tournament' in fks
        command.downgrade(config, PREVIOUS)
        columns, checks, fks, indexes = schema(connection)
        assert 'scheduled_at' not in columns and not CHECKS & checks
        assert 'fk_matches_stage_tournament' not in fks and 'ix_matches_team1' not in indexes
        assert 'fk_matches_stage' in fks  # W44(2) RESTRICT FK untouched
        command.upgrade(config, 'head')
        columns, checks, fks, indexes = schema(connection)
        assert 'scheduled_at' in columns and CHECKS <= checks
        assert {'ix_matches_tournament_stage', 'ix_matches_team1', 'ix_matches_team2'} <= indexes
        assert connection.scalar(text('SELECT count(*) FROM matches')) == 1
        assert connection.scalar(text('SELECT status FROM matches WHERE match_id=:m'),
                                 {'m': match_case['match']}) == 'PENDING'


@pytest.mark.parametrize('legacy', [
    "UPDATE matches SET status='FINISHED'",
    'UPDATE matches SET round_no=0',
    'UPDATE matches SET score_team1=-1',
    "UPDATE matches SET status='COMPLETED'",              # completed without winner
    'UPDATE matches SET winner_id=team1_id',               # winner on a pending match
    'UPDATE matches SET stage_id=:other_stage',            # stage of another tournament
    'UPDATE matches SET team2_id=team1_id',                # ck_matches_distinct_teams
    # ck_matches_winner_team with a NULL team: NOT(...) must not evaluate to NULL and slip through.
    "UPDATE matches SET status='COMPLETED', winner_id=team2_id, team1_id=NULL",
])
def test_match_migration_stops_before_ddl_on_bad_legacy_rows(request, session_factory, match_case, legacy):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        connection.execute(text(legacy), {'other_stage': match_case['other_stage']})
        with pytest.raises(RuntimeError, match=rf"Match migration blocked.*match_id \[{match_case['match']}\]"):
            command.upgrade(config, 'head')
        columns, checks, *_ = schema(connection)
        assert 'scheduled_at' not in columns and not CHECKS & checks
        assert connection.scalar(text('SELECT count(*) FROM matches')) == 1
