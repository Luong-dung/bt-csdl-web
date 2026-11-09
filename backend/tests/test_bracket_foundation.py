"""W46-01: stable tree, scope/input/preview validation and direct DB integrity."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from config.settings import get_settings
from core.brackets import (bracket_plan, can_create_bracket, ensure_bracket_input, issue_preview_token,
                           lock_bracket_context, lock_bracket_match_context, managed_match, verify_preview_token)
from core.matches import can_submit_result
from modules.identity.models import RoleAssignment, User
from modules.tournaments.bracket_schemas import BracketInput
from modules.tournaments.models import BracketMatch, Match, Stage, Tournament, TournamentBracket, TournamentRoster
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


@pytest.fixture
def bracket_case(session_factory, match_case):
    with session_factory.begin() as db:
        tournament = db.get(Tournament, match_case['tid'])
        tournament.status = 'UPCOMING'
        stage = Stage(tournament_id=tournament.tournament_id, name='Bracket', sequence_order=2)
        db.add(stage)
        db.flush()
        return match_case | {'empty_stage': stage.stage_id}


@pytest.mark.parametrize('count', [2, 4, 8, 16, 32, 64])
def test_plan_has_every_match_and_exact_destination_slots(count):
    data = BracketInput(stage_id=1, team_ids=list(range(1, count+1)))
    plan = bracket_plan(data)
    nodes = {(n.round_index, n.position): n for n in plan}
    assert len(plan) == len(nodes) == count-1
    assert [(n.team1_id, n.team2_id) for n in plan if n.round_index == 1] == list(zip(data.team_ids[::2], data.team_ids[1::2]))
    destinations = {}
    for node in plan:
        if node.round_index > 1:
            assert (node.team1_id, node.team2_id) == (None, None)
        if node.next_round is None:
            assert node.round_index == count.bit_length()-1
            assert (node.next_position, node.next_slot) == (None, None)
        else:
            key = (node.next_round, node.next_position)
            assert key in nodes and node.next_round == node.round_index+1
            destinations.setdefault(key, []).append(node.next_slot)
    assert len(destinations) == count//2-1
    assert all(sorted(slots) == [1, 2] for slots in destinations.values())


@pytest.mark.parametrize('payload', [
    {'stage_id': True, 'team_ids': [1, 2]}, {'stage_id': '1', 'team_ids': [1, 2]},
    {'stage_id': 0, 'team_ids': [1, 2]}, {'stage_id': 2147483648, 'team_ids': [1, 2]},
    {'stage_id': 1, 'team_ids': []}, {'stage_id': 1, 'team_ids': [1]},
    {'stage_id': 1, 'team_ids': [1, 2, 3]}, {'stage_id': 1, 'team_ids': [1, 1]},
    {'stage_id': 1, 'team_ids': [1, True]}, {'stage_id': 1, 'team_ids': [1, '2']},
    {'stage_id': 1, 'team_ids': [1, 2.0]}, {'stage_id': 1, 'team_ids': [1, 0]},
    {'stage_id': 1, 'team_ids': list(range(1, 129))},
    {'stage_id': 1, 'team_ids': [1, 2], 'winner_id': 1},
])
def test_input_rejects_unsupported_or_coerced_values(payload):
    with pytest.raises(ValidationError):
        BracketInput.model_validate(payload)


def test_input_and_preview_revalidate_live_roster(access, session_factory, bracket_case):
    _, _, _, teams, _ = access
    data = BracketInput(stage_id=bracket_case['empty_stage'], team_ids=[teams['Alpha'], teams['Beta']])
    with session_factory() as db:
        tournament = db.get(Tournament, bracket_case['tid'])
        fingerprint = ensure_bracket_input(db, tournament, data)
        token = issue_preview_token(tournament.tournament_id, fingerprint)
        verify_preview_token(token, tournament.tournament_id, fingerprint)
        assert ensure_bracket_input(db, tournament, data) == fingerprint
        reverse = data.model_copy(update={'team_ids': data.team_ids[::-1]})
        with pytest.raises(HTTPException) as error:
            verify_preview_token(token, tournament.tournament_id, ensure_bracket_input(db, tournament, reverse))
        assert error.value.status_code == 409
        roster = db.scalar(select(TournamentRoster).where(TournamentRoster.team_id == teams['Alpha']))
        roster.role_in_team = 'SUBSTITUTE'
        db.flush()
        with pytest.raises(HTTPException) as error:
            ensure_bracket_input(db, tournament, data)
        assert error.value.status_code == 422


@pytest.mark.parametrize('kind,code', [('unlocked', 409), ('ongoing', 409), ('format', 409),
                                       ('wrong_stage', 422), ('nonempty', 409), ('wrong_teams', 422)])
def test_create_input_validation(access, session_factory, bracket_case, kind, code):
    _, _, _, teams, _ = access
    with session_factory() as db:
        tournament = db.get(Tournament, bracket_case['tid'])
        stage_id = bracket_case['empty_stage']
        ids = [teams['Alpha'], teams['Beta']]
        if kind == 'unlocked':
            tournament.roster_locked_at = None
        elif kind == 'ongoing':
            tournament.status = 'ONGOING'
        elif kind == 'format':
            tournament.format = 'DOUBLE_ELIM'
        elif kind == 'wrong_stage':
            stage_id = bracket_case['other_stage']
        elif kind == 'nonempty':
            stage_id = bracket_case['stage']
        elif kind == 'wrong_teams':
            ids[1] = 2147483647
        with pytest.raises(HTTPException) as error:
            ensure_bracket_input(db, tournament, BracketInput(stage_id=stage_id, team_ids=ids))
        assert error.value.status_code == code


@pytest.mark.parametrize('name,expected', [('admin', True), ('organizer', True), ('referee', False),
                                          ('manager', False), ('viewer', False)])
def test_capability_and_lock_follow_manager_policy(access, session_factory, bracket_case, name, expected):
    client, headers, users, _, _ = access
    tid = bracket_case['tid']
    response = client.get(f'/api/v1/tournaments/{tid}/capabilities', headers=headers(name))
    assert response.status_code == 200
    assert response.json()['can_create_bracket'] is expected
    assert response.headers['cache-control'] == 'private, no-store'
    with session_factory() as db:
        actor = db.get(User, users[name])
        if expected:
            tournament, actor = lock_bracket_context(db, tid, actor)
            assert can_create_bracket(db, tournament, actor)
        else:
            with pytest.raises(HTTPException) as error:
                lock_bracket_context(db, tid, actor)
            assert error.value.status_code == 403


def add_bracket(db, case, users, count=2):
    bracket = TournamentBracket(tournament_id=case['tid'], stage_id=case['empty_stage'],
                                team_count=count, round_count=count.bit_length()-1,
                                team_order=list(range(1, count+1)), created_by=users['organizer'])
    db.add(bracket)
    db.flush()
    return bracket


def add_node(db, bracket, round_no, pos, **changes):
    round_index, position = round_no, pos
    match = Match(tournament_id=bracket.tournament_id, stage_id=bracket.stage_id, round_no=round_index)
    db.add(match)
    db.flush()
    final = round_index == bracket.round_count
    values = dict(match_id=match.match_id, bracket_id=bracket.bracket_id, tournament_id=bracket.tournament_id,
                  stage_id=bracket.stage_id, round_count=bracket.round_count, round_index=round_index, position=position,
                  next_round=None if final else round_index+1, next_position=None if final else (position+1)//2,
                  next_slot=None if final else 1+(position-1)%2)
    values.update(changes)
    node = BracketMatch(**values)
    db.add(node)
    db.flush()
    return node


def test_managed_graph_preserves_legacy_match_and_locks_capability(access, session_factory, bracket_case):
    client, headers, users, _, _ = access
    with session_factory.begin() as db:
        bracket = add_bracket(db, bracket_case, users, count=4)
        final = add_node(db, bracket, 2, 1)
        first = add_node(db, bracket, 1, 1)
        second = add_node(db, bracket, 1, 2)
        assert (first.next_slot, second.next_slot) == (1, 2)
        assert managed_match(db, final.match_id) is final
        assert managed_match(db, bracket_case['match']) is None
        assert db.get(Match, bracket_case['match']).next_match_id is None
    response = client.get(f"/api/v1/tournaments/{bracket_case['tid']}/capabilities", headers=headers('organizer'))
    assert response.json()['can_create_bracket'] is False


@pytest.mark.parametrize('changes', [
    {'round_index': 0}, {'position': 0}, {'position': 3}, {'next_slot': 2},
    {'next_round': None}, {'next_position': None}, {'next_slot': None},
    {'next_round': 1}, {'next_position': 2},
])
def test_direct_writes_reject_invalid_edges(access, session_factory, bracket_case, changes):
    _, _, users, _, _ = access
    with session_factory() as db:
        bracket = add_bracket(db, bracket_case, users, count=4)
        add_node(db, bracket, 2, 1)
        with pytest.raises(IntegrityError):
            add_node(db, bracket, 1, 1, **changes)
        db.rollback()


def test_direct_writes_reject_foreign_match_and_duplicate_bracket(access, session_factory, bracket_case):
    _, _, users, _, _ = access
    with session_factory() as db:
        bracket = add_bracket(db, bracket_case, users)
        with pytest.raises(IntegrityError):
            db.execute(text('INSERT INTO bracket_matches (match_id, bracket_id, tournament_id, stage_id, round_count, round_index, position) '
                            'VALUES (:match, :bracket, :tid, :stage, 1, 1, 1)'),
                       dict(match=bracket_case['match'], bracket=bracket.bracket_id, tid=bracket.tournament_id, stage=bracket.stage_id))
        db.rollback()
    with session_factory() as db:
        add_bracket(db, bracket_case, users)
        with pytest.raises(IntegrityError):
            add_bracket(db, bracket_case, users)
        db.rollback()


@pytest.mark.parametrize('kind', ['expired', 'wrong_purpose', 'wrong_tournament', 'wrong_fingerprint', 'tampered'])
def test_preview_cannot_be_reused_outside_snapshot(kind):
    payload = dict(purpose='bracket-preview-v1', tid=1, fingerprint='abc', exp=datetime.now(timezone.utc)+timedelta(minutes=15))
    if kind == 'expired':
        payload['exp'] = datetime.now(timezone.utc)-timedelta(seconds=1)
    elif kind == 'wrong_purpose':
        payload['purpose'] = 'access'
    elif kind == 'wrong_tournament':
        payload['tid'] = 2
    elif kind == 'wrong_fingerprint':
        payload['fingerprint'] = 'def'
    token = jwt.encode(payload, get_settings().JWT_SECRET, algorithm='HS256')
    if kind == 'tampered':
        token = 'invalid.'+token
    with pytest.raises(HTTPException) as error:
        verify_preview_token(token, 1, 'abc')
    assert error.value.status_code == 409


def test_result_context_locks_managed_destination_but_not_legacy_edges(access, session_factory, bracket_case):
    _, _, users, _, _ = access
    with session_factory.begin() as db:
        bracket = add_bracket(db, bracket_case, users, 4)
        final = add_node(db, bracket, 2, 1)
        first = add_node(db, bracket, 1, 1)
        add_node(db, bracket, 1, 2)
        assert final.match_id < first.match_id
        final_id, first_id = final.match_id, first.match_id
        db.get(Match, bracket_case['match']).next_match_id = final_id
    with session_factory() as db:
        actor = db.get(User, users['organizer'])
        _, source, destination, actor = lock_bracket_match_context(db, bracket_case['tid'], first_id, actor, can_submit_result)
        assert source.match_id == first_id and destination.match_id == final_id
        _, _, destination, _ = lock_bracket_match_context(db, bracket_case['tid'], bracket_case['match'], actor, can_submit_result)
        assert destination is None


@pytest.mark.parametrize('scope,expected', [('tid', True), ('other', False)])
def test_scoped_organizer_can_create_only_in_assigned_tournament(access, session_factory, bracket_case, scope, expected):
    _, _, users, _, roles = access
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users['viewer'], role_id=roles['ORGANIZER'], scope_type='TOURNAMENT',
                              scope_id=bracket_case[scope]))
    with session_factory() as db:
        assert can_create_bracket(db, db.get(Tournament, bracket_case['tid']), db.get(User, users['viewer'])) is expected
