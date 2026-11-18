import re

from playwright.sync_api import Page, expect

from test_bracket_create_ui import _setup_bracket_tournament
from test_matches_ui import _api_request
from test_tournaments import open_tournament


def _create_bracket_via_api(
    page: Page,
    api_base_url: str,
    token: str,
    tournament_id: int,
    stage_id: int,
    team_ids: list[int],
) -> dict:
    preview = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/bracket/preview",
        token=token,
        data={"stage_id": stage_id, "team_ids": team_ids},
    )
    return _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tournament_id}/bracket",
        token=token,
        data={
            "stage_id": stage_id,
            "team_ids": team_ids,
            "preview_token": preview["preview_token"],
        },
    )


def test_bracket_tree_start_result_advancement_standings_and_390px(
    page: Page, api_base_url: str, demo_password: str
):
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

    bracket = _create_bracket_via_api(page, api_base_url, token, tid, stage_id, team_ids)
    nodes = bracket["matches"]
    assert len(nodes) == 3
    m1_id = nodes[0]["match"]["match_id"]
    m2_id = nodes[1]["match"]["match_id"]
    m3_id = nodes[2]["match"]["match_id"]

    # Transition tournament to ONGOING so matches can be started and scored
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/status",
        token=token,
        data={"status": "ONGOING"},
    )

    page.reload()
    open_tournament(page, str(tid), tname)

    section = page.locator('[data-testid="tournament-bracket-section"]')
    expect(section).to_be_visible()
    expect(section.locator('[data-testid="bracket-round-1"]')).to_be_visible()
    expect(section.locator('[data-testid="bracket-round-2"]')).to_be_visible()

    node1 = section.locator(f'[data-testid="bracket-node-{m1_id}"]')
    node2 = section.locator(f'[data-testid="bracket-node-{m2_id}"]')
    node3 = section.locator(f'[data-testid="bracket-node-{m3_id}"]')
    expect(node1).to_be_visible()
    expect(node2).to_be_visible()
    expect(node3).to_be_visible()

    # Check destination labels and TBD slots in Final (node3)
    expect(node1.locator(f'[data-testid="bracket-node-next-{m1_id}"]')).to_contain_text(
        f"Thắng vào Vòng 2 · Trận #1 (Slot 1, Trận ID #{m3_id})"
    )
    expect(node2.locator(f'[data-testid="bracket-node-next-{m2_id}"]')).to_contain_text(
        f"Thắng vào Vòng 2 · Trận #1 (Slot 2, Trận ID #{m3_id})"
    )
    expect(node3.locator(f'[data-testid="bracket-node-next-{m3_id}"]')).to_contain_text(
        "Trận chung kết tranh vô địch"
    )
    expect(node3.locator(f'[data-testid="bracket-node-tbd-1-{m3_id}"]')).to_be_visible()
    expect(node3.locator(f'[data-testid="bracket-node-tbd-2-{m3_id}"]')).to_be_visible()
    # Final match with TBD slots must NOT have a Start button
    expect(node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]')).to_have_count(0)

    # Initial standings: PROVISIONAL, all 4 teams "Đang thi đấu"
    standings_panel = section.locator('[data-testid="bracket-standings-panel"]')
    expect(standings_panel.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text(
        "Tạm thời (Đang thi đấu)"
    )
    for tm in teams:
        expect(
            standings_panel.locator(f'[data-testid="bracket-standing-rank-{tm["team_id"]}"]')
        ).to_contain_text("Đang thi đấu")

    # Update schedule on Match 1 directly inside the bracket node
    node1.locator(f'[data-testid="bracket-schedule-btn-{m1_id}"]').click()
    sched_form = node1.locator(f'[data-testid="bracket-schedule-form-{m1_id}"]')
    expect(sched_form).to_be_visible()
    sched_form.locator('input[name="scheduled_at"]').fill("2026-11-20T15:30")
    sched_form.get_by_role("button", name="Lưu lịch").click()
    expect(sched_form).to_have_count(0)
    expect(node1.locator(f'[data-testid="bracket-node-schedule-{m1_id}"]')).to_contain_text("2026")

    # Start Match 1 and submit result (Team 0 beats Team 1: 2 - 0)
    node1.locator(f'[data-testid="bracket-start-btn-{m1_id}"]').click()
    expect(node1.locator(f'[data-testid="bracket-node-status-{m1_id}"]')).to_have_text("ONGOING")

    node1.locator(f'[data-testid="bracket-result-btn-{m1_id}"]').click()
    res_form1 = node1.locator(f'[data-testid="bracket-result-form-{m1_id}"]')
    expect(res_form1).to_be_visible()
    res_form1.locator('input[name="score_team1"]').fill("2")
    res_form1.locator('input[name="score_team2"]').fill("0")
    expect(res_form1.locator(f'[data-testid="bracket-result-winner-preview-{m1_id}"]')).to_contain_text(
        teams[0]["name"]
    )
    res_form1.get_by_role("button", name="Xác nhận & Lưu kết quả").click()

    # Match 1 is COMPLETED, Team 0 advances to Final Slot 1, Slot 2 remains TBD, Start on Final still hidden
    expect(node1.locator(f'[data-testid="bracket-node-status-{m1_id}"]')).to_have_text("COMPLETED")
    expect(node1.locator(f'[data-testid="bracket-node-winner-{m1_id}"]')).to_be_visible()
    expect(node3.locator(f'[data-testid="bracket-node-slot1-{m3_id}"]')).to_contain_text(teams[0]["name"])
    expect(node3.locator(f'[data-testid="bracket-node-tbd-2-{m3_id}"]')).to_be_visible()
    expect(node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]')).to_have_count(0)

    # Start Match 2 and submit result (Team 3 beats Team 2: 1 - 3)
    node2.locator(f'[data-testid="bracket-start-btn-{m2_id}"]').click()
    expect(node2.locator(f'[data-testid="bracket-node-status-{m2_id}"]')).to_have_text("ONGOING")
    node2.locator(f'[data-testid="bracket-result-btn-{m2_id}"]').click()
    res_form2 = node2.locator(f'[data-testid="bracket-result-form-{m2_id}"]')
    res_form2.locator('input[name="score_team1"]').fill("1")
    res_form2.locator('input[name="score_team2"]').fill("3")
    res_form2.get_by_role("button", name="Xác nhận & Lưu kết quả").click()

    # Final now has both Team 0 (Slot 1) and Team 3 (Slot 2), so Start button appears on Final!
    expect(node3.locator(f'[data-testid="bracket-node-slot2-{m3_id}"]')).to_contain_text(teams[3]["name"])
    expect(node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]')).to_be_visible()

    # Both semifinal losers (Team 1 and Team 2) now show tied rank "Đồng hạng #3", while finalists are still "Đang thi đấu"
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[1]["team_id"]}"]')
    ).to_contain_text("Đồng hạng #3")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[2]["team_id"]}"]')
    ).to_contain_text("Đồng hạng #3")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[0]["team_id"]}"]')
    ).to_contain_text("Đang thi đấu")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[3]["team_id"]}"]')
    ).to_contain_text("Đang thi đấu")

    # Start Final Match and submit result (Team 0 beats Team 3: 3 - 2)
    node3.locator(f'[data-testid="bracket-start-btn-{m3_id}"]').click()
    expect(node3.locator(f'[data-testid="bracket-node-status-{m3_id}"]')).to_have_text("ONGOING")
    node3.locator(f'[data-testid="bracket-result-btn-{m3_id}"]').click()
    res_form3 = node3.locator(f'[data-testid="bracket-result-form-{m3_id}"]')
    res_form3.locator('input[name="score_team1"]').fill("3")
    res_form3.locator('input[name="score_team2"]').fill("2")
    res_form3.get_by_role("button", name="Xác nhận & Lưu kết quả").click()

    # Standings transition to FINAL with #1 Champion, #2 Runner-up, and tied #3
    expect(standings_panel.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text(
        "Chính thức (Đã chốt chung kết)"
    )
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[0]["team_id"]}"]')
    ).to_contain_text("#1 (Vô địch)")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[3]["team_id"]}"]')
    ).to_contain_text("#2 (Á quân)")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[1]["team_id"]}"]')
    ).to_contain_text("Đồng hạng #3")
    expect(
        standings_panel.locator(f'[data-testid="bracket-standing-rank-{teams[2]["team_id"]}"]')
    ).to_contain_text("Đồng hạng #3")

    # Check 390px mobile viewport: no horizontal page overflow
    page.set_viewport_size({"width": 390, "height": 844})
    has_overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not has_overflow, "Bracket & standings UI overflows horizontally at 390px viewport"

    # Reload page and verify persistence for public viewer (logged out)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.reload()
    page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
    expect(page.locator(".auth-modal-close")).to_be_visible()
    page.locator(".auth-modal-close").click()

    open_tournament(page, str(tid), tname)
    public_section = page.locator('[data-testid="tournament-bracket-section"]')
    expect(public_section).to_be_visible()
    expect(
        public_section.locator('[data-testid="bracket-standings-status-badge"]')
    ).to_contain_text("Chính thức (Đã chốt chung kết)")
    expect(
        public_section.locator(f'[data-testid="bracket-standing-rank-{teams[0]["team_id"]}"]')
    ).to_contain_text("#1 (Vô địch)")
    expect(public_section.locator(f'[data-testid="bracket-node-actions-{m3_id}"]')).to_have_count(0)


