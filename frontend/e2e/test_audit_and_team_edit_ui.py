"""W47-06 Browser E2E: Audit Log Viewer (Admin & Tournament), Team/Organization Edit UI, and Tournament Delete.

Validates:
1. Tournament & Admin audit log viewers: capability-based visibility, readable before/after diff tables,
   no sensitive data leak (email/token), filtering (resource/action/tournament_id/since/until),
   real backend 422 on since > until preserving inputs, pagination across pages with X-Total-Count,
   non-manager isolation, and 390px mobile layout without horizontal overflow.
2. Team & Organization edit UI: ADMIN create/rename organization + real 409 duplicate name preserving input +
   ORGANIZATION_UPDATED diff visible in admin audit log; team manager update name/tag/logo_url/game_id +
   real 409 duplicate tag & real 409 locked game_id after open registration preserving input and refreshing
   capabilities to disable locked fields with hints; viewer isolation; Tournament Delete 409 conflict & 204 success.
3. Anti-stale guards (in-flight tournament audit log on tournament switch, in-flight team PATCH on team switch),
   double-submit prevention on team PATCH, and 401 session expiry handling on audit log endpoint.
"""
from datetime import date, timedelta
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from helpers import create_team, login, register_user, unique_username, wait_for_held_request
from test_matches_ui import _api_request, _register_and_login_api
from test_tournaments import open_tournament


def _create_upcoming_tournament(
    page: Page,
    api_base_url: str,
    token: str,
    *,
    game_slug: str = "valorant",
    prefix: str = "aud",
) -> dict:
    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    game_id = next(g["game_id"] for g in games if g["slug"] == game_slug)
    tname = f"W4706 {unique_username(prefix)[-8:]}"
    tournament = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments",
        token=token,
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
    }


def _login_api(page: Page, api_base_url: str, username: str, password: str) -> str:
    resp = _api_request(
        page,
        "POST",
        f"{api_base_url}/auth/login",
        data={"username": username, "password": password},
    )
    return resp["access_token"]


