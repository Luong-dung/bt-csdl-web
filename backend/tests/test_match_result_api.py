"""W45-02: PUT /tournaments/{id}/matches/{match_id}/result."""

import pytest
from sqlalchemy import select

from modules.identity.models import AuditLog, RoleAssignment
from modules.tournaments.models import Match, Tournament
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def url(tid, mid):
    return f'/api/v1/tournaments/{tid}/matches/{mid}/result'


def result_logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match').order_by(AuditLog.log_id)))


def stored(factory, mid):
    with factory() as db:
        m = db.get(Match, mid)
        return m.status, m.score_team1, m.score_team2, m.winner_id


@pytest.fixture
def ongoing(session_factory, match_case):
    with session_factory.begin() as db:
        db.get(Match, match_case['match']).status = 'ONGOING'
    return match_case


def referee(session_factory, access, scope_type, scope_id):
    _, _, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                              scope_type=scope_type, scope_id=scope_id))


def test_manager_submits_result_atomically_with_audit(access, session_factory, ongoing):
    client, headers, users, teams, _ = access
    response = client.put(url(ongoing['tid'], ongoing['match']), headers=headers('organizer'),
                          json={'score_team1': 1, 'score_team2': 3})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['status'] == 'COMPLETED'
    assert body['result'] == {'score_team1': 1, 'score_team2': 3, 'winner_id': teams['Beta']}
    assert body['team1'] == {'team_id': teams['Alpha'], 'name': 'Alpha'} and body['stage_name'] == 'Group'
    assert 'email' not in response.text
    assert stored(session_factory, ongoing['match']) == ('COMPLETED', 1, 3, teams['Beta'])
    [log] = result_logs(session_factory)
    assert log.action == 'MATCH_RESULT_SUBMITTED' and log.user_id == users['organizer']
    assert log.details['before']['status'] == 'ONGOING' and log.details['after']['winner_id'] == teams['Beta']
    assert log.details['tournament_id'] == ongoing['tid'] and log.details['match_id'] == ongoing['match']


def test_replay_same_result_is_idempotent_and_different_result_conflicts(access, session_factory, ongoing):
    client, headers, *_ = access
    path, auth = url(ongoing['tid'], ongoing['match']), headers('admin')
    assert client.put(path, headers=auth, json={'score_team1': 2, 'score_team2': 0}).status_code == 200
    replay = client.put(path, headers=auth, json={'score_team1': 2, 'score_team2': 0})
    assert replay.status_code == 200 and replay.json()['result']['score_team1'] == 2
    assert client.put(path, headers=auth, json={'score_team1': 0, 'score_team2': 2}).status_code == 409
    assert client.put(path, headers=auth, json={'score_team1': 3, 'score_team2': 0}).status_code == 409
    assert len(result_logs(session_factory)) == 1
    # Replay still checks the caller's current permission.
    assert client.put(path, headers=headers('viewer'), json={'score_team1': 2, 'score_team2': 0}).status_code == 403


@pytest.mark.parametrize('scope,expected', [
    (None, 403), (('GLOBAL', None), 403), (('TOURNAMENT', 'other'), 403), (('TOURNAMENT', 'tid'), 200),
])
def test_referee_needs_assignment_for_this_tournament(access, session_factory, ongoing, scope, expected):
    client, headers, *_ = access
    if scope:
        referee(session_factory, access, scope[0], ongoing.get(scope[1]))
    response = client.put(url(ongoing['tid'], ongoing['match']), headers=headers('referee'),
                          json={'score_team1': 1, 'score_team2': 0})
    assert response.status_code == expected
    assert len(result_logs(session_factory)) == (1 if expected == 200 else 0)


@pytest.mark.parametrize('name', ['manager', 'viewer'])
def test_playing_team_members_cannot_submit(access, session_factory, ongoing, name):
    client, headers, *_ = access
    response = client.put(url(ongoing['tid'], ongoing['match']), headers=headers(name),
                          json={'score_team1': 1, 'score_team2': 0})
    assert response.status_code == 403
    assert stored(session_factory, ongoing['match'])[0] == 'ONGOING'


def test_auth_and_scope_errors(access, ongoing):
    client, headers, *_ = access
    body = {'score_team1': 1, 'score_team2': 0}
    assert client.put(url(ongoing['tid'], ongoing['match']), json=body).status_code == 401
    assert client.put(url(ongoing['other'], ongoing['match']), headers=headers('admin'), json=body).status_code == 404
    assert client.put(url(ongoing['tid'], 999999), headers=headers('admin'), json=body).status_code == 404
    assert client.put(url(999999, ongoing['match']), headers=headers('admin'), json=body).status_code == 404


@pytest.mark.parametrize('body', [
    {'score_team1': 1, 'score_team2': 1}, {'score_team1': -1, 'score_team2': 0},
    {'score_team1': True, 'score_team2': 0}, {'score_team1': 1.0, 'score_team2': 0},
    {'score_team1': '2', 'score_team2': 0}, {'score_team1': 1},
    {'score_team1': 1, 'score_team2': 0, 'winner_id': 1}, {'score_team1': 2147483648, 'score_team2': 0},
])
def test_invalid_payload_is_rejected_without_audit(access, session_factory, ongoing, body):
    client, headers, *_ = access
    assert client.put(url(ongoing['tid'], ongoing['match']), headers=headers('admin'), json=body).status_code == 422
    assert stored(session_factory, ongoing['match'])[0] == 'ONGOING'
    assert result_logs(session_factory) == []


@pytest.mark.parametrize('match_status,tournament_status', [
    ('PENDING', 'ONGOING'), ('CANCELLED', 'ONGOING'), ('ONGOING', 'COMPLETED'), ('ONGOING', 'CANCELLED'),
])
def test_lifecycle_conflicts(access, session_factory, match_case, match_status, tournament_status):
    client, headers, *_ = access
    with session_factory.begin() as db:
        db.get(Match, match_case['match']).status = match_status
        db.get(Tournament, match_case['tid']).status = tournament_status
    response = client.put(url(match_case['tid'], match_case['match']), headers=headers('admin'),
                          json={'score_team1': 1, 'score_team2': 0})
    assert response.status_code == 409
    assert stored(session_factory, match_case['match'])[0] == match_status
    assert result_logs(session_factory) == []


def test_audit_failure_rolls_back_match(access, session_factory, ongoing, monkeypatch):
    client, headers, *_ = access

    def broken(*args, **kwargs):
        raise RuntimeError('audit store unavailable')
    monkeypatch.setattr('routes.match_results.record_audit', broken)
    with pytest.raises(RuntimeError, match='audit store unavailable'):
        client.put(url(ongoing['tid'], ongoing['match']), headers=headers('admin'),
                   json={'score_team1': 1, 'score_team2': 0})
    assert stored(session_factory, ongoing['match']) == ('ONGOING', 0, 0, None)
    assert result_logs(session_factory) == []
