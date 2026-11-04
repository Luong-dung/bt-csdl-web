"""W45-01 match foundation: DB constraints, shared checkers, link validation, lock helpers."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from core.matches import (as_utc, to_utc, can_cancel_match, can_manage_matches, can_start_match, can_submit_result,
                          ensure_match_teams, ensure_stage_in_tournament, lock_match_context, match_cancellable,
                          match_editable, match_result_open, match_startable, match_state)
from modules.identity.models import RoleAssignment, User
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Match, Stage, Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


@pytest.fixture
def match_case(access, session_factory):
    """Locked ONGOING tournament with two APPROVED teams that each have a PLAYER snapshot."""
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    other = organizer_tournament(client, headers)
    now = datetime.now(timezone.utc)
    with session_factory.begin() as db:
        for name, user in (('Alpha', 'viewer'), ('Beta', 'manager')):
            db.add(TournamentRegistration(tournament_id=tid, team_id=teams[name], status='APPROVED', reviewed_at=now))
            db.add(TournamentRoster(tournament_id=tid, team_id=teams[name], user_id=users[user],
                                    role_in_team='PLAYER', display_name=user))
        tournament = db.get(Tournament, tid)
        tournament.status, tournament.roster_locked_at = 'ONGOING', now
        stages = [Stage(tournament_id=tid, name='Group', sequence_order=1),
                  Stage(tournament_id=other, name='Other', sequence_order=1)]
        db.add_all(stages)
        db.flush()
        match = Match(tournament_id=tid, stage_id=stages[0].stage_id, round_no=1,
                      team1_id=teams['Alpha'], team2_id=teams['Beta'])
        db.add(match)
        db.flush()
        ids = {'tid': tid, 'other': other, 'stage': stages[0].stage_id, 'other_stage': stages[1].stage_id,
               'match': match.match_id}
    return ids


def insert(db, **values):
    row = dict(round_no=1, score_team1=0, score_team2=0, status='PENDING') | values
    db.add(Match(**row))
    db.flush()


@pytest.mark.parametrize('case,constraint', [
    ({'status': 'DONE'}, 'ck_matches_status'),
    ({'round_no': 0}, 'ck_matches_round'),
    ({'score_team1': -1}, 'ck_matches_scores'),
    ({'team2': 'Alpha'}, 'ck_matches_distinct_teams'),
    # COMPLETED so ck_matches_result cannot reject first; winner is outside the match.
    ({'winner': 'Gamma', 'status': 'COMPLETED'}, 'ck_matches_winner_team'),
    ({'team1': None, 'winner': 'Gamma', 'status': 'COMPLETED'}, 'ck_matches_winner_team'),  # NULL team must not let it pass
    ({'team1': None, 'winner': 'Beta', 'status': 'COMPLETED'}, 'ck_matches_winner_team'),
    ({'status': 'COMPLETED'}, 'ck_matches_result'),
    ({'winner': 'Alpha'}, 'ck_matches_result'),
    ({'stage': 'other_stage'}, None),  # composite FK: stage of another tournament
])
def test_database_rejects_invalid_direct_writes(access, session_factory, match_case, case, constraint):
    bad = dict(case)  # never mutate the shared parametrize dict
    with session_factory.begin() as db:
        db.add(Team(name='Gamma', tag='G', game_id=1))
    with session_factory() as db:
        teams = {t.name: t.team_id for t in db.scalars(select(Team))} | {None: None}
        values = {'tournament_id': match_case['tid'], 'stage_id': match_case[bad.pop('stage', 'stage')],
                  'team1_id': teams[bad.pop('team1', 'Alpha')], 'team2_id': teams[bad.pop('team2', 'Beta')]}
        if 'winner' in bad:
            values['winner_id'] = teams[bad.pop('winner')]
        with pytest.raises(IntegrityError) as error:
            insert(db, **values, **bad)
        if constraint:
            assert constraint in str(error.value.orig)
        db.rollback()


def test_database_accepts_completed_result_and_utc_schedule(access, session_factory, match_case):
    _, _, _, teams, _ = access
    kickoff = datetime(2026, 11, 5, 19, 0, tzinfo=timezone(timedelta(hours=7)))
    with session_factory.begin() as db:
        insert(db, tournament_id=match_case['tid'], stage_id=match_case['stage'], team1_id=teams['Alpha'],
               team2_id=teams['Beta'], score_team1=2, score_team2=1, winner_id=teams['Alpha'],
               status='COMPLETED', scheduled_at=to_utc(kickoff))
    with session_factory() as db:
        row = db.scalar(select(Match).where(Match.status == 'COMPLETED'))
        # Same instant written with different offsets compares equal once read back as UTC.
        assert as_utc(row.scheduled_at) == datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        assert as_utc(row.scheduled_at) == to_utc(datetime(2026, 11, 5, 7, 0, tzinfo=timezone(timedelta(hours=-5))))
        assert match_state(row)['scheduled_at'] == '2026-11-05T12:00:00+00:00'
        assert match_state(row)['winner_id'] == teams['Alpha']
    with pytest.raises(HTTPException) as error:
        to_utc(datetime(2026, 11, 5, 19, 0))
    assert error.value.status_code == 422


@pytest.mark.parametrize('edge', [
    datetime(1, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=7))),
    datetime(9999, 12, 31, 23, 0, tzinfo=timezone(timedelta(hours=-7))),
])
def test_to_utc_out_of_range_is_422_not_500(edge):
    with pytest.raises(HTTPException) as error:
        to_utc(edge)
    assert error.value.status_code == 422


def test_as_utc_normalizes_aware_values_from_any_session_timezone():
    # PostgreSQL returns values in the session TimeZone, e.g. Asia/Ho_Chi_Minh.
    local = datetime(2026, 11, 5, 19, 0, tzinfo=timezone(timedelta(hours=7)))
    assert as_utc(local) == local and as_utc(local).utcoffset() == timedelta(0)
    assert as_utc(local).isoformat() == '2026-11-05T12:00:00+00:00'
    assert as_utc(datetime(2026, 11, 5, 12, 0)).isoformat() == '2026-11-05T12:00:00+00:00'
    assert as_utc(None) is None


def assign(session_factory, users, roles, user, role, scope_type, scope_id):
    with session_factory.begin() as db:
        db.add(RoleAssignment(user_id=users[user], role_id=roles[role], scope_type=scope_type, scope_id=scope_id))


@pytest.mark.parametrize('user,assignment,manage,referee', [
    ('admin', None, True, True),
    ('organizer', None, True, True),             # creator of the tournament
    ('referee', None, False, False),             # REFEREE role on the user grants nothing
    ('referee', ('GLOBAL', None), False, False),
    ('referee', ('TOURNAMENT', 'other'), False, False),
    ('referee', ('TOURNAMENT', 'tid'), False, True),
    ('admin', ('TOURNAMENT', 'tid'), True, True),
    # Conflict of interest: a tournament referee who plays for (roster/active member of) either team.
    ('viewer', ('TOURNAMENT', 'tid'), False, False),   # Alpha PLAYER in the roster snapshot
    ('manager', ('TOURNAMENT', 'tid'), False, False),  # Beta PLAYER in the roster snapshot
    ('manager', None, False, False),             # team manager of a playing team
    ('viewer', None, False, False),              # PLAYER of a playing team
])
def test_shared_checkers_follow_tournament_scope(access, session_factory, match_case, user, assignment, manage, referee):
    _, _, users, _, roles = access
    if assignment:
        scope_type, scope = assignment
        assign(session_factory, users, roles, user, 'REFEREE', scope_type, match_case.get(scope))
    with session_factory() as db:
        tournament, match = db.get(Tournament, match_case['tid']), db.get(Match, match_case['match'])
        actor = db.get(User, users[user])
        assert can_manage_matches(tournament, actor) is manage
        assert can_cancel_match(db, tournament, match, actor) is manage
        assert can_start_match(db, tournament, match, actor) is referee
        assert can_submit_result(db, tournament, match, actor) is referee


def test_referee_who_is_active_member_of_a_playing_team_is_blocked(access, session_factory, match_case):
    _, _, users, teams, roles = access
    assign(session_factory, users, roles, 'referee', 'REFEREE', 'TOURNAMENT', match_case['tid'])
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=teams['Beta'], user_id=users['referee'], role_in_team='MANAGER'))
    with session_factory() as db:
        tournament, match = db.get(Tournament, match_case['tid']), db.get(Match, match_case['match'])
        actor = db.get(User, users['referee'])
        assert not can_submit_result(db, tournament, match, actor)
        assert not can_start_match(db, tournament, match, actor)
        db.execute(text("UPDATE team_memberships SET status='LEFT', left_date=CURRENT_DATE WHERE user_id=:u"),
                   {'u': users['referee']})
        assert can_submit_result(db, tournament, match, actor)
        db.rollback()


def test_lock_context_rechecks_after_lock_and_scopes_404(access, session_factory, match_case):
    _, _, users, _, roles = access
    assign(session_factory, users, roles, 'referee', 'REFEREE', 'TOURNAMENT', match_case['tid'])
    with session_factory() as db:
        actor = db.get(User, users['referee'])
        tournament, match, actor = lock_match_context(db, match_case['tid'], match_case['match'], actor,
                                                      can_submit_result)
        assert match.match_id == match_case['match'] and tournament.tournament_id == match_case['tid']
        db.rollback()
        with pytest.raises(HTTPException) as error:
            lock_match_context(db, match_case['other'], match_case['match'], actor, can_submit_result)
        assert error.value.status_code == 404
        db.rollback()
        with pytest.raises(HTTPException) as error:
            lock_match_context(db, match_case['tid'], match_case['match'], actor, can_cancel_match)
        assert error.value.status_code == 403
        db.rollback()
    # Revoked between the pre-check and the lock: the recheck after reloading the actor wins.
    with session_factory() as db:
        actor = db.get(User, users['referee'])
        assert can_submit_result(db, db.get(Tournament, match_case['tid']), None, actor)
        db.execute(text('DELETE FROM role_assignments WHERE user_id = :u'), {'u': users['referee']})
        with pytest.raises(HTTPException) as error:
            lock_match_context(db, match_case['tid'], match_case['match'], actor, can_submit_result)
        assert error.value.status_code == 403
        db.rollback()


def test_link_validation_requires_same_tournament_approved_locked_players(access, session_factory, match_case):
    _, _, users, teams, _ = access
    with session_factory.begin() as db:
        db.add(Team(name='Gamma', tag='G', game_id=1))
        db.add(Team(name='Delta', tag='D', game_id=2))
    with session_factory() as db:
        all_teams = {t.name: t.team_id for t in db.scalars(select(Team))}
        tournament = db.get(Tournament, match_case['tid'])
        assert ensure_stage_in_tournament(db, match_case['tid'], match_case['stage']).name == 'Group'
        ensure_match_teams(db, tournament, all_teams['Alpha'], all_teams['Beta'])
        for stage in (match_case['other_stage'], 999999):
            with pytest.raises(HTTPException) as error:
                ensure_stage_in_tournament(db, match_case['tid'], stage)
            assert error.value.status_code == 422
        for pair in (('Alpha', 'Alpha'), ('Alpha', 'Gamma'), ('Alpha', 'Delta')):
            with pytest.raises(HTTPException) as error:
                ensure_match_teams(db, tournament, all_teams[pair[0]], all_teams[pair[1]])
            assert error.value.status_code == 422
        db.execute(text('DELETE FROM tournament_rosters WHERE team_id = :t'), {'t': all_teams['Beta']})
        with pytest.raises(HTTPException) as error:
            ensure_match_teams(db, tournament, all_teams['Alpha'], all_teams['Beta'])
        assert 'PLAYER' in error.value.detail
        db.rollback()


def test_lifecycle_rules_table(session_factory, match_case):
    with session_factory() as db:
        tournament, match = db.get(Tournament, match_case['tid']), db.get(Match, match_case['match'])
        assert match_editable(tournament, match) and match_startable(tournament, match)
        assert match_cancellable(tournament, match) and not match_result_open(tournament, match)
        match.status = 'ONGOING'
        assert match_result_open(tournament, match) and not match_editable(tournament, match)
        tournament.status = 'COMPLETED'
        assert not match_result_open(tournament, match) and not match_cancellable(tournament, match)
        tournament.status, match.status = 'UPCOMING', 'PENDING'
        assert match_editable(tournament, match) and not match_startable(tournament, match)
        tournament.roster_locked_at = None
        assert not match_editable(tournament, match)
        match.status = 'COMPLETED'
        assert not match_cancellable(tournament, match)
        db.rollback()


def test_stage_with_matches_still_cannot_be_deleted(session_factory, match_case):
    with session_factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text('DELETE FROM stages WHERE stage_id = :s'), {'s': match_case['stage']})
        db.rollback()
