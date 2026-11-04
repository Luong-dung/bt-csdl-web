"""W45-02 races on real PostgreSQL connections (fixture savepoints cannot simulate row locks)."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event

from core.tournaments import lock_tournament
from modules.identity.models import RoleAssignment
from modules.tournaments.models import Match
from test_catalog_api import make_client
from test_match_foundation import match_case
from test_match_result_api import ongoing, result_logs, stored, url
from test_permissions import access
from test_registration_concurrency import session_factory

pytestmark = pytest.mark.postgres


def submit(session_factory, headers, name, ids, scores):
    with make_client(session_factory, logged_in=False) as client:
        return client.put(url(ids['tid'], ids['match']), headers=headers(name),
                          json={'score_team1': scores[0], 'score_team2': scores[1]}).status_code


def test_two_different_results_only_one_is_recorded(access, session_factory, ongoing):
    _, headers, _, teams, _ = access
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda s: submit(session_factory, headers, 'admin', ongoing, s), [(2, 0), (0, 2)]))
    assert sorted(codes) == [200, 409]
    status, s1, s2, winner = stored(session_factory, ongoing['match'])
    assert status == 'COMPLETED' and winner == (teams['Alpha'] if s1 > s2 else teams['Beta'])
    assert len(result_logs(session_factory)) == 1


def test_same_result_twice_concurrently_audits_once(access, session_factory, ongoing):
    _, headers, *_ = access
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda s: submit(session_factory, headers, 'admin', ongoing, s), [(1, 0), (1, 0)]))
    assert codes == [200, 200]
    assert len(result_logs(session_factory)) == 1


@pytest.mark.parametrize('change,expected', [
    ('cancel_match', 409), ('finish_tournament', 409), ('revoke_referee', 403),
])
def test_result_rechecks_after_waiting_for_tournament_lock(access, session_factory, ongoing, change, expected):
    _, headers, users, _, roles = access
    with session_factory.begin() as db:
        assignment = RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                                    scope_type='TOURNAMENT', scope_id=ongoing['tid'])
        db.add(assignment)
        db.flush()
        aid = assignment.assignment_id
    engine = session_factory.kw['bind']
    waiting = Event()

    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()

    with session_factory() as holder:
        tournament = lock_tournament(holder, ongoing['tid'])
        event.listen(engine, 'before_cursor_execute', notice)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(submit, session_factory, headers, 'referee', ongoing, (1, 0))
                try:
                    assert waiting.wait(3), 'result writer never queued on the tournament lock'
                    assert not future.done()
                    if change == 'cancel_match':
                        holder.get(Match, ongoing['match']).status = 'CANCELLED'
                    elif change == 'finish_tournament':
                        tournament.status = 'COMPLETED'
                    else:
                        holder.delete(holder.get(RoleAssignment, aid))
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == expected
        finally:
            event.remove(engine, 'before_cursor_execute', notice)
    assert stored(session_factory, ongoing['match'])[3] is None
    assert result_logs(session_factory) == []
