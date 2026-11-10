"""W46-02 result/slot/audit races through real HTTP and independent PostgreSQL connections."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import delete, event, select

from core.tournaments import lock_tournament
from modules.identity.models import AuditLog, RoleAssignment
from modules.tournaments.models import Tournament
from test_catalog_api import make_client
from test_registration_concurrency import session_factory
from test_permissions import access
from test_match_foundation import match_case
from test_bracket_foundation import bracket_case
from test_bracket_results import bracket_results, path, result, state, match_logs

pytestmark = pytest.mark.postgres


def submit(factory, headers, ids, key='first', scores=(2, 0), name='organizer'):
    with make_client(factory, logged_in=False) as client:
        return result(client, headers, ids, key, scores, name).status_code


def change_status(factory, headers, ids, status):
    with make_client(factory, logged_in=False) as client:
        return client.post(f"/api/v1/tournaments/{ids['tid']}/status", headers=headers('organizer'),
                           json={'status': status}).status_code


def test_two_semifinal_results_keep_both_final_slots(access, session_factory, bracket_results):
    _, headers, *_ = access
    ids = bracket_results
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit, session_factory, headers, ids)
        second = pool.submit(submit, session_factory, headers, ids, 'second', (0, 2))
        assert [first.result(timeout=10), second.result(timeout=10)] == [200, 200]
    assert state(session_factory, ids['final']) == ('PENDING', ids['alpha'], ids['delta'], None)
    logs = match_logs(session_factory)
    assert len(logs) == 2 and {l.details['advancement']['slot'] for l in logs} == {1, 2}


@pytest.mark.parametrize('same', [False, True])
def test_concurrent_result_replay_never_overwrites_slot_or_duplicates_audit(access, session_factory, bracket_results, same):
    _, headers, *_ = access
    ids = bracket_results
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda scores: submit(session_factory, headers, ids, scores=scores),
                              [(2, 0), (2, 0) if same else (0, 2)]))
    assert sorted(codes) == ([200, 200] if same else [200, 409])
    source = state(session_factory, ids['first'])
    assert source[0] == 'COMPLETED' and state(session_factory, ids['final'])[1] == source[3]
    assert len(match_logs(session_factory)) == 1


def test_final_result_races_with_tournament_completion(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    assert submit(session_factory, headers, ids) == 200
    assert submit(session_factory, headers, ids, 'second', (0, 2)) == 200
    assert client.post(path(ids, 'final')+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        finish = pool.submit(change_status, session_factory, headers, ids, 'COMPLETED')
        score = pool.submit(submit, session_factory, headers, ids, 'final')
        code = finish.result(timeout=10)
        assert code in (200, 409) and score.result(timeout=10) == 200
    assert state(session_factory, ids['final']) == ('COMPLETED', ids['alpha'], ids['delta'], ids['alpha'])
    with session_factory() as db:
        assert db.get(Tournament, ids['tid']).status == ('COMPLETED' if code == 200 else 'ONGOING')
        closes = list(db.scalars(select(AuditLog).where(AuditLog.action == 'TOURNAMENT_STATUS_CHANGED')))
        assert len(closes) == (1 if code == 200 else 0)
    assert len([l for l in match_logs(session_factory) if l.action == 'MATCH_RESULT_SUBMITTED']) == 3


def test_cancel_tournament_races_with_semifinal_result(access, session_factory, bracket_results):
    _, headers, *_ = access
    ids = bracket_results
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel = pool.submit(change_status, session_factory, headers, ids, 'CANCELLED')
        score = pool.submit(submit, session_factory, headers, ids)
        assert cancel.result(timeout=10) == 200
        code = score.result(timeout=10)
    assert code in (200, 409)
    assert state(session_factory, ids['first'])[0] == ('COMPLETED' if code == 200 else 'ONGOING')
    assert state(session_factory, ids['final'])[1] == (ids['alpha'] if code == 200 else None)
    assert len(match_logs(session_factory)) == (1 if code == 200 else 0)
    with session_factory() as db:
        assert db.get(Tournament, ids['tid']).status == 'CANCELLED'


def test_result_rechecks_referee_revocation_before_advancing_slot(access, session_factory, bracket_results):
    _, headers, users, _, roles = access
    ids = bracket_results
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'], scope_type='TOURNAMENT', scope_id=ids['tid']))
    engine = session_factory.kw['bind']
    waiting = Event()
    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with session_factory.begin() as holder:
                lock_tournament(holder, ids['tid'])
                holder.execute(delete(RoleAssignment).where(RoleAssignment.user_id == users['referee']))
                event.listen(engine, 'before_cursor_execute', notice)
                future = pool.submit(submit, session_factory, headers, ids, name='referee')
                assert waiting.wait(5)
            assert future.result(timeout=10) == 403
        finally:
            event.remove(engine, 'before_cursor_execute', notice)
    assert state(session_factory, ids['first'])[0] == 'ONGOING'
    assert state(session_factory, ids['final']) == ('PENDING', None, None, None)
    assert match_logs(session_factory) == []