def test_audit_logs_admin_and_tournament_filters_diff_pagination_and_390px(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    login(page, "demo_organizer", demo_password)
    org_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert org_token

    ctx = _create_upcoming_tournament(page, api_base_url, org_token, prefix="audt")
    tid = ctx["tournament_id"]
    tname = ctx["tournament_name"]

    # Grant a referee and create a stage to populate multiple tournament audit logs
    ref_user, _ref_token = _register_and_login_api(page, api_base_url, "audref", demo_password)
    ref_email = f"{ref_user['username']}@example.com"
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/referees",
        token=org_token,
        data={"user_id": ref_user["user_id"]},
    )
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/stages",
        token=org_token,
        data={"name": "Group Stage Audit", "sequence_order": 1},
    )

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")
    open_tournament(page, str(tid), tname)

    # Tournament audit log section visible to organizer; admin audit section hidden
    t_audit = page.locator('[data-testid="tournament-audit-section"]')
    expect(t_audit).to_be_visible()
    expect(page.locator('[data-testid="admin-audit-section"]')).to_have_count(0)

    # Verify ROLE_ASSIGNMENT_GRANTED log, actor username, readable before/after diff, and no email leak
    grant_row = t_audit.locator('[data-action="ROLE_ASSIGNMENT_GRANTED"]').first
    expect(grant_row).to_be_visible()
    expect(grant_row).to_contain_text("demo_organizer")
    grant_log_id = grant_row.get_attribute("data-log-id")
    assert grant_log_id is not None
    diff_table = t_audit.locator(f'[data-testid="tournament-audit-diff-{grant_log_id}"]')
    expect(diff_table).to_be_visible()
    expect(diff_table).to_contain_text("Trước (Before)")
    expect(diff_table).to_contain_text("Sau (After)")
    expect(t_audit).not_to_contain_text(ref_email)
    expect(t_audit).not_to_contain_text("@example.com")

    # Filter tournament audit logs by resource + action
    t_audit.locator('[data-testid="tournament-audit-filter-resource"]').select_option("role_assignment")
    t_audit.locator('[data-testid="tournament-audit-filter-action"]').fill("ROLE_ASSIGNMENT_GRANTED")
    t_audit.locator('[data-testid="tournament-audit-filter-apply-btn"]').click()
    expect(t_audit.locator('[data-action="ROLE_ASSIGNMENT_GRANTED"]')).to_have_count(1)
    expect(t_audit.locator('[data-action="TOURNAMENT_STAGE_CREATED"]')).to_have_count(0)

    # Real backend 422 when since > until; preserves filter inputs and clears stale rows from previous filter
    t_audit.locator('[data-testid="tournament-audit-filter-since"]').fill("2026-12-31T10:00")
    t_audit.locator('[data-testid="tournament-audit-filter-until"]').fill("2026-01-01T10:00")
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/tournaments/{tid}/audit-logs") and r.request.method == "GET"
    ) as bad_filter_resp:
        t_audit.locator('[data-testid="tournament-audit-filter-apply-btn"]').click()
    assert bad_filter_resp.value.status == 422
    expect(t_audit.locator('[data-testid="tournament-audit-error-banner"]')).to_be_visible()
    expect(t_audit.locator('[data-testid="tournament-audit-list"]')).to_have_count(0)
    expect(t_audit.locator(".audit-log-card")).to_have_count(0)
    expect(t_audit.locator('[data-action="ROLE_ASSIGNMENT_GRANTED"]')).to_have_count(0)
    expect(t_audit.locator('[data-testid="tournament-audit-empty"]')).to_have_count(0)
    expect(t_audit.locator('[data-testid="tournament-audit-filter-since"]')).to_have_value("2026-12-31T10:00")
    expect(t_audit.locator('[data-testid="tournament-audit-filter-until"]')).to_have_value("2026-01-01T10:00")

    # Reset filters clears error and restores full tournament logs
    t_audit.locator('[data-testid="tournament-audit-filter-reset-btn"]').click()
    expect(t_audit.locator('[data-testid="tournament-audit-error-banner"]')).to_have_count(0)
    expect(t_audit.locator('[data-action="TOURNAMENT_STAGE_CREATED"]').first).to_be_visible()

    # Non-manager (referee) must NOT see tournament or admin audit sections
    ref_page = browser.new_page(viewport={"width": 1280, "height": 900})
    ref_page.set_default_timeout(10_000)
    try:
        ref_page.goto(app_base_url)
        login(ref_page, ref_user["username"], demo_password)
        open_tournament(ref_page, str(tid), tname)
        expect(ref_page.locator('[data-testid="tournament-audit-section"]')).to_have_count(0)
        expect(ref_page.locator('[data-testid="admin-audit-section"]')).to_have_count(0)
    finally:
        ref_page.close()

    # Admin global audit log: seed >10 logs so pagination is exercised, test filter + pagination + 390px viewport
    admin_token = _login_api(page, api_base_url, "demo_admin", demo_password)
    for idx in range(11):
        _api_request(
            page,
            "POST",
            f"{api_base_url}/organizations",
            token=admin_token,
            data={"name": f"AudPgOrg {unique_username(f'p{idx}')[-8:]}"},
        )

    admin_page = browser.new_page(viewport={"width": 1280, "height": 900})
    admin_page.set_default_timeout(10_000)
    try:
        admin_page.goto(app_base_url)
        login(admin_page, "demo_admin", demo_password)
        a_audit = admin_page.locator('[data-testid="admin-audit-section"]')
        expect(a_audit).to_be_visible()
        expect(a_audit.locator('[data-testid="admin-audit-pagination"]')).to_be_visible()
        expect(a_audit.locator('[data-testid="admin-audit-page-info"]')).to_contain_text("Trang 1 /")

        page1_ids = a_audit.locator(".audit-log-card").evaluate_all(
            "cards => cards.map(card => card.dataset.logId)"
        )
        assert len(page1_ids) == 10

        with admin_page.expect_response(
            lambda r: urlparse(r.url).path.endswith("/admin/audit-logs")
            and "offset=10" in r.url
            and r.request.method == "GET"
        ) as page2_resp:
            a_audit.locator('[data-testid="admin-audit-page-next"]').click()
        assert page2_resp.value.status == 200
        expect(a_audit.locator('[data-testid="admin-audit-page-info"]')).to_contain_text("Trang 2 /")
        expect(a_audit.locator('[data-testid="admin-audit-refreshing-indicator"]')).to_have_count(0)
        page2_ids = a_audit.locator(".audit-log-card").evaluate_all(
            "cards => cards.map(card => card.dataset.logId)"
        )
        assert len(page2_ids) >= 1
        assert set(page1_ids).isdisjoint(set(page2_ids)), "Audit log pagination returned duplicate rows across pages"

        # Filter admin audit by tournament_id + resource
        a_audit.locator('[data-testid="admin-audit-filter-tournament-id"]').fill(str(tid))
        a_audit.locator('[data-testid="admin-audit-filter-resource"]').select_option("role_assignment")
        a_audit.locator('[data-testid="admin-audit-filter-apply-btn"]').click()
        expect(a_audit.locator('[data-action="ROLE_ASSIGNMENT_GRANTED"]')).to_have_count(1)

        # 390px mobile viewport must not overflow horizontally
        admin_page.set_viewport_size({"width": 390, "height": 844})
        has_overflow = admin_page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        assert not has_overflow, "Admin Audit Log UI overflows horizontally at 390px viewport"
    finally:
        admin_page.close()


