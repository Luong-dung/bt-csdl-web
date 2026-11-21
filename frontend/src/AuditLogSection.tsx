import { FormEvent, useEffect, useRef, useState } from "react";

export type AuditActor = {
  user_id: number;
  username: string;
};

export type AuditLogItem = {
  log_id: number;
  created_at: string | null;
  action: string;
  resource: string;
  resource_id: number | null;
  tournament_id: number | null;
  actor: AuditActor | null;
  details: unknown;
};

type AuditFilters = {
  resource: string;
  action: string;
  actor_id: string;
  resource_id: string;
  tournament_id: string;
  since: string;
  until: string;
};

const EMPTY_FILTERS: AuditFilters = {
  resource: "",
  action: "",
  actor_id: "",
  resource_id: "",
  tournament_id: "",
  since: "",
  until: "",
};

const AUDIT_LOGS_PER_PAGE = 10;

const ADMIN_RESOURCES = [
  "tournament",
  "tournament_registration",
  "tournament_roster",
  "tournament_stage",
  "match",
  "bracket",
  "role_assignment",
  "team",
  "team_membership",
  "organization",
  "publisher",
  "game",
  "area",
  "country",
];

const TOURNAMENT_RESOURCES = [
  "tournament",
  "tournament_registration",
  "tournament_roster",
  "tournament_stage",
  "match",
  "bracket",
  "role_assignment",
];

