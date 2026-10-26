import re
from datetime import date, timedelta

from playwright.sync_api import Browser, Page, expect

from helpers import login, register_user, unique_username


def create_team(page: Page, name: str, tag: str) -> None:
    page.get_by_label("Tên đội").fill(name)
    page.get_by_label("Tag").fill(tag)
    page.locator("form.team-form select[name='game_id']").select_option(label="VALORANT")
    page.get_by_role("button", name="Tạo đội").click()
    expect(page.locator(".team-list article").filter(has_text=name)).to_be_visible()


def open_tournament(page: Page, name: str) -> None:
    page.locator(".tournament-card").filter(has_text=name).get_by_role(
        "button", name=re.compile("Xem chi tiết")
    ).click()
    expect(page.locator(".tournament-detail").get_by_role("heading", name=name)).to_be_visible()


def register_team_for_tournament(
    browser: Browser, base_url: str, tournament_name: str, prefix: str
) -> tuple[Page, str]:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(base_url)
    username = unique_username(prefix)
    register_user(page, username)
    login(page, username)

    team_name = f"Browser {prefix.title()} Team {unique_username('team')[-6:]}"
    tag = f"PW{unique_username('tag')[-6:]}".upper()
    create_team(page, team_name, tag)
    open_tournament(page, tournament_name)
    page.get_by_role("button", name="Gửi đơn đăng ký").click()
    registration = page.locator(".registration-card").filter(has_text=team_name)
    expect(registration.locator(".reg-badge")).to_have_text("PENDING")
    return page, team_name


def refresh_tournament(page: Page, name: str) -> None:
    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, name)


def test_tournament_registration_review_and_public_approved_teams(
    page: Page, browser: Browser, demo_password: str
):
    login(page, "demo_organizer", demo_password)
    tournament_name = f"Browser Tournament {unique_username('tournament')[-8:]}"

    page.locator(".tournament-create summary").click()
    page.get_by_label("Tên giải đấu").fill(tournament_name)
    page.get_by_label("Tựa game").select_option(label="VALORANT")
    page.get_by_label("Bắt đầu").fill((date.today() + timedelta(days=7)).isoformat())
    page.get_by_role("button", name="Tạo giải đấu").click()
    expect(page.locator(".tournament-card").filter(has_text=tournament_name)).to_be_visible()

    open_tournament(page, tournament_name)
    approved_page, approved_team = register_team_for_tournament(
        browser, page.url, tournament_name, "approved"
    )
    approved_page.close()

    refresh_tournament(page, tournament_name)
    registration = page.locator(".registration-card").filter(has_text=approved_team)
    registration.get_by_role("button", name="Duyệt").click()
    expect(registration.locator(".reg-badge")).to_have_text("APPROVED")
    expect(
        page.locator(".approved-teams-section .approved-team-card").filter(
            has_text=approved_team
        )
    ).to_be_visible()

    rejected_page, rejected_team = register_team_for_tournament(
        browser, page.url, tournament_name, "rejected"
    )
    rejected_page.close()
    refresh_tournament(page, tournament_name)
    registration = page.locator(".registration-card").filter(has_text=rejected_team)
    page.once("dialog", lambda dialog: dialog.accept("Browser E2E rejection"))
    registration.get_by_role("button", name="Từ chối").click()
    expect(registration.locator(".reg-badge")).to_have_text("REJECTED")

    cancelled_page, cancelled_team = register_team_for_tournament(
        browser, page.url, tournament_name, "cancelled"
    )
    registration = cancelled_page.locator(".registration-card").filter(has_text=cancelled_team)
    cancelled_page.once("dialog", lambda dialog: dialog.accept())
    registration.get_by_role("button", name="Hủy đơn").click()
    expect(registration.locator(".reg-badge")).to_have_text("CANCELLED")
    cancelled_page.close()

    public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    public_page.goto(page.url)
    open_tournament(public_page, tournament_name)
    approved_teams = public_page.locator(".approved-teams-section")
    expect(approved_teams.locator(".approved-team-card").filter(has_text=approved_team)).to_be_visible()
    expect(approved_teams.locator(".approved-team-card").filter(has_text=rejected_team)).to_have_count(0)
    expect(approved_teams.locator(".approved-team-card").filter(has_text=cancelled_team)).to_have_count(0)
    public_page.close()
