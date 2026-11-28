import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from config.database import Base
from modules.catalog.models import CompetitionArea, Country, Game, Publisher
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
        "roles": 6, "permissions": 5, "role_permissions": 6,
        "publishers": 2, "games": 5, "competition_areas": 31, "countries": 8,
    }
    db.commit()
    assert seed_reference_data(db) == dict.fromkeys(
        ("roles", "permissions", "role_permissions", "publishers", "games", "competition_areas", "countries"), 0
    )
    assert set(db.scalars(select(Role.role_name))) == set(ROLE_NAMES)
    for model, count in ((Role, 6), (Publisher, 2), (Game, 5), (CompetitionArea, 31)):
        assert db.scalar(select(func.count()).select_from(model)) == count
    games = {game.slug: game for game in db.scalars(select(Game))}
    assert games["teamfight-tactics"].publisher.name == "Riot Games"
    assert games["valorant"].publisher.name == "Riot Games"
    assert games["free-fire"].publisher.name == "Garena"
    areas = {area.code: area for area in db.scalars(select(CompetitionArea))}
    assert areas["GLOBAL"].parent_id is None
    for child, parent in (("APAC", "GLOBAL"), ("VN", "APAC"), ("VN-HCM", "VN")):
        assert areas[child].parent_id == areas[parent].area_id
    # W47-04: country-specific areas are linked, multi-country areas stay NULL.
    assert (areas["VN"].country_code, areas["VN-HCM"].country_code, areas["LCK"].country_code) == ("VN", "VN", "KR")
    assert areas["GLOBAL"].country_code is None and areas["APAC"].country_code is None


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
    assert added == {"roles": 5, "permissions": 5, "role_permissions": 6,
                     "publishers": 1, "games": 5, "competition_areas": 30, "countries": 8}
    assert db.scalar(select(Game).where(Game.slug == "valorant")).publisher_id == 42
    assert db.scalar(select(CompetitionArea).where(CompetitionArea.code == "APAC")).parent_id == 42
    assert db.get(CompetitionArea, 42).name == "Custom global"
    assert db.get(Publisher, 99).name == "Custom publisher"


def test_seed_rolls_back_as_one_transaction(db):
    seed_reference_data(db)
    db.rollback()
    for model in (Role, Publisher, Game, CompetitionArea):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_country_seed_preserves_existing_rows_and_links(db):
    db.add_all([Country(country_code="VN", name="Vietnam (custom)"), Country(country_code="KR", name="Korea")])
    db.flush()
    db.add(CompetitionArea(code="VN", name="Vietnam", country_code="KR"))
    db.commit()
    added = seed_reference_data(db)
    db.commit()
    assert added["countries"] == 6
    assert db.get(Country, "VN").name == "Vietnam (custom)"
    areas = {area.code: area for area in db.scalars(select(CompetitionArea))}
    assert areas["VN"].country_code == "KR"  # existing link kept
    assert areas["VN-HCM"].country_code == "VN"
