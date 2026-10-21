from playwright.sync_api import Browser, Page, expect

from helpers import login, register_user, unique_username


def create_team(page: Page, team_name: str, tag: str) -> None:
    page.get_by_label("Tên đội").fill(team_name)
    page.get_by_label("Tag").fill(tag)
    page.get_by_label("Game").select_option(label="VALORANT")
    page.get_by_role("button", name="Tạo đội").click()
    expect(page.locator(".message.success")).to_contain_text("Tạo đội thành công")
    expect(page.locator(".team-list article").filter(has_text=team_name)).to_be_visible()


def test_authenticated_user_can_create_team(page: Page):
    username = unique_username("create")
    team_name = f"Browser Test Team {unique_username('team')[-6:]}"
    tag = f"PW{unique_username('tag')[-6:]}".upper()

    register_user(page, username)
    login(page, username)
    create_team(page, team_name, tag)

    page.locator(".team-list article").filter(has_text=team_name).get_by_role(
        "button", name="Xem đội"
    ).click()
    detail = page.locator(".team-detail")
    expect(detail.get_by_role("heading", name=team_name)).to_be_visible()
    manager_row = detail.locator(".member-row").filter(has_text=username)
    expect(manager_row).to_contain_text("MANAGER · Đang hoạt động")


def test_manager_can_add_update_and_end_membership(page: Page, browser: Browser):
    manager = unique_username("manager")
    player = unique_username("player")
    team_name = f"Browser Member Team {unique_username('member')[-6:]}"
    tag = f"PM{unique_username('tag')[-6:]}".upper()

    register_user(page, manager)
    login(page, manager)
    create_team(page, team_name, tag)

    player_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    player_page.goto(page.url)
    register_user(player_page, player)
    player_page.close()

    page.locator(".team-list article").filter(has_text=team_name).get_by_role(
        "button", name="Xem đội"
    ).click()
    detail = page.locator(".team-detail")
    page.get_by_label("Tên đăng nhập").fill(player)
    page.locator('select[name="role_in_team"]').select_option("PLAYER")
    page.get_by_role("button", name="Thêm thành viên").click()
    member = detail.locator(".member-row").filter(has_text=player)
    expect(member).to_contain_text("PLAYER · Đang hoạt động")

    page.get_by_label(f"Vị trí của {player}").select_option("COACH")
    expect(member).to_contain_text("COACH · Đang hoạt động")

    page.once("dialog", lambda dialog: dialog.accept())
    member.get_by_role("button", name="Kết thúc").click()
    expect(member).to_contain_text("COACH · Đã rời đội")
    expect(member).to_contain_text("Rời đội")
