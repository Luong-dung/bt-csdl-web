"""Minimal setup helpers for E2E; only accepts the disposable E2E DB."""

import os
from datetime import datetime, timedelta, timezone

import psycopg2
from playwright.sync_api import Page


def assign_tournament_organizer(username: str, tournament_id: int) -> None:
    database_url = os.environ.get("E2E_DATABASE_URL")
    expected_database = os.environ.get("E2E_DB_NAME")
    if not database_url or not expected_database or not expected_database.endswith("_test"):
        raise RuntimeError("Scoped-role E2E requires E2E_DATABASE_URL and an E2E_DB_NAME ending in _test")

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != expected_database:
                raise RuntimeError("Refusing scoped-role setup outside the configured E2E database")
            cursor.execute(
                """
                INSERT INTO role_assignments (user_id, role_id, scope_type, scope_id)
                SELECT u.user_id, r.role_id, 'TOURNAMENT', %s
                FROM users AS u
                JOIN roles AS r ON r.role_name = 'ORGANIZER'
                JOIN roles AS viewer ON viewer.role_name = 'VIEWER'
                WHERE u.username = %s AND u.role_id = viewer.role_id
                """,
                (tournament_id, username),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"Could not assign scoped ORGANIZER role to {username}")


def assign_tournament_referee(
    page: Page,
    api_base_url: str,
    organizer_token: str,
    username: str,
    tournament_id: int,
) -> None:
    headers = {"Authorization": f"Bearer {organizer_token}"}
    candidates_response = page.request.get(
        f"{api_base_url}/tournaments/{tournament_id}/referees/candidates",
        params={"q": username, "limit": 20},
        headers=headers,
    )
    if not candidates_response.ok:
        raise RuntimeError(
            f"Could not search referee candidate {username}: "
            f"HTTP {candidates_response.status} {candidates_response.text()}"
        )

    candidate = next(
        (
            item
            for item in candidates_response.json()
            if item["username"] == username
        ),
        None,
    )
    if candidate is None:
        raise RuntimeError(f"Could not find referee candidate {username}")

    grant_response = page.request.post(
        f"{api_base_url}/tournaments/{tournament_id}/referees",
        headers=headers,
        data={"user_id": candidate["user_id"]},
    )
    if grant_response.status != 201:
        raise RuntimeError(
            f"Could not assign scoped REFEREE role to {username}: "
            f"HTTP {grant_response.status} {grant_response.text()}"
        )


def seed_match_pagination(
    tournament_id: int,
    stage_id: int,
    team1_id: int,
    team2_id: int,
    *,
    match_count: int = 55,
) -> list[int]:
    """Seed match rows for browser pagination only in the disposable E2E DB."""
    database_url = os.environ.get("E2E_DATABASE_URL")
    expected_database = os.environ.get("E2E_DB_NAME")
    if not database_url or not expected_database or not expected_database.endswith("_test"):
        raise RuntimeError("Match pagination E2E requires E2E_DATABASE_URL and an E2E_DB_NAME ending in _test")
    if match_count <= 50:
        raise ValueError("Match pagination E2E needs more than 50 matches")

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != expected_database:
                raise RuntimeError("Refusing match setup outside the configured E2E database")
            cursor.executemany(
                """
                INSERT INTO matches
                    (tournament_id, stage_id, round_no, team1_id, team2_id,
                     score_team1, score_team2, status)
                VALUES (%s, %s, %s, %s, %s, 0, 0, 'PENDING')
                """,
                [
                    (tournament_id, stage_id, round_no, team1_id, team2_id)
                    for round_no in range(1, match_count + 1)
                ],
            )
            cursor.execute(
                """
                SELECT match_id
                FROM matches
                WHERE tournament_id = %s AND stage_id = %s AND round_no BETWEEN 1 AND %s
                ORDER BY round_no
                """,
                (tournament_id, stage_id, match_count),
            )
            return [row[0] for row in cursor.fetchall()]


