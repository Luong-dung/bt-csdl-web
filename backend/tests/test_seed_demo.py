from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base, get_db
from core.security import hash_password, verify_password
from main import create_app
from modules.catalog.models import Game
from modules.identity.models import Role, User
from modules.teams.models import Organization, Team, TeamMembership
from seed import seed_reference_data
from seed_demo import ACCOUNTS, TEAM_TAG, demo_database_url, seed_demo_data


PASSWORD = "Demo-test-password-2026"
pytestmark = pytest.mark.postgres


@pytest.fixture
def factory(request):
    if request.config.getoption("--postgres"):
        return request.getfixturevalue("postgres_session_factory")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    request.addfinalizer(engine.dispose)
    return sessionmaker(bind=engine, autoflush=False)


def test_demo_repeat_preserves_passwords_and_unrelated_data(factory):
    with factory.begin() as db:
        seed_reference_data(db)
        viewer_role = db.scalar(select(Role).where(Role.role_name == "VIEWER"))
        db.add(User(username="unrelated", email="unrelated@example.com", role_id=viewer_role.role_id,
                    password_hash=hash_password("Existing-password")))
        added = seed_demo_data(db, PASSWORD)
        assert {k: added[k] for k in ("users", "organizations", "teams", "memberships")} == {
            "users": 6, "organizations": 1, "teams": 1, "memberships": 2,
        }
        hashes = {u.username: u.password_hash for u in db.scalars(select(User))}
    with factory.begin() as db:
        assert all(count == 0 for count in seed_demo_data(db, "Different-demo-password").values())
        assert hashes == {u.username: u.password_hash for u in db.scalars(select(User))}
        assert db.scalar(select(func.count()).select_from(User)) == 7
        assert db.scalar(select(func.count()).select_from(TeamMembership)) == 2
        assert all(verify_password(PASSWORD, db.scalar(select(User).where(User.username == name)).password_hash)
                   for name, _ in ACCOUNTS)


def test_collision_rolls_back_entire_demo_seed(factory):
    with factory.begin() as db:
        seed_reference_data(db)
        viewer = db.scalar(select(Role).where(Role.role_name == "VIEWER"))
        db.add(User(username="demo_player", email="existing@example.com", role_id=viewer.role_id,
                    password_hash=hash_password(PASSWORD)))
    with pytest.raises(ValueError, match="conflicts"):
        with factory.begin() as db:
            seed_demo_data(db, PASSWORD)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Team)) == 0
        assert db.scalar(select(func.count()).select_from(Organization)) == 0


def test_changed_membership_is_not_resurrected(factory):
    with factory.begin() as db:
        seed_demo_data(db, PASSWORD)
        member = db.scalar(select(TeamMembership).join(User).where(User.username == "demo_player"))
        member.status = "ENDED"
        member.left_date = date.today()
    with pytest.raises(ValueError, match="refusing to reset"):
        with factory.begin() as db:
            seed_demo_data(db, PASSWORD)
    with factory() as db:
        member = db.scalar(select(TeamMembership).join(User).where(User.username == "demo_player"))
        assert member.status == "ENDED" and member.left_date == date.today()


@pytest.mark.parametrize("collision", ["email", "team", "other_membership"])
def test_reserved_data_conflicts_are_preserved(factory, collision):
    with factory.begin() as db:
        seed_reference_data(db)
        role = db.scalar(select(Role).where(Role.role_name == "VIEWER"))
        game = db.scalar(select(Game).where(Game.slug == "valorant"))
        if collision == "email":
            db.add(User(username="someone_else", email="demo_admin@example.com",
                        role_id=role.role_id, password_hash=hash_password(PASSWORD)))
        elif collision == "team":
            db.add(Team(name="Existing unrelated team", tag=TEAM_TAG, game_id=game.game_id))
        else:
            seed_demo_data(db, PASSWORD)
            other = Team(name="Another team", tag="OTHER43", game_id=game.game_id)
            db.add(other)
            db.flush()
            member = db.scalar(select(TeamMembership).join(User).where(User.username == "demo_manager"))
            member.team_id = other.team_id
    with factory() as db:
        before = {model: db.scalar(select(func.count()).select_from(model))
                  for model in (User, Organization, Team, TeamMembership)}
    with pytest.raises(ValueError):
        with factory.begin() as db:
            seed_demo_data(db, PASSWORD)
    with factory() as db:
        for model, count in before.items():
            assert db.scalar(select(func.count()).select_from(model)) == count
        if collision == "team":
            assert db.scalar(select(Team.name).where(Team.tag == TEAM_TAG)) == "Existing unrelated team"
        if collision == "other_membership":
            member = db.scalar(select(TeamMembership).join(User).where(User.username == "demo_manager"))
            assert member.team.tag == "OTHER43"


def test_seeded_accounts_login_and_enforce_roles(factory):
    with factory.begin() as db:
        seed_demo_data(db, PASSWORD)
        team_id = db.scalar(select(Team.team_id).where(Team.tag == TEAM_TAG))
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        tokens = {}
        for username, role in ACCOUNTS:
            response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
            assert response.status_code == 200
            assert response.json()["user"]["role"] == role
            tokens[username] = {"Authorization": "Bearer " + response.json()["access_token"]}
        assert client.post("/api/v1/catalog/publishers", json={"name": "Demo extra publisher"},
                           headers=tokens["demo_admin"]).status_code == 201
        assert client.post("/api/v1/catalog/publishers", json={"name": "Denied publisher"},
                           headers=tokens["demo_organizer"]).status_code == 403
        assert client.post(f"/api/v1/teams/{team_id}/members", json={"username": "demo_viewer"},
                           headers=tokens["demo_player"]).status_code == 403
        assert client.post(f"/api/v1/teams/{team_id}/members", json={"username": "demo_free_player"},
                           headers=tokens["demo_manager"]).status_code == 201
        game_id = client.get("/api/v1/catalog/games").json()[0]["game_id"]
        body = {"name": "Demo tournament", "game_id": game_id,
                "start_date": (date.today() + timedelta(days=7)).isoformat()}
        assert client.post("/api/v1/tournaments", json=body, headers=tokens["demo_organizer"]).status_code == 201
        assert client.post("/api/v1/tournaments", json=body, headers=tokens["demo_viewer"]).status_code == 403


@pytest.mark.parametrize("database", ["", "esports_tournament", "postgres", "production"])
def test_demo_rejects_non_demo_database_names(database):
    with pytest.raises(ValueError, match="must end"):
        demo_database_url(database)


def test_demo_rejects_application_database_even_if_named_demo(monkeypatch):
    from config.settings import Settings
    import seed_demo

    monkeypatch.setattr(seed_demo, "get_settings", lambda: Settings(DB_NAME="existing_demo"))
    with pytest.raises(ValueError, match="must differ"):
        demo_database_url("existing_demo")


def test_demo_url_changes_only_database():
    from config.settings import get_settings
    from sqlalchemy.engine import make_url

    original = make_url(get_settings().DATABASE_URL)
    result = demo_database_url("w43_isolated_demo")
    assert result.database == "w43_isolated_demo"
    assert result.set(database=original.database) == original


@pytest.mark.parametrize("password", ["", "short", "x" * 129])
def test_invalid_password_adds_no_data(factory, password):
    with factory() as db:
        before = db.scalar(select(func.count()).select_from(User))
        with pytest.raises(ValueError, match="8 to 128"):
            seed_demo_data(db, password)
        assert db.scalar(select(func.count()).select_from(User)) == before
