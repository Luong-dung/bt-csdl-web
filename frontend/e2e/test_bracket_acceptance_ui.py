"""W46-08 Browser E2E: Final Acceptance Suite for Knockout Brackets.

Validates end-to-end user workflows using real browser and APIs:
1. Full tournament bracket lifecycle:
   - Creation by organizer
   - Scoped referee permissions (start, result submission, slot advancement)
   - Foreign referee isolation (no start/result capabilities)
   - Public viewer standings persistence across page reload
2. Preview expiration handling & Double submit protection:
   - Expired/invalid preview token displays clear error banner and preserves form input
   - Double-submit guard prevents multiple concurrent creation submissions
3. In-flight tournament switching & Stale response protection:
   - In-flight bracket/standings request does not pollute switched tournament
   - CANCELLED tournament displays historical status and preserved eliminated ranks
4. Large 64-team bracket visualization & Mobile responsiveness:
   - 64-team bracket tree renders all 6 rounds and 63 matches
   - Standings pagination reflects full 64 teams (X-Total-Count: 64)
   - Mobile 390px viewport check confirms no horizontal page overflow
"""
import re
from datetime import date, timedelta

from playwright.sync_api import Page, expect

from database_support import assign_tournament_referee, seed_bracket_fast_teams
from helpers import login, register_user, unique_username
from test_bracket_create_ui import _setup_bracket_tournament
from test_bracket_view_ui import _create_bracket_via_api
from test_matches_ui import _api_request
from test_tournaments import open_tournament


