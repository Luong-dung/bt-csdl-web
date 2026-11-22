"""W46-07: Bracket concurrency races through real HTTP and independent PostgreSQL connections.

Validates:
- Concurrent bracket creation race (idempotent serialization, single audit)
- Two concurrent semifinal results filling both final slots (slot 1 and slot 2)
- Concurrent result replay vs conflicting result submission
- Race between final result submission and tournament completion (COMPLETED)
- Race between semifinal result submission and tournament cancellation (CANCELLED)
- Referee permission revocation while waiting for tournament lock (rechecks permission -> 403)
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import delete, event, select

from core.tournaments import lock_tournament
from modules.identity.models import AuditLog, RoleAssignment
from modules.tournaments.models import Match, Tournament, TournamentBracket
from test_bracket_create import add_teams, preview
from test_bracket_foundation import bracket_case
from test_catalog_api import make_client
from test_match_foundation import match_case
from test_permissions import access
from test_registration_concurrency import session_factory
from referee_helpers import grant_referee

pytestmark = pytest.mark.postgres


@pytest.fixture
def four_concurrency_case(access, session_factory, bracket_case):
    """Tournament with 4 teams, empty stage, ready for bracket operations."""
    _, _, _, teams, roles = access
    order = [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, 4)]
    with session_factory.begin() as db:
        db.get(Match, bracket_case['match']).status = 'CANCELLED'
    return bracket_case | {'order': order}


def post_create(factory, headers, ids, token, order):
    with make_client(factory, logged_in=False) as client:
        response = client.post(
            f"/api/v1/tournaments/{ids['tid']}/bracket",
            headers=headers('organizer'),
            json={'stage_id': ids['empty_stage'], 'team_ids': order, 'preview_token': token},
        )
        return response.status_code, response.json()


def submit_result(factory, headers, tid, mid, scores, role='organizer'):
    with make_client(factory, logged_in=False) as client:
        return client.put(
            f"/api/v1/tournaments/{tid}/matches/{mid}/result",
            headers=headers(role),
            json={'score_team1': scores[0], 'score_team2': scores[1]},
        ).status_code


def change_status(factory, headers, tid, status, role='organizer'):
    with make_client(factory, logged_in=False) as client:
        return client.post(
            f"/api/v1/tournaments/{tid}/status",
            headers=headers(role),
            json={'status': status},
        ).status_code


# ==============================================================================
# Race 1: Concurrent Bracket Creation
# ==============================================================================

@pytest.mark.parametrize('same_input', [True, False])
def test_concurrent_bracket_create_race(access, session_factory, four_concurrency_case, same_input):
    """Two concurrent create requests:
    - Same input: one thread gets 201 (created), the other gets 200 (idempotent replay).
      Exactly 1 bracket, 3 matches, 1 BRACKET_CREATED audit log.
    - Different input: one thread gets 201, the other gets 409 (conflict).
    """
    client, headers, _, _, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']
    other_order = order[::-1]

    token_same = preview(client, headers, four_concurrency_case).json()['preview_token']
    token_other = preview(client, headers, four_concurrency_case, order=other_order).json()['preview_token']

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(post_create, session_factory, headers, four_concurrency_case, token_same, order)
        f2 = pool.submit(
            post_create,
            session_factory,
            headers,
            four_concurrency_case,
            token_same if same_input else token_other,
            order if same_input else other_order,
        )
        res1 = f1.result(timeout=15)
        res2 = f2.result(timeout=15)

    codes = sorted([res1[0], res2[0]])
    assert codes == ([200, 201] if same_input else [201, 409])

    with session_factory() as db:
        brackets = list(db.scalars(select(TournamentBracket).where(TournamentBracket.tournament_id == tid)))
        assert len(brackets) == 1
        matches = list(db.scalars(select(Match).where(Match.tournament_id == tid, Match.stage_id == four_concurrency_case['empty_stage'])))
        assert len(matches) == 3
        audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'bracket', AuditLog.action == 'BRACKET_CREATED')))
        assert len(audits) == 1


# ==============================================================================
# Race 2: Two Concurrent Semifinals Filling Both Final Slots
# ==============================================================================

def test_two_concurrent_semifinals_fill_both_final_slots(access, session_factory, four_concurrency_case):
    """Two semifinal matches running in parallel submit results simultaneously:
    - Semifinal 1 fills slot 1 of Final.
    - Semifinal 2 fills slot 2 of Final.
    - Both transactions succeed (200, 200).
    - Final match has both team1 and team2 populated cleanly.
    - Exactly 2 MATCH_RESULT_SUBMITTED audit logs with slot 1 and slot 2.
    """
    client, headers, _, teams, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']

    token = preview(client, headers, four_concurrency_case).json()['preview_token']
    created = client.post(
        f"/api/v1/tournaments/{tid}/bracket",
        headers=headers('organizer'),
        json={'stage_id': four_concurrency_case['empty_stage'], 'team_ids': order, 'preview_token': token},
    ).json()

    # Transition tournament to ONGOING
    assert change_status(session_factory, headers, tid, 'ONGOING') == 200

    semi1_id = created['matches'][0]['match']['match_id']
    semi2_id = created['matches'][1]['match']['match_id']
    final_id = created['matches'][2]['match']['match_id']

    # Start both semifinals
    with make_client(session_factory, logged_in=False) as c:
        assert c.post(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
        assert c.post(f"/api/v1/tournaments/{tid}/matches/{semi2_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(submit_result, session_factory, headers, tid, semi1_id, (2, 0))
        f2 = pool.submit(submit_result, session_factory, headers, tid, semi2_id, (0, 2))
        res1 = f1.result(timeout=15)
        res2 = f2.result(timeout=15)

    assert [res1, res2] == [200, 200]

    with session_factory() as db:
        final_m = db.get(Match, final_id)
        assert final_m.status == 'PENDING'
        assert final_m.team1_id == order[0]  # Alpha won semi 1
        assert final_m.team2_id == order[3]  # Delta won semi 2

        logs = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match', AuditLog.action == 'MATCH_RESULT_SUBMITTED')))
        assert len(logs) == 2
        slots = {l.details['advancement']['slot'] for l in logs}
        assert slots == {1, 2}

    # Verify integration with W46-04 derived standings:
    with make_client(session_factory, logged_in=False) as c:
        std = c.get(f"/api/v1/tournaments/{tid}/bracket/standings").json()
        assert std['status'] == 'PROVISIONAL'
        items = {i['team']['team_id']: i for i in std['items']}
        # Losers: Beta (order[1]) and Gamma (order[2]) -> tied for rank 3
        assert items[order[1]]['rank'] == 3
        assert items[order[1]]['matches_played'] == 1 and items[order[1]]['losses'] == 1 and items[order[1]]['wins'] == 0
        assert items[order[2]]['rank'] == 3
        assert items[order[2]]['matches_played'] == 1 and items[order[2]]['losses'] == 1 and items[order[2]]['wins'] == 0
        # Winners: Alpha (order[0]) and Delta (order[3]) -> still alive, rank is None, wins=1
        assert items[order[0]]['rank'] is None
        assert items[order[0]]['matches_played'] == 1 and items[order[0]]['wins'] == 1 and items[order[0]]['losses'] == 0
        assert items[order[3]]['rank'] is None
        assert items[order[3]]['matches_played'] == 1 and items[order[3]]['wins'] == 1 and items[order[3]]['losses'] == 0


# ==============================================================================
# Race 3: Concurrent Result Replay vs Conflicting Result
# ==============================================================================

@pytest.mark.parametrize('same_score', [True, False])
def test_concurrent_result_replay_vs_conflicting_result(access, session_factory, four_concurrency_case, same_score):
    """Two concurrent result submissions on the same match:
    - Thread 1 sends (2, 0).
    - Thread 2 sends (2, 0) [same] or (0, 2) [conflicting].
    - Same score: [200, 200], exactly 1 audit log.
    - Conflicting score: [200, 409], exactly 1 audit log.
    """
    client, headers, _, _, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']

    token = preview(client, headers, four_concurrency_case).json()['preview_token']
    created = client.post(
        f"/api/v1/tournaments/{tid}/bracket",
        headers=headers('organizer'),
        json={'stage_id': four_concurrency_case['empty_stage'], 'team_ids': order, 'preview_token': token},
    ).json()

    assert change_status(session_factory, headers, tid, 'ONGOING') == 200
    semi1_id = created['matches'][0]['match']['match_id']

    with make_client(session_factory, logged_in=False) as c:
        assert c.post(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(submit_result, session_factory, headers, tid, semi1_id, (2, 0))
        f2 = pool.submit(submit_result, session_factory, headers, tid, semi1_id, (2, 0) if same_score else (0, 2))
        res1 = f1.result(timeout=15)
        res2 = f2.result(timeout=15)

    codes = sorted([res1, res2])
    assert codes == ([200, 200] if same_score else [200, 409])

    with session_factory() as db:
        m = db.get(Match, semi1_id)
        assert m.status == 'COMPLETED'
        if same_score:
            assert m.winner_id == order[0]
        else:
            assert m.winner_id in (order[0], order[1])
        final_id = created['matches'][2]['match']['match_id']
        assert db.get(Match, final_id).team1_id == m.winner_id
        logs = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match', AuditLog.action == 'MATCH_RESULT_SUBMITTED')))
        assert len(logs) == 1

    # Verify standings: concurrent replay (same_score=True) never doubles stats
    with make_client(session_factory, logged_in=False) as c:
        std = c.get(f"/api/v1/tournaments/{tid}/bracket/standings").json()
        items = {i['team']['team_id']: i for i in std['items']}
        if same_score:
            assert items[order[0]]['matches_played'] == 1
            assert items[order[0]]['wins'] == 1
            assert items[order[0]]['losses'] == 0
            assert items[order[0]]['rank'] is None
            assert items[order[1]]['matches_played'] == 1
            assert items[order[1]]['wins'] == 0
            assert items[order[1]]['losses'] == 1
            assert items[order[1]]['rank'] == 3
        else:
            winner_id = order[0] if m.winner_id == order[0] else order[1]
            loser_id = order[1] if m.winner_id == order[0] else order[0]
            assert items[winner_id]['matches_played'] == 1 and items[winner_id]['wins'] == 1
            assert items[loser_id]['matches_played'] == 1 and items[loser_id]['losses'] == 1 and items[loser_id]['rank'] == 3


# ==============================================================================
# Race 4: Final Result vs Tournament Completion (COMPLETED)
# ==============================================================================

def test_concurrent_final_result_vs_tournament_completion(access, session_factory, four_concurrency_case):
    """Race between submitting the Final result and closing the tournament:
    - If Final commits first -> tournament completion succeeds (200).
    - If tournament completion executes first -> rejected with 409 because Final is not COMPLETED.
    """
    client, headers, _, _, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']

    token = preview(client, headers, four_concurrency_case).json()['preview_token']
    created = client.post(
        f"/api/v1/tournaments/{tid}/bracket",
        headers=headers('organizer'),
        json={'stage_id': four_concurrency_case['empty_stage'], 'team_ids': order, 'preview_token': token},
    ).json()

    assert change_status(session_factory, headers, tid, 'ONGOING') == 200
    semi1_id = created['matches'][0]['match']['match_id']
    semi2_id = created['matches'][1]['match']['match_id']
    final_id = created['matches'][2]['match']['match_id']

    # Complete both semifinals
    with make_client(session_factory, logged_in=False) as c:
        c.post(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'})
        c.put(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/result", headers=headers('organizer'), json={'score_team1': 2, 'score_team2': 0})
        c.post(f"/api/v1/tournaments/{tid}/matches/{semi2_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'})
        c.put(f"/api/v1/tournaments/{tid}/matches/{semi2_id}/result", headers=headers('organizer'), json={'score_team1': 0, 'score_team2': 2})
        # Start Final
        assert c.post(f"/api/v1/tournaments/{tid}/matches/{final_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_score = pool.submit(submit_result, session_factory, headers, tid, final_id, (3, 1))
        f_close = pool.submit(change_status, session_factory, headers, tid, 'COMPLETED')
        score_code = f_score.result(timeout=15)
        close_code = f_close.result(timeout=15)

    assert score_code == 200
    assert close_code in (200, 409)

    with session_factory() as db:
        final_m = db.get(Match, final_id)
        assert final_m.status == 'COMPLETED'
        tourn = db.get(Tournament, tid)
        assert tourn.status == ('COMPLETED' if close_code == 200 else 'ONGOING')

        result_audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match', AuditLog.action == 'MATCH_RESULT_SUBMITTED')))
        assert len(result_audits) == 3

        status_audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament', AuditLog.action == 'TOURNAMENT_STATUS_CHANGED')))
        completed_audits = [a for a in status_audits if (a.details.get('after') or {}).get('status') == 'COMPLETED' or a.details.get('status') == 'COMPLETED']
        assert len(completed_audits) == (1 if close_code == 200 else 0)


# ==============================================================================
# Race 5: Semifinal Result vs Tournament Cancellation (CANCELLED)
# ==============================================================================

def test_concurrent_semifinal_result_vs_tournament_cancellation(access, session_factory, four_concurrency_case):
    """Race between submitting a semifinal result and cancelling the tournament:
    - If cancellation commits first -> tournament is CANCELLED, result returns 409.
    - If result commits first -> semifinal is COMPLETED, then tournament cancels cleanly.
    """
    client, headers, _, _, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']

    token = preview(client, headers, four_concurrency_case).json()['preview_token']
    created = client.post(
        f"/api/v1/tournaments/{tid}/bracket",
        headers=headers('organizer'),
        json={'stage_id': four_concurrency_case['empty_stage'], 'team_ids': order, 'preview_token': token},
    ).json()

    assert change_status(session_factory, headers, tid, 'ONGOING') == 200
    semi1_id = created['matches'][0]['match']['match_id']
    final_id = created['matches'][2]['match']['match_id']

    with make_client(session_factory, logged_in=False) as c:
        c.post(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'})

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_cancel = pool.submit(change_status, session_factory, headers, tid, 'CANCELLED')
        f_score = pool.submit(submit_result, session_factory, headers, tid, semi1_id, (2, 0))
        cancel_code = f_cancel.result(timeout=15)
        score_code = f_score.result(timeout=15)

    assert cancel_code == 200
    assert score_code in (200, 409)

    with session_factory() as db:
        assert db.get(Tournament, tid).status == 'CANCELLED'
        semi1_m = db.get(Match, semi1_id)
        assert semi1_m.status == ('COMPLETED' if score_code == 200 else 'ONGOING')
        assert db.get(Match, final_id).team1_id == (order[0] if score_code == 200 else None)

        result_audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match', AuditLog.action == 'MATCH_RESULT_SUBMITTED')))
        assert len(result_audits) == (1 if score_code == 200 else 0)

        cancel_audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'tournament', AuditLog.action == 'TOURNAMENT_STATUS_CHANGED')))
        assert any((a.details.get('after') or {}).get('status') == 'CANCELLED' or a.details.get('status') == 'CANCELLED' for a in cancel_audits)

    with make_client(session_factory, logged_in=False) as c:
        std = c.get(f"/api/v1/tournaments/{tid}/bracket/standings").json()
        assert std['status'] == 'CANCELLED'
        items = {i['team']['team_id']: i for i in std['items']}
        if score_code == 200:
            assert items[order[1]]['rank'] == 3  # Loser of semi 1 (Beta) keeps historical rank 3
            assert items[order[0]]['rank'] is None
            assert items[order[2]]['rank'] is None
            assert items[order[3]]['rank'] is None
        else:
            for tid_i in order:
                assert items[tid_i]['rank'] is None


# ==============================================================================
# Race 6: Referee Revocation while Waiting for Tournament Lock
# ==============================================================================

def test_referee_revocation_under_tournament_lock(access, session_factory, four_concurrency_case):
    """When a referee requests result submission while waiting on tournament lock,
    and their role assignment is revoked by the lock holder,
    the request must reload actor permissions and return 403.
    """
    client, headers, users, _, _ = access
    tid = four_concurrency_case['tid']
    order = four_concurrency_case['order']

    token = preview(client, headers, four_concurrency_case).json()['preview_token']
    created = client.post(
        f"/api/v1/tournaments/{tid}/bracket",
        headers=headers('organizer'),
        json={'stage_id': four_concurrency_case['empty_stage'], 'team_ids': order, 'preview_token': token},
    ).json()

    assert change_status(session_factory, headers, tid, 'ONGOING') == 200
    semi1_id = created['matches'][0]['match']['match_id']
    final_id = created['matches'][2]['match']['match_id']

    with make_client(session_factory, logged_in=False) as c:
        c.post(f"/api/v1/tournaments/{tid}/matches/{semi1_id}/status", headers=headers('organizer'), json={'status': 'ONGOING'})

    assignment = grant_referee(client, headers, tid, users['referee'])
    assert assignment.status_code == 201, assignment.text
    aid = assignment.json()['assignment_id']

    engine = session_factory.kw['bind']
    waiting = Event()

    def notice_lock(connection, cursor, statement, parameters, context, executemany):
        if 'FROM tournaments' in statement and 'FOR UPDATE' in statement:
            waiting.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with session_factory.begin() as holder:
                lock_tournament(holder, tid)
                holder.execute(delete(RoleAssignment).where(RoleAssignment.assignment_id == aid))
                event.listen(engine, 'before_cursor_execute', notice_lock)
                future = pool.submit(submit_result, session_factory, headers, tid, semi1_id, (2, 0), 'referee')
                assert waiting.wait(5), "Referee request never queued on tournament lock"
            # Lock released on block exit
            assert future.result(timeout=10) == 403
        finally:
            event.remove(engine, 'before_cursor_execute', notice_lock)

    # State unchanged: match still ONGOING, final slot 1 still None, zero result audits
    with session_factory() as db:
        assert db.get(Match, semi1_id).status == 'ONGOING'
        assert db.get(Match, final_id).team1_id is None
        audits = list(db.scalars(select(AuditLog).where(AuditLog.resource == 'match', AuditLog.action == 'MATCH_RESULT_SUBMITTED')))
        assert len(audits) == 0
