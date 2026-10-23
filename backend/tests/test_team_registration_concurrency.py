"""Real PostgreSQL connections for submit/cancel races; see test_registration_concurrency."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import delete, event, select

from core.registrations import lock_registration_tournament
from modules.teams.models import TeamMembership
from modules.tournaments.models import TournamentRegistration
from test_catalog_api import make_client
from test_permissions import access, organizer_tournament
from test_registration_concurrency import session_factory
from test_registration_decisions import registration_logs

pytestmark = pytest.mark.postgres


@pytest.fixture
def tournament(access, session_factory):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'))
    return organizer_tournament(client, headers)


def post(factory, headers, path, name, payload=None):
    with make_client(factory, logged_in=False) as client:
        return client.post(path, json=payload, headers=headers(name)).status_code


def wait_for_parent_lock(factory, tid, request, while_locked):
    """Hold the tournament lock until the request queues behind it, then run while_locked(db)."""
    attempted = Event()
    engine = factory.kw['bind']
    def notice_lock(connection, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement and 'FROM tournaments' in statement:
            attempted.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with factory.begin() as db:
                tournament = lock_registration_tournament(db, tid)
                event.listen(engine, 'before_cursor_execute', notice_lock)
                future = pool.submit(request)
                assert attempted.wait(5), 'HTTP request never attempted the parent lock'
                assert not future.done(), 'request did not wait for the parent lock'
                while_locked(db, tournament)
            return future.result(timeout=10)
        finally:
            event.remove(engine, 'before_cursor_execute', notice_lock)


def test_concurrent_submissions_create_one_registration(access, session_factory, tournament):
    _, headers, _, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}/registrations'
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda name: post(session_factory, headers, path, name, {'team_id': teams['Alpha']}),
                                 ['manager', 'admin']))
    assert sorted(statuses) == [201, 409]
    with session_factory() as db:
        assert len(db.scalars(select(TournamentRegistration)).all()) == 1
    assert len(registration_logs(session_factory)) == 1


def test_cancel_and_decision_cannot_both_succeed(access, session_factory, tournament):
    client, headers, _, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}/registrations'
    rid = client.post(path, json={'team_id': teams['Alpha']}, headers=headers('manager')).json()['registration_id']
    requests = [(f'{path}/{rid}/cancel', 'manager', None), (f'{path}/{rid}/decision', 'organizer', {'status': 'APPROVED'})]
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel, decision = list(pool.map(lambda r: post(session_factory, headers, *r), requests))
    assert sorted([cancel, decision]) == [200, 409]
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == ('CANCELLED' if cancel == 200 else 'APPROVED')
    assert len(registration_logs(session_factory)) == 2


@pytest.mark.parametrize('operation', ['submit', 'cancel'])
def test_waiting_writer_sees_committed_close(access, session_factory, tournament, operation):
    client, headers, _, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}/registrations'
    rid = None
    if operation == 'cancel':
        rid = client.post(path, json={'team_id': teams['Alpha']}, headers=headers('manager')).json()['registration_id']
    def request():
        if operation == 'submit':
            return post(session_factory, headers, path, 'manager', {'team_id': teams['Alpha']})
        return post(session_factory, headers, f'{path}/{rid}/cancel', 'manager')
    def close(db, locked):
        locked.status = 'ONGOING'
    assert wait_for_parent_lock(session_factory, tournament, request, close) == 409
    with session_factory() as db:
        rows = db.scalars(select(TournamentRegistration)).all()
        assert [row.status for row in rows] == ([] if operation == 'submit' else ['PENDING'])


@pytest.mark.parametrize('operation', ['submit', 'cancel'])
def test_manager_removed_while_waiting_is_checked_again(access, session_factory, tournament, operation):
    client, headers, users, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}/registrations'
    rid = None
    if operation == 'cancel':
        rid = client.post(path, json={'team_id': teams['Alpha']}, headers=headers('manager')).json()['registration_id']
    def request():
        if operation == 'submit':
            return post(session_factory, headers, path, 'manager', {'team_id': teams['Alpha']})
        return post(session_factory, headers, f'{path}/{rid}/cancel', 'manager')
    def revoke(db, locked):
        with session_factory.begin() as revoke_db:
            revoke_db.execute(delete(TeamMembership).where(TeamMembership.user_id == users['manager']))
    assert wait_for_parent_lock(session_factory, tournament, request, revoke) == 403
    assert len(registration_logs(session_factory)) == (0 if operation == 'submit' else 1)


@pytest.mark.parametrize('operation', ['submit', 'cancel'])
def test_unauthorized_team_writer_does_not_wait_for_lock(access, session_factory, tournament, operation):
    client, headers, _, teams, _ = access
    path = f'/api/v1/tournaments/{tournament}/registrations'
    rid = client.post(path, json={'team_id': teams['Alpha']}, headers=headers('manager')).json()['registration_id']
    def request():
        if operation == 'submit':
            return post(session_factory, headers, path, 'viewer', {'team_id': teams['Beta']})
        return post(session_factory, headers, f'{path}/{rid}/cancel', 'viewer')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with session_factory.begin() as db:
            lock_registration_tournament(db, tournament)
            assert pool.submit(request).result(timeout=3) == 403
    assert len(registration_logs(session_factory)) == 1
