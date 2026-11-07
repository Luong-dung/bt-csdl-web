import json
import re
from datetime import date, timedelta

from playwright.sync_api import Browser, Page, expect

from database_support import assign_tournament_referee
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
            "real_name": f"Match UI {username}",
            "password": password,
        },
    )
    auth = _api_request(
        page,
        "POST",
        f"{api_base_url}/auth/login",
        data={"username": username, "password": password},
    )
    return {"user_id": user["user_id"], "username": username}, auth["access_token"]


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
        teams.append(
            {
                **team,
                "mgr_token": mgr_token,
                "plr_user_id": plr_user["user_id"],
            }
        )

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
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
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
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
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
    page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
    expect(page.locator(".auth-modal-close")).to_be_visible()
    page.locator(".auth-modal-close").click()

    # Public match list MUST remain visible after logout, while management buttons are hidden
    expect(matches_section).to_contain_text("Trận đấu & Lịch thi đấu (1)")
    expect(match_card).to_be_visible()
    expect(match_card).to_contain_text(team_1["name"])
    expect(match_card).to_contain_text(team_2["name"])
    expect(matches_section.locator('[data-testid="matches-empty-state"]')).to_have_count(0)
    expect(matches_section.get_by_role("button", name="+ Tạo trận đấu")).to_have_count(0)
    expect(match_card.get_by_role("button", name="Sửa")).to_have_count(0)
    expect(match_card.get_by_role("button", name="Xóa")).to_have_count(0)


