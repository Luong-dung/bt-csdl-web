from datetime import date
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

import main  # ensures all models are registered on Base.metadata
from config.database import Base
from modules.catalog.models import Game, Publisher
from modules.tournaments.models import Tournament


def load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "7a1b2c3d4e5f_cleanup_legacy_valve_games.py"
    )
    spec = importlib.util.spec_from_file_location("migration_valve_cleanup", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        yield session
    engine.dispose()


def test_migration_cleans_unreferenced_valve_and_counter_strike(db):
    migration = load_migration()

    valve = Publisher(name="Valve")
    riot = Publisher(name="Riot Games")
    db.add_all([valve, riot])
    db.flush()

    cs2 = Game(name="Counter-Strike 2", slug="counter-strike-2", publisher_id=valve.publisher_id)
    dota = Game(name="Dota 2", slug="dota-2", publisher_id=valve.publisher_id)
    lol = Game(name="League of Legends", slug="league-of-legends", publisher_id=riot.publisher_id)
    db.add_all([cs2, dota, lol])
    db.commit()

    with patch("alembic.op.get_bind", return_value=db.connection()):
        migration.upgrade()
    db.commit()

    remaining_games = {g.slug for g in db.scalars(select(Game))}
    assert remaining_games == {"league-of-legends"}

    remaining_publishers = {p.name for p in db.scalars(select(Publisher))}
    assert remaining_publishers == {"Riot Games"}


def test_migration_preserves_referenced_games(db):
    migration = load_migration()

    valve = Publisher(name="Valve")
    db.add(valve)
    db.flush()

    cs2 = Game(name="Counter-Strike 2", slug="counter-strike-2", publisher_id=valve.publisher_id)
    db.add(cs2)
    db.flush()

    tournament = Tournament(
        name="CS2 Major",
        game_id=cs2.game_id,
        format="SINGLE_ELIM",
        start_date=date.today(),
        end_date=date.today(),
        status="UPCOMING",
    )
    db.add(tournament)
    db.commit()

    with patch("alembic.op.get_bind", return_value=db.connection()):
        migration.upgrade()
    db.commit()

    remaining_games = {g.slug for g in db.scalars(select(Game))}
    assert "counter-strike-2" in remaining_games

    remaining_publishers = {p.name for p in db.scalars(select(Publisher))}
    assert "Valve" in remaining_publishers
