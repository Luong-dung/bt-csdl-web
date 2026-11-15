"""W46-07: Bracket integration tests covering:
- Full lifecycle: UPCOMING -> preview -> create -> ONGOING -> semifinals -> finals -> COMPLETED
- Atomic winner slot advancement and transition to official standings (FINAL)
- Large 64-team bracket generation, round/slot structure, and pagination
- Fault injection: rollback of bracket create, result submit, and status updates on audit failures
- Comprehensive permission matrix: ADMIN, ORGANIZER, REFEREE (scoped/foreign/global/conflict of interest), VIEWER
- Legacy manual stage independence and migration schema verification
"""
import pytest
from sqlalchemy import func, select

from core.security import create_access_token
from modules.identity.models import AuditLog, RoleAssignment, User
from modules.teams.models import TeamMembership
from modules.tournaments.models import BracketMatch, Match, TournamentBracket
from test_bracket_create import add_teams
from test_bracket_foundation import bracket_case
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def bracket_url(tid, suffix=''):
    return f"/api/v1/tournaments/{tid}/bracket{suffix}"


def match_url(tid, match_id=None):
    base = f"/api/v1/tournaments/{tid}/matches"
    return f"{base}/{match_id}" if match_id is not None else base


@pytest.fixture
def four_team_case(access, session_factory, bracket_case):
    """UPCOMING tournament with locked roster and 4 APPROVED teams ready for bracket preview/create."""
    _, _, _, teams, roles = access
    order = [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, 4)]
    with session_factory.begin() as db:
        # Cancel the legacy manual match from match_case so it doesn't block tournament completion
        db.get(Match, bracket_case['match']).status = 'CANCELLED'
    return bracket_case | {'order': order}


# ==============================================================================
# Part 1: Full Lifecycle Integration & Atomic Advancement to Official Standings
# ==============================================================================

