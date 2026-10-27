from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from config.database import get_db
from middleware.auth import can_manage_team
from modules.identity.models import RoleAssignment
from modules.teams.models import Organization, TeamMembership
from modules.tournaments.models import Tournament
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('path', [
    '/api/v1/auth/capabilities', '/api/v1/teams/managed',
    '/api/v1/teams/1/capabilities', '/api/v1/tournaments/1/capabilities',
])
def test_capabilities_require_authentication(access, path):
    client, *_ = access
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'Authorization': 'Bearer invalid'}).status_code == 401


@pytest.mark.parametrize('name,catalog,create', [
    ('admin', True, True), ('organizer', False, True),
    ('viewer', False, False), ('manager', False, False),
])
def test_global_role_capabilities(access, name, catalog, create):
    client, headers, *_ = access
    assert client.get('/api/v1/auth/capabilities', headers=headers(name)).json() == {
        'can_manage_catalog': catalog, 'can_create_tournament': create,
    }


@pytest.mark.parametrize('role,scope,scope_id,expected', [
    ('ADMIN', 'GLOBAL', None, (True, True)),
    ('ORGANIZER', 'GLOBAL', None, (False, True)),
    ('ADMIN', 'GLOBAL', 1, (False, False)),
    ('ADMIN', 'TEAM', 1, (False, False)),
    ('ORGANIZER', 'TOURNAMENT', 1, (False, False)),
])
def test_global_assignment_matches_write_policy(access, session_factory, role, scope, scope_id, expected):
    client, headers, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles[role], scope_type=scope, scope_id=scope_id))
    data = client.get('/api/v1/auth/capabilities', headers=headers('viewer')).json()
    assert (data['can_manage_catalog'], data['can_create_tournament']) == expected
    response = client.post('/api/v1/catalog/publishers', headers=headers('viewer'), json={'name': 'Capability publisher'})
    assert response.status_code == (201 if expected[0] else 403)


@pytest.mark.parametrize('kind', ['membership', 'TEAM', 'ORGANIZATION', 'ADMIN_GLOBAL'])
def test_managed_team_picker_and_capabilities_match_writes(access, session_factory, kind):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        if kind == 'membership':
            db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['viewer'], role_in_team='MANAGER'))
        else:
            scope_id = (teams['Alpha'] if kind == 'TEAM' else
                        db.scalar(select(Organization.organization_id)) if kind == 'ORGANIZATION' else None)
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ADMIN' if kind == 'ADMIN_GLOBAL' else 'TEAM_MANAGER'],
                                  scope_type='GLOBAL' if kind == 'ADMIN_GLOBAL' else kind, scope_id=scope_id))
    auth = headers('viewer')
    expected_ids = set(teams.values()) if kind == 'ADMIN_GLOBAL' else {teams['Alpha']}
    response = client.get('/api/v1/teams/managed', headers=auth)
    assert response.status_code == 200
    assert {t['team_id'] for t in response.json()} == expected_ids
    for tid in teams.values():
        capabilities = client.get(f'/api/v1/teams/{tid}/capabilities', headers=auth).json()
        assert capabilities['can_manage_members'] == (tid in expected_ids)
        assert capabilities['can_register_for_tournament'] == (tid in expected_ids)
    # Adding another user is a real mutation, rather than just testing a hint against itself.
    assert client.post(f"/api/v1/teams/{teams['Alpha']}/members", headers=auth,
                       json={'username': 'referee'}).status_code == 201
    if kind != 'ADMIN_GLOBAL':
        assert client.post(f"/api/v1/teams/{teams['Beta']}/members", headers=auth,
                           json={'username': 'organizer'}).status_code == 403


@pytest.mark.parametrize('role,status,left', [
    ('PLAYER', 'ACTIVE', None), ('MANAGER', 'ENDED', date.today()),
    ('MANAGER', 'ACTIVE', date.today()),
])
def test_inactive_membership_does_not_grant_capabilities(access, session_factory, role, status, left):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Alpha'], user_id=users['viewer'], role_in_team=role,
                              status=status, left_date=left))
    assert client.get('/api/v1/teams/managed', headers=headers('viewer')).json() == []
    assert client.get(f"/api/v1/teams/{teams['Alpha']}/capabilities", headers=headers('viewer')).json()['can_manage_members'] is False


