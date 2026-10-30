from datetime import datetime, timezone

import pytest
from modules.identity.models import RoleAssignment
from modules.teams.models import Team
from modules.tournaments.models import TournamentRegistration
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


def test_scoped_assignment_can_read_all_large_registration_and_approved_team_pages(
    access, session_factory
):
    client, headers, users, _, roles = access
    tournament_id = organizer_tournament(client, headers)
    other_tournament_id = organizer_tournament(client, headers)
    approved_count = 55
    pending_count = 3
    reviewed_at = datetime.now(timezone.utc)

    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users["viewer"],
            role_id=roles["ORGANIZER"],
            scope_type="TOURNAMENT",
            scope_id=tournament_id,
        ))
        teams = [
            Team(name=f"W44-2-07 Team {index:02d}", tag=f"W2{index:03d}", game_id=1)
            for index in range(approved_count + pending_count)
        ]
        db.add_all(teams)
        db.flush()

        registrations = [
            TournamentRegistration(
                tournament_id=tournament_id,
                team_id=team.team_id,
                status="APPROVED" if index < approved_count else "PENDING",
                submitted_by=users["manager"],
                reviewed_by=users["organizer"] if index < approved_count else None,
                reviewed_at=reviewed_at if index < approved_count else None,
            )
            for index, team in enumerate(teams)
        ]
        db.add_all(registrations)
        db.flush()
        expected_team_ids = {team.team_id for team in teams[:approved_count]}
        expected_registration_ids = {row.registration_id for row in registrations}

    teams_url = f"/api/v1/tournaments/{tournament_id}/teams"
    first_team_page = client.get(teams_url)
    second_team_page = client.get(teams_url, params={"offset": 50})
    team_rows = first_team_page.json() + second_team_page.json()
    assert first_team_page.status_code == second_team_page.status_code == 200
    assert first_team_page.headers["x-total-count"] == str(approved_count)
    assert second_team_page.headers["x-total-count"] == str(approved_count)
    assert len(first_team_page.json()) == 50
    assert len(second_team_page.json()) == approved_count - 50
    assert {row["team_id"] for row in team_rows} == expected_team_ids
    assert len({row["team_id"] for row in team_rows}) == approved_count
    assert all(set(row) == {"team_id", "name", "tag", "game_id"} for row in team_rows)

    registrations_url = f"/api/v1/tournaments/{tournament_id}/registrations"
    scoped_headers = headers("viewer")
    first_registration_page = client.get(registrations_url, headers=scoped_headers)
    second_registration_page = client.get(
        registrations_url, headers=scoped_headers, params={"offset": 50}
    )
    registration_rows = first_registration_page.json() + second_registration_page.json()
    assert first_registration_page.status_code == second_registration_page.status_code == 200
    assert first_registration_page.headers["x-total-count"] == str(approved_count + pending_count)
    assert second_registration_page.headers["x-total-count"] == str(approved_count + pending_count)
    assert len(first_registration_page.json()) == 50
    assert len(second_registration_page.json()) == pending_count + approved_count - 50
    assert {row["registration_id"] for row in registration_rows} == expected_registration_ids
    assert len({row["registration_id"] for row in registration_rows}) == approved_count + pending_count

    approved_page = client.get(
        registrations_url, headers=scoped_headers, params={"status": "APPROVED", "limit": 100}
    )
    pending_page = client.get(
        registrations_url, headers=scoped_headers, params={"status": "PENDING", "limit": 100}
    )
    assert approved_page.headers["x-total-count"] == str(approved_count)
    assert len(approved_page.json()) == approved_count
    assert pending_page.headers["x-total-count"] == str(pending_count)
    assert len(pending_page.json()) == pending_count

    # A TOURNAMENT assignment grants review/list access only to its exact scope.
    assert client.get(registrations_url, headers=headers("referee")).status_code == 403
    other_url = f"/api/v1/tournaments/{other_tournament_id}/registrations"
    assert client.get(other_url, headers=scoped_headers).status_code == 403
