import re
from playwright.sync_api import Browser, Page, expect

from helpers import login, unique_username
from test_tournaments import create_tournament, open_tournament, refresh_tournament


def test_stage_crud_and_reorder_ui(page: Page, browser: Browser, app_base_url: str, demo_password: str):
    # 1. Organizer creates tournament
    tournament_name, tournament_id = create_tournament(page, demo_password)

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

    manager_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    manager_page.set_default_timeout(10_000)
    try:
        manager_page.goto(app_base_url)
        manager = unique_username("mgr")
        from helpers import register_user, create_team
        register_user(manager_page, manager)
        login(manager_page, manager)

        # Manager creates 2 teams
        team1_name = f"Team Alpha {unique_username('alpha')[-5:]}"
        team2_name = f"Team Beta {unique_username('beta')[-5:]}"
        create_team(manager_page, team1_name, "ALPH")
        create_team(manager_page, team2_name, "BETA")

        # Open tournament
        open_tournament(manager_page, tournament_id, tournament_name)
        reg_form = manager_page.locator(".registration-form")
        expect(reg_form).to_be_visible()

        # Both teams initially available
        select_box = reg_form.locator("select[name='team_id']")
        expect(select_box.locator("option")).to_have_count(2)

        # Register Team 1
        select_box.select_option(label=re.compile(team1_name))
        reg_form.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(manager_page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")

        # Now only Team 2 is available in dropdown
        expect(select_box.locator("option")).to_have_count(1)
        expect(select_box.locator("option")).to_contain_text(team2_name)

        # Register Team 2
        reg_form.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(manager_page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")

        # Both registered -> registration form disappears!
        expect(manager_page.locator(".registration-form")).to_have_count(0)
        expect(manager_page.locator(".registrations-section")).to_contain_text("Đơn đăng ký giải (2)")
    finally:
        manager_page.close()

