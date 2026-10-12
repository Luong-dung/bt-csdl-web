import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from config.database import Base
from modules.catalog.models import CompetitionArea, Game, Publisher
from modules.identity.models import Role
from seed import ROLE_NAMES, seed_reference_data


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


def test_empty_database_and_repeat_run(db):
    assert seed_reference_data(db) == {
        "roles": 6, "publishers": 2, "games": 4, "competition_areas": 4,
    }
    db.commit()
    assert seed_reference_data(db) == dict.fromkeys(
        ("roles", "publishers", "games", "competition_areas"), 0
    )
    assert set(db.scalars(select(Role.role_name))) == set(ROLE_NAMES)
    for model, count in ((Role, 6), (Publisher, 2), (Game, 4), (CompetitionArea, 4)):
        assert db.scalar(select(func.count()).select_from(model)) == count
    games = {game.slug: game for game in db.scalars(select(Game))}
    assert games["valorant"].publisher.name == "Riot Games"
    assert games["dota-2"].publisher.name == "Valve"
    areas = {area.code: area for area in db.scalars(select(CompetitionArea))}
    assert areas["GLOBAL"].parent_id is None
    for child, parent in (("APAC", "GLOBAL"), ("VN", "APAC"), ("VN-HCM", "VN")):
        assert areas[child].parent_id == areas[parent].area_id


def test_preserves_existing_records_and_uses_their_ids(db):
    db.add_all([
        Role(role_id=42, role_name="VIEWER"),
        Publisher(publisher_id=42, name="Riot Games"),
        CompetitionArea(area_id=42, code="GLOBAL", name="Custom global"),
        Publisher(publisher_id=99, name="Custom publisher"),
    ])
    db.commit()
    added = seed_reference_data(db)
    db.commit()
    assert added == {"roles": 5, "publishers": 1, "games": 4, "competition_areas": 3}
    assert db.scalar(select(Game).where(Game.slug == "valorant")).publisher_id == 42
    assert db.scalar(select(CompetitionArea).where(CompetitionArea.code == "APAC")).parent_id == 42
    assert db.get(CompetitionArea, 42).name == "Custom global"
    assert db.get(Publisher, 99).name == "Custom publisher"


def test_seed_rolls_back_as_one_transaction(db):
    seed_reference_data(db)
    db.rollback()
    for model in (Role, Publisher, Game, CompetitionArea):
        assert db.scalar(select(func.count()).select_from(model)) == 0
