from datetime import date, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog
from modules.tournaments.models import Tournament
from test_catalog_api import session_factory
from test_permissions import access

URL = "/api/v1/tournaments"
pytestmark = pytest.mark.postgres


def create(client, auth):
    return client.post(URL, headers=auth, json={
        "name": "Audit cup", "game_id": 1,
        "start_date": str(date.today() + timedelta(days=7)),
    })


def logs(factory):
    with factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.resource == "tournament")
                          .order_by(AuditLog.log_id)).all()


def test_tournament_audit_actor_resource_and_changes(access, session_factory):
    client, headers, users, *_ = access
    auth = headers("organizer")
    response = create(client, auth)
    assert response.status_code == 201
    tid = response.json()["tournament_id"]
    path = f"{URL}/{tid}"
    new_date = str(date.today() + timedelta(days=8))
    assert client.patch(path, headers=auth, json={"name": "Renamed cup", "start_date": new_date}).status_code == 200
    assert client.post(path + "/status", headers=auth, json={"status": "CANCELLED"}).status_code == 200
    entries = logs(session_factory)
    assert [entry.action for entry in entries] == [
        "TOURNAMENT_CREATED", "TOURNAMENT_UPDATED", "TOURNAMENT_STATUS_CHANGED",
    ]
    assert all(entry.user_id == users["organizer"] and entry.details["tournament_id"] == tid for entry in entries)
    assert entries[0].details["before"] == {}
    assert entries[0].details["after"]["created_by"] == users["organizer"]
    assert entries[1].details["before"]["name"] == "Audit cup"
    assert entries[1].details["after"] == {"name": "Renamed cup", "start_date": new_date}
    assert entries[2].details == {"tournament_id": tid, "before": {"status": "UPCOMING"}, "after": {"status": "CANCELLED"}}
    # Rejected writes must not append successful audit entries.
    assert client.patch(path, headers=headers("viewer"), json={"name": "Forbidden"}).status_code == 403
    assert client.patch(path, headers=auth, json={"name": None}).status_code == 422
    assert client.post(path + "/status", headers=auth, json={"status": "UPCOMING"}).status_code == 409
    assert len(logs(session_factory)) == 3


@pytest.mark.parametrize("operation", ["create", "update", "status"])
def test_audit_failure_rolls_back_tournament_write(access, session_factory, operation):
    client, headers, *_ = access
    auth = headers("organizer")
    existing = create(client, auth).json()
    path = f"{URL}/{existing['tournament_id']}"

    def reject_audit(mapper, connection, target):
        raise IntegrityError("injected audit insert failure", {}, Exception("audit unavailable"))

    event.listen(AuditLog, "before_insert", reject_audit)
    try:
        if operation == "create":
            response = create(client, auth)
        elif operation == "update":
            response = client.patch(path, headers=auth, json={"name": "Must rollback"})
        else:
            response = client.post(path + "/status", headers=auth, json={"status": "CANCELLED"})
        assert response.status_code == 409
    finally:
        event.remove(AuditLog, "before_insert", reject_audit)
    assert client.get(path).json() == existing
    with session_factory() as db:
        assert len(db.scalars(select(Tournament)).all()) == 1
    assert len(logs(session_factory)) == 1


def test_business_failure_does_not_leave_audit(access, session_factory):
    client, headers, *_ = access

    def reject_tournament(mapper, connection, target):
        raise IntegrityError("injected business insert failure", {}, Exception("constraint failure"))

    event.listen(Tournament, "before_insert", reject_tournament)
    try:
        assert create(client, headers("organizer")).status_code == 409
    finally:
        event.remove(Tournament, "before_insert", reject_tournament)
    assert logs(session_factory) == []
    with session_factory() as db:
        assert db.scalars(select(Tournament)).all() == []