def test_bracket_view_stale_response_guard_and_cancelled_standings(
    page: Page, api_base_url: str, demo_password: str
):
    ctx_a = _setup_bracket_tournament(
        page, api_base_url, demo_password, team_count=2, stage_names=("Stage A",)
    )
    ctx_b = _setup_bracket_tournament(
        page, api_base_url, demo_password, team_count=2, stage_names=("Stage B",)
    )
    tid_a = ctx_a["tournament_id"]
    token = ctx_a["organizer_token"]
    _create_bracket_via_api(
        page,
        api_base_url,
        token,
        tid_a,
        ctx_a["stages"][0]["stage_id"],
        [t["team_id"] for t in ctx_a["teams"]],
    )
    # Cancel Tournament A to verify CANCELLED standings badge
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid_a}/status",
        token=token,
        data={"status": "CANCELLED"},
    )

    page.reload()
    open_tournament(page, str(tid_a), ctx_a["tournament_name"])
    section = page.locator('[data-testid="tournament-bracket-section"]')
    expect(section.locator('[data-testid="bracket-standings-status-badge"]')).to_contain_text(
        "Đã hủy (Lịch sử)"
    )

    # Hold reload of Tournament A bracket while switching to Tournament B (which has no bracket)
    held_responses = []
    bracket_url = f"**/api/v1/tournaments/{tid_a}/bracket"

    def hold_bracket(route):
        response = route.fetch()
        held_responses.append((route, response))

    page.route(bracket_url, hold_bracket)
    try:
        section.locator('[data-testid="bracket-reload-btn"]').click()
        for _ in range(50):
            if len(held_responses) == 1:
                break
            page.wait_for_timeout(100)
        assert len(held_responses) == 1, "Bracket GET request did not reach the held route"

        page.locator(".tournament-detail .detail-header button").filter(
            has_text=re.compile("Đóng|Close")
        ).click()
        open_tournament(page, str(ctx_b["tournament_id"]), ctx_b["tournament_name"])

        route, response = held_responses.pop()
        route.fulfill(response=response)
        page.unroute(bracket_url, hold_bracket)

        expect(page.locator(".tournament-detail h3")).to_have_text(ctx_b["tournament_name"])
        expect(page.locator('[data-testid="bracket-view-empty"]')).to_be_visible()
        expect(page.locator('[data-testid="bracket-tree"]')).to_have_count(0)
    finally:
        for route, response in held_responses:
            route.fulfill(response=response)
        page.unroute(bracket_url, hold_bracket)
