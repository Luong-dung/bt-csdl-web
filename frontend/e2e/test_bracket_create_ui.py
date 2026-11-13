import re
from datetime import date, timedelta

from playwright.sync_api import Page, expect

from helpers import login, unique_username
from test_matches_ui import _api_request, _register_and_login_api
from test_tournaments import open_tournament


def _setup_bracket_tournament(
    page: Page,
    api_base_url: str,
    demo_password: str,
    *,
    team_count: int,
    stage_names: tuple[str, ...] = ("Sơ loại", "Playoffs"),
    lock_roster: bool = True,
) -> dict:
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    if not organizer_token:
        login(page, "demo_organizer", demo_password)
        organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    tournament_name = f"Bracket UI {unique_username('brk')[-8:]}"
    tournament = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=organizer_token,
        data={
            "name": tournament_name,
            "game_id": game_id,
            "format": "SINGLE_ELIM",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    tournament_id = tournament["tournament_id"]

    stages = []
    for idx, name in enumerate(stage_names, start=1):
        stage = _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/stages",
            token=organizer_token,
            data={"name": name, "sequence_order": idx},
        )
        stages.append(stage)

    teams = []
    for idx in range(1, team_count + 1):
        _mgr_user, mgr_token = _register_and_login_api(page, api_base_url, f"bmgr{idx}", demo_password)
        plr_user, _plr_token = _register_and_login_api(page, api_base_url, f"bplr{idx}", demo_password)
        suffix = unique_username(f"t{idx}")[-4:]
        team = _api_request(
            page,
            "POST",
            f"{api_base_url}/teams",
            token=mgr_token,
            data={
                "name": f"BTeam {idx:02d} {suffix}",
                "tag": f"B{idx:02d}{suffix[:3]}".upper()[:10],
                "game_id": game_id,
            },
        )
        team_id = team["team_id"]
        _api_request(
            page,
            "POST",
            f"{api_base_url}/teams/{team_id}/members",
            token=mgr_token,
            data={"username": plr_user["username"], "role_in_team": "PLAYER"},
        )
        reg = _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/registrations",
            token=mgr_token,
            data={"team_id": team_id},
        )
        _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/registrations/{reg['registration_id']}/decision",
            token=organizer_token,
            data={"status": "APPROVED"},
        )
        _api_request(
            page,
            "PUT",
            f"{api_base_url}/tournaments/{tournament_id}/teams/{team_id}/roster",
            token=mgr_token,
            data={"members": [{"user_id": plr_user["user_id"], "role_in_team": "PLAYER"}]},
        )
        teams.append(team)

    if lock_roster:
        _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tournament_id}/roster-lock",
            token=organizer_token,
        )

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    return {
        "tournament_id": tournament_id,
        "tournament_name": tournament_name,
        "organizer_token": organizer_token,
        "stages": stages,
        "teams": teams,
    }


def test_bracket_reorder_preview_invalidate_and_create_ui(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=4)
    tournament_id = ctx["tournament_id"]
    tournament_name = ctx["tournament_name"]
    stages = ctx["stages"]
    teams = ctx["teams"]

    open_tournament(page, str(tournament_id), tournament_name)
    section = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(section).to_be_visible()
    expect(section.locator('[data-testid="bracket-team-order-list"] li')).to_have_count(4)

    # Select second stage ("Playoffs")
    section.locator('[data-testid="bracket-stage-select"]').select_option(str(stages[1]["stage_id"]))

    # Move team 1 down so initial order changes from [0, 1, 2, 3] to [1, 0, 2, 3]
    section.locator(f'[data-testid="bracket-team-down-{teams[0]["team_id"]}"]').click()

    # Preview bracket and verify round 1 pairs reflect the new order
    section.locator('[data-testid="bracket-preview-btn"]').click()
    preview_panel = section.locator('[data-testid="bracket-preview-panel"]')
    expect(preview_panel).to_be_visible()
    expect(preview_panel).to_contain_text("4 đội · 2 vòng · 3 trận đấu")
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-1"]')).to_contain_text(teams[1]["name"])
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-1"]')).to_contain_text(teams[0]["name"])
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-2"]')).to_contain_text(teams[2]["name"])
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-2"]')).to_contain_text(teams[3]["name"])

    # Changing team order invalidates existing preview
    section.locator(f'[data-testid="bracket-team-down-{teams[2]["team_id"]}"]').click()
    expect(preview_panel).to_have_count(0)
    expect(section.locator('[data-testid="bracket-notice-banner"]')).to_contain_text("Thứ tự đội đã thay đổi")

    # Mobile viewport check (390px without horizontal overflow)
    page.set_viewport_size({"width": 390, "height": 844})
    has_overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not has_overflow, "Bracket create UI overflows horizontally at 390px viewport"

    # Re-preview and confirm creation
    section.locator('[data-testid="bracket-preview-btn"]').click()
    expect(preview_panel).to_be_visible()
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-2"]')).to_contain_text(teams[3]["name"])
    expect(preview_panel.locator('[data-testid="bracket-preview-pair-2"]')).to_contain_text(teams[2]["name"])

    section.locator('[data-testid="bracket-create-confirm-btn"]').click()
    expect(section.locator('[data-testid="bracket-notice-banner"]')).to_contain_text("Đã tạo bracket thành công (3 trận đấu)")
    expect(section.locator('[data-testid="bracket-unavailable-reason"]')).to_be_visible()

    # Matches section now displays the 3 created matches
    matches_section = page.locator('[data-testid="tournament-matches-section"]')
    expect(matches_section.locator(".match-card")).to_have_count(3)


