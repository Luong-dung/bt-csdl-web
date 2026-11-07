import json
import re
from datetime import date, timedelta

from playwright.sync_api import Browser, Page, expect

from helpers import login, register_user, unique_username
from test_tournaments import open_tournament


def _api_request(page: Page, method: str, url: str, *, token: str | None = None, data=None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    method_upper = method.upper()
    if method_upper == "GET":
        response = page.request.get(url, headers=headers)
    elif method_upper == "POST":
        response = page.request.post(url, headers=headers, data=data)
    elif method_upper == "PUT":
        response = page.request.put(url, headers=headers, data=data)
    elif method_upper == "PATCH":
        response = page.request.patch(url, headers=headers, data=data)
    elif method_upper == "DELETE":
        response = page.request.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
    assert response.ok, f"{method} {url} returned {response.status}: {response.text()}"
    if response.status == 204:
        return None
    return response.json()


def _register_and_login_api(page: Page, api_base_url: str, prefix: str, password: str) -> tuple[dict, str]:
    username = unique_username(prefix)
    user = _api_request(
        page,
        "POST",
        f"{api_base_url}/auth/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "full_name": f"Match UI {username}",
            "password": password,
        },
    )
    auth = _api_request(
        page,
        "POST",
        f"{api_base_url}/auth/login",
        data={"username": username, "password": password},
    )
    return user, auth["access_token"]


def _setup_locked_tournament_with_two_teams(
    page: Page, api_base_url: str, demo_password: str
) -> dict:
    login(page, "demo_organizer", demo_password)
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    tournament_name = f"Match UI Tournament {unique_username('m-tour')[-8:]}"
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

    stage_1 = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/stages",
        token=organizer_token,
        data={"name": "Vòng bảng", "sequence_order": 1},
    )
    stage_2 = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/stages",
        token=organizer_token,
        data={"name": "Chung kết", "sequence_order": 2},
    )

    teams = []
    for idx, label in enumerate(("Alpha", "Beta"), start=1):
        _mgr_user, mgr_token = _register_and_login_api(page, api_base_url, f"mgr{idx}", demo_password)
        plr_user, _plr_token = _register_and_login_api(page, api_base_url, f"plr{idx}", demo_password)

        team = _api_request(
            page,
            "POST",
            f"{api_base_url}/teams",
            token=mgr_token,
            data={
                "name": f"Team {label} {unique_username(label.lower())[-5:]}",
                "tag": f"T{idx}{unique_username('tg')[-5:]}".upper()[:10],
                "game_id": game_id,
            },
        )
        team_id = team["team_id"]
        _api_request(
            page,
            "POST",
            f"{api_base_url}/teams/{team_id}/members",
            token=mgr_token,
            data={"user_id": plr_user["user_id"], "role_in_team": "PLAYER"},
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
            data={"user_ids": [plr_user["user_id"]]},
        )
        teams.append(team)

    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/roster-lock",
        token=organizer_token,
    )

    page.reload()
    return {
        "tournament_id": tournament_id,
        "tournament_name": tournament_name,
        "organizer_token": organizer_token,
        "stage_1": stage_1,
        "stage_2": stage_2,
        "team_1": teams[0],
        "team_2": teams[1],
    }


