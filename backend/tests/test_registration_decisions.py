from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog, RoleAssignment
from modules.teams.models import Team
from modules.tournaments.models import Tournament, TournamentRegistration
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


@pytest.fixture
def pending(access, session_factory):
    client, headers, users, teams, _ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        row = TournamentRegistration(tournament_id=tid, team_id=teams['Alpha'], submitted_by=users['manager'])
        db.add(row)
        db.flush()
        rid = row.registration_id
    return tid, rid


def path(pending):
    tid, rid = pending
    return f'/api/v1/tournaments/{tid}/registrations/{rid}/decision'


def registration_logs(factory):
    with factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament_registration')).all()


@pytest.mark.parametrize('decision', ['APPROVED', 'REJECTED'])
@pytest.mark.parametrize('reviewer', ['admin', 'organizer', 'scoped', 'global_organizer', 'global_admin'])
def test_authorized_decision_has_actor_and_atomic_audit(access, session_factory, pending, decision, reviewer):
    client, headers, users, _, roles = access
    tid, rid = pending
    name = reviewer
    if reviewer in ('scoped', 'global_organizer', 'global_admin'):
        name = 'viewer'
        with session_factory.begin() as db:
            db.add(RoleAssignment(user_id=users[name], role_id=roles['ADMIN' if reviewer == 'global_admin' else 'ORGANIZER'],
                                  scope_type='TOURNAMENT' if reviewer == 'scoped' else 'GLOBAL',
                                  scope_id=tid if reviewer == 'scoped' else None))
            if reviewer == 'global_organizer':
                db.get(Tournament, tid).created_by = users[name]
    payload = {'status': decision}
    if decision == 'REJECTED':
        payload['rejection_reason'] = '  Ineligible team  '
    response = client.post(path(pending), json=payload, headers=headers(name))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['registration_id'] == rid and data['status'] == decision
    assert data['reviewed_by'] == users[name] and data['reviewed_at']
    assert data['rejection_reason'] == ('Ineligible team' if decision == 'REJECTED' else None)
    entries = registration_logs(session_factory)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.user_id == users[name] and entry.action == 'TOURNAMENT_REGISTRATION_' + decision
    assert entry.details['registration_id'] == rid and entry.details['tournament_id'] == tid
    assert entry.details['before']['status'] == 'PENDING' and entry.details['after']['status'] == decision
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers(name)).status_code == 409
    assert len(registration_logs(session_factory)) == 1


@pytest.mark.parametrize('name', [None, 'viewer', 'manager', 'referee', 'other_scope', 'other_organizer'])
def test_unauthorized_users_cannot_list_or_decide(access, session_factory, pending, name):
    client, headers, users, _, roles = access
    if name in ('other_scope', 'other_organizer'):
        with session_factory.begin() as db:
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'],
                                  scope_type='TOURNAMENT' if name == 'other_scope' else 'GLOBAL',
                                  scope_id=pending[0] + 1 if name == 'other_scope' else None))
        name = 'viewer'
    auth = headers(name) if name else {}
    expected = 403 if name else 401
    assert client.get(f'/api/v1/tournaments/{pending[0]}/registrations', headers=auth).status_code == expected
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=auth).status_code == expected
    with session_factory() as db:
        assert db.get(TournamentRegistration, pending[1]).status == 'PENDING'
    assert registration_logs(session_factory) == []


