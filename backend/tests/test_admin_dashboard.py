"""W48-05: Admin dashboard metrics, capabilities, and privacy-safe user search."""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, func, select

from core.permissions import ROLE_ASSIGNMENT_MANAGE
from modules.identity.models import (
    AuditLog,
    Permission,
    Role,
    User,
    role_permissions,
)
from modules.teams.models import Organization
from modules.tournaments.models import (
    Match,
    Stage,
    Tournament,
    TournamentRegistration,
)
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

__all__ = ["access", "match_case", "session_factory"]
pytestmark = pytest.mark.postgres

CAPS_URL = "/api/v1/admin/capabilities"
DASHBOARD_URL = "/api/v1/admin/dashboard"
SEARCH_URL = "/api/v1/admin/users/search"


def test_admin_capabilities_matrix(access):
    client, headers, *_ = access
    assert client.get(CAPS_URL).status_code == 401

    admin_res = client.get(CAPS_URL, headers=headers("admin"))
    assert admin_res.status_code == 200
    assert admin_res.headers.get("cache-control") == "private, no-store"
    assert admin_res.json() == {
        "can_view_dashboard": True,
        "can_manage_catalog": True,
        "can_manage_roles": True,
        "can_view_audit": True,
        "can_create_organization": True,
    }

    for who in ("organizer", "manager", "referee", "viewer"):
        res = client.get(CAPS_URL, headers=headers(who))
        assert res.status_code == 200
        assert res.json() == {
            "can_view_dashboard": False,
            "can_manage_catalog": False,
            "can_manage_roles": False,
            "can_view_audit": False,
            "can_create_organization": False,
        }


def test_admin_dashboard_permission_matrix_and_role_permissions_table(
    access, session_factory
):
    client, headers, *_ = access
    assert client.get(DASHBOARD_URL).status_code == 401
    for who in ("organizer", "manager", "referee", "viewer"):
        assert client.get(DASHBOARD_URL, headers=headers(who)).status_code == 403

    ok_res = client.get(DASHBOARD_URL, headers=headers("admin"))
    assert ok_res.status_code == 200
    assert ok_res.headers.get("cache-control") == "private, no-store"

    # Partial admin: granting only ROLE_ASSIGNMENT_MANAGE to VIEWER unlocks dashboard
    with session_factory.begin() as db:
        viewer_role_id = db.scalar(
            select(Role.role_id).where(Role.role_name == "VIEWER")
        )
        admin_role_id = db.scalar(
            select(Role.role_id).where(Role.role_name == "ADMIN")
        )
        perm_id = db.scalar(
            select(Permission.permission_id).where(
                Permission.permission_name == ROLE_ASSIGNMENT_MANAGE
            )
        )
        db.execute(
            role_permissions.insert().values(
                role_id=viewer_role_id, permission_id=perm_id
            )
        )
        db.execute(
            delete(role_permissions).where(
                role_permissions.c.role_id == admin_role_id
            )
        )

    viewer_dash = client.get(DASHBOARD_URL, headers=headers("viewer"))
    assert viewer_dash.status_code == 200
    assert viewer_dash.json()["capabilities"] == {
        "can_view_dashboard": True,
        "can_manage_catalog": False,
        "can_manage_roles": True,
        "can_view_audit": False,
        "can_create_organization": False,
    }
    # Admin stripped of role_permissions is rejected (table-driven, not hardcoded)
    assert client.get(DASHBOARD_URL, headers=headers("admin")).status_code == 403


