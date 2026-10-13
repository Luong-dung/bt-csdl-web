from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base, get_db
from main import create_app
from middleware.auth import get_current_user
from modules.teams.models import Team
from modules.tournaments.models import Tournament
from seed import seed_reference_data


@pytest.fixture
def session_factory(request):
    if request.config.getoption("--postgres"):
        yield request.getfixturevalue("postgres_session_factory")
        return
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory.begin() as db:
        seed_reference_data(db)
    yield factory
    engine.dispose()


def make_client(session_factory, logged_in=True):
    app = create_app()

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    if logged_in:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=SimpleNamespace(role_name="ADMIN"), assignments=[])
    return TestClient(app)


@pytest.fixture
def client(session_factory):
    return make_client(session_factory)


def ids(client, path, key, field="name"):
    return {item[field]: item[key] for item in client.get(f"/api/v1/catalog/{path}").json()}


def test_list_and_filter(client):
    publishers = ids(client, "publishers", "publisher_id")
    assert set(publishers) == {"Riot Games", "Valve"}

    games = client.get("/api/v1/catalog/games", params={"publisher_id": publishers["Valve"]}).json()
    assert [game["slug"] for game in games] == ["counter-strike-2", "dota-2"]

    areas = ids(client, "areas", "area_id", "code")
    children = client.get("/api/v1/catalog/areas", params={"parent_id": areas["VN"]}).json()
    assert [area["code"] for area in children] == ["VN-HCM"]

    assert client.get("/api/v1/catalog/games/9999").status_code == 404


def test_writes_require_login(session_factory):
    anonymous = make_client(session_factory, logged_in=False)
    assert anonymous.get("/api/v1/catalog/games").status_code == 200
    assert anonymous.post("/api/v1/catalog/publishers", json={"name": "Blizzard"}).status_code == 401
    assert anonymous.delete("/api/v1/catalog/games/1").status_code == 401


def test_publisher_crud(client):
    created = client.post("/api/v1/catalog/publishers", json={"name": "  Blizzard  "})
    assert created.status_code == 201
    publisher_id = created.json()["publisher_id"]
    assert created.json()["name"] == "Blizzard"

    assert client.post("/api/v1/catalog/publishers", json={"name": "Valve"}).status_code == 409
    assert client.patch(f"/api/v1/catalog/publishers/{publisher_id}", json={"name": "Valve"}).status_code == 409
    assert client.patch(f"/api/v1/catalog/publishers/{publisher_id}", json={"name": None}).status_code == 422

    renamed = client.patch(f"/api/v1/catalog/publishers/{publisher_id}", json={"name": "Blizzard Entertainment"})
    assert renamed.json()["name"] == "Blizzard Entertainment"

    assert client.delete(f"/api/v1/catalog/publishers/{publisher_id}").status_code == 204
    assert client.get(f"/api/v1/catalog/publishers/{publisher_id}").status_code == 404


def test_publisher_with_games_cannot_be_deleted(client):
    riot = ids(client, "publishers", "publisher_id")["Riot Games"]
    assert client.delete(f"/api/v1/catalog/publishers/{riot}").status_code == 409


@pytest.mark.parametrize("payload", [
    {"name": "Overwatch 2", "slug": "Overwatch 2", "publisher_id": 1},
    {"name": "Overwatch 2", "slug": "overwatch-2-", "publisher_id": 1},
    {"name": "", "slug": "overwatch-2", "publisher_id": 1},
    {"name": "Overwatch 2", "slug": "overwatch-2", "publisher_id": 0},
    {"name": "Overwatch 2", "slug": "overwatch-2", "publisher_id": 1, "extra": True},
])
def test_game_payload_validation(client, payload):
    assert client.post("/api/v1/catalog/games", json=payload).status_code == 422


