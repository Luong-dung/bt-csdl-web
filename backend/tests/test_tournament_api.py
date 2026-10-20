import pytest

from test_catalog_api import client, ids, session_factory

URL = "/api/v1/tournaments"


@pytest.fixture
def refs(client):
    return ids(client, "games", "game_id", "slug"), ids(client, "areas", "area_id", "code")


def payload(game_id, **changes):
    data = {"name": "VCT Pacific", "game_id": game_id, "start_date": "2026-11-01", "end_date": "2026-11-10"}
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

    other = client.post(URL, json=payload(games["dota-2"], name="Dota Cup", start_date="2026-12-01", end_date=None))
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
    response = client.post(URL, json=payload(games["valorant"], start_date="2026-11-01", end_date="2026-11-01"))
    assert response.status_code == 201


@pytest.mark.parametrize("changes", [
    {"name": "  "},
    {"name": "AB"},
    {"name": "x" * 151},
    {"format": "SWISS"},
    {"format": None},
    {"start_date": "2026-13-01"},
    {"start_date": None},
    {"end_date": "2026-10-31"},
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
