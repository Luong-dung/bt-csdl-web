import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base
from config.settings import get_settings
from seed import seed_reference_data


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="Run API tests in isolated PostgreSQL schemas")


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: test runs against PostgreSQL")


@pytest.fixture
def base_session_factory(request):
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


@pytest.fixture
def postgres_session_factory():
    # All DDL and API commits stay within an outer transaction, rolled back on exit.
    database_url = os.environ.get("TEST_DATABASE_URL") or get_settings().DATABASE_URL
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    schema = "w42_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                backend = Path(__file__).resolve().parents[1]
                config = Config(str(backend / "alembic.ini"))
                config.attributes["connection"] = connection
                config.attributes["version_table_schema"] = schema
                command.upgrade(config, "head")
                factory = sessionmaker(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
                with factory.begin() as db:
                    seed_reference_data(db)
                yield factory
            finally:
                transaction.rollback()
            assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                                     {"schema": schema}) == 0
    finally:
        engine.dispose()
