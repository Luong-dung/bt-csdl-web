"""W48-04 (b): final standings stored in tournament_standings when a tournament becomes COMPLETED."""
import importlib.util
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import delete, func, select

import core.standings
from modules.identity.models import AuditLog
from modules.tournaments.models import Match, Tournament, TournamentStanding
from test_bracket_create import url
from test_bracket_foundation import bracket_case  # noqa: F401 (fixture)
from test_bracket_read import build, go_live, nodes_of, play, standings
from test_catalog_api import session_factory  # noqa: F401 (fixture)
from test_match_foundation import match_case  # noqa: F401 (fixture)
from test_permissions import access  # noqa: F401 (fixture)

pytestmark = pytest.mark.postgres

MIGRATION = Path(__file__).parents[1] / 'alembic' / 'versions' / 'h48a04b00002_backfill_tournament_standings.py'


@pytest.fixture
def eight(access, session_factory, bracket_case):  # noqa: F811
    client, headers, _, teams, roles = access
    return build(client, headers, session_factory, bracket_case, roles, teams, 8)


def play_all(client, headers, factory, ids):
    """Every round, first team wins; the fixture's manual match is cancelled so completion is allowed."""
    go_live(factory, ids)
    for round_index in (1, 2, 3):
        for node in nodes_of(client, ids, round_index):
            play(client, headers, ids, node['match']['match_id'], True)
    with factory.begin() as db:
        db.get(Match, ids['match']).status = 'CANCELLED'
    return standings(client, ids).json()


def complete(client, headers, ids):
    return client.post(f"/api/v1/tournaments/{ids['tid']}/status", headers=headers('organizer'),
                       json={'status': 'COMPLETED'})


def stored(factory, tid):
    with factory() as db:
        return [(r.team_id, r.final_rank, r.matches_played, r.wins, r.losses, r.points, float(r.prize_money))
                for r in db.scalars(select(TournamentStanding).where(TournamentStanding.tournament_id == tid)
                                    .order_by(TournamentStanding.final_rank, TournamentStanding.team_id))]


def audits(factory, tid, action):
    with factory() as db:
        return db.scalars(select(AuditLog).where(AuditLog.tournament_id == tid, AuditLog.action == action)
                          .order_by(AuditLog.log_id)).all()


def test_completion_writes_the_final_table_once_with_audit(access, session_factory, eight):  # noqa: F811
    client, headers, *_ = access
    ids, _ = eight
    derived = play_all(client, headers, session_factory, ids)
    assert derived['status'] == 'FINAL' and stored(session_factory, ids['tid']) == []
    assert complete(client, headers, ids).status_code == 200
    expected = sorted((i['team']['team_id'], i['rank'], i['matches_played'], i['wins'], i['losses'], i['wins'], 0.0)
                      for i in derived['items'])
    rows = stored(session_factory, ids['tid'])
    assert sorted(rows) == expected and len(rows) == 8
    assert [r[1] for r in rows] == [1, 2, 3, 3, 5, 5, 5, 5]
    [audit] = audits(session_factory, ids['tid'], core.standings.STANDINGS_FINALIZED)
    assert audit.user_id is not None and audit.details['bracket_id'] == derived['bracket_id']
    assert audit.details['standings'] == [{'team_id': i['team']['team_id'], 'rank': i['rank']} for i in derived['items']]
    [status_audit] = audits(session_factory, ids['tid'], 'TOURNAMENT_STATUS_CHANGED')
    assert status_audit.log_id > audit.log_id
    # The public response is unchanged by the switch to the stored table, pages included.
    assert standings(client, ids).json() == derived
    page = standings(client, ids, offset=2, limit=3)
    assert page.headers['x-total-count'] == '8'
    assert page.json()['items'] == derived['items'][2:5]
    # COMPLETED is final: a second request is refused and writes nothing more.
    assert complete(client, headers, ids).status_code == 409
    assert len(stored(session_factory, ids['tid'])) == 8
    assert len(audits(session_factory, ids['tid'], core.standings.STANDINGS_FINALIZED)) == 1


