"""W45-07: Match integration, large dataset pagination/filtering, full lifecycle audit chain,
and permission/link validations.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.identity.models import AuditLog, RoleAssignment
from modules.teams.models import Team, TeamMembership
from modules.tournaments.models import Match, Stage, Tournament, TournamentRegistration, TournamentRoster
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access, organizer_tournament

pytestmark = pytest.mark.postgres


def match_url(tid, match_id=None):
    base = f'/api/v1/tournaments/{tid}/matches'
    return f'{base}/{match_id}' if match_id is not None else base


def stage_url(tid, stage_id=None):
    base = f'/api/v1/tournaments/{tid}/stages'
    return f'{base}/{stage_id}' if stage_id is not None else base


def match_audit_logs(factory, tid=None, match_id=None):
    with factory() as db:
        query = select(AuditLog).where(AuditLog.resource == 'match').order_by(AuditLog.log_id)
        logs = list(db.scalars(query))
        if tid is not None:
            logs = [l for l in logs if l.details.get('tournament_id') == tid]
        if match_id is not None:
            logs = [l for l in logs if l.details.get('match_id') == match_id]
        return logs


# ==============================================================================
# Part 1: Large Match Dataset (>50 matches) Pagination, Filters, and Stable Order
# ==============================================================================

def test_large_match_dataset_pagination_filters_and_ordering(access, session_factory):
    """Creates a tournament with 55 matches across 2 stages and 4 teams.

    Validates:
    - Page 1 (offset=0, limit=50) -> 50 matches, X-Total-Count: 55
    - Page 2 (offset=50, limit=50) -> 5 matches, X-Total-Count: 55
    - No gaps or duplicates across pages (disjoint set union == all 55 match IDs)
    - Stable sorting by (stages.sequence_order, round_no, match_id)
    - Filtering by stage_id, team_id, and status
    - Public DTO compliance: no emails/drafts leaked; result is None unless COMPLETED
    """
    client, headers, users, teams, roles = access
    tid = organizer_tournament(client, headers)
    now = datetime.now(timezone.utc)
    total_matches = 55

    with session_factory.begin() as db:
        t_gamma = Team(name="Gamma Squad", tag="GMA", game_id=1)
        t_delta = Team(name="Delta Force", tag="DLT", game_id=1)
        db.add_all([t_gamma, t_delta])
        db.flush()
        all_teams = [teams['Alpha'], teams['Beta'], t_gamma.team_id, t_delta.team_id]
        roster_users = [users[name] for name in ('viewer', 'manager', 'referee', 'admin')]

        for idx, team_id in enumerate(all_teams):
            db.add(TournamentRegistration(tournament_id=tid, team_id=team_id, status='APPROVED', reviewed_at=now))
            db.add(TournamentRoster(
                tournament_id=tid, team_id=team_id, user_id=roster_users[idx],
                role_in_team='PLAYER', display_name=f'player_{idx}'
            ))

        tournament = db.get(Tournament, tid)
        tournament.status, tournament.roster_locked_at = 'ONGOING', now

        stage1 = Stage(tournament_id=tid, name='Stage 1 Group', sequence_order=1)
        stage2 = Stage(tournament_id=tid, name='Stage 2 Playoffs', sequence_order=2)
        db.add_all([stage1, stage2])
        db.flush()
        s1_id, s2_id = stage1.stage_id, stage2.stage_id

        inserted_matches = []
        for i in range(1, total_matches + 1):
            s_id = s1_id if i <= 30 else s2_id
            round_no = (i % 5) + 1
            t1 = all_teams[(i - 1) % 4]
            t2 = all_teams[i % 4]
            if t1 == t2:
                t2 = all_teams[(i + 1) % 4]

            if i <= 25:
                status, s1_score, s2_score, winner = 'PENDING', 0, 0, None
            elif i <= 40:
                status, s1_score, s2_score, winner = 'ONGOING', 0, 0, None
            elif i <= 50:
                status, s1_score, s2_score, winner = 'COMPLETED', 2, 1, t1
            else:
                status, s1_score, s2_score, winner = 'CANCELLED', 0, 0, None

            match = Match(
                tournament_id=tid,
                stage_id=s_id,
                round_no=round_no,
                team1_id=t1,
                team2_id=t2,
                status=status,
                score_team1=s1_score,
                score_team2=s2_score,
                winner_id=winner,
                scheduled_at=now + timedelta(days=i),
            )
            db.add(match)
            inserted_matches.append(match)
        db.flush()
        expected_all_ids = {m.match_id for m in inserted_matches}
        stage1_expected_ids = {m.match_id for m in inserted_matches if m.stage_id == s1_id}
        completed_expected_ids = {m.match_id for m in inserted_matches if m.status == 'COMPLETED'}
        alpha_expected_ids = {m.match_id for m in inserted_matches if teams['Alpha'] in (m.team1_id, m.team2_id)}

    # 1. Pagination verification
    page1_res = client.get(match_url(tid), params={'offset': 0, 'limit': 50})
    assert page1_res.status_code == 200
    assert page1_res.headers['x-total-count'] == str(total_matches)
    page1_data = page1_res.json()
    assert len(page1_data) == 50

    page2_res = client.get(match_url(tid), params={'offset': 50, 'limit': 50})
    assert page2_res.status_code == 200
    assert page2_res.headers['x-total-count'] == str(total_matches)
    page2_data = page2_res.json()
    assert len(page2_data) == total_matches - 50

    page3_res = client.get(match_url(tid), params={'offset': 100, 'limit': 50})
    assert page3_res.status_code == 200
    assert page3_res.headers['x-total-count'] == str(total_matches)
    assert len(page3_res.json()) == 0

    p1_ids = {m['match_id'] for m in page1_data}
    p2_ids = {m['match_id'] for m in page2_data}
    assert len(p1_ids & p2_ids) == 0, "Duplicate matches found across pagination pages"
    assert (p1_ids | p2_ids) == expected_all_ids, "Missing matches across pagination pages"

    # 2. Stable sorting verification: (stages.sequence_order, round_no, match_id)
    combined_matches = page1_data + page2_data
    stage_orders = {s1_id: 1, s2_id: 2}
    sort_keys = [
        (stage_orders[m['stage_id']], m['round_no'], m['match_id'])
        for m in combined_matches
    ]
    assert sort_keys == sorted(sort_keys), "Matches are not stably ordered by (stage.sequence_order, round_no, match_id)"

    # 3. Filter verification
    f_stage_res = client.get(match_url(tid), params={'stage_id': s1_id, 'limit': 100})
    assert f_stage_res.status_code == 200
    assert f_stage_res.headers['x-total-count'] == str(len(stage1_expected_ids))
    assert {m['match_id'] for m in f_stage_res.json()} == stage1_expected_ids

    f_team_res = client.get(match_url(tid), params={'team_id': teams['Alpha'], 'limit': 100})
    assert f_team_res.status_code == 200
    assert f_team_res.headers['x-total-count'] == str(len(alpha_expected_ids))
    assert {m['match_id'] for m in f_team_res.json()} == alpha_expected_ids

    f_status_res = client.get(match_url(tid), params={'status': 'COMPLETED', 'limit': 100})
    assert f_status_res.status_code == 200
    assert f_status_res.headers['x-total-count'] == str(len(completed_expected_ids))
    assert {m['match_id'] for m in f_status_res.json()} == completed_expected_ids

    # 4. Public DTO data safety
    for m in combined_matches:
        assert set(m.keys()) == {
            'match_id', 'tournament_id', 'stage_id', 'stage_name', 'round_no',
            'team1', 'team2', 'scheduled_at', 'status', 'result',
        }
        assert 'email' not in str(m)
        assert 'roster' not in str(m)
        if m['status'] == 'COMPLETED':
            assert m['result'] is not None
            assert m['result']['score_team1'] >= 0
            assert m['result']['score_team2'] >= 0
            assert m['result']['winner_id'] in (m['team1']['team_id'], m['team2']['team_id'])
        else:
            assert m['result'] is None


# ==============================================================================
# Part 2: Full Match Lifecycle Integration, Audit Chain & Idempotency
# ==============================================================================

def test_full_match_lifecycle_audit_chain_and_idempotency(access, session_factory, match_case):
    """Covers the complete sequential match lifecycle:

    POST create -> PATCH update -> POST start -> PUT result -> idempotent replay & conflicts.
    Verifies that the audit log maintains an exact, intact chain with before/after state.
    """
    client, headers, users, teams, roles = access
    tid = match_case['tid']
    stage_id = match_case['stage']
    organizer_auth = headers('organizer')
    admin_auth = headers('admin')

    # Step 1: Create Match (PENDING)
    create_kickoff = "2026-11-20T19:00:00+07:00"
    create_res = client.post(
        match_url(tid),
        headers=organizer_auth,
        json={
            'stage_id': stage_id,
            'round_no': 1,
            'team1_id': teams['Alpha'],
            'team2_id': teams['Beta'],
            'scheduled_at': create_kickoff,
        },
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    mid = created['match_id']
    assert created['status'] == 'PENDING'
    assert datetime.fromisoformat(created['scheduled_at'].replace('Z', '+00:00')) == datetime(
        2026, 11, 20, 12, 0, tzinfo=timezone.utc
    )
    assert created['result'] is None

    # Step 2: Update Match Schedule & Round (PATCH)
    update_kickoff = "2026-11-21T20:30:00+07:00"
    update_res = client.patch(
        match_url(tid, mid),
        headers=organizer_auth,
        json={
            'round_no': 2,
            'scheduled_at': update_kickoff,
        },
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()
    assert updated['round_no'] == 2
    assert datetime.fromisoformat(updated['scheduled_at'].replace('Z', '+00:00')) == datetime(
        2026, 11, 21, 13, 30, tzinfo=timezone.utc
    )

    # Step 3: Start Match (ONGOING)
    start_res = client.post(
        f"{match_url(tid, mid)}/status",
        headers=organizer_auth,
        json={'status': 'ONGOING'},
    )
    assert start_res.status_code == 200, start_res.text
    started = start_res.json()
    assert started['status'] == 'ONGOING'

    # Replay start on already ONGOING match is idempotent (200, no extra audit)
    replay_start = client.post(
        f"{match_url(tid, mid)}/status",
        headers=organizer_auth,
        json={'status': 'ONGOING'},
    )
    assert replay_start.status_code == 200

    # Step 4: Submit Result (COMPLETED)
    result_res = client.put(
        f"{match_url(tid, mid)}/result",
        headers=organizer_auth,
        json={'score_team1': 3, 'score_team2': 1},
    )
    assert result_res.status_code == 200, result_res.text
    completed = result_res.json()
    assert completed['status'] == 'COMPLETED'
    assert completed['result'] == {
        'score_team1': 3,
        'score_team2': 1,
        'winner_id': teams['Alpha'],
    }

    # Step 5: Verify Audit Log Chain
    logs = match_audit_logs(session_factory, tid=tid, match_id=mid)
    actions = [l.action for l in logs]
    assert actions == [
        'MATCH_CREATED',
        'MATCH_UPDATED',
        'MATCH_STARTED',
        'MATCH_RESULT_SUBMITTED',
    ], f"Unexpected audit sequence: {actions}"

    assert logs[0].details['before'] is None
    assert logs[0].details['after']['status'] == 'PENDING'
    assert logs[1].details['before']['round_no'] == 1
    assert logs[1].details['after']['round_no'] == 2
    assert logs[2].details['before']['status'] == 'PENDING'
    assert logs[2].details['after']['status'] == 'ONGOING'
    assert logs[3].details['before']['status'] == 'ONGOING'
    assert logs[3].details['after']['status'] == 'COMPLETED'
    assert logs[3].details['after']['winner_id'] == teams['Alpha']

    # Step 6: Idempotent replay of identical result -> 200 without duplicate audit
    replay_res = client.put(
        f"{match_url(tid, mid)}/result",
        headers=admin_auth,
        json={'score_team1': 3, 'score_team2': 1},
    )
    assert replay_res.status_code == 200
    assert len(match_audit_logs(session_factory, tid=tid, match_id=mid)) == 4

    # Step 7: Different result on COMPLETED match -> 409 conflict
    conflict_res = client.put(
        f"{match_url(tid, mid)}/result",
        headers=admin_auth,
        json={'score_team1': 1, 'score_team2': 3},
    )
    assert conflict_res.status_code == 409
    assert len(match_audit_logs(session_factory, tid=tid, match_id=mid)) == 4

    # Step 8: Immutability of COMPLETED match
    assert client.patch(match_url(tid, mid), headers=organizer_auth, json={'round_no': 5}).status_code == 409
    assert client.delete(match_url(tid, mid), headers=organizer_auth).status_code == 409
    assert client.post(f"{match_url(tid, mid)}/status", headers=organizer_auth, json={'status': 'CANCELLED'}).status_code == 409
    assert client.delete(stage_url(tid, stage_id), headers=organizer_auth).status_code == 409


def test_audit_failure_fault_injection_rollback_on_all_match_writes(access, session_factory, match_case, monkeypatch):
    """Fault injection: when record_audit raises an exception during write operations,

    the entire transaction is rolled back and no partial match state persists.
    """
    client, headers, _, teams, _ = access
    tid = match_case['tid']
    mid = match_case['match']
    auth = headers('organizer')

    def broken_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit storage outage")

    monkeypatch.setattr('routes.matches.record_audit', broken_audit)
    monkeypatch.setattr('routes.match_results.record_audit', broken_audit)

    # 1. Fault injection on match creation
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.post(
            match_url(tid),
            headers=auth,
            json={
                'stage_id': match_case['stage'],
                'round_no': 99,
                'team1_id': teams['Alpha'],
                'team2_id': teams['Beta'],
            },
        )
    with session_factory() as db:
        assert db.scalar(select(Match).where(Match.tournament_id == tid, Match.round_no == 99)) is None

    # 2. Fault injection on match update
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.patch(
            match_url(tid, mid),
            headers=auth,
            json={'round_no': 88},
        )
    with session_factory() as db:
        m = db.get(Match, mid)
        assert m.round_no == 1

    # 3. Fault injection on match start
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.post(
            f"{match_url(tid, mid)}/status",
            headers=auth,
            json={'status': 'ONGOING'},
        )
    with session_factory() as db:
        m = db.get(Match, mid)
        assert m.status == 'PENDING'

    # 4. Fault injection on match cancel
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.post(
            f"{match_url(tid, mid)}/status",
            headers=auth,
            json={'status': 'CANCELLED'},
        )
    with session_factory() as db:
        m = db.get(Match, mid)
        assert m.status == 'PENDING'

    # 5. Fault injection on match delete
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.delete(match_url(tid, mid), headers=auth)
    with session_factory() as db:
        m = db.get(Match, mid)
        assert m is not None and m.match_id == mid


# ==============================================================================
# Part 3: Comprehensive Permission Matrix and Scoped Referee Enforcement
# ==============================================================================

def test_comprehensive_match_permission_matrix(access, session_factory, match_case):
    """Verifies all authorization roles and scopes across all match endpoints."""
    client, headers, users, teams, roles = access
    tid = match_case['tid']
    other_tid = match_case['other']
    mid = match_case['match']

    # 1. Quản lý giải (ADMIN and ORGANIZER creator) have full access
    for role_name in ('admin', 'organizer'):
        auth = headers(role_name)
        caps = client.get(f"{match_url(tid, mid)}/capabilities", headers=auth).json()
        assert caps['can_update'] is True
        assert caps['can_delete'] is True
        assert caps['can_start'] is True
        assert caps['can_cancel'] is True
        assert caps['can_submit_result'] is False  # match is PENDING

    # 2. Grant REFEREE assignment scoped to THIS tournament
    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users['referee'],
            role_id=roles['REFEREE'],
            scope_type='TOURNAMENT',
            scope_id=tid,
        ))

    ref_auth = headers('referee')
    ref_caps = client.get(f"{match_url(tid, mid)}/capabilities", headers=ref_auth).json()
    assert ref_caps['can_start'] is True
    assert ref_caps['can_submit_result'] is False  # PENDING
    assert ref_caps['can_update'] is False
    assert ref_caps['can_delete'] is False
    assert ref_caps['can_cancel'] is False

    # Referee cannot create/edit/delete/cancel match
    assert client.post(
        match_url(tid),
        headers=ref_auth,
        json={'stage_id': match_case['stage'], 'round_no': 2, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta']},
    ).status_code == 403
    assert client.patch(match_url(tid, mid), headers=ref_auth, json={'round_no': 2}).status_code == 403
    assert client.delete(match_url(tid, mid), headers=ref_auth).status_code == 403
    assert client.post(f"{match_url(tid, mid)}/status", headers=ref_auth, json={'status': 'CANCELLED'}).status_code == 403

    # Referee CAN start the match
    assert client.post(f"{match_url(tid, mid)}/status", headers=ref_auth, json={'status': 'ONGOING'}).status_code == 200

    # Once ONGOING, referee CAN submit the result
    ref_ongoing_caps = client.get(f"{match_url(tid, mid)}/capabilities", headers=ref_auth).json()
    assert ref_ongoing_caps['can_submit_result'] is True
    assert client.put(
        f"{match_url(tid, mid)}/result",
        headers=ref_auth,
        json={'score_team1': 2, 'score_team2': 1},
    ).status_code == 200

    # 3. Referee scoped to another tournament has NO write capabilities here
    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users['viewer'],
            role_id=roles['REFEREE'],
            scope_type='TOURNAMENT',
            scope_id=other_tid,
        ))
    other_ref_auth = headers('viewer')
    assert client.post(f"{match_url(tid, mid)}/status", headers=other_ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, mid)}/result", headers=other_ref_auth, json={'score_team1': 1, 'score_team2': 0}).status_code == 403

    # 4. Conflict of interest: referee who plays for / belongs to a participating team
    with session_factory.begin() as db:
        m2 = Match(tournament_id=tid, stage_id=match_case['stage'], round_no=10,
                   team1_id=teams['Alpha'], team2_id=teams['Beta'], status='ONGOING')
        db.add(m2)
        db.flush()
        m2_id = m2.match_id
        db.add(TeamMembership(team_id=teams['Beta'], user_id=users['referee'], role_in_team='PLAYER'))

    assert client.post(f"{match_url(tid, m2_id)}/status", headers=ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, m2_id)}/result", headers=ref_auth, json={'score_team1': 1, 'score_team2': 0}).status_code == 403


# ==============================================================================
# Part 4: Link Validations and Integrity Constraints
# ==============================================================================

def test_match_creation_and_update_link_validations(access, session_factory, match_case):
    """Ensures that invalid stages, teams, and tournament states are strictly rejected."""
    client, headers, users, teams, _ = access
    tid = match_case['tid']
    stage_id = match_case['stage']
    other_stage = match_case['other_stage']
    auth = headers('organizer')

    with session_factory.begin() as db:
        t_unapproved = Team(name="Unapproved Team", tag="UNA", game_id=1)
        t_other_game = Team(name="Other Game Team", tag="OGT", game_id=2)
        t_no_player = Team(name="No Player Team", tag="NOP", game_id=1)
        db.add_all([t_unapproved, t_other_game, t_no_player])
        db.flush()
        una_id, og_id, nop_id = t_unapproved.team_id, t_other_game.team_id, t_no_player.team_id
        db.add(TournamentRegistration(tournament_id=tid, team_id=nop_id, status='APPROVED', reviewed_at=datetime.now(timezone.utc)))

    # 1. Same team for team1 and team2
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': teams['Alpha'],
    })
    assert res.status_code == 422
    assert "khác nhau" in res.json()['detail']

    # 2. Team not approved in tournament
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': una_id,
    })
    assert res.status_code == 422
    assert "không được duyệt" in res.json()['detail']

    # 3. Team belonging to another game
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': og_id,
    })
    assert res.status_code == 422

    # 4. Team approved but lacking PLAYER in roster snapshot
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': nop_id,
    })
    assert res.status_code == 422
    assert "PLAYER" in res.json()['detail']

    # 5. Stage belonging to another tournament
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': other_stage, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta'],
    })
    assert res.status_code == 422
    assert "không thuộc giải" in res.json()['detail']

    # 6. Scheduled_at validation: missing offset -> 422
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta'],
        'scheduled_at': '2026-11-20T19:00:00',
    })
    assert res.status_code == 422

    # 7. Scheduled_at validation: unix timestamp numeric string -> 422
    res = client.post(match_url(tid), headers=auth, json={
        'stage_id': stage_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta'],
        'scheduled_at': '20261120',
    })
    assert res.status_code == 422

    # 8. Tournament roster not locked -> 409
    other_tid = match_case['other']
    with session_factory.begin() as db:
        t_unlocked = db.get(Tournament, other_tid)
        t_unlocked.roster_locked_at = None
        stg = Stage(tournament_id=other_tid, name='Unlocked Stage', sequence_order=2)
        db.add(stg)
        db.flush()
        stg_id = stg.stage_id

    res = client.post(match_url(other_tid), headers=auth, json={
        'stage_id': stg_id, 'round_no': 1, 'team1_id': teams['Alpha'], 'team2_id': teams['Beta'],
    })
    assert res.status_code == 409
    assert "khóa đội hình" in res.json()['detail']