def seed_large_tournament_pagination(
    tournament_id: int, manager_username: str, *, registered_count: int = 51
) -> dict[str, object]:
    """Seed approved teams quickly for browser pagination and registration-picker E2E."""
    database_url = os.environ.get("E2E_DATABASE_URL")
    expected_database = os.environ.get("E2E_DB_NAME")
    if not database_url or not expected_database or not expected_database.endswith("_test"):
        raise RuntimeError("Pagination E2E requires E2E_DATABASE_URL and an E2E_DB_NAME ending in _test")
    if registered_count < 26:
        raise ValueError("Pagination E2E needs at least 26 registrations to place the target on page 3")

    suffix = manager_username[-6:]
    teams = [
        (f"W44-2-08 Registered {index:02d} {suffix}", f"R{index:02d}{suffix}")
        for index in range(registered_count)
    ]
    teams.append((f"W44-2-08 Available {suffix}", f"A{suffix}"))

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != expected_database:
                raise RuntimeError("Refusing pagination setup outside the configured E2E database")

            cursor.execute(
                """
                SELECT t.game_id, t.created_by, manager.user_id, manager_role.role_id,
                       reviewer.user_id
                FROM tournaments AS t
                JOIN users AS manager ON manager.username = %s
                JOIN roles AS manager_role ON manager_role.role_name = 'TEAM_MANAGER'
                JOIN users AS reviewer ON reviewer.username = 'demo_organizer'
                WHERE t.tournament_id = %s
                """,
                (manager_username, tournament_id),
            )
            tournament = cursor.fetchone()
            if tournament is None:
                raise RuntimeError("Could not find the tournament, manager, or demo organizer for pagination setup")
            game_id, _created_by, manager_id, manager_role_id, reviewer_id = tournament

            team_ids_by_name: dict[str, int] = {}
            for name, tag in teams:
                cursor.execute(
                    "INSERT INTO teams (game_id, name, tag, created_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) RETURNING team_id",
                    (game_id, name, tag),
                )
                team_ids_by_name[name] = cursor.fetchone()[0]

            registration_ids_by_team: dict[int, int] = {}
            base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for index, (name, _tag) in enumerate(teams[:registered_count]):
                cursor.execute(
                    """
                    INSERT INTO tournament_registrations
                        (tournament_id, team_id, status, submitted_by, submitted_at, reviewed_by, reviewed_at)
                    VALUES (%s, %s, 'APPROVED', %s, %s, %s, %s)
                    RETURNING registration_id
                    """,
                    (
                        tournament_id,
                        team_ids_by_name[name],
                        manager_id,
                        base_time + timedelta(seconds=index),
                        reviewer_id,
                        base_time + timedelta(seconds=index + 1),
                    ),
                )
                registration_ids_by_team[team_ids_by_name[name]] = cursor.fetchone()[0]

            registered_team_name = teams[min(25, registered_count - 1)][0]
            available_team_name = teams[-1][0]
            cursor.executemany(
                """
                INSERT INTO role_assignments (user_id, role_id, scope_type, scope_id)
                VALUES (%s, %s, 'TEAM', %s)
                """,
                [
                    (manager_id, manager_role_id, team_ids_by_name[registered_team_name]),
                    (manager_id, manager_role_id, team_ids_by_name[available_team_name]),
                ],
            )

            return {
                "registration_ids": set(registration_ids_by_team.values()),
                "team_ids": set(team_ids_by_name[name] for name, _tag in teams[:registered_count]),
                "registered_team_id": team_ids_by_name[registered_team_name],
                "registered_registration_id": registration_ids_by_team[team_ids_by_name[registered_team_name]],
                "available_team_id": team_ids_by_name[available_team_name],
                "available_team_name": available_team_name,
            }


def seed_bracket_fast_teams(
    tournament_id: int,
    *,
    team_count: int = 64,
) -> list[int]:
    """Seed approved teams with players and locked roster for large bracket E2E."""
    database_url = os.environ.get("E2E_DATABASE_URL")
    expected_database = os.environ.get("E2E_DB_NAME")
    if not database_url or not expected_database or not expected_database.endswith("_test"):
        raise RuntimeError("Fast bracket seeding requires E2E_DATABASE_URL and an E2E_DB_NAME ending in _test")

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != expected_database:
                raise RuntimeError("Refusing bracket setup outside the configured E2E database")

            cursor.execute("SELECT game_id FROM tournaments WHERE tournament_id = %s", (tournament_id,))
            tourn_row = cursor.fetchone()
            if tourn_row is None:
                raise RuntimeError(f"Tournament {tournament_id} not found")
            game_id = tourn_row[0]

            cursor.execute("SELECT user_id FROM users WHERE username = 'demo_organizer'")
            reviewer_row = cursor.fetchone()
            reviewer_id = reviewer_row[0] if reviewer_row else 1

            cursor.execute("SELECT role_id FROM roles WHERE role_name = 'PLAYER'")
            player_role_row = cursor.fetchone()
            if not player_role_row:
                cursor.execute("SELECT role_id FROM roles WHERE role_name = 'VIEWER'")
                player_role_row = cursor.fetchone()
            player_role_id = player_role_row[0]

            team_ids = []
            base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
            ts = int(datetime.now().timestamp()) % 1000000
            for idx in range(1, team_count + 1):
                u_name = f"b64p{idx}_{ts}"
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role_id, created_at) VALUES (%s, %s, 'unused', %s, CURRENT_TIMESTAMP) RETURNING user_id",
                    (u_name, f"{u_name}@example.com", player_role_id),
                )
                user_id = cursor.fetchone()[0]

                name = f"B64 Team {idx:02d} {ts}"
                tag = f"B{idx:02d}"[:10]
                cursor.execute(
                    "INSERT INTO teams (game_id, name, tag, created_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) RETURNING team_id",
                    (game_id, name, tag),
                )
                team_id = cursor.fetchone()[0]
                team_ids.append(team_id)

                cursor.execute(
                    """
                    INSERT INTO tournament_registrations
                        (tournament_id, team_id, status, submitted_by, submitted_at, reviewed_by, reviewed_at)
                    VALUES (%s, %s, 'APPROVED', %s, %s, %s, %s)
                    """,
                    (tournament_id, team_id, user_id, base_time, reviewer_id, base_time + timedelta(seconds=1)),
                )

                cursor.execute(
                    """
                    INSERT INTO tournament_rosters (tournament_id, team_id, user_id, role_in_team, display_name)
                    VALUES (%s, %s, %s, 'PLAYER', %s)
                    """,
                    (tournament_id, team_id, user_id, f"Player {idx}"),
                )

            # Mark tournament roster locked
            cursor.execute(
                "UPDATE tournaments SET roster_locked_at = CURRENT_TIMESTAMP WHERE tournament_id = %s",
                (tournament_id,),
            )
            return team_ids