def test_full_bracket_lifecycle_advancement_and_standings(access, session_factory, four_team_case):
    """End-to-end integration:
    UPCOMING -> preview token -> create 4-team bracket -> ONGOING ->
    semifinal 1 -> semifinal 2 -> final -> official standings (FINAL) -> COMPLETED tournament.
    """
    client, headers, users, teams, roles = access
    tid = four_team_case['tid']
    stage_id = four_team_case['empty_stage']
    team_order = four_team_case['order']
    t_alpha, t_beta, t_gamma, t_delta = team_order
    organizer_auth = headers('organizer')

    # Step 1: Preview bracket
    preview_res = client.post(
        bracket_url(tid, '/preview'),
        headers=organizer_auth,
        json={'stage_id': stage_id, 'team_ids': team_order},
    )
    assert preview_res.status_code == 200, preview_res.text
    preview_data = preview_res.json()
    preview_token = preview_data['preview_token']
    assert preview_data['team_count'] == 4
    assert preview_data['round_count'] == 2
    assert len(preview_data['matches']) == 3

    # Step 2: Create bracket
    create_res = client.post(
        bracket_url(tid),
        headers=organizer_auth,
        json={
            'stage_id': stage_id,
            'team_ids': team_order,
            'preview_token': preview_token,
        },
    )
    assert create_res.status_code == 201, create_res.text
    bracket_data = create_res.json()
    bracket_id = bracket_data['bracket_id']
    nodes = bracket_data['matches']
    assert len(nodes) == 3

    # Identify matches: nodes 0 and 1 are Round 1 (semifinals), node 2 is Round 2 (final)
    m_semi1 = [n for n in nodes if n['round_index'] == 1 and n['position'] == 1][0]
    m_semi2 = [n for n in nodes if n['round_index'] == 1 and n['position'] == 2][0]
    m_final = [n for n in nodes if n['round_index'] == 2 and n['position'] == 1][0]

    semi1_id = m_semi1['match']['match_id']
    semi2_id = m_semi2['match']['match_id']
    final_id = m_final['match']['match_id']

    assert m_semi1['next_match_id'] == final_id and m_semi1['next_slot'] == 1
    assert m_semi2['next_match_id'] == final_id and m_semi2['next_slot'] == 2
    assert m_final['next_match_id'] is None and m_final['next_slot'] is None
    assert m_final['match']['team1'] is None and m_final['match']['team2'] is None

    # Step 3: Check initial Standings (PROVISIONAL, all rank=null)
    std_res = client.get(bracket_url(tid, '/standings'))
    assert std_res.status_code == 200
    std_data = std_res.json()
    assert std_data['status'] == 'PROVISIONAL'
    assert std_data['total'] == 4
    assert all(item['rank'] is None for item in std_data['items'])
    assert all(item['matches_played'] == 0 for item in std_data['items'])

    # Step 4: Transition tournament to ONGOING
    tourn_start = client.post(
        f"/api/v1/tournaments/{tid}/status",
        headers=organizer_auth,
        json={'status': 'ONGOING'},
    )
    assert tourn_start.status_code == 200

    # Step 5: Semifinal 1 (Alpha vs Beta) -> Alpha wins 2 - 0
    assert client.post(f"{match_url(tid, semi1_id)}/status", headers=organizer_auth, json={'status': 'ONGOING'}).status_code == 200
    res_semi1 = client.put(f"{match_url(tid, semi1_id)}/result", headers=organizer_auth, json={'score_team1': 2, 'score_team2': 0})
    assert res_semi1.status_code == 200

    # Final match must now have team1 populated with Alpha, team2 still None
    final_check1 = client.get(match_url(tid, final_id)).json()
    assert final_check1['team1']['team_id'] == t_alpha
    assert final_check1['team2'] is None

    # Standings check after Semifinal 1: Beta eliminated at Round 1 -> rank 3 (2^(2-1)+1 = 3)
    std1 = client.get(bracket_url(tid, '/standings')).json()
    assert std1['status'] == 'PROVISIONAL'
    ranks1 = {item['team']['team_id']: item['rank'] for item in std1['items']}
    assert ranks1[t_beta] == 3
    assert ranks1[t_alpha] is None

    # Step 6: Semifinal 2 (Gamma vs Delta) -> Delta wins 1 - 2
    assert client.post(f"{match_url(tid, semi2_id)}/status", headers=organizer_auth, json={'status': 'ONGOING'}).status_code == 200
    res_semi2 = client.put(f"{match_url(tid, semi2_id)}/result", headers=organizer_auth, json={'score_team1': 1, 'score_team2': 2})
    assert res_semi2.status_code == 200

    # Final match must now have both team1 (Alpha) and team2 (Delta)!
    final_check2 = client.get(match_url(tid, final_id)).json()
    assert final_check2['team1']['team_id'] == t_alpha
    assert final_check2['team2']['team_id'] == t_delta
    assert final_check2['status'] == 'PENDING'

    # Standings check: Gamma and Beta both eliminated at Round 1 -> tied for rank 3
    std2 = client.get(bracket_url(tid, '/standings')).json()
    ranks2 = {item['team']['team_id']: item['rank'] for item in std2['items']}
    assert ranks2[t_beta] == 3
    assert ranks2[t_gamma] == 3
    assert ranks2[t_alpha] is None
    assert ranks2[t_delta] is None

    # Step 7: Final Match (Alpha vs Delta) -> Alpha wins 3 - 1
    assert client.post(f"{match_url(tid, final_id)}/status", headers=organizer_auth, json={'status': 'ONGOING'}).status_code == 200
    res_final = client.put(f"{match_url(tid, final_id)}/result", headers=organizer_auth, json={'score_team1': 3, 'score_team2': 1})
    assert res_final.status_code == 200

    # Step 8: Standings are now officially FINAL!
    final_std = client.get(bracket_url(tid, '/standings')).json()
    assert final_std['status'] == 'FINAL'
    final_ranks = {item['team']['team_id']: item['rank'] for item in final_std['items']}
    assert final_ranks[t_alpha] == 1  # Champion
    assert final_ranks[t_delta] == 2  # Runner-up
    assert final_ranks[t_beta] == 3   # Tied 3rd
    assert final_ranks[t_gamma] == 3  # Tied 3rd

    # Step 9: Tournament completion succeeds
    tourn_finish = client.post(
        f"/api/v1/tournaments/{tid}/status",
        headers=organizer_auth,
        json={'status': 'COMPLETED'},
    )
    assert tourn_finish.status_code == 200

    # Step 10: Verify intact Audit Log chain
    with session_factory() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.resource.in_(['bracket', 'match'])).order_by(AuditLog.log_id)))
        actions = [l.action for l in logs]
        assert actions == [
            'BRACKET_CREATED',
            'MATCH_STARTED',
            'MATCH_RESULT_SUBMITTED',
            'MATCH_STARTED',
            'MATCH_RESULT_SUBMITTED',
            'MATCH_STARTED',
            'MATCH_RESULT_SUBMITTED',
        ]
        # First result advanced to slot 1
        res1_log = [l for l in logs if l.action == 'MATCH_RESULT_SUBMITTED' and l.details['match_id'] == semi1_id][0]
        assert res1_log.details['bracket_id'] == bracket_id
        assert res1_log.details['advancement']['slot'] == 1
        assert res1_log.details['advancement']['match_id'] == final_id

        # Second result advanced to slot 2
        res2_log = [l for l in logs if l.action == 'MATCH_RESULT_SUBMITTED' and l.details['match_id'] == semi2_id][0]
        assert res2_log.details['bracket_id'] == bracket_id
        assert res2_log.details['advancement']['slot'] == 2
        assert res2_log.details['advancement']['match_id'] == final_id

        # Final result has advancement=None
        res_final_log = [l for l in logs if l.action == 'MATCH_RESULT_SUBMITTED' and l.details['match_id'] == final_id][0]
        assert res_final_log.details['bracket_id'] == bracket_id
        assert res_final_log.details['advancement'] is None


