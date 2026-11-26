"""W48-01: full demo scenario seeded through the real API (SQLite by default, PostgreSQL with --postgres)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import Base
from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import Team
from modules.tournaments.models import Match, Tournament, TournamentBracket, TournamentRegistration
from seed import seed_reference_data
from seed_demo import run_seed, seed_demo_data
from seed_demo_scenario import CUP, DRAFT, LEAGUE, OPEN, ScenarioError, seed_demo_scenario

PASSWORD = "Demo-test-password-2026"
pytestmark = pytest.mark.postgres


@pytest.fixture
def connection(request):
    if request.config.getoption("--postgres"):
        return request.getfixturevalue("postgres_session_factory").kw["bind"]
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    conn = engine.connect()
    outer = conn.begin()
    request.addfinalizer(lambda: (outer.rollback(), conn.close(), engine.dispose()))
    return conn


def session(connection):
    return Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")


def seed_all(connection, today=None, now=None):
    with session(connection) as db:
        seed_reference_data(db)
        seed_demo_data(db, PASSWORD)
        db.commit()
    return seed_demo_scenario(connection, PASSWORD, today, now)


def test_scenario_covers_every_tournament_state_through_the_api(connection):
    assert seed_all(connection) == {"users": 7, "teams": 3, "tournaments": 4}
    with session(connection) as db:
        status = {t.name: t for t in db.scalars(select(Tournament))}
        assert {n: status[n].status for n in (CUP, OPEN, LEAGUE, DRAFT)} == {
            CUP: "COMPLETED", OPEN: "ONGOING", LEAGUE: "UPCOMING", DRAFT: "UPCOMING"}
        cup, open_ = status[CUP].tournament_id, status[OPEN].tournament_id
        assert db.scalar(select(func.count()).select_from(TournamentBracket)) == 2

        def matches(tid, state):
            return db.scalar(select(func.count()).select_from(Match).where(
                Match.tournament_id == tid, Match.status == state))
        assert (matches(cup, "COMPLETED"), matches(open_, "COMPLETED"), matches(open_, "PENDING")) == (3, 1, 2)
        # Every bracket match has a schedule (set via PATCH while PENDING); Open's remaining ones are tomorrow.
        assert db.scalar(select(func.count()).select_from(Match).where(Match.scheduled_at.is_(None))) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "MATCH_UPDATED")) == 6
        regs = dict(db.execute(select(TournamentRegistration.status, func.count()).where(
            TournamentRegistration.tournament_id == status[LEAGUE].tournament_id).group_by(
            TournamentRegistration.status)).all())
        assert regs == {"APPROVED": 1, "PENDING": 2}
        assert db.scalar(select(func.count()).select_from(TournamentRegistration).where(
            TournamentRegistration.tournament_id == status[DRAFT].tournament_id)) == 0

        referee = db.scalar(select(User.user_id).where(User.username == "demo_referee"))
        grants = db.scalars(select(RoleAssignment).where(RoleAssignment.user_id == referee)).all()
        assert sorted(g.scope_id for g in grants) == sorted([cup, open_])
        # Referee is granted via API (audited) and really entered the cup final.
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "ROLE_ASSIGNMENT_GRANTED")) == 2
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "MATCH_RESULT_SUBMITTED", AuditLog.user_id == referee)) == 1


def test_scenario_is_idempotent_and_refuses_partial_state(connection):
    seed_all(connection)
    with session(connection) as db:
        before = (db.scalar(select(func.count()).select_from(AuditLog)),
                  db.scalar(select(func.count()).select_from(Tournament)))
    assert seed_demo_scenario(connection, "Other-password-2026") == {"users": 0, "teams": 0, "tournaments": 0}
    with session(connection) as db:
        assert before == (db.scalar(select(func.count()).select_from(AuditLog)),
                          db.scalar(select(func.count()).select_from(Tournament)))
        db.delete(db.scalar(select(Tournament).where(Tournament.name == DRAFT)))
        db.commit()
    with pytest.raises(ScenarioError, match="Partial demo scenario"):
        seed_demo_scenario(connection, PASSWORD)


def test_reserved_team_tag_collision_is_refused(connection):
    with session(connection) as db:
        seed_reference_data(db)
        seed_demo_data(db, PASSWORD)
        base = db.scalar(select(Team).where(Team.tag == "DEMO43"))
        db.add(Team(name="Squatter", tag="DEMO48B", game_id=base.game_id))
        db.commit()
    with pytest.raises(ScenarioError, match="tag already exists"):
        seed_demo_scenario(connection, PASSWORD)


def test_future_dates_are_relative_to_today(connection):
    seed_all(connection, today=date(2027, 1, 10))
    with session(connection) as db:
        starts = dict(db.execute(select(Tournament.name, Tournament.start_date)).all())
        assert str(starts[LEAGUE]) == "2027-01-24" and str(starts[DRAFT]) == "2027-02-09"


def test_run_seed_base_only_skips_scenario(connection):
    with session(connection) as db:
        seed_reference_data(db)
        db.commit()
    added = run_seed(connection, PASSWORD, base_only=True)
    assert added["users"] == 6 and not any(k.startswith("scenario_") for k in added)
    with session(connection) as db:
        assert db.scalar(select(func.count()).select_from(Tournament)) == 0
    assert run_seed(connection, PASSWORD)["scenario_tournaments"] == 4


def test_reset_is_refused_outside_postgresql(request, connection):
    if request.config.getoption("--postgres"):
        pytest.skip("Never DROP SCHEMA public inside the shared PostgreSQL test database")
    with pytest.raises(ValueError, match="only supports PostgreSQL"):
        run_seed(connection, PASSWORD, reset=True)


VN = timezone(timedelta(hours=7))


def as_vn(value):
    # SQLite returns naive UTC, PostgreSQL returns aware datetimes.
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(VN)


@pytest.mark.parametrize("now, played", [
    (datetime(2027, 1, 10, 8, 30, tzinfo=VN), ["05:00", "06:00", "07:00", "07:00"]),
    # Seeding just after midnight: played matches clamp to today 00:00, never before the start date.
    (datetime(2027, 1, 10, 1, 15, tzinfo=VN), ["00:00", "00:00", "00:00", "00:00"]),
])
def test_played_matches_are_in_the_past_and_pending_ones_tomorrow(connection, now, played):
    seed_all(connection, today=date(2027, 1, 10), now=now)
    with session(connection) as db:
        rows = db.execute(select(Tournament.name, Match.status, Match.scheduled_at).join(
            Tournament, Tournament.tournament_id == Match.tournament_id).order_by(Match.match_id)).all()
    done = [as_vn(at) for _, status, at in rows if status == "COMPLETED"]
    assert [d.strftime("%H:%M") for d in done] == played
    assert all(d.date() == date(2027, 1, 10) and d <= now for d in done)
    pending = sorted(as_vn(at) for name, status, at in rows if status == "PENDING")
    assert pending == [datetime(2027, 1, 11, 19, tzinfo=VN), datetime(2027, 1, 11, 21, tzinfo=VN)]
