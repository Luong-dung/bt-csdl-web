from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog, RoleAssignment
from modules.teams.models import Organization, Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament
from test_registration_decisions import registration_logs

pytestmark = pytest.mark.postgres


def grant_manager(factory, users, teams, roles, kind, name='manager', team='Alpha'):
    with factory.begin() as db:
        if kind == 'membership':
            db.add(TeamMembership(team_id=teams[team], user_id=users[name], role_in_team='MANAGER'))
        else:
            scope_id = teams[team] if kind == 'TEAM' else db.scalar(select(Organization.organization_id))
            db.add(RoleAssignment(user_id=users[name], role_id=roles['TEAM_MANAGER'], scope_type=kind, scope_id=scope_id))


@pytest.fixture
def tournament(access, session_factory):
    client, headers, users, teams, roles = access
    grant_manager(session_factory, users, teams, roles, 'membership')
    return organizer_tournament(client, headers)


def url(tid, suffix=''):
    return f'/api/v1/tournaments/{tid}/registrations{suffix}'


def register(client, headers, tid, team_id, name='manager'):
    return client.post(url(tid), json={'team_id': team_id}, headers=headers(name))


@pytest.mark.parametrize('kind', ['membership', 'TEAM', 'ORGANIZATION', 'admin'])
def test_team_manager_submits_pending_registration_with_audit(access, session_factory, kind):
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    name = 'admin' if kind == 'admin' else 'manager'
    if kind != 'admin':
        grant_manager(session_factory, users, teams, roles, kind)
    response = register(client, headers, tid, teams['Alpha'], name)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['status'] == 'PENDING' and data['team_id'] == teams['Alpha'] and data['tournament_id'] == tid
    assert data['submitted_by'] == users[name] and data['submitted_at']
    assert data['reviewed_at'] is None and data['cancelled_at'] is None
    [entry] = registration_logs(session_factory)
    assert entry.user_id == users[name] and entry.action == 'TOURNAMENT_REGISTRATION_CREATED'
    assert entry.details['registration_id'] == data['registration_id'] and entry.details['before'] is None
    assert entry.details['after']['status'] == 'PENDING'
    # One row per tournament/team; a second submission is a conflict without a second audit.
    assert register(client, headers, tid, teams['Alpha'], name).status_code == 409
    assert len(registration_logs(session_factory)) == 1


@pytest.mark.parametrize('name,team,expected', [
    (None, 'Alpha', 401),
    ('viewer', 'Alpha', 403),
    ('referee', 'Alpha', 403),
    ('organizer', 'Alpha', 403),
    ('manager', 'Beta', 403),
])
def test_only_manager_of_that_team_can_submit(access, session_factory, tournament, name, team, expected):
    client, headers, _, teams, _ = access
    auth = headers(name) if name else {}
    assert client.post(url(tournament), json={'team_id': teams[team]}, headers=auth).status_code == expected
    assert registration_logs(session_factory) == []


def test_role_without_team_scope_cannot_submit(access, session_factory):
    client, headers, _, teams, _ = access
    tid = organizer_tournament(client, headers)
    # TEAM_MANAGER as a global role alone does not grant any specific team.
    assert register(client, headers, tid, teams['Alpha']).status_code == 403


def test_global_team_manager_assignment_does_not_grant_registration_access(access, session_factory):
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    created = register(client, headers, tid, teams['Alpha'], 'admin')
    assert created.status_code == 201, created.text
    rid = created.json()['registration_id']
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['TEAM_MANAGER'],
                              scope_type='GLOBAL', scope_id=None))

    # A global TEAM_MANAGER assignment must not be treated as authority over every team.
    assert register(client, headers, tid, teams['Beta'], 'viewer').status_code == 403
    assert client.get(url(tid), headers=headers('viewer')).status_code == 403
    assert client.post(url(tid, f'/{rid}/cancel'), headers=headers('viewer')).status_code == 403
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == 'PENDING'
    assert len(registration_logs(session_factory)) == 1


@pytest.mark.parametrize('payload', [
    {}, {'team_id': 0}, {'team_id': -1}, {'team_id': 'abc'}, {'team_id': 2147483648},
    {'team_id': 1, 'status': 'APPROVED'}, {'team_id': 1, 'submitted_by': 1},
])
def test_invalid_payload(access, session_factory, tournament, payload):
    client, headers, *_ = access
    assert client.post(url(tournament), json=payload, headers=headers('manager')).status_code == 422
    assert registration_logs(session_factory) == []