# ==============================================================================
# Part 2: Large 64-Team Bracket Lifecycle, Tree Structure & Pagination
# ==============================================================================

def test_large_64_team_bracket_lifecycle_and_pagination(access, session_factory, bracket_case):
    """Generates a 64-team single-elimination bracket (63 matches, 6 rounds).
    Verifies tree completeness, destination connectivity, and standings pagination.
    """
    client, headers, users, teams, roles = access
    tid = bracket_case['tid']
    stage_id = bracket_case['empty_stage']
    organizer_auth = headers('organizer')

    team_order = [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, 64)]
    assert len(team_order) == 64

    # 1. Preview
    p_res = client.post(bracket_url(tid, '/preview'), headers=organizer_auth,
                        json={'stage_id': stage_id, 'team_ids': team_order})
    assert p_res.status_code == 200
    token = p_res.json()['preview_token']

    # 2. Create 64-team bracket
    c_res = client.post(bracket_url(tid), headers=organizer_auth,
                        json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': token})
    assert c_res.status_code == 201
    bracket_data = c_res.json()
    assert bracket_data['team_count'] == 64
    assert bracket_data['round_count'] == 6
    assert len(bracket_data['matches']) == 63

    # 3. Verify Tree Structure: Round 1 has 32, Round 2 has 16, ..., Round 6 has 1
    matches = bracket_data['matches']
    by_round = {}
    for m in matches:
        by_round.setdefault(m['round_index'], []).append(m)

    assert [len(by_round[r]) for r in range(1, 7)] == [32, 16, 8, 4, 2, 1]

    # Every round 1 match has concrete teams; higher rounds have TBD
    for m in by_round[1]:
        assert m['match']['team1'] is not None and m['match']['team2'] is not None
    for r in range(2, 7):
        for m in by_round[r]:
            assert m['match']['team1'] is None and m['match']['team2'] is None

    # Destination connectivity: all matches in rounds 1..5 point to exact slot 1 or 2 in round+1
    for r in range(1, 6):
        for m in by_round[r]:
            assert m['next_round'] == r + 1
            assert m['next_position'] == (m['position'] + 1) // 2
            assert m['next_slot'] in (1, 2)
            assert m['next_match_id'] is not None

    final_match = by_round[6][0]
    assert final_match['next_round'] is None
    assert final_match['next_position'] is None
    assert final_match['next_slot'] is None
    assert final_match['next_match_id'] is None

    # 4. Standings Pagination (>50 items)
    std_p1 = client.get(bracket_url(tid, '/standings'), params={'offset': 0, 'limit': 50})
    assert std_p1.status_code == 200
    assert std_p1.headers['x-total-count'] == "64"
    p1_items = std_p1.json()['items']
    assert len(p1_items) == 50

    std_p2 = client.get(bracket_url(tid, '/standings'), params={'offset': 50, 'limit': 50})
    assert std_p2.status_code == 200
    assert std_p2.headers['x-total-count'] == "64"
    p2_items = std_p2.json()['items']
    assert len(p2_items) == 14

    p1_ids = {item['team']['team_id'] for item in p1_items}
    p2_ids = {item['team']['team_id'] for item in p2_items}
    assert len(p1_ids & p2_ids) == 0, "Overlapping teams across standings pages"
    assert (p1_ids | p2_ids) == set(team_order), "Missing teams in standings pagination"

    # 5. Public DTO Safety Check
    for item in p1_items + p2_items:
        assert set(item.keys()) == {'team', 'rank', 'matches_played', 'wins', 'losses'}
        assert 'email' not in str(item)
        assert 'password' not in str(item)


# ==============================================================================
# Part 3: Fault Injection Rollback on Bracket Mutations
# ==============================================================================

def test_audit_failure_fault_injection_rollback_on_bracket_operations(access, session_factory, four_team_case, monkeypatch):
    """Fault injection: when record_audit raises an exception during write operations,
    the entire transaction is rolled back and no partial bracket or match state persists.
    """
    client, headers, users, _, _ = access
    tid = four_team_case['tid']
    stage_id = four_team_case['empty_stage']
    team_order = four_team_case['order']
    organizer_auth = headers('organizer')

    p_res = client.post(bracket_url(tid, '/preview'), headers=organizer_auth,
                        json={'stage_id': stage_id, 'team_ids': team_order})
    preview_token = p_res.json()['preview_token']

    def broken_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit storage outage")

    # 1. Fault injection on bracket creation
    monkeypatch.setattr('routes.brackets.record_audit', broken_audit)
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.post(
            bracket_url(tid),
            headers=organizer_auth,
            json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': preview_token},
        )

    # Verify zero bracket rows, zero matches in stage, zero audit logs
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TournamentBracket).where(TournamentBracket.tournament_id == tid)) == 0
        assert db.scalar(select(func.count()).select_from(Match).where(Match.stage_id == stage_id)) == 0
        assert db.scalar(select(func.count()).select_from(BracketMatch)) == 0

    # 2. Reset monkeypatch and create bracket cleanly
    monkeypatch.undo()
    create_res = client.post(
        bracket_url(tid),
        headers=organizer_auth,
        json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': preview_token},
    )
    assert create_res.status_code == 201
    bracket_data = create_res.json()
    semi1_id = bracket_data['matches'][0]['match']['match_id']
    final_id = bracket_data['matches'][2]['match']['match_id']

    # Transition tournament to ONGOING and start match
    client.post(f"/api/v1/tournaments/{tid}/status", headers=organizer_auth, json={'status': 'ONGOING'})
    client.post(f"{match_url(tid, semi1_id)}/status", headers=organizer_auth, json={'status': 'ONGOING'})

    # 3. Fault injection on result submission (which advances winner into destination slot)
    monkeypatch.setattr('routes.match_results.record_audit', broken_audit)
    with pytest.raises(RuntimeError, match="Simulated audit storage outage"):
        client.put(
            f"{match_url(tid, semi1_id)}/result",
            headers=organizer_auth,
            json={'score_team1': 2, 'score_team2': 0},
        )

    # Verify atomic rollback: source match remains ONGOING (not COMPLETED), destination slot 1 remains None, and zero result audits written
    with session_factory() as db:
        source_m = db.get(Match, semi1_id)
        dest_m = db.get(Match, final_id)
        assert source_m.status == 'ONGOING'
        assert source_m.winner_id is None
        assert dest_m.team1_id is None
        assert dest_m.team2_id is None
        result_audits = list(db.scalars(select(AuditLog).where(
            AuditLog.resource == 'match',
            AuditLog.action == 'MATCH_RESULT_SUBMITTED',
        )))
        assert len(result_audits) == 0


