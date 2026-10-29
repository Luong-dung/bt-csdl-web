from datetime import date, timedelta

import pytest
from sqlalchemy import select

from core.security import create_access_token
from middleware.auth import has_role
from modules.identity.models import Role, RoleAssignment, User
from modules.teams.models import Organization, Team, TeamMembership
from modules.tournaments.models import Tournament
from test_catalog_api import session_factory, make_client


@pytest.fixture
def access(session_factory):
    with session_factory.begin() as db:
        roles = {r.role_name: r.role_id for r in db.scalars(select(Role))}
        for name, role in [("admin", "ADMIN"), ("viewer", "VIEWER"), ("organizer", "ORGANIZER"),
                           ("manager", "TEAM_MANAGER"), ("referee", "REFEREE")]:
            db.add(User(username=name, email=f"{name}@example.com", password_hash="unused", role_id=roles[role]))
        db.add(Organization(name="Org"))
        db.flush()
        org = db.scalar(select(Organization))
        db.add_all([Team(name="Alpha", tag="A", game_id=1, organization_id=org.organization_id),
                    Team(name="Beta", tag="B", game_id=1)])
        db.flush()
        users = {u.username: u.user_id for u in db.scalars(select(User))}
        teams = {t.name: t.team_id for t in db.scalars(select(Team))}
    client = make_client(session_factory, logged_in=False)
    def headers(name):
        return {"Authorization": "Bearer " + create_access_token({"sub": str(users[name])})}
    return client, headers, users, teams, roles


pytestmark = pytest.mark.postgres


WRITES = [
    (method, f"/api/v1/catalog/{resource}{suffix}", payload)
    for resource, payload in [("publishers", {"name": "New publisher"}),
                              ("games", {"name": "New game", "slug": "new-game", "publisher_id": 1}),
                              ("areas", {"name": "New area", "code": "NEW"})]
    for method, suffix in [("POST", ""), ("PATCH", "/1"), ("DELETE", "/1")]
]


@pytest.mark.parametrize("method,path,payload", WRITES)
def test_catalog_denies_anonymous_and_viewer(access, method, path, payload):
    client, headers, *_ = access
    assert client.request(method, path, json=payload).status_code == 401
    assert client.request(method, path, json=payload, headers=headers("viewer")).status_code == 403


@pytest.mark.parametrize("sub", [None, "", "abc", "-1", "0", "1.2", "99999", "2147483648", "9" * 5000])
def test_invalid_subject_returns_401(access, sub):
    client, *_ = access
    token = create_access_token({} if sub is None else {"sub": sub})
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_bad_and_expired_token(access):
    client, *_ = access
    import jwt
    from config.settings import get_settings
    expired = jwt.encode({"sub": "1", "exp": 1}, get_settings().JWT_SECRET, algorithm="HS256")
    for token in ["invalid", expired]:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_global_and_scoped_assignment(access, session_factory):
    client, headers, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ADMIN"], scope_type="TOURNAMENT", scope_id=1))
    payload = {"name": "Scoped denied"}
    assert client.post("/api/v1/catalog/publishers", json=payload, headers=headers("viewer")).status_code == 403
    with session_factory.begin() as db:
        user = db.get(User, users["viewer"])
        assert has_role(user, "ADMIN", scope_type="TOURNAMENT", scope_id=1)
        assert not has_role(user, "ADMIN", scope_type="TOURNAMENT", scope_id=2)
        assert not has_role(user, "REFEREE", scope_type="TOURNAMENT", scope_id=1)
        db.add(RoleAssignment(user_id=user.user_id, role_id=roles["ADMIN"], scope_type="GLOBAL"))
    assert client.post("/api/v1/catalog/publishers", json=payload, headers=headers("viewer")).status_code == 201


def test_create_tournament_roles(access):
    client, headers, *_ = access
    payload = {"name": "Tournament", "game_id": 1, "start_date": str(date.today() + timedelta(days=7))}
    assert client.post("/api/v1/tournaments", json=payload).status_code == 401
    for name in ["viewer", "manager", "referee"]:
        assert client.post("/api/v1/tournaments", json=payload, headers=headers(name)).status_code == 403
    for name in ["admin", "organizer"]:
        assert client.post("/api/v1/tournaments", json=payload, headers=headers(name)).status_code == 201


@pytest.mark.parametrize("kind", ["membership", "TEAM", "ORGANIZATION"])
def test_manager_only_controls_own_team(access, session_factory, kind):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        if kind == "membership":
            db.add(TeamMembership(team_id=teams["Alpha"], user_id=users["manager"], role_in_team="MANAGER"))
        else:
            scope_id = teams["Alpha"] if kind == "TEAM" else db.scalar(select(Organization.organization_id))
            db.add(RoleAssignment(user_id=users["manager"], role_id=roles["TEAM_MANAGER"], scope_type=kind, scope_id=scope_id))
    payload = {"username": "viewer"}
    assert client.post(f"/api/v1/teams/{teams['Beta']}/members", json=payload, headers=headers("manager")).status_code == 403
    assert client.post(f"/api/v1/teams/{teams['Alpha']}/members", json=payload, headers=headers("manager")).status_code == 201


