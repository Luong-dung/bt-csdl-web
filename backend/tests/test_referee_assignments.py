"""W47-01: grant/revoke tournament referees and ADMIN role assignments with history and audit."""

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from modules.identity.models import AuditLog, RoleAssignment, User
from modules.tournaments.models import Tournament
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def path(tid, suffix=''):
    return f'/api/v1/tournaments/{tid}/referees{suffix}'


def start(client, ids, auth):
    return client.post(f"/api/v1/tournaments/{ids['tid']}/matches/{ids['match']}/status",
                       headers=auth, json={'status': 'ONGOING'})


def audits(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'role_assignment')
                               .order_by(AuditLog.log_id)))


def grant(client, headers, tid, users, who='organizer', target='referee'):
    return client.post(path(tid), headers=headers(who), json={'user_id': users[target]})


# ---------- tournament referees ----------

def test_grant_lets_referee_start_and_revoke_blocks_again(access, session_factory, match_case):
    client, headers, users, *_ = access
    assert start(client, match_case, headers('referee')).status_code == 403
    created = grant(client, headers, match_case['tid'], users)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body['active'] and body['granted_by'] == users['organizer'] and 'email' not in body
    listed = client.get(path(match_case['tid']), headers=headers('organizer'))
    assert [r['user_id'] for r in listed.json()] == [users['referee']] and listed.headers['x-total-count'] == '1'

    revoked = client.delete(path(match_case['tid'], f"/{body['assignment_id']}"), headers=headers('organizer'))
    assert revoked.status_code == 200 and revoked.json()['active'] is False
    assert start(client, match_case, headers('referee')).status_code == 403
    # History is kept, hidden from the default list.
    assert client.get(path(match_case['tid']), headers=headers('organizer')).json() == []
    history = client.get(path(match_case['tid']) + '?include_revoked=true', headers=headers('organizer')).json()
    assert [r['revoked_by'] for r in history] == [users['organizer']]

    granted_again = grant(client, headers, match_case['tid'], users)
    assert granted_again.status_code == 201
    assert start(client, match_case, headers('referee')).status_code == 200
    actions = [(a.action, a.user_id, a.details['tournament_id']) for a in audits(session_factory)]
    assert actions == [('ROLE_ASSIGNMENT_GRANTED', users['organizer'], match_case['tid']),
                       ('ROLE_ASSIGNMENT_REVOKED', users['organizer'], match_case['tid']),
                       ('ROLE_ASSIGNMENT_GRANTED', users['organizer'], match_case['tid'])]
    assert audits(session_factory)[1].details['before']['revoked_at'] is None
    assert audits(session_factory)[1].details['after']['revoked_at'] is not None


def test_duplicate_active_grant_conflicts_without_audit(access, session_factory, match_case):
    client, headers, users, *_ = access
    assert grant(client, headers, match_case['tid'], users).status_code == 201
    assert grant(client, headers, match_case['tid'], users).status_code == 409
    assert grant(client, headers, match_case['tid'], users, who='admin').status_code == 409
    assert len(audits(session_factory)) == 1


@pytest.mark.parametrize('who,code', [(None, 401), ('viewer', 403), ('manager', 403), ('referee', 403)])
def test_non_managers_cannot_list_grant_or_revoke(access, session_factory, match_case, who, code):
    client, headers, users, *_ = access
    assignment = grant(client, headers, match_case['tid'], users).json()['assignment_id']
    auth = headers(who) if who else {}
    tid = match_case['tid']
    assert client.get(path(tid), headers=auth).status_code == code
    assert client.post(path(tid), headers=auth, json={'user_id': users['admin']}).status_code == code
    assert client.delete(path(tid, f'/{assignment}'), headers=auth).status_code == code
    assert len(audits(session_factory)) == 1


def test_scoped_referee_cannot_grant_other_referees(access, session_factory, match_case):
    client, headers, users, *_ = access
    assert grant(client, headers, match_case['tid'], users).status_code == 201
    assert grant(client, headers, match_case['tid'], users, who='referee', target='admin').status_code == 403


