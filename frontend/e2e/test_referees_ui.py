"""W47-05 Browser E2E: Tournament Referee Management UI.

Validates:
1. Candidate user search (username/real_name without exposing email), grant, reload persistence,
   revoke, revoked history toggle, re-grant, non-manager visibility isolation, and 390px mobile layout.
2. Error handling & retry: list 500 + retry, 422 self-grant / 404 unknown user / 409 conflict of interest /
   409 duplicate active grant (all preserving form input), 409 already-revoked treated as done + refresh,
   closed tournament (CANCELLED) disabling grant while keeping list & revoke, and 401 session expiry.
3. Double-submit prevention on POST /referees and anti-stale guards when switching tournament or logging out
   while GET /referees is in-flight.
"""
import re
from datetime import date, timedelta
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from helpers import login, unique_username, wait_for_held_request
from test_matches_ui import _api_request, _register_and_login_api
from test_tournaments import open_tournament


def _create_upcoming_tournament(
    page: Page,
    api_base_url: str,
    demo_password: str,
    *,
    prefix: str = "ref",
) -> dict:
    organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    if not organizer_token:
        login(page, "demo_organizer", demo_password)
        organizer_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert organizer_token

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    tname = f"Ref UI {unique_username(prefix)[-8:]}"
    tournament = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=organizer_token,
        data={
            "name": tname,
            "game_id": game_id,
            "format": "SINGLE_ELIM",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
        },
    )
    return {
        "tournament_id": tournament["tournament_id"],
        "tournament_name": tname,
        "game_id": game_id,
        "organizer_token": organizer_token,
    }


def test_referees_search_grant_revoke_history_and_390px_mobile_ui(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    ctx = _create_upcoming_tournament(page, api_base_url, demo_password, prefix="main")
    tid = ctx["tournament_id"]
    tname = ctx["tournament_name"]

    cand_user, _cand_tok = _register_and_login_api(page, api_base_url, "refcand", demo_password)
    cand_username = cand_user["username"]
    cand_email = f"{cand_username}@example.com"
    cand_uid = cand_user["user_id"]

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tid), tname)

    section = page.locator('[data-testid="tournament-referees-section"]')
    expect(section).to_be_visible()
    expect(section.locator('[data-testid="referees-empty"]')).to_be_visible()

    # Search by email must NOT find the user (no email probing/leak)
    section.locator('[data-testid="referee-user-search-input"]').fill(cand_email)
    section.locator('[data-testid="referee-user-search-btn"]').click()
    expect(section.locator('[data-testid="referee-search-empty"]')).to_be_visible()

    # Search by username returns candidate without exposing email
    section.locator('[data-testid="referee-user-search-input"]').fill(cand_username)
    section.locator('[data-testid="referee-user-search-btn"]').click()
    cand_item = section.locator(f'[data-testid="referee-candidate-item-{cand_uid}"]')
    expect(cand_item).to_be_visible()
    expect(cand_item).to_contain_text(cand_username)
    expect(cand_item).not_to_contain_text(cand_email)
    expect(section).not_to_contain_text("@example.com")

    # Select candidate populates user_id and selected badge
    section.locator(f'[data-testid="referee-candidate-select-{cand_uid}"]').click()
    expect(section.locator('[data-testid="referee-selected-candidate"]')).to_contain_text(cand_username)
    expect(section.locator('[data-testid="referee-user-id-input"]')).to_have_value(str(cand_uid))

    # Check 390px mobile viewport has no horizontal document overflow
    page.set_viewport_size({"width": 390, "height": 844})
    has_overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not has_overflow, "Referee management UI overflows horizontally at 390px viewport"
    page.set_viewport_size({"width": 1280, "height": 800})

    # Grant referee via UI (real POST /tournaments/{tid}/referees)
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as grant_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert grant_resp.value.status == 201
    assignment_id = grant_resp.value.json()["assignment_id"]

    expect(section.locator('[data-testid="referees-notice-banner"]')).to_contain_text(cand_username)
    row = section.locator(f'[data-testid="referee-row-{assignment_id}"]')
    expect(row).to_be_visible()
    expect(row).to_contain_text(cand_username)
    expect(row).not_to_contain_text(cand_email)
    expect(section.locator(f'[data-testid="referee-status-{assignment_id}"]')).to_have_text("Đang hiệu lực")

    # Reload persistence
    page.reload()
    open_tournament(page, str(tid), tname)
    section = page.locator('[data-testid="tournament-referees-section"]')
    expect(section.locator(f'[data-testid="referee-row-{assignment_id}"]')).to_be_visible()

    # Non-manager (even the scoped referee itself) must NOT see referee management section
    ref_page = browser.new_page(viewport={"width": 1280, "height": 800})
    ref_page.set_default_timeout(10_000)
    try:
        ref_page.goto(app_base_url)
        login(ref_page, cand_username, demo_password)
        open_tournament(ref_page, str(tid), tname)
        expect(ref_page.locator('[data-testid="tournament-referees-section"]')).to_have_count(0)
    finally:
        ref_page.close()

    # Revoke referee via UI
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees/{assignment_id}")
        and r.request.method == "DELETE"
    ) as revoke_resp:
        section.locator(f'[data-testid="referee-revoke-btn-{assignment_id}"]').click()
    assert revoke_resp.value.status == 200

    expect(section.locator('[data-testid="referees-notice-banner"]')).to_contain_text("Đã thu hồi")
    expect(section.locator('[data-testid="referees-empty"]')).to_be_visible()

    # Toggle include_revoked to view history (no revoke button on revoked row)
    section.locator('[data-testid="referees-include-revoked-toggle"]').check()
    expect(section.locator(f'[data-testid="referee-row-{assignment_id}"]')).to_be_visible()
    expect(section.locator(f'[data-testid="referee-status-{assignment_id}"]')).to_have_text("Đã thu hồi")
    expect(section.locator(f'[data-testid="referee-revoke-btn-{assignment_id}"]')).to_have_count(0)

    # Re-grant same user creates a new active assignment
    section.locator('[data-testid="referee-user-id-input"]').fill(str(cand_uid))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as regrant_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert regrant_resp.value.status == 201
    new_assignment_id = regrant_resp.value.json()["assignment_id"]
    assert new_assignment_id != assignment_id
    expect(section.locator(f'[data-testid="referee-status-{new_assignment_id}"]')).to_have_text("Đang hiệu lực")