def test_match_crud_partial_patch_and_local_schedule_ui(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_locked_tournament_with_two_teams(page, api_base_url, demo_password)
    tournament_id = ctx["tournament_id"]
    tournament_name = ctx["tournament_name"]
    organizer_token = ctx["organizer_token"]
    stage_1 = ctx["stage_1"]
    team_1 = ctx["team_1"]
    team_2 = ctx["team_2"]

    open_tournament(page, str(tournament_id), tournament_name)

    matches_section = page.locator('[data-testid="tournament-matches-section"]')
    expect(matches_section).to_be_visible()
    expect(matches_section).to_contain_text("Trận đấu & Lịch thi đấu (0)")
    expect(matches_section.locator('[data-testid="matches-empty-state"]')).to_contain_text(
        "Giải đấu chưa có trận đấu nào được xếp lịch."
    )

    # 1. Create a PENDING match with schedule via UI
    create_btn = matches_section.get_by_role("button", name="+ Tạo trận đấu")
    expect(create_btn).to_be_visible()
    create_btn.click()

    create_form = matches_section.locator('[data-testid="match-create-form"]')
    expect(create_form).to_be_visible()
    create_form.locator('select[name="stage_id"]').select_option(str(stage_1["stage_id"]))
    create_form.locator('input[name="round_no"]').fill("1")
    create_form.locator('select[name="team1_id"]').select_option(str(team_1["team_id"]))
    create_form.locator('select[name="team2_id"]').select_option(str(team_2["team_id"]))
    create_form.locator('input[name="scheduled_at"]').fill("2026-11-15T14:30")
    create_form.get_by_role("button", name="Lưu trận đấu").click()

    expect(matches_section.locator(".notice-banner")).to_contain_text("Đã tạo trận đấu mới thành công.")
    expect(matches_section).to_contain_text("Trận đấu & Lịch thi đấu (1)")

    match_card = matches_section.locator(".match-card").first
    expect(match_card).to_be_visible()
    match_id = match_card.get_attribute("data-match-id")
    assert match_id is not None

    # Local schedule is formatted as DD/MM/YYYY HH:mm with UTC offset, and PENDING shows VS (not 0 - 0)
    expect(match_card.locator(f'[data-testid="match-schedule-{match_id}"]')).to_contain_text("15/11/2026 14:30")
    expect(match_card.locator(f'[data-testid="match-schedule-{match_id}"]')).to_contain_text("UTC")
    expect(match_card.locator(".match-vs")).to_have_text("VS")
    expect(match_card.locator(f'[data-testid="match-score-{match_id}"]')).to_have_count(0)

    # 2. Set scheduled_at with non-zero seconds via API (10:00:30Z) and verify editing ONLY round_no
    # sends ONLY {"round_no": 2} in PATCH (preserving seconds on scheduled_at and not sending teams)
    _api_request(
        page,
        "PATCH",
        f"{api_base_url}/tournaments/{tournament_id}/matches/{match_id}",
        token=organizer_token,
        data={"scheduled_at": "2026-11-15T10:00:30Z"},
    )
    page.reload()
    open_tournament(page, str(tournament_id), tournament_name)

    match_card = page.locator(f'[data-testid="match-card-{match_id}"]')
    expect(match_card.get_by_role("button", name="Sửa")).to_be_visible()
    match_card.get_by_role("button", name="Sửa").click()

    edit_form = page.locator(f'[data-testid="match-edit-form-{match_id}"]')
    expect(edit_form).to_be_visible()
    edit_form.locator('input[name="round_no"]').fill("2")

    patch_payloads: list[dict] = []

    def capture_patch(route):
        if route.request.method == "PATCH":
            patch_payloads.append(json.loads(route.request.post_data or "{}"))
        route.continue_()

    match_patch_url = f"**/api/v1/tournaments/{tournament_id}/matches/{match_id}"
    page.route(match_patch_url, capture_patch)
    try:
        edit_form.get_by_role("button", name="Lưu").click()
        expect(matches_section.locator(".notice-banner")).to_contain_text("Đã cập nhật trận đấu thành công.")
        assert len(patch_payloads) == 1
        assert patch_payloads[0] == {"round_no": 2}
    finally:
        page.unroute(match_patch_url)

    # Verify backend scheduled_at still preserves :30 seconds
    updated_matches = _api_request(page, "GET", f"{api_base_url}/tournaments/{tournament_id}/matches")
    assert len(updated_matches) == 1
    assert ":30" in updated_matches[0]["scheduled_at"]
    expect(match_card.locator(".match-round-badge")).to_have_text("Round #2")

    # 3. Clear schedule ("Xóa lịch") -> sends {"scheduled_at": null}
    match_card.get_by_role("button", name="Sửa").click()
    edit_form = page.locator(f'[data-testid="match-edit-form-{match_id}"]')
    edit_form.get_by_role("button", name="Xóa lịch").click()
    edit_form.get_by_role("button", name="Lưu").click()

    expect(matches_section.locator(".notice-banner")).to_contain_text("Đã cập nhật trận đấu thành công.")
    expect(match_card.locator(f'[data-testid="match-schedule-{match_id}"]')).to_contain_text("Chưa xếp lịch")

    # 4. Delete match
    page.once("dialog", lambda dialog: dialog.accept())
    match_card.get_by_role("button", name="Xóa").click()
    expect(matches_section.locator(".notice-banner")).to_contain_text("Đã xóa trận đấu.")
    expect(matches_section).to_contain_text("Trận đấu & Lịch thi đấu (0)")


def test_match_capability_strict_gating_and_403_refresh_preserves_form(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_locked_tournament_with_two_teams(page, api_base_url, demo_password)
    tournament_id = ctx["tournament_id"]
    tournament_name = ctx["tournament_name"]
    organizer_token = ctx["organizer_token"]
    stage_1 = ctx["stage_1"]
    team_1 = ctx["team_1"]
    team_2 = ctx["team_2"]

    created_match = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/matches",
        token=organizer_token,
        data={
            "stage_id": stage_1["stage_id"],
            "round_no": 1,
            "team1_id": team_1["team_id"],
            "team2_id": team_2["team_id"],
        },
    )
    match_id = created_match["match_id"]

    # 1. When /capabilities fails (e.g., 404/network), UI must NOT infer permissions from can_manage_matches && PENDING
    match_cap_url = f"**/api/v1/tournaments/{tournament_id}/matches/{match_id}/capabilities"
    page.route(match_cap_url, lambda route: route.fulfill(status=404, body=json.dumps({"detail": "Not found"})))
    try:
        open_tournament(page, str(tournament_id), tournament_name)
        match_card = page.locator(f'[data-testid="match-card-{match_id}"]')
        expect(match_card).to_be_visible()
        expect(match_card.get_by_role("button", name="Sửa")).to_have_count(0)
        expect(match_card.get_by_role("button", name="Xóa")).to_have_count(0)
    finally:
        page.unroute(match_cap_url)

    # 2. Reload with real capabilities -> Sửa & Xóa are visible; then simulate 403 on PATCH -> refreshes capabilities while keeping form data
    page.reload()
    open_tournament(page, str(tournament_id), tournament_name)
    match_card = page.locator(f'[data-testid="match-card-{match_id}"]')
    expect(match_card.get_by_role("button", name="Sửa")).to_be_visible()
    match_card.get_by_role("button", name="Sửa").click()

    edit_form = page.locator(f'[data-testid="match-edit-form-{match_id}"]')
    expect(edit_form).to_be_visible()
    edit_form.locator('input[name="round_no"]').fill("5")

    match_patch_url = f"**/api/v1/tournaments/{tournament_id}/matches/{match_id}"
    revoked_cap = {
        "match_id": match_id,
        "can_update": False,
        "can_delete": False,
        "can_start": False,
        "can_submit_result": False,
        "can_cancel": False,
        "editable_fields": [],
    }
    page.route(
        match_patch_url,
        lambda route: route.fulfill(
            status=403,
            content_type="application/json",
            body=json.dumps({"detail": "Quyền chỉnh sửa trận đấu đã bị thu hồi."}),
        )
        if route.request.method == "PATCH"
        else route.continue_(),
    )
    page.route(
        match_cap_url,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(revoked_cap),
        ),
    )
    try:
        edit_form.get_by_role("button", name="Lưu").click()
        # Form stays open with error message and user's entered round_no ("5") preserved
        expect(edit_form).to_be_visible()
        expect(edit_form.locator(".error-banner")).to_contain_text("Quyền chỉnh sửa trận đấu đã bị thu hồi.")
        expect(edit_form.locator('input[name="round_no"]')).to_have_value("5")

        # After closing the edit form, refreshed capabilities hide Sửa and Xóa buttons
        edit_form.get_by_role("button", name="Hủy").click()
        expect(match_card.get_by_role("button", name="Sửa")).to_have_count(0)
        expect(match_card.get_by_role("button", name="Xóa")).to_have_count(0)
    finally:
        page.unroute(match_patch_url)
        page.unroute(match_cap_url)


