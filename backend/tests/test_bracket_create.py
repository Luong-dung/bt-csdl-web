"""W46-03 API: bracket preview/create, idempotent replay, live revalidation and rollback."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select

from config.settings import get_settings
from core.brackets import PREVIEW_AUDIENCE, issue_preview_token
from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import Team
from modules.tournaments.models import (BracketMatch, Match, Stage, Tournament, TournamentBracket,
                                        TournamentRegistration, TournamentRoster)
from test_bracket_foundation import bracket_case
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def add_teams(factory, ids, roles, count):
    """Top the tournament up to `count` APPROVED teams, each with a locked PLAYER snapshot."""
    now = datetime.now(timezone.utc)
    added = []
    with factory.begin() as db:
        tour = db.get(Tournament, ids['tid'])
        for index in range(count-2):
            name = f'Team{index:02d}'
            team = Team(name=name, tag=f'T{index:02d}', game_id=tour.game_id)
            user = User(username=name, email=name+'@example.com', password_hash='unused', role_id=roles['PLAYER'])
            db.add_all([team, user])
            db.flush()
            db.add(TournamentRegistration(tournament_id=ids['tid'], team_id=team.team_id, status='APPROVED',
                                          reviewed_at=now))
            db.add(TournamentRoster(tournament_id=ids['tid'], team_id=team.team_id, user_id=user.user_id,
                                    role_in_team='PLAYER', display_name=name))
            added.append(team.team_id)
    return added


@pytest.fixture
def four(access, session_factory, bracket_case):
    _, _, _, teams, roles = access
    order = [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, 4)]
    return bracket_case | {'order': order}


def url(ids, suffix=''):
    return f"/api/v1/tournaments/{ids['tid']}/bracket{suffix}"


def body(ids, order=None, stage='empty_stage'):
    return {'stage_id': ids[stage], 'team_ids': list(ids['order'] if order is None else order)}


def preview(client, headers, ids, order=None, name='organizer'):
    return client.post(url(ids, '/preview'), headers=headers(name), json=body(ids, order))


def create(client, headers, ids, token, order=None, name='organizer', stage='empty_stage'):
    return client.post(url(ids), headers=headers(name), json=body(ids, order, stage) | {'preview_token': token})


def counts(factory, tid):
    with factory() as db:
        return (db.scalar(select(func.count()).select_from(TournamentBracket)),
                db.scalar(select(func.count()).select_from(Match).where(Match.tournament_id == tid)),
                db.scalar(select(func.count()).select_from(BracketMatch)),
                db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.resource == 'bracket')))


def test_preview_is_read_only_uncached_and_shows_pairs(access, session_factory, four):
    client, headers, *_ = access
    before = counts(session_factory, four['tid'])
    response = preview(client, headers, four)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    data = response.json()
    assert (data['team_count'], data['round_count'], data['expires_in']) == (4, 2, 900)
    assert [t['team_id'] for t in data['teams']] == four['order'] and data['teams'][0]['name'] == 'Alpha'
    first = [(m['team1_id'], m['team2_id']) for m in data['matches'] if m['round_index'] == 1]
    assert first == [tuple(four['order'][:2]), tuple(four['order'][2:])]
    final = data['matches'][-1]
    assert (final['round_index'], final['team1_id'], final['team2_id'], final['next_round']) == (2, None, None, None)
    assert all('match_id' not in m for m in data['matches'])
    assert counts(session_factory, four['tid']) == before


def test_create_writes_full_tree_in_one_audited_transaction(access, session_factory, four):
    client, headers, users, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    response = create(client, headers, four, token)
    assert response.status_code == 201
    assert response.headers['cache-control'] == 'private, no-store'
    data = response.json()
    assert (data['team_count'], data['round_count'], data['team_ids']) == (4, 2, four['order'])
    nodes = data['matches']
    assert [(n['round_index'], n['position']) for n in nodes] == [(1, 1), (1, 2), (2, 1)]
    final_id = nodes[2]['match']['match_id']
    assert [(n['next_match_id'], n['next_slot']) for n in nodes] == [(final_id, 1), (final_id, 2), (None, None)]
    assert [n['match']['team1']['team_id'] for n in nodes[:2]] == [four['order'][0], four['order'][2]]
    assert nodes[2]['match']['team1'] is None and nodes[2]['match']['team2'] is None
    assert {n['match']['status'] for n in nodes} == {'PENDING'} and all(n['match']['result'] is None for n in nodes)
    assert {n['match']['stage_id'] for n in nodes} == {four['empty_stage']}
    with session_factory() as db:
        matches = [db.get(Match, n['match']['match_id']) for n in nodes]
        assert [m.round_no for m in matches] == [1, 1, 2]
        assert all(m.next_match_id is None for m in matches)  # edges live only in metadata
        [log] = db.scalars(select(AuditLog).where(AuditLog.resource == 'bracket'))
        assert (log.action, log.user_id) == ('BRACKET_CREATED', users['organizer'])
        assert log.details['bracket_id'] == data['bracket_id'] and log.details['team_ids'] == four['order']
        assert sorted(log.details['match_ids']) == sorted(m.match_id for m in matches)
    caps = client.get(f"/api/v1/tournaments/{four['tid']}/capabilities", headers=headers('organizer')).json()
    assert caps['can_create_bracket'] is False
    assert preview(client, headers, four).status_code == 409


def test_replay_returns_same_bracket_and_conflicting_input_is_rejected(access, session_factory, four):
    client, headers, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    first = create(client, headers, four, token)
    after = counts(session_factory, four['tid'])
    # A retry after timeout replays even when the token is no longer valid.
    replay = create(client, headers, four, 'expired-or-garbage')
    assert replay.status_code == 200 and replay.json() == first.json()
    assert counts(session_factory, four['tid']) == after
    reordered = four['order'][::-1]
    assert create(client, headers, four, token, order=reordered).status_code == 409
    with session_factory.begin() as db:
        other = Stage(tournament_id=four['tid'], name='Spare', sequence_order=3)
        db.add(other)
        db.flush()
        four = four | {'spare': other.stage_id}
    assert create(client, headers, four, token, stage='spare').status_code == 409
    assert counts(session_factory, four['tid']) == after


def test_token_must_match_live_input(access, session_factory, four):
    client, headers, users, teams, roles = access
    token = preview(client, headers, four).json()['preview_token']
    before = counts(session_factory, four['tid'])
    swapped = [four['order'][1], four['order'][0], *four['order'][2:]]
    assert create(client, headers, four, token, order=swapped).status_code == 409
    expired = jwt.encode({'purpose': 'bracket-preview-v1', 'aud': PREVIEW_AUDIENCE, 'tid': four['tid'],
                          'fingerprint': 'x', 'exp': datetime.now(timezone.utc)-timedelta(seconds=1)},
                         get_settings().JWT_SECRET, algorithm='HS256')
    assert create(client, headers, four, expired).status_code == 409
    assert create(client, headers, four, issue_preview_token(four['other'], 'x', 1)).status_code == 409
    access_token = headers('organizer')['Authorization'].split()[1]
    assert create(client, headers, four, access_token).status_code == 409
    # Roster snapshot changes after preview: the old token no longer matches.
    with session_factory.begin() as db:
        db.add(TournamentRoster(tournament_id=four['tid'], team_id=teams['Alpha'], user_id=users['admin'],
                                role_in_team='PLAYER', display_name='late'))
    assert create(client, headers, four, token).status_code == 409
    assert counts(session_factory, four['tid']) == before
    fresh = preview(client, headers, four).json()['preview_token']
    assert create(client, headers, four, fresh).status_code == 201


def test_live_validation_runs_again_on_create(access, session_factory, four):
    client, headers, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    with session_factory.begin() as db:
        db.scalar(select(TournamentRegistration).where(
            TournamentRegistration.team_id == four['order'][3])).status = 'REJECTED'
    assert create(client, headers, four, token).status_code == 422
    with session_factory.begin() as db:
        db.scalar(select(TournamentRegistration).where(
            TournamentRegistration.team_id == four['order'][3])).status = 'APPROVED'
        db.get(Tournament, four['tid']).status = 'ONGOING'
    assert create(client, headers, four, token).status_code == 409
    assert counts(session_factory, four['tid'])[0] == 0


@pytest.mark.parametrize('case,status', [
    ('three_teams', 422), ('missing_team', 422), ('foreign_stage', 422), ('used_stage', 409),
    ('ongoing', 409), ('unlocked', 409), ('no_tournament', 404), ('no_tournament_bad_body', 422),
])
def test_preview_and_create_reject_invalid_input(access, session_factory, four, case, status):
    client, headers, *_ = access
    payload = body(four)
    tid = four['tid']
    if case == 'three_teams':
        payload['team_ids'] = four['order'][:3]
    elif case == 'missing_team':
        payload['team_ids'] = four['order'][:2]
    elif case == 'foreign_stage':
        payload['stage_id'] = four['other_stage']
    elif case == 'used_stage':
        payload['stage_id'] = four['stage']
    elif case in ('ongoing', 'unlocked'):
        with session_factory.begin() as db:
            tour = db.get(Tournament, tid)
            if case == 'ongoing':
                tour.status = 'ONGOING'
            else:
                tour.roster_locked_at = None
    elif case.startswith('no_tournament'):
        tid = 2147483647
        if case.endswith('bad_body'):
            payload['team_ids'] = [1, 2, 3]
    base = f'/api/v1/tournaments/{tid}/bracket'
    before = counts(session_factory, four['tid'])
    assert client.post(base+'/preview', headers=headers('organizer'), json=payload).status_code == status
    created = client.post(base, headers=headers('organizer'), json=payload | {'preview_token': 'x'})
    assert created.status_code == status
    assert created.headers['cache-control'] == 'private, no-store'
    assert counts(session_factory, four['tid']) == before


@pytest.mark.parametrize('who', ['anonymous', 'viewer', 'manager', 'referee', 'global_referee'])
def test_only_tournament_managers_preview_or_create(access, session_factory, four, who):
    client, headers, users, _, roles = access
    token = preview(client, headers, four).json()['preview_token']
    if who.endswith('referee'):
        with session_factory.begin() as db:
            scope = ('TOURNAMENT', four['tid']) if who == 'referee' else ('GLOBAL', None)
            db.add(RoleAssignment(user_id=users['referee'], role_id=roles['REFEREE'],
                                  scope_type=scope[0], scope_id=scope[1]))
    name = 'referee' if who.endswith('referee') else who
    auth = {} if who == 'anonymous' else headers(name)
    expected = 401 if who == 'anonymous' else 403
    assert client.post(url(four, '/preview'), headers=auth, json=body(four)).status_code == expected
    assert client.post(url(four), headers=auth, json=body(four) | {'preview_token': token}).status_code == expected
    assert counts(session_factory, four['tid'])[0] == 0


def test_admin_can_create_and_audit_failure_rolls_back(access, session_factory, four, monkeypatch):
    client, headers, *_ = access
    before = counts(session_factory, four['tid'])
    token = preview(client, headers, four, name='admin').json()['preview_token']

    def broken(*args, **kwargs):
        raise RuntimeError('injected audit failure')
    monkeypatch.setattr('routes.brackets.record_audit', broken)
    with pytest.raises(RuntimeError, match='injected audit failure'):
        create(client, headers, four, token, name='admin')
    assert counts(session_factory, four['tid']) == before
    monkeypatch.undo()
    assert create(client, headers, four, token, name='admin').status_code == 201


def test_created_structure_is_guarded_by_w46_02(access, session_factory, four):
    client, headers, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    nodes = create(client, headers, four, token).json()['matches']
    match_url = f"/api/v1/tournaments/{four['tid']}/matches"
    final = nodes[2]['match']['match_id']
    assert client.delete(f'{match_url}/{final}', headers=headers('organizer')).status_code == 409
    assert client.patch(f'{match_url}/{final}', headers=headers('organizer'), json={'round_no': 3}).status_code == 409
    manual = {'stage_id': four['empty_stage'], 'round_no': 1, 'team1_id': four['order'][0], 'team2_id': four['order'][1]}
    assert client.post(match_url, headers=headers('organizer'), json=manual).status_code == 409
    caps = client.get(f'{match_url}/{nodes[0]["match"]["match_id"]}/capabilities', headers=headers('organizer')).json()
    assert caps['can_delete'] is False and caps['editable_fields'] == ['scheduled_at']
    # next_match_id stays NULL, so the legacy-link guard does not block rescheduling.
    moved = client.patch(f'{match_url}/{final}', headers=headers('organizer'),
                         json={'scheduled_at': '2030-01-02T03:04:00Z'})
    assert moved.status_code == 200 and moved.json()['scheduled_at'].startswith('2030-01-02T03:04')


@pytest.mark.parametrize('count', [2, 8, 64])
def test_supported_sizes_create_every_edge(access, session_factory, bracket_case, count):
    client, headers, _, teams, roles = access
    ids = bracket_case | {'order': [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, count)]}
    token = preview(client, headers, ids).json()['preview_token']
    data = create(client, headers, ids, token).json()
    nodes = data['matches']
    rounds = count.bit_length()-1
    assert (len(nodes), data['round_count']) == (count-1, rounds)
    by_id = {n['match']['match_id']: n for n in nodes}
    assert len(by_id) == count-1
    first_round = [t for n in nodes if n['round_index'] == 1 for t in (n['match']['team1']['team_id'],
                                                                       n['match']['team2']['team_id'])]
    assert first_round == ids['order']
    incoming = {}
    for node in nodes:
        if node['round_index'] == rounds:
            assert node['next_match_id'] is None
            continue
        target = by_id[node['next_match_id']]
        assert target['round_index'] == node['round_index']+1
        incoming.setdefault(node['next_match_id'], []).append(node['next_slot'])
    assert all(sorted(slots) == [1, 2] for slots in incoming.values()) and len(incoming) == count//2-1


def test_preview_token_is_bound_to_the_manager_who_previewed(access, session_factory, four):
    client, headers, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    assert jwt.decode(token, options={'verify_signature': False})['sub'] is not None
    # Another manager (ADMIN) may create, but only with a preview of their own.
    assert create(client, headers, four, token, name='admin').status_code == 409
    assert counts(session_factory, four['tid'])[0] == 0
    own = preview(client, headers, four, name='admin').json()['preview_token']
    assert create(client, headers, four, own, name='admin').status_code == 201


def test_replay_after_tournament_started_returns_current_state(access, session_factory, four):
    client, headers, *_ = access
    token = preview(client, headers, four).json()['preview_token']
    created = create(client, headers, four, token).json()
    with session_factory.begin() as db:
        db.get(Tournament, four['tid']).status = 'ONGOING'
    first = created['matches'][0]['match']['match_id']
    match_url = f"/api/v1/tournaments/{four['tid']}/matches/{first}"
    assert client.post(match_url+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    assert client.put(match_url+'/result', headers=headers('organizer'),
                      json={'score_team1': 2, 'score_team2': 0}).status_code == 200
    before = counts(session_factory, four['tid'])
    replay = create(client, headers, four, token)
    assert replay.status_code == 200
    nodes = replay.json()['matches']
    assert nodes[0]['match']['status'] == 'COMPLETED' and nodes[0]['match']['result']['winner_id'] == four['order'][0]
    assert nodes[2]['match']['team1']['team_id'] == four['order'][0]
    assert counts(session_factory, four['tid']) == before
    # A different input hits the replay-mismatch branch (409), never a second bracket.
    assert create(client, headers, four, token, order=four['order'][::-1]).status_code == 409
