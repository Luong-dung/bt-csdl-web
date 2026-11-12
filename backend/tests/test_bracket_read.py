"""W46-04 API: public bracket tree and standings derived from COMPLETED managed matches."""
import pytest
from sqlalchemy import select

from modules.tournaments.models import Match, Tournament
from test_bracket_create import add_teams, create, preview, url
from test_bracket_foundation import bracket_case
from test_catalog_api import session_factory
from test_match_foundation import match_case
from test_permissions import access

pytestmark = pytest.mark.postgres


def build(client, headers, factory, case, roles, teams, count):
    ids = case | {'order': [teams['Alpha'], teams['Beta'], *add_teams(factory, case, roles, count)]}
    token = preview(client, headers, ids).json()['preview_token']
    created = create(client, headers, ids, token)
    assert created.status_code == 201
    return ids, created.json()


def go_live(factory, ids):
    with factory.begin() as db:
        db.get(Tournament, ids['tid']).status = 'ONGOING'


def play(client, headers, ids, match_id, first_wins=True):
    base = f"/api/v1/tournaments/{ids['tid']}/matches/{match_id}"
    assert client.post(base+'/status', headers=headers('organizer'), json={'status': 'ONGOING'}).status_code == 200
    scores = {'score_team1': 2, 'score_team2': 1} if first_wins else {'score_team1': 0, 'score_team2': 3}
    response = client.put(base+'/result', headers=headers('organizer'), json=scores)
    assert response.status_code == 200
    return scores


def nodes_of(client, ids, round_index):
    return [n for n in client.get(url(ids)).json()['matches'] if n['round_index'] == round_index]


def standings(client, ids, **params):
    response = client.get(url(ids, '/standings'), params=params)
    assert response.status_code == 200
    return response


@pytest.fixture
def eight(access, session_factory, bracket_case):
    client, headers, _, teams, roles = access
    return build(client, headers, session_factory, bracket_case, roles, teams, 8)


def test_bracket_is_public_and_matches_create_response(access, eight):
    client, headers, *_ = access
    ids, created = eight
    response = client.get(url(ids))
    assert response.status_code == 200 and response.json() == created
    assert 'no-store' not in response.headers.get('cache-control', '')
    assert 'preview_token' not in response.text and 'created_by' not in response.text
    assert client.get(url(ids), headers=headers('viewer')).json() == created


def test_missing_tournament_or_bracket_is_404(access, bracket_case):
    client, *_ = access
    assert client.get('/api/v1/tournaments/2147483647/bracket').status_code == 404
    assert client.get('/api/v1/tournaments/2147483647/bracket/standings').status_code == 404
    assert client.get(f"/api/v1/tournaments/{bracket_case['tid']}/bracket").status_code == 404
    assert client.get(f"/api/v1/tournaments/{bracket_case['tid']}/bracket/standings").status_code == 404