def test_match_lifecycle_start_cancel_and_result_submission_ui(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_locked_tournament_with_two_teams(page, api_base_url, demo_password)
    tournament_id = ctx["tournament_id"]
    tournament_name = ctx["tournament_name"]
    organizer_token = ctx["organizer_token"]
    stage_1 = ctx["stage_1"]
    stage_2 = ctx["stage_2"]
    team_1 = ctx["team_1"]
    team_2 = ctx["team_2"]

    match_1 = _api_request(
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
    match_2 = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/matches",
        token=organizer_token,
        data={
            "stage_id": stage_1["stage_id"],
            "round_no": 2,
            "team1_id": team_1["team_id"],
            "team2_id": team_2["team_id"],
        },
    )
    m1_id = match_1["match_id"]
    m2_id = match_2["match_id"]

    open_tournament(page, str(tournament_id), tournament_name)
    matches_section = page.locator('[data-testid="tournament-matches-section"]')
    card_1 = matches_section.locator(f'[data-testid="match-card-{m1_id}"]')
    card_2 = matches_section.locator(f'[data-testid="match-card-{m2_id}"]')

    # While tournament is UPCOMING, Bắt đầu and Nhập kết quả are not shown, but Hủy trận is available
    expect(card_1.locator(f'[data-testid="match-start-btn-{m1_id}"]')).to_have_count(0)
    expect(card_1.locator(f'[data-testid="match-result-btn-{m1_id}"]')).to_have_count(0)
    expect(card_1.locator(f'[data-testid="match-cancel-btn-{m1_id}"]')).to_be_visible()

    # Transition tournament to ONGOING via UI
    page.locator(".manage-panel .status-actions").get_by_role("button", name=re.compile("ONGOING")).click()
    expect(page.locator(".tournament-detail .detail-stats")).to_contain_text("ONGOING")

    # Now Bắt đầu is visible on PENDING matches
    expect(card_1.locator(f'[data-testid="match-start-btn-{m1_id}"]')).to_be_visible()
    expect(card_2.locator(f'[data-testid="match-start-btn-{m2_id}"]')).to_be_visible()

    # 1. Cancel match_2 via UI
    page.once("dialog", lambda dialog: dialog.accept())
    card_2.locator(f'[data-testid="match-cancel-btn-{m2_id}"]').click()
    expect(matches_section.locator(".notice-banner")).to_contain_text("Đã hủy trận đấu.")
    expect(card_2.locator(".match-status-badge")).to_have_text("CANCELLED")
    expect(card_2.locator(f'[data-testid="match-actions-{m2_id}"]')).to_have_count(0)

    # 2. Start match_1 via UI
    card_1.locator(f'[data-testid="match-start-btn-{m1_id}"]').click()
    expect(matches_section.locator(".notice-banner")).to_contain_text("Đã bắt đầu trận đấu.")
    expect(card_1.locator(".match-status-badge")).to_have_text("ONGOING")
    expect(card_1.locator(f'[data-testid="match-edit-btn-{m1_id}"]')).to_have_count(0)
    expect(card_1.locator(f'[data-testid="match-delete-btn-{m1_id}"]')).to_have_count(0)
    expect(card_1.locator(f'[data-testid="match-result-btn-{m1_id}"]')).to_be_visible()

    # 3. Open result form on match_1, verify draw warning & winner preview
    card_1.locator(f'[data-testid="match-result-btn-{m1_id}"]').click()
    result_form = card_1.locator(f'[data-testid="match-result-form-{m1_id}"]')
    expect(result_form).to_be_visible()

    result_form.locator('input[name="score_team1"]').fill("1")
    result_form.locator('input[name="score_team2"]').fill("1")
    preview = result_form.locator(f'[data-testid="match-result-winner-preview-{m1_id}"]')
    expect(preview).to_contain_text("W45 không hỗ trợ kết quả hòa")

    result_form.locator('input[name="score_team1"]').fill("2")
    result_form.locator('input[name="score_team2"]').fill("1")
    expect(preview).to_contain_text(f"Xác nhận đội thắng: 🏆 {team_1['name']} (2 - 1)")

    # Simulate another user saving a different result (0 - 2) in the background before submitting
    _api_request(
        page,
        "PUT",
        f"{api_base_url}/tournaments/{tournament_id}/matches/{m1_id}/result",
        token=organizer_token,
        data={"score_team1": 0, "score_team2": 2},
    )

    # Submitting 2 - 1 now triggers 409; form stays open with inputs preserved while match row refreshes to 0 - 2
    result_form.get_by_role("button", name="Xác nhận & Lưu kết quả").click()
    expect(result_form).to_be_visible()
    expect(result_form.locator(f'[data-testid="match-result-error-{m1_id}"]')).to_be_visible()
    expect(result_form.locator('input[name="score_team1"]')).to_have_value("2")
    expect(result_form.locator('input[name="score_team2"]')).to_have_value("1")
    expect(card_1.locator(".match-status-badge")).to_have_text("COMPLETED")
    expect(card_1.locator(f'[data-testid="match-score-{m1_id}"]')).to_have_text("0 - 2")
    expect(card_1.locator(".team-right")).to_contain_text("🏆 Thắng")

    result_form.get_by_role("button", name="Hủy").click()
    expect(result_form).to_have_count(0)

    # 4. Create match_3, start it, and submit result normally via UI, then verify persistence after reload
    match_3 = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/matches",
        token=organizer_token,
        data={
            "stage_id": stage_2["stage_id"],
            "round_no": 1,
            "team1_id": team_1["team_id"],
            "team2_id": team_2["team_id"],
        },
    )
    m3_id = match_3["match_id"]
    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tournament_id), tournament_name)

    card_3 = page.locator(f'[data-testid="match-card-{m3_id}"]')
    card_3.locator(f'[data-testid="match-start-btn-{m3_id}"]').click()
    expect(card_3.locator(".match-status-badge")).to_have_text("ONGOING")

    card_3.locator(f'[data-testid="match-result-btn-{m3_id}"]').click()
    form_3 = card_3.locator(f'[data-testid="match-result-form-{m3_id}"]')
    form_3.locator('input[name="score_team1"]').fill("3")
    form_3.locator('input[name="score_team2"]').fill("1")
    expect(form_3.locator(f'[data-testid="match-result-winner-preview-{m3_id}"]')).to_contain_text(
        f"Xác nhận đội thắng: 🏆 {team_1['name']} (3 - 1)"
    )
    form_3.get_by_role("button", name="Xác nhận & Lưu kết quả").click()

    expect(page.locator('[data-testid="tournament-matches-section"] .notice-banner')).to_contain_text(
        "Đã ghi nhận kết quả trận đấu thành công."
    )
    expect(card_3.locator(".match-status-badge")).to_have_text("COMPLETED")
    expect(card_3.locator(f'[data-testid="match-score-{m3_id}"]')).to_have_text("3 - 1")
    expect(card_3.locator(".team-left")).to_contain_text("🏆 Thắng")

    # Reload and verify result persists
    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tournament_id), tournament_name)
    card_3_after = page.locator(f'[data-testid="match-card-{m3_id}"]')
    expect(card_3_after.locator(".match-status-badge")).to_have_text("COMPLETED")
    expect(card_3_after.locator(f'[data-testid="match-score-{m3_id}"]')).to_have_text("3 - 1")
    expect(card_3_after.locator(".team-left")).to_contain_text("🏆 Thắng")