def test_completed_tournament_reads_the_stored_table_and_falls_back(access, session_factory, eight):  # noqa: F811
    client, headers, *_ = access
    ids, _ = eight
    derived = play_all(client, headers, session_factory, ids)
    assert complete(client, headers, ids).status_code == 200
    champion = derived['items'][0]['team']['team_id']
    with session_factory.begin() as db:
        db.get(TournamentStanding, (ids['tid'], champion)).wins = 99
    # Read from the table, not re-derived from matches.
    assert standings(client, ids).json()['items'][0]['wins'] == 99
    # A snapshot that does not cover the bracket is ignored; no rows at all (finished before W48-04) too.
    with session_factory.begin() as db:
        db.delete(db.get(TournamentStanding, (ids['tid'], champion)))
    assert standings(client, ids).json() == derived
    with session_factory.begin() as db:
        db.execute(delete(TournamentStanding).where(TournamentStanding.tournament_id == ids['tid']))
    assert standings(client, ids).json() == derived


def test_completion_without_bracket_writes_nothing(access, session_factory, bracket_case):  # noqa: F811
    client, headers, *_ = access
    ids = bracket_case
    go_live(session_factory, ids)
    with session_factory.begin() as db:
        db.get(Match, ids['match']).status = 'CANCELLED'
    assert complete(client, headers, ids).status_code == 200
    assert stored(session_factory, ids['tid']) == []
    assert audits(session_factory, ids['tid'], core.standings.STANDINGS_FINALIZED) == []
    assert client.get(url(ids, '/standings')).status_code == 404


def test_failure_rolls_back_status_and_table(access, session_factory, eight, monkeypatch):  # noqa: F811
    client, headers, *_ = access
    ids, _ = eight
    play_all(client, headers, session_factory, ids)

    def broken_audit(*args, **kwargs):
        raise RuntimeError('audit down')
    monkeypatch.setattr(core.standings, 'record_audit', broken_audit)
    with pytest.raises(RuntimeError):
        complete(client, headers, ids)
    with session_factory() as db:
        assert db.get(Tournament, ids['tid']).status == 'ONGOING'
    assert stored(session_factory, ids['tid']) == []


def run_backfill(factory):
    spec = importlib.util.spec_from_file_location('backfill_standings', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with factory.begin() as db:
        with Operations.context(MigrationContext.configure(db.connection())):
            module.upgrade()
    return module


def test_backfill_restores_the_same_table_and_skips_undecided(access, session_factory, eight):  # noqa: F811
    client, headers, *_ = access
    ids, _ = eight
    play_all(client, headers, session_factory, ids)
    assert complete(client, headers, ids).status_code == 200
    written = stored(session_factory, ids['tid'])
    with session_factory.begin() as db:
        db.execute(delete(TournamentStanding))
    run_backfill(session_factory)
    assert stored(session_factory, ids['tid']) == written
    run_backfill(session_factory)  # rows exist now: skipped, no duplicates
    assert stored(session_factory, ids['tid']) == written
    # A COMPLETED tournament whose bracket is not fully decided is left alone.
    with session_factory.begin() as db:
        db.execute(delete(TournamentStanding))
        final = db.get(Match, db.scalar(select(func.max(Match.match_id)).where(Match.tournament_id == ids['tid'])))
        final.status, final.winner_id = 'CANCELLED', None
    run_backfill(session_factory)
    assert stored(session_factory, ids['tid']) == []


def test_backfill_ranking_never_guesses():
    module = importlib.util.module_from_spec(importlib.util.spec_from_file_location('bf', MIGRATION))
    module.__spec__.loader.exec_module(module)
    rows = [(1, 'COMPLETED', 1, 2, 1), (1, 'COMPLETED', 3, 4, 4), (2, 'COMPLETED', 1, 4, 4)]
    table = {r['team_id']: (r['rank'], r['wins'], r['losses']) for r in module.final_table([1, 2, 3, 4], 2, rows)}
    assert table == {4: (1, 2, 0), 1: (2, 1, 1), 2: (3, 0, 1), 3: (3, 0, 1)}
    assert module.final_table([1, 2, 3, 4], 2, rows[:2]) is None  # no final
    assert module.final_table([1, 2, 3, 4], 2, rows[:2] + [(2, 'COMPLETED', 1, 4, 9)]) is None  # bad winner
    assert module.final_table([1, 2, 3, 4], 2, rows[:2] + [(2, 'CANCELLED', 1, 4, None)]) is None
