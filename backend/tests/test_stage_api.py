from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog, RoleAssignment
from modules.tournaments.models import Match, Stage, Tournament
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


def path(tid):
    return f'/api/v1/tournaments/{tid}/stages'


def logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament_stage').order_by(AuditLog.log_id)))


@pytest.fixture
def stage_case(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    other = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        rows = [Stage(tournament_id=tid, name='Group', sequence_order=1),
                Stage(tournament_id=tid, name='Final', sequence_order=2),
                Stage(tournament_id=other, name='Other', sequence_order=1)]
        db.add_all(rows)
        db.flush()
        ids = [row.stage_id for row in rows]
    return tid, other, ids


def test_public_list_detail_pagination_and_parent_scope(access, stage_case):
    client, *_ = access
    tid, other, ids = stage_case
    response = client.get(path(tid), params={'limit': 1, 'offset': 1})
    assert response.status_code == 200 and response.headers['x-total-count'] == '2'
    assert response.json() == [{'stage_id': ids[1], 'tournament_id': tid, 'name': 'Final', 'sequence_order': 2}]
    assert client.get(f'{path(tid)}/{ids[0]}').json()['name'] == 'Group'
    assert client.get(f'{path(tid)}/{ids[2]}').status_code == 404
    assert len(client.get(path(other)).json()) == 1
    assert client.get(path(tid), params={'offset': 100}).headers['x-total-count'] == '2'


def test_empty_list_and_order_are_valid_noops(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    assert client.get(path(tid)).json() == []
    assert client.put(path(tid) + '/order', headers=headers('organizer'), json={'stage_ids': []}).json() == []
    assert logs(session_factory) == []


def test_crud_and_atomic_audit(access, session_factory):
    client, headers, users, *_ = access
    tid = organizer_tournament(client, headers)
    response = client.post(path(tid), headers=headers('organizer'), json={'name': '  Vòng bảng  ', 'sequence_order': 4})
    assert response.status_code == 201, response.text
    sid = response.json()['stage_id']
    assert response.json()['name'] == 'Vòng bảng'
    response = client.patch(f'{path(tid)}/{sid}', headers=headers('organizer'), json={'name': 'Playoffs', 'sequence_order': 7})
    assert response.status_code == 200 and response.json()['sequence_order'] == 7
    # Identical PATCH does not create a second success audit.
    assert client.patch(f'{path(tid)}/{sid}', headers=headers('organizer'), json={'name': 'Playoffs'}).status_code == 200
    response = client.delete(f'{path(tid)}/{sid}', headers=headers('organizer'))
    assert response.status_code == 204 and response.content == b''
    assert client.get(f'{path(tid)}/{sid}').status_code == 404
    entries = logs(session_factory)
    assert [entry.action for entry in entries] == ['TOURNAMENT_STAGE_CREATED', 'TOURNAMENT_STAGE_UPDATED', 'TOURNAMENT_STAGE_DELETED']
    assert all(entry.user_id == users['organizer'] and entry.details['tournament_id'] == tid for entry in entries)
    assert entries[0].details['before'] is None
    assert entries[1].details['before']['sequence_order'] == 4
    assert entries[1].details['after']['name'] == 'Playoffs'
    assert entries[2].details['before']['stage_id'] == sid and entries[2].details['after'] is None


@pytest.mark.parametrize('kind', ['admin', 'creator', 'scoped', 'global_admin', 'global_organizer_owner', 'global_organizer_other', 'outsider', 'wrong_scope', 'creatorless'])
def test_stage_rights_use_tournament_checker(access, session_factory, stage_case, kind):
    client, headers, users, _, roles = access
    tid, other, _ = stage_case
    actor = 'organizer' if kind == 'creator' else 'admin' if kind == 'admin' else 'viewer'
    with session_factory.begin() as db:
        if kind == 'scoped' or kind == 'wrong_scope':
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT',
                                  scope_id=tid if kind == 'scoped' else other))
        if kind in ('global_admin', 'global_organizer_owner', 'global_organizer_other'):
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ADMIN' if kind == 'global_admin' else 'ORGANIZER'], scope_type='GLOBAL'))
            if kind == 'global_organizer_owner':
                db.get(Tournament, tid).created_by = users['viewer']
        if kind == 'creatorless':
            db.get(Tournament, tid).created_by = None
            db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=tid))
    allowed = kind in ('admin', 'creator', 'scoped', 'global_admin', 'global_organizer_owner')
    hint = client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers(actor))
    assert hint.json()['can_manage_stages'] == allowed
    assert hint.headers['cache-control'] == 'private, no-store'
    response = client.post(path(tid), headers=headers(actor), json={'name': 'New', 'sequence_order': 3})
    assert response.status_code == (201 if allowed else 403)
    assert len(logs(session_factory)) == int(allowed)