def test_team_org_edit_capabilities_409_preserve_input_and_tournament_delete(
    page: Page, browser, app_base_url: str, api_base_url: str, demo_password: str
):
    # 1) ADMIN creates & renames Organization, hits real 409 duplicate name preserving input,
    #    and verifies ORGANIZATION_UPDATED before/after diff in Admin Audit Log.
    login(page, "demo_admin", demo_password)
    admin_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert admin_token

    org_a_name = f"OrgAlpha {unique_username('orga')[-6:]}"
    org_b_name = f"OrgBeta {unique_username('orgb')[-6:]}"
    org_a_renamed = f"OrgAlphaV2 {unique_username('orgr')[-6:]}"

    _api_request(
        page,
        "POST",
        f"{api_base_url}/organizations",
        token=admin_token,
        data={"name": org_b_name},
    )

    org_section = page.locator('[data-testid="organizations-section"]')
    expect(org_section.locator('[data-testid="org-create-form"]')).to_be_visible()
    org_section.locator('[data-testid="org-create-name-input"]').fill(org_a_name)
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith("/organizations") and r.request.method == "POST"
    ) as create_org_resp:
        org_section.locator('[data-testid="org-create-submit-btn"]').click()
    assert create_org_resp.value.status == 201
    org_a_id = create_org_resp.value.json()["organization_id"]

    expect(org_section.locator('[data-testid="org-notice-banner"]')).to_contain_text(org_a_name)
    org_section.locator(f'[data-testid="org-view-btn-{org_a_id}"]').click()
    org_detail = org_section.locator('[data-testid="org-detail-panel"]')
    expect(org_detail).to_contain_text(org_a_name)

    # Duplicate organization name -> real 409 preserving input
    org_detail.locator('[data-testid="org-edit-open-btn"]').click()
    org_detail.locator('[data-testid="org-edit-name-input"]').fill(org_b_name)
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/organizations/{org_a_id}") and r.request.method == "PATCH"
    ) as dup_org_resp:
        org_detail.locator('[data-testid="org-edit-save-btn"]').click()
    assert dup_org_resp.value.status == 409
    expect(org_detail.locator('[data-testid="org-edit-error-banner"]')).to_be_visible()
    expect(org_detail.locator('[data-testid="org-edit-name-input"]')).to_have_value(org_b_name)

    # Valid rename -> 200 and visible in Admin Audit Log with before/after diff
    org_detail.locator('[data-testid="org-edit-name-input"]').fill(org_a_renamed)
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/organizations/{org_a_id}") and r.request.method == "PATCH"
    ) as ok_org_resp:
        org_detail.locator('[data-testid="org-edit-save-btn"]').click()
    assert ok_org_resp.value.status == 200
    expect(org_detail).to_contain_text(org_a_renamed)

    a_audit = page.locator('[data-testid="admin-audit-section"]')
    a_audit.locator('[data-testid="admin-audit-filter-resource"]').select_option("organization")
    a_audit.locator('[data-testid="admin-audit-filter-resource-id"]').fill(str(org_a_id))
    a_audit.locator('[data-testid="admin-audit-filter-apply-btn"]').click()
    org_upd_row = a_audit.locator('[data-action="ORGANIZATION_UPDATED"]').first
    expect(org_upd_row).to_be_visible()
    expect(org_upd_row).to_contain_text(org_a_name)
    expect(org_upd_row).to_contain_text(org_a_renamed)

    # 2) Team manager updates team profile, hits real 409 duplicate tag & real 409 locked game_id
    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    valorant_game = next(g for g in games if g["slug"] == "valorant")
    alt_game = next(g for g in games if g["slug"] != "valorant")

    mgr_page = browser.new_page(viewport={"width": 1280, "height": 900})
    mgr_page.set_default_timeout(10_000)
    try:
        mgr_page.goto(app_base_url)
        mgr_username = unique_username("teamedit")
        register_user(mgr_page, mgr_username)
        login(mgr_page, mgr_username)
        mgr_token = mgr_page.evaluate("localStorage.getItem('esports_access_token')")
        assert mgr_token

        # Non-admin must NOT see org create form
        expect(mgr_page.locator('[data-testid="org-create-form"]')).to_have_count(0)

        t1_name = f"EditTeam {unique_username('t1')[-6:]}"
        t1_tag = f"T{unique_username('g1')[-7:].upper()}"
        t2_name = f"OtherTeam {unique_username('t2')[-6:]}"
        t2_tag = f"O{unique_username('g2')[-7:].upper()}"

        create_team(mgr_page, t1_name, t1_tag)
        _other_user, other_token = _register_and_login_api(mgr_page, api_base_url, "othertm", demo_password)
        t2_created = _api_request(
            mgr_page,
            "POST",
            f"{api_base_url}/teams",
            token=other_token,
            data={"name": t2_name, "tag": t2_tag, "game_id": valorant_game["game_id"]},
        )
        t2_id = t2_created["team_id"]

        # Open Team 1 detail and edit name/tag/logo_url/game_id
        t1_card = mgr_page.locator(".team-list article").filter(has_text=t1_name)
        t1_id = t1_card.get_attribute("data-team-id")
        assert t1_id is not None
        t1_card.get_by_role("button", name="Xem đội").click()
        detail = mgr_page.locator(".team-detail")
        expect(detail.locator('[data-testid="team-edit-open-btn"]')).to_be_visible()
        detail.locator('[data-testid="team-edit-open-btn"]').click()

        updated_name = f"EditTeamV2 {unique_username('u1')[-6:]}"
        updated_tag = f"U{unique_username('u2')[-7:].upper()}"
        logo_url = "https://example.com/team-v2.png"

        detail.locator('[data-testid="team-edit-name-input"]').fill(updated_name)
        detail.locator('[data-testid="team-edit-tag-input"]').fill(updated_tag)
        detail.locator('[data-testid="team-edit-logo-input"]').fill(logo_url)
        detail.locator('[data-testid="team-edit-game-select"]').select_option(str(alt_game["game_id"]))
        with mgr_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{t1_id}") and r.request.method == "PATCH"
        ) as patch_ok:
            detail.locator('[data-testid="team-edit-save-btn"]').click()
        assert patch_ok.value.status == 200
        expect(detail.locator('[data-testid="team-edit-notice-banner"]')).to_be_visible()
        expect(detail.get_by_role("heading", name=updated_name)).to_be_visible()
        expect(detail.locator('[data-testid="team-profile-meta"]')).to_contain_text(alt_game["name"])
        expect(detail.locator('[data-testid="team-profile-meta"]')).to_contain_text(logo_url)

        # Switch game back to VALORANT so we can register it to a VALORANT tournament
        detail.locator('[data-testid="team-edit-open-btn"]').click()
        detail.locator('[data-testid="team-edit-game-select"]').select_option(str(valorant_game["game_id"]))
        with mgr_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{t1_id}") and r.request.method == "PATCH"
        ) as patch_back:
            detail.locator('[data-testid="team-edit-save-btn"]').click()
        assert patch_back.value.status == 200

        # Duplicate tag -> real 409 preserving input
        detail.locator('[data-testid="team-edit-open-btn"]').click()
        detail.locator('[data-testid="team-edit-tag-input"]').fill(t2_tag)
        with mgr_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{t1_id}") and r.request.method == "PATCH"
        ) as dup_tag_resp:
            detail.locator('[data-testid="team-edit-save-btn"]').click()
        assert dup_tag_resp.value.status == 409
        expect(detail.locator('[data-testid="team-edit-error-banner"]')).to_be_visible()
        expect(detail.locator('[data-testid="team-edit-tag-input"]')).to_have_value(t2_tag)

        # Restore valid tag in input; register team to an UPCOMING tournament via API while edit form stays open
        detail.locator('[data-testid="team-edit-tag-input"]').fill(updated_tag)
        org_token = _login_api(mgr_page, api_base_url, "demo_organizer", demo_password)
        t_ctx = _create_upcoming_tournament(mgr_page, api_base_url, org_token, prefix="tlock")
        _api_request(
            mgr_page,
            "POST",
            f"{api_base_url}/tournaments/{t_ctx['tournament_id']}/registrations",
            token=mgr_token,
            data={"team_id": int(t1_id)},
        )

        # Now try changing game_id along with an unsaved name draft -> real backend 409;
        # capabilities refresh disables game_id, reverts game_id to saved value matching header,
        # and preserves still-editable fields (name).
        final_name = f"LockedGameOK {unique_username('ok')[-6:]}"
        detail.locator('[data-testid="team-edit-name-input"]').fill(final_name)
        detail.locator('[data-testid="team-edit-game-select"]').select_option(str(alt_game["game_id"]))
        with mgr_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{t1_id}") and r.request.method == "PATCH"
        ) as lock_409_resp:
            detail.locator('[data-testid="team-edit-save-btn"]').click()
        assert lock_409_resp.value.status == 409
        expect(detail.locator('[data-testid="team-edit-error-banner"]')).to_be_visible()
        expect(detail.locator('[data-testid="team-edit-game-select"]')).to_be_disabled()
        expect(detail.locator('[data-testid="team-edit-game-select"]')).to_have_value(str(valorant_game["game_id"]))
        expect(detail.locator('[data-testid="team-edit-name-input"]')).to_have_value(final_name)
        expect(detail.locator('[data-testid="team-game-locked-hint"]')).to_be_visible()
        expect(detail.locator('[data-testid="team-org-locked-hint"]')).to_be_visible()

        # Check 390px viewport on team edit + organization section has no horizontal overflow
        mgr_page.set_viewport_size({"width": 390, "height": 844})
        has_overflow = mgr_page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        assert not has_overflow, "Team Edit / Organizations UI overflows horizontally at 390px viewport"
        mgr_page.set_viewport_size({"width": 1280, "height": 900})

        # Preserved editable name can be submitted immediately while locked game_id stays at saved value
        with mgr_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{t1_id}") and r.request.method == "PATCH"
        ) as name_ok_resp:
            detail.locator('[data-testid="team-edit-save-btn"]').click()
        assert name_ok_resp.value.status == 200
        expect(detail.get_by_role("heading", name=final_name)).to_be_visible()
        expect(detail.locator('[data-testid="team-profile-meta"]')).to_contain_text(valorant_game["name"])
    finally:
        mgr_page.close()

    # 2b) ADMIN locked organization_id 409: reverts organization_id to saved value while preserving editable name
    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_admin")
    t2_card = page.locator(".team-list article").filter(has_text=t2_name)
    t2_card.get_by_role("button", name="Xem đội").click()
    admin_team_detail = page.locator(".team-detail")
    admin_team_detail.locator('[data-testid="team-edit-open-btn"]').click()

    org_lock_name = f"LockedOrgOK {unique_username('olo')[-6:]}"
    admin_team_detail.locator('[data-testid="team-edit-name-input"]').fill(org_lock_name)
    admin_team_detail.locator('[data-testid="team-edit-org-select"]').select_option(str(org_a_id))

    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{t_ctx['tournament_id']}/registrations",
        token=other_token,
        data={"team_id": t2_id},
    )
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/teams/{t2_id}") and r.request.method == "PATCH"
    ) as org_409_resp:
        admin_team_detail.locator('[data-testid="team-edit-save-btn"]').click()
    assert org_409_resp.value.status == 409
    expect(admin_team_detail.locator('[data-testid="team-edit-error-banner"]')).to_be_visible()
    expect(admin_team_detail.locator('[data-testid="team-edit-org-select"]')).to_be_disabled()
    expect(admin_team_detail.locator('[data-testid="team-edit-org-select"]')).to_have_value("")
    expect(admin_team_detail.locator('[data-testid="team-edit-game-select"]')).to_be_disabled()
    expect(admin_team_detail.locator('[data-testid="team-edit-game-select"]')).to_have_value(
        str(valorant_game["game_id"])
    )
    expect(admin_team_detail.locator('[data-testid="team-edit-name-input"]')).to_have_value(org_lock_name)

    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith(f"/teams/{t2_id}") and r.request.method == "PATCH"
    ) as org_name_ok:
        admin_team_detail.locator('[data-testid="team-edit-save-btn"]').click()
    assert org_name_ok.value.status == 200
    expect(admin_team_detail.get_by_role("heading", name=org_lock_name)).to_be_visible()
    expect(admin_team_detail.locator('[data-testid="team-profile-meta"]')).to_contain_text("Độc lập")

    # 3) Non-manager viewer sees neither team edit nor org create/edit
    viewer_page = browser.new_page(viewport={"width": 1280, "height": 900})
    viewer_page.set_default_timeout(10_000)
    try:
        viewer_page.goto(app_base_url)
        viewer_card = viewer_page.locator(".team-list article").filter(has_text=final_name)
        viewer_card.get_by_role("button", name="Xem đội").click()
        expect(viewer_page.locator('[data-testid="team-edit-open-btn"]')).to_have_count(0)
        expect(viewer_page.locator('[data-testid="org-create-form"]')).to_have_count(0)
        viewer_page.locator(f'[data-testid="org-view-btn-{org_a_id}"]').click()
        expect(viewer_page.locator('[data-testid="org-detail-panel"]')).to_be_visible()
        expect(viewer_page.locator('[data-testid="org-edit-open-btn"]')).to_have_count(0)
    finally:
        viewer_page.close()

    # 4) Tournament Delete UI: 409 when data added concurrently, and 204 success on clean UPCOMING tournament
    org_page = browser.new_page(viewport={"width": 1280, "height": 900})
    org_page.set_default_timeout(10_000)
    try:
        org_page.goto(app_base_url)
        login(org_page, "demo_organizer", demo_password)
        org_token = org_page.evaluate("localStorage.getItem('esports_access_token')")
        assert org_token

        t_conflict = _create_upcoming_tournament(org_page, api_base_url, org_token, prefix="del409")
        t_clean = _create_upcoming_tournament(org_page, api_base_url, org_token, prefix="del204")

        org_page.reload()
        expect(org_page.locator(".profile")).to_contain_text("demo_organizer")

        # Open t_conflict -> delete button visible -> add stage via API -> click delete -> real 409
        open_tournament(org_page, str(t_conflict["tournament_id"]), t_conflict["tournament_name"])
        expect(org_page.locator('[data-testid="tournament-delete-btn"]')).to_be_visible()
        _api_request(
            org_page,
            "POST",
            f"{api_base_url}/tournaments/{t_conflict['tournament_id']}/stages",
            token=org_token,
            data={"name": "Blocker Stage", "sequence_order": 1},
        )
        org_page.once("dialog", lambda d: d.accept())
        with org_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{t_conflict['tournament_id']}")
            and r.request.method == "DELETE"
        ) as del_409_resp:
            org_page.locator('[data-testid="tournament-delete-btn"]').click()
        assert del_409_resp.value.status == 409
        expect(org_page.locator('[data-testid="tournament-delete-error-banner"]')).to_be_visible()
        expect(org_page.locator('[data-testid="tournament-delete-btn"]')).to_have_count(0)
        expect(org_page.locator('[data-testid="tournament-delete-unavailable-reason"]')).to_be_visible()

        # Open t_clean -> delete succeeds with real 204
        open_tournament(org_page, str(t_clean["tournament_id"]), t_clean["tournament_name"])
        expect(org_page.locator('[data-testid="tournament-delete-btn"]')).to_be_visible()
        org_page.once("dialog", lambda d: d.accept())
        with org_page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{t_clean['tournament_id']}")
            and r.request.method == "DELETE"
        ) as del_204_resp:
            org_page.locator('[data-testid="tournament-delete-btn"]').click()
        assert del_204_resp.value.status == 204
        expect(org_page.locator(".tournament-detail")).to_have_count(0)
        expect(org_page.locator(".message.success")).to_contain_text("Đã xóa giải đấu")
    finally:
        org_page.close()


