from datetime import date, timedelta

from playwright.sync_api import Page, expect

from database_support import assign_tournament_organizer, seed_large_tournament_pagination
from helpers import login, register_user, unique_username
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
        open_tournament(scoped_page, str(other["tournament_id"]), other["name"])
        other_stages = scoped_page.locator('[data-testid="tournament-stages-section"]')
        expect(other_stages).to_be_visible()
        expect(other_stages.get_by_role("button", name="+ Thêm vòng đấu")).to_have_count(0)
    finally:
        scoped_page.close()


def test_large_registration_and_approved_team_ui_pagination(
    page: Page, browser, app_base_url: str, demo_password: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)
    manager_username = unique_username("w44-2-08-pagination-manager")
    manager_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    manager_page.set_default_timeout(10_000)
    try:
        manager_page.goto(app_base_url)
        register_user(manager_page, manager_username)
        login(manager_page, manager_username)
        fixture = seed_large_tournament_pagination(int(tournament_id), manager_username)

        # This team's registration is deliberately on page 3; the other scoped team is unregistered.
        open_tournament(manager_page, tournament_id, tournament_name)
        registration_form = manager_page.locator(".registration-form")
        expect(registration_form).to_be_visible()
        team_picker = registration_form.locator('select[name="team_id"]')
        expect(team_picker.locator(f'option[value="{fixture["registered_team_id"]}"]')).to_have_count(0)
        expect(team_picker.locator(f'option[value="{fixture["available_team_id"]}"]')).to_have_count(1)
        expect(team_picker).to_have_value(str(fixture["available_team_id"]))
    finally:
        manager_page.close()

    registration_ids = {str(value) for value in fixture["registration_ids"]}
    team_ids = {str(value) for value in fixture["team_ids"]}
    target_registration_id = str(fixture["registered_registration_id"])

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
        current_registration_ids = registrations.evaluate_all(
            "items => items.map(item => item.dataset.registrationId)"
        )
        if target_registration_id in current_registration_ids:
            assert page_index == 2
        seen_registrations.update(current_registration_ids)
        seen_teams.update(approved_teams.evaluate_all("items => items.map(item => item.dataset.teamId)"))
        if page_index < 5:
            previous_registration_ids = registrations.evaluate_all(
                "items => items.map(item => item.dataset.registrationId)"
            )
            previous_team_ids = approved_teams.evaluate_all(
                "items => items.map(item => item.dataset.teamId)"
            )
            registration_pages.get_by_role("button", name="Sau ›").click()
            team_pages.get_by_role("button", name="Sau ›").click()
            page.wait_for_function(
                """previous => {
                    const registrationIds = Array.from(
                        document.querySelectorAll(".registration-card[data-registration-id]")
                    ).map(item => item.dataset.registrationId);
                    const teamIds = Array.from(
                        document.querySelectorAll(".approved-team-card[data-team-id]")
                    ).map(item => item.dataset.teamId);
                    return registrationIds.length > 0 && teamIds.length > 0
                        && JSON.stringify(registrationIds) !== JSON.stringify(previous.registrationIds)
                        && JSON.stringify(teamIds) !== JSON.stringify(previous.teamIds);
                }""",
                arg={
                    "registrationIds": previous_registration_ids,
                    "teamIds": previous_team_ids,
                },
            )

    assert seen_registrations == registration_ids
    assert seen_teams == team_ids
    assert target_registration_id in seen_registrations