@pytest.mark.parametrize('method,suffix,body', [('POST', '', {'name': 'New', 'sequence_order': 3}),
    ('PATCH', '/first', {'name': 'Rename'}), ('DELETE', '/first', None), ('PUT', '/order', {'stage_ids': []})])
def test_all_writers_require_auth_and_deny_viewer(access, session_factory, stage_case, method, suffix, body):
    client, headers, *_ = access
    tid, _, ids = stage_case
    endpoint = path(tid) + suffix.replace('first', str(ids[0]))
    for auth, expected in [(None, 401), (headers('viewer'), 403)]:
        assert client.request(method, endpoint, headers=auth, json=body).status_code == expected
    assert logs(session_factory) == []


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_lifecycle_blocks_every_stage_writer(access, session_factory, stage_case, state):
    client, headers, *_ = access
    tid, _, ids = stage_case
    with session_factory.begin() as db:
        db.get(Tournament, tid).status = state
    auth = headers('admin')
    assert not client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=auth).json()['can_manage_stages']
    requests = [('POST', path(tid), {'name': 'New', 'sequence_order': 3}),
                ('PATCH', f'{path(tid)}/{ids[0]}', {'name': 'Rename'}),
                ('DELETE', f'{path(tid)}/{ids[0]}', None),
                ('PUT', path(tid) + '/order', {'stage_ids': ids[:2][::-1]})]
    for method, endpoint, body in requests:
        assert client.request(method, endpoint, headers=auth, json=body).status_code == 409
    assert client.get(path(tid)).status_code == 200
    assert logs(session_factory) == []


def test_roster_lock_does_not_lock_stage_configuration(access, session_factory, stage_case):
    client, headers, *_ = access
    tid, _, _ = stage_case
    with session_factory.begin() as db:
        db.get(Tournament, tid).roster_locked_at = datetime.now(timezone.utc)
    assert client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers('organizer')).json()['can_manage_stages']
    assert client.post(path(tid), headers=headers('organizer'), json={'name': 'Still configurable', 'sequence_order': 3}).status_code == 201


@pytest.mark.parametrize('payload', [
    {'name': '', 'sequence_order': 1}, {'name': '   ', 'sequence_order': 1}, {'name': 'x' * 81, 'sequence_order': 1},
    {'name': 'x', 'sequence_order': 0}, {'name': 'x', 'sequence_order': -1}, {'name': 'x', 'sequence_order': True},
    {'name': 'x', 'sequence_order': '1'}, {'name': 'x', 'sequence_order': 1.5}, {'name': 'x', 'sequence_order': 2147483648},
    {'name': 'x', 'sequence_order': 1, 'tournament_id': 1}, {'name': None, 'sequence_order': 1},
])
def test_create_validation(access, payload):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    assert client.post(path(tid), headers=headers('organizer'), json=payload).status_code == 422


@pytest.mark.parametrize('payload', [{}, {'name': None}, {'sequence_order': None}, {'name': ' '},
                                    {'status': 'ONGOING'}, {'sequence_order': True}])
def test_patch_validation(access, stage_case, payload):
    client, headers, *_ = access
    tid, _, ids = stage_case
    assert client.patch(f'{path(tid)}/{ids[0]}', headers=headers('organizer'), json=payload).status_code == 422


def test_duplicate_orders_and_cross_tournament_mutations_roll_back(access, session_factory, stage_case):
    client, headers, *_ = access
    tid, _, ids = stage_case
    auth = headers('organizer')
    assert client.post(path(tid), headers=auth, json={'name': 'Duplicate', 'sequence_order': 1}).status_code == 409
    assert client.patch(f'{path(tid)}/{ids[0]}', headers=auth, json={'name': 'Must not persist', 'sequence_order': 2}).status_code == 409
    assert client.patch(f'{path(tid)}/{ids[2]}', headers=auth, json={'name': 'Wrong tournament'}).status_code == 404
    assert client.delete(f'{path(tid)}/{ids[2]}', headers=auth).status_code == 404
    assert client.get(f'{path(tid)}/{ids[0]}').json()['name'] == 'Group'
    assert logs(session_factory) == []