def test_audit_and_team_edit_anti_stale_guards_double_submit_and_401(
    page: Page, api_base_url: str, demo_password: str
):
    login(page, "demo_organizer", demo_password)
    org_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert org_token

    t_a = _create_upcoming_tournament(page, api_base_url, org_token, prefix="stla")
    t_b = _create_upcoming_tournament(page, api_base_url, org_token, prefix="stlb")
    # Add a distinctive stage in Tournament A so Tournament A has STAGE_CREATED while Tournament B does not
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{t_a['tournament_id']}/stages",
        token=org_token,
        data={"name": "Stale Stage A", "sequence_order": 1},
    )

    page.reload()
    expect(page.locator(".profile")).to_contain_text("demo_organizer")

    # 1) Anti-stale guard for Tournament Audit Log on tournament switch
    held_audit_routes: list = []
    audit_released = False
    audit_a_pattern = f"**/tournaments/{t_a['tournament_id']}/audit-logs*"

    def hold_audit_a(route):
        if audit_released or route.request.method != "GET":
            route.continue_()
            return
        resp = route.fetch()
        held_audit_routes.append((route, resp))

    page.route(audit_a_pattern, hold_audit_a)
    try:
        open_tournament(page, str(t_a["tournament_id"]), t_a["tournament_name"])
        wait_for_held_request(page, held_audit_routes, expected_count=1)

        # Switch to Tournament B while Tournament A's audit request is still held
        open_tournament(page, str(t_b["tournament_id"]), t_b["tournament_name"])
        t_audit = page.locator('[data-testid="tournament-audit-section"]')
        expect(t_audit.locator('[data-action="TOURNAMENT_CREATED"]').first).to_be_visible()
        expect(t_audit.locator('[data-action="TOURNAMENT_STAGE_CREATED"]')).to_have_count(0)

        # Release Tournament A's delayed audit response -> must NOT contaminate Tournament B
        audit_released = True
        route_obj, fetched_resp = held_audit_routes[0]
        with page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/tournaments/{t_a['tournament_id']}/audit-logs")
        ):
            route_obj.fulfill(response=fetched_resp)
    finally:
        page.unroute(audit_a_pattern, hold_audit_a)

    page.wait_for_timeout(300)
    expect(page.locator('[data-testid="tournament-audit-section"] [data-action="TOURNAMENT_STAGE_CREATED"]')).to_have_count(0)

    # 2) 401 session expiry on Audit Log reloads cleanly to logged-out state
    audit_b_pattern = f"**/tournaments/{t_b['tournament_id']}/audit-logs*"

    def mock_401(route):
        if route.request.method == "GET":
            route.fulfill(
                status=401,
                content_type="application/json",
                body='{"detail":"Phiên đăng nhập đã hết hạn"}',
            )
            return
        route.continue_()

    page.route(audit_b_pattern, mock_401)
    try:
        page.locator('[data-testid="tournament-audit-reload-btn"]').click()
        expect(page.locator(".message.error")).to_contain_text("Phiên đăng nhập đã hết hạn")
        expect(page.locator('[data-testid="tournament-audit-section"]')).to_have_count(0)
    finally:
        page.unroute(audit_b_pattern, mock_401)

    # 3) Team Edit double-submit guard + anti-stale on switching team while PATCH is in-flight
    stale_mgr = unique_username("stlmgr")
    register_user(page, stale_mgr)
    login(page, stale_mgr)

    games = _api_request(page, "GET", f"{api_base_url}/catalog/games")
    valorant_game_id = next(g["game_id"] for g in games if g["slug"] == "valorant")

    team_x_name = f"StaleTeamX {unique_username('stx')[-6:]}"
    team_x_tag = f"X{unique_username('tx')[-7:].upper()}"
    team_y_name = f"StaleTeamY {unique_username('sty')[-6:]}"
    team_y_tag = f"Y{unique_username('ty')[-7:].upper()}"

    create_team(page, team_x_name, team_x_tag)
    _other_u, other_tok = _register_and_login_api(page, api_base_url, "stly", demo_password)
    _api_request(
        page,
        "POST",
        f"{api_base_url}/teams",
        token=other_tok,
        data={"name": team_y_name, "tag": team_y_tag, "game_id": valorant_game_id},
    )
    page.reload()
    expect(page.locator(".profile")).to_contain_text(stale_mgr)

    card_x = page.locator(".team-list article").filter(has_text=team_x_name)
    card_y = page.locator(".team-list article").filter(has_text=team_y_name)
    expect(card_x).to_be_visible()
    expect(card_y).to_be_visible()
    team_x_id = card_x.get_attribute("data-team-id")
    assert team_x_id is not None

    card_x.get_by_role("button", name="Xem đội").click()
    detail = page.locator(".team-detail")
    detail.locator('[data-testid="team-edit-open-btn"]').click()
    detail.locator('[data-testid="team-edit-name-input"]').fill(f"{team_x_name} Renamed")

    held_patch_routes: list = []
    patch_released = False
    patch_x_pattern = f"**/teams/{team_x_id}"

    def hold_patch_x(route):
        if patch_released or route.request.method != "PATCH":
            route.continue_()
            return
        resp = route.fetch()
        held_patch_routes.append((route, resp))

    page.route(patch_x_pattern, hold_patch_x)
    try:
        detail.locator('[data-testid="team-edit-save-btn"]').click()
        wait_for_held_request(page, held_patch_routes, expected_count=1)
        expect(detail.locator('[data-testid="team-edit-save-btn"]')).to_be_disabled()

        # Dispatch synthetic submit while request is in-flight -> double-submit guard blocks 2nd PATCH
        detail.locator('[data-testid="team-edit-form"]').evaluate(
            "form => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))"
        )
        page.wait_for_timeout(150)
        assert len(held_patch_routes) == 1, f"Expected 1 PATCH request, got {len(held_patch_routes)}"

        # Switch to Team Y while Team X's PATCH is still in-flight
        card_y.get_by_role("button", name="Xem đội").click()
        expect(detail.get_by_role("heading", name=team_y_name)).to_be_visible()

        # Release Team X's PATCH -> must NOT contaminate Team Y or show Team X notice on Team Y
        patch_released = True
        route_obj, fetched_resp = held_patch_routes[0]
        with page.expect_response(
            lambda r: urlparse(r.url).path.endswith(f"/teams/{team_x_id}") and r.request.method == "PATCH"
        ):
            route_obj.fulfill(response=fetched_resp)
    finally:
        page.unroute(patch_x_pattern, hold_patch_x)

    page.wait_for_timeout(300)
    expect(detail.get_by_role("heading", name=team_y_name)).to_be_visible()
    expect(detail.locator('[data-testid="team-edit-notice-banner"]')).to_have_count(0)
