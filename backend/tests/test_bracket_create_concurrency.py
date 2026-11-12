"""W46-03 create races through real HTTP and independent PostgreSQL connections."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from modules.identity.models import AuditLog
from modules.tournaments.models import BracketMatch, Match, TournamentBracket
from test_bracket_create import add_teams, body, preview
from test_bracket_foundation import bracket_case
from test_catalog_api import make_client
from test_match_foundation import match_case
from test_permissions import access
from test_registration_concurrency import session_factory

pytestmark = pytest.mark.postgres


@pytest.fixture
def eight(access, session_factory, bracket_case):
    _, _, _, teams, roles = access
    return bracket_case | {'order': [teams['Alpha'], teams['Beta'], *add_teams(session_factory, bracket_case, roles, 8)]}


def post_create(factory, headers, ids, token, order):
    with make_client(factory, logged_in=False) as client:
        response = client.post(f"/api/v1/tournaments/{ids['tid']}/bracket", headers=headers('organizer'),
                               json=body(ids, order) | {'preview_token': token})
        return response.status_code, response.json()


def totals(factory, tid):
    with factory() as db:
        return (db.scalar(select(func.count()).select_from(TournamentBracket)),
                db.scalar(select(func.count()).select_from(Match).where(Match.tournament_id == tid)),
                db.scalar(select(func.count()).select_from(BracketMatch)),
                db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == 'BRACKET_CREATED')))


@pytest.mark.parametrize('same', [True, False])
def test_concurrent_creates_produce_one_bracket_and_one_audit(access, session_factory, eight, same):
    client, headers, *_ = access
    order = eight['order']
    other = order[::-1]
    token = preview(client, headers, eight).json()['preview_token']
    other_token = preview(client, headers, eight, order=other).json()['preview_token']
    before = totals(session_factory, eight['tid'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post_create, session_factory, headers, eight, token, order),
                   pool.submit(post_create, session_factory, headers, eight,
                               token if same else other_token, order if same else other)]
        results = [f.result(timeout=15) for f in futures]
    codes = sorted(code for code, _ in results)
    assert codes == ([200, 201] if same else [201, 409])
    created = [data for code, data in results if code == 201][0]
    if same:
        assert [data for code, data in results if code == 200][0] == created
    assert totals(session_factory, eight['tid']) == (before[0]+1, before[1]+7, before[2]+7, before[3]+1)
    with session_factory() as db:
        bracket = db.scalar(select(TournamentBracket))
        assert bracket.bracket_id == created['bracket_id'] and bracket.team_order == created['team_ids']
