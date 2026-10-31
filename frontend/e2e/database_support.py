"""Minimal setup helpers for scoped-role E2E; only accepts the disposable E2E DB."""

import os

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
