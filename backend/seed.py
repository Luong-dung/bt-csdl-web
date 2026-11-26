"""Seed the minimum reference data after running Alembic migrations.

Run from backend with: python seed.py
Existing records are preserved; the caller owns the transaction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import SessionLocal
from core.permissions import PERMISSIONS, ROLE_PERMISSIONS
from modules.catalog.models import CompetitionArea, Country, Game, Publisher
from modules.identity.models import Permission, Role, role_permissions


ROLE_NAMES = ("ADMIN", "ORGANIZER", "REFEREE", "TEAM_MANAGER", "PLAYER", "VIEWER")
GAMES = (
    ("Riot Games", "Teamfight Tactics", "teamfight-tactics"),
    ("Riot Games", "League of Legends", "league-of-legends"),
    ("Riot Games", "VALORANT", "valorant"),
    ("Garena", "Liên Quân Mobile", "arena-of-valor"),
    ("Garena", "Free Fire", "free-fire"),
)
# Parents must appear before their children.
AREAS = (
    ("GLOBAL", "Global", None),
    ("APAC", "Asia-Pacific", "GLOBAL"),
    ("VN", "Vietnam", "APAC"),
    ("VN-HCM", "Ho Chi Minh City", "VN"),
    # 1. League of Legends (LoL) - 6 khu vực chuyên nghiệp
    ("LCK", "Korea (LCK)", "GLOBAL"),
    ("LPL", "China (LPL)", "GLOBAL"),
    ("LEC", "EMEA (LEC)", "GLOBAL"),
    ("LCS", "North America (LCS)", "GLOBAL"),
    ("CBLOL", "Brazil (CBLOL)", "GLOBAL"),
    ("LCP", "Asia-Pacific (LCP)", "GLOBAL"),
    # 2. Teamfight Tactics (TFT) - 4 khu vực
    ("TFT AMER", "TFT Americas", "GLOBAL"),
    ("TFT EMEA", "TFT EMEA", "GLOBAL"),
    ("TFT APAC", "TFT APAC", "GLOBAL"),
    ("TFT CN", "TFT China", "GLOBAL"),
    # 3. VALORANT (VLR) - 4 khu vực
    ("VCT Americas", "VCT Americas", "GLOBAL"),
    ("VCT EMEA", "VCT EMEA", "GLOBAL"),
    ("VCT Pacific", "VCT Pacific", "GLOBAL"),
    ("VCT CN", "VCT China", "GLOBAL"),
    # 4. Liên Quân Mobile (LQM / Arena of Valor) - 5 khu vực
    ("RPL", "Thailand (RPL)", "GLOBAL"),
    ("AOG", "Vietnam (AOG)", "GLOBAL"),
    ("GCS", "Chinese Taipei (GCS)", "GLOBAL"),
    ("ASL", "Indonesia (ASL)", "GLOBAL"),
    ("AVC", "AoV International Championship", "GLOBAL"),
    # 5. Free Fire - 8 khu vực
    ("FFWS SEA", "FFWS Southeast Asia", "GLOBAL"),
    ("FFWS BR", "FFWS Brazil", "GLOBAL"),
    ("FFWS LATAM", "FFWS Latin America", "GLOBAL"),
    ("FFWS MEA", "FFWS Middle East & Africa", "GLOBAL"),
    ("FFWS NA", "FFWS North America", "GLOBAL"),
    ("FFWS PK", "FFWS Pakistan", "GLOBAL"),
    ("FFWS IN", "FFWS India", "GLOBAL"),
    ("FFWS BD", "FFWS Bangladesh", "GLOBAL"),
)

# W47-04 (W03-02): minimal ISO 3166-1 alpha-2 countries and the areas that belong to one country.
COUNTRIES = (
    ("VN", "Việt Nam"), ("TH", "Thái Lan"), ("ID", "Indonesia"), ("KR", "Hàn Quốc"),
    ("CN", "Trung Quốc"), ("TW", "Đài Loan"), ("BR", "Brazil"), ("US", "Hoa Kỳ"),
)
AREA_COUNTRIES = {
    "VN": "VN", "VN-HCM": "VN", "AOG": "VN", "RPL": "TH", "ASL": "ID", "LCK": "KR",
    "LPL": "CN", "GCS": "TW", "CBLOL": "BR", "FFWS BR": "BR",
}


def seed_reference_data(db: Session) -> dict[str, int]:
    """Insert missing records using natural keys, without fixed primary keys."""
    added = {"roles": 0, "permissions": 0, "role_permissions": 0,
             "publishers": 0, "games": 0, "competition_areas": 0, "countries": 0}
    for name in ROLE_NAMES:
        if db.scalar(select(Role).where(Role.role_name == name)) is None:
            db.add(Role(role_name=name))
            added["roles"] += 1
    db.flush()

    # Default grants are written only together with a newly created permission, so a grant an
    # operator removed on purpose is not restored by re-running the seed.
    role_ids = dict(db.execute(select(Role.role_name, Role.role_id)).all())
    for permission_name, description in PERMISSIONS:
        if db.scalar(select(Permission).where(Permission.permission_name == permission_name)) is not None:
            continue
        permission = Permission(permission_name=permission_name, description=description)
        db.add(permission)
        db.flush()
        added["permissions"] += 1
        for role_name, granted in ROLE_PERMISSIONS.items():
            if permission_name in granted and role_name in role_ids:
                db.execute(role_permissions.insert().values(
                    role_id=role_ids[role_name], permission_id=permission.permission_id))
                added["role_permissions"] += 1

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

    for country_code, name in COUNTRIES:
        if db.get(Country, country_code) is None and db.scalar(
                select(Country.country_code).where(Country.name == name)) is None:
            db.add(Country(country_code=country_code, name=name))
            added["countries"] += 1
    db.flush()

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
        # Fill a missing link only; an area's existing country is preserved.
        country_code = AREA_COUNTRIES.get(code)
        if area.country_code is None and country_code is not None and db.get(Country, country_code) is not None:
            area.country_code = country_code
    db.flush()
    return added


def main() -> None:
    with SessionLocal.begin() as db:
        added = seed_reference_data(db)
    print("Seed completed: " + ", ".join(f"{table} +{count}" for table, count in added.items()))


if __name__ == "__main__":
    main()
