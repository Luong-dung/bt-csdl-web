"""Result and W47 referee races through independent PostgreSQL connections."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep

import pytest
from sqlalchemy import select, text

from core.tournaments import lock_tournament
from modules.identity.models import AuditLog, RoleAssignment
from modules.tournaments.models import Tournament
from test_catalog_api import make_client
from test_registration_concurrency import session_factory
from referee_helpers import grant_referee as grant_referee_api
from test_permissions import access
from test_match_foundation import match_case
from test_bracket_foundation import bracket_case
from test_bracket_results import bracket_results, path, result, state, match_logs

pytestmark = pytest.mark.postgres


def submit(factory, headers, ids, key='first', scores=(2, 0), name='organizer'):
    with make_client(factory, logged_in=False) as client:
        return result(client, headers, ids, key, scores, name).status_code


def grant_referee(factory, headers, tid, user_id):
    with make_client(factory, logged_in=False) as client:
        return grant_referee_api(client, headers, tid, user_id).status_code


def revoke_referee(factory, headers, tid, assignment_id):
    with make_client(factory, logged_in=False) as client:
        return client.delete(f'/api/v1/tournaments/{tid}/referees/{assignment_id}',
                             headers=headers('organizer')).status_code


def wait_for_lock_waiters(factory, expected):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with factory() as db:
            count = db.scalar(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "AND wait_event_type = 'Lock' AND query ILIKE '%tournaments%'"
            ))
        if count >= expected:
            return True
        sleep(0.025)
    return False


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


def test_concurrent_referee_grants_create_one_assignment_and_one_audit(access, session_factory, bracket_results):
    _, headers, users, _, roles = access
    tid = bracket_results['tid']
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: grant_referee(session_factory, headers, tid, users['referee']), range(2)))
    assert sorted(codes) == [201, 409]
    with session_factory() as db:
        assignments = list(db.scalars(select(RoleAssignment).where(
            RoleAssignment.user_id == users['referee'],
            RoleAssignment.role_id == roles['REFEREE'],
            RoleAssignment.scope_type == 'TOURNAMENT',
            RoleAssignment.scope_id == tid,
            RoleAssignment.revoked_at.is_(None),
        )))
        audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'role_assignment')))
    assert len(assignments) == 1
    assert [audit.action for audit in audits] == ['ROLE_ASSIGNMENT_GRANTED']
    assert audits[0].details['tournament_id'] == tid


def test_result_rechecks_referee_revocation_before_advancing_slot(access, session_factory, bracket_results):
    client, headers, users, _, _ = access
    ids = bracket_results
    created = grant_referee_api(client, headers, ids['tid'], users['referee'])
    assert created.status_code == 201, created.text
    assignment_id = created.json()['assignment_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        with session_factory.begin() as holder:
            lock_tournament(holder, ids['tid'])
            revoke = pool.submit(revoke_referee, session_factory, headers, ids['tid'], assignment_id)
            assert wait_for_lock_waiters(session_factory, 1), 'revoke request never waited for tournament lock'
            result_request = pool.submit(submit, session_factory, headers, ids, name='referee')
            assert wait_for_lock_waiters(session_factory, 2), 'result request never waited behind revocation'
        assert revoke.result(timeout=10) == 200
        assert result_request.result(timeout=10) == 403
    assert state(session_factory, ids['first'])[0] == 'ONGOING'
    assert state(session_factory, ids['final']) == ('PENDING', None, None, None)
    assert match_logs(session_factory) == []
    with session_factory() as db:
        assignment = db.get(RoleAssignment, assignment_id)
        assert assignment.revoked_by == users['organizer'] and assignment.revoked_at is not None
        audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'role_assignment')
                                 .order_by(AuditLog.log_id)))
    assert [audit.action for audit in audits] == ['ROLE_ASSIGNMENT_GRANTED', 'ROLE_ASSIGNMENT_REVOKED']
    assert all(audit.details['tournament_id'] == ids['tid'] for audit in audits)
