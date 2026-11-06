"""W45-03/-04: match list/detail, manual schedule, start/cancel lifecycle and capabilities."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select

from modules.identity.models import AuditLog, RoleAssignment
from modules.teams.models import Team
from modules.tournaments.models import Match, Stage, Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def base(tid):
    return f'/api/v1/tournaments/{tid}/matches'


def detail(ids, match=None):
    return f"{base(ids['tid'])}/{match or ids['match']}"


def logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match').order_by(AuditLog.log_id)))


def set_match(factory, match_id, **values):
    with factory.begin() as db:
        match = db.get(Match, match_id)
        for field, value in values.items():
            setattr(match, field, value)


def set_tournament(factory, tid, **values):
    with factory.begin() as db:
        tournament = db.get(Tournament, tid)
        for field, value in values.items():
            setattr(tournament, field, value)


def make_referee(access, factory, tid, name='referee'):
    _, _, users, _, roles = access
    with factory.begin() as db:
        db.add(RoleAssignment(user_id=users[name], role_id=roles['REFEREE'], scope_type='TOURNAMENT', scope_id=tid))


def new_body(ids, teams, **extra):
    return {'stage_id': ids['stage'], 'round_no': 2, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta']} | extra


# ---------- public read ----------

def test_public_read_exposes_only_public_fields(access, match_case):
    client, _, _, teams, _ = access
    response = client.get(detail(match_case))
    assert response.status_code == 200
    assert set(response.json()) == {'match_id', 'tournament_id', 'stage_id', 'stage_name', 'round_no', 'team1',
                                    'team2', 'scheduled_at', 'status', 'result'}
    assert response.json()['result'] is None  # default 0-0 columns are not a result
    assert response.json()['team1'] == {'team_id': teams['Alpha'], 'name': 'Alpha'}
    assert 'email' not in response.text and 'roster' not in response.text
    assert client.get(f"{base(match_case['other'])}/{match_case['match']}").status_code == 404
    assert client.get(detail(match_case, 999999)).status_code == 404
    assert client.get(base(999999)).status_code == 404


def test_list_paginates_over_50_without_gaps_and_counts_total(access, session_factory, match_case):
    client, _, _, teams, _ = access
    with session_factory.begin() as db:
        db.add_all(Match(tournament_id=match_case['tid'], stage_id=match_case['stage'], round_no=1 + n % 3,
                         team1_id=teams['Alpha'], team2_id=teams['Beta']) for n in range(120))
    seen = []
    for offset in range(0, 121, 50):
        page = client.get(base(match_case['tid']), params={'offset': offset, 'limit': 50})
        assert page.status_code == 200 and page.headers['x-total-count'] == '121'
        seen += [row['match_id'] for row in page.json()]
    assert len(seen) == 121 and len(set(seen)) == 121
    assert client.get(base(match_case['tid']), params={'limit': 101}).status_code == 422
    assert client.get(base(match_case['tid']), params={'status': 'DONE'}).status_code == 422


def test_list_page_does_not_query_per_match(access, session_factory, match_case):
    client, _, _, teams, _ = access
    with session_factory.begin() as db:
        db.add_all(Match(tournament_id=match_case['tid'], stage_id=match_case['stage'], round_no=1,
                         team1_id=teams['Alpha'], team2_id=teams['Beta']) for _ in range(40))
    statements = []
    engine = session_factory.kw['bind']
    listener = lambda conn, cur, statement, *rest: statements.append(statement)
    event.listen(engine, 'before_cursor_execute', listener)
    try:
        assert len(client.get(base(match_case['tid'])).json()) == 41
    finally:
        event.remove(engine, 'before_cursor_execute', listener)
    assert len(statements) < 10


def test_list_filters_and_stable_order(access, session_factory, match_case):
    client, _, _, teams, _ = access
    with session_factory.begin() as db:
        db.add(Team(name='Gamma', tag='GM', game_id=1))
        first = Stage(tournament_id=match_case['tid'], name='Earlier', sequence_order=5)
        late = Stage(tournament_id=match_case['tid'], name='Later', sequence_order=9)
        db.add_all([first, late])
        db.flush()
        gamma = db.scalar(select(Team.team_id).where(Team.name == 'Gamma'))
        later = Match(tournament_id=match_case['tid'], stage_id=late.stage_id, round_no=1, team1_id=teams['Alpha'],
                      team2_id=gamma, status='CANCELLED')
        earlier = Match(tournament_id=match_case['tid'], stage_id=first.stage_id, round_no=7,
                        team1_id=teams['Alpha'], team2_id=teams['Beta'])
        db.add_all([later, earlier])
        db.flush()
        ids = {'later': later.match_id, 'earlier': earlier.match_id, 'late_stage': late.stage_id}

    def listed(**params):
        return [row['match_id'] for row in client.get(base(match_case['tid']), params=params).json()]

    assert listed() == [match_case['match'], ids['earlier'], ids['later']]
    assert listed(stage_id=ids['late_stage']) == [ids['later']]
    assert listed(team_id=gamma) == [ids['later']]
    assert listed(status='CANCELLED') == [ids['later']]
    assert listed(status='COMPLETED') == []


# ---------- create ----------

def test_create_stores_utc_and_audits_in_one_transaction(access, session_factory, match_case):
    client, headers, users, teams, _ = access
    response = client.post(base(match_case['tid']), headers=headers('organizer'),
                           json=new_body(match_case, teams, scheduled_at='2026-11-05T19:00:00+07:00'))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['status'] == 'PENDING' and body['result'] is None and body['round_no'] == 2
    assert datetime.fromisoformat(body['scheduled_at'].replace('Z', '+00:00')) == datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    assert body['scheduled_at'].endswith(('Z', '+00:00'))
    reloaded = client.get(detail(match_case, body['match_id'])).json()
    assert reloaded['scheduled_at'] == body['scheduled_at']
    [log] = logs(session_factory)
    assert log.action == 'MATCH_CREATED' and log.user_id == users['organizer']
    assert log.details['before'] is None and log.details['match_id'] == body['match_id']


def test_same_instant_in_different_offsets_is_the_same_schedule(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    created = client.post(base(match_case['tid']), headers=headers('admin'),
                          json=new_body(match_case, teams, scheduled_at='2026-11-05T12:00:00Z')).json()
    path = detail(match_case, created['match_id'])
    same = client.patch(path, headers=headers('admin'), json={'scheduled_at': '2026-11-05T07:00:00-05:00'})
    assert same.status_code == 200 and same.json()['scheduled_at'] == created['scheduled_at']
    assert [log.action for log in logs(session_factory)] == ['MATCH_CREATED']


@pytest.mark.parametrize('change', [
    {'scheduled_at': '2026-11-05T12:00:00'},  # no offset
    {'scheduled_at': 1762344000},             # Unix number
    {'round_no': 0}, {'round_no': True}, {'round_no': 1.5}, {'round_no': 2147483648},
    {'team1_id': '1'}, {'winner_id': 1}, {'status': 'COMPLETED'}, {'score_team1': 3},
])
def test_create_rejects_bad_payload(access, session_factory, match_case, change):
    client, headers, _, teams, _ = access
    response = client.post(base(match_case['tid']), headers=headers('admin'), json=new_body(match_case, teams) | change)
    assert response.status_code == 422
    assert logs(session_factory) == []


NUMERIC_SCHEDULES = ['20261105', '1762344000', '1762344000000', '1762344000.5']


@pytest.mark.parametrize('value', NUMERIC_SCHEDULES)
def test_create_rejects_numeric_schedule_string(access, session_factory, match_case, value):
    client, headers, _, teams, _ = access
    response = client.post(base(match_case['tid']), headers=headers('admin'),
                           json=new_body(match_case, teams, scheduled_at=value))
    assert response.status_code == 422
    assert logs(session_factory) == []


@pytest.mark.parametrize('value', NUMERIC_SCHEDULES)
def test_update_rejects_numeric_schedule_string(access, session_factory, match_case, value):
    client, headers, *_ = access
    response = client.patch(detail(match_case), headers=headers('admin'), json={'scheduled_at': value})
    assert response.status_code == 422
    assert client.get(detail(match_case)).json()['scheduled_at'] is None
    assert logs(session_factory) == []


def test_update_null_schedule_still_clears(access, match_case):
    client, headers, *_ = access
    path = detail(match_case)
    assert client.patch(path, headers=headers('admin'), json={'scheduled_at': '2026-11-05T12:00:00+07:00'}).status_code == 200
    cleared = client.patch(path, headers=headers('admin'), json={'scheduled_at': None})
    assert cleared.status_code == 200 and cleared.json()['scheduled_at'] is None


@pytest.mark.parametrize('value', ['0001-01-01T00:00:00+07:00', '9999-12-31T23:00:00-07:00'])
def test_create_rejects_schedule_outside_utc_range(access, match_case, value):
    client, headers, _, teams, _ = access
    response = client.post(base(match_case['tid']), headers=headers('admin'),
                           json=new_body(match_case, teams, scheduled_at=value))
    assert response.status_code == 422


def test_create_validates_links_against_this_tournament(access, session_factory, match_case):
    client, headers, users, teams, _ = access
    with session_factory.begin() as db:
        db.add_all([Team(name='Pending', tag='PD', game_id=1), Team(name='NoPlayer', tag='NP', game_id=1),
                    Team(name='OtherGame', tag='OG', game_id=2)])
        db.flush()
        team_ids = {t.name: t.team_id for t in db.scalars(select(Team))}
        now = datetime.now(timezone.utc)
        db.add(TournamentRegistration(tournament_id=match_case['tid'], team_id=team_ids['Pending'], status='PENDING'))
        db.add(TournamentRoster(tournament_id=match_case['tid'], team_id=team_ids['Pending'], user_id=users['referee'],
                                role_in_team='PLAYER', display_name='r'))
        db.add(TournamentRegistration(tournament_id=match_case['tid'], team_id=team_ids['NoPlayer'], status='APPROVED', reviewed_at=now))
    auth, tid = headers('admin'), match_case['tid']

    def create(**change):
        return client.post(base(tid), headers=auth, json=new_body(match_case, teams) | change).status_code

    assert create(team2_id=teams['Alpha']) == 422                 # same team twice
    assert create(stage_id=match_case['other_stage']) == 422      # stage of another tournament
    assert create(stage_id=999999) == 422
    assert create(team2_id=999999) == 422
    assert create(team2_id=team_ids['Pending']) == 422            # not APPROVED
    assert create(team2_id=team_ids['NoPlayer']) == 422           # no locked PLAYER
    assert create(team2_id=team_ids['OtherGame']) == 422          # not registered / other game
    assert logs(session_factory) == []


def test_create_permission_matrix(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    make_referee(access, session_factory, match_case['tid'])
    path, body = base(match_case['tid']), new_body(match_case, teams)
    assert client.post(path, json=body).status_code == 401
    for name in ('referee', 'manager', 'viewer'):
        assert client.post(path, headers=headers(name), json=body).status_code == 403
    assert client.post(path, headers=headers('organizer'), json=body).status_code == 201
    assert client.post(path, headers=headers('admin'), json=body).status_code == 201
    assert client.post(base(999999), headers=headers('admin'), json=body).status_code == 404


@pytest.mark.parametrize('values,expected', [
    ({'status': 'UPCOMING'}, 201),
    ({'status': 'ONGOING'}, 201),
    ({'status': 'COMPLETED'}, 409),
    ({'status': 'CANCELLED'}, 409),
    ({'status': 'UPCOMING', 'roster_locked_at': None}, 409),
])
def test_create_follows_tournament_lifecycle(access, session_factory, match_case, values, expected):
    client, headers, _, teams, _ = access
    set_tournament(session_factory, match_case['tid'], **values)
    response = client.post(base(match_case['tid']), headers=headers('admin'), json=new_body(match_case, teams))
    assert response.status_code == expected


def test_lifecycle_conflict_precedes_link_validation(access, session_factory, match_case):
    # An unlocked tournament has no snapshot: the caller must learn to lock, not that a team has no PLAYER.
    client, headers, _, teams, _ = access
    set_tournament(session_factory, match_case['tid'], status='UPCOMING', roster_locked_at=None)
    response = client.post(base(match_case['tid']), headers=headers('admin'),
                           json=new_body(match_case, teams, team2_id=teams['Alpha']))
    assert response.status_code == 409


# ---------- update and delete ----------

def test_update_changes_fields_and_audits_once(access, session_factory, match_case):
    client, headers, _, _, _ = access
    auth = headers('organizer')
    response = client.patch(detail(match_case), headers=auth, json={'round_no': 4, 'scheduled_at': '2026-12-01T01:00:00+07:00'})
    assert response.status_code == 200 and response.json()['round_no'] == 4
    assert response.json()['scheduled_at'].startswith('2026-11-30T18:00:00')
    [log] = logs(session_factory)
    assert log.action == 'MATCH_UPDATED' and log.details['before']['round_no'] == 1 and log.details['after']['round_no'] == 4
    # Same values again: no second audit row.
    assert client.patch(detail(match_case), headers=auth, json={'round_no': 4}).status_code == 200
    assert len(logs(session_factory)) == 1
    # Explicit null clears the schedule.
    cleared = client.patch(detail(match_case), headers=auth, json={'scheduled_at': None})
    assert cleared.status_code == 200 and cleared.json()['scheduled_at'] is None


@pytest.mark.parametrize('payload', [{}, {'round_no': None}, {'team1_id': None}, {'stage_id': None}, {'status': 'ONGOING'}])
def test_update_rejects_empty_or_null_or_unknown(access, match_case, payload):
    client, headers, *_ = access
    assert client.patch(detail(match_case), headers=headers('admin'), json=payload).status_code == 422


def test_update_validates_new_stage_and_teams(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    auth = headers('admin')
    assert client.patch(detail(match_case), headers=auth, json={'stage_id': match_case['other_stage']}).status_code == 422
    assert client.patch(detail(match_case), headers=auth, json={'team1_id': teams['Beta']}).status_code == 422
    assert client.patch(detail(match_case), headers=auth, json={'team2_id': 999999}).status_code == 422
    assert logs(session_factory) == []


def test_update_with_missing_legacy_team_is_422_not_500(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    set_match(session_factory, match_case['match'], team2_id=None)
    response = client.patch(detail(match_case), headers=headers('admin'), json={'team1_id': teams['Beta']})
    assert response.status_code == 422
    # The other fields of a legacy match remain editable.
    assert client.patch(detail(match_case), headers=headers('admin'), json={'round_no': 3}).status_code == 200


@pytest.mark.parametrize('status', ['ONGOING', 'CANCELLED'])
def test_update_and_delete_only_while_pending(access, session_factory, match_case, status):
    client, headers, *_ = access
    set_match(session_factory, match_case['match'], status=status)
    auth = headers('admin')
    assert client.patch(detail(match_case), headers=auth, json={'round_no': 2}).status_code == 409
    assert client.delete(detail(match_case), headers=auth).status_code == 409
    assert logs(session_factory) == []


def test_completed_match_is_immutable(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    set_match(session_factory, match_case['match'], status='COMPLETED', winner_id=teams['Alpha'], score_team1=1)
    auth = headers('admin')
    assert client.patch(detail(match_case), headers=auth, json={'round_no': 2}).status_code == 409
    assert client.delete(detail(match_case), headers=auth).status_code == 409
    for status in ('ONGOING', 'CANCELLED'):
        assert client.post(f'{detail(match_case)}/status', headers=auth, json={'status': status}).status_code == 409


@pytest.mark.parametrize('side', ['source', 'target'])
def test_historical_bracket_links_are_not_rewritten(access, session_factory, match_case, side):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        linked = Match(tournament_id=match_case['tid'], stage_id=match_case['stage'], round_no=2,
                       team1_id=teams['Alpha'], team2_id=teams['Beta'])
        db.add(linked)
        db.flush()
        if side == 'source':
            db.get(Match, match_case['match']).next_match_id = linked.match_id
        else:
            linked.next_match_id = match_case['match']
    auth = headers('admin')
    assert client.patch(detail(match_case), headers=auth, json={'round_no': 3}).status_code == 409
    assert client.delete(detail(match_case), headers=auth).status_code == 409
    caps = client.get(f'{detail(match_case)}/capabilities', headers=auth).json()
    assert not caps['can_update'] and not caps['can_delete'] and caps['editable_fields'] == []


def test_delete_removes_match_with_audit(access, session_factory, match_case):
    client, headers, users, *_ = access
    response = client.delete(detail(match_case), headers=headers('organizer'))
    assert response.status_code == 204 and response.content == b''
    assert client.get(detail(match_case)).status_code == 404
    [log] = logs(session_factory)
    assert log.action == 'MATCH_DELETED' and log.user_id == users['organizer']
    assert log.details['after'] is None and log.details['before']['match_id'] == match_case['match']
    assert client.delete(detail(match_case), headers=headers('organizer')).status_code == 404


def test_schedule_writes_are_manager_only(access, session_factory, match_case):
    client, headers, *_ = access
    make_referee(access, session_factory, match_case['tid'])
    for name in ('referee', 'manager', 'viewer'):
        assert client.patch(detail(match_case), headers=headers(name), json={'round_no': 2}).status_code == 403
        assert client.delete(detail(match_case), headers=headers(name)).status_code == 403
    assert client.patch(detail(match_case), json={'round_no': 2}).status_code == 401
    other = f"{base(match_case['other'])}/{match_case['match']}"
    assert client.patch(other, headers=headers('admin'), json={'round_no': 2}).status_code == 404


# ---------- start and cancel ----------

def status(client, ids, auth, value):
    return client.post(f'{detail(ids)}/status', headers=auth, json={'status': value})


def test_start_then_restart_is_idempotent(access, session_factory, match_case):
    client, headers, users, *_ = access
    first = status(client, match_case, headers('organizer'), 'ONGOING')
    assert first.status_code == 200 and first.json()['status'] == 'ONGOING'
    again = status(client, match_case, headers('organizer'), 'ONGOING')
    assert again.status_code == 200 and again.json()['status'] == 'ONGOING'
    [log] = logs(session_factory)
    assert log.action == 'MATCH_STARTED' and log.user_id == users['organizer']
    assert log.details['before']['status'] == 'PENDING' and log.details['after']['status'] == 'ONGOING'
    # A restart still checks the caller's current permission.
    assert status(client, match_case, headers('viewer'), 'ONGOING').status_code == 403


@pytest.mark.parametrize('tournament', ['UPCOMING', 'COMPLETED', 'CANCELLED'])
@pytest.mark.parametrize('match', ['PENDING', 'ONGOING'])
def test_start_and_restart_need_ongoing_tournament(access, session_factory, match_case, tournament, match):
    client, headers, *_ = access
    set_match(session_factory, match_case['match'], status=match)
    set_tournament(session_factory, match_case['tid'], status=tournament)
    assert status(client, match_case, headers('admin'), 'ONGOING').status_code == 409
    assert logs(session_factory) == []


def test_start_rechecks_teams_at_start_time(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    with session_factory.begin() as db:
        reg = db.scalar(select(TournamentRegistration).where(TournamentRegistration.team_id == teams['Beta'],
                                                             TournamentRegistration.tournament_id == match_case['tid']))
        reg.status = 'REJECTED'
    assert status(client, match_case, headers('admin'), 'ONGOING').status_code == 422
    with session_factory() as db:
        assert db.get(Match, match_case['match']).status == 'PENDING'
    assert logs(session_factory) == []


def test_start_with_missing_legacy_team_conflicts(access, session_factory, match_case):
    client, headers, *_ = access
    set_match(session_factory, match_case['match'], team1_id=None)
    assert status(client, match_case, headers('admin'), 'ONGOING').status_code == 409


@pytest.mark.parametrize('scope,start_code', [
    (None, 403), ('GLOBAL', 403), ('other', 403), ('tid', 200),
])
def test_referee_start_needs_assignment_for_this_tournament(access, session_factory, match_case, scope, start_code):
    client, headers, users, _, roles = access
    if scope:
        with session_factory.begin() as db:
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                                  scope_type='GLOBAL' if scope == 'GLOBAL' else 'TOURNAMENT',
                                  scope_id=None if scope == 'GLOBAL' else match_case[scope]))
    assert status(client, match_case, headers('referee'), 'ONGOING').status_code == start_code


def test_referee_from_a_playing_team_cannot_start(access, session_factory, match_case):
    client, headers, *_ = access
    make_referee(access, session_factory, match_case['tid'], 'viewer')  # viewer is an Alpha PLAYER
    assert status(client, match_case, headers('viewer'), 'ONGOING').status_code == 403


def test_referee_cannot_cancel(access, session_factory, match_case):
    client, headers, *_ = access
    make_referee(access, session_factory, match_case['tid'])
    assert status(client, match_case, headers('referee'), 'CANCELLED').status_code == 403
    assert status(client, match_case, headers('referee'), 'ONGOING').status_code == 200
    assert status(client, match_case, headers('referee'), 'CANCELLED').status_code == 403


@pytest.mark.parametrize('initial', ['PENDING', 'ONGOING'])
def test_cancel_then_cancel_again_is_idempotent(access, session_factory, match_case, initial):
    client, headers, *_ = access
    set_match(session_factory, match_case['match'], status=initial)
    auth = headers('organizer')
    first = status(client, match_case, auth, 'CANCELLED')
    assert first.status_code == 200 and first.json()['status'] == 'CANCELLED'
    assert status(client, match_case, auth, 'CANCELLED').status_code == 200
    [log] = logs(session_factory)
    assert log.action == 'MATCH_CANCELLED' and log.details['before']['status'] == initial
    assert status(client, match_case, auth, 'ONGOING').status_code == 409  # no restore in W45


@pytest.mark.parametrize('tournament', ['COMPLETED', 'CANCELLED'])
def test_cancel_blocked_after_tournament_ended(access, session_factory, match_case, tournament):
    client, headers, *_ = access
    set_tournament(session_factory, match_case['tid'], status=tournament)
    assert status(client, match_case, headers('admin'), 'CANCELLED').status_code == 409


@pytest.mark.parametrize('payload', [{'status': 'COMPLETED'}, {'status': 'PENDING'}, {}, {'status': 'ONGOING', 'x': 1}])
def test_status_cannot_bypass_result_validation(access, session_factory, match_case, payload):
    client, headers, *_ = access
    response = client.post(f'{detail(match_case)}/status', headers=headers('admin'), json=payload)
    assert response.status_code == 422
    with session_factory() as db:
        assert db.get(Match, match_case['match']).status == 'PENDING'


def test_status_auth_and_scope_errors(access, match_case):
    client, headers, *_ = access
    body = {'status': 'ONGOING'}
    assert client.post(f'{detail(match_case)}/status', json=body).status_code == 401
    assert client.post(f"{base(match_case['other'])}/{match_case['match']}/status", headers=headers('admin'), json=body).status_code == 404
    assert client.post(f'{detail(match_case, 999999)}/status', headers=headers('admin'), json=body).status_code == 404


@pytest.mark.parametrize('call', [
    lambda client, ids, auth, teams: client.post(base(ids['tid']), headers=auth, json=new_body(ids, teams)),
    lambda client, ids, auth, teams: client.patch(detail(ids), headers=auth, json={'round_no': 9}),
    lambda client, ids, auth, teams: client.delete(detail(ids), headers=auth),
    lambda client, ids, auth, teams: status(client, ids, auth, 'ONGOING'),
    lambda client, ids, auth, teams: status(client, ids, auth, 'CANCELLED'),
], ids=['create', 'update', 'delete', 'start', 'cancel'])
def test_audit_failure_rolls_back_the_match_change(access, session_factory, match_case, monkeypatch, call):
    client, headers, _, teams, _ = access
    with session_factory() as db:
        before = db.scalar(select(Match).where(Match.match_id == match_case['match']))
        snapshot = (before.status, before.round_no)
        count = len(db.scalars(select(Match)).all())

    def boom(*args, **kwargs):
        raise RuntimeError('audit down')

    monkeypatch.setattr('routes.matches.record_audit', boom)
    with pytest.raises(RuntimeError):
        call(client, match_case, headers('admin'), teams)
    with session_factory() as db:
        after = db.get(Match, match_case['match'])
        assert after is not None and (after.status, after.round_no) == snapshot
        assert len(db.scalars(select(Match)).all()) == count


# ---------- capabilities (W45-04) ----------

def caps(client, ids, auth):
    response = client.get(f'{detail(ids)}/capabilities', headers=auth)
    assert response.status_code == 200, response.text
    assert 'private' in response.headers['cache-control']
    return response.json()


def flags(body):
    return tuple(body[key] for key in ('can_update', 'can_delete', 'can_start', 'can_submit_result', 'can_cancel'))


@pytest.mark.parametrize('match,expected', [
    ('PENDING', (True, True, True, False, True)),
    ('ONGOING', (False, False, False, True, True)),
    ('CANCELLED', (False, False, False, False, False)),
])
def test_manager_capabilities_follow_match_lifecycle(access, session_factory, match_case, match, expected):
    client, headers, *_ = access
    set_match(session_factory, match_case['match'], status=match)
    body = caps(client, match_case, headers('organizer'))
    assert flags(body) == expected
    assert bool(body['editable_fields']) == expected[0]


def test_completed_match_has_no_write_capability(access, session_factory, match_case):
    client, headers, _, teams, _ = access
    set_match(session_factory, match_case['match'], status='COMPLETED', winner_id=teams['Alpha'], score_team1=1)
    assert flags(caps(client, match_case, headers('admin'))) == (False,) * 5


def test_referee_capabilities_by_scope(access, session_factory, match_case):
    client, headers, users, _, roles = access
    assert flags(caps(client, match_case, headers('referee'))) == (False,) * 5
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                              scope_type='TOURNAMENT', scope_id=match_case['other']))
    assert flags(caps(client, match_case, headers('referee'))) == (False,) * 5
    make_referee(access, session_factory, match_case['tid'])
    assert flags(caps(client, match_case, headers('referee'))) == (False, False, True, False, False)
    set_match(session_factory, match_case['match'], status='ONGOING')
    assert flags(caps(client, match_case, headers('referee'))) == (False, False, False, True, False)


@pytest.mark.parametrize('name', ['manager', 'viewer'])
def test_players_have_no_capability_even_with_referee_assignment(access, session_factory, match_case, name):
    client, headers, *_ = access
    assert flags(caps(client, match_case, headers(name))) == (False,) * 5
    make_referee(access, session_factory, match_case['tid'], name)
    assert flags(caps(client, match_case, headers(name))) == (False,) * 5


def test_capabilities_require_login_and_scope_to_tournament(access, match_case):
    client, headers, *_ = access
    assert client.get(f'{detail(match_case)}/capabilities').status_code == 401
    other = f"{base(match_case['other'])}/{match_case['match']}/capabilities"
    assert client.get(other, headers=headers('admin')).status_code == 404


def test_tournament_capability_reports_match_management(access, session_factory, match_case):
    client, headers, *_ = access
    path = f"/api/v1/tournaments/{match_case['tid']}/capabilities"
    assert client.get(path, headers=headers('organizer')).json()['can_manage_matches'] is True
    assert client.get(path, headers=headers('viewer')).json()['can_manage_matches'] is False
    set_tournament(session_factory, match_case['tid'], status='COMPLETED')
    assert client.get(path, headers=headers('organizer')).json()['can_manage_matches'] is False
    set_tournament(session_factory, match_case['tid'], status='UPCOMING', roster_locked_at=None)
    assert client.get(path, headers=headers('organizer')).json()['can_manage_matches'] is False
