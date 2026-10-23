import pytest
from fastapi.testclient import TestClient

from config.database import get_db
from main import create_app


@pytest.fixture
def client(base_session_factory):
    app = create_app()

    def override_db():
        db = base_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client


pytestmark = pytest.mark.postgres


def register_and_login(client, username):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Smoke-test-password-1",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Smoke-test-password-1"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], registration.json()["user_id"]


def test_smoke_create_list_team_and_add_member(client):
    manager_token, _ = register_and_login(client, "smoke-manager")
    member_token, member_id = register_and_login(client, "smoke-player")
    games = client.get("/api/v1/catalog/games").json()
    game_id = next(game["game_id"] for game in games if game["slug"] == "valorant")
    manager_headers = {"Authorization": f"Bearer {manager_token}"}

    created = client.post(
        "/api/v1/teams",
        headers=manager_headers,
        json={"name": "Smoke Test Team", "tag": "SMK", "game_id": game_id},
    )
    assert created.status_code == 201
    team_id = created.json()["team_id"]

    team_list = client.get("/api/v1/teams")
    assert team_list.status_code == 200
    assert any(team["team_id"] == team_id for team in team_list.json())

    detail = client.get(f"/api/v1/teams/{team_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Smoke Test Team"
    assert any(
        member["role"] == "MANAGER" for member in detail.json()["members"]
    )

    added = client.post(
        f"/api/v1/teams/{team_id}/members",
        headers=manager_headers,
        json={"username": "smoke-player", "role_in_team": "PLAYER"},
    )
    assert added.status_code == 201
    assert added.json()["user_id"] == member_id

    updated_detail = client.get(f"/api/v1/teams/{team_id}")
    assert any(
        member["user_id"] == member_id and member["role"] == "PLAYER"
        for member in updated_detail.json()["members"]
    )


def test_team_writes_require_authentication(client):
    games = client.get("/api/v1/catalog/games").json()
    game_id = next(game["game_id"] for game in games if game["slug"] == "valorant")

    create_response = client.post(
        "/api/v1/teams",
        json={"name": "Anonymous Team", "tag": "ANO", "game_id": game_id},
    )
    assert create_response.status_code == 401

    add_member_response = client.post(
        "/api/v1/teams/1/members",
        json={"username": "unknown-user", "role_in_team": "PLAYER"},
    )
    assert add_member_response.status_code == 401

    assert client.get("/api/v1/teams").status_code == 200
