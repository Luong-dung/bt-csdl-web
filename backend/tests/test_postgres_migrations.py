from pathlib import Path
from shutil import copytree

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

import conftest

pytestmark = pytest.mark.postgres


def test_postgres_fixture_runs_new_head(request, monkeypatch):
    if not request.config.getoption("--postgres"):
        pytest.skip("requires --postgres")

    tmp_path = request.getfixturevalue("tmp_path")
    backend = Path(__file__).resolve().parents[1]
    head = ScriptDirectory.from_config(Config(str(backend / "alembic.ini"))).get_current_head()
    versions = tmp_path / "versions"
    copytree(backend / "alembic" / "versions", versions)
    (versions / "fixture_probe.py").write_text(
        'from alembic import op\n'
        'revision = "fixture_probe"\n'
        f'down_revision = "{head}"\n'
        'branch_labels = None\n'
        'depends_on = None\n'
        'def upgrade():\n'
        '    op.execute("CREATE TABLE fixture_migration_probe (id INTEGER)")\n'
        'def downgrade():\n'
        '    op.execute("DROP TABLE fixture_migration_probe")\n',
        encoding="utf-8",
    )

    def test_config(filename):
        config = Config(filename)
        config.set_main_option("version_locations", versions.as_posix())
        return config

    monkeypatch.setattr(conftest, "Config", test_config)
    factory = request.getfixturevalue("postgres_session_factory")
    with factory() as db:
        schema = db.scalar(text("SELECT current_schema()"))
        assert schema.startswith("w42_test_")
        assert db.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version')) == "fixture_probe"
        assert db.scalar(text("SELECT to_regclass(:name)"),
                         {"name": f"{schema}.fixture_migration_probe"}) is not None
