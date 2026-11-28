"""W48-05 Browser E2E: Admin Dashboard & System Role Assignments UI.

Validates:
1. Capability gating: hidden for non-admin users (ORGANIZER, VIEWER), visible for ADMIN,
   and partial-admin capability disabling on shortcuts.
2. Summary KPIs: users (total + by_role), teams & organizations & pending registrations,
   tournaments by status (with interactive status filter pill), and matches awaiting
   result (with "Mở giải →" action opening tournament detail).
3. Shortcuts to #catalog, #admin-roles, #audit-logs + user dropdown quick links.
4. System Role Assignments UI (#admin-roles): privacy-safe user search (no email leak),
   grant scoped role, real backend 409 conflict preserving input, live dashboard KPI
   refresh, scope filter, revoke role, and include_revoked toggle.
5. Responsive 390x844 layout with zero horizontal overflow.
6. Empty states, 500 error + retry clearing stale data, 403 mid-session revocation,
   401 session expiry logout, and anti-stale guard on logout during in-flight request.
"""
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, expect

from helpers import login, wait_for_held_request
from test_matches_ui import (
    _api_request,
    _register_and_login_api,
    _setup_locked_tournament_with_two_teams,
)


def _logout_ui(page: Page) -> None:
    page.get_by_role("button", name="Đăng xuất").click()
    expect(page.locator("[data-testid='sidebar-login']")).to_be_visible()
    close_btn = page.locator(".auth-modal-close")
    if close_btn.is_visible():
        close_btn.click()


