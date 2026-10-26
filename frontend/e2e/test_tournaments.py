import re
from datetime import date, timedelta

from playwright.sync_api import Browser, Page, expect

from helpers import login, register_user, unique_username


def create_tournament(page: Page, demo_password: str) -> tuple[str, str]:
    login(page, "demo_organizer", demo_password)
    name = f"Browser Tournament {unique_username('tournament')[-8:]}"
    page.locator(".tournament-create summary").click()
    page.get_by_label("Tên giải đấu").fill(name)
    page.get_by_label("Tựa game").select_option(label="VALORANT")
    page.get_by_label("Bắt đầu").fill((date.today() + timedelta(days=7)).isoformat())
    page.get_by_role("button", name="Tạo giải đấu").click()
    expect(page.locator(".message.success")).to_contain_text("Đã tạo giải đấu mới")
    card = page.locator(".tournament-card").filter(has_text=name)
    expect(card).to_be_visible()
    tournament_id = card.get_attribute("data-tournament-id")
    assert tournament_id is not None
    return name, tournament_id


def create_team(page: Page, name: str, tag: str) -> None:
    page.get_by_label("Tên đội").fill(name)
    page.get_by_label("Tag").fill(tag)
    page.locator("form.team-form select[name='game_id']").select_option(label="VALORANT")
    page.get_by_role("button", name="Tạo đội").click()
    expect(page.locator(".message.success")).to_contain_text("Tạo đội thành công")
    expect(page.locator(".team-list article").filter(has_text=name)).to_be_visible()


def open_tournament(page: Page, tournament_id: str, name: str) -> None:
    page.locator(f'.tournament-card[data-tournament-id="{tournament_id}"]').get_by_role(
        "button", name=re.compile("Xem chi tiết")
    ).click()
    expect(page.locator(".tournament-detail").get_by_role("heading", name=name)).to_be_visible()


def create_user_team_and_register(
    browser: Browser, app_base_url: str, tournament_id: str, tournament_name: str, prefix: str
) -> tuple[Page, str, str, str]:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(app_base_url)
        username = unique_username(prefix)
        register_user(page, username)
        login(page, username)

        team_name = f"Browser {prefix.title()} Team {unique_username('team')[-6:]}"
        tag = f"PW{unique_username('tag')[-6:]}".upper()
        create_team(page, team_name, tag)
        team_card = page.locator(".team-list article").filter(has_text=team_name)
        team_id = team_card.get_attribute("data-team-id")
        assert team_id is not None
        open_tournament(page, tournament_id, tournament_name)
        page.get_by_role("button", name="Gửi đơn đăng ký").click()
        expect(page.locator(".notice-banner")).to_contain_text("Đã gửi đơn đăng ký thành công")
        registration = page.locator(f'.registration-card[data-team-id="{team_id}"]')
        expect(registration.locator(".reg-badge")).to_have_text("PENDING")
        return page, username, team_name, team_id
    except Exception:
        page.close()
        raise


def refresh_tournament(
    page: Page, tournament_id: str, name: str, username: str = "demo_organizer"
) -> None:
    page.reload()
    expect(page.locator(".profile")).to_contain_text(username)
    open_tournament(page, tournament_id, name)


def test_tournament_approval_hides_team_from_registration_and_lists_it_publicly(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)
    manager_page, _username, team_name, team_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "approved"
    )
    public_page = None
    try:
        refresh_tournament(page, tournament_id, tournament_name)
        registration = page.locator(f'.registration-card[data-team-id="{team_id}"]')
        registration.get_by_role("button", name="Duyệt").click()
        expect(registration.locator(".reg-badge")).to_have_text("APPROVED")
        expect(
            page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        ).to_be_visible()

        refresh_tournament(manager_page, tournament_id, tournament_name, username=_username)
        approved_registration = manager_page.locator(
            f'.registration-card[data-team-id="{team_id}"]'
        )
        expect(approved_registration.locator(".reg-badge")).to_have_text("APPROVED")
        expect(manager_page.locator(".registration-form")).to_have_count(0)

        public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        public_page.goto(app_base_url)
        open_tournament(public_page, tournament_id, tournament_name)
        expect(
            public_page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        ).to_be_visible()
    finally:
        manager_page.close()
        if public_page is not None:
            public_page.close()


def test_tournament_rejection_persists_after_reload(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)
    manager_page, _username, team_name, team_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "rejected"
    )
    try:
        refresh_tournament(page, tournament_id, tournament_name)
        registration = page.locator(f'.registration-card[data-team-id="{team_id}"]')
        page.once("dialog", lambda dialog: dialog.accept("Browser E2E rejection"))
        registration.get_by_role("button", name="Từ chối").click()
        expect(registration.locator(".reg-badge")).to_have_text("REJECTED")

        refresh_tournament(page, tournament_id, tournament_name)
        rejected_registration = page.locator(f'.registration-card[data-team-id="{team_id}"]')
        expect(rejected_registration.locator(".reg-badge")).to_have_text("REJECTED")
        expect(rejected_registration.locator(".reg-reason")).to_contain_text(
            "Browser E2E rejection"
        )
    finally:
        manager_page.close()


def test_tournament_cancellation_persists_after_reload(
    page: Page, browser: Browser, app_base_url: str, demo_password: str
):
    tournament_name, tournament_id = create_tournament(page, demo_password)
    manager_page, username, team_name, team_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "cancelled"
    )
    try:
        registration = manager_page.locator(f'.registration-card[data-team-id="{team_id}"]')
        manager_page.once("dialog", lambda dialog: dialog.accept())
        registration.get_by_role("button", name="Hủy đơn").click()
        expect(registration.locator(".reg-badge")).to_have_text("CANCELLED")

        refresh_tournament(manager_page, tournament_id, tournament_name, username=username)
        cancelled_registration = manager_page.locator(
            f'.registration-card[data-team-id="{team_id}"]'
        )
        expect(cancelled_registration.locator(".reg-badge")).to_have_text("CANCELLED")
    finally:
        manager_page.close()
