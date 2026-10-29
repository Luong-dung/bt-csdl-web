from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from modules.tournaments.models import Tournament
from test_catalog_api import client, ids, session_factory

URL = "/api/v1/tournaments"
pytestmark = pytest.mark.postgres


def day(offset):
    return str(date.today() + timedelta(days=offset))


@pytest.fixture
def refs(client):
    return ids(client, "games", "game_id", "slug"), ids(client, "areas", "area_id", "code")


def payload(game_id, **changes):
    data = {"name": "VCT Pacific", "game_id": game_id, "start_date": day(10), "end_date": day(19)}
    data.update(changes)
    return data


def test_create_list_and_detail(client, refs):
    games, areas = refs
    created = client.post(URL, json=payload(games["valorant"], name="  VCT Pacific  ", area_id=areas["VN"],
                                            format="ROUND_ROBIN", description="Vòng loại"))
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "VCT Pacific"
    assert body["format"] == "ROUND_ROBIN"
    assert body["status"] == "UPCOMING"
    assert body["area_id"] == areas["VN"]

    other = client.post(URL, json=payload(games["dota-2"], name="Dota Cup", start_date=day(40), end_date=None))
    assert other.status_code == 201
    assert other.json()["format"] == "SINGLE_ELIM"
    assert other.json()["end_date"] is None

    listed = client.get(URL).json()
    assert [t["name"] for t in listed] == ["Dota Cup", "VCT Pacific"]
    by_game = client.get(URL, params={"game_id": games["valorant"]}).json()
    assert [t["tournament_id"] for t in by_game] == [body["tournament_id"]]
    assert client.get(URL, params={"area_id": areas["VN"]}).json() == by_game

    detail = client.get(f"{URL}/{body['tournament_id']}")
    assert detail.status_code == 200
    assert detail.json() == body


def test_same_day_tournament_is_allowed(client, refs):
    games, _ = refs
    response = client.post(URL, json=payload(games["valorant"], start_date=day(0), end_date=day(0)))
    assert response.status_code == 201


@pytest.mark.parametrize("changes", [
    {"name": "  "},
    {"name": "AB"},
    {"name": "x" * 151},
    {"format": "SWISS"},
    {"format": None},
    {"start_date": "2026-13-01"},
    {"start_date": None},
    {"end_date": day(9)},
    {"start_date": day(-1), "end_date": None},
    {"game_id": 0},
    {"game_id": 2147483648},
    {"game_id": "abc"},
    {"area_id": -1},
    {"description": "x" * 2001},
    {"status": "FINISHED"},
    {"tournament_id": 99},
    {"unknown": 1},
])
def test_invalid_payload_returns_422(client, refs, changes):
    games, _ = refs
    data = payload(games["valorant"])
    data.update(changes)
    assert client.post(URL, json=data).status_code == 422
    assert client.get(URL).json() == []


def test_missing_required_fields_returns_422(client):
    assert client.post(URL, json={}).status_code == 422
    assert client.post(URL, json={"name": "VCT Pacific"}).status_code == 422


def test_unknown_game_or_area_returns_422(client, refs):
    games, _ = refs
    missing_game = client.post(URL, json=payload(99999))
    assert missing_game.status_code == 422
    assert missing_game.json()["detail"] == "Game không tồn tại"

    missing_area = client.post(URL, json=payload(games["valorant"], area_id=99999))
    assert missing_area.status_code == 422
    assert missing_area.json()["detail"] == "Khu vực không tồn tại"
    assert client.get(URL).json() == []


@pytest.mark.parametrize("path", ["/0", "/-1", "/2147483648", "/abc"])
def test_invalid_tournament_id_returns_422(client, path):
    assert client.get(URL + path).status_code == 422


def test_missing_tournament_returns_404(client):
    assert client.get(f"{URL}/2147483647").status_code == 404


@pytest.mark.parametrize("params", [{"game_id": 0}, {"area_id": 2147483648}, {"game_id": "abc"}])
def test_invalid_list_filter_returns_422(client, params):
    assert client.get(URL, params=params).status_code == 422


@pytest.fixture
def tournament(client, refs, session_factory):
    games, _ = refs
    tournament_id = client.post(URL, json=payload(games["valorant"])).json()["tournament_id"]
    # Lifecycle tests start the tournament; W44-2-04 requires a locked roster (tested in test_roster_lock.py).
    with session_factory.begin() as db:
        db.get(Tournament, tournament_id).roster_locked_at = datetime.now(timezone.utc)
    return client.get(f"{URL}/{tournament_id}").json()


def set_status(client, tournament_id, *statuses):
    for value in statuses:
        response = client.post(f"{URL}/{tournament_id}/status", json={"status": value})
        assert response.status_code == 200, response.json()
    return response.json()


