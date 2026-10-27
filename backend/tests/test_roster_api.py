from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.security import create_access_token
from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


def roster(tid, team_id):
    return f'/api/v1/tournaments/{tid}/teams/{team_id}/roster'


def logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament_roster')
                               .order_by(AuditLog.log_id)))


def rows(factory, tid):
    with factory() as db:
        return sorted((r.team_id, r.user_id, r.role_in_team, r.display_name)
                      for r in db.scalars(select(TournamentRoster).where(TournamentRoster.tournament_id == tid)))


@pytest.fixture
def case(access, session_factory):
    """Alpha (APPROVED): manager MANAGER, viewer/p1 PLAYER, p2 SUBSTITUTE. Beta (APPROVED): p3 PLAYER."""
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        extra = [User(username=name, email=f'{name}@example.com', password_hash='unused', role_id=roles['VIEWER'])
                 for name in ('p1', 'p2', 'p3')]
        db.add_all(extra)
        db.flush()
        users.update({u.username: u.user_id for u in extra})
        db.add_all([TournamentRegistration(tournament_id=tid, team_id=team, status='APPROVED',
                                           reviewed_at=datetime.now(timezone.utc))
                    for team in (teams['Alpha'], teams['Beta'])])
        db.add_all([
            TeamMembership(team_id=teams['Alpha'], user_id=users['manager'], role_in_team='MANAGER'),
            TeamMembership(team_id=teams['Alpha'], user_id=users['viewer'], role_in_team='PLAYER'),
            TeamMembership(team_id=teams['Alpha'], user_id=users['p1'], role_in_team='PLAYER'),
            TeamMembership(team_id=teams['Alpha'], user_id=users['p2'], role_in_team='SUBSTITUTE'),
            TeamMembership(team_id=teams['Beta'], user_id=users['p3'], role_in_team='PLAYER'),
        ])
    return tid


def body(*members):
    return {'members': [{'user_id': uid, 'role_in_team': role} for uid, role in members]}


def test_manager_replaces_roster_atomically_with_audit(access, session_factory, case):
    client, headers, users, teams, _ = access
    alpha = teams['Alpha']
    response = client.put(roster(case, alpha), headers=headers('manager'),
                          json=body((users['p2'], 'SUBSTITUTE'), (users['viewer'], 'PLAYER')))
    assert response.status_code == 200
    expected = {'tournament_id': case, 'team_id': alpha, 'locked': False, 'members': sorted([
        {'user_id': users['viewer'], 'display_name': 'viewer', 'role_in_team': 'PLAYER'},
        {'user_id': users['p2'], 'display_name': 'p2', 'role_in_team': 'SUBSTITUTE'},
    ], key=lambda m: m['user_id'])}
    assert response.json() == expected
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get(roster(case, alpha), headers=headers('manager')).json() == expected
    [log] = logs(session_factory)
    assert log.action == 'TOURNAMENT_ROSTER_UPDATED' and log.user_id == users['manager']
    assert log.details['before'] == [] and [m['user_id'] for m in log.details['after']] == sorted(
        [users['viewer'], users['p2']])

    # Replace: drop p2, keep viewer, add p1 in one request.
    response = client.put(roster(case, alpha), headers=headers('manager'),
                          json=body((users['viewer'], 'PLAYER'), (users['p1'], 'PLAYER')))
    assert {m['user_id'] for m in response.json()['members']} == {users['viewer'], users['p1']}
    assert rows(session_factory, case) == sorted([(alpha, users['viewer'], 'PLAYER', 'viewer'),
                                                  (alpha, users['p1'], 'PLAYER', 'p1')])
    assert len(logs(session_factory)) == 2


def test_identical_put_is_noop_and_empty_draft_is_valid(access, session_factory, case):
    client, headers, users, teams, _ = access
    payload = body((users['viewer'], 'PLAYER'))
    first = client.put(roster(case, teams['Alpha']), headers=headers('manager'), json=payload)
    second = client.put(roster(case, teams['Alpha']), headers=headers('manager'), json=payload)
    assert second.status_code == 200 and second.json() == first.json()
    assert len(logs(session_factory)) == 1
    empty = client.put(roster(case, teams['Alpha']), headers=headers('manager'), json={'members': []})
    assert empty.status_code == 200 and empty.json()['members'] == []
    assert rows(session_factory, case) == [] and len(logs(session_factory)) == 2