def test_bracket_invalid_team_count_and_409_preserves_input(
    page: Page, api_base_url: str, demo_password: str
):
    # Case 1: 3 approved teams (not power of 2) -> clear explanation and preview disabled
    ctx_3 = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=3)
    open_tournament(page, str(ctx_3["tournament_id"]), ctx_3["tournament_name"])
    section_3 = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(section_3.locator('[data-testid="bracket-invalid-count-reason"]')).to_contain_text("3")
    expect(section_3.locator('[data-testid="bracket-preview-btn"]')).to_be_disabled()

    # Close tournament detail and test Case 2: stage with existing manual match returns 409 and preserves order/stage
    page.locator(".tournament-detail .detail-header button").filter(
        has_text=re.compile("Đóng|Close")
    ).click()

    ctx_2 = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=2)
    tid = ctx_2["tournament_id"]
    stages = ctx_2["stages"]
    teams = ctx_2["teams"]
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/matches",
        token=ctx_2["organizer_token"],
        data={
            "stage_id": stages[0]["stage_id"],
            "round_no": 1,
            "team1_id": teams[0]["team_id"],
            "team2_id": teams[1]["team_id"],
        },
    )

    page.reload()
    open_tournament(page, str(tid), ctx_2["tournament_name"])
    section_2 = page.locator('[data-testid="tournament-bracket-create-section"]')

    # Reorder teams [0, 1] -> [1, 0] and select stage 0 (non-empty)
    section_2.locator(f'[data-testid="bracket-team-down-{teams[0]["team_id"]}"]').click()
    section_2.locator('[data-testid="bracket-stage-select"]').select_option(str(stages[0]["stage_id"]))
    section_2.locator('[data-testid="bracket-preview-btn"]').click()

    expect(section_2.locator('[data-testid="bracket-error-banner"]')).to_contain_text("Stage đã có trận")
    # Input must be preserved
    expect(section_2.locator('[data-testid="bracket-stage-select"]')).to_have_value(str(stages[0]["stage_id"]))
    first_row = section_2.locator('[data-testid="bracket-team-order-list"] li').first
    expect(first_row).to_contain_text(teams[1]["name"])


def test_bracket_preview_stale_response_ignored_on_tournament_change_and_viewer_hidden(
    page: Page, api_base_url: str, demo_password: str
):
    ctx_a = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=2, stage_names=("Stage A",))
    ctx_b = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=2, stage_names=("Stage B",))

    open_tournament(page, str(ctx_a["tournament_id"]), ctx_a["tournament_name"])
    section = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(section).to_be_visible()

    held_responses = []
    preview_url = f"**/api/v1/tournaments/{ctx_a['tournament_id']}/bracket/preview"

    def hold_preview(route):
        response = route.fetch()
        held_responses.append((route, response))

    page.route(preview_url, hold_preview)
    try:
        section.locator('[data-testid="bracket-preview-btn"]').click()
        page.wait_for_timeout(200)
        assert len(held_responses) == 1, "Preview request did not reach the held route"

        # Switch to Tournament B while Tournament A preview is in-flight
        page.locator(".tournament-detail .detail-header button").filter(
            has_text=re.compile("Đóng|Close")
        ).click()
        open_tournament(page, str(ctx_b["tournament_id"]), ctx_b["tournament_name"])

        route, response = held_responses.pop()
        route.fulfill(response=response)
        page.unroute(preview_url, hold_preview)

        expect(page.locator(".tournament-detail h3")).to_have_text(ctx_b["tournament_name"])
        expect(page.locator('[data-testid="bracket-preview-panel"]')).to_have_count(0)
        expect(page.locator('[data-testid="bracket-error-banner"]')).to_have_count(0)
    finally:
        for route, response in held_responses:
            route.fulfill(response=response)
        page.unroute(preview_url, hold_preview)

    # Logout and verify unauthenticated viewer does not see bracket creation section
    page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
    expect(page.locator(".auth-modal-close")).to_be_visible()
    page.locator(".auth-modal-close").click()
    expect(page.locator('[data-testid="tournament-bracket-create-section"]')).to_have_count(0)


def test_bracket_loads_all_16_approved_teams_across_pagination(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=16, stage_names=("Bracket 16",))
    open_tournament(page, str(ctx["tournament_id"]), ctx["tournament_name"])

    section = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(section).to_be_visible()
    expect(section.locator('[data-testid="bracket-team-order-list"] li')).to_have_count(16)

    section.locator('[data-testid="bracket-preview-btn"]').click()
    preview_panel = section.locator('[data-testid="bracket-preview-panel"]')
    expect(preview_panel).to_be_visible()
    expect(preview_panel).to_contain_text("16 đội · 4 vòng · 15 trận đấu")
    expect(preview_panel.locator('[data-testid="bracket-preview-pairs"] li')).to_have_count(8)

    section.locator('[data-testid="bracket-create-confirm-btn"]').click()
    expect(section.locator('[data-testid="bracket-notice-banner"]')).to_contain_text("Đã tạo bracket thành công (15 trận đấu)")
