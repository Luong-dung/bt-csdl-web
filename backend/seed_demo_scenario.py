"""W48-01: full demo scenario driven through the real HTTP API (rules, locks and audit included).

Everything runs on one caller-owned connection; each request uses a SAVEPOINT, so a
failure anywhere is rolled back by the caller together with the base demo seed.
"""
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from config.database import get_db
from core.security import create_access_token, hash_password
from main import create_app
from modules.catalog.models import Game
from modules.identity.models import Role, User
from modules.teams.models import Team
from modules.tournaments.models import Tournament

# username, account role
SCENARIO_ACCOUNTS = (
    ("demo_referee", "VIEWER"),
    ("demo_manager_b", "TEAM_MANAGER"),
    ("demo_manager_c", "TEAM_MANAGER"),
    ("demo_manager_d", "TEAM_MANAGER"),
    ("demo_player_b", "PLAYER"),
    ("demo_player_c", "PLAYER"),
    ("demo_player_d", "PLAYER"),
)
# tag, name, manager, player  (DEMO43 comes from the base seed)
SCENARIO_TEAMS = (
    ("DEMO48B", "W48 Demo Bravo", "demo_manager_b", "demo_player_b"),
    ("DEMO48C", "W48 Demo Charlie", "demo_manager_c", "demo_player_c"),
    ("DEMO48D", "W48 Demo Delta", "demo_manager_d", "demo_player_d"),
)
CUP, OPEN, LEAGUE, DRAFT = ("W48 Demo Cup", "W48 Demo Open", "W48 Demo League", "W48 Demo Draft")
TOURNAMENT_NAMES = (CUP, OPEN, LEAGUE, DRAFT)


class ScenarioError(ValueError):
    pass


class _Api:
    def __init__(self, connection: Connection, users: dict[str, int]):
        app = create_app()

        def db_override():
            # Route commits only release a savepoint; the caller owns the real transaction.
            db = Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.users = users

    def __call__(self, method: str, path: str, actor: str, json=None, expect: int = 200):
        token = create_access_token({"sub": str(self.users[actor])})
        response = self.client.request(method, "/api/v1" + path, json=json,
                                       headers={"Authorization": "Bearer " + token})
        if response.status_code != expect:
            raise ScenarioError(f"{method} {path} as {actor}: {response.status_code} {response.text}")
        return response.json() if response.content else None


def _ensure_users(db: Session, password: str) -> int:
    roles = {r.role_name: r.role_id for r in db.scalars(select(Role))}
    added = 0
    for username, role in SCENARIO_ACCOUNTS:
        email = f"{username}@example.com"
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            if db.scalar(select(User).where(User.email == email)) is not None:
                raise ScenarioError(f"Reserved demo email is already used: {email}")
            db.add(User(username=username, email=email, real_name=username,
                        password_hash=hash_password(password), role_id=roles[role]))
            added += 1
        elif user.email != email or user.role_id != roles[role]:
            raise ScenarioError(f"Reserved demo account conflicts with existing data: {username}")
    db.flush()
    return added


def _run_bracket(api: _Api, tid: int, stage_id: int, team_ids: list[int], results: int,
                 referee_for_last: bool = False) -> None:
    """Create a bracket, start the tournament and play the first `results` matches in order."""
    preview = api("POST", f"/tournaments/{tid}/bracket/preview", "demo_organizer",
                  {"stage_id": stage_id, "team_ids": team_ids})
    bracket = api("POST", f"/tournaments/{tid}/bracket", "demo_organizer",
                  {"stage_id": stage_id, "team_ids": team_ids, "preview_token": preview["preview_token"]},
                  expect=201)
    api("POST", f"/tournaments/{tid}/status", "demo_organizer", {"status": "ONGOING"})
    order = sorted(bracket["matches"], key=lambda n: (n["round_index"], n["position"]))
    for index, node in enumerate(order[:results]):
        mid = node["match"]["match_id"]
        actor = "demo_referee" if referee_for_last and index == results - 1 else "demo_organizer"
        api("POST", f"/tournaments/{tid}/matches/{mid}/status", actor, {"status": "ONGOING"})
        score = (2, 1) if index % 2 == 0 else (0, 2)
        api("PUT", f"/tournaments/{tid}/matches/{mid}/result", actor,
            {"score_team1": score[0], "score_team2": score[1]})