def test_reorder_swaps_and_compacts_sparse_orders_without_overflow(access, session_factory, stage_case):
    client, headers, users, *_ = access
    tid, _, ids = stage_case
    with session_factory.begin() as db:
        db.get(Stage, ids[1]).sequence_order = 2147483647
    auth = headers('organizer')
    response = client.put(path(tid) + '/order', headers=auth, json={'stage_ids': [ids[1], ids[0]]})
    assert response.status_code == 200, response.text
    assert [(s['stage_id'], s['sequence_order']) for s in response.json()] == [(ids[1], 1), (ids[0], 2)]
    # A second permutation exercises swapping immediate-UNIQUE values 1 and 2.
    assert client.put(path(tid) + '/order', headers=auth, json={'stage_ids': ids[:2]}).status_code == 200
    assert client.put(path(tid) + '/order', headers=auth, json={'stage_ids': ids[:2]}).status_code == 200
    entries = logs(session_factory)
    assert len(entries) == 2 and all(e.action == 'TOURNAMENT_STAGES_REORDERED' for e in entries)
    assert entries[0].user_id == users['organizer']
    assert entries[0].details['before'][1]['sequence_order'] == 2147483647
    assert entries[0].details['after'][0]['stage_id'] == ids[1]


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'foreign', 'unknown', 'extra', 'wrong_type', 'too_large'])
def test_reorder_requires_exact_ids_and_valid_body(access, session_factory, stage_case, kind):
    client, headers, *_ = access
    tid, _, ids = stage_case
    values = {'missing': ids[:1], 'duplicate': [ids[0], ids[0]], 'foreign': [ids[0], ids[2]],
              'unknown': [ids[0], 2147483647], 'extra': ids, 'wrong_type': [True], 'too_large': list(range(1, 1002))}[kind]
    response = client.put(path(tid) + '/order', headers=headers('organizer'), json={'stage_ids': values})
    assert response.status_code == 422, response.text
    assert [s['stage_id'] for s in client.get(path(tid)).json()] == ids[:2]
    assert logs(session_factory) == []


def test_deleting_stage_with_match_is_blocked_at_api_and_database(access, session_factory, stage_case):
    client, headers, *_ = access
    tid, _, ids = stage_case
    with session_factory.begin() as db:
        db.add(Match(tournament_id=tid, stage_id=ids[0], round_no=1))
    assert client.delete(f'{path(tid)}/{ids[0]}', headers=headers('organizer')).status_code == 409
    with session_factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(delete(Stage).where(Stage.stage_id == ids[0]))
        db.rollback()
        assert db.scalar(select(Match.match_id)) is not None
    assert logs(session_factory) == []


@pytest.mark.parametrize('operation', ['create', 'update', 'delete', 'reorder'])
def test_audit_failure_rolls_back_entire_stage_change(access, session_factory, stage_case, operation):
    client, headers, *_ = access
    tid, _, ids = stage_case
    with session_factory() as db:
        engine = db.get_bind()

    def fail_audit(connection, cursor, statement, parameters, context, executemany):
        if 'INSERT INTO audit_logs' in statement:
            raise RuntimeError('stage audit unavailable')
    event.listen(engine, 'before_cursor_execute', fail_audit)
    try:
        method, endpoint, body = {
            'create': ('POST', path(tid), {'name': 'New', 'sequence_order': 3}),
            'update': ('PATCH', f'{path(tid)}/{ids[0]}', {'name': 'Changed'}),
            'delete': ('DELETE', f'{path(tid)}/{ids[0]}', None),
            'reorder': ('PUT', path(tid) + '/order', {'stage_ids': ids[:2][::-1]}),
        }[operation]
        with pytest.raises(RuntimeError, match='stage audit unavailable'):
            client.request(method, endpoint, headers=headers('organizer'), json=body)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_audit)
    assert [(s['name'], s['sequence_order']) for s in client.get(path(tid)).json()] == [('Group', 1), ('Final', 2)]
    assert logs(session_factory) == []


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'offset=-1', 'offset=2147483648'])
def test_list_pagination_validation(access, stage_case, query):
    client, *_ = access
    assert client.get(path(stage_case[0]) + '?' + query).status_code == 422


@pytest.mark.parametrize('tid,sid,expected', [(0, None, 422), (2147483648, None, 422),
                                            (999999, None, 404), (None, 0, 422),
                                            (None, 2147483648, 422), (None, 999999, 404)])
def test_parent_and_stage_resource_ids(access, stage_case, tid, sid, expected):
    client, *_ = access
    endpoint = path(stage_case[0] if tid is None else tid)
    if sid is not None:
        endpoint += f'/{sid}'
    assert client.get(endpoint).status_code == expected


def test_more_than_fifty_stages_can_be_read_and_reordered(access, session_factory):
    client, headers, *_ = access
    tid = organizer_tournament(client, headers)
    with session_factory.begin() as db:
        db.add_all(Stage(tournament_id=tid, name=f'Stage {i}', sequence_order=i) for i in range(1, 56))
    first = client.get(path(tid))
    second = client.get(path(tid) + '?offset=50')
    assert first.headers['x-total-count'] == second.headers['x-total-count'] == '55'
    assert len(first.json()) == 50 and len(second.json()) == 5
    ids = [s['stage_id'] for s in first.json() + second.json()]
    result = client.put(path(tid) + '/order', headers=headers('organizer'), json={'stage_ids': ids[::-1]})
    assert result.status_code == 200 and [s['stage_id'] for s in result.json()] == ids[::-1]
