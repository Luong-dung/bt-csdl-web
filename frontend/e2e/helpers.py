from time import monotonic
from uuid import uuid4

from playwright.sync_api import Page, expect


TEST_PASSWORD = "Browser-test-password-43"


def unique_username(prefix: str) -> str:
    return f"pw-{prefix}-{uuid4().hex[:10]}"


def register_user(page: Page, username: str, password: str = TEST_PASSWORD) -> None:
    if not page.get_by_label("Tên đăng nhập").is_visible():
        page.locator(".sidebar-login, [data-testid='sidebar-login']").first.click()
    page.get_by_role("button", name="Chưa có tài khoản? Đăng ký").click()
    page.get_by_label("Họ và tên").fill(f"Browser Test {username}")
    page.get_by_label("Email").fill(f"{username}@example.com")
    page.get_by_label("Tên đăng nhập").fill(username)
    page.get_by_label("Mật khẩu").fill(password)
    page.get_by_role("button", name="Tạo tài khoản").click()
    expect(page.locator(".message.success")).to_contain_text("Đăng ký thành công")


def login(page: Page, username: str, password: str = TEST_PASSWORD) -> None:
    if not page.get_by_label("Tên đăng nhập").is_visible():
        page.locator(".sidebar-login, [data-testid='sidebar-login']").first.click()
    page.get_by_label("Tên đăng nhập").fill(username)
    page.get_by_label("Mật khẩu").fill(password)
    page.get_by_role("button", name="Đăng nhập").click()
    expect(page.get_by_role("heading", name="Tài khoản đã xác thực")).to_be_visible()
    expect(page.locator(".profile")).to_contain_text(username)


def create_team(page: Page, team_name: str, tag: str) -> None:
    page.get_by_label("Tên đội").fill(team_name)
    page.get_by_label("Tag").fill(tag)
    page.locator("form.team-form select[name='game_id']").select_option(label="VALORANT")
    page.get_by_role("button", name="Tạo đội").click()
    expect(page.locator(".message.success")).to_contain_text("Tạo đội thành công")
    expect(page.locator(".team-list article").filter(has_text=team_name)).to_be_visible()


def wait_for_held_request(
    page: Page, requests: list, expected_count: int = 1, timeout_s: float = 10.0
) -> list:
    """Pump Playwright events until the route handler holds at least expected_count request(s)."""
    deadline = monotonic() + timeout_s
    while len(requests) < expected_count and monotonic() < deadline:
        page.wait_for_timeout(50)
    assert len(requests) >= expected_count, (
        f"Expected at least {expected_count} request(s) to be intercepted within {timeout_s} seconds, got {len(requests)}"
    )
    return requests