@pytest.mark.parametrize('payload', [
    {}, {'members': None}, {'members': [], 'extra': 1},
    {'members': [{'user_id': True, 'role_in_team': 'PLAYER'}]},
    {'members': [{'user_id': '5', 'role_in_team': 'PLAYER'}]},
    {'members': [{'user_id': 0, 'role_in_team': 'PLAYER'}]},
    {'members': [{'user_id': 2147483648, 'role_in_team': 'PLAYER'}]},
    {'members': [{'user_id': 5, 'role_in_team': 'MANAGER'}]},
    {'members': [{'user_id': 5, 'role_in_team': 'PLAYER', 'display_name': 'x'}]},
    {'members': [{'user_id': 5, 'role_in_team': 'PLAYER'}, {'user_id': 5, 'role_in_team': 'SUBSTITUTE'}]},
    {'members': [{'user_id': i, 'role_in_team': 'PLAYER'} for i in range(1, 102)]},
])
def test_body_validation(access, session_factory, case, payload):
    client, headers, _, teams, _ = access
    assert client.put(roster(case, teams['Alpha']), headers=headers('manager'), json=payload).status_code == 422
    assert logs(session_factory) == []


@pytest.mark.parametrize('who,role', [
    ('p3', 'PLAYER'),          # active in another team
    ('manager', 'PLAYER'),     # MANAGER membership cannot be promoted by the body
    ('p2', 'PLAYER'),          # role must match membership
    ('referee', 'PLAYER'),     # not a member at all
    ('left', 'PLAYER'),        # membership ended
    ('inactive', 'PLAYER'),    # membership not ACTIVE
])
def test_only_active_player_or_substitute_of_team(access, session_factory, case, who, role):
    client, headers, users, teams, _ = access
    if who in ('left', 'inactive'):
        with session_factory.begin() as db:
            membership = db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p1']))
            if who == 'left':
                membership.left_date = date.today()
            else:
                membership.status = 'INACTIVE'
        who = 'p1'
    response = client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                          json=body((users['viewer'], 'PLAYER'), (users[who], role)))
    assert response.status_code == 422
    assert rows(session_factory, case) == [] and logs(session_factory) == []


@pytest.mark.parametrize('name,status', [(None, 401), ('viewer', 403), ('organizer', 403), ('referee', 403)])
def test_put_requires_team_manager(access, session_factory, case, name, status):
    client, headers, users, teams, roles = access
    if name == 'referee':  # manages Beta only
        with session_factory.begin() as db:
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['TEAM_MANAGER'],
                                  scope_type='TEAM', scope_id=teams['Beta']))
    auth = headers(name) if name else {}
    response = client.put(roster(case, teams['Alpha']), headers=auth, json=body((users['viewer'], 'PLAYER')))
    assert response.status_code == status
    assert rows(session_factory, case) == [] and logs(session_factory) == []


def test_team_scope_assignment_and_admin_can_edit(access, session_factory, case):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['TEAM_MANAGER'],
                              scope_type='TEAM', scope_id=teams['Beta']))
    assert client.put(roster(case, teams['Beta']), headers=headers('referee'),
                      json=body((users['p3'], 'PLAYER'))).status_code == 200
    assert client.put(roster(case, teams['Alpha']), headers=headers('admin'),
                      json=body((users['p1'], 'PLAYER'))).status_code == 200
    assert [log.user_id for log in logs(session_factory)] == [users['referee'], users['admin']]


@pytest.mark.parametrize('state', ['locked', 'ONGOING', 'COMPLETED', 'CANCELLED', 'PENDING', 'REJECTED'])
def test_lifecycle_and_registration_block_writes(access, session_factory, case, state):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        tournament = db.get(Tournament, case)
        if state == 'locked':
            tournament.roster_locked_at = datetime.now(timezone.utc)
            tournament.roster_locked_by = users['organizer']
        elif state in ('PENDING', 'REJECTED'):
            registration = db.scalar(select(TournamentRegistration).where(
                TournamentRegistration.team_id == teams['Alpha']))
            registration.status = state
            if state == 'PENDING':
                registration.reviewed_at = None
        else:
            tournament.status = state
    response = client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                          json=body((users['viewer'], 'PLAYER')))
    assert response.status_code == 409
    assert rows(session_factory, case) == [] and logs(session_factory) == []