def test_game_crud(client):
    publishers = ids(client, "publishers", "publisher_id")
    payload = {"name": "Teamfight Tactics", "slug": "teamfight-tactics", "publisher_id": publishers["Riot Games"]}
    created = client.post("/api/v1/catalog/games", json=payload)
    assert created.status_code == 201
    game_id = created.json()["game_id"]

    assert client.post("/api/v1/catalog/games", json={**payload, "name": "TFT"}).status_code == 409
    assert client.post("/api/v1/catalog/games", json={**payload, "slug": "tft"}).status_code == 409
    assert client.post("/api/v1/catalog/games", json={**payload, "name": "X", "slug": "x",
                                                      "publisher_id": 9999}).status_code == 422
    assert client.patch(f"/api/v1/catalog/games/{game_id}", json={"slug": "valorant"}).status_code == 409

    moved = client.patch(f"/api/v1/catalog/games/{game_id}", json={"publisher_id": publishers["Valve"]})
    assert moved.status_code == 200
    assert moved.json()["publisher_id"] == publishers["Valve"]
    assert moved.json()["slug"] == "teamfight-tactics"

    assert client.delete(f"/api/v1/catalog/games/{game_id}").status_code == 204
    assert client.delete(f"/api/v1/catalog/games/{game_id}").status_code == 404


def test_game_in_use_cannot_be_deleted(client, session_factory):
    games = ids(client, "games", "game_id", "slug")
    with session_factory.begin() as db:
        db.add(Team(name="Saigon Buffalo", tag="SGB", game_id=games["league-of-legends"]))
        db.add(Tournament(name="VCS", game_id=games["valorant"], start_date=date(2026, 10, 1)))
    team_used = client.delete(f"/api/v1/catalog/games/{games['league-of-legends']}")
    assert team_used.status_code == 409
    assert "đội tuyển" in team_used.json()["detail"]
    tournament_used = client.delete(f"/api/v1/catalog/games/{games['valorant']}")
    assert tournament_used.status_code == 409
    assert "giải đấu" in tournament_used.json()["detail"]
    assert client.delete(f"/api/v1/catalog/games/{games['dota-2']}").status_code == 204


def test_area_crud_and_hierarchy(client):
    areas = ids(client, "areas", "area_id", "code")
    created = client.post("/api/v1/catalog/areas", json={"name": "Ha Noi", "code": "VN-HN", "parent_id": areas["VN"]})
    assert created.status_code == 201
    hanoi = created.json()["area_id"]

    assert client.post("/api/v1/catalog/areas", json={"name": "Dup", "code": "VN"}).status_code == 409
    assert client.post("/api/v1/catalog/areas", json={"name": "Lower", "code": "vn-x"}).status_code == 422
    assert client.post("/api/v1/catalog/areas", json={"name": "Orphan", "code": "XX",
                                                      "parent_id": 9999}).status_code == 422

    # A node cannot become its own parent or a child of its descendant.
    assert client.patch(f"/api/v1/catalog/areas/{areas['VN']}", json={"parent_id": areas["VN"]}).status_code == 422
    assert client.patch(f"/api/v1/catalog/areas/{areas['APAC']}", json={"parent_id": hanoi}).status_code == 422

    detached = client.patch(f"/api/v1/catalog/areas/{hanoi}", json={"parent_id": None})
    assert detached.status_code == 200
    assert detached.json()["parent_id"] is None
    assert client.patch(f"/api/v1/catalog/areas/{hanoi}", json={"code": None}).status_code == 422

    assert client.delete(f"/api/v1/catalog/areas/{areas['VN']}").status_code == 409
    assert client.delete(f"/api/v1/catalog/areas/{areas['VN-HCM']}").status_code == 204
    assert client.delete(f"/api/v1/catalog/areas/{areas['VN']}").status_code == 204


def test_area_used_by_tournament_cannot_be_deleted(client, session_factory):
    areas = ids(client, "areas", "area_id", "code")
    games = ids(client, "games", "game_id", "slug")
    with session_factory.begin() as db:
        db.add(Tournament(name="VCS", game_id=games["valorant"], area_id=areas["VN-HCM"],
                          start_date=date(2026, 10, 1)))
    response = client.delete(f"/api/v1/catalog/areas/{areas['VN-HCM']}")
    assert response.status_code == 409
    assert "giải đấu" in response.json()["detail"]