def test_referees_errors_401_403_404_409_422_retry_and_closed_tournament(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    ctx = _create_upcoming_tournament(page, api_base_url, demo_password, prefix="err")
    tid = ctx["tournament_id"]
    tname = ctx["tournament_name"]
    token = ctx["organizer_token"]
    game_id = ctx["game_id"]

    # Create a registered team with a player (conflict of interest target)
    _mgr, mgr_tok = _register_and_login_api(page, api_base_url, "refmgr", demo_password)
    plr, _plr_tok = _register_and_login_api(page, api_base_url, "refplr", demo_password)
    clean_ref, _clean_tok = _register_and_login_api(page, api_base_url, "refok", demo_password)
    me_org = _api_request(page, "GET", f"{api_base_url}/auth/me", token=token)

    suffix = unique_username("rt")[-4:]
    team = _api_request(
        page,
        "POST",
        f"{api_base_url}/teams",
        token=mgr_tok,
        data={"name": f"RefTeam {suffix}", "tag": f"RT{suffix[:4]}".upper(), "game_id": game_id},
    )
    _api_request(
        page,
        "POST",
        f"{api_base_url}/teams/{team['team_id']}/members",
        token=mgr_tok,
        data={"username": plr["username"], "role_in_team": "PLAYER"},
    )
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/registrations",
        token=mgr_tok,
        data={"team_id": team["team_id"]},
    )

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tid), tname)
    section = page.locator('[data-testid="tournament-referees-section"]')
    expect(section).to_be_visible()

    # 1. List 500 error + Retry recovers cleanly
    list_url = f"**/api/v1/tournaments/{tid}/referees*"

    def fail_list_once(route):
        if route.request.method == "GET" and urlparse(route.request.url).path.endswith(f"/tournaments/{tid}/referees"):
            route.fulfill(status=500, content_type="application/json", body='{"detail":"Lỗi máy chủ tạm thời"}')
        else:
            route.continue_()

    page.route(list_url, fail_list_once)
    try:
        section.locator('[data-testid="referees-reload-btn"]').click()
        expect(section.locator('[data-testid="referees-error-banner"]')).to_contain_text("Lỗi máy chủ tạm thời")
    finally:
        page.unroute(list_url, fail_list_once)

    section.locator('[data-testid="referees-retry-btn"]').click()
    expect(section.locator('[data-testid="referees-error-banner"]')).to_have_count(0)
    expect(section.locator('[data-testid="referees-empty"]')).to_be_visible()

    # 2. Real backend 422 (self-grant) preserves input
    uid_input = section.locator('[data-testid="referee-user-id-input"]')
    uid_input.fill(str(me_org["id"]))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as self_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert self_resp.value.status == 422
    expect(section.locator('[data-testid="referee-form-error-banner"]')).to_contain_text("tự cấp")
    expect(uid_input).to_have_value(str(me_org["id"]))

    # 3. Real backend 404 (unknown user) preserves input
    uid_input.fill("999999")
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as notfound_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert notfound_resp.value.status == 404
    expect(section.locator('[data-testid="referee-form-error-banner"]')).to_contain_text("Không tìm thấy người dùng")
    expect(uid_input).to_have_value("999999")

    # 4. Real backend 409 (conflict of interest: active player of registered team) preserves input
    uid_input.fill(str(plr["user_id"]))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as coi_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert coi_resp.value.status == 409
    expect(section.locator('[data-testid="referee-form-error-banner"]')).to_contain_text("đang thi đấu")
    expect(uid_input).to_have_value(str(plr["user_id"]))

    # 5. Real backend 409 (duplicate active grant done via API while UI is open) preserves input & refreshes list
    api_grant = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/referees",
        token=token,
        data={"user_id": clean_ref["user_id"]},
    )
    aid_1 = api_grant["assignment_id"]
    uid_input.fill(str(clean_ref["user_id"]))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as dup_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert dup_resp.value.status == 409
    expect(section.locator('[data-testid="referee-form-error-banner"]')).to_contain_text("đã có quyền này")
    expect(uid_input).to_have_value(str(clean_ref["user_id"]))
    expect(section.locator(f'[data-testid="referee-row-{aid_1}"]')).to_be_visible()

    # 6. Real backend 409 on revoke (already revoked via API) -> UI treats as done and refreshes list
    _api_request(
        page,
        "DELETE",
        f"{api_base_url}/tournaments/{tid}/referees/{aid_1}",
        token=token,
    )
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees/{aid_1}")
        and r.request.method == "DELETE"
    ) as rev409_resp:
        section.locator(f'[data-testid="referee-revoke-btn-{aid_1}"]').click()
    assert rev409_resp.value.status == 409
    expect(section.locator('[data-testid="referees-notice-banner"]')).to_contain_text("đã được thu hồi trước đó")
    expect(section.locator('[data-testid="referees-empty"]')).to_be_visible()

    # 6b. Real backend 403 when scoped organizer loses permission while form is open:
    #     shows 403 error banner, reloads capability, hides grant panel and explains loss of permission
    scoped_org, _scoped_org_tok = _register_and_login_api(page, api_base_url, "scorg", demo_password)
    admin_login = _api_request(
        page,
        "POST",
        f"{api_base_url}/auth/login",
        data={"username": "demo_admin", "password": demo_password},
    )
    admin_token = admin_login["access_token"]
    org_assign = _api_request(
        page,
        "POST",
        f"{api_base_url}/admin/role-assignments",
        token=admin_token,
        data={
            "user_id": scoped_org["user_id"],
            "role": "ORGANIZER",
            "scope_type": "TOURNAMENT",
            "scope_id": tid,
        },
    )
    scoped_org_page = browser.new_page(viewport={"width": 1280, "height": 800})
    scoped_org_page.set_default_timeout(10_000)
    try:
        scoped_org_page.goto(app_base_url)
        login(scoped_org_page, scoped_org["username"], demo_password)
        open_tournament(scoped_org_page, str(tid), tname)
        sc_sec = scoped_org_page.locator('[data-testid="tournament-referees-section"]')
        expect(sc_sec.locator('[data-testid="referee-grant-panel"]')).to_be_visible()

        # Admin revokes scoped organizer permission while UI form is open
        _api_request(
            page,
            "DELETE",
            f"{api_base_url}/admin/role-assignments/{org_assign['assignment_id']}",
            token=admin_token,
        )
        sc_sec.locator('[data-testid="referee-user-id-input"]').fill(str(clean_ref["user_id"]))
        with scoped_org_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
        ) as resp_403:
            sc_sec.locator('[data-testid="referee-grant-submit-btn"]').click()
        assert resp_403.value.status == 403
        expect(sc_sec.locator('[data-testid="referee-form-error-banner"]')).to_be_visible()
        expect(sc_sec.locator('[data-testid="referee-grant-panel"]')).to_have_count(0)
        expect(sc_sec.locator('[data-testid="referee-grant-unavailable-reason"]')).to_contain_text(
            "không còn quyền"
        )
    finally:
        scoped_org_page.close()

    # 7. Closed tournament (CANCELLED): grant returns 409, capability reloads to hide grant form,
    #    while list and revoke button remain available and functional!
    api_grant_2 = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/referees",
        token=token,
        data={"user_id": clean_ref["user_id"]},
    )
    aid_2 = api_grant_2["assignment_id"]
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/status",
        token=token,
        data={"status": "CANCELLED"},
    )
    uid_input.fill(str(clean_ref["user_id"]))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees") and r.request.method == "POST"
    ) as closed_resp:
        section.locator('[data-testid="referee-grant-submit-btn"]').click()
    assert closed_resp.value.status == 409
    expect(section.locator('[data-testid="referee-form-error-banner"]')).to_contain_text("đã kết thúc hoặc bị hủy")
    expect(section.locator('[data-testid="referee-grant-panel"]')).to_have_count(0)
    expect(section.locator('[data-testid="referee-grant-unavailable-reason"]')).to_be_visible()

    # Active referee is still listed and revocable in CANCELLED tournament
    expect(section.locator(f'[data-testid="referee-row-{aid_2}"]')).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/referees/{aid_2}")
        and r.request.method == "DELETE"
    ) as closed_rev_resp:
        section.locator(f'[data-testid="referee-revoke-btn-{aid_2}"]').click()
    assert closed_rev_resp.value.status == 200
    expect(section.locator('[data-testid="referees-empty"]')).to_be_visible()

    # 8. 401 on referee reload triggers handleAuthExpired
    def fail_401(route):
        if route.request.method == "GET" and urlparse(route.request.url).path.endswith(f"/tournaments/{tid}/referees"):
            route.fulfill(status=401, content_type="application/json", body='{"detail":"Token hết hạn"}')
        else:
            route.continue_()

    page.route(list_url, fail_401)
    try:
        section.locator('[data-testid="referees-reload-btn"]').click()
        expect(page.locator(".profile")).to_have_count(0)
        expect(page.locator(".message.error")).to_contain_text("Phiên đăng nhập đã hết hạn")
    finally:
        page.unroute(list_url, fail_401)