def test_manager_of_other_tournament_cannot_touch_this_one(access, session_factory, match_case):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        db.get(Tournament, match_case['tid']).created_by = users['admin']
    assert grant(client, headers, match_case['tid'], users).status_code == 403
    assignment = grant(client, headers, match_case['tid'], users, who='admin').json()['assignment_id']
    # Assignment of tournament A addressed through tournament B is not found there.
    assert client.delete(path(match_case['other'], f'/{assignment}'), headers=headers('organizer')).status_code == 404


def test_self_grant_unknown_user_and_bad_payload(access, session_factory, match_case):
    client, headers, users, *_ = access
    tid = match_case['tid']
    assert grant(client, headers, tid, users, target='organizer').status_code == 422
    assert client.post(path(tid), headers=headers('organizer'), json={'user_id': 999999}).status_code == 404
    for body in ({}, {'user_id': '5'}, {'user_id': 0}, {'user_id': 1, 'role': 'ADMIN'}):
        assert client.post(path(tid), headers=headers('organizer'), json=body).status_code == 422
    assert client.post(path(999999), headers=headers('organizer'), json={'user_id': users['referee']}).status_code == 404
    assert audits(session_factory) == []


@pytest.mark.parametrize('player', ['viewer', 'manager'])
def test_players_of_the_tournament_cannot_become_referee(access, session_factory, match_case, player):
    client, headers, users, *_ = access
    assert grant(client, headers, match_case['tid'], users, target=player).status_code == 409
    # The same user may referee another tournament where they do not play.
    assert grant(client, headers, match_case['other'], users, target=player).status_code == 201


@pytest.mark.parametrize('status', ['COMPLETED', 'CANCELLED'])
def test_closed_tournament_cannot_grant_but_can_revoke(access, session_factory, match_case, status):
    client, headers, users, *_ = access
    assignment = grant(client, headers, match_case['tid'], users).json()['assignment_id']
    with session_factory.begin() as db:
        db.get(Tournament, match_case['tid']).status = status
    assert grant(client, headers, match_case['tid'], users, target='admin').status_code == 409
    caps = client.get(f"/api/v1/tournaments/{match_case['tid']}/capabilities", headers=headers('organizer')).json()
    assert caps['can_manage_referees'] is False
    assert client.get(path(match_case['tid']), headers=headers('organizer')).status_code == 200
    assert client.delete(path(match_case['tid'], f'/{assignment}'), headers=headers('organizer')).status_code == 200


def test_revoke_twice_conflicts_and_wrong_role_is_not_found(access, session_factory, match_case):
    client, headers, users, _, roles = access
    assignment = grant(client, headers, match_case['tid'], users).json()['assignment_id']
    url = path(match_case['tid'], f'/{assignment}')
    assert client.delete(url, headers=headers('organizer')).status_code == 200
    assert client.delete(url, headers=headers('organizer')).status_code == 409
    with session_factory.begin() as db:
        organizer = RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'],
                                   scope_type='TOURNAMENT', scope_id=match_case['tid'])
        db.add(organizer)
        db.flush()
        other_id = organizer.assignment_id
    # A tournament manager may not revoke an ORGANIZER assignment through the referee API.
    assert client.delete(path(match_case['tid'], f'/{other_id}'), headers=headers('organizer')).status_code == 404
    assert len(audits(session_factory)) == 2


def test_capability_reports_referee_management(access, match_case):
    client, headers, *_ = access
    url = f"/api/v1/tournaments/{match_case['tid']}/capabilities"
    assert client.get(url, headers=headers('organizer')).json()['can_manage_referees'] is True
    assert client.get(url, headers=headers('viewer')).json()['can_manage_referees'] is False