def test_creatorless_tournament_remains_admin_only(access, session_factory, pending):
    client, headers, users, _, roles = access
    with session_factory.begin() as db:
        db.get(Tournament, pending[0]).created_by = None
        db.add(RoleAssignment(user_id=users['organizer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=pending[0]))
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code == 403
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('admin')).status_code == 200


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_closed_tournament_cannot_process_pending_registration(access, session_factory, pending, state):
    client, headers, *_ = access
    with session_factory.begin() as db:
        db.get(Tournament, pending[0]).status = state
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code == 409
    # History is still readable by the reviewer after closing.
    assert client.get(f'/api/v1/tournaments/{pending[0]}/registrations', headers=headers('organizer')).status_code == 200
    assert registration_logs(session_factory) == []


@pytest.mark.parametrize('state', ['APPROVED', 'REJECTED', 'CANCELLED'])
def test_final_registration_cannot_be_decided_again(access, session_factory, pending, state):
    client, headers, *_ = access
    with session_factory.begin() as db:
        row = db.get(TournamentRegistration, pending[1])
        row.status = state
        if state == 'CANCELLED':
            row.cancelled_at = datetime.now(timezone.utc)
        else:
            row.reviewed_at = datetime.now(timezone.utc)
    assert client.post(path(pending), json={'status': 'REJECTED'}, headers=headers('organizer')).status_code == 409
    assert registration_logs(session_factory) == []


@pytest.mark.parametrize('payload', [
    {}, {'status': 'PENDING'}, {'status': 'CANCELLED'}, {'status': 'accepted'},
    {'status': 'APPROVED', 'team_id': 1}, {'status': 'APPROVED', 'reviewed_by': 1},
    {'status': 'APPROVED', 'rejection_reason': 'No'},
    {'status': 'REJECTED', 'rejection_reason': ''},
    {'status': 'REJECTED', 'rejection_reason': '   '},
    {'status': 'REJECTED', 'rejection_reason': 'x' * 501},
])
def test_invalid_payload_rejected_without_audit(access, session_factory, pending, payload):
    client, headers, *_ = access
    assert client.post(path(pending), json=payload, headers=headers('organizer')).status_code == 422
    assert registration_logs(session_factory) == []


def test_wrong_game_cannot_be_approved_but_can_be_rejected(access, session_factory, pending):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        db.get(Team, teams['Alpha']).game_id = 2
    assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code == 409
    assert client.post(path(pending), json={'status': 'REJECTED'}, headers=headers('organizer')).status_code == 200


def test_list_filter_pagination_and_cross_tournament_isolation(access, session_factory, pending):
    client, headers, users, teams, _ = access
    tid, rid = pending
    other_tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        second = TournamentRegistration(tournament_id=tid, team_id=teams['Beta'], submitted_by=users['manager'])
        db.add(second)
        db.add(TournamentRegistration(tournament_id=other_tid, team_id=teams['Alpha']))
        db.flush()
        second_id = second.registration_id
    url = f'/api/v1/tournaments/{tid}/registrations'
    auth = headers('organizer')
    assert [r['registration_id'] for r in client.get(url, headers=auth).json()] == [rid, second_id]
    assert client.get(url + '?limit=1&offset=1', headers=auth).json()[0]['registration_id'] == second_id
    assert client.get(url + '?status=APPROVED', headers=auth).json() == []
    assert len(client.get(url + '?status=PENDING', headers=auth).json()) == 2
    assert client.post(path((other_tid, rid)), json={'status': 'APPROVED'}, headers=auth).status_code == 404
    for query in ('limit=0', 'limit=101', 'offset=-1', 'offset=999999999999999999999', 'status=BAD'):
        assert client.get(url + '?' + query, headers=auth).status_code == 422


@pytest.mark.parametrize('tid,rid,expected', [(99999, 1, 404), (1, 99999, 404), (0, 1, 422), (1, 0, 422), (2147483648, 1, 422)])
def test_missing_or_invalid_ids(access, pending, tid, rid, expected):
    client, headers, *_ = access
    # The tournament ID may differ on PostgreSQL; substitute only the existing sentinel.
    if tid == 1:
        tid = pending[0]
    assert client.post(path((tid, rid)), json={'status': 'APPROVED'}, headers=headers('admin')).status_code == expected


@pytest.mark.parametrize('target', [AuditLog, TournamentRegistration])
def test_write_or_audit_failure_rolls_back_everything(access, session_factory, pending, target):
    client, headers, *_ = access
    def reject(mapper, connection, row):
        raise IntegrityError('injected failure', {}, Exception('unavailable'))
    event_name = 'before_insert' if target is AuditLog else 'before_update'
    event.listen(target, event_name, reject)
    try:
        assert client.post(path(pending), json={'status': 'APPROVED'}, headers=headers('organizer')).status_code == 409
    finally:
        event.remove(target, event_name, reject)
    with session_factory() as db:
        row = db.get(TournamentRegistration, pending[1])
        assert row.status == 'PENDING' and row.reviewed_by is None and row.reviewed_at is None
    assert registration_logs(session_factory) == []


@pytest.mark.parametrize('invalid', ['duplicate', 'status', 'timestamps', 'reason', 'foreign_key'])
def test_database_constraints(access, session_factory, pending, invalid):
    tid, _ = pending
    _, _, _, teams, _ = access
    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            row = TournamentRegistration(tournament_id=tid, team_id=teams['Beta'])
            if invalid == 'duplicate':
                row.team_id = teams['Alpha']
            elif invalid == 'status':
                row.status = 'UNKNOWN'
            elif invalid == 'timestamps':
                row.status = 'APPROVED'
            elif invalid == 'reason':
                row.rejection_reason = 'Not rejected'
            else:
                row.team_id = 999999
            db.add(row)