def test_update_upcoming_tournament(client, refs, tournament):
    games, areas = refs
    path = f"{URL}/{tournament['tournament_id']}"
    response = client.patch(path, json={"name": "  VCT Masters  ", "game_id": games["dota-2"], "area_id": areas["VN"],
                                        "format": "DOUBLE_ELIM", "start_date": day(5), "end_date": None})
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["game_id"], body["area_id"]) == ("VCT Masters", games["dota-2"], areas["VN"])
    assert (body["format"], body["start_date"], body["end_date"]) == ("DOUBLE_ELIM", day(5), None)
    assert client.get(path).json() == body

    cleared = client.patch(path, json={"area_id": None, "description": None})
    assert cleared.status_code == 200
    assert cleared.json()["area_id"] is None
    assert cleared.json()["name"] == "VCT Masters"


@pytest.mark.parametrize("changes", [
    {},
    {"name": None},
    {"game_id": None},
    {"format": None},
    {"start_date": None},
    {"name": "AB"},
    {"format": "SWISS"},
    {"status": "ONGOING"},
    {"created_by": 1},
    {"unknown": 1},
    {"end_date": day(9)},
    {"start_date": day(20)},
    {"start_date": day(-1)},
    {"game_id": 99999},
    {"area_id": 99999},
])
def test_invalid_update_returns_422(client, tournament, changes):
    path = f"{URL}/{tournament['tournament_id']}"
    assert client.patch(path, json=changes).status_code == 422
    assert client.get(path).json() == tournament


def test_update_keeps_past_start_date_of_started_tournament(client, session_factory, tournament):
    with session_factory.begin() as db:
        db.get(Tournament, tournament["tournament_id"]).start_date = date.today() - timedelta(days=3)
    response = client.patch(f"{URL}/{tournament['tournament_id']}", json={"start_date": day(-3), "name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["start_date"] == day(-3)


def test_update_or_status_of_missing_tournament_returns_404(client):
    assert client.patch(f"{URL}/2147483647", json={"name": "Missing"}).status_code == 404
    assert client.post(f"{URL}/2147483647/status", json={"status": "ONGOING"}).status_code == 404


@pytest.mark.parametrize("path", [
    ("CANCELLED",),
    ("ONGOING", "COMPLETED"),
    ("ONGOING", "CANCELLED"),
])
def test_allowed_status_transitions(client, tournament, path):
    assert set_status(client, tournament["tournament_id"], *path)["status"] == path[-1]


@pytest.mark.parametrize("path,target", [
    ((), "UPCOMING"),
    ((), "COMPLETED"),
    (("ONGOING",), "ONGOING"),
    (("ONGOING",), "UPCOMING"),
    (("ONGOING", "COMPLETED"), "ONGOING"),
    (("ONGOING", "COMPLETED"), "CANCELLED"),
    (("CANCELLED",), "UPCOMING"),
    (("CANCELLED",), "ONGOING"),
])
def test_invalid_status_transition_returns_409(client, tournament, path, target):
    tournament_id = tournament["tournament_id"]
    current = set_status(client, tournament_id, *path) if path else tournament
    response = client.post(f"{URL}/{tournament_id}/status", json={"status": target})
    assert response.status_code == 409
    assert client.get(f"{URL}/{tournament_id}").json() == current


@pytest.mark.parametrize("body", [{}, {"status": "FINISHED"}, {"status": None}, {"status": "ONGOING", "extra": 1}])
def test_invalid_status_payload_returns_422(client, tournament, body):
    assert client.post(f"{URL}/{tournament['tournament_id']}/status", json=body).status_code == 422


def test_ongoing_tournament_allows_only_basic_edits(client, refs, tournament):
    games, areas = refs
    tournament_id = tournament["tournament_id"]
    set_status(client, tournament_id, "ONGOING")
    path = f"{URL}/{tournament_id}"
    allowed = client.patch(path, json={"name": "VCT Live", "description": "Đang đấu", "end_date": day(30)})
    assert allowed.status_code == 200
    assert (allowed.json()["name"], allowed.json()["end_date"]) == ("VCT Live", day(30))
    for changes in [{"format": "ROUND_ROBIN"}, {"start_date": day(11)}, {"game_id": games["dota-2"]},
                    {"area_id": areas["VN"]}, {"name": "Mixed", "format": "ROUND_ROBIN"}]:
        assert client.patch(path, json=changes).status_code == 409
    assert client.get(path).json() == allowed.json()


@pytest.mark.parametrize("final", [("ONGOING", "COMPLETED"), ("CANCELLED",)])
def test_final_tournament_is_read_only(client, tournament, final):
    tournament_id = tournament["tournament_id"]
    set_status(client, tournament_id, *final)
    assert client.patch(f"{URL}/{tournament_id}", json={"name": "Too late"}).status_code == 409


@pytest.mark.parametrize("changes", [{"status": "FINISHED"}, {"end_date": date.today() - timedelta(days=1)}])
def test_database_rejects_invalid_status_and_dates(session_factory, changes):
    data = {"name": "Direct", "game_id": 1, "start_date": date.today(), **changes}
    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            db.add(Tournament(**data))
