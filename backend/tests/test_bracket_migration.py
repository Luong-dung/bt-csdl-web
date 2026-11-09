"""W46 upgrade/downgrade must preserve historical matches and refuse metadata loss."""
import pytest
from alembic import command
from sqlalchemy import inspect, text

from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access
from test_bracket_foundation import bracket_case, add_bracket, add_node
from test_roster_migration import migration_config

pytestmark = pytest.mark.postgres
PREVIOUS = 'b45a01c0ffee'


def test_upgrade_from_w45_preserves_linked_matches_and_standings(request, session_factory, match_case, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, _, teams, _ = access
    with session_factory() as db:
        connection = db.connection()
        config = migration_config(connection)
        command.downgrade(config, PREVIOUS)
        assert 'tournament_brackets' not in inspect(connection).get_table_names()
        connection.execute(text('UPDATE matches SET next_match_id=match_id WHERE match_id=:id'), {'id': match_case['match']})
        connection.execute(text('INSERT INTO tournament_standings (tournament_id,team_id,final_rank,matches_played,wins,losses,points,prize_money) '
                                'VALUES (:tid,:team,1,1,1,0,3,100)'), {'tid': match_case['tid'], 'team': teams['Alpha']})
        before = connection.execute(text('SELECT * FROM matches ORDER BY match_id')).all()
        standings = connection.execute(text('SELECT * FROM tournament_standings')).all()
        command.upgrade(config, 'head')
        assert {'tournament_brackets', 'bracket_matches'} <= set(inspect(connection).get_table_names())
        assert connection.scalar(text('SELECT count(*) FROM bracket_matches')) == 0
        assert connection.scalar(text('SELECT count(*) FROM tournament_brackets')) == 0
        assert connection.execute(text('SELECT * FROM matches ORDER BY match_id')).all() == before
        assert connection.execute(text('SELECT * FROM tournament_standings')).all() == standings
        command.downgrade(config, PREVIOUS)
        assert connection.execute(text('SELECT * FROM matches ORDER BY match_id')).all() == before
        command.upgrade(config, 'head')


def test_downgrade_with_managed_bracket_stops_before_ddl(request, session_factory, bracket_case, access):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL migration DDL')
    _, _, users, _, _ = access
    with session_factory() as db:
        bracket = add_bracket(db, bracket_case, users)
        node = add_node(db, bracket, 1, 1)
        connection = db.connection()
        config = migration_config(connection)
        with pytest.raises(RuntimeError, match='Bracket downgrade blocked'):
            command.downgrade(config, PREVIOUS)
        assert {'tournament_brackets', 'bracket_matches'} <= set(inspect(connection).get_table_names())
        assert connection.scalar(text('SELECT count(*) FROM bracket_matches WHERE match_id=:id'), {'id': node.match_id}) == 1
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == 'c46a01b00001'