def seed_demo_scenario(connection: Connection, password: str, today: date | None = None) -> dict[str, int]:
    """Requires the base seed (`seed_demo_data`) on the same connection. Idempotent:
    if all scenario tournaments exist nothing is written; a partial scenario is refused."""
    today = today or date.today()
    with Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint") as db:
        existing = set(db.scalars(select(Tournament.name).where(Tournament.name.in_(TOURNAMENT_NAMES))))
        if existing == set(TOURNAMENT_NAMES):
            return {"users": 0, "teams": 0, "tournaments": 0}
        if existing:
            raise ScenarioError(f"Partial demo scenario found ({sorted(existing)}); use --reset")
        if db.scalar(select(Team).where(Team.tag.in_([t[0] for t in SCENARIO_TEAMS]))) is not None:
            raise ScenarioError("Reserved demo team tag already exists; use --reset")
        added_users = _ensure_users(db, password)
        users = {u.username: u.user_id for u in db.scalars(select(User).where(User.username.like("demo\\_%", escape="\\")))}
        game_id = db.scalar(select(Game.game_id).where(Game.slug == "valorant"))
        base_team = db.scalar(select(Team.team_id).where(Team.tag == "DEMO43"))
        if game_id is None or base_team is None:
            raise ScenarioError("Run the base demo seed first (valorant game, team DEMO43)")
        db.commit()

    api = _Api(connection, users)
    teams = {"demo_manager": base_team}
    for tag, name, manager, player in SCENARIO_TEAMS:
        team = api("POST", "/teams", manager, {"name": name, "tag": tag, "game_id": game_id}, expect=201)
        api("POST", f"/teams/{team['team_id']}/members", manager,
            {"username": player, "role_in_team": "PLAYER"}, expect=201)
        teams[manager] = team["team_id"]
    players = {"demo_manager": "demo_player", "demo_manager_b": "demo_player_b",
               "demo_manager_c": "demo_player_c", "demo_manager_d": "demo_player_d"}

    def tournament(name: str, start: date) -> int:
        return api("POST", "/tournaments", "demo_organizer",
                   {"name": name, "game_id": game_id, "format": "SINGLE_ELIM",
                    "start_date": start.isoformat(),
                    "description": "Dữ liệu demo W48 — không phải giải thật."}, expect=201)["tournament_id"]

    def enter_teams(tid: int, managers, approve=True, roster=True) -> list[int]:
        for manager in managers:
            reg = api("POST", f"/tournaments/{tid}/registrations", manager,
                      {"team_id": teams[manager]}, expect=201)
            if approve:
                api("POST", f"/tournaments/{tid}/registrations/{reg['registration_id']}/decision",
                    "demo_organizer", {"status": "APPROVED"})
            if approve and roster:
                api("PUT", f"/tournaments/{tid}/teams/{teams[manager]}/roster", manager,
                    {"members": [{"user_id": users[players[manager]], "role_in_team": "PLAYER"}]})
        return [teams[m] for m in managers]

    def ready(tid: int, team_ids_managers) -> tuple[int, list[int]]:
        team_ids = enter_teams(tid, team_ids_managers)
        api("POST", f"/tournaments/{tid}/roster-lock", "demo_organizer")
        stage = api("POST", f"/tournaments/{tid}/stages", "demo_organizer",
                    {"name": "Playoffs", "sequence_order": 1}, expect=201)
        return stage["stage_id"], team_ids

    all_managers = ("demo_manager", "demo_manager_b", "demo_manager_c", "demo_manager_d")

    # 1) Completed cup: full bracket, final entered by the granted referee, then COMPLETED.
    cup = tournament(CUP, today)
    stage, ids = ready(cup, all_managers)
    api("POST", f"/tournaments/{cup}/referees", "demo_organizer", {"user_id": users["demo_referee"]}, expect=201)
    _run_bracket(api, cup, stage, ids, results=3, referee_for_last=True)
    api("POST", f"/tournaments/{cup}/status", "demo_organizer", {"status": "COMPLETED"})

    # 2) Ongoing open: one semifinal played, the rest left for the live demo; referee active.
    open_ = tournament(OPEN, today)
    stage, ids = ready(open_, all_managers)
    api("POST", f"/tournaments/{open_}/referees", "demo_organizer", {"user_id": users["demo_referee"]}, expect=201)
    _run_bracket(api, open_, stage, ids, results=1)

    # 3) Upcoming league: one approved team, the rest pending for the approval demo.
    league = tournament(LEAGUE, today + timedelta(days=14))
    enter_teams(league, ("demo_manager",))
    enter_teams(league, ("demo_manager_b", "demo_manager_c"), approve=False)

    # 4) Empty upcoming tournament: deletable in the demo (W47-04).
    tournament(DRAFT, today + timedelta(days=30))
    return {"users": added_users, "teams": len(SCENARIO_TEAMS), "tournaments": len(TOURNAMENT_NAMES)}
