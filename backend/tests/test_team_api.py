from datetime import date, timedelta

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from config.database import get_db
from main import create_app
from middleware.auth import get_current_user
from modules.catalog.models import Game
from modules.identity.models import AuditLog, Role, User
from modules.teams.models import TeamMembership

USERS = {"alice": "PLAYER", "bob": "PLAYER", "carol": "PLAYER", "dave": "PLAYER", "root": "ADMIN"}


@pytest.fixture
def session_factory(base_session_factory):
    factory = base_session_factory
    with factory.begin() as db:
        roles = {role.role_name: role.role_id for role in db.scalars(select(Role))}
        for username, role in USERS.items():
            db.add(User(username=username, email=f"{username}@example.com",
                        password_hash="x", role_id=roles[role]))
    yield factory


pytestmark = pytest.mark.postgres


@pytest.fixture
def client(session_factory):
    app = create_app()

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_user(x_test_user: str | None = Header(default=None)):
        if x_test_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        db = session_factory()
        user = db.scalar(select(User).where(User.username == x_test_user))
        user.role  # load before the session closes
        for assignment in user.assignments:
            assignment.role
        db.close()
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def as_user(username):
    return {"X-Test-User": username}


@pytest.fixture
def game_id(session_factory):
    with session_factory() as db:
        return db.scalar(select(Game.game_id).where(Game.slug == "valorant"))


@pytest.fixture
def team(client, game_id):
    response = client.post("/api/v1/teams", json={"name": "Team Flash", "tag": "flash", "game_id": game_id},
                           headers=as_user("alice"))
    assert response.status_code == 201
    return response.json()


def add(client, team_id, username, actor="alice", role="PLAYER"):
    return client.post(f"/api/v1/teams/{team_id}/members", json={"username": username, "role_in_team": role},
                       headers=as_user(actor))


def test_create_team_makes_creator_manager(client, team):
    assert team["tag"] == "FLASH"
    detail = client.get(f"/api/v1/teams/{team['team_id']}").json()
    assert [(m["username"], m["role"], m["status"]) for m in detail["members"]] == [("alice", "MANAGER", "ACTIVE")]


def test_create_team_validation(client, team, game_id):
    payload = {"name": "Other", "tag": "OTH", "game_id": game_id}
    assert client.post("/api/v1/teams", json=payload).status_code == 401
    assert client.post("/api/v1/teams", json={**payload, "game_id": 9999}, headers=as_user("bob")).status_code == 422
    assert client.post("/api/v1/teams", json={**payload, "tag": "O T"}, headers=as_user("bob")).status_code == 422
    assert client.post("/api/v1/teams", json={**payload, "tag": "Flash"}, headers=as_user("bob")).status_code == 409
    # alice already manages Team Flash, so she cannot found a second team.
    assert client.post("/api/v1/teams", json=payload, headers=as_user("alice")).status_code == 409
    assert client.post("/api/v1/teams", json=payload, headers=as_user("bob")).status_code == 201

    listed = client.get("/api/v1/teams", params={"game_id": game_id}).json()
    assert [t["tag"] for t in listed] == ["OTH", "FLASH"]


def test_only_manager_or_admin_can_manage_members(client, team):
    team_id = team["team_id"]
    assert add(client, team_id, "bob").status_code == 201
    # A regular member and an outsider are both rejected.
    assert add(client, team_id, "carol", actor="bob").status_code == 403
    assert add(client, team_id, "carol", actor="dave").status_code == 403
    assert add(client, team_id, "carol", actor="root").status_code == 201

    bob = client.get(f"/api/v1/teams/{team_id}/members").json()[1]
    path = f"/api/v1/teams/{team_id}/members/{bob['membership_id']}"
    assert client.patch(path, json={"role_in_team": "COACH"}, headers=as_user("carol")).status_code == 403
    assert client.post(f"{path}/end", headers=as_user("carol")).status_code == 403
    assert client.patch(path, json={"role_in_team": "COACH"}).status_code == 401


def test_member_validation(client, team):
    team_id = team["team_id"]
    assert add(client, team_id, "nobody").status_code == 404
    assert add(client, team_id, "bob", role="CAPTAIN").status_code == 422
    assert add(client, 9999, "bob").status_code == 404
    assert add(client, team_id, "bob").status_code == 201
    assert add(client, team_id, "bob").status_code == 409


def test_member_cannot_be_active_in_two_teams(client, team, game_id):
    assert add(client, team["team_id"], "bob").status_code == 201
    other = client.post("/api/v1/teams", json={"name": "Team Secret", "tag": "TS", "game_id": game_id},
                        headers=as_user("carol")).json()
    response = add(client, other["team_id"], "bob", actor="carol")
    assert response.status_code == 409
    assert "Team Flash" in response.json()["detail"]