@pytest.mark.parametrize("status,role,left", [("LEFT", "MANAGER", date.today()),
                                             ("ACTIVE", "PLAYER", None),
                                             ("ACTIVE", "MANAGER", date.today())])
def test_inactive_or_player_cannot_manage(access, session_factory, status, role, left):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams["Alpha"], user_id=users["manager"], role_in_team=role,
                              status=status, left_date=left))
    assert client.post(f"/api/v1/teams/{teams['Alpha']}/members", json={"username": "viewer"},
                       headers=headers("manager")).status_code == 403


def test_team_auth_admin_and_global_manager(access):
    client, headers, _, teams, _ = access
    path = f"/api/v1/teams/{teams['Alpha']}/members"
    payload = {"username": "viewer"}
    assert client.post(path, json=payload).status_code == 401
    assert client.post(path, json=payload, headers=headers("manager")).status_code == 403
    assert client.post(path, json=payload, headers=headers("admin")).status_code == 201


def test_public_reads_and_authenticated_team_creation(access):
    client, headers, *_ = access
    for path in ["/api/v1/catalog/games", "/api/v1/teams", "/api/v1/tournaments"]:
        assert client.get(path).status_code == 200
    payload = {"name": "New team", "tag": "NEW", "game_id": 1}
    assert client.post("/api/v1/teams", json=payload).status_code == 401
    assert client.post("/api/v1/teams", json=payload, headers=headers("viewer")).status_code == 201


@pytest.mark.parametrize("resource,payload,update,key", [
    ("publishers", {"name": "JWT Publisher"}, {"name": "Renamed"}, "publisher_id"),
    ("games", {"name": "JWT Game", "slug": "jwt-game", "publisher_id": 1}, {"name": "Renamed"}, "game_id"),
    ("areas", {"name": "JWT Area", "code": "JWT"}, {"name": "Renamed"}, "area_id"),
])
def test_admin_catalog_crud_with_real_jwt(access, resource, payload, update, key):
    client, headers, *_ = access
    path = f"/api/v1/catalog/{resource}"
    created = client.post(path, json=payload, headers=headers("admin"))
    assert created.status_code == 201
    path += f"/{created.json()[key]}"
    assert client.patch(path, json=update, headers=headers("admin")).status_code == 200
    assert client.delete(path, headers=headers("admin")).status_code == 204
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("name", ["viewer", "organizer", "manager", "referee"])
def test_other_roles_cannot_write_catalog(access, name):
    client, headers, *_ = access
    assert client.post("/api/v1/catalog/publishers", json={"name": "Forbidden"},
                       headers=headers(name)).status_code == 403


@pytest.mark.parametrize("scope,scope_id", [("GLOBAL", 1), ("TEAM", None), ("UNKNOWN", 1)])
def test_malformed_admin_assignment_does_not_grant_global_access(access, session_factory, scope, scope_id):
    client, headers, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ADMIN"], scope_type=scope, scope_id=scope_id))
    assert client.post("/api/v1/catalog/publishers", json={"name": "Forbidden"},
                       headers=headers("viewer")).status_code == 403


def test_scoped_organizer_cannot_create_new_tournament(access, session_factory):
    client, headers, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ORGANIZER"], scope_type="TOURNAMENT", scope_id=1))
    payload = {"name": "New tournament", "game_id": 1, "start_date": str(date.today() + timedelta(days=7))}
    assert client.post("/api/v1/tournaments", json=payload, headers=headers("viewer")).status_code == 403
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ORGANIZER"], scope_type="GLOBAL"))
    assert client.post("/api/v1/tournaments", json=payload, headers=headers("viewer")).status_code == 201


def organizer_tournament(client, headers):
    payload = {"name": "Organizer cup", "game_id": 1, "start_date": str(date.today() + timedelta(days=7))}
    created = client.post("/api/v1/tournaments", json=payload, headers=headers("organizer"))
    assert created.status_code == 201
    return created.json()["tournament_id"]


def tournament_writes(client, tournament_id, auth):
    path = f"/api/v1/tournaments/{tournament_id}"
    return (client.patch(path, json={"description": "Updated"}, headers=auth).status_code,
            client.post(path + "/status", json={"status": "CANCELLED"}, headers=auth).status_code)


def test_tournament_records_creator(access):
    client, headers, users, *_ = access
    tournament_id = organizer_tournament(client, headers)
    assert client.get(f"/api/v1/tournaments/{tournament_id}").json()["created_by"] == users["organizer"]


