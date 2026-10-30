import re
from playwright.sync_api import Browser, Page, expect

from helpers import create_team, login, register_user, unique_username
from test_tournaments import create_tournament, open_tournament, refresh_tournament


def test_stage_crud_and_reorder_ui(page: Page, browser: Browser, app_base_url: str, demo_password: str):
    # 1. Organizer creates tournament and opens it
    tournament_name, tournament_id = create_tournament(page, demo_password)
    open_tournament(page, tournament_id, tournament_name)

    # 2. Check stages section is visible and can_manage_stages allows adding stages
    stages_section = page.locator('[data-testid="tournament-stages-section"]')
    expect(stages_section).to_be_visible()
    expect(stages_section).to_contain_text("Vòng đấu / Giai đoạn (0)")
    add_btn = stages_section.get_by_role("button", name="+ Thêm vòng đấu")
    expect(add_btn).to_be_visible()

    # 3. Add first stage: "Vòng bảng", order 1
    add_btn.click()
    create_form = page.locator('[data-testid="stage-create-form"]')
    expect(create_form).to_be_visible()
    create_form.get_by_label(re.compile("Tên vòng đấu")).fill("Vòng bảng")
    create_form.get_by_label(re.compile("Thứ tự")).fill("1")
    create_form.get_by_role("button", name="Lưu vòng đấu").click()

    expect(stages_section.locator(".notice-banner")).to_contain_text("Đã thêm vòng đấu thành công")
    stage_1 = page.locator('.stage-card[data-sequence-order="1"]')
    expect(stage_1).to_be_visible()
    expect(stage_1.locator(".stage-badge")).to_have_text("#1")
    expect(stage_1.locator(".stage-name")).to_have_text("Vòng bảng")

    # 4. Add second stage: "Chung kết", order 2
    stages_section.get_by_role("button", name="+ Thêm vòng đấu").click()
    create_form = page.locator('[data-testid="stage-create-form"]')
    create_form.get_by_label(re.compile("Tên vòng đấu")).fill("Chung kết")
    create_form.get_by_label(re.compile("Thứ tự")).fill("2")
    create_form.get_by_role("button", name="Lưu vòng đấu").click()

    stage_2 = page.locator('.stage-card[data-sequence-order="2"]')
    expect(stage_2).to_be_visible()
    expect(stage_2.locator(".stage-badge")).to_have_text("#2")
    expect(stage_2.locator(".stage-name")).to_have_text("Chung kết")
    expect(stages_section).to_contain_text("Vòng đấu / Giai đoạn (2)")

    # 5. Test 409 conflict on duplicate order: Try adding duplicate order 1
    stages_section.get_by_role("button", name="+ Thêm vòng đấu").click()
    create_form = page.locator('[data-testid="stage-create-form"]')
    create_form.get_by_label(re.compile("Tên vòng đấu")).fill("Bán kết")
    create_form.get_by_label(re.compile("Thứ tự")).fill("1")
    create_form.get_by_role("button", name="Lưu vòng đấu").click()

    # Form remains open with error banner and preserved inputs (requirement: giữ form khi lỗi 409/422)
    expect(create_form.locator(".error-banner")).to_be_visible()
    expect(create_form.get_by_label(re.compile("Tên vòng đấu"))).to_have_value("Bán kết")
    expect(create_form.get_by_label(re.compile("Thứ tự"))).to_have_value("1")

    # Cancel create form
    create_form.get_by_role("button", name="Hủy").click()
    expect(create_form).not_to_be_visible()

    # 6. Edit stage 2: rename "Chung kết" to "Chung kết tổng"
    stage_2.get_by_role("button", name="Sửa").click()
    edit_form = page.locator(f'[data-testid="stage-edit-form-{stage_2.get_attribute("data-stage-id")}"]')
    expect(edit_form).to_be_visible()
    edit_form.get_by_label(re.compile("Tên vòng đấu")).fill("Chung kết tổng")
    edit_form.get_by_role("button", name="Lưu").click()

    expect(stages_section.locator(".notice-banner")).to_contain_text("Đã cập nhật vòng đấu")
    expect(page.locator('.stage-card[data-sequence-order="2"] .stage-name')).to_have_text("Chung kết tổng")

    # 7. Atomic reorder: move stage 2 up (swapping with stage 1)
    stage_to_move = page.locator('.stage-card[data-sequence-order="2"]')
    stage_to_move.get_by_role("button", name="▲ Lên").click()

    expect(stages_section.locator(".notice-banner")).to_contain_text("Đã cập nhật thứ tự vòng đấu")
    # Now order 1 is "Chung kết tổng" and order 2 is "Vòng bảng"
    expect(page.locator('.stage-card[data-sequence-order="1"] .stage-name')).to_have_text("Chung kết tổng")
    expect(page.locator('.stage-card[data-sequence-order="2"] .stage-name')).to_have_text("Vòng bảng")

    # 8. Delete stage: delete "Vòng bảng"
    stage_to_delete = page.locator('.stage-card[data-sequence-order="2"]')
    page.once("dialog", lambda dialog: dialog.accept())
    stage_to_delete.get_by_role("button", name="Xóa").click()

    expect(stages_section.locator(".notice-banner")).to_contain_text("Đã xóa vòng đấu")
    expect(stages_section).to_contain_text("Vòng đấu / Giai đoạn (1)")
    expect(page.locator('.stage-card .stage-name')).to_have_text("Chung kết tổng")

    # 9. Verify public user cannot see mutation buttons
    public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    public_page.set_default_timeout(10_000)
    try:
        public_page.goto(app_base_url)
        open_tournament(public_page, tournament_id, tournament_name)
        pub_stages = public_page.locator('[data-testid="tournament-stages-section"]')
        expect(pub_stages).to_be_visible()
        expect(pub_stages).to_contain_text("Chung kết tổng")
        # Mutation buttons should NOT be visible
        expect(pub_stages.get_by_role("button", name="+ Thêm vòng đấu")).to_have_count(0)
        expect(pub_stages.get_by_role("button", name="Sửa")).to_have_count(0)
        expect(pub_stages.get_by_role("button", name="Xóa")).to_have_count(0)
        expect(pub_stages.get_by_role("button", name="▲ Lên")).to_have_count(0)
        expect(pub_stages.get_by_role("button", name="▼ Xuống")).to_have_count(0)
    finally:
        public_page.close()


