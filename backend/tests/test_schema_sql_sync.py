"""W48-02: database/schema_postgres.sql must mirror `alembic upgrade head`, and migrations must round-trip.

PostgreSQL only (`--postgres -m postgres`). Everything runs inside the fixture's outer transaction,
in throwaway schemas, and is rolled back.
"""
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.postgres

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_SQL = BACKEND.parent / 'database' / 'schema_postgres.sql'
W46_HEAD = 'c46a01b00001'  # last revision before the W47 migrations

QUERIES = {
    'columns': """SELECT table_name, column_name, data_type, coalesce(character_maximum_length::text, ''),
                         coalesce(numeric_precision::text, ''), coalesce(numeric_scale::text, ''), is_nullable,
                         regexp_replace(coalesce(column_default, ''), '::[a-z ]+', '', 'g')
                  FROM information_schema.columns WHERE table_schema = :s""",
    'keys': """SELECT tc.table_name, tc.constraint_type,
                      string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position)
               FROM information_schema.table_constraints tc
               JOIN information_schema.key_column_usage kcu
                 ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
               WHERE tc.table_schema = :s AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')
               GROUP BY tc.table_name, tc.constraint_type, tc.constraint_name""",
    'constraint_defs': """SELECT conrelid::regclass::text, contype, pg_get_constraintdef(oid)
                          FROM pg_constraint WHERE connamespace = CAST(:s AS regnamespace)
                            AND contype IN ('c', 'f')""",
    'indexes': """SELECT tablename, regexp_replace(indexdef, 'INDEX \\S+ ON \\S+', 'INDEX ON ' || tablename)
                  FROM pg_indexes WHERE schemaname = :s""",
}


def migration_config(connection, schema):
    config = Config(str(BACKEND / 'alembic.ini'))
    config.attributes['connection'] = connection
    config.attributes['version_table_schema'] = schema
    return config


def snapshot(connection, schema):
    """Structure of `schema`, read while it is the only schema on search_path (no qualified names)."""
    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    result = {}
    for name, query in QUERIES.items():
        rows = connection.execute(text(query), {'s': schema}).all()
        result[name] = {tuple(str(v).replace(f'"{schema}".', '').replace(f'{schema}.', '') for v in row)
                        for row in rows if row[0] != 'alembic_version'}
    return result


@pytest.fixture
def connection(request):
    if not request.config.getoption('--postgres'):
        pytest.skip('PostgreSQL DDL; run with --postgres -m postgres')
    conn = request.getfixturevalue('postgres_session_factory').kw['bind']
    migrated = conn.scalar(text('SELECT current_schema()'))
    yield conn, migrated
    conn.execute(text(f'SET LOCAL search_path TO "{migrated}"'))


def test_schema_sql_matches_migration_head(connection):
    conn, migrated = connection
    expected = snapshot(conn, migrated)
    target = 'w48_sql_' + uuid4().hex
    conn.execute(text(f'CREATE SCHEMA "{target}"'))
    conn.execute(text(f'SET LOCAL search_path TO "{target}"'))
    # Raw DBAPI cursor: the file contains '%' (modulo) and must run exactly as psql would run it.
    conn.connection.cursor().execute(SCHEMA_SQL.read_text(encoding='utf-8'))
    actual = snapshot(conn, target)
    for part in QUERIES:
        assert sorted(expected[part] - actual[part]) == [] and sorted(actual[part] - expected[part]) == [], (
            f'{part}: only in migrations {sorted(expected[part] - actual[part])}; '
            f'only in schema_postgres.sql {sorted(actual[part] - expected[part])}')
    assert len({row[0] for row in actual['columns']}) == 20  # business tables (alembic_version excluded)


def test_w47_migrations_downgrade_and_upgrade_cleanly(connection):
    conn, migrated = connection
    config = migration_config(conn, migrated)
    head = snapshot(conn, migrated)
    command.downgrade(config, W46_HEAD)
    conn.execute(text(f'SET LOCAL search_path TO "{migrated}"'))
    assert conn.scalar(text('SELECT version_num FROM alembic_version')) == W46_HEAD
    command.upgrade(config, 'head')
    assert snapshot(conn, migrated) == head


def test_full_downgrade_to_base_and_back(connection):
    conn, migrated = connection
    config = migration_config(conn, migrated)
    head = snapshot(conn, migrated)
    command.downgrade(config, 'base')
    conn.execute(text(f'SET LOCAL search_path TO "{migrated}"'))
    assert conn.scalar(text("SELECT count(*) FROM information_schema.tables "
                            "WHERE table_schema = current_schema() AND table_name <> 'alembic_version'")) == 0
    command.upgrade(config, 'head')
    assert snapshot(conn, migrated) == head