def test_bracket_full_lifecycle_referee_matrix_and_reload(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    # 1. Setup a tournament with 4 teams and locked roster
    ctx = _setup_bracket_tournament(
        page,
        api_base_url,
        demo_password,
        team_count=4,
        stage_names=("Playoffs",),
        lock_roster=True,
    )
    tid = ctx["tournament_id"]
    tname = ctx["tournament_name"]
    token = ctx["organizer_token"]
    stage_id = ctx["stages"][0]["stage_id"]
    teams = ctx["teams"]
    team_ids = [t["team_id"] for t in teams]

    # Setup another tournament for foreign referee
    other_ctx = _setup_bracket_tournament(
        page,
        api_base_url,
        demo_password,
        team_count=2,
        stage_names=("Other Stage",),
        lock_roster=True,
    )
    other_tid = other_ctx["tournament_id"]

    # 2. Register Scoped Referee and Foreign Referee
    ref_scoped_name = unique_username("ref-scoped")
    ref_foreign_name = unique_username("ref-foreign")

    reg_page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        reg_page.goto(app_base_url)
        register_user(reg_page, ref_scoped_name, demo_password)
        register_user(reg_page, ref_foreign_name, demo_password)
    finally:
        reg_page.close()

    assign_tournament_referee(ref_scoped_name, tid)
    assign_tournament_referee(ref_foreign_name, other_tid)

    # 3. Organizer creates bracket in UI
    open_tournament(page, str(tid), tname)
    create_section = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(create_section).to_be_visible()
    create_section.locator('[data-testid="bracket-preview-btn"]').click()
    expect(create_section.locator('[data-testid="bracket-preview-panel"]')).to_be_visible()
    create_section.locator('[data-testid="bracket-create-confirm-btn"]').click()
    expect(create_section.locator('[data-testid="bracket-notice-banner"]')).to_contain_text(
        "Đã tạo bracket thành công"
    )

    # Transition tournament to ONGOING via API
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/status",
        token=token,
        data={"status": "ONGOING"},
    )

    bracket_info = _api_request(page, "GET", f"{api_base_url}/tournaments/{tid}/bracket")
    matches = bracket_info["matches"]
    m1_id = matches[0]["match"]["match_id"]
    m2_id = matches[1]["match"]["match_id"]
    m3_id = matches[2]["match"]["match_id"]

    # 4. Login as Scoped Referee and coordinate matches
    scoped_page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        scoped_page.goto(app_base_url)
        login(scoped_page, ref_scoped_name, demo_password)
        open_tournament(scoped_page, str(tid), tname)

        bracket_sec = scoped_page.locator('[data-testid="tournament-bracket-section"]')
        expect(bracket_sec).to_be_visible()

        # Scoped referee cannot create bracket or reschedule matches on pending nodes
        expect(scoped_page.locator('[data-testid="tournament-bracket-create-section"]')).to_have_count(0)
        expect(bracket_sec.locator('[data-testid^="bracket-schedule-btn-"]')).to_have_count(0)

        # Semifinal 1: Start (transitions from PENDING to ONGOING)
        node1 = bracket_sec.locator(f'[data-testid="bracket-node-{m1_id}"]')
        expect(node1.locator(f'[data-testid="bracket-start-btn-{m1_id}"]')).to_be_visible()
        node1.locator(f'[data-testid="bracket-start-btn-{m1_id}"]').click()
        expect(node1.locator(f'[data-testid="bracket-node-status-{m1_id}"]')).to_have_text("ONGOING")

        # 5. Login as Foreign Referee while m1 is ONGOING and m2 is PENDING
        # Verify Foreign Referee has no start, result, schedule, or creation capabilities
        foreign_page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            foreign_page.goto(app_base_url)
            login(foreign_page, ref_foreign_name, demo_password)
            open_tournament(foreign_page, str(tid), tname)

            f_bracket_sec = foreign_page.locator('[data-testid="tournament-bracket-section"]')
            expect(f_bracket_sec).to_be_visible()
            expect(foreign_page.locator('[data-testid="tournament-bracket-create-section"]')).to_have_count(0)
            expect(f_bracket_sec.locator('[data-testid^="bracket-start-btn-"]')).to_have_count(0)
            expect(f_bracket_sec.locator('[data-testid^="bracket-result-btn-"]')).to_have_count(0)
            expect(f_bracket_sec.locator('[data-testid^="bracket-schedule-btn-"]')).to_have_count(0)
        finally:
            foreign_page.close()

        # Semifinal 1: Submit Result (Team 0 beats Team 1: 2 - 0)
        node1.locator(f'[data-testid="bracket-result-btn-{m1_id}"]').click()
        res_form1 = node1.locator(f'[data-testid="bracket-result-form-{m1_id}"]')
        res_form1.locator('input[name="score_team1"]').fill("2")
        res_form1.locator('input[name="score_team2"]').fill("0")
        res_form1.get_by_role("button", name="Xác nhận & Lưu kết quả").click()
        expect(node1.locator(f'[data-testid="bracket-node-status-{m1_id}"]')).to_have_text("COMPLETED")

        # Verify winner Team 0 moved into Final slot 1
        node3 = bracket_sec.locator(f'[data-testid="bracket-node-{m3_id}"]')
        expect(node3.locator(f'[data-testid="bracket-node-slot1-{m3_id}"]')).to_contain_text(teams[0]["name"])

        # Semifinal 2: Start and Submit Result (Team 3 beats Team 2: 1 - 3)
        node2 = bracket_sec.locator(f'[data-testid="bracket-node-{m2_id}"]')
        node2.locator(f'[data-testid="bracket-start-btn-{m2_id}"]').click()
        expect(node2.locator(f'[data-testid="bracket-node-status-{m2_id}"]')).to_have_text("ONGOING")

        node2.locator(f'[data-testid="bracket-result-btn-{m2_id}"]').click()
        res_form2 = node2.locator(f'[data-testid="bracket-result-form-{m2_id}"]')
        res_form2.locator('input[name="score_team1"]').fill("1")
        res_form2.locator('input[name="score_team2"]').fill("3")
        res_form2.get_by_role("button", name="Xác nhận & Lưu kết quả").click()
        expect(node2.locator(f'[data-testid="bracket-node-status-{m2_id}"]')).to_have_text("COMPLETED")

        # Verify winner Team 3 moved into Final slot 2
        expect(node3.locator(f'[data-testid="bracket-node-slot2-{m3_id}"]')).to_contain_text(teams[3]["name"])

        # Final Match: Now ready to start
        expect(node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]')).to_be_visible()
        node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]').click()
        expect(node3.locator(f'[data-testid="bracket-node-status-{m3_id}"]')).to_have_text("ONGOING")

        node3.locator(f'[data-testid="bracket-result-btn-{m3_id}"]').click()
        res_form3 = node3.locator(f'[data-testid="bracket-result-form-{m3_id}"]')
        res_form3.locator('input[name="score_team1"]').fill("3")
        res_form3.locator('input[name="score_team2"]').fill("1")
        res_form3.get_by_role("button", name="Xác nhận & Lưu kết quả").click()
        expect(node3.locator(f'[data-testid="bracket-node-status-{m3_id}"]')).to_have_text("COMPLETED")

        # Verify Standings became FINAL
        standings = bracket_sec.locator('[data-testid="bracket-standings-panel"]')
        expect(standings.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text(
            "Chính thức"
        )
        expect(standings.locator(f'[data-testid="bracket-standing-rank-{teams[0]["team_id"]}"]')).to_contain_text(
            "#1 (Vô địch)"
        )
        expect(standings.locator(f'[data-testid="bracket-standing-rank-{teams[3]["team_id"]}"]')).to_contain_text(
            "#2"
        )
    finally:
        scoped_page.close()

    # 6. Public viewer (unauthenticated) persistence across page reload
    page.reload()
    page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
    expect(page.locator(".auth-modal-close")).to_be_visible()
    page.locator(".auth-modal-close").click()

    open_tournament(page, str(tid), tname)
    public_sec = page.locator('[data-testid="tournament-bracket-section"]')
    expect(public_sec).to_be_visible()
    expect(public_sec.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text("Chính thức")
    expect(public_sec.locator(f'[data-testid="bracket-standing-rank-{teams[0]["team_id"]}"]')).to_contain_text(
        "#1 (Vô địch)"
    )


def test_bracket_preview_expiry_and_double_submit_protection(
    page: Page, api_base_url: str, demo_password: str
):
    ctx = _setup_bracket_tournament(page, api_base_url, demo_password, team_count=4)
    tid = ctx["tournament_id"]
    tname = ctx["tournament_name"]
    stages = ctx["stages"]
    teams = ctx["teams"]

    open_tournament(page, str(tid), tname)
    section = page.locator('[data-testid="tournament-bracket-create-section"]')
    expect(section).to_be_visible()

    # Move team 0 down
    section.locator(f'[data-testid="bracket-team-down-{teams[0]["team_id"]}"]').click()
    section.locator('[data-testid="bracket-stage-select"]').select_option(str(stages[1]["stage_id"]))

    # 1. Preview with tampered token to test REAL backend 409 error response
    preview_url = f"**/api/v1/tournaments/{tid}/bracket/preview"

    def tamper_preview_token(route):
        response = route.fetch()
        data = response.json()
        # Tamper last character of preview_token so backend verify_preview_token raises real 409
        old_tok = data["preview_token"]
        data["preview_token"] = old_tok[:-1] + ("x" if old_tok[-1] != "x" else "y")
        route.fulfill(response=response, json=data)

    page.route(preview_url, tamper_preview_token)
    try:
        section.locator('[data-testid="bracket-preview-btn"]').click()
        preview_panel = section.locator('[data-testid="bracket-preview-panel"]')
        expect(preview_panel).to_be_visible()
        expect(preview_panel.locator('[data-testid="bracket-preview-expiry"]')).to_be_visible()
    finally:
        page.unroute(preview_url, tamper_preview_token)

    # Click confirm: real backend receives tampered token and responds with REAL 409
    with page.expect_response(
        lambda r: f"/tournaments/{tid}/bracket" in r.url and r.request.method == "POST"
    ) as resp_info:
        section.locator('[data-testid="bracket-create-confirm-btn"]').click()
    assert resp_info.value.status == 409
    expect(section.locator('[data-testid="bracket-error-banner"]')).to_contain_text(
        "Preview hết hạn hoặc không hợp lệ"
    )
    # Input preserved: stage and team order remain as selected
    expect(section.locator('[data-testid="bracket-stage-select"]')).to_have_value(str(stages[1]["stage_id"]))
    first_row = section.locator('[data-testid="bracket-team-order-list"] li').first
    expect(first_row).to_contain_text(teams[1]["name"])

    # 2. Re-click preview to obtain a fresh, valid preview token from backend
    with page.expect_response(
        lambda r: f"/tournaments/{tid}/bracket/preview" in r.url and r.request.method == "POST"
    ):
        section.locator('[data-testid="bracket-preview-btn"]').click()
    preview_panel = section.locator('[data-testid="bracket-preview-panel"]')
    expect(preview_panel).to_be_visible()

    # Double submit protection check: button disables while creation is pending
    creation_requests = []

    def hold_create(route):
        if route.request.method == "POST":
            creation_requests.append(route)
        else:
            route.continue_()

    bracket_url = f"**/api/v1/tournaments/{tid}/bracket"
    page.route(bracket_url, hold_create)
    try:
        confirm_btn = section.locator('[data-testid="bracket-create-confirm-btn"]')
        confirm_btn.click()
        for _ in range(50):
            if len(creation_requests) == 1:
                break
            page.wait_for_timeout(100)
        assert len(creation_requests) == 1, "Creation request did not reach held route"
        # Confirm button must be disabled during submission
        expect(confirm_btn).to_be_disabled()

        # Release the in-flight request to real backend
        route = creation_requests[0]
        route.continue_()
    finally:
        page.unroute(bracket_url, hold_create)

    # Assert creation succeeded on real backend and UI renders tree and notice
    expect(section.locator('[data-testid="bracket-notice-banner"]')).to_contain_text(
        "Đã tạo bracket thành công"
    )
    expect(page.locator('[data-testid="bracket-tree"]')).to_be_visible()
    assert len(creation_requests) == 1, "Expected exactly 1 creation request sent"


def test_bracket_in_flight_switch_anti_stale_and_cancelled_standings(
    page: Page, api_base_url: str, demo_password: str
):
    ctx_a = _setup_bracket_tournament(
        page, api_base_url, demo_password, team_count=4, stage_names=("Stage A",), lock_roster=True
    )
    ctx_b = _setup_bracket_tournament(
        page, api_base_url, demo_password, team_count=2, stage_names=("Stage B",), lock_roster=True
    )
    tid_a = ctx_a["tournament_id"]
    token = ctx_a["organizer_token"]
    teams_a = ctx_a["teams"]
    t0_id = teams_a[0]["team_id"]
    t1_id = teams_a[1]["team_id"]

    _create_bracket_via_api(
        page,
        api_base_url,
        token,
        tid_a,
        ctx_a["stages"][0]["stage_id"],
        [t["team_id"] for t in teams_a],
    )

    # Set Tournament A to ONGOING and complete Semifinal 1 (Team 0 beats Team 1: 2 - 0)
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid_a}/status",
        token=token,
        data={"status": "ONGOING"},
    )
    bracket_a = _api_request(page, "GET", f"{api_base_url}/tournaments/{tid_a}/bracket")
    semi1_id = bracket_a["matches"][0]["match"]["match_id"]
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid_a}/matches/{semi1_id}/status",
        token=token,
        data={"status": "ONGOING"},
    )
    _api_request(
        page,
        "PUT",
        f"{api_base_url}/tournaments/{tid_a}/matches/{semi1_id}/result",
        token=token,
        data={"score_team1": 2, "score_team2": 0},
    )

    open_tournament(page, str(tid_a), ctx_a["tournament_name"])
    sec_a = page.locator('[data-testid="tournament-bracket-section"]')
    expect(sec_a).to_be_visible()

    # --- Part 1: Tournament switch in-flight guard ---
    held_tourn = []
    bracket_url = f"**/api/v1/tournaments/{tid_a}/bracket"

    def hold_bracket(route):
        try:
            resp = route.fetch()
            held_tourn.append((route, resp))
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    page.route(bracket_url, hold_bracket)
    try:
        sec_a.locator('[data-testid="bracket-reload-btn"]').click()
        for _ in range(50):
            if len(held_tourn) >= 1:
                break
            page.wait_for_timeout(100)
        assert len(held_tourn) >= 1

        # Switch to Tournament B
        page.locator(".tournament-detail .detail-header button").filter(
            has_text=re.compile("Đóng|Close")
        ).click()
        open_tournament(page, str(ctx_b["tournament_id"]), ctx_b["tournament_name"])

        # Unroute before fulfilling to avoid intercepting new requests
        page.unroute(bracket_url, hold_bracket)
        for r, resp in list(held_tourn):
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        held_tourn.clear()

        # Tournament B must show empty bracket view without contamination
        expect(page.locator(".tournament-detail h3")).to_have_text(ctx_b["tournament_name"])
        expect(page.locator('[data-testid="bracket-view-empty"]')).to_be_visible()
        expect(page.locator('[data-testid="bracket-tree"]')).to_have_count(0)
    finally:
        try:
            page.unroute(bracket_url, hold_bracket)
        except Exception:
            pass
        for r, resp in list(held_tourn):
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        held_tourn.clear()

    # --- Part 2: Session switch (logout) in-flight guard ---
    # Close Tournament B and reopen Tournament A as Organizer
    page.locator(".tournament-detail .detail-header button").filter(
        has_text=re.compile("Đóng|Close")
    ).click()
    open_tournament(page, str(tid_a), ctx_a["tournament_name"])
    expect(sec_a).to_be_visible()

    held_session = []

    def hold_session_request(route):
        try:
            resp = route.fetch()
            held_session.append((route, resp))
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    page.route(bracket_url, hold_session_request)
    try:
        sec_a.locator('[data-testid="bracket-reload-btn"]').click()
        for _ in range(50):
            if len(held_session) >= 1:
                break
            page.wait_for_timeout(100)
        assert len(held_session) >= 1

        # Logout while request is in-flight
        page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
        expect(page.locator(".auth-modal-close")).to_be_visible()
        page.locator(".auth-modal-close").click()

        # Unroute before fulfilling so no further public requests get held
        page.unroute(bracket_url, hold_session_request)
        for r, resp in list(held_session):
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        held_session.clear()

        # Public viewer interface must not be contaminated with old session capabilities
        expect(page.locator('[data-testid="tournament-bracket-create-section"]')).to_have_count(0)
        expect(page.locator('[data-testid^="bracket-schedule-btn-"]')).to_have_count(0)
        expect(page.locator(".profile")).to_have_count(0)
    finally:
        try:
            page.unroute(bracket_url, hold_session_request)
        except Exception:
            pass
        for r, resp in list(held_session):
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        held_session.clear()

    # --- Part 3: CANCELLED tournament with historical eliminated rank ---
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid_a}/status",
        token=token,
        data={"status": "CANCELLED"},
    )
    # Reload/reopen Tournament A as public viewer
    page.reload()
    open_tournament(page, str(tid_a), ctx_a["tournament_name"])
    expect(page.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text(
        "Đã hủy (Lịch sử)"
    )
    # Eliminated team 1 preserves historical rank #3 / Dừng bước (Hạng #3)
    expect(page.locator(f'[data-testid="bracket-standing-rank-{t1_id}"]')).to_contain_text("#3")
    expect(page.locator(f'[data-testid="bracket-standing-state-{t1_id}"]')).to_contain_text("Hạng #3")

    # Non-eliminated team 0 displays "Chưa xếp hạng" and "Giải đã hủy"
    expect(page.locator(f'[data-testid="bracket-standing-rank-{t0_id}"]')).to_contain_text("Chưa xếp hạng")
    expect(page.locator(f'[data-testid="bracket-standing-state-{t0_id}"]')).to_contain_text("Giải đã hủy")


def test_bracket_64_teams_tree_standings_and_mobile_responsive(
    page: Page, api_base_url: str, demo_password: str
):
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    if not organizer_token:
        login(page, "demo_organizer", demo_password)
        organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    tname = f"Bracket 64 E2E {unique_username('')[-6:]}"
    tournament = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=organizer_token,
        data={
            "name": tname,
            "game_id": game_id,
            "format": "SINGLE_ELIM",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    tid = tournament["tournament_id"]

    stage = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/stages",
        token=organizer_token,
        data={"name": "Playoffs 64", "sequence_order": 1},
    )
    stage_id = stage["stage_id"]

    # Seed 64 teams with approved registrations and locked roster
    team_ids = seed_bracket_fast_teams(tid, team_count=64)

    # Create bracket for 64 teams
    _create_bracket_via_api(page, api_base_url, organizer_token, tid, stage_id, team_ids)

    # Open tournament in UI
    page.reload()
    open_tournament(page, str(tid), tname)

    bracket_sec = page.locator('[data-testid="tournament-bracket-section"]')
    expect(bracket_sec).to_be_visible()

    # Tree renders all 6 rounds and 63 matches
    expect(bracket_sec.locator('[data-testid="bracket-tree"]')).to_be_visible()
    expect(bracket_sec.locator('.bracket-round-column')).to_have_count(6)
    expect(bracket_sec.locator('.bracket-node-card')).to_have_count(63)

    # Standings table reflects 64 teams
    standings_table = bracket_sec.locator('[data-testid="bracket-standings-table"]')
    expect(standings_table).to_be_visible()
    expect(bracket_sec.locator('[data-testid^="bracket-standing-row-"]')).to_have_count(64)

    # Mobile 390px viewport responsiveness test: page does not blow out horizontally
    page.set_viewport_size({"width": 390, "height": 844})
    has_page_overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not has_page_overflow, "Page has horizontal document overflow at 390px viewport"

    # Bracket scroll container is scrollable horizontally
    scroll_container = bracket_sec.locator('[data-testid="bracket-tree-scroll"]')
    expect(scroll_container).to_be_visible()
    is_scrollable = page.evaluate(
        "el => el.scrollWidth > el.clientWidth",
        scroll_container.element_handle(),
    )
    assert is_scrollable, "Bracket tree scroll container is not horizontally scrollable for 64 teams"
    page.set_viewport_size({"width": 1280, "height": 800})
