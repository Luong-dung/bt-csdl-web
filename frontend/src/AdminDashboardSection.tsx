import { FormEvent, useEffect, useRef, useState } from "react";

export type AdminCapabilities = {
  can_view_dashboard: boolean;
  can_manage_catalog: boolean;
  can_manage_roles: boolean;
  can_view_audit: boolean;
  can_create_organization: boolean;
};

export type AdminDashboardMatchTeam = {
  team_id: number;
  name: string;
};

export type AdminDashboardPendingMatch = {
  match_id: number;
  tournament_id: number;
  tournament_name: string;
  stage_id: number;
  stage_name: string;
  round_no: number;
  status: "PENDING" | "ONGOING";
  scheduled_at: string | null;
  team1: AdminDashboardMatchTeam | null;
  team2: AdminDashboardMatchTeam | null;
};

export type AdminDashboardData = {
  capabilities: AdminCapabilities;
  users: {
    total: number;
    by_role: Record<string, number>;
  };
  teams_total: number;
  organizations_total: number;
  active_role_assignments: number;
  pending_registrations: number;
  tournaments: {
    total: number;
    by_status: Record<"UPCOMING" | "ONGOING" | "COMPLETED" | "CANCELLED", number>;
  };
  matches_awaiting_result: {
    total: number;
    ongoing: number;
    pending_ready: number;
    pending_tbd: number;
    items: AdminDashboardPendingMatch[];
  };
};

export type RoleAssignmentItem = {
  assignment_id: number;
  user_id: number;
  username: string;
  role: string;
  scope_type: "GLOBAL" | "TOURNAMENT" | "TEAM" | "ORGANIZATION";
  scope_id: number | null;
  granted_by: number | null;
  granted_at: string | null;
  revoked_by: number | null;
  revoked_at: string | null;
  active: boolean;
};

export type AdminUserCandidate = {
  user_id: number;
  username: string;
  real_name: string | null;
  role: string;
};

const USER_ROLE_ORDER = [
  "ADMIN",
  "ORGANIZER",
  "REFEREE",
  "TEAM_MANAGER",
  "PLAYER",
  "VIEWER",
] as const;

const TOURNAMENT_STATUS_META: ReadonlyArray<{
  status: "UPCOMING" | "ONGOING" | "COMPLETED" | "CANCELLED";
  label: string;
  tone: string;
}> = [
  { status: "UPCOMING", label: "Sắp diễn ra", tone: "upcoming" },
  { status: "ONGOING", label: "Đang diễn ra", tone: "ongoing" },
  { status: "COMPLETED", label: "Đã kết thúc", tone: "completed" },
  { status: "CANCELLED", label: "Đã hủy", tone: "cancelled" },
];

const GRANTABLE_ROLES = [
  "ADMIN",
  "ORGANIZER",
  "REFEREE",
  "TEAM_MANAGER",
  "VIEWER",
] as const;

const SCOPE_TYPES = [
  { value: "GLOBAL", label: "Toàn hệ thống (GLOBAL)" },
  { value: "TOURNAMENT", label: "Theo giải đấu (TOURNAMENT)" },
  { value: "TEAM", label: "Theo đội tuyển (TEAM)" },
  { value: "ORGANIZATION", label: "Theo tổ chức (ORGANIZATION)" },
] as const;

const ROLES_PER_PAGE = 10;

function extractErrorMessage(
  body: { detail?: string | { msg?: string }[] } | null,
  fallback: string
): string {
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg ?? "Dữ liệu không hợp lệ").join("; ");
  }
  return fallback;
}

function formatAdminTimestamp(isoValue: string | null): string {
  if (!isoValue) return "Chưa xếp lịch";
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return isoValue;
  return date.toLocaleString("vi-VN");
}

type AdminDashboardSectionProps = {
  apiBase: string;
  token: string;
  canView: boolean;
  capabilities: AdminCapabilities | null;
  onAuthExpired: () => void;
  onPermissionDenied?: (message: string) => void;
  onNavigateSection: (sectionId: string) => void;
  onFilterTournamentsByStatus: (
    status: "UPCOMING" | "ONGOING" | "COMPLETED" | "CANCELLED"
  ) => void;
  onOpenTournament: (tournamentId: number) => void;
  refreshSignal?: number;
};

