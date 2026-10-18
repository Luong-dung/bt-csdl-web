"""Opt-in demo data; never run implicitly during normal reference seeding."""

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.security import hash_password
from modules.catalog.models import Game
from modules.identity.models import Role, User
from modules.teams.models import Organization, Team, TeamMembership
from seed import seed_reference_data


ACCOUNTS = (
    ("demo_admin", "ADMIN"),
    ("demo_organizer", "ORGANIZER"),
    ("demo_manager", "TEAM_MANAGER"),
    ("demo_player", "PLAYER"),
    ("demo_free_player", "PLAYER"),
    ("demo_viewer", "VIEWER"),
)
TEAM_TAG = "DEMO43"
TEAM_NAME = "W43 Demo Team"
ORGANIZATION_NAME = "W43 Demo Organization"


def seed_demo_data(db: Session, password: str) -> dict[str, int]:
    """Caller owns transaction. Existing passwords and business data are preserved.

    Reserved usernames/tags with incompatible data fail instead of being repurposed.
    """
    if not 8 <= len(password) <= 128:
        raise ValueError("Demo password must contain 8 to 128 characters")
    added = seed_reference_data(db)
    added.update(users=0, organizations=0, teams=0, memberships=0)
    roles = {r.role_name: r for r in db.scalars(select(Role))}
    users = {}
    for username, role in ACCOUNTS:
        email = f"{username}@example.com"
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            if db.scalar(select(User).where(User.email == email)) is not None:
                raise ValueError(f"Reserved demo email is already used: {email}")
            user = User(username=username, email=email, real_name=username,
                        password_hash=hash_password(password), role_id=roles[role].role_id)
            db.add(user)
            db.flush()
            added["users"] += 1
        elif user.email != email or user.role_id != roles[role].role_id:
            raise ValueError(f"Reserved demo account conflicts with existing data: {username}")
        users[username] = user

    organization = db.scalar(select(Organization).where(Organization.name == ORGANIZATION_NAME))
    if organization is None:
        organization = Organization(name=ORGANIZATION_NAME)
        db.add(organization)
        db.flush()
        added["organizations"] += 1
    game = db.scalar(select(Game).where(Game.slug == "valorant"))
    if game is None:
        raise ValueError("Demo requires the reference game slug valorant")
    team = db.scalar(select(Team).where(Team.tag == TEAM_TAG))
    if team is None:
        team = Team(name=TEAM_NAME, tag=TEAM_TAG, game_id=game.game_id,
                    organization_id=organization.organization_id)
        db.add(team)
        db.flush()
        added["teams"] += 1
    elif (team.name != TEAM_NAME or team.game_id != game.game_id
          or team.organization_id != organization.organization_id):
        raise ValueError("Reserved demo team conflicts with existing data")

    for username, role in (("demo_manager", "MANAGER"), ("demo_player", "PLAYER")):
        user = users[username]
        memberships = db.scalars(select(TeamMembership).where(
            TeamMembership.user_id == user.user_id,
            (TeamMembership.status == "ACTIVE") | (TeamMembership.team_id == team.team_id),
        )).all()
        if memberships:
            if not (len(memberships) == 1 and memberships[0].team_id == team.team_id
                    and memberships[0].status == "ACTIVE" and memberships[0].left_date is None
                    and memberships[0].role_in_team == role):
                raise ValueError(f"Demo membership changed; refusing to reset: {username}")
            continue
        db.add(TeamMembership(team_id=team.team_id, user_id=user.user_id, role_in_team=role))
        db.flush()
        added["memberships"] += 1
    return added


def demo_database_url(database: str):
    if not database or not database.endswith(("_demo", "_test")):
        raise ValueError("Explicit database name must end with _demo or _test")
    settings = get_settings()
    if database == settings.DB_NAME:
        raise ValueError("Demo target must differ from the configured application database")
    return make_url(settings.DATABASE_URL).set(database=database)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Separate existing PostgreSQL database ending in _demo/_test")
    parser.add_argument("--migrate", action="store_true", help="Run Alembic upgrade head on the demo target before seeding")
    args = parser.parse_args()
    try:
        url = demo_database_url(args.database)
        password = os.environ.get("DEMO_PASSWORD", "")
        if not 8 <= len(password) <= 128:
            raise ValueError("Set DEMO_PASSWORD to 8 to 128 characters")
    except ValueError as exc:
        parser.error(str(exc))
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            if args.migrate:
                config = Config(str(Path(__file__).parent / "alembic.ini"))
                config.set_main_option("script_location", str(Path(__file__).parent / "alembic"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            with Session(bind=connection, autoflush=False) as db:
                added = seed_demo_data(db, password)
                db.flush()
        print("Demo seed completed in " + args.database + ": " + ", ".join(f"{k} +{v}" for k, v in added.items()))
        print("Accounts: " + ", ".join(username for username, _ in ACCOUNTS))
        print("Existing account passwords were preserved; DEMO_PASSWORD applies only to newly created accounts.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