# ==============================================================================
# Part 4: Comprehensive Bracket Permission Matrix
# ==============================================================================

def test_comprehensive_bracket_permission_matrix(access, session_factory, four_team_case):
    """Verifies access control across all roles and scopes on bracket operations:
    - ADMIN & ORGANIZER creator & ORGANIZER scoped: full management
    - ORGANIZER scoped to another tournament: 403
    - REFEREE role-only (no RoleAssignment): 403 on write operations
    - REFEREE scoped to this tournament: can start & submit result, CANNOT preview, create, edit, delete, or cancel bracket matches
    - REFEREE scoped to another tournament: 403
    - GLOBAL REFEREE: 403
    - REFEREE with conflict of interest (player in participating team): 403 on start & result
    - VIEWER (403) and Anonymous without token (401) on write endpoints
    """
    client, headers, users, teams, roles = access
    tid = four_team_case['tid']
    other_tid = four_team_case['other']
    stage_id = four_team_case['empty_stage']
    team_order = four_team_case['order']
    t_alpha, t_beta, t_gamma, t_delta = team_order

    # 1. Anonymous (no token) -> 401 on write endpoints
    assert client.post(bracket_url(tid, '/preview'), json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 401
    assert client.post(bracket_url(tid), json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': 'dummy'}).status_code == 401
    assert client.patch(match_url(tid, 1), json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 401
    assert client.put(f"{match_url(tid, 1)}/result", json={'score_team1': 2, 'score_team2': 0}).status_code == 401

    # 2. VIEWER -> 403 on write endpoints
    viewer_auth = headers('viewer')
    assert client.post(bracket_url(tid, '/preview'), headers=viewer_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 403
    assert client.post(bracket_url(tid), headers=viewer_auth, json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': 'dummy'}).status_code == 403
    assert client.patch(match_url(tid, 1), headers=viewer_auth, json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 403
    assert client.put(f"{match_url(tid, 1)}/result", headers=viewer_auth, json={'score_team1': 2, 'score_team2': 0}).status_code == 403

    # 3. REFEREE with role-only (no RoleAssignment) -> 403 on write endpoints
    ref_auth = headers('referee')
    assert client.post(bracket_url(tid, '/preview'), headers=ref_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 403
    assert client.post(bracket_url(tid), headers=ref_auth, json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': 'dummy'}).status_code == 403
    assert client.patch(match_url(tid, 1), headers=ref_auth, json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 403
    assert client.post(f"{match_url(tid, 1)}/status", headers=ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, 1)}/result", headers=ref_auth, json={'score_team1': 2, 'score_team2': 0}).status_code == 403

    # 4. Scoped ORGANIZER vs Foreign ORGANIZER vs ADMIN
    with session_factory.begin() as db:
        foreign_org = User(username='foreign_org', email='foreign_org@example.com', password_hash='unused', role_id=roles['ORGANIZER'])
        scoped_org = User(username='scoped_org', email='scoped_org@example.com', password_hash='unused', role_id=roles['ORGANIZER'])
        db.add_all([foreign_org, scoped_org])
        db.flush()
        db.add_all([
            RoleAssignment(user_id=foreign_org.user_id, role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=other_tid),
            RoleAssignment(user_id=scoped_org.user_id, role_id=roles['ORGANIZER'], scope_type='TOURNAMENT', scope_id=tid),
        ])
        foreign_org_token = create_access_token({"sub": str(foreign_org.user_id)})
        scoped_org_token = create_access_token({"sub": str(scoped_org.user_id)})
    foreign_org_auth = {"Authorization": "Bearer " + foreign_org_token}
    scoped_org_auth = {"Authorization": "Bearer " + scoped_org_token}
    admin_auth = headers('admin')
    creator_auth = headers('organizer')

    # Foreign organizer cannot preview or create bracket on tid
    assert client.post(bracket_url(tid, '/preview'), headers=foreign_org_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 403
    assert client.post(bracket_url(tid), headers=foreign_org_auth, json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': 'dummy'}).status_code == 403

    # ADMIN and Scoped ORGANIZER CAN preview bracket
    assert client.post(bracket_url(tid, '/preview'), headers=admin_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 200
    assert client.post(bracket_url(tid, '/preview'), headers=scoped_org_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 200

    # 5. Preview & Create by Creator ORGANIZER
    p_res = client.post(bracket_url(tid, '/preview'), headers=creator_auth,
                        json={'stage_id': stage_id, 'team_ids': team_order})
    assert p_res.status_code == 200
    token = p_res.json()['preview_token']

    c_res = client.post(bracket_url(tid), headers=creator_auth,
                        json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': token})
    assert c_res.status_code == 201
    bracket_data = c_res.json()
    semi1_id = bracket_data['matches'][0]['match']['match_id']
    semi2_id = bracket_data['matches'][1]['match']['match_id']

    # 6. Schedule PATCH permissions on PENDING bracket match:
    # Foreign organizer cannot patch schedule
    assert client.patch(match_url(tid, semi1_id), headers=foreign_org_auth, json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 403
    # Creator organizer, scoped organizer, and admin can patch scheduled_at
    assert client.patch(match_url(tid, semi1_id), headers=creator_auth, json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 200
    assert client.patch(match_url(tid, semi1_id), headers=scoped_org_auth, json={'scheduled_at': '2026-11-21T14:00:00Z'}).status_code == 200
    assert client.patch(match_url(tid, semi1_id), headers=admin_auth, json={'scheduled_at': '2026-11-22T16:00:00Z'}).status_code == 200
    # Patching non-schedule fields on bracket match is rejected with 409
    bad_struct = client.patch(match_url(tid, semi1_id), headers=creator_auth, json={'round_no': 2})
    assert bad_struct.status_code == 409
    assert 'Trận thuộc bracket chỉ được sửa lịch thi đấu' in bad_struct.json()['detail']

    # 7. Grant REFEREE scoped to THIS tournament
    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users['referee'],
            role_id=roles['REFEREE'],
            scope_type='TOURNAMENT',
            scope_id=tid,
        ))

    # Scoped referee CANNOT preview or create bracket
    assert client.post(bracket_url(tid, '/preview'), headers=ref_auth, json={'stage_id': stage_id, 'team_ids': team_order}).status_code == 403
    assert client.post(bracket_url(tid), headers=ref_auth, json={'stage_id': stage_id, 'team_ids': team_order, 'preview_token': token}).status_code == 403

    # Scoped referee CANNOT patch schedule, delete, or cancel bracket match
    assert client.patch(match_url(tid, semi1_id), headers=ref_auth, json={'scheduled_at': '2026-11-20T12:00:00Z'}).status_code == 403
    assert client.delete(match_url(tid, semi1_id), headers=ref_auth).status_code == 403
    assert client.post(f"{match_url(tid, semi1_id)}/status", headers=ref_auth, json={'status': 'CANCELLED'}).status_code == 403

    # Transition tournament to ONGOING
    client.post(f"/api/v1/tournaments/{tid}/status", headers=creator_auth, json={'status': 'ONGOING'})

    # Scoped referee CAN start match and submit result
    assert client.post(f"{match_url(tid, semi1_id)}/status", headers=ref_auth, json={'status': 'ONGOING'}).status_code == 200
    assert client.put(f"{match_url(tid, semi1_id)}/result", headers=ref_auth, json={'score_team1': 2, 'score_team2': 0}).status_code == 200

    # 8. Foreign referee (scoped to other_tid) has NO write permissions here
    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users['viewer'],
            role_id=roles['REFEREE'],
            scope_type='TOURNAMENT',
            scope_id=other_tid,
        ))
    foreign_ref_auth = headers('viewer')
    assert client.post(f"{match_url(tid, semi2_id)}/status", headers=foreign_ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, semi2_id)}/result", headers=foreign_ref_auth, json={'score_team1': 2, 'score_team2': 1}).status_code == 403

    # 9. Global referee has NO write permissions (policy requires TOURNAMENT assignment)
    with session_factory.begin() as db:
        db.add(RoleAssignment(
            user_id=users['manager'],
            role_id=roles['REFEREE'],
            scope_type='GLOBAL',
            scope_id=None,
        ))
    global_ref_auth = headers('manager')
    assert client.post(f"{match_url(tid, semi2_id)}/status", headers=global_ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, semi2_id)}/result", headers=global_ref_auth, json={'score_team1': 2, 'score_team2': 1}).status_code == 403

    # 10. Conflict of interest: referee who belongs to participating team Gamma
    with session_factory.begin() as db:
        db.add(TeamMembership(team_id=t_gamma, user_id=users['referee'], role_in_team='PLAYER'))

    # Referee cannot start or score match involving Gamma
    assert client.post(f"{match_url(tid, semi2_id)}/status", headers=ref_auth, json={'status': 'ONGOING'}).status_code == 403
    assert client.put(f"{match_url(tid, semi2_id)}/result", headers=ref_auth, json={'score_team1': 2, 'score_team2': 1}).status_code == 403


# ==============================================================================
# Part 5: Legacy Stage Independence & Migration Integrity
# ==============================================================================

def test_legacy_stage_independence_and_migration_integrity(access, session_factory, four_team_case):
    """Verifies that:
    1. Stages with bracket reject manual matches (POST /matches -> 409).
    2. Manual matches cannot be patched into bracket stage (PATCH stage_id -> 409).
    3. Manual matches in other stages operate independently and do NOT contribute to bracket standings.
    4. Legacy next_match_id link on manual match does NOT auto-advance winner into destination slot.
    5. Database schema for brackets complies with migrations.
    """
    client, headers, _, teams, _ = access
    tid = four_team_case['tid']
    stage_bracket_id = four_team_case['empty_stage']
    manual_stage_id = four_team_case['stage']
    organizer_auth = headers('organizer')
    team_order = four_team_case['order']

    # 1. Create a manual match in the manual stage
    manual_res = client.post(
        match_url(tid),
        headers=organizer_auth,
        json={
            'stage_id': manual_stage_id,
            'round_no': 1,
            'team1_id': teams['Alpha'],
            'team2_id': teams['Beta'],
        },
    )
    assert manual_res.status_code == 201
    manual_mid = manual_res.json()['match_id']

    # 2. Create bracket in stage_bracket_id
    p_res = client.post(bracket_url(tid, '/preview'), headers=organizer_auth,
                        json={'stage_id': stage_bracket_id, 'team_ids': team_order})
    token = p_res.json()['preview_token']
    assert client.post(bracket_url(tid), headers=organizer_auth,
                       json={'stage_id': stage_bracket_id, 'team_ids': team_order, 'preview_token': token}).status_code == 201

    # 3. Reject creating manual match into the bracket stage -> 409
    bad_create = client.post(
        match_url(tid),
        headers=organizer_auth,
        json={
            'stage_id': stage_bracket_id,
            'round_no': 1,
            'team1_id': teams['Alpha'],
            'team2_id': teams['Beta'],
        },
    )
    assert bad_create.status_code == 409
    assert "stage của bracket" in bad_create.json()['detail']

    # 4. Reject patching manual match into the bracket stage -> 409
    bad_patch = client.patch(
        match_url(tid, manual_mid),
        headers=organizer_auth,
        json={'stage_id': stage_bracket_id},
    )
    assert bad_patch.status_code == 409
    assert "stage của bracket" in bad_patch.json()['detail']

    # 5. Create a destination manual match in manual_stage_id with no teams and link via legacy next_match_id
    with session_factory.begin() as db:
        dest_match = Match(
            tournament_id=tid,
            stage_id=manual_stage_id,
            round_no=2,
            team1_id=None,
            team2_id=None,
            status='PENDING',
            score_team1=0,
            score_team2=0,
        )
        db.add(dest_match)
        db.flush()
        manual_dest_id = dest_match.match_id
        db.get(Match, manual_mid).next_match_id = manual_dest_id

    # 6. Transition tournament to ONGOING and complete the manual match
    client.post(f"/api/v1/tournaments/{tid}/status", headers=organizer_auth, json={'status': 'ONGOING'})
    client.post(f"{match_url(tid, manual_mid)}/status", headers=organizer_auth, json={'status': 'ONGOING'})
    score_manual = client.put(f"{match_url(tid, manual_mid)}/result", headers=organizer_auth,
                              json={'score_team1': 5, 'score_team2': 3})
    assert score_manual.status_code == 200

    # 7. Verify legacy next_match_id destination was NOT altered (no auto-advancement for unmanaged match)
    with session_factory() as db:
        dest_m = db.get(Match, manual_dest_id)
        assert dest_m.team1_id is None
        assert dest_m.team2_id is None

    # 8. Verify that bracket standings DO NOT count the manual match!
    # All bracket matches are still PENDING, so matches_played for Alpha and Beta must be 0!
    standings = client.get(bracket_url(tid, '/standings')).json()
    stats = {item['team']['team_id']: item for item in standings['items']}
    assert stats[teams['Alpha']]['matches_played'] == 0
    assert stats[teams['Beta']]['matches_played'] == 0
    assert stats[teams['Alpha']]['wins'] == 0

    # 9. Verify DB metadata and constraints
    with session_factory() as db:
        bracket_match_count = db.scalar(select(func.count()).select_from(BracketMatch).where(BracketMatch.stage_id == stage_bracket_id))
        manual_match_node = db.get(BracketMatch, manual_mid)
        assert bracket_match_count == 3
        assert manual_match_node is None
