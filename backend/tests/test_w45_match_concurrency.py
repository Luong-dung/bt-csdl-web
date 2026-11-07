"""W45-07: Match concurrency races on real PostgreSQL connections.

Validates:
- Concurrent match creation vs stage deletion (FK RESTRICT & tournament lock)
- Concurrent match start vs match cancellation (row lock serialization)
- Referee assignment revocation while waiting for tournament lock (rechecks permission -> 403)
- Tournament completion while waiting for tournament lock (rechecks status -> 409)
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event

import pytest
from sqlalchemy import event, select

from core.tournaments import lock_tournament
from modules.identity.models import RoleAssignment
from modules.tournaments.models import Match, Stage, Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import make_client
from test_permissions import access, organizer_tournament
from test_registration_concurrency import session_factory

pytestmark = pytest.mark.postgres


def match_url(tid, match_id=None):
    base = f'/api/v1/tournaments/{tid}/matches'
    return f'{base}/{match_id}' if match_id is not None else base


def stage_url(tid, stage_id=None):
    base = f'/api/v1/tournaments/{tid}/stages'
    return f'{base}/{stage_id}' if stage_id is not None else base


@pytest.fixture
def empty_stage_case(access, session_factory):
    """UPCOMING tournament with locked roster, two approved teams, and an empty stage."""
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    now = datetime.now(timezone.utc)
    with session_factory.begin() as db:
        for name, user in (('Alpha', 'viewer'), ('Beta', 'manager')):
            db.add(TournamentRegistration(tournament_id=tid, team_id=teams[name], status='APPROVED', reviewed_at=now))
            db.add(TournamentRoster(
                tournament_id=tid, team_id=teams[name], user_id=users[user],
                role_in_team='PLAYER', display_name=user
            ))
        tournament = db.get(Tournament, tid)
        tournament.status, tournament.roster_locked_at = 'UPCOMING', now
        stage = Stage(tournament_id=tid, name='Playoffs', sequence_order=1)
        db.add(stage)
        db.flush()
        return {'tid': tid, 'stage': stage.stage_id}


@pytest.fixture
def match_case(access, session_factory):
    """Locked ONGOING tournament with two APPROVED teams that each have a PLAYER snapshot, and one PENDING match."""
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    now = datetime.now(timezone.utc)
    with session_factory.begin() as db:
        for name, user in (('Alpha', 'viewer'), ('Beta', 'manager')):
            db.add(TournamentRegistration(tournament_id=tid, team_id=teams[name], status='APPROVED', reviewed_at=now))
            db.add(TournamentRoster(
                tournament_id=tid, team_id=teams[name], user_id=users[user],
                role_in_team='PLAYER', display_name=user,
            ))
        tournament = db.get(Tournament, tid)
        tournament.status, tournament.roster_locked_at = 'ONGOING', now
        stage = Stage(tournament_id=tid, name='Group', sequence_order=1)
        db.add(stage)
        db.flush()
        match = Match(
            tournament_id=tid,
            stage_id=stage.stage_id,
            round_no=1,
            team1_id=teams['Alpha'],
            team2_id=teams['Beta'],
        )
        db.add(match)
        db.flush()
        return {'tid': tid, 'stage': stage.stage_id, 'match': match.match_id}


def test_concurrent_match_create_and_stage_delete(access, session_factory, empty_stage_case):
    """Race between creating a match in an empty stage and deleting that stage.

    Tournament lock serializes all stage and match writers:
    - If match creation commits first: stage deletion fails with 409 (cannot delete stage with matches / FK RESTRICT).
    - If stage deletion commits first: match creation fails with 422 (stage not in tournament).
    Database integrity is preserved; no match is ever left referencing a deleted stage.
    """
    _, headers, _, teams, _ = access
    tid = empty_stage_case['tid']
    stage_id = empty_stage_case['stage']

    def create_match():
        with make_client(session_factory, logged_in=False) as client:
            return client.post(
                match_url(tid),
                headers=headers('organizer'),
                json={
                    'stage_id': stage_id,
                    'round_no': 1,
                    'team1_id': teams['Alpha'],
                    'team2_id': teams['Beta'],
                },
            ).status_code

    def delete_stage():
        with make_client(session_factory, logged_in=False) as client:
            return client.delete(
                stage_url(tid, stage_id),
                headers=headers('organizer'),
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_create = pool.submit(create_match)
        f_delete = pool.submit(delete_stage)
        create_code = f_create.result(timeout=10)
        delete_code = f_delete.result(timeout=10)

    # Valid outcomes:
    # 1. Match created (201), Stage delete blocked (409)
    # 2. Stage deleted (204), Match create rejected (422)
    assert sorted([create_code, delete_code]) in ([201, 409], [204, 422])

    with session_factory() as db:
        remaining_stage = db.get(Stage, stage_id)
        matches_in_stage = list(db.scalars(select(Match).where(Match.stage_id == stage_id)))
        if remaining_stage is None:
            assert len(matches_in_stage) == 0
        else:
            assert len(matches_in_stage) == 1


def test_concurrent_match_start_and_cancel(access, session_factory, match_case):
    """Race between starting a match (ONGOING) and cancelling a match (CANCELLED).

    Row locks on the match ensure orderly state transitions:
    - If Start runs first -> 200 (ONGOING). Cancel runs second -> 200 (CANCELLED).
    - If Cancel runs first -> 200 (CANCELLED). Start runs second -> 409 (CANNOT start CANCELLED match).
    Final match state in DB must be CANCELLED and never corrupt.
    """
    _, headers, _, _, _ = access
    tid = match_case['tid']
    mid = match_case['match']

    def start_match():
        with make_client(session_factory, logged_in=False) as client:
            return client.post(
                f"{match_url(tid, mid)}/status",
                headers=headers('organizer'),
                json={'status': 'ONGOING'},
            ).status_code

    def cancel_match():
        with make_client(session_factory, logged_in=False) as client:
            return client.post(
                f"{match_url(tid, mid)}/status",
                headers=headers('organizer'),
                json={'status': 'CANCELLED'},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_start = pool.submit(start_match)
        f_cancel = pool.submit(cancel_match)
        start_code = f_start.result(timeout=10)
        cancel_code = f_cancel.result(timeout=10)

    assert sorted([start_code, cancel_code]) in ([200, 200], [200, 409])
    with session_factory() as db:
        final_match = db.get(Match, mid)
        assert final_match.status == 'CANCELLED'


def test_start_rechecks_referee_revocation_under_lock(access, session_factory, match_case):
    """When a referee requests start match while waiting on tournament lock,

    and the referee's role assignment is revoked by the lock holder,
    the start request must reload actor permissions and return 403.
    """
    _, headers, users, _, roles = access
    tid = match_case['tid']
    mid = match_case['match']

    with session_factory.begin() as db:
        assignment = RoleAssignment(
            user_id=users['referee'],
            role_id=roles['REFEREE'],
            scope_type='TOURNAMENT',
            scope_id=tid,
        )
        db.add(assignment)
        db.flush()
        aid = assignment.assignment_id

    engine = session_factory.kw['bind']
    waiting = Event()

    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()

    with session_factory() as holder:
        lock_tournament(holder, tid)
        event.listen(engine, 'before_cursor_execute', notice)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                def submit_start():
                    with make_client(session_factory, logged_in=False) as client:
                        return client.post(
                            f"{match_url(tid, mid)}/status",
                            headers=headers('referee'),
                            json={'status': 'ONGOING'},
                        ).status_code

                future = pool.submit(submit_start)
                try:
                    assert waiting.wait(5), "start request never queued on tournament lock"
                    assert not future.done()
                    holder.delete(holder.get(RoleAssignment, aid))
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == 403
        finally:
            event.remove(engine, 'before_cursor_execute', notice)

    with session_factory() as db:
        match = db.get(Match, mid)
        assert match.status == 'PENDING'


def test_start_rechecks_tournament_completion_under_lock(access, session_factory, match_case):
    """When a start match request is waiting on tournament lock,

    and the tournament is ended (COMPLETED) by the lock holder,
    the start request must recheck tournament status and return 409.
    """
    _, headers, _, _, _ = access
    tid = match_case['tid']
    mid = match_case['match']

    engine = session_factory.kw['bind']
    waiting = Event()

    def notice(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()

    with session_factory() as holder:
        tourn = lock_tournament(holder, tid)
        event.listen(engine, 'before_cursor_execute', notice)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                def submit_start():
                    with make_client(session_factory, logged_in=False) as client:
                        return client.post(
                            f"{match_url(tid, mid)}/status",
                            headers=headers('organizer'),
                            json={'status': 'ONGOING'},
                        ).status_code

                future = pool.submit(submit_start)
                try:
                    assert waiting.wait(5), "start request never queued on tournament lock"
                    assert not future.done()
                    tourn.status = 'COMPLETED'
                    holder.commit()
                finally:
                    holder.rollback()
                assert future.result(timeout=5) == 409
        finally:
            event.remove(engine, 'before_cursor_execute', notice)

    with session_factory() as db:
        match = db.get(Match, mid)
        assert match.status == 'PENDING'