def test_match_list_preserved_after_logout(
    page: Page, browser: Browser, app_base_url: str, api_base_url: str, demo_password: str
):
    ctx = _setup_locked_tournament_with_two_teams(page, api_base_url, demo_password)
    tournament_id = ctx["tournament_id"]
    tournament_name = ctx["tournament_name"]
    organizer_token = ctx["organizer_token"]
    stage_1 = ctx["stage_1"]
    team_1 = ctx["team_1"]
    team_2 = ctx["team_2"]

    created_match = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/matches",
        token=organizer_token,
        data={
            "stage_id": stage_1["stage_id"],
            "round_no": 1,
            "team1_id": team_1["team_id"],
            "team2_id": team_2["team_id"],
            "scheduled_at": "2026-11-20T09:00:00Z",
        },
    )
    match_id = created_match["match_id"]

    # Open tournament while logged in as organizer
    open_tournament(page, str(tournament_id), tournament_name)
    matches_section = page.locator('[data-testid="tournament-matches-section"]')
    match_card = matches_section.locator(f'[data-testid="match-card-{match_id}"]')
    expect(match_card).to_be_visible()
    expect(matches_section.get_by_role("button", name="+ Tạo trận đấu")).to_be_visible()
    expect(match_card.get_by_role("button", name="Sửa")).to_be_visible()

    # Log out while viewing the tournament detail
    page.get_by_role("button", name="Đăng xuất").click()
    # Close auth modal if it opened on logout
    close_modal_btn = page.locator(".auth-modal-close")
    if close_modal_btn.is_visible():
        close_modal_btn.click()

    # Public match list MUST remain visible after logout, while management buttons are hidden
    expect(matches_section).to_contain_text("Trận đấu & Lịch thi đấu (1)")
    expect(match_card).to_be_visible()
    expect(match_card).to_contain_text(team_1["name"])
    expect(match_card).to_contain_text(team_2["name"])
    expect(matches_section.locator('[data-testid="matches-empty-state"]')).to_have_count(0)
    expect(matches_section.get_by_role("button", name="+ Tạo trận đấu")).to_have_count(0)
    expect(match_card.get_by_role("button", name="Sửa")).to_have_count(0)
    expect(match_card.get_by_role("button", name="Xóa")).to_have_count(0)
