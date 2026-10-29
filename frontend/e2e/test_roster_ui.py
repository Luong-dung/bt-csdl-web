import re
from datetime import date, timedelta
from playwright.sync_api import Browser, Page, expect

from helpers import create_team, login, register_user, unique_username
from test_tournaments import create_tournament, open_tournament, refresh_tournament


def add_player_to_team(page: Page, team_name: str, player_username: str) -> None:
    page.locator(".team-list article").filter(has_text=team_name).get_by_role(
        "button", name="Xem đội"
    ).click()
    detail = page.locator(".team-detail")
    page.get_by_label("Tên đăng nhập").fill(player_username)
    page.locator('select[name="role_in_team"]').select_option("PLAYER")
    page.get_by_role("button", name="Thêm thành viên").click()
    member = detail.locator(".member-row").filter(has_text=player_username)
    expect(member).to_contain_text("PLAYER · Đang hoạt động")
    page.locator(".team-detail button").filter(has_text=re.compile("Đóng|Close")).click()


def test_approved_team_roster_selection_and_organizer_lock(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    # 1. Organizer creates tournament
    tournament_name, tournament_id = create_tournament(page, demo_password)

    # 2. Manager creates team and adds a PLAYER member
    manager_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    manager_page.set_default_timeout(10_000)
    public_page = None

    try:
        manager_page.goto(app_base_url)
        manager = unique_username("mgr")
        player = unique_username("plr")
        register_user(manager_page, manager)
        login(manager_page, manager)

        # Create another user for player
        player_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        player_page.set_default_timeout(10_000)
        try:
            player_page.goto(app_base_url)
            register_user(player_page, player)
        finally:
            player_page.close()

        team_name = f"Browser Roster Team {unique_username('roster')[-6:]}"
        tag = f"RO{unique_username('tag')[-5:]}".upper()
        create_team(manager_page, team_name, tag)
        team_card = manager_page.locator(".team-list article").filter(has_text=team_name)
        team_id = team_card.get_attribute("data-team-id")
        assert team_id is not None

        # Add player to team
        add_player_to_team(manager_page, team_name, player)

        # Manager registers team for tournament
        open_tournament(manager_page, tournament_id, tournament_name)
        manager_page.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(manager_page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")

        # 3. Organizer approves team
        refresh_tournament(page, tournament_id, tournament_name)
        registration = page.locator(f'.registration-card[data-team-id="{team_id}"]')
        registration.get_by_role("button", name="Duyệt").click()
        expect(registration.locator(".reg-badge")).to_have_text("APPROVED")
        expect(page.locator(f'.approved-team-card[data-team-id="{team_id}"]')).to_be_visible()

        # Organizer sees start conditions warning: Roster must be locked
        expect(page.locator(".condition-item.unmet")).to_contain_text("Điều kiện bắt đầu giải đấu")
        expect(page.locator(".roster-lock-controls button")).to_contain_text("Khóa đội hình giải đấu")

        # 3a. Khóa 409: Thử khóa khi đội APPROVED chưa có PLAYER trong roster
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".roster-lock-controls button").filter(has_text="Khóa đội hình giải đấu").click()
        expect(page.locator(".roster-lock-controls .error-banner")).to_be_visible()
        expect(page.locator(".condition-item.unmet")).to_be_visible()

        # 3b. Xem nháp 401: Khách vãng lai chưa đăng nhập xem nháp bị 401
        anon_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        anon_page.set_default_timeout(10_000)
        try:
            anon_page.goto(app_base_url)
            open_tournament(anon_page, tournament_id, tournament_name)
            anon_card = anon_page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
            expect(anon_card).to_be_visible()
            anon_card.locator(".roster-btn").click()
            expect(anon_page.locator(f'.team-roster-panel[data-team-id="{team_id}"] .error-banner')).to_contain_text(
                "Đội hình đang là bản nháp riêng tư. Cần đăng nhập để xem."
            )
        finally:
            anon_page.close()

        # 3c. Xem nháp 403: Người dùng khác không thuộc đội và không quản lý giải bị 403
        stranger_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        stranger_page.set_default_timeout(10_000)
        try:
            stranger = unique_username("stranger")
            stranger_page.goto(app_base_url)
            register_user(stranger_page, stranger)
            login(stranger_page, stranger)
            open_tournament(stranger_page, tournament_id, tournament_name)
            stranger_card = stranger_page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
            expect(stranger_card).to_be_visible()
            stranger_card.locator(".roster-btn").click()
            expect(stranger_page.locator(f'.team-roster-panel[data-team-id="{team_id}"] .error-banner')).to_contain_text(
                "Bạn không có quyền xem đội hình nháp này"
            )
        finally:
            stranger_page.close()

        # 4. Manager selects and saves roster
        refresh_tournament(manager_page, tournament_id, tournament_name, username=manager)
        approved_card = manager_page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        expect(approved_card).to_be_visible()

        # Open team roster panel
        approved_card.locator(".roster-btn").click()
        roster_panel = manager_page.locator(f'.team-roster-panel[data-team-id="{team_id}"]')
        expect(roster_panel).to_be_visible()
        expect(roster_panel).to_contain_text("Bản nháp (Chưa khóa)")

        # Add player from dropdown
        add_select = roster_panel.locator(".add-member-form select")
        expect(add_select).to_be_visible()
        add_select.select_option(label=f"{player} (PLAYER)")

        # Verify member appears in roster draft list
        expect(roster_panel.locator(".roster-members-list")).to_contain_text(player)

        # Save roster
        roster_panel.get_by_role("button", name="Lưu đội hình").click()
        expect(roster_panel.locator(".notice-banner")).to_contain_text("Đã lưu đội hình tham dự thành công")

        # Reload manager page and verify roster persisted
        refresh_tournament(manager_page, tournament_id, tournament_name, username=manager)
        manager_page.locator(f'.approved-team-card[data-team-id="{team_id}"] .roster-btn').click()
        roster_panel = manager_page.locator(f'.team-roster-panel[data-team-id="{team_id}"]')
        expect(roster_panel.locator(".roster-members-list")).to_contain_text(player)

        # Manager changes draft in UI (gỡ thành viên) but hasn't saved yet
        roster_panel.locator(".roster-member-row button").filter(has_text="Gỡ khỏi đội hình").click()

        # 5. Organizer locks tournament roster in parallel session
        refresh_tournament(page, tournament_id, tournament_name)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".roster-lock-controls button").filter(has_text="Khóa đội hình giải đấu").click()
        expect(page.locator(".roster-lock-controls .notice-banner")).to_contain_text("Đã khóa đội hình giải đấu thành công")

        # Start condition is now MET
        expect(page.locator(".condition-item.met")).to_contain_text("Đội hình giải đấu đã được khóa")

        # "Chuyển sang ONGOING" button is now available in status actions
        expect(page.locator(".status-actions button").filter(has_text="Chuyển sang ONGOING")).to_be_visible()

        # Detail stat shows "Đã khóa"
        expect(page.locator(".detail-stats")).to_contain_text("Đã khóa")

        # 5a. E2E ca 409 khi lưu: Quản lý đội lưu bản nháp sau khi giải đã bị khóa -> nhận 409, giữ thông báo lỗi, tự chuyển sang snapshot
        roster_panel.get_by_role("button", name="Lưu đội hình").click()
        expect(roster_panel.locator(".error-banner")).to_be_visible()
        expect(roster_panel.locator(".error-banner")).to_contain_text(re.compile(r"Xung đột|đã bị khóa|khóa"))
        expect(roster_panel).to_contain_text("Đã khóa (Snapshot)")
        expect(roster_panel.get_by_role("button", name="Lưu đội hình")).to_have_count(0)
        expect(roster_panel.locator(".roster-members-grid")).to_contain_text(player)

        # 5b. E2E ca đổi giải / reset lockLoading: đóng chi tiết giải và mở lại -> không bị kẹt spinner lockLoading
        page.locator("button").filter(has_text="Quay lại danh sách giải").click()
        expect(page.locator(".tournament-detail")).to_have_count(0)
        open_tournament(page, tournament_id, tournament_name)
        expect(page.locator(".roster-lock-controls .spinner")).to_have_count(0)

        # 5c. Bấm chuyển trạng thái sang ONGOING thật
        page.locator(".status-actions button").filter(has_text="Chuyển sang ONGOING").click()
        expect(page.locator(".detail-stats")).to_contain_text("ONGOING")

        # 6. Manager reloads - roster is locked read-only snapshot
        refresh_tournament(manager_page, tournament_id, tournament_name, username=manager)
        manager_page.locator(f'.approved-team-card[data-team-id="{team_id}"] .roster-btn').click()
        locked_roster_panel = manager_page.locator(f'.team-roster-panel[data-team-id="{team_id}"]')
        expect(locked_roster_panel).to_contain_text("Đã khóa (Snapshot)")
        expect(locked_roster_panel.get_by_role("button", name="Lưu đội hình")).to_have_count(0)
        expect(locked_roster_panel.locator(".roster-members-grid")).to_contain_text(player)

        # 7. Public user views the locked roster snapshot (publicly viewable after lock)
        public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        public_page.set_default_timeout(10_000)
        public_page.goto(app_base_url)
        open_tournament(public_page, tournament_id, tournament_name)
        public_card = public_page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        expect(public_card).to_be_visible()
        public_card.locator(".roster-btn").click()

        public_roster_panel = public_page.locator(f'.team-roster-panel[data-team-id="{team_id}"]')
        expect(public_roster_panel).to_be_visible()
        expect(public_roster_panel).to_contain_text("Đã khóa (Snapshot)")
        expect(public_roster_panel.locator(".roster-members-grid")).to_contain_text(player)
    finally:
        manager_page.close()
        if public_page is not None:
            public_page.close()
