from playwright.sync_api import Page, expect

from helpers import login, register_user, unique_username


def test_registration_login_session_and_logout(page: Page):
    username = unique_username("auth")
    password = "Browser-test-password-43"

    page.get_by_label("Tên đăng nhập").fill("demo_viewer")
    page.get_by_label("Mật khẩu").fill("wrong-browser-password")
    page.get_by_role("button", name="Đăng nhập").click()
    expect(page.locator(".message.error")).to_contain_text("Sai tài khoản hoặc mật khẩu")

    register_user(page, username, password)
    login(page, username, password)
    assert page.evaluate("localStorage.getItem('esports_access_token')")

    page.reload()
    expect(page.get_by_role("heading", name="Tài khoản đã xác thực")).to_be_visible()
    expect(page.locator(".profile")).to_contain_text(username)

    page.get_by_role("button", name="Đăng xuất").click()
    expect(page.get_by_role("heading", name="Đăng nhập")).to_be_visible()
    assert page.evaluate("localStorage.getItem('esports_access_token')") is None
