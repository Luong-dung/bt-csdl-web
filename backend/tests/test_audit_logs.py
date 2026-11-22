"""W47-02: one audit writer (tournament_id/resource_id derived from details), catalog audit, read API."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, func, select

from core.audit import derive_ids, record_audit
from modules.catalog.models import Publisher
from modules.identity.models import AuditLog
from modules.tournaments.models import Tournament
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres
ADMIN = '/api/v1/admin/audit-logs'


def tlogs(tid):
    return f'/api/v1/tournaments/{tid}/audit-logs'


def count(factory):
    with factory() as db:
        return db.scalar(select(func.count()).select_from(AuditLog))


def seed_activity(client, headers, users, ids):
    """Real API writes: a referee grant and a match start in tournament A, a stage in tournament B."""
    assert client.post(f"/api/v1/tournaments/{ids['tid']}/referees", headers=headers('organizer'),
                       json={'user_id': users['referee']}).status_code == 201
    assert client.post(f"/api/v1/tournaments/{ids['tid']}/matches/{ids['match']}/status",
                       headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    assert client.post(f"/api/v1/tournaments/{ids['other']}/stages", headers=headers('organizer'),
                       json={'name': 'B-stage', 'sequence_order': 2}).status_code == 201


# ---------- writer ----------

@pytest.mark.parametrize('resource,details,expected', [
    ('match', {'tournament_id': 3, 'match_id': 9}, (3, 9)),
    ('role_assignment', {'tournament_id': None, 'after': {'assignment_id': 4}}, (None, 4)),
    ('role_assignment', {'tournament_id': 2, 'before': {'assignment_id': 5}, 'after': None}, (2, 5)),
    ('tournament_roster', {'tournament_id': 1, 'locked_at': 'x'}, (1, None)),
    ('team_membership', {'team_id': 1, 'membership_id': 8}, (None, 8)),
    ('unknown', {'tournament_id': 7, 'x_id': 1}, (7, None)),
    ('match', {'tournament_id': '3', 'match_id': True}, (None, None)),  # only real ints
    ('match', None, (None, None)),
])
def test_derive_ids(resource, details, expected):
    assert derive_ids(resource, details) == expected


def test_api_writes_fill_scope_columns(access, session_factory, match_case):
    client, headers, users, *_ = access
    seed_activity(client, headers, users, match_case)
    with session_factory() as db:
        rows = db.execute(select(AuditLog.resource, AuditLog.tournament_id, AuditLog.resource_id)
                          .order_by(AuditLog.log_id)).all()
    by_resource = {r.resource: r for r in rows}
    assert by_resource['role_assignment'].tournament_id == match_case['tid']
    assert by_resource['match'] == ('match', match_case['tid'], match_case['match'])
    assert by_resource['tournament_stage'].tournament_id == match_case['other']


# ---------- catalog audit ----------

def test_catalog_create_update_delete_are_audited(access, session_factory):
    client, headers, users, *_ = access
    auth = headers('admin')
    created = client.post('/api/v1/catalog/publishers', headers=auth, json={'name': 'Audit Pub'})
    assert created.status_code == 201
    pid = created.json()['publisher_id']
    assert client.patch(f'/api/v1/catalog/publishers/{pid}', headers=auth, json={'name': 'Audit Pub 2'}).status_code == 200
    assert client.delete(f'/api/v1/catalog/publishers/{pid}', headers=auth).status_code == 204
    logs = client.get(ADMIN + f'?resource=publisher&resource_id={pid}', headers=auth).json()
    assert [l['action'] for l in logs] == ['CATALOG_PUBLISHER_DELETED', 'CATALOG_PUBLISHER_UPDATED',
                                           'CATALOG_PUBLISHER_CREATED']
    assert {l['actor']['user_id'] for l in logs} == {users['admin']}
    deleted, updated, created_log = (l['details'] for l in logs)
    assert created_log['before'] is None and created_log['after']['name'] == 'Audit Pub'
    assert updated['before']['name'] == 'Audit Pub' and updated['after']['name'] == 'Audit Pub 2'
    assert deleted['before']['name'] == 'Audit Pub 2' and deleted['after'] is None


def test_rejected_catalog_write_has_no_audit(access, session_factory):
    client, headers, *_ = access
    client.post('/api/v1/catalog/publishers', headers=headers('admin'), json={'name': 'Dup'})
    before = count(session_factory)
    assert client.post('/api/v1/catalog/publishers', headers=headers('admin'), json={'name': 'Dup'}).status_code == 409
    assert client.post('/api/v1/catalog/publishers', headers=headers('viewer'), json={'name': 'X'}).status_code == 403
    assert count(session_factory) == before


def test_catalog_audit_failure_rolls_back_the_write(access, session_factory):
    client, headers, *_ = access
    engine = session_factory.kw['bind']

    def fail(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('INSERT INTO AUDIT_LOGS'):
            raise RuntimeError('audit down')
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError):
            client.post('/api/v1/catalog/publishers', headers=headers('admin'), json={'name': 'Ghost'})
    finally:
        event.remove(engine, 'before_cursor_execute', fail)
    with session_factory() as db:
        assert db.scalar(select(Publisher).where(Publisher.name == 'Ghost')) is None


# ---------- read API ----------

def test_manager_sees_only_own_tournament_newest_first(access, session_factory, match_case):
    client, headers, users, *_ = access
    seed_activity(client, headers, users, match_case)
    response = client.get(tlogs(match_case['tid']), headers=headers('organizer'))
    assert response.status_code == 200
    body = response.json()
    # The fixture created the tournament through the API, so its creation is logged too.
    assert response.headers['x-total-count'] == str(len(body)) == '3'
    assert [l['action'] for l in body] == ['MATCH_STARTED', 'ROLE_ASSIGNMENT_GRANTED', 'TOURNAMENT_CREATED']
    assert all(l['tournament_id'] == match_case['tid'] for l in body)
    assert body[0]['actor'] == {'user_id': users['organizer'], 'username': 'organizer'}
    other = client.get(tlogs(match_case['other']), headers=headers('organizer')).json()
    assert [l['resource'] for l in other] == ['tournament_stage', 'tournament']


@pytest.mark.parametrize('who,code', [(None, 401), ('viewer', 403), ('referee', 403), ('manager', 403)])
def test_tournament_logs_need_manager(access, match_case, who, code):
    client, headers, *_ = access
    assert client.get(tlogs(match_case['tid']), headers=headers(who) if who else {}).status_code == code


def test_manager_of_another_tournament_cannot_view_logs(access, session_factory, match_case):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        db.get(Tournament, match_case['tid']).created_by = users['admin']
    assert client.get(tlogs(match_case['tid']), headers=headers('organizer')).status_code == 403
    assert client.get(tlogs(match_case['other']), headers=headers('organizer')).status_code == 200
    assert client.get(tlogs(match_case['tid']), headers=headers('admin')).status_code == 200


def test_admin_logs_are_admin_only(access, match_case):
    client, headers, *_ = access
    assert client.get(ADMIN).status_code == 401
    for who in ('organizer', 'viewer', 'referee'):
        assert client.get(ADMIN, headers=headers(who)).status_code == 403
    assert client.get(ADMIN, headers=headers('admin')).status_code == 200
    assert client.get(tlogs(999999), headers=headers('admin')).status_code == 404


def test_filters(access, session_factory, match_case):
    client, headers, users, *_ = access
    seed_activity(client, headers, users, match_case)
    auth = headers('admin')

    def actions(query):
        response = client.get(ADMIN + query, headers=auth)
        assert response.status_code == 200, response.text
        return [l['resource'] for l in response.json()]
    assert actions(f"?tournament_id={match_case['tid']}&resource=match") == ['match']
    assert actions('?action=ROLE_ASSIGNMENT_GRANTED') == ['role_assignment']
    assert actions(f"?actor_id={users['admin']}") == []
    assert actions(f"?resource=match&resource_id={match_case['match']}") == ['match']
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')
    assert actions(f'?since={future}') == []
    # 2 tournament creations from the fixture + 3 seeded writes.
    assert len(actions(f'?since={past}&until={future}')) == 5
    for bad in ('?since=2026-11-17T00:00:00', f'?since={future}&until={past}', '?limit=0', '?limit=101',
                '?actor_id=0', '?resource=' + 'x' * 101):
        assert client.get(ADMIN + bad, headers=auth).status_code == 422, bad


def test_pagination_is_stable_and_total_exact(access, session_factory):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        for i in range(7):
            record_audit(db, users['admin'], 'TEST', 'publisher', {'publisher_id': i + 1})
    auth = headers('admin')
    pages = [client.get(ADMIN + f'?resource=publisher&offset={o}&limit=3', headers=auth) for o in (0, 3, 6)]
    assert {p.headers['x-total-count'] for p in pages} == {'7'}
    ids = [l['log_id'] for p in pages for l in p.json()]
    assert len(ids) == len(set(ids)) == 7 and ids == sorted(ids, reverse=True)


def test_sensitive_keys_are_scrubbed_and_reads_write_nothing(access, session_factory, match_case):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        db.add(AuditLog(user_id=users['viewer'], action='LEGACY', resource='tournament', tournament_id=match_case['tid'],
                        details={'tournament_id': match_case['tid'], 'email': 'x@y.z',
                                 'after': {'Password_Hash': 'h', 'list': [{'token': 't', 'keep': 1}]}}))
    before = count(session_factory)
    body = client.get(tlogs(match_case['tid']), headers=headers('organizer')).json()
    assert body[0]['details'] == {'tournament_id': match_case['tid'], 'after': {'list': [{'keep': 1}]}}
    assert 'email' not in str(body)
    client.get(ADMIN, headers=headers('admin'))
    assert count(session_factory) == before


def test_deleted_actor_shows_no_actor(access, session_factory):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        record_audit(db, None, 'SYSTEM', 'publisher', {'publisher_id': 1})
    assert client.get(ADMIN + '?action=SYSTEM', headers=headers('admin')).json()[0]['actor'] is None


def test_audit_reads_are_not_cached_and_capabilities(access, match_case):
    client, headers, *_ = access
    for response in (client.get(tlogs(match_case['tid']), headers=headers('organizer')),
                     client.get(tlogs(match_case['tid']), headers=headers('viewer')),
                     client.get(ADMIN, headers=headers('admin')), client.get(ADMIN)):
        assert response.headers.get('cache-control') == 'private, no-store'
    caps = f"/api/v1/tournaments/{match_case['tid']}/capabilities"
    assert client.get(caps, headers=headers('organizer')).json()['can_view_audit'] is True
    assert client.get(caps, headers=headers('viewer')).json()['can_view_audit'] is False
    assert client.get('/api/v1/auth/capabilities', headers=headers('admin')).json()['can_view_audit'] is True
    assert client.get('/api/v1/auth/capabilities', headers=headers('organizer')).json()['can_view_audit'] is False
