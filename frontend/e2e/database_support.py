"""Minimal setup helpers for E2E; only accepts the disposable E2E DB."""

import os
from datetime import datetime, timedelta, timezone

import psycopg2


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