def test_audit_failure_rolls_back_grant(access, session_factory, match_case):
    client, headers, users, *_ = access
    engine = session_factory.kw['bind']

    def fail(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('INSERT INTO AUDIT_LOGS'):
            raise RuntimeError('audit down')
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError):
            grant(client, headers, match_case['tid'], users)
    finally:
        event.remove(engine, 'before_cursor_execute', fail)
    with session_factory() as db:
        assert db.scalar(select(RoleAssignment).where(RoleAssignment.user_id == users['referee'])) is None
    assert start(client, match_case, headers('referee')).status_code == 403


def test_database_allows_one_active_assignment_but_keeps_revoked_history(access, session_factory, match_case):
    _, _, users, _, roles = access
    row = dict(user_id=users['referee'], role_id=roles['REFEREE'], scope_type='TOURNAMENT', scope_id=match_case['tid'])
    with session_factory.begin() as db:
        from datetime import datetime, timezone
        db.add(RoleAssignment(**row, revoked_at=datetime.now(timezone.utc)))
        db.add(RoleAssignment(**row))
    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            db.add(RoleAssignment(**row))
    global_row = dict(user_id=users['referee'], role_id=roles['VIEWER'], scope_type='GLOBAL', scope_id=None)
    with session_factory.begin() as db:
        db.add(RoleAssignment(**global_row))
    with pytest.raises(IntegrityError):  # NULL scope_id must not bypass uniqueness
        with session_factory.begin() as db:
            db.add(RoleAssignment(**global_row))


def test_revoked_assignment_grants_nothing_to_checkers(access, session_factory, match_case):
    _, _, users, _, roles = access
    from datetime import datetime, timezone
    from middleware.auth import has_role
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ADMIN'], scope_type='GLOBAL',
                              revoked_at=datetime.now(timezone.utc)))
    with session_factory() as db:
        assert not has_role(db.get(User, users['viewer']), 'ADMIN')


# ---------- ADMIN role assignments ----------

ADMIN = '/api/v1/admin/role-assignments'


def test_admin_grants_and_revokes_any_scope(access, session_factory, match_case):
    client, headers, users, teams, _ = access
    for body in ({'role': 'ORGANIZER', 'scope_type': 'TOURNAMENT', 'scope_id': match_case['tid']},
                 {'role': 'TEAM_MANAGER', 'scope_type': 'TEAM', 'scope_id': teams['Beta']},
                 {'role': 'ORGANIZER', 'scope_type': 'GLOBAL'}):
        created = client.post(ADMIN, headers=headers('admin'), json={'user_id': users['referee']} | body)
        assert created.status_code == 201, created.text
    listed = client.get(ADMIN + f"?user_id={users['referee']}", headers=headers('admin'))
    assert listed.headers['x-total-count'] == '3'
    tournament_scope = listed.json()[0]['assignment_id']
    # The new scoped organizer now manages that tournament, until revoked.
    caps = f"/api/v1/tournaments/{match_case['tid']}/capabilities"
    assert client.get(caps, headers=headers('referee')).json()['can_manage'] is True
    assert client.delete(f'{ADMIN}/{tournament_scope}', headers=headers('admin')).status_code == 200
    assert client.get(caps, headers=headers('referee')).json()['can_manage'] is False
    assert [a.action for a in audits(session_factory)].count('ROLE_ASSIGNMENT_REVOKED') == 1


@pytest.mark.parametrize('body', [
    {'role': 'ORGANIZER', 'scope_type': 'GLOBAL', 'scope_id': 1},
    {'role': 'ORGANIZER', 'scope_type': 'TOURNAMENT'},
    {'role': 'ORGANIZER', 'scope_type': 'TOURNAMENT', 'scope_id': 999999},
    {'role': 'SUPERUSER', 'scope_type': 'GLOBAL'},
    {'role': 'ORGANIZER', 'scope_type': 'PLANET', 'scope_id': 1},
])
def test_admin_rejects_invalid_scope(access, session_factory, body):
    client, headers, users, *_ = access
    assert client.post(ADMIN, headers=headers('admin'), json={'user_id': users['referee']} | body).status_code == 422
    assert audits(session_factory) == []