def test_scoped_referee_match_operations_ui(
    page: Page, browser: Browser, app_base_url: str, api_base_url: str, demo_password: str
):
    ctx_a = _setup_locked_tournament_with_two_teams(page, api_base_url, demo_password)
    tour_a_id = ctx_a["tournament_id"]
    tour_a_name = ctx_a["tournament_name"]
    organizer_token = ctx_a["organizer_token"]

    # Create a second tournament (Tournament B) that is also locked and ONGOING with a PENDING match
    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")
    tour_b_name = f"Match UI Other Tour {unique_username('b-tour')[-8:]}"
    tour_b = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=organizer_token,
        data={
            "name": tour_b_name,
            "game_id": game_id,
            "format": "SINGLE_ELIM",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    tour_b_id = tour_b["tournament_id"]
    stage_b = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tour_b_id}/stages",
        token=organizer_token,
        data={"name": "Vòng 1", "sequence_order": 1},
    )
    for tm in (ctx_a["team_1"], ctx_a["team_2"]):
        reg = _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tour_b_id}/registrations",
            token=tm["mgr_token"],
            data={"team_id": tm["team_id"]},
        )
        _api_request(
            page,
            "POST",
            f"{api_base_url}/tournaments/{tour_b_id}/registrations/{reg['registration_id']}/decision",
            token=organizer_token,
            data={"status": "APPROVED"},
        )
        _api_request(
            page,
            "PUT",
            f"{api_base_url}/tournaments/{tour_b_id}/teams/{tm['team_id']}/roster",
            token=tm["mgr_token"],
            data={"members": [{"user_id": tm["plr_user_id"], "role_in_team": "PLAYER"}]},
        )

    _api_request(page, "POST", f"{api_base_url}/tournaments/{tour_b_id}/roster-lock", token=organizer_token)

    # Transition both Tournament A and Tournament B to ONGOING and create a PENDING match in each
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tour_a_id}/status",
        token=organizer_token,
        data={"status": "ONGOING"},
    )
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tour_b_id}/status",
        token=organizer_token,
        data={"status": "ONGOING"},
    )
    match_a = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tour_a_id}/matches",
        token=organizer_token,
        data={
            "stage_id": ctx_a["stage_1"]["stage_id"],
            "round_no": 1,
            "team1_id": ctx_a["team_1"]["team_id"],
            "team2_id": ctx_a["team_2"]["team_id"],
        },
    )
    match_b = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tour_b_id}/matches",
        token=organizer_token,
        data={
            "stage_id": stage_b["stage_id"],
            "round_no": 1,
            "team1_id": ctx_a["team_1"]["team_id"],
            "team2_id": ctx_a["team_2"]["team_id"],
        },
    )

    # Register a new user and assign tournament-scoped REFEREE ONLY on Tournament A
    ref_user, _ref_tok = _register_and_login_api(page, api_base_url, "referee", demo_password)
    assign_tournament_referee(ref_user["username"], tour_a_id)

    ref_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    ref_page.set_default_timeout(10_000)
    try:
        ref_page.goto(app_base_url)
        login(ref_page, ref_user["username"], demo_password)

        # 1. In Tournament B (not assigned), referee sees NO match management or referee controls
        open_tournament(ref_page, str(tour_b_id), tour_b_name)
        card_b = ref_page.locator(f'[data-testid="match-card-{match_b["match_id"]}"]')
        expect(card_b).to_be_visible()
        expect(ref_page.locator('[data-testid="tournament-matches-section"]').get_by_role("button", name="+ Tạo trận đấu")).to_have_count(0)
        expect(card_b.locator(f'[data-testid="match-actions-{match_b["match_id"]}"]')).to_have_count(0)

        # 2. In Tournament A (assigned), referee sees Bắt đầu (and NOT + Tạo trận đấu, Sửa, Hủy trận, Xóa)
        ref_page.reload()
        expect(ref_page.locator(".profile")).to_contain_text(ref_user["username"])
        open_tournament(ref_page, str(tour_a_id), tour_a_name)
        ma_id = match_a["match_id"]
        card_a = ref_page.locator(f'[data-testid="match-card-{ma_id}"]')
        expect(card_a).to_be_visible()
        expect(ref_page.locator('[data-testid="tournament-matches-section"]').get_by_role("button", name="+ Tạo trận đấu")).to_have_count(0)
        expect(card_a.locator(f'[data-testid="match-edit-btn-{ma_id}"]')).to_have_count(0)
        expect(card_a.locator(f'[data-testid="match-delete-btn-{ma_id}"]')).to_have_count(0)
        expect(card_a.locator(f'[data-testid="match-cancel-btn-{ma_id}"]')).to_have_count(0)
        expect(card_a.locator(f'[data-testid="match-start-btn-{ma_id}"]')).to_be_visible()

        # Referee starts match_a and submits result
        card_a.locator(f'[data-testid="match-start-btn-{ma_id}"]').click()
        expect(card_a.locator(".match-status-badge")).to_have_text("ONGOING")
        expect(card_a.locator(f'[data-testid="match-cancel-btn-{ma_id}"]')).to_have_count(0)
        expect(card_a.locator(f'[data-testid="match-result-btn-{ma_id}"]')).to_be_visible()

        card_a.locator(f'[data-testid="match-result-btn-{ma_id}"]').click()
        r_form = card_a.locator(f'[data-testid="match-result-form-{ma_id}"]')
        r_form.locator('input[name="score_team1"]').fill("2")
        r_form.locator('input[name="score_team2"]').fill("0")
        r_form.get_by_role("button", name="Xác nhận & Lưu kết quả").click()

        expect(card_a.locator(".match-status-badge")).to_have_text("COMPLETED")
        expect(card_a.locator(f'[data-testid="match-score-{ma_id}"]')).to_have_text("2 - 0")
    finally:
        ref_page.close()


