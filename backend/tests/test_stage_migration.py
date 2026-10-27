import pytest
from alembic import command
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_permissions import access
from test_roster_migration import migration_config
from test_stage_api import stage_case

pytestmark = pytest.mark.postgres


def test_stage_upgrade_downgrade_preserves_stages_matches_and_constraints(request, session_factory, stage_case):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    tid, _, ids = stage_case
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        # Fresh installation already exercised the live-metadata path via fixture.
        command.downgrade(config, 'cb86835f3e5f')
        assert not inspect(connection).get_unique_constraints('stages')
        connection.execute(text("INSERT INTO matches (tournament_id, stage_id, round_no, score_team1, score_team2, status) "
                                "VALUES (:tid, :sid, 1, 0, 0, 'PENDING')"), {'tid': tid, 'sid': ids[0]})
        assert next(f for f in inspect(connection).get_foreign_keys('matches') if f['constrained_columns'] == ['stage_id'])['options']['ondelete'] == 'CASCADE'
        command.upgrade(config, 'head')
        inspector = inspect(connection)
        assert 'uq_stages_tournament_order' in {c['name'] for c in inspector.get_unique_constraints('stages')}
        assert {'ck_stages_positive_order', 'ck_stages_name'} <= {c['name'] for c in inspector.get_check_constraints('stages')}
        fk = next(f for f in inspector.get_foreign_keys('matches') if f['constrained_columns'] == ['stage_id'])
        assert fk['options']['ondelete'] == 'RESTRICT'
        assert connection.scalar(text('SELECT count(*) FROM stages')) == 3
        assert connection.scalar(text('SELECT count(*) FROM matches')) == 1
        assert connection.scalar(text('SELECT name FROM stages WHERE stage_id=:sid'), {'sid': ids[0]}) == 'Group'
        command.downgrade(config, 'cb86835f3e5f')
        command.upgrade(config, 'head')
        assert connection.scalar(text('SELECT count(*) FROM matches')) == 1


@pytest.mark.parametrize('invalid', ['duplicate', 'zero', 'blank'])
def test_stage_migration_stops_on_bad_legacy_data_without_changing_schema(request, session_factory, stage_case, invalid):
    if not request.config.getoption('--postgres'):
        pytest.skip('requires PostgreSQL migration DDL')
    tid, _, ids = stage_case
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, 'cb86835f3e5f')
        statement = {
            'duplicate': 'UPDATE stages SET sequence_order=1 WHERE stage_id=:sid',
            'zero': 'UPDATE stages SET sequence_order=0 WHERE stage_id=:sid',
            'blank': "UPDATE stages SET name='  ' WHERE stage_id=:sid",
        }[invalid]
        connection.execute(text(statement), {'sid': ids[1]})
        with pytest.raises(RuntimeError, match='Stage migration blocked'):
            command.upgrade(config, 'head')
        assert not inspect(connection).get_unique_constraints('stages')
        fk = next(f for f in inspect(connection).get_foreign_keys('matches') if f['constrained_columns'] == ['stage_id'])
        assert fk['options']['ondelete'] == 'CASCADE'
        assert connection.scalar(text('SELECT count(*) FROM stages')) == 3