def test_referees_double_submit_guard_and_in_flight_switch_anti_stale(
    page: Page, api_base_url: str, demo_password: str
):
    ctx_a = _create_upcoming_tournament(page, api_base_url, demo_password, prefix="stla")
    ctx_b = _create_upcoming_tournament(page, api_base_url, demo_password, prefix="stlb")
    tid_a = ctx_a["tournament_id"]
    tname_a = ctx_a["tournament_name"]
    tid_b = ctx_b["tournament_id"]
    tname_b = ctx_b["tournament_name"]

    ref_user, _ref_tok = _register_and_login_api(page, api_base_url, "refdbl", demo_password)

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tid_a), tname_a)
    section_a = page.locator('[data-testid="tournament-referees-section"]')
    expect(section_a).to_be_visible()

    # --- Part 1: Double-submit guard on POST /referees ---
    held_posts = []
    post_count = 0
    post_url = f"**/api/v1/tournaments/{tid_a}/referees"

    def hold_grant_post(route):
        nonlocal post_count
        if route.request.method == "POST" and urlparse(route.request.url).path.endswith(f"/tournaments/{tid_a}/referees"):
            post_count += 1
            held_posts.append(route)
        else:
            route.continue_()

    page.route(post_url, hold_grant_post)
    try:
        section_a.locator('[data-testid="referee-user-id-input"]').fill(str(ref_user["user_id"]))
        submit_btn = section_a.locator('[data-testid="referee-grant-submit-btn"]')
        submit_btn.click()
        wait_for_held_request(page, held_posts, expected_count=1)
        expect(submit_btn).to_be_disabled()
        # Dispatch an extra submit event while request is in-flight -> synchronous ref lock must ignore it
        section_a.locator('[data-testid="referee-grant-form"]').dispatch_event("submit")
        page.wait_for_timeout(150)
        assert post_count == 1, f"Expected exactly 1 grant POST request, got {post_count}"
        held_posts.pop(0).continue_()
    finally:
        page.unroute(post_url, hold_grant_post)
        for r in list(held_posts):
            try:
                r.continue_()
            except Exception:
                pass
        held_posts.clear()

    expect(section_a.locator('[data-testid="referees-notice-banner"]')).to_contain_text(ref_user["username"])
    expect(section_a.locator('[data-testid="referees-list"]')).to_contain_text(ref_user["username"])
    assert post_count == 1

    # --- Part 2: In-flight tournament switch anti-stale guard ---
    held_tourn = []
    released_tourn = False
    list_url_a = f"**/api/v1/tournaments/{tid_a}/referees*"

    def hold_list_tourn(route):
        if (
            not released_tourn
            and route.request.method == "GET"
            and urlparse(route.request.url).path.endswith(f"/tournaments/{tid_a}/referees")
        ):
            resp = route.fetch()
            held_tourn.append((route, resp))
        else:
            route.continue_()

    page.route(list_url_a, hold_list_tourn)
    try:
        section_a.locator('[data-testid="referees-reload-btn"]').click()
        wait_for_held_request(page, held_tourn, expected_count=1)

        # Switch to Tournament B while Tournament A's GET /referees is in-flight
        page.locator(".tournament-detail .detail-header button").filter(
            has_text=re.compile("Đóng|Close")
        ).click()
        open_tournament(page, str(tid_b), tname_b)

        released_tourn = True
        with page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid_a}/referees") and r.request.method == "GET"
        ):
            while held_tourn:
                r, resp = held_tourn.pop(0)
                r.fulfill(response=resp)
        page.unroute(list_url_a, hold_list_tourn)

        expect(page.locator(".tournament-detail h3")).to_have_text(tname_b)
        section_b = page.locator('[data-testid="tournament-referees-section"]')
        expect(section_b.locator('[data-testid="referees-empty"]')).to_be_visible()
        expect(section_b.locator('[data-testid="referees-list"]')).to_have_count(0)
    finally:
        released_tourn = True
        while held_tourn:
            r, resp = held_tourn.pop(0)
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        try:
            page.unroute(list_url_a, hold_list_tourn)
        except Exception:
            pass

    # --- Part 3: In-flight session switch (logout) anti-stale guard ---
    page.locator(".tournament-detail .detail-header button").filter(
        has_text=re.compile("Đóng|Close")
    ).click()
    open_tournament(page, str(tid_a), tname_a)
    expect(page.locator('[data-testid="tournament-referees-section"]')).to_be_visible()

    held_session = []
    released_session = False

    def hold_list_session(route):
        if (
            not released_session
            and route.request.method == "GET"
            and urlparse(route.request.url).path.endswith(f"/tournaments/{tid_a}/referees")
        ):
            resp = route.fetch()
            held_session.append((route, resp))
        else:
            route.continue_()

    page.route(list_url_a, hold_list_session)
    try:
        page.locator('[data-testid="referees-reload-btn"]').click()
        wait_for_held_request(page, held_session, expected_count=1)

        # Logout while GET /referees is in-flight
        page.locator(".profile").get_by_role("button", name="Đăng xuất").click()
        expect(page.locator(".auth-modal-close")).to_be_visible()
        page.locator(".auth-modal-close").click()

        released_session = True
        with page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid_a}/referees") and r.request.method == "GET"
        ):
            while held_session:
                r, resp = held_session.pop(0)
                r.fulfill(response=resp)
        page.unroute(list_url_a, hold_list_session)

        expect(page.locator('[data-testid="tournament-referees-section"]')).to_have_count(0)
        expect(page.locator(".profile")).to_have_count(0)
    finally:
        released_session = True
        while held_session:
            r, resp = held_session.pop(0)
            try:
                r.fulfill(response=resp)
            except Exception:
                pass
        try:
            page.unroute(list_url_a, hold_list_session)
        except Exception:
            pass
