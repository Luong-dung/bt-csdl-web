"""W47-03 races on real PostgreSQL connections: team update vs registration creation.

Both writers lock the team row (registration: tournament -> team), so whichever commits first wins
and the other re-reads committed data after its lock wait.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event

import pytest
from sqlalchemy import event, select

from core.rosters import lock_roster_teams
from modules.catalog.models import Game
from modules.identity.models import AuditLog
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import TournamentRegistration
from test_catalog_api import make_client
from test_permissions import access, organizer_tournament
from test_registration_concurrency import session_factory

pytestmark = pytest.mark.postgres


@pytest.fixture
def tournament(access, session_factory):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'))
    return organizer_tournament(client, headers)


def other_game(session_factory):
    with session_factory() as db:
        return db.scalar(select(Game.game_id).where(Game.game_id != 1).order_by(Game.game_id))


def call(factory, headers, method, path, payload):
    with make_client(factory, logged_in=False) as client:
        return client.request(method, path, json=payload, headers=headers('manager')).status_code


def while_team_locked(factory, team_id, request, change):
    """Hold the team row lock until the request queues on it, apply change(db, team), then commit."""
    attempted = Event()
    engine = factory.kw['bind']

    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement and 'FROM teams' in statement:
            attempted.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with factory.begin() as db:
                [team] = lock_roster_teams(db, [team_id])
                event.listen(engine, 'before_cursor_execute', notice)
                future = pool.submit(request)
                assert attempted.wait(5), 'request never asked for the team lock'
                assert not future.done(), 'request did not wait for the team lock'
                change(db, team)
            return future.result(timeout=10)
        finally:
            event.remove(engine, 'before_cursor_execute', notice)


def test_registration_waits_for_game_change_and_rejects(access, session_factory, tournament):
    _, headers, _, teams, _ = access
    game = other_game(session_factory)
    request = lambda: call(session_factory, headers, 'POST', f'/api/v1/tournaments/{tournament}/registrations',
                           {'team_id': teams['Alpha']})
    def change_game(db, team):
        team.game_id = game
    assert while_team_locked(session_factory, teams['Alpha'], request, change_game) == 422
    with session_factory() as db:
        assert db.scalars(select(TournamentRegistration)).all() == []


def test_team_update_waits_for_registration_and_rejects(access, session_factory, tournament):
    _, headers, _, teams, _ = access
    game = other_game(session_factory)
    request = lambda: call(session_factory, headers, 'PATCH', f'/api/v1/teams/{teams["Alpha"]}', {'game_id': game})
    def register(db, team):
        db.add(TournamentRegistration(tournament_id=tournament, team_id=team.team_id, status='PENDING',
                                      submitted_at=datetime.now(timezone.utc)))
    assert while_team_locked(session_factory, teams['Alpha'], request, register) == 409
    with session_factory() as db:
        assert db.get(Team, teams['Alpha']).game_id == 1
        assert db.scalars(select(AuditLog).where(AuditLog.resource == 'team')).all() == []


def test_parallel_game_change_and_registration_stay_consistent(access, session_factory, tournament):
    _, headers, _, teams, _ = access
    game = other_game(session_factory)
    requests = [('PATCH', f'/api/v1/teams/{teams["Alpha"]}', {'game_id': game}),
                ('POST', f'/api/v1/tournaments/{tournament}/registrations', {'team_id': teams['Alpha']})]
    with ThreadPoolExecutor(max_workers=2) as pool:
        update, registration = pool.map(lambda r: call(session_factory, headers, *r), requests)
    assert sorted([update, registration]) in ([200, 422], [201, 409])
    with session_factory() as db:
        team = db.get(Team, teams['Alpha'])
        registrations = db.scalars(select(TournamentRegistration)).all()
        # Never a registration whose team plays a different game than the tournament.
        assert (team.game_id, len(registrations)) == ((game, 0) if update == 200 else (1, 1))