def test_missing_tournament_or_team_is_404(access, session_factory, tournament):
    client, headers, _, teams, _ = access
    assert register(client, headers, 999999, teams['Alpha']).status_code == 404
    assert register(client, headers, tournament, 999999, 'admin').status_code == 404
    assert registration_logs(session_factory) == []


def test_team_from_other_game_is_rejected(access, session_factory, tournament):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        db.get(Team, teams['Alpha']).game_id = 2
    assert register(client, headers, tournament, teams['Alpha']).status_code == 422
    assert registration_logs(session_factory) == []


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_closed_tournament_rejects_submit_and_cancel(access, session_factory, tournament, state):
    client, headers, _, teams, _ = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    with session_factory.begin() as db:
        db.get(Tournament, tournament).status = state
        db.add(Team(name='Gamma', tag='G', game_id=1))
    with session_factory() as db:
        gamma = db.scalar(select(Team.team_id).where(Team.name == 'Gamma'))
    assert register(client, headers, tournament, gamma, 'admin').status_code == 409
    assert client.post(url(tournament, f'/{rid}/cancel'), headers=headers('manager')).status_code == 409
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == 'PENDING'
    assert len(registration_logs(session_factory)) == 1


@pytest.mark.parametrize('state', ['REJECTED', 'CANCELLED'])
def test_final_registration_cannot_be_resubmitted(access, session_factory, tournament, state):
    client, headers, _, teams, _ = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    if state == 'REJECTED':
        decided = client.post(url(tournament, f'/{rid}/decision'), json={'status': 'REJECTED'}, headers=headers('organizer'))
    else:
        decided = client.post(url(tournament, f'/{rid}/cancel'), headers=headers('manager'))
    assert decided.status_code == 200
    assert register(client, headers, tournament, teams['Alpha']).status_code == 409
    assert len(registration_logs(session_factory)) == 2


def test_team_manager_cancels_pending_registration(access, session_factory, tournament):
    client, headers, users, teams, _ = access
    created = register(client, headers, tournament, teams['Alpha']).json()
    response = client.post(url(tournament, f"/{created['registration_id']}/cancel"), headers=headers('manager'))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['status'] == 'CANCELLED' and data['cancelled_by'] == users['manager'] and data['cancelled_at']
    assert data['reviewed_at'] is None
    assert datetime.fromisoformat(data['cancelled_at']) >= datetime.fromisoformat(data['submitted_at'])
    entry = registration_logs(session_factory)[-1]
    assert entry.action == 'TOURNAMENT_REGISTRATION_CANCELLED' and entry.user_id == users['manager']
    assert entry.details['before'] == {'status': 'PENDING', 'cancelled_by': None, 'cancelled_at': None}
    assert entry.details['after']['status'] == 'CANCELLED'
    # Cancelling again, or approving afterwards, conflicts.
    assert client.post(url(tournament, f"/{created['registration_id']}/cancel"), headers=headers('manager')).status_code == 409
    assert client.post(url(tournament, f"/{created['registration_id']}/decision"), json={'status': 'APPROVED'},
                       headers=headers('organizer')).status_code == 409
    assert len(registration_logs(session_factory)) == 2


@pytest.mark.parametrize('decision', ['APPROVED', 'REJECTED'])
def test_decided_registration_cannot_be_cancelled(access, session_factory, tournament, decision):
    client, headers, _, teams, _ = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    assert client.post(url(tournament, f'/{rid}/decision'), json={'status': decision},
                       headers=headers('organizer')).status_code == 200
    assert client.post(url(tournament, f'/{rid}/cancel'), headers=headers('manager')).status_code == 409
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == decision


@pytest.mark.parametrize('name,expected', [(None, 401), ('viewer', 403), ('organizer', 403), ('other_manager', 403)])
def test_only_team_manager_can_cancel(access, session_factory, tournament, name, expected):
    client, headers, users, teams, roles = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    if name == 'other_manager':
        grant_manager(session_factory, users, teams, roles, 'membership', name='viewer', team='Beta')
        name = 'viewer'
    auth = headers(name) if name else {}
    assert client.post(url(tournament, f'/{rid}/cancel'), headers=auth).status_code == expected
    with session_factory() as db:
        assert db.get(TournamentRegistration, rid).status == 'PENDING'
    assert len(registration_logs(session_factory)) == 1