def test_admin_api_is_admin_only_and_cannot_target_self(access, session_factory, match_case):
    client, headers, users, *_ = access
    body = {'user_id': users['referee'], 'role': 'ADMIN', 'scope_type': 'GLOBAL'}
    assert client.post(ADMIN, json=body).status_code == 401
    for who in ('organizer', 'viewer', 'referee'):
        assert client.post(ADMIN, headers=headers(who), json=body).status_code == 403
        assert client.get(ADMIN, headers=headers(who)).status_code == 403
    assert client.post(ADMIN, headers=headers('admin'), json=body | {'user_id': users['admin']}).status_code == 422


# ---------- review PR #101 ----------

def admin_referee(client, headers, users, tid, target='referee'):
    return client.post(ADMIN, headers=headers('admin'),
                       json={'user_id': users[target], 'role': 'REFEREE', 'scope_type': 'TOURNAMENT', 'scope_id': tid})


@pytest.mark.parametrize('player', ['viewer', 'manager'])
def test_admin_api_applies_referee_conflict_of_interest(access, session_factory, match_case, player):
    client, headers, users, *_ = access
    assert admin_referee(client, headers, users, match_case['tid'], player).status_code == 409
    assert audits(session_factory) == []


@pytest.mark.parametrize('status', ['COMPLETED', 'CANCELLED'])
def test_admin_api_cannot_grant_referee_in_closed_tournament(access, session_factory, match_case, status):
    client, headers, users, *_ = access
    with session_factory.begin() as db:
        db.get(Tournament, match_case['tid']).status = status
    assert admin_referee(client, headers, users, match_case['tid']).status_code == 409
    assert audits(session_factory) == []


@pytest.mark.parametrize('role,scope', [
    ('ADMIN', 'TEAM'), ('ADMIN', 'TOURNAMENT'), ('REFEREE', 'GLOBAL'), ('REFEREE', 'TEAM'),
    ('TEAM_MANAGER', 'TOURNAMENT'), ('TEAM_MANAGER', 'GLOBAL'), ('ORGANIZER', 'TEAM'), ('VIEWER', 'TOURNAMENT'),
])
def test_admin_rejects_role_scope_pairs_no_checker_honours(access, session_factory, match_case, role, scope):
    client, headers, users, teams, _ = access
    scope_id = {'GLOBAL': None, 'TEAM': teams['Alpha'], 'TOURNAMENT': match_case['tid']}[scope]
    body = {'user_id': users['referee'], 'role': role, 'scope_type': scope, 'scope_id': scope_id}
    assert client.post(ADMIN, headers=headers('admin'), json=body).status_code == 422
    assert audits(session_factory) == []


@pytest.mark.parametrize('scope', ['TEAM', 'ORGANIZATION'])
def test_scoped_team_manager_of_registered_team_cannot_referee(access, session_factory, match_case, scope):
    client, headers, users, teams, roles = access
    with session_factory.begin() as db:
        from modules.teams.models import Team
        alpha = db.get(Team, teams['Alpha'])
        scope_id = alpha.team_id if scope == 'TEAM' else alpha.organization_id
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['TEAM_MANAGER'],
                              scope_type=scope, scope_id=scope_id))
    assert grant(client, headers, match_case['tid'], users).status_code == 409
    assert admin_referee(client, headers, users, match_case['tid']).status_code == 409
    assert grant(client, headers, match_case['other'], users).status_code == 201


def test_permission_lists_are_not_cached(access, match_case):
    client, headers, users, *_ = access
    assignment = grant(client, headers, match_case['tid'], users).json()['assignment_id']
    responses = [client.get(path(match_case['tid']), headers=headers('organizer')),
                 client.get(path(match_case['tid'])),
                 client.delete(path(match_case['tid'], f'/{assignment}'), headers=headers('organizer')),
                 client.get(ADMIN, headers=headers('admin')),
                 client.get(ADMIN, headers=headers('viewer'))]
    assert [r.headers.get('cache-control') for r in responses] == ['private, no-store'] * 5
