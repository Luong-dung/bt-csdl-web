import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base, get_db
from main import create_app
from seed import seed_reference_data


@pytest.fixture
def client():
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

    app = create_app()

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def test_register_login_and_get_current_user(client):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "username": "smoke-user",
            "email": "smoke-user@example.com",
            "password": "Smoke-test-password-1",
            "real_name": "Smoke User",
        },
    )
    assert registration.status_code == 201
    assert registration.json()["user_id"] > 0

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "username": "smoke-user",
            "email": "another@example.com",
            "password": "Smoke-test-password-1",
        },
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "smoke-user", "password": "Smoke-test-password-1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"
    assert login.json()["user"]["role"] == "VIEWER"

    current_user = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert current_user.status_code == 200
    assert current_user.json() == {
        "id": registration.json()["user_id"],
        "username": "smoke-user",
        "email": "smoke-user@example.com",
        "role": "VIEWER",
    }

    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"username": "smoke-user", "password": "incorrect-password"},
    )
    assert invalid_login.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_registration_rejects_invalid_payload(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ab",
            "email": "not-an-email",
            "password": "short",
        },
    )
    assert response.status_code == 422
