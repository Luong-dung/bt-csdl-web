"""Roster lock races on independent PostgreSQL transactions, not savepoints."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from threading import Event

import pytest
from sqlalchemy import event, select

from core.rosters import lock_roster_teams
from core.tournaments import lock_tournament
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import make_client
from test_permissions import access
from test_registration_concurrency import session_factory
from test_roster_api import body, case, roster
from test_roster_lock import draft, lock_logs, lock_path

pytestmark = pytest.mark.postgres


def queued(factory, table, request, hold, holder_action):
    """Run `request` while another connection holds `hold`; apply `holder_action` and commit before release."""
    started = Event()
    engine = factory.kw['bind']

    def probe(connection, cursor, statement, parameters, context, executemany):
        if f'FROM {table}' in statement and 'FOR UPDATE' in statement:
            started.set()
    with factory() as holder:
        hold(holder)
        event.listen(engine, 'before_cursor_execute', probe)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(request)
                try:
                    assert started.wait(5), f'request never queued on {table}'
                    assert not future.done(), f'request did not wait for the {table} lock'
                    holder_action(holder)
                    holder.commit()
                finally:
                    holder.rollback()
                return future.result(timeout=10)
        finally:
            event.remove(engine, 'before_cursor_execute', probe)


def post_lock(factory, headers, tid):
    def request():
        with make_client(factory, logged_in=False) as client:
            return client.post(lock_path(tid), headers=headers('organizer')).status_code
    return request


def test_lock_waits_for_roster_writer_and_sees_removed_player(session_factory, access, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)

    def remove_beta_player(holder):  # what a concurrent PUT [] for Beta commits
        holder.delete(holder.scalar(select(TournamentRoster).where(TournamentRoster.team_id == teams['Beta'])))
    status = queued(session_factory, 'tournaments', post_lock(session_factory, headers, case),
                    lambda h: lock_tournament(h, case), remove_beta_player)
    assert status == 409
    with session_factory() as db:
        assert db.get(Tournament, case).roster_locked_at is None
    assert lock_logs(session_factory) == []


def test_roster_put_waits_for_lock_and_is_rejected(session_factory, access, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)

    def put():
        with make_client(session_factory, logged_in=False) as c:
            return c.put(roster(case, teams['Alpha']), headers=headers('manager'),
                         json=body((users['p1'], 'PLAYER'))).status_code

    def commit_lock(holder):
        tournament = holder.get(Tournament, case)
        tournament.roster_locked_at = datetime.now(timezone.utc)
        tournament.roster_locked_by = users['organizer']
    assert queued(session_factory, 'tournaments', put, lambda h: lock_tournament(h, case), commit_lock) == 409
    assert {m['user_id'] for m in client.get(roster(case, teams['Alpha'])).json()['members']} == {
        users['viewer'], users['p2']}


def test_lock_waits_for_membership_writer_and_rejects_ended_member(session_factory, access, case):
    """A membership writer holds only the team lock; the roster lock queues on it after the tournament lock."""
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)

    def end_p2(holder):
        holder.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p2'])).left_date = date.today()
    status = queued(session_factory, 'teams', post_lock(session_factory, headers, case),
                    lambda h: lock_roster_teams(h, [teams['Alpha']]), end_p2)
    assert status == 409 and lock_logs(session_factory) == []


def test_membership_writer_waits_for_lock_and_snapshot_is_kept(session_factory, access, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    members = client.get(f'/api/v1/teams/{teams["Alpha"]}/members', headers=headers('manager')).json()
    mid = next(m['membership_id'] for m in members if m['user_id'] == users['p2'])

    def end_membership():
        with make_client(session_factory, logged_in=False) as c:
            return c.post(f'/api/v1/teams/{teams["Alpha"]}/members/{mid}/end',
                          headers=headers('manager')).status_code
    def commit_lock(holder):  # what the lock writer commits while holding tournament and team locks
        tournament = holder.get(Tournament, case)
        tournament.roster_locked_at = datetime.now(timezone.utc)
        tournament.roster_locked_by = users['organizer']
    status = queued(session_factory, 'teams', end_membership,
                    lambda h: (lock_tournament(h, case), lock_roster_teams(h, [teams['Alpha']])), commit_lock)
    assert status == 200  # membership may change after the lock; the snapshot does not
    snapshot = client.get(roster(case, teams['Alpha'])).json()
    assert snapshot['locked'] and users['p2'] in {m['user_id'] for m in snapshot['members']}


@pytest.mark.parametrize('locked_first,status', [(True, 200), (False, 409)])
def test_start_waits_for_lock_decision(session_factory, access, case, locked_first, status):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)

    def start():
        with make_client(session_factory, logged_in=False) as c:
            return c.post(f'/api/v1/tournaments/{case}/status', headers=headers('organizer'),
                          json={'status': 'ONGOING'}).status_code

    def maybe_lock(holder):
        if locked_first:
            tournament = holder.get(Tournament, case)
            tournament.roster_locked_at = datetime.now(timezone.utc)
            tournament.roster_locked_by = users['organizer']
    assert queued(session_factory, 'tournaments', start, lambda h: lock_tournament(h, case), maybe_lock) == status
    assert client.get(f'/api/v1/tournaments/{case}').json()['status'] == ('ONGOING' if locked_first else 'UPCOMING')


def test_approval_waits_for_lock_and_is_rejected(session_factory, access, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    with session_factory.begin() as db:
        gamma = Team(name='Gamma', tag='G', game_id=1)
        db.add(gamma)
        db.flush()
        pending = TournamentRegistration(tournament_id=case, team_id=gamma.team_id, status='PENDING')
        db.add(pending)
        db.flush()
        rid = pending.registration_id

    def approve():
        with make_client(session_factory, logged_in=False) as c:
            return c.post(f'/api/v1/tournaments/{case}/registrations/{rid}/decision',
                          headers=headers('organizer'), json={'status': 'APPROVED'}).status_code

    def commit_lock(holder):
        tournament = holder.get(Tournament, case)
        tournament.roster_locked_at = datetime.now(timezone.utc)
        tournament.roster_locked_by = users['organizer']
    assert queued(session_factory, 'tournaments', approve, lambda h: lock_tournament(h, case), commit_lock) == 409
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == 'PENDING'


def test_parallel_lock_requests_audit_once(session_factory, access, case):
    client, headers, users, teams, _ = access
    draft(client, headers, users, teams, case)
    request = post_lock(session_factory, headers, case)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: request(), range(2)))
    assert statuses == [200, 200]
    assert len(lock_logs(session_factory)) == 1
