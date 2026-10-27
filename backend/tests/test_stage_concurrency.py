from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event, select

from core.tournaments import lock_tournament
from modules.identity.models import RoleAssignment
from modules.tournaments.models import Stage
from test_catalog_api import make_client
from test_permissions import access
from test_registration_concurrency import session_factory
from test_stage_api import logs, path, stage_case

pytestmark = pytest.mark.postgres


def test_concurrent_creates_share_tournament_lock_and_one_order(session_factory, access, stage_case):
    _, headers, *_ = access
    tid, _, _ = stage_case

    def create(name):
        with make_client(session_factory, logged_in=False) as client:
            return client.post(path(tid), headers=headers('organizer'), json={'name': name, 'sequence_order': 3}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ['Semi', 'Final']))
    assert sorted(results) == [201, 409]
    with session_factory() as db:
        assert len(list(db.scalars(select(Stage).where(Stage.tournament_id == tid)))) == 3
    assert len(logs(session_factory)) == 1


@pytest.mark.parametrize('change,expected', [('lifecycle', 409), ('permission', 403)])
def test_reorder_rechecks_state_and_scope_after_parent_lock(session_factory, access, stage_case, change, expected):
    _, headers, users, _, roles = access
    tid, _, ids = stage_case
    with session_factory.begin() as db:
        assignment = RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=tid)
        db.add(assignment)
        db.flush()
        aid = assignment.assignment_id
    engine = session_factory.kw['bind']
    waiting = Event()

    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()

    def reorder():
        with make_client(session_factory, logged_in=False) as client:
            return client.put(path(tid) + '/order', headers=headers('viewer'), json={'stage_ids': ids[:2][::-1]}).status_code

    with session_factory() as holder:
        tournament = lock_tournament(holder, tid)
        event.listen(engine, 'before_cursor_execute', notice)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(reorder)
                try:
                    assert waiting.wait(3), 'stage writer never attempted the parent lock'
                    assert not future.done()
                    if change == 'lifecycle':
                        tournament.status = 'ONGOING'
                    else:
                        holder.delete(holder.get(RoleAssignment, aid))
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == expected
        finally:
            event.remove(engine, 'before_cursor_execute', notice)
    with session_factory() as db:
        assert [s.stage_id for s in db.scalars(select(Stage).where(Stage.tournament_id == tid).order_by(Stage.sequence_order))] == ids[:2]
    assert logs(session_factory) == []


def test_two_reorders_leave_one_complete_permutation(session_factory, access, stage_case):
    _, headers, *_ = access
    tid, _, ids = stage_case
    # Use sparse orders so neither request can be dismissed as an initial no-op.
    with session_factory.begin() as db:
        db.get(Stage, ids[0]).sequence_order = 5
        db.get(Stage, ids[1]).sequence_order = 9

    def reorder(order):
        with make_client(session_factory, logged_in=False) as client:
            response = client.put(path(tid) + '/order', headers=headers('organizer'), json={'stage_ids': order})
            assert response.status_code == 200, response.text
            assert [s['stage_id'] for s in response.json()] == order
            return order

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(reorder, [ids[:2], ids[:2][::-1]]))
    with session_factory() as db:
        rows = list(db.scalars(select(Stage).where(Stage.tournament_id == tid).order_by(Stage.sequence_order)))
        assert [s.sequence_order for s in rows] == [1, 2]
        assert [s.stage_id for s in rows] in [ids[:2], ids[:2][::-1]]
    assert len(logs(session_factory)) == 2
