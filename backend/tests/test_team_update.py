"""W47-03: PATCH /teams/{id} and organization CRUD (W04-01)."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

import routes.organizations
import routes.team
from modules.catalog.models import Game
from modules.identity.models import AuditLog, RoleAssignment
from modules.teams.models import Organization, Team, TeamMembership
from modules.tournaments.models import Tournament, TournamentRegistration
from test_catalog_api import session_factory
from test_permissions import access

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


@pytest.fixture
def setup(access, session_factory):
    """viewer manages Alpha through membership; Alpha belongs to 'Org'; second org 'Org2' exists."""
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['viewer'], role_in_team='MANAGER'))
        db.add(Organization(name='Org2'))
        db.flush()
        orgs = {o.name: o.organization_id for o in db.scalars(select(Organization))}
        games = list(db.scalars(select(Game.game_id).order_by(Game.game_id)))
    return client, headers, users, teams, roles, orgs, games


def patch(client, headers, team_id, payload, name='viewer'):
    return client.patch(f'/api/v1/teams/{team_id}', json=payload, headers=headers(name) if name else None)


def logs(session_factory, resource='team'):
    with session_factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.resource == resource).order_by(AuditLog.log_id)).all()


def assign_org_manager(session_factory, users, roles, name, organization_id):
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users[name], role_id=roles['TEAM_MANAGER'],
                              scope_type='ORGANIZATION', scope_id=organization_id))


def add_registration(session_factory, team_id, status='PENDING', tournament_status='UPCOMING', locked=False):
    with session_factory.begin() as db:
        tournament = Tournament(name=f'Cup {tournament_status} {status} {locked}', game_id=1,
                                start_date=date(2026, 12, 1), status=tournament_status,
                                roster_locked_at=NOW if locked else None)
        db.add(tournament)
        db.flush()
        registration = TournamentRegistration(
            tournament_id=tournament.tournament_id, team_id=team_id, status=status, submitted_at=NOW,
            reviewed_at=NOW if status in ('APPROVED', 'REJECTED') else None,
            cancelled_at=NOW if status == 'CANCELLED' else None)
        db.add(registration)
        db.flush()
        return registration.registration_id


# ---- Team update -------------------------------------------------------------------------------


def test_manager_updates_profile_with_audit(setup, session_factory):
    client, headers, users, teams, _, orgs, _ = setup
    response = patch(client, headers, teams['Alpha'],
                     {'name': ' Alpha Prime ', 'tag': 'alp', 'logo_url': 'https://cdn.example/alpha.png'})
    assert response.status_code == 200
    assert response.json() == {'team_id': teams['Alpha'], 'name': 'Alpha Prime', 'tag': 'ALP', 'game_id': 1,
                               'organization_id': orgs['Org'], 'logo_url': 'https://cdn.example/alpha.png'}
    detail = client.get(f'/api/v1/teams/{teams["Alpha"]}').json()
    assert (detail['name'], detail['logo_url'], detail['organization_id']) == (
        'Alpha Prime', 'https://cdn.example/alpha.png', orgs['Org'])
    [log] = logs(session_factory)
    assert (log.action, log.user_id, log.resource_id, log.tournament_id) == (
        'TEAM_UPDATED', users['viewer'], teams['Alpha'], None)
    assert log.details['before'] == {'team_id': teams['Alpha'], 'organization_id': orgs['Org'], 'game_id': 1,
                                     'name': 'Alpha', 'tag': 'A', 'logo_url': None}
    assert log.details['after']['tag'] == 'ALP'
    # Clearing the optional logo is allowed with null.
    assert patch(client, headers, teams['Alpha'], {'logo_url': None}).json()['logo_url'] is None


def test_permission_matrix(setup, session_factory):
    client, headers, _, teams, *_ = setup
    assert patch(client, headers, teams['Alpha'], {'name': 'Nope'}, name=None).status_code == 401
    assert patch(client, headers, teams['Beta'], {'name': 'Nope'}).status_code == 403  # manages Alpha only
    assert patch(client, headers, teams['Alpha'], {'name': 'Nope'}, name='organizer').status_code == 403
    assert patch(client, headers, 999999, {'name': 'Nope'}).status_code == 404
    assert patch(client, headers, teams['Beta'], {'name': 'Beta by admin'}, name='admin').status_code == 200
    assert len(logs(session_factory)) == 1  # only the admin update


@pytest.mark.parametrize('payload', [
    {}, {'status': 'X'}, {'name': None}, {'tag': None}, {'game_id': None}, {'name': 'A'},
    {'tag': 'a b'}, {'tag': 'x' * 11}, {'logo_url': 'ftp://x'}, {'logo_url': 'https://' + 'a' * 250},
    {'game_id': 0}, {'organization_id': 0}, {'team_id': 5},
])
def test_invalid_payload_422_without_audit(setup, session_factory, payload):
    client, headers, _, teams, *_ = setup
    assert patch(client, headers, teams['Alpha'], payload).status_code == 422
    assert logs(session_factory) == []


def test_unknown_game_or_organization_422(setup, session_factory):
    client, headers, _, teams, *_ = setup
    assert patch(client, headers, teams['Alpha'], {'game_id': 999999}).status_code == 422
    assert patch(client, headers, teams['Beta'], {'organization_id': 999999}, name='admin').status_code == 422
    assert logs(session_factory) == []


def test_duplicate_tag_409_and_noop_not_audited(setup, session_factory):
    client, headers, _, teams, *_ = setup
    with session_factory.begin() as db:
        db.get(Team, teams['Beta']).tag = 'BB'
        db.get(Team, teams['Alpha']).tag = 'AA'
    assert patch(client, headers, teams['Alpha'], {'tag': 'bb'}).status_code == 409  # case-insensitive
    same = patch(client, headers, teams['Alpha'], {'name': 'Alpha', 'tag': 'aa', 'game_id': 1})
    assert same.status_code == 200 and same.json()['tag'] == 'AA'
    assert logs(session_factory) == []


def test_change_game_when_free(setup, session_factory):
    client, headers, _, teams, _, _, games = setup
    response = patch(client, headers, teams['Alpha'], {'game_id': games[1]})
    assert response.status_code == 200 and response.json()['game_id'] == games[1]
    assert logs(session_factory)[0].details['after']['game_id'] == games[1]


@pytest.mark.parametrize('status,tournament_status', [
    ('PENDING', 'UPCOMING'), ('APPROVED', 'UPCOMING'), ('APPROVED', 'ONGOING'),
])
def test_open_registration_blocks_game_and_organization(setup, session_factory, status, tournament_status):
    client, headers, _, teams, _, orgs, games = setup
    add_registration(session_factory, teams['Alpha'], status, tournament_status)
    assert patch(client, headers, teams['Alpha'], {'game_id': games[1]}).status_code == 409
    assert patch(client, headers, teams['Alpha'], {'organization_id': None}, name='admin').status_code == 409
    assert patch(client, headers, teams['Alpha'], {'organization_id': orgs['Org2'], 'name': 'X Y'},
                 name='admin').status_code == 409
    # Profile fields stay editable; nothing from the rejected requests was written.
    assert patch(client, headers, teams['Alpha'], {'name': 'Still editable'}).status_code == 200
    with session_factory() as db:
        team = db.get(Team, teams['Alpha'])
        assert (team.game_id, team.organization_id, team.name) == (1, orgs['Org'], 'Still editable')
    assert len(logs(session_factory)) == 1


@pytest.mark.parametrize('status,tournament_status', [
    ('REJECTED', 'UPCOMING'), ('CANCELLED', 'UPCOMING'), ('PENDING', 'CANCELLED'), ('APPROVED', 'COMPLETED'),
])
def test_finished_registration_does_not_block(setup, session_factory, status, tournament_status):
    client, headers, _, teams, _, orgs, games = setup
    add_registration(session_factory, teams['Alpha'], status, tournament_status)
    assert patch(client, headers, teams['Alpha'], {'organization_id': orgs['Org2']}, name='admin').status_code == 200
    assert patch(client, headers, teams['Alpha'], {'game_id': games[1]}).status_code == 200


def test_locked_roster_history_blocks_game_only(setup, session_factory):
    client, headers, _, teams, _, orgs, games = setup
    add_registration(session_factory, teams['Alpha'], 'APPROVED', 'COMPLETED', locked=True)
    response = patch(client, headers, teams['Alpha'], {'game_id': games[1]})
    assert response.status_code == 409 and 'đội hình khóa' in response.json()['detail']
    assert patch(client, headers, teams['Alpha'], {'organization_id': orgs['Org2']}, name='admin').status_code == 200


def test_organization_move_requires_both_sides(setup, session_factory):
    client, headers, users, teams, roles, orgs, _ = setup
    alpha = teams['Alpha']
    # A plain team manager cannot detach the team from its organization or move it elsewhere.
    assert patch(client, headers, alpha, {'organization_id': None}).status_code == 403
    assert patch(client, headers, alpha, {'organization_id': orgs['Org2']}).status_code == 403
    assign_org_manager(session_factory, users, roles, 'viewer', orgs['Org'])
    # Managing the source only is not enough to hand the team to another organization.
    assert patch(client, headers, alpha, {'organization_id': orgs['Org2']}).status_code == 403
    assert patch(client, headers, alpha, {'organization_id': None}).status_code == 200
    # Attaching a free team needs rights on the target organization.
    assert patch(client, headers, alpha, {'organization_id': orgs['Org2']}).status_code == 403
    assign_org_manager(session_factory, users, roles, 'viewer', orgs['Org2'])
    assert patch(client, headers, alpha, {'organization_id': orgs['Org2']}).status_code == 200
    assert [log.details['after']['organization_id'] for log in logs(session_factory)] == [None, orgs['Org2']]


def test_organization_scope_manager_can_edit_team_of_org(setup, session_factory):
    client, headers, users, teams, roles, orgs, _ = setup
    assert patch(client, headers, teams['Alpha'], {'name': 'Org edit'}, name='manager').status_code == 403
    assign_org_manager(session_factory, users, roles, 'manager', orgs['Org'])
    assert patch(client, headers, teams['Alpha'], {'name': 'Org edit'}, name='manager').status_code == 200
    assert patch(client, headers, teams['Beta'], {'name': 'Org edit'}, name='manager').status_code == 403


def test_audit_failure_rolls_back_update(setup, session_factory, monkeypatch):
    client, headers, _, teams, *_ = setup
    def broken(*args, **kwargs):
        raise RuntimeError('audit down')
    monkeypatch.setattr(routes.team, 'record_audit', broken)
    with pytest.raises(RuntimeError):
        patch(client, headers, teams['Alpha'], {'name': 'Rolled back'})
    with session_factory() as db:
        assert db.get(Team, teams['Alpha']).name == 'Alpha'


def test_team_capabilities_editable_fields(setup, session_factory):
    client, headers, users, teams, roles, orgs, _ = setup
    def caps(team, name='viewer'):
        return client.get(f'/api/v1/teams/{team}/capabilities', headers=headers(name)).json()
    viewer = caps(teams['Alpha'])
    assert viewer['can_update'] is True
    assert viewer['editable_fields'] == ['name', 'tag', 'logo_url', 'game_id']  # no organization rights
    assert caps(teams['Alpha'], 'admin')['editable_fields'] == ['name', 'tag', 'logo_url', 'game_id', 'organization_id']
    assert caps(teams['Beta'])['can_update'] is False and caps(teams['Beta'])['editable_fields'] == []
    assign_org_manager(session_factory, users, roles, 'viewer', orgs['Org'])
    assert 'organization_id' in caps(teams['Alpha'])['editable_fields']
    add_registration(session_factory, teams['Alpha'], 'PENDING', 'UPCOMING')
    assert caps(teams['Alpha'], 'admin')['editable_fields'] == ['name', 'tag', 'logo_url']


def test_list_endpoints_keep_minimal_shape(setup):
    client, *_ = setup
    assert all(set(row) == {'team_id', 'name', 'tag', 'game_id'} for row in client.get('/api/v1/teams').json())


# ---- Organizations -----------------------------------------------------------------------------


def org_path(organization_id=None):
    return '/api/v1/organizations' + (f'/{organization_id}' if organization_id is not None else '')


def test_organizations_public_read(setup):
    client, _, _, teams, _, orgs, _ = setup
    assert [o['name'] for o in client.get(org_path()).json()] == ['Org', 'Org2']
    detail = client.get(org_path(orgs['Org'])).json()
    assert detail['name'] == 'Org' and [t['team_id'] for t in detail['teams']] == [teams['Alpha']]
    assert client.get(org_path(999999)).status_code == 404
    assert client.get(org_path(0)).status_code == 422


def test_create_organization_admin_only(setup, session_factory):
    client, headers, users, *_ = setup
    assert client.post(org_path(), json={'name': 'New Org'}).status_code == 401
    assert client.post(org_path(), json={'name': 'New Org'}, headers=headers('organizer')).status_code == 403
    for bad in [{}, {'name': ' x '}, {'name': 'y' * 151}, {'name': 'Ok', 'extra': 1}]:
        assert client.post(org_path(), json=bad, headers=headers('admin')).status_code == 422
    assert client.post(org_path(), json={'name': 'Org'}, headers=headers('admin')).status_code == 409
    created = client.post(org_path(), json={'name': ' New Org '}, headers=headers('admin'))
    assert created.status_code == 201 and created.json()['name'] == 'New Org'
    [log] = logs(session_factory, 'organization')
    assert (log.action, log.user_id, log.resource_id) == (
        'ORGANIZATION_CREATED', users['admin'], created.json()['organization_id'])
    assert log.details['before'] is None and log.details['after']['name'] == 'New Org'


def test_update_organization_rights_and_audit(setup, session_factory):
    client, headers, users, _, roles, orgs, _ = setup
    path = org_path(orgs['Org'])
    assert client.patch(path, json={'name': 'Renamed'}).status_code == 401
    assert client.patch(path, json={'name': 'Renamed'}, headers=headers('viewer')).status_code == 403
    assert client.patch(org_path(999999), json={'name': 'Renamed'}, headers=headers('admin')).status_code == 404
    caps = client.get(path + '/capabilities', headers=headers('manager')).json()
    assert caps == {'organization_id': orgs['Org'], 'can_update': False}
    assign_org_manager(session_factory, users, roles, 'manager', orgs['Org'])
    assert client.get(path + '/capabilities', headers=headers('manager')).json()['can_update'] is True
    assert client.patch(path, json={'name': 'Org2'}, headers=headers('manager')).status_code == 409
    assert client.patch(org_path(orgs['Org2']), json={'name': 'X Org'}, headers=headers('manager')).status_code == 403
    assert client.patch(path, json={'name': 'Org'}, headers=headers('manager')).status_code == 200  # no-op
    renamed = client.patch(path, json={'name': 'Renamed'}, headers=headers('manager'))
    assert renamed.status_code == 200 and renamed.json()['name'] == 'Renamed'
    [log] = logs(session_factory, 'organization')
    assert (log.action, log.details['before']['name'], log.details['after']['name']) == (
        'ORGANIZATION_UPDATED', 'Org', 'Renamed')


def test_organization_audit_failure_rolls_back(setup, session_factory, monkeypatch):
    client, headers, *_ = setup
    monkeypatch.setattr(routes.organizations, 'record_audit',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('audit down')))
    with pytest.raises(RuntimeError):
        client.post(org_path(), json={'name': 'Ghost'}, headers=headers('admin'))
    assert 'Ghost' not in [o['name'] for o in client.get(org_path()).json()]


def test_audit_log_api_filters_team_resource(setup):
    client, headers, _, teams, *_ = setup
    patch(client, headers, teams['Alpha'], {'name': 'Audited'})
    rows = client.get('/api/v1/admin/audit-logs', params={'resource': 'team', 'resource_id': teams['Alpha']},
                      headers=headers('admin')).json()
    assert [row['action'] for row in rows] == ['TEAM_UPDATED']