export function AdminDashboardSection({
  apiBase,
  token,
  canView,
  capabilities,
  onAuthExpired,
  onPermissionDenied,
  onNavigateSection,
  onFilterTournamentsByStatus,
  onOpenTournament,
  refreshSignal = 0,
}: AdminDashboardSectionProps) {
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  const requestVersion = useRef(0);
  const mountedRef = useRef(true);
  const scopeKeyRef = useRef("");

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestVersion.current += 1;
    };
  }, []);

  const fetchDashboard = async () => {
    if (!token || !canView) return;
    const reqV = ++requestVersion.current;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${apiBase}/admin/dashboard`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!mountedRef.current || requestVersion.current !== reqV) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const msg = extractErrorMessage(
          body,
          "Không thể tải bảng điều khiển quản trị."
        );
        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        setData(null);
        setLoaded(true);
        setError(msg);
        if (res.status === 403) {
          onPermissionDenied?.(msg);
        }
        return;
      }

      const payload = (await res.json()) as AdminDashboardData;
      if (!mountedRef.current || requestVersion.current !== reqV) return;
      setData(payload);
      setLoaded(true);
    } catch (reason) {
      if (!mountedRef.current || requestVersion.current !== reqV) return;
      setData(null);
      setLoaded(true);
      setError(
        (reason as Error).message || "Không thể tải bảng điều khiển quản trị."
      );
    } finally {
      if (mountedRef.current && requestVersion.current === reqV) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const scopeChanged = scopeKeyRef.current !== token;
    scopeKeyRef.current = token;
    requestVersion.current += 1;

    if (scopeChanged) {
      setData(null);
      setLoaded(false);
      setError("");
      setLoading(false);
    } else if (!canView) {
      setData(null);
      setLoading(false);
    }

    if (token && canView) {
      void fetchDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, canView, refreshSignal]);

  if (!canView && !error) {
    return null;
  }

  const effectiveCaps: AdminCapabilities = data?.capabilities ??
    capabilities ?? {
      can_view_dashboard: canView,
      can_manage_catalog: false,
      can_manage_roles: false,
      can_view_audit: false,
      can_create_organization: false,
    };

  return (
    <section
      className="panel admin-dashboard-panel"
      id="admin-dashboard"
      data-testid="admin-dashboard-section"
    >
      <div className="section-header">
        <div>
          <span className="auth-overline">NEXUS ADMIN CONTROL</span>
          <h2>Bảng điều khiển Quản trị (ADMIN)</h2>
          <p className="muted small-text">
            Tổng quan hệ thống thời gian thực: người dùng, đội tuyển, giải đấu
            theo trạng thái, trận chờ kết quả và lối tắt quản trị theo quyền.
          </p>
        </div>
        {canView && (
          <div className="referees-header-actions">
            {loading && data !== null && (
              <span
                className="matches-refreshing-indicator"
                data-testid="admin-dashboard-refreshing-indicator"
              >
                <span className="spinner" /> Đang làm mới...
              </span>
            )}
            <button
              type="button"
              className="button secondary small"
              data-testid="admin-dashboard-reload-btn"
              disabled={loading}
              onClick={() => void fetchDashboard()}
            >
              Tải lại
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="error-banner" data-testid="admin-dashboard-error-banner">
          <span>{error}</span>
          {canView && (
            <button
              type="button"
              className="button secondary small"
              data-testid="admin-dashboard-retry-btn"
              disabled={loading}
              onClick={() => void fetchDashboard()}
            >
              Thử lại
            </button>
          )}
        </div>
      )}

      {!canView ? (
        <p
          className="muted small-text"
          data-testid="admin-dashboard-unavailable-reason"
        >
          Bạn không còn quyền truy cập bảng điều khiển quản trị.
        </p>
      ) : loading && !loaded ? (
        <p className="muted" data-testid="admin-dashboard-loading">
          <span className="spinner" /> Đang tải dữ liệu tổng quan hệ thống...
        </p>
      ) : data ? (
        <>
          {data.teams_total === 0 && data.tournaments.total === 0 && (
            <div
              className="notice-banner"
              data-testid="admin-dashboard-empty-data-banner"
            >
              Hệ thống hiện chưa có đội tuyển hoặc giải đấu nào. Bạn có thể khởi
              tạo danh mục hoặc giải đấu mới từ các lối tắt bên dưới.
            </div>
          )}

          <div
            className="admin-dashboard-kpis"
            data-testid="admin-dashboard-kpis"
          >
            <article className="admin-kpi-card" data-testid="admin-kpi-users">
              <div className="admin-kpi-top">
                <span className="admin-kpi-label">Người dùng hệ thống</span>
                <strong
                  className="admin-kpi-value"
                  data-testid="admin-kpi-users-total"
                >
                  {data.users.total}
                </strong>
              </div>
              <div className="admin-kpi-chips">
                {USER_ROLE_ORDER.map((role) => (
                  <span
                    key={role}
                    className="admin-kpi-chip"
                    data-testid={`admin-kpi-role-${role}`}
                  >
                    {role}: <strong>{data.users.by_role[role] ?? 0}</strong>
                  </span>
                ))}
              </div>
            </article>

            <article className="admin-kpi-card" data-testid="admin-kpi-teams">
              <div className="admin-kpi-top">
                <span className="admin-kpi-label">Đội tuyển & Tổ chức</span>
                <strong
                  className="admin-kpi-value"
                  data-testid="admin-kpi-teams-total"
                >
                  {data.teams_total}
                </strong>
              </div>
              <div className="admin-kpi-chips">
                <span
                  className="admin-kpi-chip"
                  data-testid="admin-kpi-orgs-total"
                >
                  Tổ chức: <strong>{data.organizations_total}</strong>
                </span>
                <span
                  className="admin-kpi-chip"
                  data-testid="admin-kpi-pending-regs"
                >
                  Đơn chờ duyệt: <strong>{data.pending_registrations}</strong>
                </span>
              </div>
              <button
                type="button"
                className="link-button admin-kpi-link"
                data-testid="admin-kpi-open-teams"
                onClick={() => onNavigateSection("teams")}
              >
                Xem danh sách đội →
              </button>
            </article>

            <article
              className="admin-kpi-card"
              data-testid="admin-kpi-tournaments"
            >
              <div className="admin-kpi-top">
                <span className="admin-kpi-label">Giải đấu theo trạng thái</span>
                <strong
                  className="admin-kpi-value"
                  data-testid="admin-kpi-tournaments-total"
                >
                  {data.tournaments.total}
                </strong>
              </div>
              <div className="admin-kpi-status-grid">
                {TOURNAMENT_STATUS_META.map((item) => (
                  <button
                    key={item.status}
                    type="button"
                    className={`admin-status-pill tone-${item.tone}`}
                    data-testid={`admin-kpi-status-${item.status}`}
                    onClick={() => onFilterTournamentsByStatus(item.status)}
                    title={`Lọc danh sách giải theo trạng thái ${item.status}`}
                  >
                    <span>{item.label}</span>
                    <strong>{data.tournaments.by_status[item.status] ?? 0}</strong>
                  </button>
                ))}
              </div>
            </article>

            <article
              className="admin-kpi-card"
              data-testid="admin-kpi-matches-awaiting"
            >
              <div className="admin-kpi-top">
                <span className="admin-kpi-label">Trận chờ kết quả</span>
                <strong
                  className="admin-kpi-value"
                  data-testid="admin-kpi-matches-awaiting-total"
                >
                  {data.matches_awaiting_result.total}
                </strong>
              </div>
              <div className="admin-kpi-chips">
                <span
                  className="admin-kpi-chip chip-ongoing"
                  data-testid="admin-kpi-matches-ongoing"
                >
                  Đang diễn ra:{" "}
                  <strong>{data.matches_awaiting_result.ongoing}</strong>
                </span>
                <span
                  className="admin-kpi-chip chip-ready"
                  data-testid="admin-kpi-matches-ready"
                >
                  Chờ bắt đầu:{" "}
                  <strong>{data.matches_awaiting_result.pending_ready}</strong>
                </span>
                <span
                  className="admin-kpi-chip"
                  data-testid="admin-kpi-matches-tbd"
                >
                  Chờ nhánh TBD:{" "}
                  <strong>{data.matches_awaiting_result.pending_tbd}</strong>
                </span>
              </div>
            </article>
          </div>

          <div
            className="admin-shortcuts-bar"
            data-testid="admin-dashboard-shortcuts"
          >
            <div className="admin-shortcuts-title">
              <strong>Lối tắt quản trị nhanh</strong>
              <span className="muted small-text">
                Kích hoạt theo quyền thực tế từ role_permissions
              </span>
            </div>
            <div className="admin-shortcuts-actions">
              <button
                type="button"
                className="button secondary small admin-shortcut-btn"
                data-testid="admin-shortcut-catalog"
                disabled={!effectiveCaps.can_manage_catalog}
                title={
                  effectiveCaps.can_manage_catalog
                    ? "Di chuyển tới Quản trị Danh mục"
                    : "Tài khoản không có quyền catalog.manage"
                }
                onClick={() => onNavigateSection("catalog")}
              >
                ⚙ Quản trị Danh mục (Catalog)
              </button>
              <button
                type="button"
                className="button secondary small admin-shortcut-btn"
                data-testid="admin-shortcut-roles"
                disabled={!effectiveCaps.can_manage_roles}
                title={
                  effectiveCaps.can_manage_roles
                    ? "Di chuyển tới Quản lý Phân quyền hệ thống"
                    : "Tài khoản không có quyền role_assignment.manage"
                }
                onClick={() => onNavigateSection("admin-roles")}
              >
                🔑 Phân quyền hệ thống ({data.active_role_assignments} hiệu lực)
              </button>
              <button
                type="button"
                className="button secondary small admin-shortcut-btn"
                data-testid="admin-shortcut-audit"
                disabled={!effectiveCaps.can_view_audit}
                title={
                  effectiveCaps.can_view_audit
                    ? "Di chuyển tới Nhật ký kiểm toán hệ thống"
                    : "Tài khoản không có quyền audit_log.view_all"
                }
                onClick={() => onNavigateSection("audit-logs")}
              >
                📋 Nhật ký kiểm toán (Audit Log)
              </button>
            </div>
          </div>

          <div
            className="admin-pending-matches-box"
            data-testid="admin-dashboard-pending-matches"
          >
            <div className="admin-pending-matches-header">
              <h3>
                Trận đấu đang chờ kết quả ({data.matches_awaiting_result.total})
              </h3>
              {data.matches_awaiting_result.total >
                data.matches_awaiting_result.items.length && (
                <span className="muted small-text">
                  Hiển thị {data.matches_awaiting_result.items.length}/
                  {data.matches_awaiting_result.total} trận ưu tiên xử lý trước
                </span>
              )}
            </div>

            {data.matches_awaiting_result.items.length === 0 ? (
              <p
                className="muted small-text"
                data-testid="admin-dashboard-pending-matches-empty"
              >
                Hiện không có trận đấu nào đang chờ kết quả.
              </p>
            ) : (
              <div className="admin-pending-match-list">
                {data.matches_awaiting_result.items.map((item) => (
                  <div
                    key={item.match_id}
                    className="admin-pending-match-row"
                    data-testid={`admin-pending-match-row-${item.match_id}`}
                  >
                    <div className="admin-pending-match-main">
                      <div className="admin-pending-match-badges">
                        <span
                          className={`admin-match-badge status-${item.status.toLowerCase()}`}
                        >
                          {item.status === "ONGOING"
                            ? "ĐANG DIỄN RA"
                            : "CHỜ KẾT QUẢ"}
                        </span>
                        <strong className="admin-pending-tournament">
                          {item.tournament_name}
                        </strong>
                        <span className="muted small-text">
                          {item.stage_name} · Vòng {item.round_no}
                        </span>
                      </div>
                      <div className="admin-pending-match-teams">
                        <span>
                          <strong>{item.team1?.name ?? "TBD"}</strong> vs{" "}
                          <strong>{item.team2?.name ?? "TBD"}</strong>
                        </span>
                        <span className="muted small-text">
                          Lịch: {formatAdminTimestamp(item.scheduled_at)}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="button secondary small"
                      data-testid={`admin-pending-match-open-${item.match_id}`}
                      onClick={() => onOpenTournament(item.tournament_id)}
                    >
                      Mở giải →
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}

type AdminRoleAssignmentsSectionProps = {
  apiBase: string;
  token: string;
  canManageRoles: boolean;
  onAuthExpired: () => void;
  onPermissionDenied?: (message: string) => void;
  onRolesChanged?: () => void;
};

export function AdminRoleAssignmentsSection({
  apiBase,
  token,
  canManageRoles,
  onAuthExpired,
  onPermissionDenied,
  onRolesChanged,
}: AdminRoleAssignmentsSectionProps) {
  const [assignments, setAssignments] = useState<RoleAssignmentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [listError, setListError] = useState("");
  const [notice, setNotice] = useState("");

  const [draftScopeFilter, setDraftScopeFilter] = useState("");
  const [appliedScopeFilter, setAppliedScopeFilter] = useState("");
  const [draftIncludeRevoked, setDraftIncludeRevoked] = useState(false);
  const [appliedIncludeRevoked, setAppliedIncludeRevoked] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searchSubmitted, setSearchSubmitted] = useState(false);
  const [candidates, setCandidates] = useState<AdminUserCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] =
    useState<AdminUserCandidate | null>(null);

  const [userIdInput, setUserIdInput] = useState("");
  const [roleCode, setRoleCode] = useState<string>("ORGANIZER");
  const [scopeType, setScopeType] = useState<string>("GLOBAL");
  const [scopeIdInput, setScopeIdInput] = useState("");
  const [grantLoading, setGrantLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [revokingId, setRevokingId] = useState<number | null>(null);

  const listVersion = useRef(0);
  const searchVersion = useRef(0);
  const grantInFlightRef = useRef(false);
  const revokeInFlightRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const scopeKeyRef = useRef("");
  const lastRequestedRef = useRef<{
    scopeFilter: string;
    includeRevoked: boolean;
    page: number;
  }>({
    scopeFilter: "",
    includeRevoked: false,
    page: 0,
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      listVersion.current += 1;
      searchVersion.current += 1;
    };
  }, []);

  const fetchAssignments = async (
    targetScope: string,
    targetIncludeRevoked: boolean,
    targetPage: number
  ) => {
    if (!token || !canManageRoles) return;
    lastRequestedRef.current = {
      scopeFilter: targetScope,
      includeRevoked: targetIncludeRevoked,
      page: targetPage,
    };
    const reqV = ++listVersion.current;
    setLoading(true);
    setListError("");

    const params = new URLSearchParams({
      offset: String(targetPage * ROLES_PER_PAGE),
      limit: String(ROLES_PER_PAGE),
      include_revoked: targetIncludeRevoked ? "true" : "false",
    });
    if (targetScope) {
      params.set("scope_type", targetScope);
    }

    try {
      const res = await fetch(`${apiBase}/admin/role-assignments?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!mountedRef.current || listVersion.current !== reqV) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const msg = extractErrorMessage(
          body,
          "Không thể tải danh sách phân quyền."
        );
        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        setAssignments([]);
        setTotal(0);
        setLoaded(true);
        setListError(msg);
        if (res.status === 403) {
          onPermissionDenied?.(msg);
        }
        return;
      }

      const totalHeader = res.headers.get("X-Total-Count");
      const items = (await res.json()) as RoleAssignmentItem[];
      if (!mountedRef.current || listVersion.current !== reqV) return;

      const parsedTotal =
        totalHeader !== null ? Number(totalHeader) : items.length;
      setAssignments(items);
      setTotal(Number.isNaN(parsedTotal) ? items.length : parsedTotal);
      setDraftScopeFilter(targetScope);
      setAppliedScopeFilter(targetScope);
      setDraftIncludeRevoked(targetIncludeRevoked);
      setAppliedIncludeRevoked(targetIncludeRevoked);
      setPage(targetPage);
      setLoaded(true);
    } catch (reason) {
      if (!mountedRef.current || listVersion.current !== reqV) return;
      setAssignments([]);
      setTotal(0);
      setLoaded(true);
      setListError(
        (reason as Error).message || "Không thể tải danh sách phân quyền."
      );
    } finally {
      if (mountedRef.current && listVersion.current === reqV) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const scopeChanged = scopeKeyRef.current !== token;
    scopeKeyRef.current = token;
    listVersion.current += 1;
    searchVersion.current += 1;

    if (scopeChanged) {
      grantInFlightRef.current = false;
      revokeInFlightRef.current = null;
      lastRequestedRef.current = {
        scopeFilter: "",
        includeRevoked: false,
        page: 0,
      };
      setAssignments([]);
      setTotal(0);
      setPage(0);
      setLoaded(false);
      setLoading(false);
      setListError("");
      setNotice("");
      setDraftScopeFilter("");
      setAppliedScopeFilter("");
      setDraftIncludeRevoked(false);
      setAppliedIncludeRevoked(false);
      setSearchQuery("");
      setSearchLoading(false);
      setSearchError("");
      setSearchSubmitted(false);
      setCandidates([]);
      setSelectedCandidate(null);
      setUserIdInput("");
      setRoleCode("ORGANIZER");
      setScopeType("GLOBAL");
      setScopeIdInput("");
      setGrantLoading(false);
      setFormError("");
      setRevokingId(null);
    } else if (!canManageRoles) {
      setAssignments([]);
      setTotal(0);
      setLoading(false);
    }

    if (token && canManageRoles) {
      void fetchAssignments(
        scopeChanged ? "" : appliedScopeFilter,
        scopeChanged ? false : appliedIncludeRevoked,
        scopeChanged ? 0 : page
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, canManageRoles]);

  const handleSearchUsers = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canManageRoles) return;
    const trimmed = searchQuery.trim();
    if (trimmed.length < 2) {
      setSearchError("Nhập ít nhất 2 ký tự để tìm tài khoản.");
      setCandidates([]);
      setSearchSubmitted(false);
      return;
    }

    const reqV = ++searchVersion.current;
    setSearchLoading(true);
    setSearchError("");
    try {
      const params = new URLSearchParams({ q: trimmed, limit: "8" });
      const res = await fetch(`${apiBase}/admin/users/search?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!mountedRef.current || searchVersion.current !== reqV) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const msg = extractErrorMessage(body, "Không thể tìm kiếm người dùng.");
        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        setCandidates([]);
        setSearchSubmitted(false);
        setSearchError(msg);
        if (res.status === 403) {
          onPermissionDenied?.(msg);
        }
        return;
      }

      const items = (await res.json()) as AdminUserCandidate[];
      if (!mountedRef.current || searchVersion.current !== reqV) return;
      setCandidates(items);
      setSearchSubmitted(true);
    } catch (reason) {
      if (!mountedRef.current || searchVersion.current !== reqV) return;
      setCandidates([]);
      setSearchSubmitted(false);
      setSearchError(
        (reason as Error).message || "Không thể tìm kiếm người dùng."
      );
    } finally {
      if (mountedRef.current && searchVersion.current === reqV) {
        setSearchLoading(false);
      }
    }
  };

  const handleGrantRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canManageRoles) return;
    if (grantInFlightRef.current || grantLoading) return;

    const trimmedUser = userIdInput.trim();
    if (!/^[1-9]\d*$/.test(trimmedUser)) {
      setFormError("ID người nhận quyền (user_id) phải là số nguyên dương.");
      return;
    }

    let parsedScopeId: number | null = null;
    if (scopeType !== "GLOBAL") {
      const trimmedScope = scopeIdInput.trim();
      if (!/^[1-9]\d*$/.test(trimmedScope)) {
        setFormError(
          `Phạm vi ${scopeType} bắt buộc nhập ID phạm vi (scope_id) là số nguyên dương.`
        );
        return;
      }
      parsedScopeId = Number(trimmedScope);
    }

    grantInFlightRef.current = true;
    const startingToken = token;
    setGrantLoading(true);
    setFormError("");
    setNotice("");

    try {
      const res = await fetch(`${apiBase}/admin/role-assignments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${startingToken}`,
        },
        body: JSON.stringify({
          user_id: Number(trimmedUser),
          role: roleCode,
          scope_type: scopeType,
          scope_id: parsedScopeId,
        }),
      });
      if (!mountedRef.current || scopeKeyRef.current !== startingToken) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const msg = extractErrorMessage(body, "Không thể cấp phân quyền.");
        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        setFormError(msg);
        if (res.status === 403) {
          onPermissionDenied?.(msg);
        }
        return;
      }

      const created = (await res.json()) as RoleAssignmentItem;
      if (!mountedRef.current || scopeKeyRef.current !== startingToken) return;

      setNotice(
        `Đã cấp quyền ${created.role} (${created.scope_type}${
          created.scope_id !== null ? ` #${created.scope_id}` : ""
        }) cho ${created.username} (User #${created.user_id}).`
      );
      setSelectedCandidate(null);
      setUserIdInput("");
      setScopeIdInput("");
      await fetchAssignments(appliedScopeFilter, appliedIncludeRevoked, 0);
      onRolesChanged?.();
    } catch (reason) {
      if (!mountedRef.current || scopeKeyRef.current !== startingToken) return;
      setFormError((reason as Error).message || "Không thể cấp phân quyền.");
    } finally {
      grantInFlightRef.current = false;
      if (mountedRef.current && scopeKeyRef.current === startingToken) {
        setGrantLoading(false);
      }
    }
  };

  const handleRevokeRole = async (assignmentId: number) => {
    if (!token || !canManageRoles) return;
    if (revokeInFlightRef.current !== null || revokingId !== null) return;

    revokeInFlightRef.current = assignmentId;
    const startingToken = token;
    setRevokingId(assignmentId);
    setFormError("");
    setNotice("");

    try {
      const res = await fetch(
        `${apiBase}/admin/role-assignments/${assignmentId}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${startingToken}` },
        }
      );
      if (!mountedRef.current || scopeKeyRef.current !== startingToken) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const msg = extractErrorMessage(body, "Không thể thu hồi phân quyền.");
        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        if (res.status === 409) {
          setNotice("Phân quyền này đã được thu hồi trước đó.");
          await fetchAssignments(
            appliedScopeFilter,
            appliedIncludeRevoked,
            page
          );
          onRolesChanged?.();
          return;
        }
        setFormError(msg);
        if (res.status === 403) {
          onPermissionDenied?.(msg);
        }
        return;
      }

      setNotice(`Đã thu hồi phân quyền #${assignmentId}.`);
      const nextPage = page > 0 && assignments.length === 1 ? page - 1 : page;
      await fetchAssignments(
        appliedScopeFilter,
        appliedIncludeRevoked,
        nextPage
      );
      onRolesChanged?.();
    } catch (reason) {
      if (!mountedRef.current || scopeKeyRef.current !== startingToken) return;
      setFormError(
        (reason as Error).message || "Không thể thu hồi phân quyền."
      );
    } finally {
      revokeInFlightRef.current = null;
      if (mountedRef.current && scopeKeyRef.current === startingToken) {
        setRevokingId(null);
      }
    }
  };

  if (!canManageRoles && !listError && !formError) {
    return null;
  }

  const totalPages = Math.max(1, Math.ceil(total / ROLES_PER_PAGE));

  return (
    <section
      className="panel admin-roles-panel"
      id="admin-roles"
      data-testid="admin-roles-section"
    >
      <div className="section-header">
        <div>
          <span className="auth-overline">ROLE ASSIGNMENTS</span>
          <h2>
            Phân quyền Hệ thống ({total}{" "}
            {appliedIncludeRevoked ? "bản ghi" : "đang hiệu lực"})
          </h2>
          <p className="muted small-text">
            Cấp phát và thu hồi vai trò theo phạm vi GLOBAL / TOURNAMENT / TEAM
            / ORGANIZATION. Email tài khoản không được hiển thị.
          </p>
        </div>
        {canManageRoles && (
          <div className="referees-header-actions">
            <div className="referees-toggle-label">
              <input
                id="admin-role-include-revoked"
                type="checkbox"
                data-testid="admin-role-include-revoked-toggle"
                checked={draftIncludeRevoked}
                disabled={loading}
                onChange={(e) => {
                  const next = e.target.checked;
                  setDraftIncludeRevoked(next);
                  void fetchAssignments(appliedScopeFilter, next, 0);
                }}
              />
              <label htmlFor="admin-role-include-revoked">
                Hiện cả phân quyền đã thu hồi
              </label>
            </div>
            <button
              type="button"
              className="button secondary small"
              data-testid="admin-role-reload-btn"
              disabled={loading}
              onClick={() =>
                void fetchAssignments(
                  appliedScopeFilter,
                  appliedIncludeRevoked,
                  page
                )
              }
            >
              Tải lại
            </button>
          </div>
        )}
      </div>

      {notice && (
        <div className="notice-banner" data-testid="admin-role-notice-banner">
          {notice}
        </div>
      )}

      {listError && (
        <div className="error-banner" data-testid="admin-role-error-banner">
          <span>{listError}</span>
          {canManageRoles && (
            <button
              type="button"
              className="button secondary small"
              data-testid="admin-role-retry-btn"
              disabled={loading}
              onClick={() =>
                void fetchAssignments(
                  lastRequestedRef.current.scopeFilter,
                  lastRequestedRef.current.includeRevoked,
                  lastRequestedRef.current.page
                )
              }
            >
              Thử lại
            </button>
          )}
        </div>
      )}

      {formError && (
        <div
          className="error-banner"
          data-testid="admin-role-form-error-banner"
        >
          {formError}
        </div>
      )}

      {!canManageRoles ? (
        <p
          className="muted small-text"
          data-testid="admin-roles-unavailable-reason"
        >
          Bạn không còn quyền quản lý phân quyền hệ thống.
        </p>
      ) : (
        <>
          <div
            className="referee-grant-panel"
            data-testid="admin-role-grant-panel"
          >
            <form
              className="referee-search-form"
              noValidate
              onSubmit={(e) => void handleSearchUsers(e)}
            >
              <div className="referee-search-row">
                <div className="referee-search-field">
                  <label htmlFor="admin-role-user-search">
                    Tìm tài khoản nhận quyền (username / họ tên)
                  </label>
                  <input
                    id="admin-role-user-search"
                    type="text"
                    placeholder="Nhập tối thiểu 2 ký tự, ví dụ: demo_"
                    data-testid="admin-role-search-input"
                    value={searchQuery}
                    disabled={searchLoading || grantLoading}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="button secondary small"
                  data-testid="admin-role-search-btn"
                  disabled={searchLoading || grantLoading}
                >
                  {searchLoading ? "Đang tìm..." : "Tìm tài khoản"}
                </button>
              </div>
              {searchError && (
                <p
                  className="muted small-text text-danger"
                  data-testid="admin-role-search-error"
                >
                  {searchError}
                </p>
              )}
              {searchSubmitted && candidates.length === 0 && !searchError && (
                <p
                  className="muted small-text"
                  data-testid="admin-role-search-empty"
                >
                  Không tìm thấy tài khoản phù hợp.
                </p>
              )}
              {candidates.length > 0 && (
                <div
                  className="referee-candidate-list"
                  data-testid="admin-role-candidates"
                >
                  {candidates.map((cand) => (
                    <div
                      key={cand.user_id}
                      className={`referee-candidate-item ${
                        selectedCandidate?.user_id === cand.user_id
                          ? "is-selected"
                          : ""
                      }`}
                    >
                      <div className="referee-candidate-info">
                        <strong>{cand.username}</strong>
                        {cand.real_name && (
                          <span className="muted small-text">
                            ({cand.real_name})
                          </span>
                        )}
                        <span className="referee-id-pill">#{cand.user_id}</span>
                        <span className="referee-id-pill">{cand.role}</span>
                      </div>
                      <button
                        type="button"
                        className="button secondary small"
                        data-testid={`admin-role-select-user-${cand.user_id}`}
                        disabled={grantLoading}
                        onClick={() => {
                          setSelectedCandidate(cand);
                          setUserIdInput(String(cand.user_id));
                          setFormError("");
                        }}
                      >
                        Chọn #{cand.user_id}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </form>

            {selectedCandidate && (
              <div className="referee-selected-pill">
                <span>
                  Đã chọn: <strong>{selectedCandidate.username}</strong> (#
                  {selectedCandidate.user_id})
                </span>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setSelectedCandidate(null)}
                >
                  Bỏ chọn
                </button>
              </div>
            )}

            <form
              className="admin-role-grant-grid"
              noValidate
              data-testid="admin-role-grant-form"
              onSubmit={(e) => void handleGrantRole(e)}
            >
              <div className="admin-role-field">
                <label htmlFor="admin-role-user-id">
                  ID người nhận quyền (user_id){" "}
                  <span className="required">*</span>
                </label>
                <input
                  id="admin-role-user-id"
                  type="text"
                  inputMode="numeric"
                  placeholder="VD: 5"
                  data-testid="admin-role-user-id-input"
                  value={userIdInput}
                  disabled={grantLoading}
                  onChange={(e) => setUserIdInput(e.target.value)}
                />
              </div>

              <div className="admin-role-field">
                <label htmlFor="admin-role-code">Vai trò cấp phát</label>
                <select
                  id="admin-role-code"
                  data-testid="admin-role-code-select"
                  value={roleCode}
                  disabled={grantLoading}
                  onChange={(e) => setRoleCode(e.target.value)}
                >
                  {GRANTABLE_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>

              <div className="admin-role-field">
                <label htmlFor="admin-role-scope-type">Phạm vi áp dụng</label>
                <select
                  id="admin-role-scope-type"
                  data-testid="admin-role-scope-type-select"
                  value={scopeType}
                  disabled={grantLoading}
                  onChange={(e) => {
                    const next = e.target.value;
                    setScopeType(next);
                    if (next === "GLOBAL") {
                      setScopeIdInput("");
                    }
                  }}
                >
                  {SCOPE_TYPES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="admin-role-field">
                <label htmlFor="admin-role-scope-id">
                  ID phạm vi (scope_id)
                </label>
                <input
                  id="admin-role-scope-id"
                  type="text"
                  inputMode="numeric"
                  placeholder={
                    scopeType === "GLOBAL"
                      ? "Không dùng cho GLOBAL"
                      : "Nhập ID giải / đội / tổ chức"
                  }
                  data-testid="admin-role-scope-id-input"
                  value={scopeIdInput}
                  disabled={grantLoading || scopeType === "GLOBAL"}
                  onChange={(e) => setScopeIdInput(e.target.value)}
                />
              </div>

              <div className="admin-role-submit-wrap">
                <button
                  type="submit"
                  className="button small"
                  data-testid="admin-role-grant-btn"
                  disabled={grantLoading}
                >
                  {grantLoading ? "Đang cấp quyền..." : "Cấp quyền"}
                </button>
              </div>
            </form>
          </div>

          <div className="admin-role-filter-bar">
            <div className="admin-role-filter-group">
              <label htmlFor="admin-role-filter-scope">Lọc phạm vi:</label>
              <select
                id="admin-role-filter-scope"
                data-testid="admin-role-filter-scope-select"
                value={draftScopeFilter}
                disabled={loading}
                onChange={(e) => {
                  const next = e.target.value;
                  setDraftScopeFilter(next);
                  void fetchAssignments(next, appliedIncludeRevoked, 0);
                }}
              >
                <option value="">Tất cả phạm vi</option>
                {SCOPE_TYPES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.value}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {loading && !loaded ? (
            <p className="muted" data-testid="admin-role-loading">
              <span className="spinner" /> Đang tải danh sách phân quyền...
            </p>
          ) : assignments.length === 0 && !listError ? (
            <p className="muted small-text" data-testid="admin-role-empty">
              Chưa có phân quyền nào khớp bộ lọc hiện tại.
            </p>
          ) : (
            <div className="referee-list" data-testid="admin-role-list">
              {assignments.map((item) => (
                <div
                  key={item.assignment_id}
                  className={`referee-card ${
                    item.active ? "" : "is-revoked"
                  }`}
                  data-testid={`admin-role-row-${item.assignment_id}`}
                >
                  <div className="referee-card-info">
                    <div className="referee-card-title">
                      <span className="referee-id-pill">
                        #{item.assignment_id}
                      </span>
                      <strong>{item.role}</strong>
                      <span className="audit-resource-badge">
                        {item.scope_type}
                        {item.scope_id !== null ? ` #${item.scope_id}` : ""}
                      </span>
                      <span className="muted small-text">
                        {item.username} (User #{item.user_id})
                      </span>
                      <span
                        className={`referee-status-badge ${
                          item.active ? "status-active" : "status-revoked"
                        }`}
                      >
                        {item.active ? "ĐANG HIỆU LỰC" : "ĐÃ THU HỒI"}
                      </span>
                    </div>
                    <p className="muted small-text referee-card-meta">
                      Cấp lúc: {formatAdminTimestamp(item.granted_at)}
                      {item.granted_by !== null
                        ? ` · Bởi User #${item.granted_by}`
                        : ""}
                      {item.revoked_at
                        ? ` · Thu hồi lúc: ${formatAdminTimestamp(
                            item.revoked_at
                          )}`
                        : ""}
                    </p>
                  </div>
                  {item.active && (
                    <div className="referee-card-actions">
                      <button
                        type="button"
                        className="button secondary small danger-link"
                        data-testid={`admin-role-revoke-btn-${item.assignment_id}`}
                        disabled={
                          revokingId === item.assignment_id || grantLoading
                        }
                        onClick={() => void handleRevokeRole(item.assignment_id)}
                      >
                        {revokingId === item.assignment_id
                          ? "Đang thu hồi..."
                          : "Thu hồi"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {total > ROLES_PER_PAGE && (
            <div className="pagination" data-testid="admin-role-pagination">
              <button
                type="button"
                className="button secondary small"
                disabled={loading || page <= 0}
                onClick={() =>
                  void fetchAssignments(
                    appliedScopeFilter,
                    appliedIncludeRevoked,
                    page - 1
                  )
                }
              >
                ← Trang trước
              </button>
              <span className="muted small-text">
                Trang {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                className="button secondary small"
                disabled={loading || page + 1 >= totalPages}
                onClick={() =>
                  void fetchAssignments(
                    appliedScopeFilter,
                    appliedIncludeRevoked,
                    page + 1
                  )
                }
              >
                Trang sau →
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
