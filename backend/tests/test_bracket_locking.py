"""Real connections prove bracket helpers recheck permissions after the shared parent lock."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event

from core.brackets import lock_bracket_context, lock_bracket_match_context
from core.matches import can_submit_result
from core.tournaments import lock_tournament
from modules.identity.models import RoleAssignment, User
from test_registration_concurrency import session_factory
from test_permissions import access
from test_match_foundation import match_case
from test_bracket_foundation import bracket_case, add_bracket, add_node

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('operation,role', [('create', 'ORGANIZER'), ('result', 'REFEREE')])
def test_revoked_assignment_is_rechecked_after_bracket_lock(access, session_factory, bracket_case, operation, role):
    _, _, users, _, roles = access
    tid = bracket_case['tid']
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles[role], scope_type='TOURNAMENT', scope_id=tid))
        bracket = add_bracket(db, bracket_case, users, 4)
        add_node(db, bracket, 2, 1)
        source = add_node(db, bracket, 1, 1)
        add_node(db, bracket, 1, 2)
        mid = source.match_id
    attempted = Event()
    engine = session_factory.kw['bind']

    def notice_lock(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            attempted.set()

    def waiting_call():
        with session_factory() as db:
            actor = db.get(User, users['referee'])
            try:
                if operation == 'create':
                    lock_bracket_context(db, tid, actor)
                else:
                    lock_bracket_match_context(db, tid, mid, actor, can_submit_result)
            except HTTPException as error:
                return error.status_code
            return 200

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with session_factory.begin() as db:
                lock_tournament(db, tid)
                db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == users['referee']))
                event.listen(engine, 'before_cursor_execute', notice_lock)
                future = pool.submit(waiting_call)
                assert attempted.wait(5), 'request never reached the tournament lock'
            assert future.result(timeout=10) == 403
        finally:
            event.remove(engine, 'before_cursor_execute', notice_lock)