def test_admin_dashboard_metrics_breakdown_and_no_sensitive_leak(
    access, session_factory, match_case
):
    client, headers, users, teams, _ = access
    tid_ongoing = match_case["tid"]
    tid_upcoming = match_case["other"]
    stage_id = match_case["stage"]
    first_match_id = match_case["match"]

    # Grant an active referee assignment via API
    grant_res = client.post(
        f"/api/v1/tournaments/{tid_ongoing}/referees",
        headers=headers("organizer"),
        json={"user_id": users["referee"]},
    )
    assert grant_res.status_code == 201

    # Start first_match_id -> ONGOING
    start_res = client.post(
        f"/api/v1/tournaments/{tid_ongoing}/matches/{first_match_id}/status",
        headers=headers("organizer"),
        json={"status": "ONGOING"},
    )
    assert start_res.status_code == 200

    with session_factory.begin() as db:
        db.add(Organization(name="Dash Test Org"))
        # Add 1 ready PENDING match, 1 TBD PENDING match, and 1 COMPLETED match
        db.add_all(
            [
                Match(
                    tournament_id=tid_ongoing,
                    stage_id=stage_id,
                    round_no=2,
                    team1_id=teams["Alpha"],
                    team2_id=teams["Beta"],
                    status="PENDING",
                ),
                Match(
                    tournament_id=tid_ongoing,
                    stage_id=stage_id,
                    round_no=3,
                    team1_id=teams["Alpha"],
                    team2_id=None,
                    status="PENDING",
                ),
                Match(
                    tournament_id=tid_ongoing,
                    stage_id=stage_id,
                    round_no=4,
                    team1_id=teams["Alpha"],
                    team2_id=teams["Beta"],
                    winner_id=teams["Alpha"],
                    score_team1=2,
                    score_team2=0,
                    status="COMPLETED",
                ),
            ]
        )
        # Create a CANCELLED tournament with an unplayed match (must NOT be counted)
        game_id = db.get(Tournament, tid_ongoing).game_id
        cancelled_t = Tournament(
            name="Cancelled Dash Cup",
            game_id=game_id,
            format="SINGLE_ELIM",
            start_date=date.today() + timedelta(days=5),
            status="CANCELLED",
            created_by=users["organizer"],
        )
        db.add(cancelled_t)
        db.flush()
        cancelled_tid = cancelled_t.tournament_id
        cancelled_stage = Stage(
            tournament_id=cancelled_tid,
            name="Cancelled Stage",
            sequence_order=1,
        )
        db.add(cancelled_stage)
        db.flush()
        db.add(
            Match(
                tournament_id=cancelled_tid,
                stage_id=cancelled_stage.stage_id,
                round_no=1,
                team1_id=teams["Alpha"],
                team2_id=teams["Beta"],
                status="PENDING",
            )
        )
        # Add a PENDING registration on the UPCOMING tournament
        db.add(
            TournamentRegistration(
                tournament_id=tid_upcoming,
                team_id=teams["Alpha"],
                status="PENDING",
                submitted_by=users["manager"],
            )
        )

    with session_factory() as db:
        audit_before = db.scalar(select(func.count()).select_from(AuditLog))

    res = client.get(DASHBOARD_URL, headers=headers("admin"))
    assert res.status_code == 200
    body = res.json()

    # Read-only guarantee: dashboard never writes audit rows or exposes emails
    with session_factory() as db:
        audit_after = db.scalar(select(func.count()).select_from(AuditLog))
    assert audit_after == audit_before
    raw_text = res.text.lower()
    assert "@example.com" not in raw_text
    assert "password" not in raw_text

    assert body["users"]["total"] >= 5
    assert body["users"]["by_role"]["ADMIN"] >= 1
    assert body["teams_total"] >= 2
    assert body["organizations_total"] >= 1
    assert body["active_role_assignments"] >= 1
    assert body["pending_registrations"] == 1
    assert body["tournaments"]["by_status"] == {
        "UPCOMING": 1,
        "ONGOING": 1,
        "COMPLETED": 0,
        "CANCELLED": 1,
    }
    assert body["tournaments"]["total"] == 3

    awaiting = body["matches_awaiting_result"]
    assert awaiting["ongoing"] == 1
    assert awaiting["pending_ready"] == 1
    assert awaiting["pending_tbd"] == 1
    assert awaiting["total"] == 3
    statuses = [item["status"] for item in awaiting["items"]]
    assert statuses[0] == "ONGOING"
    assert all(item["tournament_id"] != cancelled_tid for item in awaiting["items"])


def test_admin_dashboard_empty_business_data(access):
    client, headers, *_ = access
    res = client.get(DASHBOARD_URL, headers=headers("admin"))
    assert res.status_code == 200
    body = res.json()
    assert body["tournaments"] == {
        "total": 0,
        "by_status": {
            "UPCOMING": 0,
            "ONGOING": 0,
            "COMPLETED": 0,
            "CANCELLED": 0,
        },
    }
    assert body["matches_awaiting_result"] == {
        "total": 0,
        "ongoing": 0,
        "pending_ready": 0,
        "pending_tbd": 0,
        "items": [],
    }


def test_admin_user_search_privacy_escape_and_permissions(access, session_factory):
    client, headers, users, *_ = access
    assert client.get(SEARCH_URL, params={"q": "ad"}).status_code == 401
    for who in ("organizer", "manager", "referee", "viewer"):
        assert (
            client.get(
                SEARCH_URL, params={"q": "ad"}, headers=headers(who)
            ).status_code
            == 403
        )
    assert (
        client.get(
            SEARCH_URL, params={"q": " a "}, headers=headers("admin")
        ).status_code
        == 422
    )

    with session_factory.begin() as db:
        ref = db.get(User, users["referee"])
        ref.real_name = "Trọng Tài Đặc Biệt"
        ref_email = ref.email
        ref_username = ref.username

    # Searching by email must NOT find the user
    by_email = client.get(
        SEARCH_URL, params={"q": ref_email}, headers=headers("admin")
    )
    assert by_email.status_code == 200
    assert by_email.json() == []

    # Searching by username/real_name works and omits email
    by_name = client.get(
        SEARCH_URL, params={"q": "Đặc Biệt"}, headers=headers("admin")
    )
    assert by_name.status_code == 200
    assert by_name.headers.get("cache-control") == "private, no-store"
    items = by_name.json()
    assert any(item["username"] == ref_username for item in items)
    for item in items:
        assert "email" not in item
        assert set(item.keys()) == {"user_id", "username", "real_name", "role"}

    # Wildcards % and _ are escaped literally
    assert (
        client.get(
            SEARCH_URL, params={"q": "%%"}, headers=headers("admin")
        ).json()
        == []
    )
    assert (
        client.get(
            SEARCH_URL, params={"q": "__"}, headers=headers("admin")
        ).json()
        == []
    )
