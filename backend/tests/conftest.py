import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import get_settings
from seed import seed_reference_data


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="Run API tests in isolated PostgreSQL schemas")


@pytest.fixture
def postgres_session_factory():
    # All DDL and API commits stay within an outer transaction, rolled back on exit.
    engine = create_engine(get_settings().DATABASE_URL, connect_args={"connect_timeout": 5})
    schema = "w42_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                context = MigrationContext.configure(connection)
                migrations = Path(__file__).resolve().parents[1] / "alembic" / "versions"
                with Operations.context(context):
                    for filename in ["53bbc0801b4f_identity_module.py", "20261011_2000_timezone_columns.py"]:
                        spec = importlib.util.spec_from_file_location("test_migration", migrations / filename)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        module.upgrade()
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