def test_missing_resources(access, case):
    client, headers, users, teams, _ = access
    payload = body((users['viewer'], 'PLAYER'))
    assert client.put(roster(999999, teams['Alpha']), headers=headers('admin'), json=payload).status_code == 404
    assert client.put(roster(case, 999999), headers=headers('admin'), json=payload).status_code == 404
    assert client.get(roster(case, 999999), headers=headers('admin')).status_code == 404
    assert client.get(roster(0, teams['Alpha'])).status_code == 422
    assert client.get(roster(case, 2147483648)).status_code == 422


def test_user_in_other_team_roster_conflicts(access, session_factory, case):
    """A player who moved teams after being drafted elsewhere must be removed there first."""
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TournamentRoster(tournament_id=case, team_id=teams['Beta'], user_id=users['p1'],
                                role_in_team='PLAYER', display_name='p1'))
    response = client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                          json=body((users['p1'], 'PLAYER')))
    assert response.status_code == 409
    assert rows(session_factory, case) == [(teams['Beta'], users['p1'], 'PLAYER', 'p1')]
    assert logs(session_factory) == []


def test_failure_rolls_back_roster_and_audit(access, session_factory, case, monkeypatch):
    client, headers, users, teams, _ = access

    def broken_audit(*_):
        raise IntegrityError('audit', {}, Exception('forced'))
    monkeypatch.setattr('routes.rosters.record_audit', broken_audit)
    response = client.put(roster(case, teams['Alpha']), headers=headers('manager'),
                          json=body((users['viewer'], 'PLAYER')))
    assert response.status_code == 409
    assert rows(session_factory, case) == [] and logs(session_factory) == []


@pytest.mark.parametrize('name,status', [(None, 401), ('viewer', 403), ('p3', 403),
                                         ('manager', 200), ('organizer', 200), ('admin', 200)])
def test_draft_read_is_private(access, session_factory, case, name, status):
    client, headers, users, teams, _ = access
    client.put(roster(case, teams['Alpha']), headers=headers('manager'), json=body((users['viewer'], 'PLAYER')))
    response = client.get(roster(case, teams['Alpha']), headers=headers(name) if name else {})
    assert response.status_code == status
    assert response.headers['cache-control'] == 'private, no-store'
    if status == 200:
        assert response.json()['members'] == [
            {'user_id': users['viewer'], 'display_name': 'viewer', 'role_in_team': 'PLAYER'}]


def test_locked_roster_is_public_minimal_and_keeps_snapshot(access, session_factory, case):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add_all([TournamentRoster(tournament_id=case, team_id=teams['Alpha'], user_id=users['p1'],
                                     role_in_team='PLAYER', display_name='Frozen p1'),
                    TournamentRoster(tournament_id=case, team_id=teams['Alpha'], user_id=users['p2'],
                                     role_in_team='SUBSTITUTE', display_name=None)])
        tournament = db.get(Tournament, case)
        tournament.roster_locked_at = datetime.now(timezone.utc)
        tournament.roster_locked_by = users['organizer']
        # Membership changes after lock must not rebuild the snapshot.
        db.scalar(select(TeamMembership).where(TeamMembership.user_id == users['p1'])).left_date = date.today()
        db.get(User, users['p1']).username = 'renamed'
    response = client.get(roster(case, teams['Alpha']))
    assert response.status_code == 200
    assert response.json() == {'tournament_id': case, 'team_id': teams['Alpha'], 'locked': True, 'members': [
        {'user_id': users['p1'], 'display_name': 'Frozen p1', 'role_in_team': 'PLAYER'},
        {'user_id': users['p2'], 'display_name': None, 'role_in_team': 'SUBSTITUTE'},
    ]}
    assert 'email' not in response.text
    bad = {'Authorization': 'Bearer ' + create_access_token({'sub': '999999'})}
    assert client.get(roster(case, teams['Alpha']), headers=bad).status_code == 401


def test_unapproved_team_roster_is_not_found(access, session_factory, case):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        registration = db.scalar(select(TournamentRegistration).where(
            TournamentRegistration.team_id == teams['Alpha']))
        registration.status, registration.reviewed_at = 'PENDING', None
        db.get(Tournament, case).roster_locked_at = datetime.now(timezone.utc)
    assert client.get(roster(case, teams['Alpha']), headers=headers('admin')).status_code == 404
    assert client.get(roster(case, teams['Alpha'])).status_code == 404