function localInputToIsoOffset(localValue: string): string | null {
  const trimmed = localValue.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return "__INVALID__";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absMinutes = Math.abs(offsetMinutes);
  const offHours = String(Math.floor(absMinutes / 60)).padStart(2, "0");
  const offMins = String(absMinutes % 60).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${sign}${offHours}:${offMins}`;
}

function formatAuditTime(isoValue: string | null): string {
  if (!isoValue) return "Chưa xác định";
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return isoValue;
  return date.toLocaleString("vi-VN");
}

function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Có (true)" : "Không (false)";
  if (typeof value === "number" || typeof value === "string") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

type AuditLogSectionProps = {
  apiBase: string;
  mode: "admin" | "tournament";
  tournamentId?: number;
  token: string;
  canView: boolean;
  prefix: "admin-audit" | "tournament-audit";
  title: string;
  subtitle: string;
  onAuthExpired: () => void;
  onPermissionDenied?: (message: string) => void;
  refreshSignal?: number;
};

export function AuditLogSection({
  apiBase,
  mode,
  tournamentId,
  token,
  canView,
  prefix,
  title,
  subtitle,
  onAuthExpired,
  onPermissionDenied,
  refreshSignal = 0,
}: AuditLogSectionProps) {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [draftFilters, setDraftFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<AuditFilters>(EMPTY_FILTERS);

  const requestVersion = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestVersion.current += 1;
    };
  }, []);

  const fetchLogs = async (filters: AuditFilters, targetPage: number) => {
    if (!token || !canView) return;
    if (mode === "tournament" && !tournamentId) return;

    const reqV = ++requestVersion.current;
    setLoading(true);
    setError("");

    const params = new URLSearchParams({
      offset: String(targetPage * AUDIT_LOGS_PER_PAGE),
      limit: String(AUDIT_LOGS_PER_PAGE),
    });

    if (filters.resource.trim()) params.set("resource", filters.resource.trim());
    if (filters.action.trim()) params.set("action", filters.action.trim());

    for (const [key, rawVal] of [
      ["actor_id", filters.actor_id],
      ["resource_id", filters.resource_id],
      ...(mode === "admin" ? [["tournament_id", filters.tournament_id]] : []),
    ] as const) {
      const trimmed = rawVal.trim();
      if (trimmed) {
        if (!/^[1-9]\d*$/.test(trimmed)) {
          setError(`Bộ lọc ${key} phải là số nguyên dương.`);
          setLoading(false);
          setLoaded(true);
          return;
        }
        params.set(key, trimmed);
      }
    }

    const sinceIso = localInputToIsoOffset(filters.since);
    if (sinceIso === "__INVALID__") {
      setError("Thời điểm 'Từ lúc' (since) không hợp lệ.");
      setLoading(false);
      setLoaded(true);
      return;
    }
    const untilIso = localInputToIsoOffset(filters.until);
    if (untilIso === "__INVALID__") {
      setError("Thời điểm 'Đến lúc' (until) không hợp lệ.");
      setLoading(false);
      setLoaded(true);
      return;
    }
    if (sinceIso) params.set("since", sinceIso);
    if (untilIso) params.set("until", untilIso);

    const endpoint =
      mode === "admin"
        ? `${apiBase}/admin/audit-logs?${params}`
        : `${apiBase}/tournaments/${tournamentId}/audit-logs?${params}`;

    try {
      const res = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!mountedRef.current || requestVersion.current !== reqV) return;

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          detail?: string | { msg?: string }[];
        } | null;
        const detail = body?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((item) => item.msg ?? "Bộ lọc không hợp lệ").join("; ")
              : "Không thể tải nhật ký hoạt động.";

        if (res.status === 401) {
          onAuthExpired();
          return;
        }
        if (res.status === 403) {
          setLogs([]);
          setTotal(0);
          setLoaded(true);
          setError(msg);
          onPermissionDenied?.(msg);
          return;
        }
        setLoaded(true);
        setError(msg);
        return;
      }

      const totalHeader = res.headers.get("X-Total-Count");
      const list = (await res.json()) as AuditLogItem[];
      if (!mountedRef.current || requestVersion.current !== reqV) return;

      const parsedTotal = totalHeader !== null ? Number(totalHeader) : list.length;
      setLogs(list);
      setTotal(Number.isNaN(parsedTotal) ? list.length : parsedTotal);
      setLoaded(true);
    } catch (reason) {
      if (!mountedRef.current || requestVersion.current !== reqV) return;
      setLoaded(true);
      setError((reason as Error).message || "Không thể tải nhật ký hoạt động.");
    } finally {
      if (mountedRef.current && requestVersion.current === reqV) {
        setLoading(false);
      }
    }
  };

  const scopeKeyRef = useRef("");

  // Reset and fetch whenever scope (mode/tournamentId/token) changes, or when canView becomes true.
  // Keep 403 error banner intact if canView flips from true -> false after a permission-denied reload.
  useEffect(() => {
    const scopeKey = `${mode}:${tournamentId ?? ""}:${token}`;
    const scopeChanged = scopeKeyRef.current !== scopeKey;
    scopeKeyRef.current = scopeKey;

    requestVersion.current += 1;
    if (scopeChanged) {
      setLogs([]);
      setTotal(0);
      setPage(0);
      setLoaded(false);
      setError("");
      setDraftFilters(EMPTY_FILTERS);
      setAppliedFilters(EMPTY_FILTERS);
    }
    if (canView && token && (mode === "admin" || Boolean(tournamentId))) {
      setLoaded(false);
      setError("");
      void fetchLogs(EMPTY_FILTERS, 0);
    }
  }, [mode, tournamentId, token, canView]);

  // Allow parent mutations to gently refresh the current page without clearing filters.
  useEffect(() => {
    if (refreshSignal <= 0) return;
    if (canView && token && (mode === "admin" || Boolean(tournamentId))) {
      void fetchLogs(appliedFilters, page);
    }
  }, [refreshSignal]);

  if (!canView && !error) return null;

  const handleApplyFilters = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const nextFilters = { ...draftFilters };
    setAppliedFilters(nextFilters);
    setPage(0);
    void fetchLogs(nextFilters, 0);
  };

  const handleResetFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(0);
    void fetchLogs(EMPTY_FILTERS, 0);
  };

  const handlePageChange = (nextPage: number) => {
    setPage(nextPage);
    void fetchLogs(appliedFilters, nextPage);
  };

  const resourceOptions = mode === "admin" ? ADMIN_RESOURCES : TOURNAMENT_RESOURCES;
  const hasActiveFilters = Object.values(appliedFilters).some((v) => v.trim() !== "");

  const renderDetails = (log: AuditLogItem) => {
    const details = log.details;
    if (!isPlainRecord(details) || Object.keys(details).length === 0) {
      return (
        <p className="muted small-text audit-legacy-note">
          Không có chi tiết bổ sung (log cũ / chưa xác định).
        </p>
      );
    }

    const hasBeforeAfter = "before" in details || "after" in details;
    const rawBefore = hasBeforeAfter ? details.before : undefined;
    const rawAfter = hasBeforeAfter ? details.after : undefined;
    const beforeObj = isPlainRecord(rawBefore) ? rawBefore : null;
    const afterObj = isPlainRecord(rawAfter) ? rawAfter : null;

    const metaEntries = Object.entries(details).filter(
      ([k]) => k !== "before" && k !== "after"
    );

    const diffKeys = hasBeforeAfter
      ? Array.from(
          new Set([
            ...(beforeObj ? Object.keys(beforeObj) : []),
            ...(afterObj ? Object.keys(afterObj) : []),
          ])
        )
      : [];

    const changeKind =
      hasBeforeAfter && beforeObj === null && afterObj !== null
        ? "Tạo mới"
        : hasBeforeAfter && beforeObj !== null && afterObj === null
          ? "Đã xóa"
          : hasBeforeAfter && beforeObj !== null && afterObj !== null
            ? "Cập nhật"
            : null;

    return (
      <div className="audit-details-box" data-testid={`${prefix}-details-${log.log_id}`}>
        {metaEntries.length > 0 && (
          <div className="audit-meta-chips">
            {changeKind && <span className="audit-kind-badge">{changeKind}</span>}
            {metaEntries.map(([key, val]) => (
              <span key={key} className="audit-meta-chip">
                <strong>{key}:</strong> {formatAuditValue(val)}
              </span>
            ))}
          </div>
        )}

        {hasBeforeAfter && diffKeys.length > 0 ? (
          <div className="audit-diff-table-wrap" data-testid={`${prefix}-diff-${log.log_id}`}>
            <table className="audit-diff-table">
              <thead>
                <tr>
                  <th>Trường</th>
                  <th>Trước (Before)</th>
                  <th>Sau (After)</th>
                </tr>
              </thead>
              <tbody>
                {diffKeys.map((field) => {
                  const bVal = beforeObj ? formatAuditValue(beforeObj[field]) : "—";
                  const aVal = afterObj ? formatAuditValue(afterObj[field]) : "—";
                  const changed = bVal !== aVal;
                  return (
                    <tr key={field} className={changed ? "is-changed" : ""}>
                      <td>
                        <code>{field}</code>
                      </td>
                      <td className="audit-val-before">{bVal}</td>
                      <td className="audit-val-after">{aVal}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : hasBeforeAfter ? (
          <div className="audit-diff-table-wrap" data-testid={`${prefix}-diff-${log.log_id}`}>
            <p className="muted small-text">
              Before: {formatAuditValue(rawBefore)} · After: {formatAuditValue(rawAfter)}
            </p>
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div
      className={mode === "admin" ? "panel audit-panel" : "tournament-audit-section"}
      id={mode === "admin" ? "audit-logs" : undefined}
      data-testid={`${prefix}-section`}
    >
      <div className="section-header">
        <div>
          {mode === "admin" ? (
            <h2>
              {title} ({total})
            </h2>
          ) : (
            <h4>
              {title} ({total})
            </h4>
          )}
          <p className="muted small-text">{subtitle}</p>
        </div>
        {canView && (
          <div className="referees-header-actions">
            {loading && logs.length > 0 && (
              <span
                className="matches-refreshing-indicator"
                data-testid={`${prefix}-refreshing-indicator`}
              >
                <span className="spinner" /> Đang cập nhật...
              </span>
            )}
            <button
              type="button"
              className="button secondary small"
              data-testid={`${prefix}-reload-btn`}
              disabled={loading}
              onClick={() => void fetchLogs(appliedFilters, page)}
            >
              Tải lại
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="error-banner" data-testid={`${prefix}-error-banner`}>
          <span>{error}</span>
          {canView && (
            <button
              type="button"
              className="button secondary small"
              data-testid={`${prefix}-retry-btn`}
              onClick={() => void fetchLogs(appliedFilters, page)}
            >
              Thử lại
            </button>
          )}
        </div>
      )}

      {!canView ? (
        <p className="muted small-text" data-testid={`${prefix}-unavailable-reason`}>
          Bạn không có quyền xem nhật ký hoạt động này.
        </p>
      ) : (
        <>
          <form
            className="audit-filters-form"
            noValidate
            onSubmit={handleApplyFilters}
            data-testid={`${prefix}-filters-form`}
          >
            <div className="audit-filters-grid">
              <div className="audit-filter-field">
                <label htmlFor={`${prefix}-filter-resource`}>Tài nguyên (Resource)</label>
                <select
                  id={`${prefix}-filter-resource`}
                  name="resource"
                  data-testid={`${prefix}-filter-resource`}
                  value={draftFilters.resource}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, resource: e.target.value }))
                  }
                >
                  <option value="">Tất cả tài nguyên</option>
                  {resourceOptions.map((resName) => (
                    <option key={resName} value={resName}>
                      {resName}
                    </option>
                  ))}
                </select>
              </div>

              <label>
                Hành động (Action)
                <input
                  type="text"
                  name="action"
                  data-testid={`${prefix}-filter-action`}
                  placeholder="VD: TEAM_UPDATED, ROLE_ASSIGNMENT_GRANTED"
                  maxLength={100}
                  value={draftFilters.action}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, action: e.target.value }))
                  }
                />
              </label>

              <label>
                Actor ID
                <input
                  type="text"
                  inputMode="numeric"
                  name="actor_id"
                  data-testid={`${prefix}-filter-actor-id`}
                  placeholder="ID người thực hiện"
                  value={draftFilters.actor_id}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, actor_id: e.target.value }))
                  }
                />
              </label>

              <label>
                Resource ID
                <input
                  type="text"
                  inputMode="numeric"
                  name="resource_id"
                  data-testid={`${prefix}-filter-resource-id`}
                  placeholder="ID bản ghi"
                  value={draftFilters.resource_id}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, resource_id: e.target.value }))
                  }
                />
              </label>

              {mode === "admin" && (
                <label>
                  Tournament ID
                  <input
                    type="text"
                    inputMode="numeric"
                    name="tournament_id"
                    data-testid={`${prefix}-filter-tournament-id`}
                    placeholder="ID giải đấu"
                    value={draftFilters.tournament_id}
                    disabled={loading}
                    onChange={(e) =>
                      setDraftFilters((prev) => ({ ...prev, tournament_id: e.target.value }))
                    }
                  />
                </label>
              )}

              <label>
                Từ lúc (Since)
                <input
                  type="datetime-local"
                  name="since"
                  data-testid={`${prefix}-filter-since`}
                  value={draftFilters.since}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, since: e.target.value }))
                  }
                />
              </label>

              <label>
                Đến lúc (Until)
                <input
                  type="datetime-local"
                  name="until"
                  data-testid={`${prefix}-filter-until`}
                  value={draftFilters.until}
                  disabled={loading}
                  onChange={(e) =>
                    setDraftFilters((prev) => ({ ...prev, until: e.target.value }))
                  }
                />
              </label>
            </div>

            <div className="form-actions">
              <button
                type="submit"
                className="button small"
                data-testid={`${prefix}-filter-apply-btn`}
                disabled={loading}
              >
                Áp dụng bộ lọc
              </button>
              <button
                type="button"
                className="button secondary small"
                data-testid={`${prefix}-filter-reset-btn`}
                disabled={loading}
                onClick={handleResetFilters}
              >
                Xóa bộ lọc
              </button>
            </div>
          </form>

          {(!loaded && !error) || (loading && logs.length === 0) ? (
            <div className="loading-state" data-testid={`${prefix}-loading`}>
              <span className="spinner" /> Đang tải nhật ký hoạt động...
            </div>
          ) : logs.length === 0 ? (
            !error ? (
              <p className="muted" data-testid={`${prefix}-empty`}>
                {hasActiveFilters
                  ? "Không có bản ghi nhật ký nào khớp với bộ lọc hiện tại."
                  : "Chưa có bản ghi nhật ký hoạt động nào."}
              </p>
            ) : null
          ) : (
            <>
              <div className="audit-log-list" data-testid={`${prefix}-list`}>
                {logs.map((log) => (
                  <article
                    key={log.log_id}
                    className="audit-log-card"
                    data-testid={`${prefix}-row-${log.log_id}`}
                    data-log-id={log.log_id}
                    data-action={log.action}
                    data-resource={log.resource}
                  >
                    <div className="audit-log-header">
                      <div className="audit-log-badges">
                        <span className="audit-id-badge">#{log.log_id}</span>
                        <span className="audit-action-badge">{log.action}</span>
                        <span className="audit-resource-badge">
                          {log.resource}
                          {log.resource_id !== null ? ` #${log.resource_id}` : ""}
                        </span>
                        {log.tournament_id !== null && (
                          <span className="referee-id-pill">Giải #{log.tournament_id}</span>
                        )}
                      </div>
                      <span className="muted small-text audit-timestamp">
                        {formatAuditTime(log.created_at)}
                      </span>
                    </div>

                    <div className="audit-log-actor">
                      <span className="muted small-text">Người thực hiện: </span>
                      {log.actor ? (
                        <strong>
                          {log.actor.username}{" "}
                          <span className="muted small-text">(#{log.actor.user_id})</span>
                        </strong>
                      ) : (
                        <span className="muted">Hệ thống / Không xác định</span>
                      )}
                    </div>

                    {renderDetails(log)}
                  </article>
                ))}
              </div>

              {total > AUDIT_LOGS_PER_PAGE && (
                <div className="pagination-controls" data-testid={`${prefix}-pagination`}>
                  <button
                    type="button"
                    className="button secondary small"
                    data-testid={`${prefix}-page-prev`}
                    disabled={page === 0 || loading}
                    onClick={() => handlePageChange(page - 1)}
                  >
                    ‹ Trước
                  </button>
                  <span className="pagination-info" data-testid={`${prefix}-page-info`}>
                    Trang {page + 1} / {Math.max(1, Math.ceil(total / AUDIT_LOGS_PER_PAGE))} (Tổng{" "}
                    {total} bản ghi)
                  </span>
                  <button
                    type="button"
                    className="button secondary small"
                    data-testid={`${prefix}-page-next`}
                    disabled={page >= Math.ceil(total / AUDIT_LOGS_PER_PAGE) - 1 || loading}
                    onClick={() => handlePageChange(page + 1)}
                  >
                    Sau ›
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