def test_admin_dashboard_metrics_shortcuts_roles_and_390px(
    page: Page,
    app_base_url: str,
    api_base_url: str,
    demo_password: str,
):
    # 1. Non-admin users (ORGANIZER & VIEWER) must NOT see admin dashboard or roles
    login(page, "demo_organizer", demo_password)
    expect(page.locator('[data-testid="admin-dashboard-section"]')).to_have_count(0)
    expect(page.locator('[data-testid="admin-roles-section"]')).to_have_count(0)
    _logout_ui(page)

    login(page, "demo_viewer", demo_password)
    expect(page.locator('[data-testid="admin-dashboard-section"]')).to_have_count(0)
    expect(page.locator('[data-testid="admin-roles-section"]')).to_have_count(0)
    _logout_ui(page)

    # 2. Seed an ONGOING tournament with 1 ONGOING match and 1 PENDING match
    setup = _setup_locked_tournament_with_two_teams(
        page, api_base_url, demo_password
    )
    tid = setup["tournament_id"]
    tname = setup["tournament_name"]
    org_token = setup["organizer_token"]
    stage1_id = setup["stage_1"]["stage_id"]
    team1_id = setup["team_1"]["team_id"]
    team2_id = setup["team_2"]["team_id"]

    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/status",
        token=org_token,
        data={"status": "ONGOING"},
    )
    ongoing_match = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/matches",
        token=org_token,
        data={
            "stage_id": stage1_id,
            "round_no": 1,
            "team1_id": team1_id,
            "team2_id": team2_id,
            "scheduled_at": "2026-06-15T09:00:00Z",
        },
    )
    _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/matches/{ongoing_match['match_id']}/status",
        token=org_token,
        data={"status": "ONGOING"},
    )
    pending_match = _api_request(
        page,
        "POST",
        f"{api_base_url}/tournaments/{tid}/matches",
        token=org_token,
        data={
            "stage_id": stage1_id,
            "round_no": 2,
            "team1_id": team1_id,
            "team2_id": team2_id,
            "scheduled_at": "2026-06-15T12:00:00Z",
        },
    )
    _logout_ui(page)

    candidate_user, _ = _register_and_login_api(
        page, api_base_url, "admrole", demo_password
    )
    candidate_uid = candidate_user["user_id"]
    candidate_uname = candidate_user["username"]

    # 3. Login as demo_admin and verify dashboard metrics match backend API
    login(page, "demo_admin", demo_password)
    admin_token = page.evaluate("localStorage.getItem('esports_access_token')")
    assert admin_token

    expected = _api_request(
        page, "GET", f"{api_base_url}/admin/dashboard", token=admin_token
    )

    dashboard = page.locator('[data-testid="admin-dashboard-section"]')
    expect(dashboard).to_be_visible()
    expect(dashboard.locator('[data-testid="admin-kpi-users-total"]')).to_have_text(
        str(expected["users"]["total"])
    )
    expect(dashboard.locator('[data-testid="admin-kpi-teams-total"]')).to_have_text(
        str(expected["teams_total"])
    )
    expect(
        dashboard.locator('[data-testid="admin-kpi-tournaments-total"]')
    ).to_have_text(str(expected["tournaments"]["total"]))
    expect(
        dashboard.locator('[data-testid="admin-kpi-matches-awaiting-total"]')
    ).to_have_text(str(expected["matches_awaiting_result"]["total"]))

    # Privacy check: no email addresses leaked in dashboard or role assignments
    expect(dashboard).not_to_contain_text("@example.com")
    expect(dashboard).not_to_contain_text("@demo.local")

    # 4. Pending match row displays both ONGOING and PENDING matches & opens tournament
    ongoing_mid = ongoing_match["match_id"]
    pending_mid = pending_match["match_id"]
    expect(
        dashboard.locator(f'[data-testid="admin-pending-match-row-{ongoing_mid}"]')
    ).to_contain_text("ĐANG DIỄN RA")
    expect(
        dashboard.locator(f'[data-testid="admin-pending-match-row-{pending_mid}"]')
    ).to_contain_text("CHỜ KẾT QUẢ")

    dashboard.locator(
        f'[data-testid="admin-pending-match-open-{ongoing_mid}"]'
    ).click()
    expect(page.locator(".tournament-detail")).to_contain_text(tname)

    # Interactive tournament status filter pill filters #tournaments
    dashboard.locator('[data-testid="admin-kpi-status-ONGOING"]').click()
    expect(page.locator("#tournaments")).to_contain_text(tname)

    # 5. Shortcuts & top-right user dropdown quick links
    expect(dashboard.locator('[data-testid="admin-shortcut-catalog"]')).to_be_enabled()
    expect(dashboard.locator('[data-testid="admin-shortcut-roles"]')).to_be_enabled()
    expect(dashboard.locator('[data-testid="admin-shortcut-audit"]')).to_be_enabled()

    dashboard.locator('[data-testid="admin-shortcut-catalog"]').click()
    expect(page.locator("#catalog")).to_be_visible()

    dashboard.locator('[data-testid="admin-shortcut-audit"]').click()
    expect(page.locator("#audit-logs")).to_be_visible()

    page.locator(".ewc-user-block.is-authenticated").click()
    expect(
        page.locator('[data-testid="dropdown-admin-dashboard-btn"]')
    ).to_be_visible()
    page.locator('[data-testid="dropdown-admin-roles-btn"]').click()

    # 6. Admin Role Assignments (#admin-roles): search -> grant -> 409 -> revoke
    roles_sec = page.locator('[data-testid="admin-roles-section"]')
    expect(roles_sec).to_be_visible()
    expect(roles_sec).not_to_contain_text("@example.com")

    roles_sec.locator('[data-testid="admin-role-search-input"]').fill(
        candidate_uname[:12]
    )
    roles_sec.locator('[data-testid="admin-role-search-btn"]').click()
    cand_list = roles_sec.locator('[data-testid="admin-role-candidates"]')
    expect(cand_list).to_contain_text(candidate_uname)
    expect(cand_list).not_to_contain_text("@example.com")

    roles_sec.locator(
        f'[data-testid="admin-role-select-user-{candidate_uid}"]'
    ).click()
    expect(
        roles_sec.locator('[data-testid="admin-role-user-id-input"]')
    ).to_have_value(str(candidate_uid))

    roles_sec.locator('[data-testid="admin-role-code-select"]').select_option(
        "ORGANIZER"
    )
    roles_sec.locator('[data-testid="admin-role-scope-type-select"]').select_option(
        "TOURNAMENT"
    )
    roles_sec.locator('[data-testid="admin-role-scope-id-input"]').fill(str(tid))
    roles_sec.locator('[data-testid="admin-role-grant-btn"]').click()

    expect(
        roles_sec.locator('[data-testid="admin-role-notice-banner"]')
    ).to_contain_text(f"User #{candidate_uid}")

    # Dashboard active_role_assignments shortcut badge refreshes automatically
    expected_after_grant = expected["active_role_assignments"] + 1
    expect(
        dashboard.locator('[data-testid="admin-shortcut-roles"]')
    ).to_contain_text(f"({expected_after_grant} hiệu lực)")

    # Real backend 409 duplicate grant preserves inputs and shows form error
    roles_sec.locator('[data-testid="admin-role-user-id-input"]').fill(
        str(candidate_uid)
    )
    roles_sec.locator('[data-testid="admin-role-scope-id-input"]').fill(str(tid))
    with page.expect_response(
        lambda r: urlparse(r.url).path.endswith("/admin/role-assignments")
        and r.request.method == "POST"
    ) as dup_resp:
        roles_sec.locator('[data-testid="admin-role-grant-btn"]').click()
    assert dup_resp.value.status == 409
    expect(
        roles_sec.locator('[data-testid="admin-role-form-error-banner"]')
    ).to_be_visible()
    expect(
        roles_sec.locator('[data-testid="admin-role-user-id-input"]')
    ).to_have_value(str(candidate_uid))
    expect(
        roles_sec.locator('[data-testid="admin-role-scope-id-input"]')
    ).to_have_value(str(tid))

    # Filter by TOURNAMENT scope and revoke the granted assignment
    roles_sec.locator('[data-testid="admin-role-filter-scope-select"]').select_option(
        "TOURNAMENT"
    )
    granted_row = roles_sec.locator(".referee-card").filter(
        has_text=f"User #{candidate_uid}"
    )
    expect(granted_row).to_be_visible()
    row_test_id = granted_row.get_attribute("data-testid")
    assert row_test_id and row_test_id.startswith("admin-role-row-")
    assignment_id = row_test_id.replace("admin-role-row-", "")

    roles_sec.locator(
        f'[data-testid="admin-role-revoke-btn-{assignment_id}"]'
    ).click()
    expect(
        roles_sec.locator('[data-testid="admin-role-notice-banner"]')
    ).to_contain_text(f"Đã thu hồi phân quyền #{assignment_id}")
    expect(
        roles_sec.locator(f'[data-testid="admin-role-row-{assignment_id}"]')
    ).to_have_count(0)

    # Toggle include_revoked to inspect historical revoked row
    roles_sec.locator('[data-testid="admin-role-include-revoked-toggle"]').check()
    revoked_row = roles_sec.locator(
        f'[data-testid="admin-role-row-{assignment_id}"]'
    )
    expect(revoked_row).to_be_visible()
    expect(revoked_row).to_contain_text("ĐÃ THU HỒI")

    # 7. Responsive 390px check: zero horizontal document overflow
    page.set_viewport_size({"width": 390, "height": 844})
    dashboard.scroll_into_view_if_needed()
    expect(dashboard).to_be_visible()
    roles_sec.scroll_into_view_if_needed()
    expect(roles_sec).to_be_visible()
    has_overflow = page.evaluate(
        "document.documentElement.scrollWidth > window.innerWidth"
    )
    assert not has_overflow, "Horizontal overflow detected at 390px viewport!"