def test_retry_tournament_capabilities_loads_player_roster_badge(
    page: Page, api_base_url: str, demo_password: str
):
    login(page, "demo_organizer", demo_password)
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    tournament_name = f"Retry Roster Badge {unique_username('r-badge')[-8:]}"
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

    _mgr_user, mgr_token = _register_and_login_api(page, api_base_url, "rbmgr", demo_password)
    plr_user, _plr_token = _register_and_login_api(page, api_base_url, "rbplr", demo_password)
    team = _api_request(
        page,
        "POST",
        f"{api_base_url}/teams",
        token=mgr_token,
        data={
            "name": f"Retry Team {unique_username('rtm')[-5:]}",
            "tag": f"RB{unique_username('rbg')[-5:]}".upper()[:10],
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

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")

    # Simulate initial failure on tournament capabilities when opening the tournament
    cap_url = f"**/api/v1/tournaments/{tournament_id}/capabilities"
    fail_once = {"should_fail": True}

    def handle_cap_route(route):
        if fail_once["should_fail"]:
            fail_once["should_fail"] = False
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "Lỗi mạng tạm thời khi tải quyền giải đấu."}),
            )
        else:
            route.continue_()

    page.route(cap_url, handle_cap_route)
    try:
        open_tournament(page, str(tournament_id), tournament_name)
        team_card = page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        expect(team_card).to_be_visible()
        # Because initial capabilities failed, PLAYER badge is not loaded yet and capability error banner is visible
        cap_error_banner = page.locator('[data-testid="capability-error-banner"]')
        expect(cap_error_banner).to_be_visible()
        expect(team_card.locator(".status-badge.ready")).to_have_count(0)

        # Click "Thử lại" -> capabilities load AND PLAYER readiness badge ("Đã có PLAYER") is loaded!
        cap_error_banner.get_by_role("button", name=re.compile("Thử lại|Retry")).click()
        expect(cap_error_banner).to_have_count(0)
        expect(team_card.locator(".status-badge.ready")).to_have_text("Đã có PLAYER")
    finally:
        page.unroute(cap_url)

    # Also verify reloadTournamentDetailsData ("Thử lại" in registrations section when both capabilities and registrations fail)
    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    reg_url = f"**/api/v1/tournaments/{tournament_id}/registrations*"
    fail_reload = {"cap": True, "reg": True}

    def handle_cap_reload(route):
        if fail_reload["cap"]:
            fail_reload["cap"] = False
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "Lỗi tải quyền giải đấu."}),
            )
        else:
            route.continue_()

    def handle_reg_reload(route):
        if fail_reload["reg"]:
            fail_reload["reg"] = False
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "Lỗi tải danh sách đơn đăng ký."}),
            )
        else:
            route.continue_()

    page.route(cap_url, handle_cap_reload)
    page.route(reg_url, handle_reg_reload)
    try:
        open_tournament(page, str(tournament_id), tournament_name)
        team_card = page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        expect(team_card).to_be_visible()
        expect(team_card.locator(".status-badge.ready")).to_have_count(0)

        reg_error_banner = page.locator(".registrations-section .error-banner")
        expect(reg_error_banner).to_be_visible()
        reg_error_banner.get_by_role("button", name=re.compile("Thử lại|Retry")).click()

        expect(reg_error_banner).to_have_count(0)
        expect(team_card.locator(".status-badge.ready")).to_have_text("Đã có PLAYER")
    finally:
        page.unroute(cap_url)
        page.unroute(reg_url)


