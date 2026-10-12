"""Seed the minimum reference data after running Alembic migrations.

Run from backend with: python seed.py
Existing records are preserved; the caller owns the transaction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import SessionLocal
from modules.catalog.models import CompetitionArea, Game, Publisher
from modules.identity.models import Role


ROLE_NAMES = ("ADMIN", "ORGANIZER", "REFEREE", "TEAM_MANAGER", "PLAYER", "VIEWER")
GAMES = (
    ("Riot Games", "League of Legends", "league-of-legends"),
    ("Riot Games", "VALORANT", "valorant"),
    ("Valve", "Counter-Strike 2", "counter-strike-2"),
    ("Valve", "Dota 2", "dota-2"),
)
# Parents must appear before their children.
AREAS = (
    ("GLOBAL", "Global", None),
    ("APAC", "Asia-Pacific", "GLOBAL"),
    ("VN", "Vietnam", "APAC"),
    ("VN-HCM", "Ho Chi Minh City", "VN"),
)


def seed_reference_data(db: Session) -> dict[str, int]:
    """Insert missing records using natural keys, without fixed primary keys."""
    added = {"roles": 0, "publishers": 0, "games": 0, "competition_areas": 0}
    for name in ROLE_NAMES:
        if db.scalar(select(Role).where(Role.role_name == name)) is None:
            db.add(Role(role_name=name))
            added["roles"] += 1

    publishers = {}
    for publisher_name, name, slug in GAMES:
        if publisher_name not in publishers:
            publisher = db.scalar(select(Publisher).where(Publisher.name == publisher_name))
            if publisher is None:
                publisher = Publisher(name=publisher_name)
                db.add(publisher)
                db.flush()
                added["publishers"] += 1
            publishers[publisher_name] = publisher
        game = db.scalar(select(Game).where(Game.slug == slug))
        if game is None:
            game = db.scalar(select(Game).where(Game.name == name))
        if game is None:
            db.add(Game(name=name, slug=slug, publisher_id=publishers[publisher_name].publisher_id))
            added["games"] += 1

    areas = {}
    for code, name, parent_code in AREAS:
        area = db.scalar(select(CompetitionArea).where(CompetitionArea.code == code))
        if area is None:
            area = CompetitionArea(
                code=code, name=name,
                parent_id=areas[parent_code].area_id if parent_code else None,
            )
            db.add(area)
            db.flush()
            added["competition_areas"] += 1
        areas[code] = area
    db.flush()
    return added


def main() -> None:
    with SessionLocal.begin() as db:
        added = seed_reference_data(db)
    print("Seed completed: " + ", ".join(f"{table} +{count}" for table, count in added.items()))


if __name__ == "__main__":
    main()