def test_admin_dashboard_empty_error_retry_401_403_and_anti_stale(
    page: Page,
    app_base_url: str,
    demo_password: str,
):
    login(page, "demo_admin", demo_password)
    dashboard = page.locator('[data-testid="admin-dashboard-section"]')
    expect(dashboard).to_be_visible()
    expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_be_visible()

    # 1. Partial admin capabilities + empty pending matches + empty business banner
    partial_caps = {
        "can_view_dashboard": True,
        "can_manage_catalog": False,
        "can_manage_roles": False,
        "can_view_audit": True,
        "can_create_organization": False,
    }
    empty_payload = {
        "capabilities": partial_caps,
        "users": {"total": 1, "by_role": {"ADMIN": 1}},
        "teams_total": 0,
        "organizations_total": 0,
        "active_role_assignments": 0,
        "pending_registrations": 0,
        "tournaments": {
            "total": 0,
            "by_status": {
                "UPCOMING": 0,
                "ONGOING": 0,
                "COMPLETED": 0,
                "CANCELLED": 0,
            },
        },
        "matches_awaiting_result": {
            "total": 0,
            "ongoing": 0,
            "pending_ready": 0,
            "pending_tbd": 0,
            "items": [],
        },
    }

    def handle_partial_caps(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(partial_caps),
        )

    def handle_empty_dashboard(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(empty_payload),
        )

    page.route("**/api/v1/admin/capabilities", handle_partial_caps)
    page.route("**/api/v1/admin/dashboard", handle_empty_dashboard)
    try:
        page.reload()
        expect(dashboard).to_be_visible()
        expect(
            dashboard.locator('[data-testid="admin-dashboard-empty-data-banner"]')
        ).to_be_visible()
        expect(
            dashboard.locator('[data-testid="admin-dashboard-pending-matches-empty"]')
        ).to_be_visible()
        expect(
            dashboard.locator('[data-testid="admin-shortcut-catalog"]')
        ).to_be_disabled()
        expect(
            dashboard.locator('[data-testid="admin-shortcut-roles"]')
        ).to_be_disabled()
        expect(
            dashboard.locator('[data-testid="admin-shortcut-audit"]')
        ).to_be_enabled()
        expect(page.locator('[data-testid="admin-roles-section"]')).to_have_count(0)
    finally:
        page.unroute("**/api/v1/admin/dashboard", handle_empty_dashboard)
        page.unroute("**/api/v1/admin/capabilities", handle_partial_caps)

    page.reload()
    expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_be_visible()

    # 2. Simulated 500 error clears stale KPIs and Retry recovers cleanly
    fail_once = {"should_fail": True}

    def handle_500_then_ok(route: Route) -> None:
        if fail_once["should_fail"]:
            fail_once["should_fail"] = False
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "Lỗi máy chủ tạm thời khi tải dashboard."}),
            )
        else:
            route.continue_()

    page.route("**/api/v1/admin/dashboard", handle_500_then_ok)
    try:
        dashboard.locator('[data-testid="admin-dashboard-reload-btn"]').click()
        expect(
            dashboard.locator('[data-testid="admin-dashboard-error-banner"]')
        ).to_contain_text("Lỗi máy chủ tạm thời khi tải dashboard.")
        expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_have_count(
            0
        )

        dashboard.locator('[data-testid="admin-dashboard-retry-btn"]').click()
        expect(
            dashboard.locator('[data-testid="admin-dashboard-error-banner"]')
        ).to_have_count(0)
        expect(
            dashboard.locator('[data-testid="admin-dashboard-kpis"]')
        ).to_be_visible()
    finally:
        page.unroute("**/api/v1/admin/dashboard", handle_500_then_ok)

    # 3. Simulated 403 revocation clears stale KPIs & shows unavailable reason
    revoked_caps = {
        "can_view_dashboard": False,
        "can_manage_catalog": False,
        "can_manage_roles": False,
        "can_view_audit": False,
        "can_create_organization": False,
    }

    def handle_403_dashboard(route: Route) -> None:
        route.fulfill(
            status=403,
            content_type="application/json",
            body=json.dumps({"detail": "Quyền quản trị đã bị thu hồi."}),
        )

    def handle_revoked_caps(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(revoked_caps),
        )

    page.route("**/api/v1/admin/dashboard", handle_403_dashboard)
    page.route("**/api/v1/admin/capabilities", handle_revoked_caps)
    try:
        dashboard.locator('[data-testid="admin-dashboard-reload-btn"]').click()
        expect(
            dashboard.locator('[data-testid="admin-dashboard-error-banner"]')
        ).to_contain_text("Quyền quản trị đã bị thu hồi.")
        expect(
            dashboard.locator('[data-testid="admin-dashboard-unavailable-reason"]')
        ).to_be_visible()
        expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_have_count(
            0
        )
    finally:
        page.unroute("**/api/v1/admin/dashboard", handle_403_dashboard)
        page.unroute("**/api/v1/admin/capabilities", handle_revoked_caps)

    page.reload()
    expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_be_visible()

    # 4. Anti-stale guard: logout while GET /admin/dashboard is held in-flight
    held_routes: list[Route] = []

    def hold_dashboard(route: Route) -> None:
        held_routes.append(route)

    page.route("**/api/v1/admin/dashboard", hold_dashboard)
    try:
        dashboard.locator('[data-testid="admin-dashboard-reload-btn"]').click()
        wait_for_held_request(page, held_routes, expected_count=1)
        _logout_ui(page)
        held_routes[0].fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(empty_payload),
        )
        page.wait_for_timeout(150)
        expect(page.locator('[data-testid="admin-dashboard-section"]')).to_have_count(
            0
        )
    finally:
        page.unroute("**/api/v1/admin/dashboard", hold_dashboard)

    # 5. 401 session expiry on /admin/dashboard logs user out cleanly
    login(page, "demo_admin", demo_password)
    expect(dashboard.locator('[data-testid="admin-dashboard-kpis"]')).to_be_visible()

    def handle_401_dashboard(route: Route) -> None:
        route.fulfill(
            status=401,
            content_type="application/json",
            body=json.dumps({"detail": "Token không hợp lệ hoặc đã hết hạn."}),
        )

    page.route("**/api/v1/admin/dashboard", handle_401_dashboard)
    try:
        dashboard.locator('[data-testid="admin-dashboard-reload-btn"]').click()
        expect(page.locator("[data-testid='sidebar-login']")).to_be_visible()
        expect(page.locator('[data-testid="admin-dashboard-section"]')).to_have_count(
            0
        )
    finally:
        page.unroute("**/api/v1/admin/dashboard", handle_401_dashboard)
