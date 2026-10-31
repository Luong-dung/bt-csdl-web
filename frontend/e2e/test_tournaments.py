import re
from datetime import date, timedelta

import pytest
from playwright.sync_api import Browser, Page, expect

from helpers import create_team, login, register_user, unique_username


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


def open_tournament(page: Page, tournament_id: str, name: str) -> None:
    expect(page.locator(".tournament-grid .tournament-card").first).to_be_visible()
    card = page.locator(f'.tournament-card[data-tournament-id="{tournament_id}"]')
    while card.count() == 0:
        pagination = page.locator(".tournament-zone .pagination")
        next_page = pagination.get_by_role("button", name="Sau →")
        if pagination.count() == 0 or not next_page.is_enabled():
            break
        previous_ids = page.locator(".tournament-grid .tournament-card").evaluate_all(
            "cards => cards.map(card => card.dataset.tournamentId)"
        )
        next_page.click()
        page.wait_for_function(
            """previous => {
                if (document.querySelector(".tournament-zone .loading-state")) return false;
                const ids = Array.from(document.querySelectorAll(".tournament-grid .tournament-card"))
                    .map(card => card.dataset.tournamentId);
                return ids.length > 0 && JSON.stringify(ids) !== JSON.stringify(previous);
            }""",
            arg=previous_ids,
        )
    card.get_by_role(
        "button", name=re.compile("Xem chi tiết")
    ).click()
    expect(page.locator(".tournament-detail").get_by_role("heading", name=name)).to_be_visible()


def create_user_team_and_register(
    browser: Browser, app_base_url: str, tournament_id: str, tournament_name: str, prefix: str
) -> tuple[Page, str, str, str]:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(10_000)
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
        registration_id = registration.get_attribute("data-registration-id")
        assert registration_id is not None
        return page, username, team_id, registration_id
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
    manager_page, _username, team_id, registration_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "approved"
    )
    public_page = None
    try:
        refresh_tournament(page, tournament_id, tournament_name)
        registration = page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
        registration.get_by_role("button", name="Duyệt").click()
        expect(registration.locator(".reg-badge")).to_have_text("APPROVED")
        expect(
            page.locator(f'.approved-team-card[data-team-id="{team_id}"]')
        ).to_be_visible()

        refresh_tournament(manager_page, tournament_id, tournament_name, username=_username)
        approved_registration = manager_page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
        expect(approved_registration.locator(".reg-badge")).to_have_text("APPROVED")
        expect(manager_page.locator(".registration-form")).to_have_count(0)

        public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        public_page.set_default_timeout(10_000)
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
    manager_page, _username, _team_id, registration_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "rejected"
    )
    try:
        refresh_tournament(page, tournament_id, tournament_name)
        registration = page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
        page.once("dialog", lambda dialog: dialog.accept("Browser E2E rejection"))
        registration.get_by_role("button", name="Từ chối").click()
        expect(registration.locator(".reg-badge")).to_have_text("REJECTED")

        refresh_tournament(page, tournament_id, tournament_name)
        rejected_registration = page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
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
    manager_page, username, _team_id, registration_id = create_user_team_and_register(
        browser, app_base_url, tournament_id, tournament_name, "cancelled"
    )
    try:
        registration = manager_page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
        manager_page.once("dialog", lambda dialog: dialog.accept())
        registration.get_by_role("button", name="Hủy đơn").click()
        expect(registration.locator(".reg-badge")).to_have_text("CANCELLED")

        refresh_tournament(manager_page, tournament_id, tournament_name, username=username)
        cancelled_registration = manager_page.locator(
            f'.registration-card[data-registration-id="{registration_id}"]'
        )
        expect(cancelled_registration.locator(".reg-badge")).to_have_text("CANCELLED")
    finally:
        manager_page.close()


@pytest.mark.parametrize('action', ['reject', 'cancel'])
def test_locked_capabilities_hide_new_entries_and_approval_but_keep_resolution(
    page: Page, browser: Browser, app_base_url: str, demo_password: str, action: str
):
    """UI contract test: intercept lock hints until W44-2-04 supplies lock mutation.

    Backend locked-state enforcement and unchanged APPROVED teams are tested
    separately in test_roster_foundation.py on SQLite and PostgreSQL.
    """
    name, tid = create_tournament(page, demo_password)
    manager_page, username, _team_id, rid = create_user_team_and_register(
        browser, app_base_url, tid, name, 'lock' + action
    )

    def locked_hints(route):
        response = route.fetch()
        data = response.json()
        data.update(roster_locked=True, can_lock_roster=False, can_approve_registrations=False)
        route.fulfill(response=response, json=data)

    try:
        page.get_by_role('button', name='Đăng xuất', exact=True).click()
        login(page, 'demo_admin', demo_password)
        refresh_tournament(page, tid, name, username='demo_admin')
        # ADMIN also manages the seeded demo team, so there is a real submit
        # form to hide; the pending registration does not by itself hide it.
        expect(page.locator('.registration-form')).to_be_visible()
        path = f'**/api/v1/tournaments/{tid}/capabilities'
        page.route(path, locked_hints)
        manager_page.route(path, locked_hints)
        refresh_tournament(page, tid, name, username='demo_admin')
        expect(page.locator('.registration-form')).to_have_count(0)
        registration = page.locator(f'.registration-card[data-registration-id="{rid}"]')
        expect(registration.get_by_role('button', name='Duyệt', exact=True)).to_have_count(0)
        expect(registration.get_by_role('button', name='Từ chối', exact=True)).to_be_visible()

        if action == 'reject':
            page.once('dialog', lambda dialog: dialog.accept('Closed before roster lock'))
            registration.get_by_role('button', name='Từ chối', exact=True).click()
            expect(registration.locator('.reg-badge')).to_have_text('REJECTED')
            refresh_tournament(page, tid, name, username='demo_admin')
            expect(page.locator(f'.registration-card[data-registration-id="{rid}"] .reg-badge')).to_have_text('REJECTED')
        else:
            refresh_tournament(manager_page, tid, name, username=username)
            own_registration = manager_page.locator(f'.registration-card[data-registration-id="{rid}"]')
            manager_page.once('dialog', lambda dialog: dialog.accept())
            own_registration.get_by_role('button', name='Hủy đơn', exact=True).click()
            expect(own_registration.locator('.reg-badge')).to_have_text('CANCELLED')
            refresh_tournament(manager_page, tid, name, username=username)
            expect(manager_page.locator(f'.registration-card[data-registration-id="{rid}"] .reg-badge')).to_have_text('CANCELLED')
    finally:
        manager_page.close()
