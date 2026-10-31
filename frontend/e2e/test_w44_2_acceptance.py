from datetime import date, timedelta

from playwright.sync_api import Page, expect

from database_support import assign_tournament_organizer
from helpers import TEST_PASSWORD, login, register_user, unique_username
from test_tournaments import create_tournament, open_tournament


def _api_json(page: Page, method: str, url: str, *, token: str | None = None, data=None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    if method.upper() == "GET":
        response = page.request.get(url, headers=headers)
    else:
        response = page.request.post(url, headers=headers, data=data)
    assert response.ok, f"{method} {url} returned {response.status}: {response.text()}"
    return response.json()


def test_scoped_organizer_assignment_controls_tournament_ui(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    target_name, target_id = create_tournament(page, demo_password)
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token
    games = _api_json(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(game["game_id"] for game in games if game["slug"] == "valorant")
    other = _api_json(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=organizer_token,
        data={
            "name": f"Unassigned Tournament {unique_username('other')[-8:]}",
            "game_id": game_id,
            "format": "SINGLE_ELIM",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )

    scoped_username = unique_username("scoped-org")
    scoped_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    scoped_page.set_default_timeout(10_000)
    try:
        scoped_page.goto(app_base_url)
        register_user(scoped_page, scoped_username)
        assign_tournament_organizer(scoped_username, int(target_id))
        login(scoped_page, scoped_username)

        open_tournament(scoped_page, target_id, target_name)
        target_stages = scoped_page.locator('[data-testid="tournament-stages-section"]')
        expect(target_stages.get_by_role("button", name="+ Thêm vòng đấu")).to_be_visible()

        scoped_page.locator(".tournament-detail .detail-header button").filter(
            has_text="Đóng"
        ).click()
        expect(scoped_page.locator(".tournament-detail")).to_have_count(0)
        other_card = scoped_page.locator(
            f'.tournament-card[data-tournament-id="{other["tournament_id"]}"]'
        )
        other_card.get_by_role("button", name="Xem chi tiết").click()
        other_stages = scoped_page.locator('[data-testid="tournament-stages-section"]')
        expect(other_stages).to_be_visible()
        expect(other_stages.get_by_role("button", name="+ Thêm vòng đấu")).to_have_count(0)
    finally:
        scoped_page.close()


def test_large_registration_and_approved_team_ui_pagination(
    page: Page, demo_password: str, api_base_url: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token
    games = _api_json(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(game["game_id"] for game in games if game["slug"] == "valorant")

    registration_ids: set[str] = set()
    team_ids: set[str] = set()
    for index in range(51):
        username = unique_username(f"w44-2-08-{index}")
        _api_json(
            page,
            "POST",
            f"{api_base_url}/auth/register",
            data={
                "username": username,
                "email": f"{username}@example.com",
                "password": TEST_PASSWORD,
                "real_name": username,
            },
        )
        manager_token = _api_json(
            page,
            "POST",
            f"{api_base_url}/auth/login",
            data={"username": username, "password": TEST_PASSWORD},
        )["access_token"]
        team = _api_json(
            page,
            "POST",
            f"{api_base_url}/teams",
            token=manager_token,
            data={
                "name": f"W44-2-08 Team {index:02d} {username[-5:]}",
                "tag": f"E{index:02d}{username[-5:]}"[:10],
                "game_id": game_id,
            },
        )
        registration = _api_json(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/registrations",
            token=manager_token,
            data={"team_id": team["team_id"]},
        )
        _api_json(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/registrations/{registration['registration_id']}/decision",
            token=organizer_token,
            data={"status": "APPROVED"},
        )
        registration_ids.add(str(registration["registration_id"]))
        team_ids.add(str(team["team_id"]))

    page.reload()
    open_tournament(page, tournament_id, tournament_name)
    registrations = page.locator(".registration-card[data-registration-id]")
    approved_teams = page.locator(".approved-team-card[data-team-id]")
    registration_pages = page.locator('[data-testid="registrations-pagination"]')
    team_pages = page.locator('[data-testid="approved-teams-pagination"]')
    expect(registration_pages.locator(".pagination-info")).to_have_text("Trang 1 / 6 (Tổng 51 đơn)")
    expect(team_pages.locator(".pagination-info")).to_have_text("Trang 1 / 6 (Tổng 51 đội)")

    seen_registrations: set[str] = set()
    seen_teams: set[str] = set()
    for page_index in range(6):
        expect(registration_pages.locator(".pagination-info")).to_contain_text(f"Trang {page_index + 1} / 6")
        expect(team_pages.locator(".pagination-info")).to_contain_text(f"Trang {page_index + 1} / 6")
        seen_registrations.update(
            registrations.evaluate_all("items => items.map(item => item.dataset.registrationId)")
        )
        seen_teams.update(approved_teams.evaluate_all("items => items.map(item => item.dataset.teamId)"))
        if page_index < 5:
            registration_pages.get_by_role("button", name="Sau ›").click()
            team_pages.get_by_role("button", name="Sau ›").click()

    assert seen_registrations == registration_ids
    assert seen_teams == team_ids