def test_standings_follow_results_and_final_ranks(access, session_factory, eight):
    client, headers, *_ = access
    ids, created = eight
    order = ids['order']
    data = standings(client, ids).json()
    assert data['status'] == 'PROVISIONAL' and data['total'] == 8
    assert [i['team']['team_id'] for i in data['items']] == order
    assert all((i['rank'], i['matches_played'], i['wins'], i['losses']) == (None, 0, 0, 0) for i in data['items'])
    assert set(data['items'][0]) == {'team', 'rank', 'matches_played', 'wins', 'losses'}
    assert set(data['items'][0]['team']) == {'team_id', 'name'}
    go_live(session_factory, ids)
    # Quarterfinals: first team wins pairs 1 and 3, second team wins pairs 2 and 4.
    for node in nodes_of(client, ids, 1):
        play(client, headers, ids, node['match']['match_id'], node['position'] % 2 == 1)
    qf_winners = [order[0], order[3], order[4], order[7]]
    semis = nodes_of(client, ids, 2)
    assert [(n['match']['team1']['team_id'], n['match']['team2']['team_id']) for n in semis] == \
        [tuple(qf_winners[:2]), tuple(qf_winners[2:])]
    mid = standings(client, ids).json()
    assert mid['status'] == 'PROVISIONAL'
    ranks = {i['team']['team_id']: i['rank'] for i in mid['items']}
    assert [ranks[t] for t in order] == [None, 5, 5, None, None, 5, 5, None]
    # Ranked teams first, NULL rank last; ties keep the confirmed team order.
    assert [i['team']['team_id'] for i in mid['items']] == [order[1], order[2], order[5], order[6]] + qf_winners
    for node in semis:
        play(client, headers, ids, node['match']['match_id'], True)
    [final] = nodes_of(client, ids, 3)
    play(client, headers, ids, final['match']['match_id'], False)
    done = standings(client, ids).json()
    assert done['status'] == 'FINAL'
    table = [(i['team']['team_id'], i['rank'], i['matches_played'], i['wins'], i['losses']) for i in done['items']]
    assert table == [(order[4], 1, 3, 3, 0), (order[0], 2, 3, 2, 1), (order[3], 3, 2, 1, 1), (order[7], 3, 2, 1, 1),
                     (order[1], 5, 1, 0, 1), (order[2], 5, 1, 0, 1), (order[5], 5, 1, 0, 1), (order[6], 5, 1, 0, 1)]
    # Replaying a stored result changes nothing; pagination keeps the same order and exact total.
    scores = {'score_team1': 0, 'score_team2': 3}
    assert client.put(f"/api/v1/tournaments/{ids['tid']}/matches/{final['match']['match_id']}/result",
                      headers=headers('organizer'), json=scores).status_code == 200
    assert standings(client, ids).json() == done
    page = standings(client, ids, offset=2, limit=3)
    assert page.headers['x-total-count'] == '8'
    assert [i['team']['team_id'] for i in page.json()['items']] == [r[0] for r in table[2:5]]
    assert (page.json()['total'], page.json()['offset'], page.json()['limit']) == (8, 2, 3)
    assert standings(client, ids, offset=8).json()['items'] == []
    # Reload of the tree keeps winners and slots.
    tree = client.get(url(ids)).json()
    assert tree['matches'][-1]['match']['result']['winner_id'] == order[4]


def test_manual_matches_and_cancelled_tournament(access, session_factory, eight):
    client, headers, *_ = access
    ids, _ = eight
    go_live(session_factory, ids)
    first = nodes_of(client, ids, 1)[0]
    play(client, headers, ids, first['match']['match_id'])
    with session_factory.begin() as db:
        # A finished manual match in another stage involving bracket teams must not count.
        manual = db.get(Match, ids['match'])
        manual.team1_id, manual.team2_id = ids['order'][0], ids['order'][1]
        manual.status, manual.score_team1, manual.winner_id = 'COMPLETED', 5, ids['order'][0]
    items = {i['team']['team_id']: i for i in standings(client, ids).json()['items']}
    assert (items[ids['order'][0]]['matches_played'], items[ids['order'][0]]['wins']) == (1, 1)
    assert (items[ids['order'][1]]['losses'], items[ids['order'][1]]['rank']) == (1, 5)
    assert client.post(f"/api/v1/tournaments/{ids['tid']}/status", headers=headers('organizer'),
                       json={'status': 'CANCELLED'}).status_code == 200
    cancelled = standings(client, ids).json()
    assert cancelled['status'] == 'CANCELLED'
    assert {i['team']['team_id']: i['rank'] for i in cancelled['items']}[ids['order'][1]] == 5
    assert len(client.get(url(ids)).json()['matches']) == 7  # history stays visible


@pytest.mark.parametrize('params', [{'limit': 0}, {'limit': 101}, {'offset': -1}, {'limit': 'x'}])
def test_standings_reject_bad_pagination(access, eight, params):
    client, *_ = access
    ids, _ = eight
    assert client.get(url(ids, '/standings'), params=params).status_code == 422


def test_sixty_four_teams_are_all_visible(access, session_factory, bracket_case):
    client, headers, _, teams, roles = access
    ids, created = build(client, headers, session_factory, bracket_case, roles, teams, 64)
    tree = client.get(url(ids)).json()
    assert len(tree['matches']) == 63 and tree == created
    assert [n['round_index'] for n in tree['matches']].count(6) == 1
    data = standings(client, ids, limit=100).json()
    assert data['total'] == 64 and len(data['items']) == 64
    assert len(standings(client, ids).json()['items']) == 50
