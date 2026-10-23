from datetime import date, datetime, timedelta, timezone

import pytest

from modules.teams.models import Team
from modules.tournaments.models import Tournament, TournamentRegistration
from test_catalog_api import session_factory
from test_permissions import access

pytestmark = pytest.mark.postgres

URL = '/api/v1/tournaments'


@pytest.fixture
def tournaments(session_factory):
    """Six tournaments over two games and all statuses, newest start date first in listings."""
    rows = [('Alpha cup', 1, 'UPCOMING'), ('Beta cup', 1, 'ONGOING'), ('Gamma cup', 2, 'UPCOMING'),
            ('Delta cup', 1, 'COMPLETED'), ('Epsilon cup', 2, 'CANCELLED'), ('Zeta cup', 1, 'UPCOMING')]
    today = date.today()
    with session_factory.begin() as db:
        created = [Tournament(name=name, game_id=game, status=state, start_date=today + timedelta(days=index))
                   for index, (name, game, state) in enumerate(rows)]
        db.add_all(created)
        db.flush()
        return {t.name: t.tournament_id for t in created}


def names(response):
    return [row['name'] for row in response.json()]


@pytest.mark.parametrize('query,expected', [
    ('', ['Zeta cup', 'Epsilon cup', 'Delta cup', 'Gamma cup', 'Beta cup', 'Alpha cup']),
    ('?status=UPCOMING', ['Zeta cup', 'Gamma cup', 'Alpha cup']),
    ('?status=ONGOING', ['Beta cup']),
    ('?status=COMPLETED', ['Delta cup']),
    ('?status=CANCELLED', ['Epsilon cup']),
    ('?game_id=2', ['Epsilon cup', 'Gamma cup']),
    ('?game_id=1&status=UPCOMING', ['Zeta cup', 'Alpha cup']),
    ('?game_id=2&status=ONGOING', []),
])
def test_public_list_filters_by_game_and_status(session_factory, access, tournaments, query, expected):
    client, *_ = access
    response = client.get(URL + query)
    assert response.status_code == 200
    assert names(response) == expected
    assert response.headers['x-total-count'] == str(len(expected))


def test_pagination_is_bounded_and_reports_filtered_total(session_factory, access, tournaments):
    client, *_ = access
    first = client.get(URL + '?limit=2')
    second = client.get(URL + '?limit=2&offset=2')
    last = client.get(URL + '?limit=2&offset=4')
    assert names(first) + names(second) + names(last) == names(client.get(URL))
    assert {r.headers['x-total-count'] for r in (first, second, last)} == {'6'}
    beyond = client.get(URL + '?status=UPCOMING&offset=10')
    assert beyond.json() == [] and beyond.headers['x-total-count'] == '3'


def test_default_page_size_is_fifty(session_factory, access):
    client, *_ = access
    with session_factory.begin() as db:
        db.add_all([Tournament(name=f'Cup {i:03}', game_id=1, start_date=date.today()) for i in range(55)])
    response = client.get(URL)
    assert len(response.json()) == 50 and response.headers['x-total-count'] == '55'
    assert len(client.get(URL + '?limit=100').json()) == 55


@pytest.mark.parametrize('query', [
    '?status=upcoming', '?status=OPEN', '?limit=0', '?limit=101', '?offset=-1',
    '?offset=2147483648', '?game_id=0', '?game_id=2147483648', '?area_id=-1',
])
def test_invalid_list_query(session_factory, access, query):
    client, *_ = access
    assert client.get(URL + query).status_code == 422


def test_browser_can_read_total_header(session_factory, access, tournaments):
    client, *_ = access
    response = client.get(URL, headers={'Origin': 'http://localhost:5173'})
    exposed = response.headers['access-control-expose-headers'].lower()
    assert 'x-total-count' in exposed


@pytest.fixture
def roster(access, session_factory, tournaments):
    """Alpha cup: Alpha/Gamma APPROVED, Beta PENDING, Delta REJECTED, Omega CANCELLED; Beta APPROVED elsewhere."""
    _, _, users, teams, _ = access
    now = datetime.now(timezone.utc)
    with session_factory.begin() as db:
        extra = [Team(name=name, tag=name[:3].upper(), game_id=1) for name in ('Gamma', 'Delta', 'Omega')]
        db.add_all(extra)
        db.flush()
        ids = {**teams, **{t.name: t.team_id for t in extra}}
        cup, other = tournaments['Alpha cup'], tournaments['Zeta cup']
        def reg(tid, team, state):
            row = TournamentRegistration(tournament_id=tid, team_id=ids[team], status=state, submitted_by=users['manager'])
            if state in ('APPROVED', 'REJECTED'):
                row.reviewed_at, row.reviewed_by = now, users['organizer']
            if state == 'REJECTED':
                row.rejection_reason = 'Private reason'
            if state == 'CANCELLED':
                row.cancelled_at = now
            return row
        db.add_all([reg(cup, 'Gamma', 'APPROVED'), reg(cup, 'Alpha', 'APPROVED'), reg(cup, 'Beta', 'PENDING'),
                    reg(cup, 'Delta', 'REJECTED'), reg(cup, 'Omega', 'CANCELLED'), reg(other, 'Beta', 'APPROVED')])
    return cup, ids


def test_public_roster_lists_only_approved_teams(session_factory, access, roster):
    client, *_ = access
    cup, ids = roster
    response = client.get(f'{URL}/{cup}/teams')
    assert response.status_code == 200
    assert [row['name'] for row in response.json()] == ['Alpha', 'Gamma']
    assert response.headers['x-total-count'] == '2'
    # Only public team fields; no submitter, reviewer or rejection details.
    assert all(set(row) == {'team_id', 'name', 'tag', 'game_id'} for row in response.json())
    assert [row['team_id'] for row in response.json()] == [ids['Alpha'], ids['Gamma']]


def test_public_roster_pagination_and_empty(session_factory, access, roster, tournaments):
    client, *_ = access
    cup, _ = roster
    page = client.get(f'{URL}/{cup}/teams?limit=1&offset=1')
    assert [row['name'] for row in page.json()] == ['Gamma'] and page.headers['x-total-count'] == '2'
    empty = client.get(f"{URL}/{tournaments['Gamma cup']}/teams")
    assert empty.status_code == 200 and empty.json() == [] and empty.headers['x-total-count'] == '0'


@pytest.mark.parametrize('state', ['ONGOING', 'COMPLETED', 'CANCELLED'])
def test_roster_stays_readable_after_tournament_closes(session_factory, access, roster, state):
    client, *_ = access
    cup, _ = roster
    with session_factory.begin() as db:
        db.get(Tournament, cup).status = state
    assert [row['name'] for row in client.get(f'{URL}/{cup}/teams').json()] == ['Alpha', 'Gamma']


@pytest.mark.parametrize('value,expected', [('999999', 404), ('0', 422), ('2147483648', 422), ('abc', 422)])
def test_roster_for_missing_or_invalid_tournament(session_factory, access, value, expected):
    client, *_ = access
    assert client.get(f'{URL}/{value}/teams').status_code == expected


@pytest.mark.parametrize('query', ['?limit=0', '?limit=101', '?offset=-1'])
def test_roster_rejects_invalid_pagination(session_factory, access, roster, query):
    client, *_ = access
    cup, _ = roster
    assert client.get(f'{URL}/{cup}/teams{query}').status_code == 422