def test_dropdown_never_shows_already_registered_teams(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)

    manager1_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    manager1_page.set_default_timeout(10_000)
    manager2_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    manager2_page.set_default_timeout(10_000)
    try:
        # Manager 1 registers Team 1
        manager1_page.goto(app_base_url)
        mgr1 = unique_username("mgr1")
        register_user(manager1_page, mgr1)
        login(manager1_page, mgr1)

        team1_name = f"Team Alpha {unique_username('alpha')[-5:]}"
        tag1 = f"A{unique_username('tag')[-5:]}".upper()[:10]
        create_team(manager1_page, team1_name, tag1)

        open_tournament(manager1_page, tournament_id, tournament_name)
        reg_form1 = manager1_page.locator(".registration-form")
        expect(reg_form1).to_be_visible()
        reg_form1.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(manager1_page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")

        # After registering, form is hidden for Manager 1 (team already registered)
        expect(manager1_page.locator(".registration-form")).to_have_count(0)

        # Manager 2 registers Team 2
        manager2_page.goto(app_base_url)
        mgr2 = unique_username("mgr2")
        register_user(manager2_page, mgr2)
        login(manager2_page, mgr2)

        team2_name = f"Team Beta {unique_username('beta')[-5:]}"
        tag2 = f"B{unique_username('tag')[-5:]}".upper()[:10]
        create_team(manager2_page, team2_name, tag2)

        open_tournament(manager2_page, tournament_id, tournament_name)
        reg_form2 = manager2_page.locator(".registration-form")
        expect(reg_form2).to_be_visible()
        reg_form2.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(manager2_page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")

        # After registering, form is hidden for Manager 2
        expect(manager2_page.locator(".registration-form")).to_have_count(0)

        # Organizer checks registrations: both teams are listed
        refresh_tournament(page, tournament_id, tournament_name)
        expect(page.locator(".registrations-section")).to_contain_text("Đơn đăng ký giải (2)")
    finally:
        manager1_page.close()
        manager2_page.close()


def test_session_switch_anti_stale_response_guard(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    # 1. Organizer A creates tournament and verifies manage capabilities
    tournament_name, tournament_id = create_tournament(page, demo_password)
    open_tournament(page, tournament_id, tournament_name)
    stages_section = page.locator('[data-testid="tournament-stages-section"]')
    expect(stages_section).to_be_visible()
    expect(stages_section.get_by_role("button", name="+ Thêm vòng đấu")).to_be_visible()

    # 2. Register regular user B on separate page
    user_b = unique_username("userb")
    reg_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        reg_page.goto(app_base_url)
        register_user(reg_page, user_b, demo_password)
    finally:
        reg_page.close()

    # 3. Intercept capabilities and registrations for this tournament
    held_capabilities = []
    held_registrations = []

    def intercept_caps(route):
        if not held_capabilities:
            held_capabilities.append(route)
            return
        route.continue_()

    def intercept_regs(route):
        if not held_registrations:
            held_registrations.append(route)
            return
        route.continue_()

    cap_url = f"**/api/v1/tournaments/{tournament_id}/capabilities"
    reg_url = f"**/api/v1/tournaments/{tournament_id}/registrations*"
    page.route(cap_url, intercept_caps)
    page.route(reg_url, intercept_regs)

    try:
        # Trigger data fetch for Organizer A by closing and reopening the tournament
        page.locator(".tournament-detail .detail-header button").filter(has_text=re.compile("Đóng|Close")).click()
        expect(page.locator(".tournament-detail")).to_have_count(0)
        page.locator(f'.tournament-card[data-tournament-id="{tournament_id}"]').get_by_role(
            "button", name=re.compile("Xem chi tiết")
        ).click()

        # Wait until Organizer A's capabilities request is captured in held_capabilities
        page.wait_for_timeout(300)
        assert len(held_capabilities) >= 1

        # While Organizer A's requests are in-flight, Organizer A logs out
        page.get_by_role("button", name="Đăng xuất").click()
        expect(page.get_by_role("heading", name="Đăng nhập")).to_be_visible()

        # User B (regular user, not organizer) logs in
        login(page, user_b, demo_password)

        # Ensure tournament detail is open for User B
        if page.locator(".tournament-detail").count() == 0:
            open_tournament(page, tournament_id, tournament_name)
        stages_b = page.locator('[data-testid="tournament-stages-section"]')
        expect(stages_b).to_be_visible()
        # User B is NOT organizer: "+ Thêm vòng đấu" is not visible
        expect(stages_b.get_by_role("button", name="+ Thêm vòng đấu")).to_have_count(0)
        expect(page.locator(".manage-panel")).to_have_count(0)

        # 4. Release Organizer A's held requests (which have can_manage=True)
        for r in held_capabilities:
            fetched = r.fetch()
            r.fulfill(response=fetched)
        held_capabilities.clear()

        for r in held_registrations:
            fetched = r.fetch()
            r.fulfill(response=fetched)
        held_registrations.clear()

        # 5. Verify that Organizer A's stale responses were rejected by the session guard:
        # User B MUST STILL NOT have "+ Thêm vòng đấu", manage panel, or organizer controls
        page.wait_for_timeout(500)
        expect(stages_b.get_by_role("button", name="+ Thêm vòng đấu")).to_have_count(0)
        expect(page.locator(".manage-panel")).to_have_count(0)
    finally:
        page.unroute(cap_url)
        page.unroute(reg_url)