def test_change_role(client, team):
    team_id = team["team_id"]
    bob = add(client, team_id, "bob").json()
    path = f"/api/v1/teams/{team_id}/members/{bob['membership_id']}"
    promoted = client.patch(path, json={"role_in_team": "MANAGER"}, headers=as_user("alice"))
    assert promoted.json()["role"] == "MANAGER"
    # bob is now a manager and can manage the team himself.
    assert add(client, team_id, "carol", actor="bob").status_code == 201
    assert client.patch(path, json={"role_in_team": "CAPTAIN"}, headers=as_user("alice")).status_code == 422
    assert client.patch(f"/api/v1/teams/{team_id}/members/9999", json={"role_in_team": "COACH"},
                        headers=as_user("alice")).status_code == 404


def test_last_manager_is_protected(client, team):
    team_id = team["team_id"]
    alice = client.get(f"/api/v1/teams/{team_id}/members").json()[0]
    path = f"/api/v1/teams/{team_id}/members/{alice['membership_id']}"
    assert client.patch(path, json={"role_in_team": "PLAYER"}, headers=as_user("alice")).status_code == 409
    assert client.post(f"{path}/end", headers=as_user("alice")).status_code == 409

    bob = add(client, team_id, "bob", role="MANAGER").json()
    assert client.post(f"{path}/end", headers=as_user("alice")).status_code == 200
    bob_path = f"/api/v1/teams/{team_id}/members/{bob['membership_id']}"
    assert client.post(f"{bob_path}/end", headers=as_user("bob")).status_code == 409


def test_end_membership_keeps_history_and_allows_transfer(client, team, game_id, session_factory):
    team_id = team["team_id"]
    bob = add(client, team_id, "bob").json()
    path = f"/api/v1/teams/{team_id}/members/{bob['membership_id']}"

    ended = client.post(f"{path}/end", headers=as_user("alice"))
    assert ended.status_code == 200
    assert ended.json()["status"] == "ENDED"
    assert ended.json()["left_date"] == date.today().isoformat()
    assert client.post(f"{path}/end", headers=as_user("alice")).status_code == 409
    assert client.patch(path, json={"role_in_team": "COACH"}, headers=as_user("alice")).status_code == 409

    assert [m["username"] for m in client.get(f"/api/v1/teams/{team_id}/members").json()] == ["alice"]
    history = client.get(f"/api/v1/teams/{team_id}/members", params={"include_history": True}).json()
    assert [(m["username"], m["status"]) for m in history] == [("alice", "ACTIVE"), ("bob", "ENDED")]

    # Same-day rejoin collides with the (team, user, joined_date) unique key.
    assert add(client, team_id, "bob").status_code == 409
    # bob is free to join another team once his membership has ended.
    other = client.post("/api/v1/teams", json={"name": "Team Secret", "tag": "TS", "game_id": game_id},
                        headers=as_user("carol")).json()
    assert add(client, other["team_id"], "bob", actor="carol").status_code == 201

    # Back-date the old membership: rejoining on a later day works.
    with session_factory.begin() as db:
        db.get(TeamMembership, bob["membership_id"]).joined_date = date.today() - timedelta(days=30)
        moved = db.scalar(select(TeamMembership).where(
            TeamMembership.team_id == other["team_id"], TeamMembership.role_in_team == "PLAYER"))
        moved.status, moved.left_date = "ENDED", date.today()
    assert add(client, team_id, "bob").status_code == 201


def test_member_can_leave_on_their_own(client, team):
    team_id = team["team_id"]
    bob = add(client, team_id, "bob").json()
    left = client.post(f"/api/v1/teams/{team_id}/members/{bob['membership_id']}/end", headers=as_user("bob"))
    assert left.status_code == 200
    assert left.json()["status"] == "ENDED"


def test_membership_changes_are_audited(client, team, session_factory):
    team_id = team["team_id"]
    bob = add(client, team_id, "bob").json()
    path = f"/api/v1/teams/{team_id}/members/{bob['membership_id']}"
    client.patch(path, json={"role_in_team": "COACH"}, headers=as_user("alice"))
    client.post(f"{path}/end", headers=as_user("alice"))

    with session_factory() as db:
        logs = db.scalars(select(AuditLog).order_by(AuditLog.log_id)).all()
    assert [log.action for log in logs] == [
        "TEAM_MEMBER_ADDED", "TEAM_MEMBER_ADDED", "TEAM_MEMBER_ROLE_CHANGED", "TEAM_MEMBER_ENDED",
    ]
    assert logs[2].details["old_role"] == "PLAYER"
    assert logs[2].details["new_role"] == "COACH"
    assert logs[3].details["member_user_id"] == bob["user_id"]
