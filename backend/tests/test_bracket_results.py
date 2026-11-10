"""W46-02 API: atomic advancement, immutable structure and terminal tournament guards."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import Team
from modules.tournaments.models import BracketMatch, Match, Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_permissions import access
from test_match_foundation import match_case
from test_bracket_foundation import bracket_case, add_bracket, add_node

pytestmark = pytest.mark.postgres


@pytest.fixture
def bracket_results(access, session_factory, bracket_case):
    _, _, users, teams, roles = access
    now = datetime.now(timezone.utc)
    ids = bracket_case.copy()
    with session_factory.begin() as db:
        tour = db.get(Tournament, ids['tid'])
        tour.status = 'ONGOING'
        db.get(Match, ids['match']).status = 'CANCELLED'
        extra = []
        for name in ['Gamma', 'Delta']:
            team = Team(name=name, tag=name, game_id=tour.game_id)
            user = User(username=name, email=name+'@example.com', password_hash='unused', role_id=roles['PLAYER'])
            db.add_all([team, user])
            db.flush()
            db.add(TournamentRegistration(tournament_id=ids['tid'], team_id=team.team_id, status='APPROVED', reviewed_at=now))
            db.add(TournamentRoster(tournament_id=ids['tid'], team_id=team.team_id, user_id=user.user_id,
                                    role_in_team='PLAYER', display_name=name))
            extra.append(team.team_id)
        bracket = add_bracket(db, ids, users, 4)
        bracket.team_order = [teams['Alpha'], teams['Beta'], *extra]
        final = add_node(db, bracket, 2, 1)
        first = add_node(db, bracket, 1, 1)
        second = add_node(db, bracket, 1, 2)
        for node, pair in [(first, (teams['Alpha'], teams['Beta'])), (second, extra)]:
            match = db.get(Match, node.match_id)
            match.team1_id, match.team2_id, match.status = *pair, 'ONGOING'
        ids.update(bracket=bracket.bracket_id, first=first.match_id, second=second.match_id,
                   final=final.match_id, alpha=teams['Alpha'], beta=teams['Beta'], gamma=extra[0], delta=extra[1])
    return ids


def path(ids, key='first'):
    return f"/api/v1/tournaments/{ids['tid']}/matches/{ids[key]}"


def result(client, headers, ids, key='first', scores=(2, 0), name='organizer'):
    return client.put(path(ids, key)+'/result', headers=headers(name),
                      json={'score_team1': scores[0], 'score_team2': scores[1]})


def match_logs(factory):
    with factory() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match').order_by(AuditLog.log_id)))


def state(factory, mid):
    with factory() as db:
        m = db.get(Match, mid)
        return m.status, m.team1_id, m.team2_id, m.winner_id


def complete_bracket(client, headers, ids):
    assert result(client, headers, ids).status_code == 200
    assert result(client, headers, ids, 'second', (0, 2)).status_code == 200
    assert client.post(path(ids, 'final')+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    assert result(client, headers, ids, 'final', (3, 1)).status_code == 200


def test_results_fill_both_slots_and_final_survives_reload(access, session_factory, bracket_results):
    client, headers, users, _, _ = access
    ids = bracket_results
    assert result(client, headers, ids).status_code == 200
    assert state(session_factory, ids['final']) == ('PENDING', ids['alpha'], None, None)
    [log] = match_logs(session_factory)
    assert log.user_id == users['organizer'] and log.details['bracket_id'] == ids['bracket']
    assert log.details['advancement']['slot'] == 1
    assert log.details['advancement']['before']['team1_id'] is None
    assert log.details['advancement']['after']['team1_id'] == ids['alpha']
    assert result(client, headers, ids).status_code == 200
    assert len(match_logs(session_factory)) == 1
    assert result(client, headers, ids, 'second', (0, 2)).status_code == 200
    assert state(session_factory, ids['final']) == ('PENDING', ids['alpha'], ids['delta'], None)
    assert client.post(path(ids, 'final')+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    before = len(match_logs(session_factory))
    assert result(client, headers, ids).status_code == 200  # replay even after the destination starts
    assert len(match_logs(session_factory)) == before
    assert result(client, headers, ids, 'final', (3, 1)).status_code == 200
    assert client.get(path(ids, 'final')).json()['result']['winner_id'] == ids['alpha']
    assert match_logs(session_factory)[-1].details['advancement'] is None
    with session_factory() as db:
        assert db.get(Tournament, ids['tid']).status == 'ONGOING'  # completion stays explicit


@pytest.mark.parametrize('slot,status,other', [(999999, 'PENDING', None), (None, 'ONGOING', None),
                                             (None, 'CANCELLED', None), (None, 'PENDING', 'alpha')])
def test_destination_conflict_rolls_back_source(access, session_factory, bracket_results, slot, status, other):
    client, headers, _, _, _ = access
    ids = bracket_results
    with session_factory.begin() as db:
        final = db.get(Match, ids['final'])
        final.team1_id = ids['beta'] if slot else None
        final.status = status
        final.team2_id = ids.get(other)
    response = result(client, headers, ids)
    assert response.status_code == 409
    assert state(session_factory, ids['first'])[::3] == ('ONGOING', None)
    assert match_logs(session_factory) == []


def test_same_winner_in_pending_destination_is_a_safe_noop(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    with session_factory.begin() as db:
        db.get(Match, ids['final']).team1_id = ids['alpha']
    assert result(client, headers, ids).status_code == 200
    assert state(session_factory, ids['final'])[1] == ids['alpha']
    assert len(match_logs(session_factory)) == 1


@pytest.mark.parametrize('replacement', [None, 'beta'])
def test_replay_detects_missing_or_different_slot_without_repair(access, session_factory, bracket_results, replacement):
    client, headers, *_ = access
    ids = bracket_results
    assert result(client, headers, ids).status_code == 200
    with session_factory.begin() as db:
        db.get(Match, ids['final']).team1_id = ids.get(replacement)
    assert result(client, headers, ids).status_code == 409
    assert state(session_factory, ids['final'])[1] == ids.get(replacement)
    assert len(match_logs(session_factory)) == 1


def test_audit_failure_rolls_back_result_and_slot(access, session_factory, bracket_results, monkeypatch):
    client, headers, *_ = access
    ids = bracket_results
    def broken(*args, **kwargs):
        raise RuntimeError('injected audit failure')
    monkeypatch.setattr('routes.match_results.record_audit', broken)
    with pytest.raises(RuntimeError, match='injected audit failure'):
        result(client, headers, ids)
    assert state(session_factory, ids['first']) == ('ONGOING', ids['alpha'], ids['beta'], None)
    assert state(session_factory, ids['final']) == ('PENDING', None, None, None)
    assert match_logs(session_factory) == []


@pytest.mark.parametrize('payload', [{'round_no': 2}, {'stage_id': 1}, {'team1_id': 1}, {'team2_id': 2},
                                    {'round_no': 2, 'scheduled_at': None}])
def test_managed_structure_cannot_be_patched(access, session_factory, bracket_results, payload):
    client, headers, *_ = access
    ids = bracket_results
    assert client.patch(path(ids, 'final'), headers=headers('organizer'), json=payload).status_code == 409
    assert match_logs(session_factory) == []


def test_schedule_only_caps_and_delete_cancel_guards(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    caps = client.get(path(ids, 'final')+'/capabilities', headers=headers('organizer')).json()
    assert caps['can_update'] and caps['editable_fields'] == ['scheduled_at']
    assert not caps['can_delete'] and not caps['can_cancel'] and not caps['can_start']
    assert client.post(path(ids, 'final')+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 409
    assert client.delete(path(ids, 'final'), headers=headers('organizer')).status_code == 409
    assert client.post(path(ids)+'/status', headers=headers('organizer'), json={'status': 'CANCELLED'}).status_code == 409
    schedule = {'scheduled_at': '2026-11-15T19:30:00+07:00'}
    assert client.patch(path(ids, 'final'), headers=headers('organizer'), json=schedule).status_code == 200
    assert client.patch(path(ids, 'final'), headers=headers('organizer'), json={'scheduled_at': '2026-11-15T12:30:00Z'}).status_code == 200
    assert len(match_logs(session_factory)) == 1
    assert client.patch(path(ids, 'final'), headers=headers('organizer'), json={'scheduled_at': None}).status_code == 200
    assert len(match_logs(session_factory)) == 2


def test_manual_match_cannot_enter_managed_stage(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    payload = dict(stage_id=ids['empty_stage'], round_no=1, team1_id=ids['alpha'], team2_id=ids['beta'])
    assert client.post(f"/api/v1/tournaments/{ids['tid']}/matches", headers=headers('organizer'), json=payload).status_code == 409
    with session_factory.begin() as db:
        db.get(Match, ids['match']).status = 'PENDING'
    assert client.patch(path(ids, 'match'), headers=headers('organizer'), json={'stage_id': ids['empty_stage']}).status_code == 409
    assert match_logs(session_factory) == []


def test_legacy_next_match_link_does_not_advance(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    with session_factory.begin() as db:
        legacy = db.get(Match, ids['match'])
        legacy.status, legacy.next_match_id = 'ONGOING', ids['final']
    assert result(client, headers, ids, 'match').status_code == 200
    assert state(session_factory, ids['final']) == ('PENDING', None, None, None)
    assert 'bracket_id' not in match_logs(session_factory)[0].details


@pytest.mark.parametrize('phase', ['pending', 'cancelled', 'missing_metadata', 'done'])
def test_tournament_completion_requires_finished_complete_bracket(access, session_factory, bracket_results, phase):
    client, headers, *_ = access
    ids = bracket_results
    if phase != 'pending':
        complete_bracket(client, headers, ids)
    with session_factory.begin() as db:
        if phase == 'cancelled':
            final = db.get(Match, ids['final'])
            final.status, final.winner_id = 'CANCELLED', None
        if phase == 'missing_metadata':
            db.delete(db.get(BracketMatch, ids['second']))
    caps = client.get(f"/api/v1/tournaments/{ids['tid']}/capabilities", headers=headers('organizer')).json()
    assert ('COMPLETED' in caps['allowed_status_transitions']) == (phase == 'done')
    response = client.post(f"/api/v1/tournaments/{ids['tid']}/status", headers=headers('organizer'), json={'status': 'COMPLETED'})
    assert response.status_code == (200 if phase == 'done' else 409)


def test_pending_manual_match_also_blocks_completion(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    complete_bracket(client, headers, ids)
    with session_factory.begin() as db:
        db.get(Match, ids['match']).status = 'PENDING'
    target = f"/api/v1/tournaments/{ids['tid']}/status"
    assert client.post(target, headers=headers('organizer'), json={'status': 'COMPLETED'}).status_code == 409
    assert client.post(path(ids, 'match')+'/status', headers=headers('organizer'), json={'status': 'CANCELLED'}).status_code == 200
    assert client.post(target, headers=headers('organizer'), json={'status': 'COMPLETED'}).status_code == 200


def test_cancel_tournament_keeps_history_and_blocks_writes(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    assert result(client, headers, ids).status_code == 200
    before = [state(session_factory, ids[key]) for key in ['first', 'second', 'final']]
    target = f"/api/v1/tournaments/{ids['tid']}/status"
    assert client.post(target, headers=headers('organizer'), json={'status': 'CANCELLED'}).status_code == 200
    assert [state(session_factory, ids[key]) for key in ['first', 'second', 'final']] == before
    assert result(client, headers, ids, 'second').status_code == 409
    assert result(client, headers, ids).status_code == 200  # consistent replay is read-only
    assert len(match_logs(session_factory)) == 1


def test_format_cannot_change_after_bracket_creation(access, session_factory, bracket_results):
    client, headers, *_ = access
    ids = bracket_results
    with session_factory.begin() as db:
        db.get(Tournament, ids['tid']).status = 'UPCOMING'
    target = f"/api/v1/tournaments/{ids['tid']}"
    assert client.patch(target, headers=headers('organizer'), json={'format': 'ROUND_ROBIN'}).status_code == 409
    caps = client.get(target+'/capabilities', headers=headers('organizer')).json()
    assert 'format' not in caps['editable_fields']


@pytest.mark.parametrize('kind,expected', [('admin', 200), ('organizer', 200), ('scoped', 200),
                                         ('foreign', 403), ('global', 403), ('role_only', 403), ('own_roster', 403)])
def test_result_scope_is_enforced_for_managed_matches(access, session_factory, bracket_results, kind, expected):
    client, headers, users, _, roles = access
    ids = bracket_results
    actor = kind if kind in ('admin', 'organizer') else 'referee'
    with session_factory.begin() as db:
        if kind in ('scoped', 'foreign', 'global', 'own_roster'):
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                                  scope_type='GLOBAL' if kind == 'global' else 'TOURNAMENT',
                                  scope_id=None if kind == 'global' else ids['other' if kind == 'foreign' else 'tid']))
        if kind == 'own_roster':
            db.add(TournamentRoster(tournament_id=ids['tid'], team_id=ids['alpha'],
                                    user_id=users['referee'], role_in_team='SUBSTITUTE'))
    assert result(client, headers, ids, name=actor).status_code == expected
    assert len(match_logs(session_factory)) == (1 if expected == 200 else 0)
    assert state(session_factory, ids['final'])[1] == (ids['alpha'] if expected == 200 else None)


def test_commit_constraint_failure_rolls_back_result_destination_and_audit(access, session_factory, bracket_results, monkeypatch):
    client, headers, *_ = access
    ids = bracket_results
    from core.audit import record_audit
    def invalid_actor(db, user_id, action, resource, details):
        record_audit(db, 2147483647, action, resource, details)
    monkeypatch.setattr('routes.match_results.record_audit', invalid_actor)
    assert result(client, headers, ids).status_code == 409
    assert state(session_factory, ids['first']) == ('ONGOING', ids['alpha'], ids['beta'], None)
    assert state(session_factory, ids['final']) == ('PENDING', None, None, None)
    assert match_logs(session_factory) == []