def test_cancel_requires_registration_in_url_tournament(access, session_factory, tournament):
    client, headers, _, teams, _ = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    other = organizer_tournament(client, headers)
    assert client.post(url(other, f'/{rid}/cancel'), headers=headers('manager')).status_code == 404
    assert client.post(url(tournament, '/999999/cancel'), headers=headers('manager')).status_code == 404
    assert client.post(url(999999, f'/{rid}/cancel'), headers=headers('manager')).status_code == 404
    assert client.post(url(tournament, '/0/cancel'), headers=headers('manager')).status_code == 422


def test_team_manager_lists_only_own_team_registrations(access, session_factory, tournament):
    client, headers, users, teams, roles = access
    alpha = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    beta = register(client, headers, tournament, teams['Beta'], 'admin').json()['registration_id']
    own = client.get(url(tournament), headers=headers('manager'))
    assert own.status_code == 200 and [row['registration_id'] for row in own.json()] == [alpha]
    filtered = client.get(url(tournament) + f"?team_id={teams['Alpha']}&status=PENDING", headers=headers('manager'))
    assert [row['registration_id'] for row in filtered.json()] == [alpha]
    assert client.get(url(tournament) + f"?team_id={teams['Beta']}", headers=headers('manager')).status_code == 403
    # The tournament manager still sees every registration and may filter by team.
    everything = client.get(url(tournament), headers=headers('organizer')).json()
    assert [row['registration_id'] for row in everything] == [alpha, beta]
    by_team = client.get(url(tournament) + f"?team_id={teams['Beta']}", headers=headers('organizer')).json()
    assert [row['registration_id'] for row in by_team] == [beta]


def test_manager_of_unregistered_team_gets_empty_list(access, session_factory, tournament):
    client, headers, *_ = access
    response = client.get(url(tournament), headers=headers('manager'))
    assert response.status_code == 200 and response.json() == []


@pytest.mark.parametrize('name,expected', [(None, 401), ('viewer', 403), ('referee', 403)])
def test_non_managers_cannot_list(access, session_factory, tournament, name, expected):
    client, headers, *_ = access
    assert client.get(url(tournament), headers=headers(name) if name else {}).status_code == expected


def test_list_validates_team_filter(access, session_factory, tournament):
    client, headers, *_ = access
    for value in ['0', '-1', 'abc', '2147483648']:
        assert client.get(url(tournament) + f'?team_id={value}', headers=headers('manager')).status_code == 422


def test_revoked_manager_loses_access(access, session_factory, tournament):
    client, headers, users, teams, _ = access
    rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']
    with session_factory.begin() as db:
        membership = db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['manager']))
        membership.status = 'LEFT'
        membership.left_date = datetime.now(timezone.utc).date()
    assert client.get(url(tournament), headers=headers('manager')).status_code == 403
    assert client.post(url(tournament, f'/{rid}/cancel'), headers=headers('manager')).status_code == 403


@pytest.mark.parametrize('operation', ['create', 'cancel'])
def test_audit_failure_rolls_back_registration_write(access, session_factory, tournament, operation):
    client, headers, _, teams, _ = access
    rid = None
    if operation == 'cancel':
        rid = register(client, headers, tournament, teams['Alpha']).json()['registration_id']

    def reject_audit(mapper, connection, target):
        raise IntegrityError('injected audit insert failure', {}, Exception('audit unavailable'))

    event.listen(AuditLog, 'before_insert', reject_audit)
    try:
        if operation == 'create':
            response = register(client, headers, tournament, teams['Alpha'])
        else:
            response = client.post(url(tournament, f'/{rid}/cancel'), headers=headers('manager'))
        assert response.status_code == 409
    finally:
        event.remove(AuditLog, 'before_insert', reject_audit)
    with session_factory() as db:
        rows = db.scalars(select(TournamentRegistration)).all()
        assert [row.status for row in rows] == ([] if operation == 'create' else ['PENDING'])
    assert len(registration_logs(session_factory)) == (0 if operation == 'create' else 1)