def test_creator_organizer_can_manage_tournament(access):
    client, headers, *_ = access
    assert tournament_writes(client, organizer_tournament(client, headers), headers("organizer")) == (200, 200)


def test_admin_can_manage_any_tournament(access):
    client, headers, *_ = access
    assert tournament_writes(client, organizer_tournament(client, headers), headers("admin")) == (200, 200)


@pytest.mark.parametrize("name", ["viewer", "manager", "referee", "other_organizer"])
def test_other_users_cannot_manage_tournament(access, session_factory, name):
    client, headers, users, _, roles = access
    if name == "other_organizer":
        with session_factory.begin() as db:
            user = User(username=name, email=f"{name}@example.com", password_hash="unused", role_id=roles["ORGANIZER"])
            db.add(user)
            db.flush()
            users[name] = user.user_id
    tournament_id = organizer_tournament(client, headers)
    assert tournament_writes(client, tournament_id, {}) == (401, 401)
    assert tournament_writes(client, tournament_id, headers(name)) == (403, 403)
    assert client.get(f"/api/v1/tournaments/{tournament_id}").json()["status"] == "UPCOMING"


def test_scoped_organizer_manages_only_assigned_tournament(access, session_factory):
    client, headers, users, _, roles = access
    assigned, other = organizer_tournament(client, headers), organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ORGANIZER"], scope_type="TOURNAMENT",
                              scope_id=assigned))
    assert tournament_writes(client, assigned, headers("viewer")) == (200, 200)
    assert tournament_writes(client, other, headers("viewer")) == (403, 403)


def test_creator_without_organizer_role_loses_access(access, session_factory):
    client, headers, users, _, roles = access
    tournament_id = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.get(User, users["organizer"]).role_id = roles["VIEWER"]
    assert tournament_writes(client, tournament_id, headers("organizer")) == (403, 403)


def test_tournament_without_creator_is_admin_only(access, session_factory):
    client, headers, users, _, roles = access
    tournament_id = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.get(Tournament, tournament_id).created_by = None
        db.add(RoleAssignment(user_id=users["viewer"], role_id=roles["ORGANIZER"], scope_type="TOURNAMENT",
                              scope_id=tournament_id))
    path = f"/api/v1/tournaments/{tournament_id}"
    before = client.get(path).json()
    for name in ["organizer", "viewer"]:
        assert tournament_writes(client, tournament_id, headers(name)) == (403, 403)
    assert client.get(path).json() == before
    assert tournament_writes(client, tournament_id, headers("admin")) == (200, 200)


def test_revocation_applies_to_existing_token(access, session_factory):
    client, headers, users, _, roles = access
    token_headers = headers("viewer")
    with session_factory.begin() as db:
        assignment = RoleAssignment(user_id=users["viewer"], role_id=roles["ADMIN"], scope_type="GLOBAL")
        db.add(assignment)
        db.flush()
        assignment_id = assignment.assignment_id
    assert client.post("/api/v1/catalog/publishers", json={"name": "Allowed"}, headers=token_headers).status_code == 201
    with session_factory.begin() as db:
        db.delete(db.get(RoleAssignment, assignment_id))
    assert client.post("/api/v1/catalog/publishers", json={"name": "Denied"}, headers=token_headers).status_code == 403


def test_registration_cannot_request_admin_role(access, session_factory):
    client, *_ = access
    assert client.post("/api/v1/auth/register", json={"username": "newviewer", "email": "newviewer@example.com",
                       "password": "test-password", "role_id": 1, "role": "ADMIN"}).status_code == 201
    with session_factory() as db:
        user = db.scalar(select(User).where(User.username == "newviewer"))
        assert user.role.role_name == "VIEWER"
        assert user.assignments == []


@pytest.mark.parametrize("kind", ["membership", "TEAM", "ORGANIZATION"])
def test_manager_can_change_role_and_end_membership(access, session_factory, kind):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        if kind == "membership":
            db.add(TeamMembership(team_id=teams["Alpha"], user_id=users["manager"], role_in_team="MANAGER"))
        else:
            scope_id = teams["Alpha"] if kind == "TEAM" else db.scalar(select(Organization.organization_id))
            db.add(RoleAssignment(user_id=users["manager"], role_id=roles["TEAM_MANAGER"], scope_type=kind, scope_id=scope_id))
    base = f"/api/v1/teams/{teams['Alpha']}/members"
    added = client.post(base, json={"username": "viewer"}, headers=headers("manager"))
    assert added.status_code == 201
    member = f"{base}/{added.json()['membership_id']}"
    assert client.patch(member, json={"role_in_team": "COACH"}, headers=headers("referee")).status_code == 403
    assert client.patch(member, json={"role_in_team": "COACH"}, headers=headers("manager")).status_code == 200
    assert client.post(f"{member}/end", headers=headers("referee")).status_code == 403
    assert client.post(f"{member}/end", headers=headers("manager")).status_code == 200
