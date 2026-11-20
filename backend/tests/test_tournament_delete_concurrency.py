"""W47-04 races on real PostgreSQL connections: delete vs writers that add tournament data."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from modules.identity.models import AuditLog
from modules.teams.models import TeamMembership
from modules.tournaments.models import Stage, Tournament, TournamentRegistration
from test_catalog_api import make_client
from test_permissions import access, organizer_tournament
from test_registration_concurrency import session_factory
from test_team_registration_concurrency import wait_for_parent_lock

pytestmark = pytest.mark.postgres


@pytest.fixture
def tournament(access, session_factory):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'))
    return organizer_tournament(client, headers)


def call(factory, headers, method, path, name, payload=None):
    with make_client(factory, logged_in=False) as client:
        return client.request(method, path, json=payload, headers=headers(name)).status_code


def deleted(factory):
    with factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.action == 'TOURNAMENT_DELETED')).all()


def test_delete_waits_and_sees_stage_added_meanwhile(access, session_factory, tournament):
    _, headers, *_ = access
    request = lambda: call(session_factory, headers, 'DELETE', f'/api/v1/tournaments/{tournament}', 'organizer')
    def add_stage(db, locked):
        db.add(Stage(tournament_id=locked.tournament_id, name='Groups', sequence_order=1))
    assert wait_for_parent_lock(session_factory, tournament, request, add_stage) == 409
    with session_factory() as db:
        assert db.get(Tournament, tournament) is not None
        assert len(db.scalars(select(Stage)).all()) == 1
    assert deleted(session_factory) == []


def test_delete_waits_and_rechecks_rights(access, session_factory, tournament):
    _, headers, users, *_ = access
    request = lambda: call(session_factory, headers, 'DELETE', f'/api/v1/tournaments/{tournament}', 'organizer')
    def hand_over(db, locked):
        locked.created_by = users['admin']
    assert wait_for_parent_lock(session_factory, tournament, request, hand_over) == 403
    assert deleted(session_factory) == []


def test_parallel_delete_and_registration_never_lose_data(access, session_factory, tournament):
    _, headers, _, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}'
    requests = [('DELETE', path, 'organizer', None),
                ('POST', path + '/registrations', 'manager', {'team_id': teams['Alpha']})]
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete, register = pool.map(lambda r: call(session_factory, headers, *r), requests)
    # Either the delete ran first (registration then finds no tournament) or the registration blocks it.
    assert (delete, register) in ((204, 404), (409, 201))
    with session_factory() as db:
        registrations = db.scalars(select(TournamentRegistration)).all()
        assert (db.get(Tournament, tournament) is None) == (delete == 204)
        assert len(registrations) == (1 if register == 201 else 0)
    assert len(deleted(session_factory)) == (1 if delete == 204 else 0)