def test_picker_pagination_filter_and_no_global_manager_shortcut(access):
    client, headers, *_ = access
    assert client.get('/api/v1/teams/managed', headers=headers('manager')).json() == []
    auth = headers('admin')
    first = client.get('/api/v1/teams/managed?limit=1', headers=auth).json()
    second = client.get('/api/v1/teams/managed?limit=1&offset=1', headers=auth).json()
    assert first[0]['name'] == 'Alpha' and second[0]['name'] == 'Beta'
    assert client.get('/api/v1/teams/managed?game_id=9999', headers=auth).json() == []
    for query in ['limit=101', 'limit=0', 'offset=-1', 'game_id=0', 'game_id=2147483648']:
        assert client.get('/api/v1/teams/managed?' + query, headers=auth).status_code == 422


def test_team_assignment_revocation_and_account_switch(access, session_factory):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['TEAM_MANAGER'], scope_type='TEAM', scope_id=teams['Alpha']))
    path = f"/api/v1/teams/{teams['Alpha']}/capabilities"
    assert client.get(path, headers=headers('viewer')).headers['cache-control'] == 'private, no-store'
    assert client.get(path, headers=headers('viewer')).json()['can_manage_members']
    assert not client.get(path, headers=headers('manager')).json()['can_manage_members']
    with session_factory.begin() as db:
        db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == users['viewer']))
    assert not client.get(path, headers=headers('viewer')).json()['can_manage_members']
    assert client.get('/api/v1/teams/managed', headers=headers('viewer')).json() == []


@pytest.mark.parametrize('kind', ['creator', 'scoped', 'admin', 'outsider'])
@pytest.mark.parametrize('state', ['UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED'])
def test_tournament_capabilities_respect_scope_and_state(access, session_factory, kind, state):
    client, headers, users, _, roles = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.get(Tournament, tid).status = state
        if kind == 'scoped':
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=tid))
    name = {'creator': 'organizer', 'scoped': 'viewer', 'admin': 'admin', 'outsider': 'manager'}[kind]
    data = client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers(name)).json()
    manages = kind != 'outsider'
    editable = manages and state in ('UPCOMING', 'ONGOING')
    assert data['can_manage'] == manages
    assert data['can_update'] == editable
    assert data['can_change_status'] == editable
    assert data['can_review_registrations'] == (manages and state == 'UPCOMING')
    # Unlocked UPCOMING cannot start yet (W44-2-04); the locked case is covered in test_roster_lock.py.
    expected = {'UPCOMING': ['CANCELLED'], 'ONGOING': ['CANCELLED', 'COMPLETED']}.get(state, [])
    assert data['allowed_status_transitions'] == (expected if manages else [])
    if editable and state == 'ONGOING':
        assert data['editable_fields'] == ['description', 'end_date', 'name']
    elif not editable:
        assert data['editable_fields'] == []
    # Permission and lifecycle hints agree with the existing PATCH endpoint.
    response = client.patch(f'/api/v1/tournaments/{tid}', json={'name': 'Capability renamed'}, headers=headers(name))
    assert response.status_code == (403 if not manages else 200 if editable else 409)


def test_scoped_organizer_cannot_manage_other_or_creatorless_tournament(access, session_factory):
    client, headers, users, _, roles = access
    first, second = organizer_tournament(client, headers), organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=first))
        db.get(Tournament, first).created_by = None
    for tid in (first, second):
        assert not client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers('viewer')).json()['can_manage']
    assert client.get(f'/api/v1/tournaments/{first}/capabilities', headers=headers('admin')).json()['can_manage']


@pytest.mark.parametrize('resource', ['teams', 'tournaments'])
def test_missing_and_invalid_resource(access, resource):
    client, headers, *_ = access
    for value, status in [('999999', 404), ('0', 422), ('2147483648', 422), ('abc', 422)]:
        assert client.get(f'/api/v1/{resource}/{value}/capabilities', headers=headers('viewer')).status_code == status


@pytest.mark.parametrize('team_first', [True, False])
def test_managed_route_survives_router_include_order(access, session_factory, team_first):
    from routes.capabilities import router as capability_router
    from routes.team import router as team_router
    _, headers, _, teams, _ = access
    app = FastAPI()
    routers = [team_router, capability_router] if team_first else [capability_router, team_router]
    for router in routers:
        app.include_router(router)
    def override_db():
        with session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get('/api/v1/teams/managed', headers=headers('admin'))
    assert response.status_code == 200
    assert {row['team_id'] for row in response.json()} == set(teams.values())


@pytest.mark.parametrize('url,auth,expected', [
    ('/api/v1/auth/capabilities', None, 401),
    ('/api/v1/teams/managed', None, 401),
    ('/api/v1/teams/999999/capabilities', 'viewer', 404),
    ('/api/v1/tournaments/999999/capabilities', 'viewer', 404),
    ('/api/v1/teams/0/capabilities', 'viewer', 422),
    ('/api/v1/tournaments/2147483648/capabilities', 'viewer', 422),
    ('/api/v1/teams/managed?limit=0', 'viewer', 422),
    ('/api/v1/auth/capabilities', 'viewer', 200),
    ('/api/v1/teams/managed', 'admin', 200),
])
def test_no_store_on_success_and_handled_errors(access, url, auth, expected):
    client, headers, *_ = access
    response = client.get(url, headers=headers(auth) if auth else {})
    assert response.status_code == expected
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'cache-control' not in client.get('/api/v1/catalog/games').headers


def test_no_store_on_invalid_token_and_redirect(access):
    client, headers, *_ = access
    bad = client.get('/api/v1/auth/capabilities', headers={'Authorization': 'Bearer invalid'})
    assert bad.status_code == 401 and bad.headers['cache-control'] == 'private, no-store'
    redirect = client.get('/api/v1/teams/managed/', headers=headers('admin'), follow_redirects=False)
    assert redirect.status_code == 307 and redirect.headers['cache-control'] == 'private, no-store'


@pytest.mark.parametrize('invalid', ['0', '-1', 'abc', '2147483648'])
def test_shared_id_validation_on_team_reads_and_mutations(access, invalid):
    client, headers, _, teams, _ = access
    auth = headers('admin')
    for method, url, payload in [
        ('GET', f'/api/v1/teams/{invalid}', None),
        ('GET', f'/api/v1/teams/{invalid}/capabilities', None),
        ('GET', f'/api/v1/teams/{invalid}/members', None),
        ('POST', f'/api/v1/teams/{invalid}/members', {'username': 'viewer'}),
        ('PATCH', f'/api/v1/teams/{invalid}/members/1', {'role_in_team': 'PLAYER'}),
        ('POST', f'/api/v1/teams/{invalid}/members/1/end', None),
        ('PATCH', f"/api/v1/teams/{teams['Alpha']}/members/{invalid}", {'role_in_team': 'PLAYER'}),
        ('POST', f"/api/v1/teams/{teams['Alpha']}/members/{invalid}/end", None),
    ]:
        response = client.request(method, url, headers=auth, json=payload)
        assert response.status_code == 422, (method, url, response.text)


def test_team_ids_keep_valid_missing_as_404_and_bound_game_ids(access):
    client, headers, *_ = access
    for suffix in ['', '/members', '/capabilities']:
        assert client.get('/api/v1/teams/2147483647' + suffix, headers=headers('admin')).status_code == 404
    assert client.get('/api/v1/teams?game_id=2147483648').status_code == 422
    assert client.post('/api/v1/teams', headers=headers('admin'), json={
        'name': 'Invalid game team', 'tag': 'BAD', 'game_id': 2147483648,
    }).status_code == 422


@pytest.mark.parametrize('name', ['admin', 'viewer'])
def test_team_capability_uses_one_team_query(access, session_factory, name):
    client, headers, _, teams, _ = access
    statements = []
    def track(connection, cursor, statement, parameters, context, executemany):
        if 'FROM teams' in statement:
            statements.append(statement)
    engine = session_factory.kw['bind']
    # PostgreSQL fixtures bind a Connection; SQLite fixtures bind an Engine.
    target = engine.engine if hasattr(engine, 'engine') else engine
    event.listen(target, 'before_cursor_execute', track)
    try:
        response = client.get(f"/api/v1/teams/{teams['Alpha']}/capabilities", headers=headers(name))
        assert response.status_code == 200
        assert response.json()['can_manage_members'] == (name == 'admin')
        assert len(statements) == 1
    finally:
        event.remove(target, 'before_cursor_execute', track)


def test_admin_checker_preserves_shortcut_and_routes_validate_existence(access, session_factory):
    client, headers, users, *_ = access
    with session_factory() as db:
        from modules.identity.models import User
        assert can_manage_team(db, 999999, db.get(User, users['admin']))
    assert client.get('/api/v1/teams/999999', headers=headers('admin')).status_code == 404
