import { FormEvent, useEffect, useRef, useState } from "react";
import "./styles.css";

type User = { id: number; username: string; email?: string; role: string };
type Game = { game_id: number; name: string; slug: string; publisher_id: number };
type Publisher = { publisher_id: number; name: string };
type Area = { area_id: number; name: string; code: string; parent_id: number | null };
type Team = { team_id: number; name: string; tag: string; game_id: number };
type TeamMember = { membership_id: number; user_id: number; username: string; role: string; status: string; joined_date: string; left_date: string | null };
type TeamDetail = Team & { members: TeamMember[] };
type Tournament = {
  tournament_id: number; name: string; game_id: number; area_id: number | null;
  format: "SINGLE_ELIM" | "DOUBLE_ELIM" | "ROUND_ROBIN"; start_date: string;
  end_date: string | null; status: "UPCOMING" | "ONGOING" | "COMPLETED" | "CANCELLED";
  description: string | null; created_by: number | null; created_at: string;
};
type TournamentCapabilities = {
  tournament_id: number; can_manage: boolean; can_update: boolean;
  can_change_status: boolean; can_review_registrations: boolean;
  can_approve_registrations: boolean; roster_locked: boolean;
  can_lock_roster: boolean; can_manage_stages?: boolean;
  editable_fields: string[]; allowed_status_transitions: string[];
};
type RosterRole = "PLAYER" | "SUBSTITUTE";
type RosterMember = {
  user_id: number;
  display_name: string | null;
  role_in_team: RosterRole;
};
type RosterRead = {
  tournament_id: number;
  team_id: number;
  locked: boolean;
  members: RosterMember[];
};
type RosterLockRead = {
  tournament_id: number;
  locked: boolean;
  locked_at: string | null;
};
type RosterCapabilities = {
  tournament_id: number;
  team_id: number;
  can_view_roster: boolean;
  can_edit_roster: boolean;
};
type RosterDraftItem = {
  user_id: number;
  role_in_team: RosterRole;
  username?: string;
  display_name?: string;
};
type RegistrationStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
type TournamentRegistrationItem = {
  registration_id: number; tournament_id: number; team_id: number;
  status: RegistrationStatus; submitted_by: number | null; submitted_at: string;
  reviewed_by: number | null; reviewed_at: string | null; rejection_reason: string | null;
  cancelled_by: number | null; cancelled_at: string | null;
};
type ApprovedTeam = { team_id: number; name: string; tag: string; game_id: number };
type Stage = {
  stage_id: number;
  tournament_id: number;
  name: string;
  sequence_order: number;
};
const APPROVED_TEAMS_PER_PAGE = 10;
const REGISTRATIONS_PER_PAGE = 10;
type GlobalCapabilities = { can_manage_catalog: boolean; can_create_tournament: boolean };
type TeamCapabilities = { team_id: number; can_manage_members: boolean; can_register_for_tournament: boolean };
type AuthMode = "login" | "register";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "esports_access_token";

class RequestError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

type ValidationError = { msg?: string };

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | ValidationError[] } | null;
    const detail = body?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item.msg ?? "Dữ liệu không hợp lệ").join("; ")
        : "Yêu cầu không thành công";
    throw new RequestError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authCheckAttempt, setAuthCheckAttempt] = useState(0);
  const [games, setGames] = useState<Game[]>([]);
  const [publishers, setPublishers] = useState<Publisher[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<TeamDetail | null>(null);
  const [teamCapabilities, setTeamCapabilities] = useState<TeamCapabilities | null>(null);
  const [teamCapabilityError, setTeamCapabilityError] = useState("");
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedTournament, setSelectedTournament] = useState<Tournament | null>(null);
  const [tournamentCapabilities, setTournamentCapabilities] = useState<TournamentCapabilities | null>(null);
  const [tournamentLoading, setTournamentLoading] = useState(false);
  const [capabilityError, setCapabilityError] = useState("");
  const [approvedTeams, setApprovedTeams] = useState<ApprovedTeam[]>([]);
  const [managedTeamsForTournament, setManagedTeamsForTournament] = useState<Team[]>([]);
  const [registrations, setRegistrations] = useState<TournamentRegistrationItem[]>([]);
  const [allTournamentRegistrations, setAllTournamentRegistrations] = useState<TournamentRegistrationItem[]>([]);
  const [registrationLoading, setRegistrationLoading] = useState(false);
  const [registrationError, setRegistrationError] = useState("");
  const [registrationNotice, setRegistrationNotice] = useState("");
  const [registrationStatusFilter, setRegistrationStatusFilter] = useState<string>("");
  const [tournamentError, setTournamentError] = useState("");
  const [tournamentTotal, setTournamentTotal] = useState(0);
  const [tournamentPage, setTournamentPage] = useState(0);
  const [tournamentGameFilter, setTournamentGameFilter] = useState("");
  const [tournamentStatusFilter, setTournamentStatusFilter] = useState("");
  const [globalCapabilities, setGlobalCapabilities] = useState<GlobalCapabilities | null>(null);
  const [globalCapabilityError, setGlobalCapabilityError] = useState("");
  const [memberLoading, setMemberLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogReloadError, setCatalogReloadError] = useState("");
  const [selectedRosterTeam, setSelectedRosterTeam] = useState<{ team_id: number; name: string; tag?: string } | null>(null);
  const [rosterLock, setRosterLock] = useState<RosterLockRead | null>(null);
  const [rosterData, setRosterData] = useState<RosterRead | null>(null);
  const [rosterCapabilities, setRosterCapabilities] = useState<RosterCapabilities | null>(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [rosterError, setRosterError] = useState("");
  const [rosterNotice, setRosterNotice] = useState("");
  const [rosterSaving, setRosterSaving] = useState(false);
  const [teamEligibleMembers, setTeamEligibleMembers] = useState<TeamMember[]>([]);
  const [rosterDraftMembers, setRosterDraftMembers] = useState<RosterDraftItem[]>([]);
  const [lockLoading, setLockLoading] = useState(false);
  const [lockError, setLockError] = useState("");
  const [lockNotice, setLockNotice] = useState("");
  const [approvedRosterStatuses, setApprovedRosterStatuses] = useState<Record<number, { loaded: boolean; hasPlayer: boolean }>>({});
  const [rosterStatusWarning, setRosterStatusWarning] = useState("");

  const [stages, setStages] = useState<Stage[]>([]);
  const [stagesLoading, setStagesLoading] = useState(false);
  const [stagesError, setStagesError] = useState("");
  const [stagesNotice, setStagesNotice] = useState("");
  const [stageActionLoading, setStageActionLoading] = useState(false);
  const [isCreatingStage, setIsCreatingStage] = useState(false);
  const [newStageName, setNewStageName] = useState("");
  const [newStageOrder, setNewStageOrder] = useState("");
  const [stageFormError, setStageFormError] = useState("");
  const [editingStageId, setEditingStageId] = useState<number | null>(null);
  const [editingStageName, setEditingStageName] = useState("");
  const [editingStageOrder, setEditingStageOrder] = useState("");

  const [approvedTeamsTotal, setApprovedTeamsTotal] = useState(0);
  const [approvedTeamsPage, setApprovedTeamsPage] = useState(0);

  const [registrationTotal, setRegistrationTotal] = useState(0);
  const [registrationPage, setRegistrationPage] = useState(0);

  const sessionVersion = useRef(0);
  const tournamentViewVersion = useRef(0);
  const rosterTeamVersion = useRef(0);
  const activeRosterTeamIdRef = useRef<number | null>(null);

  const resetStagesState = () => {
    setStages([]);
    setStagesLoading(false);
    setStagesError("");
    setStagesNotice("");
    setStageActionLoading(false);
    setIsCreatingStage(false);
    setNewStageName("");
    setNewStageOrder("");
    setStageFormError("");
    setEditingStageId(null);
    setEditingStageName("");
    setEditingStageOrder("");
  };

  const resetRosterState = () => {
    activeRosterTeamIdRef.current = null;
    rosterTeamVersion.current += 1;
    setSelectedRosterTeam(null);
    setRosterData(null);
    setRosterCapabilities(null);
    setRosterLoading(false);
    setRosterSaving(false);
    setLockLoading(false);
    setRosterError("");
    setRosterNotice("");
    setTeamEligibleMembers([]);
    setRosterDraftMembers([]);
    setRosterStatusWarning("");
  };

  const handleAuthExpired = (customMessage?: string) => {
    sessionVersion.current += 1;
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setTeamCapabilities(null);
    setTeamCapabilityError("");
    setGlobalCapabilities(null);
    setGlobalCapabilityError("");
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setError(customMessage || "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
  };

  const loadTeams = async () => {
    try {
      const [loadedGames, loadedTeams] = await Promise.all([
        request<Game[]>("/catalog/games"),
        request<Team[]>("/teams"),
      ]);
      setGames(loadedGames);
      setTeams(loadedTeams);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const loadCatalog = async () => {
    const [loadedPublishers, loadedGames, loadedAreas] = await Promise.all([
      request<Publisher[]>("/catalog/publishers"),
      request<Game[]>("/catalog/games"),
      request<Area[]>("/catalog/areas"),
    ]);
    setPublishers(loadedPublishers);
    setGames(loadedGames);
    setAreas(loadedAreas);
  };

  const loadTournaments = async (page = tournamentPage, gameId = tournamentGameFilter, status = tournamentStatusFilter) => {
    setTournamentLoading(true);
    setTournamentError("");
    try {
      const params = new URLSearchParams({ offset: String(page * 6), limit: "6" });
      if (gameId) params.set("game_id", gameId);
      if (status) params.set("status", status);
      const response = await fetch(`${API}/tournaments?${params}`);
      if (!response.ok) throw new RequestError("Không thể tải danh sách giải đấu", response.status);
      setTournaments(await response.json() as Tournament[]);
      setTournamentTotal(Number(response.headers.get("X-Total-Count") ?? 0));
    } catch (reason) {
      setTournamentError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  useEffect(() => {
    loadTeams();
    loadCatalog().catch((reason) => {
      setCatalogReloadError((reason as Error).message);
      setError(`Không thể tải catalog: ${(reason as Error).message}`);
    });
  }, []);

  useEffect(() => {
    void loadTournaments();
  }, [tournamentPage, tournamentGameFilter, tournamentStatusFilter]);

  useEffect(() => {
    if (!token) return;
    const version = sessionVersion.current;
    const controller = new AbortController();
    let active = true;

    request<User>("/auth/me", { signal: controller.signal }, token)
      .then((currentUser) => {
        if (active && sessionVersion.current === version) setUser(currentUser);
      })
      .catch((reason: unknown) => {
        if (!active || controller.signal.aborted) return;
        if (reason instanceof RequestError && (reason.status === 401 || reason.status === 403)) {
          handleAuthExpired();
          return;
        }
        setError("Không thể kiểm tra phiên đăng nhập. Hãy thử lại.");
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [token, authCheckAttempt]);

  const loadGlobalCapabilities = async () => {
    if (!token) {
      setGlobalCapabilities(null);
      setGlobalCapabilityError("");
      return;
    }
    try {
      setGlobalCapabilityError("");
      const caps = await request<GlobalCapabilities>("/auth/capabilities", {}, token);
      setGlobalCapabilities(caps);
    } catch (reason) {
      setGlobalCapabilities(null);
      setGlobalCapabilityError((reason as Error).message || "Không thể tải quyền tài khoản.");
    }
  };

  useEffect(() => {
    void loadGlobalCapabilities();
  }, [token]);

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    const form = new FormData(event.currentTarget);
    try {
      if (authMode === "register") {
        await request("/auth/register", {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            email: form.get("email"),
            password: form.get("password"),
            real_name: form.get("real_name") ?? "",
          }),
        });
        setNotice("Đăng ký thành công. Hãy đăng nhập để tiếp tục.");
        setAuthMode("login");
      } else {
        const result = await request<{ access_token: string; user: User }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
        });
        sessionVersion.current += 1;
        localStorage.setItem(TOKEN_KEY, result.access_token);
        setToken(result.access_token);
        setUser(result.user);
        setNotice("Đăng nhập thành công.");
      }
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    sessionVersion.current += 1;
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setTeamCapabilities(null);
    setTeamCapabilityError("");
    setGlobalCapabilities(null);
    setGlobalCapabilityError("");
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setNotice("Bạn đã đăng xuất.");
  };

  const createTeam = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setError("");
    setNotice("");
    setLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    try {
      await request<Team>("/teams", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          tag: form.get("tag"),
          game_id: Number(form.get("game_id")),
        }),
      }, token);
      formElement.reset();
      await loadTeams();
      setNotice("Tạo đội thành công. Bạn đã trở thành MANAGER của đội.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamCapabilities = async (teamId: number) => {
    if (!token) {
      setTeamCapabilities(null);
      setTeamCapabilityError("");
      return;
    }
    try {
      setTeamCapabilityError("");
      const capabilities = await request<TeamCapabilities>(`/teams/${teamId}/capabilities`, {}, token);
      setTeamCapabilities(capabilities);
    } catch (reason) {
      setTeamCapabilities(null);
      setTeamCapabilityError((reason as Error).message || "Không thể tải quyền quản lý đội tuyển.");
    }
  };

  const viewTeam = async (teamId: number) => {
    setError("");
    setNotice("");
    setTeamCapabilityError("");
    try {
      const team = await request<TeamDetail>(`/teams/${teamId}`);
      setSelectedTeam(team);
      await loadTeamCapabilities(teamId);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const refreshSelectedTeam = async () => {
    if (!selectedTeam) return;
    try {
      const team = await request<TeamDetail>(`/teams/${selectedTeam.team_id}`);
      setSelectedTeam(team);
      await loadTeamCapabilities(selectedTeam.team_id);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const addMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTeam) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members`, {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          role_in_team: form.get("role_in_team"),
        }),
      }, token);
      formElement.reset();
      await refreshSelectedTeam();
      setNotice("Đã thêm thành viên vào đội.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const updateMemberRole = async (membershipId: number, role: string) => {
    if (!token || !selectedTeam) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members/${membershipId}`, {
        method: "PATCH",
        body: JSON.stringify({ role_in_team: role }),
      }, token);
      await refreshSelectedTeam();
      setNotice("Đã cập nhật vị trí thành viên.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const endMembership = async (membership: TeamMember) => {
    if (!token || !selectedTeam) return;
    const action = membership.user_id === user?.id ? "rời đội" : "kết thúc membership của thành viên này";
    if (!window.confirm(`Bạn có chắc muốn ${action}? Thao tác này không thể hoàn tác ngay.`)) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members/${membership.membership_id}/end`, {
        method: "POST",
      }, token);
      await refreshSelectedTeam();
      setNotice(membership.user_id === user?.id ? "Bạn đã rời đội." : "Đã kết thúc membership.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const canManageSelectedTeam = teamCapabilities?.can_manage_members === true;

  const catalogRequest = async (path: string, method: "POST" | "PATCH" | "DELETE", body?: object): Promise<boolean> => {
    if (!token || !globalCapabilities?.can_manage_catalog) return false;
    setError("");
    setNotice("");
    setCatalogLoading(true);
    try {
      await request(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }, token);
    } catch (reason) {
      setError((reason as Error).message);
      setCatalogLoading(false);
      return false;
    }
    try {
      await loadCatalog();
      setCatalogReloadError("");
      setNotice("Đã cập nhật catalog.");
      return true;
    } catch (reason) {
      const message = (reason as Error).message;
      setCatalogReloadError(message);
      setError(`Đã ghi thành công nhưng không thể tải lại danh sách: ${message}. Không gửi lại thao tác; hãy thử tải lại.`);
      return false;
    } finally {
      setCatalogLoading(false);
    }
  };

  const retryCatalogLoad = async () => {
    setError("");
    setNotice("");
    setCatalogLoading(true);
    try {
      await loadCatalog();
      setCatalogReloadError("");
      setNotice("Đã tải lại catalog.");
    } catch (reason) {
      const message = (reason as Error).message;
      setCatalogReloadError(message);
      setError(`Không thể tải lại catalog: ${message}`);
    } finally {
      setCatalogLoading(false);
    }
  };

  const submitPublisher = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (await catalogRequest("/catalog/publishers", "POST", { name: form.get("name") })) formElement.reset();
  };

  const submitGame = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (await catalogRequest("/catalog/games", "POST", {
      name: form.get("name"),
      slug: form.get("slug"),
      publisher_id: Number(form.get("publisher_id")),
    })) formElement.reset();
  };

  const submitArea = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const parent = form.get("parent_id");
    if (await catalogRequest("/catalog/areas", "POST", {
      name: form.get("name"),
      code: form.get("code"),
      parent_id: parent ? Number(parent) : null,
    })) formElement.reset();
  };

  const editCatalogItem = async (kind: "publishers" | "games" | "areas", item: Publisher | Game | Area) => {
    const name = window.prompt("Tên mới:", "name" in item ? item.name : "");
    if (!name?.trim()) return;
    if (kind === "publishers") {
      await catalogRequest(`/catalog/publishers/${(item as Publisher).publisher_id}`, "PATCH", { name: name.trim() });
    } else if (kind === "games") {
      const game = item as Game;
      const slug = window.prompt("Slug mới:", game.slug);
      if (!slug?.trim()) return;
      const publisherId = window.prompt(
        `Publisher ID mới (${publishers.map((publisher) => `${publisher.publisher_id}: ${publisher.name}`).join(", ")}):`,
        String(game.publisher_id),
      );
      if (!publisherId?.trim() || !Number.isInteger(Number(publisherId))) return;
      await catalogRequest(`/catalog/games/${game.game_id}`, "PATCH", {
        name: name.trim(), slug: slug.trim(), publisher_id: Number(publisherId),
      });
    } else {
      const area = item as Area;
      const code = window.prompt("Mã khu vực mới:", area.code);
      if (!code?.trim()) return;
      const parentId = window.prompt(
        `Khu vực cha ID mới (để trống để bỏ cấp cha; ${areas.map((candidate) => `${candidate.area_id}: ${candidate.code}`).join(", ")}):`,
        area.parent_id ? String(area.parent_id) : "",
      );
      if (parentId === null) return;
      if (parentId && !Number.isInteger(Number(parentId))) return;
      await catalogRequest(`/catalog/areas/${area.area_id}`, "PATCH", {
        name: name.trim(), code: code.trim(), parent_id: parentId ? Number(parentId) : null,
      });
    }
  };

  const deleteCatalogItem = async (kind: "publishers" | "games" | "areas", id: number, label: string) => {
    if (!window.confirm(`Bạn có chắc muốn xóa ${label}?`)) return;
    await catalogRequest(`/catalog/${kind}/${id}`, "DELETE");
  };

  const closeTournamentDetail = () => {
    tournamentViewVersion.current += 1;
    setSelectedTournament(null);
    setTournamentCapabilities(null);
    setCapabilityError("");
    setApprovedTeams([]);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setRegistrationError("");
    setRegistrationNotice("");
    setRegistrationStatusFilter("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockLoading(false);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setRosterStatusWarning("");
  };

  const loadTournamentCapabilities = async (
    tournamentId: number,
    authToken = token,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ): Promise<TournamentCapabilities | null> => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      setTournamentCapabilities(null);
      setCapabilityError("");
      return null;
    }
    try {
      setCapabilityError("");
      const caps = await request<TournamentCapabilities>(`/tournaments/${tournamentId}/capabilities`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      setTournamentCapabilities(caps);
      return caps;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return null;
      }
      setTournamentCapabilities(null);
      setCapabilityError((reason as Error).message || "Không thể tải quyền quản lý giải đấu.");
      return null;
    }
  };

  const loadApprovedTeams = async (
    tournamentId: number,
    page = approvedTeamsPage,
    expectedVersion?: number
  ): Promise<{ list: ApprovedTeam[]; total: number }> => {
    try {
      const offset = page * APPROVED_TEAMS_PER_PAGE;
      const res = await fetch(`${API}/tournaments/${tournamentId}/teams?offset=${offset}&limit=${APPROVED_TEAMS_PER_PAGE}`);
      if (!res.ok) throw new RequestError("Không thể tải danh sách đội đã duyệt", res.status);
      const total = Number(res.headers.get("X-Total-Count") ?? 0);
      const list = (await res.json()) as ApprovedTeam[];
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return { list, total };
      setApprovedTeams(list);
      setApprovedTeamsTotal(total);
      return { list, total };
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return { list: [], total: 0 };
      setApprovedTeams([]);
      setApprovedTeamsTotal(0);
      setRegistrationError((reason as Error).message);
      return { list: [], total: 0 };
    }
  };

  const handleApprovedTeamsPageChange = async (newPage: number) => {
    if (!selectedTournament) return;
    setApprovedTeamsPage(newPage);
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    const { list } = await loadApprovedTeams(selectedTournament.tournament_id, newPage, version);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
    if (token && list && (tournamentCapabilities?.can_manage || tournamentCapabilities?.can_lock_roster)) {
      void loadApprovedTeamRosterStatuses(selectedTournament.tournament_id, list, token, version, sessionV);
    }
  };

  const loadApprovedTeamRosterStatuses = async (
    tournamentId: number,
    teams: ApprovedTeam[],
    authToken: string,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken || teams.length === 0) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setApprovedRosterStatuses({});
      setRosterStatusWarning("");
      return;
    }
    try {
      let hasFetchFailure = false;
      const results = await Promise.all(
        teams.map(async (t) => {
          try {
            const r = await request<RosterRead>(`/tournaments/${tournamentId}/teams/${t.team_id}/roster`, {}, authToken);
            const hasPlayer = r.members.some((m) => m.role_in_team === "PLAYER");
            return { teamId: t.team_id, loaded: true, hasPlayer };
          } catch {
            hasFetchFailure = true;
            return { teamId: t.team_id, loaded: false, hasPlayer: false };
          }
        })
      );
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      const statusMap: Record<number, { loaded: boolean; hasPlayer: boolean }> = {};
      for (const res of results) {
        statusMap[res.teamId] = { loaded: res.loaded, hasPlayer: res.hasPlayer };
      }
      setApprovedRosterStatuses(statusMap);
      if (hasFetchFailure) {
        setRosterStatusWarning("Không thể tải trạng thái đội hình của một số đội đã duyệt.");
      } else {
        setRosterStatusWarning("");
      }
    } catch {
      // ignore status check error
    }
  };

  // Lưu ý: Endpoint /teams/managed mặc định limit 50; trong phạm vi demo W44 danh sách hiển thị tối đa 50 đội.
  const loadManagedTeamsForTournament = async (
    gameId: number,
    authToken = token,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ): Promise<Team[]> => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament([]);
      return [];
    }
    try {
      const list = await request<Team[]>(`/teams/managed?game_id=${gameId}`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament(list);
      return list;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament([]);
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return [];
      }
      setRegistrationError((reason as Error).message);
      return [];
    }
  };

  const loadTournamentRegistrations = async (
    tournamentId: number,
    statusFilter = registrationStatusFilter,
    authToken = token,
    expectedVersion?: number,
    managedTeams?: Team[],
    page = registrationPage,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    setRegistrationError("");
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      setRegistrationTotal(0);
      return;
    }
    try {
      const offset = page * REGISTRATIONS_PER_PAGE;
      const params = new URLSearchParams({ offset: String(offset), limit: String(REGISTRATIONS_PER_PAGE) });
      if (statusFilter) params.set("status", statusFilter);

      const paginatedResPromise = fetch(`${API}/tournaments/${tournamentId}/registrations?${params}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      const teamsToCheck = managedTeams ?? managedTeamsForTournament;
      const managedRegistrationsPromise = teamsToCheck.length > 0
        ? Promise.all(
            teamsToCheck.map(async (t) => {
              try {
                const res = await request<TournamentRegistrationItem[]>(
                  `/tournaments/${tournamentId}/registrations?team_id=${t.team_id}`,
                  {},
                  authToken
                );
                return res;
              } catch {
                return [];
              }
            })
          )
        : Promise.resolve([]);

      const [paginatedRes, managedRegArrays] = await Promise.all([
        paginatedResPromise,
        managedRegistrationsPromise,
      ]);

      if (!paginatedRes.ok) {
        if (paginatedRes.status === 401) {
          handleAuthExpired();
          return;
        }
        if (paginatedRes.status === 403) {
          if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
          if (sessionVersion.current !== sessionV) return;
          setRegistrations([]);
          setAllTournamentRegistrations([]);
          setRegistrationTotal(0);
          return;
        }
        throw new RequestError("Không thể tải danh sách đơn đăng ký", paginatedRes.status);
      }

      const total = Number(paginatedRes.headers.get("X-Total-Count") ?? 0);
      const paginatedList = (await paginatedRes.json()) as TournamentRegistrationItem[];
      const allManagedRegs = (managedRegArrays as TournamentRegistrationItem[][]).flat();

      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setRegistrations(paginatedList);
      setRegistrationTotal(total);
      setAllTournamentRegistrations(allManagedRegs);
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    }
  };

  const handleRegistrationPageChange = async (newPage: number) => {
    if (!selectedTournament || !token) return;
    setRegistrationPage(newPage);
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    await loadTournamentRegistrations(
      selectedTournament.tournament_id,
      registrationStatusFilter,
      token,
      version,
      undefined,
      newPage,
      sessionV
    );
  };

  const fetchAllStages = async (tournamentId: number): Promise<Stage[]> => {
    let all: Stage[] = [];
    let offset = 0;
    const limit = 100;
    while (true) {
      const res = await fetch(`${API}/tournaments/${tournamentId}/stages?offset=${offset}&limit=${limit}`);
      if (!res.ok) {
        throw new RequestError("Không thể tải danh sách vòng đấu", res.status);
      }
      const total = Number(res.headers.get("X-Total-Count") ?? 0);
      const data = (await res.json()) as Stage[];
      all = all.concat(data);
      if (all.length >= total || data.length < limit) break;
      offset += limit;
    }
    return all;
  };

  const loadTournamentStages = async (tournamentId: number, expectedVersion?: number): Promise<Stage[]> => {
    setStagesLoading(true);
    setStagesError("");
    try {
      const list = await fetchAllStages(tournamentId);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return list;
      setStages(list);
      return list;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      setStages([]);
      setStagesError((reason as Error).message || "Không thể tải danh sách vòng đấu.");
      return [];
    } finally {
      if (expectedVersion === undefined || tournamentViewVersion.current === expectedVersion) {
        setStagesLoading(false);
      }
    }
  };

  const handleCreateStage = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token || !selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const trimmedName = newStageName.trim();
    const orderNum = Number(newStageOrder);

    if (!trimmedName) {
      setStageFormError("Tên vòng đấu không được để trống.");
      return;
    }
    if (!Number.isInteger(orderNum) || orderNum <= 0) {
      setStageFormError("Thứ tự vòng đấu phải là số nguyên dương.");
      return;
    }

    setStageActionLoading(true);
    setStageFormError("");
    setStagesNotice("");
    try {
      await request<Stage>(`/tournaments/${currentTournamentId}/stages`, {
        method: "POST",
        body: JSON.stringify({ name: trimmedName, sequence_order: orderNum }),
      }, token);
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      setNewStageName("");
      setNewStageOrder("");
      setIsCreatingStage(false);
      setStagesNotice("Đã thêm vòng đấu thành công.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion);
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStageFormError((reason as Error).message || "Không thể tạo vòng đấu.");
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setStageActionLoading(false);
      }
    }
  };

  const handleUpdateStage = async (stageId: number, e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token || !selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const trimmedName = editingStageName.trim();
    const orderNum = Number(editingStageOrder);

    if (!trimmedName) {
      setStageFormError("Tên vòng đấu không được để trống.");
      return;
    }
    if (!Number.isInteger(orderNum) || orderNum <= 0) {
      setStageFormError("Thứ tự vòng đấu phải là số nguyên dương.");
      return;
    }

    setStageActionLoading(true);
    setStageFormError("");
    setStagesNotice("");
    try {
      await request<Stage>(`/tournaments/${currentTournamentId}/stages/${stageId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: trimmedName, sequence_order: orderNum }),
      }, token);
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      setEditingStageId(null);
      setStagesNotice("Đã cập nhật vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion);
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStageFormError((reason as Error).message || "Không thể cập nhật vòng đấu.");
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setStageActionLoading(false);
      }
    }
  };

  const handleDeleteStage = async (stage: Stage) => {
    if (!token || !selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    if (!window.confirm(`Bạn có chắc chắn muốn xóa vòng đấu "${stage.name}"?`)) return;

    setStageActionLoading(true);
    setStagesError("");
    setStagesNotice("");
    try {
      await request(`/tournaments/${currentTournamentId}/stages/${stage.stage_id}`, {
        method: "DELETE",
      }, token);
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      setStagesNotice("Đã xóa vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion);
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStagesError((reason as Error).message || "Không thể xóa vòng đấu.");
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setStageActionLoading(false);
      }
    }
  };

  const handleMoveStage = async (stageIndex: number, direction: "up" | "down") => {
    if (!token || !selectedTournament || stageActionLoading) return;
    const targetIndex = direction === "up" ? stageIndex - 1 : stageIndex + 1;
    if (targetIndex < 0 || targetIndex >= stages.length) return;

    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    setStageActionLoading(true);
    setStagesError("");
    setStagesNotice("");

    try {
      const allStages = await fetchAllStages(currentTournamentId);
      if (tournamentViewVersion.current !== currentTournamentVersion) return;

      const currentStageId = stages[stageIndex].stage_id;
      const allIdx = allStages.findIndex((s) => s.stage_id === currentStageId);
      if (allIdx === -1) {
        throw new Error("Không tìm thấy vòng đấu để sắp xếp.");
      }
      const allTargetIdx = direction === "up" ? allIdx - 1 : allIdx + 1;
      if (allTargetIdx < 0 || allTargetIdx >= allStages.length) return;

      const updated = [...allStages];
      const temp = updated[allIdx];
      updated[allIdx] = updated[allTargetIdx];
      updated[allTargetIdx] = temp;

      const stageIds = updated.map((s) => s.stage_id);
      const reordered = await request<Stage[]>(`/tournaments/${currentTournamentId}/stages/order`, {
        method: "PUT",
        body: JSON.stringify({ stage_ids: stageIds }),
      }, token);

      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      setStages(reordered);
      setStagesNotice("Đã cập nhật thứ tự vòng đấu.");
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStagesError((reason as Error).message || "Không thể sắp xếp thứ tự vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion);
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setStageActionLoading(false);
      }
    }
  };

  const loadRosterLock = async (tournamentId: number, expectedVersion?: number) => {
    try {
      const res = await request<RosterLockRead>(`/tournaments/${tournamentId}/roster-lock`);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setRosterLock(res);
    } catch {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setRosterLock(null);
    }
  };

  const loadTeamRosterData = async (
    teamId: number,
    expectedTournamentVersion?: number,
    expectedTeamVersion?: number,
    preserveError = false,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    setRosterLoading(true);
    if (!preserveError) {
      setRosterError("");
    }
    setRosterNotice("");
    try {
      let caps: RosterCapabilities | null = null;
      if (token) {
        try {
          caps = await request<RosterCapabilities>(
            `/tournaments/${currentTournamentId}/teams/${teamId}/roster/capabilities`,
            {},
            token
          );
        } catch (reason) {
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          if (reason instanceof RequestError && reason.status === 401) {
            handleAuthExpired();
            return;
          }
          throw reason;
        }
      }

      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterCapabilities(caps);

      const roster = await request<RosterRead>(
        `/tournaments/${currentTournamentId}/teams/${teamId}/roster`,
        {},
        token || undefined
      );

      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterData(roster);
      setRosterDraftMembers(
        roster.members.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
          display_name: m.display_name ?? undefined,
        }))
      );

      if (caps?.can_edit_roster && token) {
        try {
          const members = await request<TeamMember[]>(
            `/teams/${teamId}/members?include_history=false`,
            {},
            token
          );
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          const eligible = members.filter(
            (m) => m.status === "ACTIVE" && (m.role === "PLAYER" || m.role === "SUBSTITUTE")
          );
          setTeamEligibleMembers(eligible);
        } catch (reason) {
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          if (reason instanceof RequestError && reason.status === 401) {
            handleAuthExpired();
            return;
          }
          setTeamEligibleMembers([]);
          setRosterError((reason as Error).message || "Không thể tải danh sách thành viên đội để chọn đội hình.");
          return;
        }
      } else {
        setTeamEligibleMembers([]);
      }
    } catch (reason) {
      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterData(null);
      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          if (token) {
            handleAuthExpired();
          } else {
            setRosterError("Đội hình đang là bản nháp riêng tư. Cần đăng nhập để xem.");
          }
          return;
        }
        if (reason.status === 403) {
          setRosterError("Bạn không có quyền xem đội hình nháp này (chỉ quản lý đội hoặc quản lý giải).");
          return;
        }
      }
      setRosterError((reason as Error).message || "Không thể tải thông tin đội hình.");
    } finally {
      if (
        (expectedTournamentVersion === undefined || tournamentViewVersion.current === expectedTournamentVersion) &&
        (expectedTeamVersion === undefined || rosterTeamVersion.current === expectedTeamVersion) &&
        sessionVersion.current === sessionV &&
        activeRosterTeamIdRef.current === teamId
      ) {
        setRosterLoading(false);
      }
    }
  };

  const openTeamRoster = async (teamId: number, teamName: string, teamTag?: string) => {
    if (selectedRosterTeam?.team_id === teamId) {
      resetRosterState();
      return;
    }
    const currentTeamVersion = ++rosterTeamVersion.current;
    activeRosterTeamIdRef.current = teamId;
    setSelectedRosterTeam({ team_id: teamId, name: teamName, tag: teamTag });
    setRosterData(null);
    setRosterCapabilities(null);
    setTeamEligibleMembers([]);
    setRosterDraftMembers([]);
    setRosterError("");
    setRosterNotice("");
    await loadTeamRosterData(teamId, tournamentViewVersion.current, currentTeamVersion, false, sessionVersion.current);
  };

  const addMemberToRosterDraft = (userId: number) => {
    const member = teamEligibleMembers.find((m) => m.user_id === userId);
    if (!member) return;
    if (rosterDraftMembers.some((m) => m.user_id === userId)) return;
    setRosterNotice("");
    setRosterError("");
    setRosterDraftMembers((prev) => [
      ...prev,
      {
        user_id: member.user_id,
        role_in_team: member.role as RosterRole,
        username: member.username,
      },
    ]);
  };

  const removeMemberFromRosterDraft = (userId: number) => {
    setRosterNotice("");
    setRosterError("");
    setRosterDraftMembers((prev) => prev.filter((m) => m.user_id !== userId));
  };

  const saveRoster = async () => {
    if (!token || !selectedTournament || !selectedRosterTeam) return;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const currentTeamId = selectedRosterTeam.team_id;
    const currentTeamVersion = rosterTeamVersion.current;

    setRosterSaving(true);
    setRosterError("");
    setRosterNotice("");
    try {
      const payload = {
        members: rosterDraftMembers.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
        })),
      };
      const updated = await request<RosterRead>(
        `/tournaments/${currentTournamentId}/teams/${currentTeamId}/roster`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
        token
      );

      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (rosterTeamVersion.current !== currentTeamVersion || activeRosterTeamIdRef.current !== currentTeamId) return;

      setRosterData(updated);
      setRosterDraftMembers(
        updated.members.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
          display_name: m.display_name ?? undefined,
        }))
      );
      setRosterNotice("Đã lưu đội hình tham dự thành công!");

      setApprovedRosterStatuses((prev) => ({
        ...prev,
        [currentTeamId]: {
          loaded: true,
          hasPlayer: updated.members.some((m) => m.role_in_team === "PLAYER"),
        },
      }));
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (rosterTeamVersion.current !== currentTeamVersion || activeRosterTeamIdRef.current !== currentTeamId) return;

      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          handleAuthExpired();
          return;
        }
        if (reason.status === 409) {
          const conflictMsg =
            reason.message || "Xung đột: Giải đấu đã bị khóa hoặc trạng thái đội hình đã thay đổi.";
          const currentSession = sessionVersion.current;
          const [caps, , approvedData] = await Promise.all([
            loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
            loadRosterLock(currentTournamentId, currentTournamentVersion),
            loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
            loadTeamRosterData(currentTeamId, currentTournamentVersion, currentTeamVersion, true, currentSession),
          ]);
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)
          ) {
            void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
          }
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            rosterTeamVersion.current === currentTeamVersion
          ) {
            setRosterError(conflictMsg);
          }
          return;
        }
      }
      setRosterError((reason as Error).message || "Không thể lưu đội hình.");
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        rosterTeamVersion.current === currentTeamVersion &&
        activeRosterTeamIdRef.current === currentTeamId
      ) {
        setRosterSaving(false);
      }
    }
  };

  const handleLockRoster = async () => {
    if (!token || !selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;

    const confirmed = window.confirm(
      "Xác nhận khóa đội hình cho giải đấu này?\n\nSau khi khóa:\n- Không thể chỉnh sửa đội hình của các đội.\n- Không thể nhận thêm đơn đăng ký mới.\n- Snapshot đội hình sẽ được cố định để chuẩn bị thi đấu."
    );
    if (!confirmed) return;

    setLockLoading(true);
    setLockError("");
    setLockNotice("");
    try {
      const res = await request<RosterLockRead>(
        `/tournaments/${currentTournamentId}/roster-lock`,
        { method: "POST" },
        token
      );

      if (tournamentViewVersion.current !== currentTournamentVersion) return;

      setRosterLock(res);
      setLockNotice("Đã khóa đội hình giải đấu thành công! Snapshot đội hình đã được cố định.");

      const currentSession = sessionVersion.current;
      const [caps, approvedData] = await Promise.all([
        loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
        loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
        loadTournaments(),
      ]);

      if (tournamentViewVersion.current !== currentTournamentVersion || sessionVersion.current !== currentSession) return;

      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
      }

      if (activeRosterTeamIdRef.current) {
        await loadTeamRosterData(activeRosterTeamIdRef.current, currentTournamentVersion, rosterTeamVersion.current, false, currentSession);
      }
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;

      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          handleAuthExpired();
          return;
        }
        if (reason.status === 409) {
          const conflictMsg =
            reason.message || "Xung đột khi khóa đội hình: Trạng thái giải đấu hoặc đội hình đã thay đổi.";
          const currentSession = sessionVersion.current;
          const [caps, , approvedData] = await Promise.all([
            loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
            loadRosterLock(currentTournamentId, currentTournamentVersion),
            loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
          ]);
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)
          ) {
            void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
          }
          if (activeRosterTeamIdRef.current) {
            await loadTeamRosterData(activeRosterTeamIdRef.current, currentTournamentVersion, rosterTeamVersion.current, false, currentSession);
          }
          if (tournamentViewVersion.current === currentTournamentVersion && sessionVersion.current === currentSession) {
            setLockError(conflictMsg);
          }
          return;
        }
      }
      setLockError((reason as Error).message || "Không thể khóa đội hình.");
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setLockLoading(false);
      }
    }
  };
  const reloadTournamentDetailsData = async (tournament: Tournament) => {
    const version = tournamentViewVersion.current;
    const currentSession = sessionVersion.current;
    setRegistrationError("");
    const managedTeams = await loadManagedTeamsForTournament(tournament.game_id, token, version, currentSession);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== currentSession) return;
    const [, approvedData] = await Promise.all([
      loadTournamentCapabilities(tournament.tournament_id, token, version, currentSession),
      loadApprovedTeams(tournament.tournament_id, approvedTeamsPage, version),
      loadTournamentRegistrations(tournament.tournament_id, registrationStatusFilter, token, version, managedTeams, registrationPage, currentSession),
      loadRosterLock(tournament.tournament_id, version),
      loadTournamentStages(tournament.tournament_id, version),
    ]);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== currentSession) return;
    if (token && approvedData?.list && (tournamentCapabilities?.can_manage || tournamentCapabilities?.can_lock_roster)) {
      void loadApprovedTeamRosterStatuses(tournament.tournament_id, approvedData.list, token, version, currentSession);
    }
    if (activeRosterTeamIdRef.current) {
      await loadTeamRosterData(activeRosterTeamIdRef.current, version, rosterTeamVersion.current, false, currentSession);
    }
  };

  useEffect(() => {
    if (!selectedTournament) return;
    if (!token) {
      setTournamentCapabilities(null);
      setCapabilityError("");
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      setRegistrationTotal(0);
      setRegistrationPage(0);
      setApprovedTeamsTotal(0);
      setApprovedTeamsPage(0);
      setManagedTeamsForTournament([]);
      setRegistrationError("");
      setRegistrationNotice("");
      resetRosterState();
      resetStagesState();
      setRosterLock(null);
      setLockError("");
      setLockNotice("");
      setApprovedRosterStatuses({});
      return;
    }
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    void (async () => {
      const managedTeams = await loadManagedTeamsForTournament(selectedTournament.game_id, token, version, sessionV);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      const [, caps, approvedData] = await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, version, managedTeams, registrationPage, sessionV),
        loadTournamentCapabilities(selectedTournament.tournament_id, token, version, sessionV),
        loadApprovedTeams(selectedTournament.tournament_id, approvedTeamsPage, version),
        loadRosterLock(selectedTournament.tournament_id, version),
        loadTournamentStages(selectedTournament.tournament_id, version),
      ]);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(selectedTournament.tournament_id, approvedData.list, token, version, sessionV);
      }
      if (activeRosterTeamIdRef.current) {
        await loadTeamRosterData(activeRosterTeamIdRef.current, version, rosterTeamVersion.current, false, sessionV);
      }
    })();
  }, [token]);

  const submitRegistration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTournament) return;
    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    const form = new FormData(event.currentTarget);
    const teamId = Number(form.get("team_id"));
    if (!teamId) {
      setRegistrationLoading(false);
      return;
    }
    try {
      await request<TournamentRegistrationItem>(`/tournaments/${selectedTournament.tournament_id}/registrations`, {
        method: "POST",
        body: JSON.stringify({ team_id: teamId }),
      }, token);
      setRegistrationNotice("Đã gửi đơn đăng ký thành công.");
      await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, tournamentViewVersion.current, undefined, registrationPage, sessionVersion.current),
        loadManagedTeamsForTournament(selectedTournament.game_id, token, tournamentViewVersion.current, sessionVersion.current),
      ]);
    } catch (reason) {
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      setRegistrationLoading(false);
    }
  };

  const cancelRegistration = async (registrationId: number) => {
    if (!token || !selectedTournament) return;
    if (!window.confirm("Bạn có chắc chắn muốn hủy đơn đăng ký này?")) return;
    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    try {
      await request<TournamentRegistrationItem>(`/tournaments/${selectedTournament.tournament_id}/registrations/${registrationId}/cancel`, {
        method: "POST",
      }, token);
      setRegistrationNotice("Đã hủy đơn đăng ký.");
      await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, tournamentViewVersion.current, undefined, registrationPage, sessionVersion.current),
        loadManagedTeamsForTournament(selectedTournament.game_id, token, tournamentViewVersion.current, sessionVersion.current),
      ]);
    } catch (reason) {
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      setRegistrationLoading(false);
    }
  };

  const decideRegistration = async (registrationId: number, status: "APPROVED" | "REJECTED") => {
    if (!token || !selectedTournament) return;
    let rejectionReason: string | undefined = undefined;
    if (status === "REJECTED") {
      const reason = window.prompt("Nhập lý do từ chối (tùy chọn, tối đa 500 ký tự):");
      if (reason === null) return;
      if (reason.trim()) rejectionReason = reason.trim().slice(0, 500);
    }
    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    try {
      const body: { status: "APPROVED" | "REJECTED"; rejection_reason?: string } = { status };
      if (rejectionReason) body.rejection_reason = rejectionReason;
      await request<TournamentRegistrationItem>(`/tournaments/${selectedTournament.tournament_id}/registrations/${registrationId}/decision`, {
        method: "POST",
        body: JSON.stringify(body),
      }, token);
      setRegistrationNotice(status === "APPROVED" ? "Đã duyệt đơn đăng ký." : "Đã từ chối đơn đăng ký.");
      const [, approvedData, caps] = await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, tournamentViewVersion.current, undefined, registrationPage, sessionVersion.current),
        loadApprovedTeams(selectedTournament.tournament_id, approvedTeamsPage, tournamentViewVersion.current),
        loadTournamentCapabilities(selectedTournament.tournament_id, token, tournamentViewVersion.current, sessionVersion.current),
      ]);
      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(selectedTournament.tournament_id, approvedData.list, token, tournamentViewVersion.current, sessionVersion.current);
      }
    } catch (reason) {
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      setRegistrationLoading(false);
    }
  };

  const handleRegistrationFilterChange = async (status: string) => {
    setRegistrationStatusFilter(status);
    setRegistrationPage(0);
    if (!selectedTournament || !token) return;
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    await loadTournamentRegistrations(
      selectedTournament.tournament_id,
      status,
      token,
      version,
      undefined,
      0,
      sessionV
    );
  };

  const viewTournament = async (tournamentId: number) => {
    const version = ++tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    setError("");
    setNotice("");
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRosterLock(null);
    setLockLoading(false);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setRosterStatusWarning("");
    setApprovedTeamsPage(0);
    setApprovedTeamsTotal(0);
    setRegistrationPage(0);
    setRegistrationTotal(0);
    try {
      const tournament = await request<Tournament>(`/tournaments/${tournamentId}`);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      setSelectedTournament(tournament);

      const managedTeamsPromise = loadManagedTeamsForTournament(tournament.game_id, token, version, sessionV);
      const capsPromise = loadTournamentCapabilities(tournamentId, token, version, sessionV);
      const approvedPromise = loadApprovedTeams(tournamentId, 0, version);
      const lockPromise = loadRosterLock(tournamentId, version);
      const stagesPromise = loadTournamentStages(tournamentId, version);

      const [managedTeams, caps, approvedData] = await Promise.all([
        managedTeamsPromise,
        capsPromise,
        approvedPromise,
        lockPromise,
        stagesPromise,
      ]);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;

      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(tournamentId, approvedData.list, token, version, sessionV);
      }

      await loadTournamentRegistrations(tournamentId, registrationStatusFilter, token, version, managedTeams, 0, sessionV);
    } catch (reason) {
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      setError((reason as Error).message);
    }
  };

  const submitTournament = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setError("");
    setNotice("");
    setTournamentLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const body = {
      name: form.get("name"), game_id: Number(form.get("game_id")),
      area_id: form.get("area_id") ? Number(form.get("area_id")) : null,
      format: form.get("format"), start_date: form.get("start_date"),
      end_date: form.get("end_date") || null, description: form.get("description") || null,
    };
    try {
      await request<Tournament>("/tournaments", { method: "POST", body: JSON.stringify(body) }, token);
      formElement.reset();
      await loadTournaments();
      setNotice("Đã tạo giải đấu mới.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  const changeTournamentStatus = async (status: string) => {
    if (!token || !selectedTournament) return;
    setTournamentLoading(true);
    setError("");
    try {
      const updated = await request<Tournament>(`/tournaments/${selectedTournament.tournament_id}/status`, {
        method: "POST", body: JSON.stringify({ status }),
      }, token);
      setSelectedTournament(updated);
      await loadTournamentCapabilities(updated.tournament_id, token, tournamentViewVersion.current, sessionVersion.current);
      await loadRosterLock(updated.tournament_id);
      await loadTournaments();
      setNotice(`Đã chuyển trạng thái giải sang ${status}.`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  const updateTournament = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTournament) return;
    setTournamentLoading(true);
    const form = new FormData(event.currentTarget);
    const nullableFields = ["end_date", "description", "area_id"];
    const editable = tournamentCapabilities?.editable_fields ?? [];
    const body: Record<string, string | number | null> = {};
    for (const [key, value] of form.entries()) {
      if (!editable.includes(key)) continue;
      if (value !== "") {
        body[key] = key === "game_id" || key === "area_id" ? Number(value) : String(value);
      } else if (nullableFields.includes(key)) {
        body[key] = null;
      }
    }
    try {
      const updated = await request<Tournament>(`/tournaments/${selectedTournament.tournament_id}`, {
        method: "PATCH", body: JSON.stringify(body),
      }, token);
      setSelectedTournament(updated);
      await loadTournamentCapabilities(updated.tournament_id, token, tournamentViewVersion.current, sessionVersion.current);
      await loadTournaments();
      setNotice("Đã cập nhật thông tin giải đấu.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  return <main className="shell">
    <header className="hero">
      <div>
        <div className="brand-lockup"><span className="brand-mark">N</span><span>NEXUS<span>ARENA</span></span></div>
        <span className="eyebrow">W44 · COMPETITIVE GAMING PLATFORM</span>
        <h1>Build your legacy.<br /><em>Own the arena.</em></h1>
        <p>Quản lý đội tuyển, khám phá giải đấu và đưa đội của bạn lên bảng xếp hạng.</p>
      </div>
      {user && <div className="account"><span>Xin chào, <strong>{user.username}</strong></span><button className="button secondary" onClick={logout}>Đăng xuất</button></div>}
    </header>

    {(error || notice) && <div className={error ? "message error" : "message success"}>
      <p>{error || notice}</p>
      {error === "Không thể kiểm tra phiên đăng nhập. Hãy thử lại." && <button className="link-button" onClick={() => {
        setError("");
        setAuthCheckAttempt((attempt) => attempt + 1);
      }}>Thử lại</button>}
    </div>}

    <section className="auth-layout">
      <section className="panel auth-panel">
        <div className="panel-title"><h2>{user ? "Tài khoản đã xác thực" : authMode === "login" ? "Đăng nhập" : "Đăng ký"}</h2><span>AUTH API</span></div>
        {user ? <div className="profile">
          <p><strong>{user.username}</strong></p>
          <p>{user.email ?? "Email đã được xác thực"} · Vai trò: {user.role}</p>
          <p className="muted">JWT đang được lưu trong trình duyệt và dùng cho các request cần xác thực.</p>
        </div> : <form onSubmit={submitAuth}>
          {authMode === "register" && <>
            <label>Họ và tên<input name="real_name" maxLength={100} /></label>
            <label>Email<input name="email" type="email" required /></label>
          </>}
          <label>Tên đăng nhập<input name="username" minLength={3} maxLength={50} required /></label>
          <label>Mật khẩu<input name="password" type="password" minLength={8} maxLength={128} required /></label>
          <button className="button" disabled={loading}>{loading ? "Đang xử lý..." : authMode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</button>
          <button type="button" className="link-button" onClick={() => { setError(""); setNotice(""); setAuthMode(authMode === "login" ? "register" : "login"); }}>
            {authMode === "login" ? "Chưa có tài khoản? Đăng ký" : "Đã có tài khoản? Đăng nhập"}
          </button>
        </form>}
      </section>
      <aside className="panel checklist">
        <span className="eyebrow">PHẠM VI W42-06</span>
        <h2>Luồng quản lý đội</h2>
        <ul>
          <li>Tải game qua <code>GET /catalog/games</code></li>
          <li>Tải đội qua <code>GET /teams</code></li>
          <li>Tạo đội qua <code>POST /teams</code></li>
          <li>Người tạo tự động là MANAGER</li>
        </ul>
      </aside>
    </section>
    <section className="tournament-zone">
      <div className="section-heading">
        <div><span className="eyebrow">W44-05 · ARENA CONTROL</span><h2>Giải đấu đang diễn ra</h2><p>Khám phá lịch thi đấu, theo dõi trạng thái và vận hành giải từ một command center.</p></div>
        <span className="section-count">{tournamentTotal} giải</span>
      </div>
      <div className="tournament-toolbar">
        <label>Tựa game<select aria-label="Bộ lọc giải đấu" value={tournamentGameFilter} onChange={(event) => { setTournamentPage(0); setTournamentGameFilter(event.target.value); }}><option value="">Tất cả tựa game</option>{games.map((game) => <option key={game.game_id} value={game.game_id}>{game.name}</option>)}</select></label>
        <label>Trạng thái<select value={tournamentStatusFilter} onChange={(event) => { setTournamentPage(0); setTournamentStatusFilter(event.target.value); }}><option value="">Tất cả trạng thái</option><option value="UPCOMING">Sắp diễn ra</option><option value="ONGOING">Đang diễn ra</option><option value="COMPLETED">Đã kết thúc</option><option value="CANCELLED">Đã hủy</option></select></label>
        <button className="button secondary" onClick={() => void loadTournaments()} disabled={tournamentLoading}>↻ Làm mới</button>
      </div>
      {tournamentError && <div className="inline-error"><span>{tournamentError}</span><button className="link-button" onClick={() => void loadTournaments()}>Thử lại</button></div>}
      {tournamentLoading && <div className="loading-state"><span className="spinner" /> Đang đồng bộ dữ liệu giải đấu...</div>}
      {!tournamentLoading && !tournamentError && tournaments.length === 0 && <div className="empty-state"><strong>Chưa có giải đấu phù hợp</strong><span>Thử thay đổi bộ lọc hoặc tạo giải đấu đầu tiên.</span></div>}
      <div className="tournament-grid">{tournaments.map((tournament) => {
        const game = games.find((item) => item.game_id === tournament.game_id);
        return <article className="tournament-card" data-tournament-id={tournament.tournament_id} key={tournament.tournament_id} onClick={() => void viewTournament(tournament.tournament_id)}>
          <div className="card-topline"><span className={`status status-${tournament.status.toLowerCase()}`}>{tournament.status === "UPCOMING" ? "SẮP DIỄN RA" : tournament.status === "ONGOING" ? "LIVE NOW" : tournament.status === "COMPLETED" ? "ĐÃ KẾT THÚC" : "ĐÃ HỦY"}</span><span className="tournament-id">#T{String(tournament.tournament_id).padStart(3, "0")}</span></div>
          <h3>{tournament.name}</h3><p className="game-label">{game?.name ?? "Unknown title"} <span>·</span> {tournament.format.replace("_", " ")}</p>
          <div className="card-meta"><span>◷ {new Date(tournament.start_date).toLocaleDateString("vi-VN")}</span><span>{tournament.end_date ? `→ ${new Date(tournament.end_date).toLocaleDateString("vi-VN")}` : "Open end"}</span></div>
          <button className="card-link" onClick={(event) => { event.stopPropagation(); void viewTournament(tournament.tournament_id); }}>Xem chi tiết <span>→</span></button>
        </article>;
      })}</div>
      {tournamentTotal > 6 && <div className="pagination"><button className="button secondary" disabled={tournamentPage === 0 || tournamentLoading} onClick={() => setTournamentPage((page) => page - 1)}>← Trước</button><span>Trang {tournamentPage + 1} / {Math.ceil(tournamentTotal / 6)}</span><button className="button secondary" disabled={(tournamentPage + 1) * 6 >= tournamentTotal || tournamentLoading} onClick={() => setTournamentPage((page) => page + 1)}>Sau →</button></div>}
      {globalCapabilityError && <div className="error-banner"><span>{globalCapabilityError}</span><button className="button secondary" onClick={() => void loadGlobalCapabilities()}>Thử lại</button></div>}
      {globalCapabilities?.can_create_tournament && <details className="tournament-create"><summary><span>+</span> Tạo giải đấu mới</summary><form onSubmit={submitTournament} className="tournament-form">
        <label>Tên giải đấu<input name="name" placeholder="VCT Vietnam — Stage 1" minLength={3} maxLength={150} required /></label><label>Tựa game<select name="game_id" defaultValue="" required><option value="" disabled>Chọn tựa game</option>{games.map((game) => <option key={game.game_id} value={game.game_id}>{game.name}</option>)}</select></label><label>Thể thức<select name="format" defaultValue="SINGLE_ELIM"><option value="SINGLE_ELIM">Single Elimination</option><option value="DOUBLE_ELIM">Double Elimination</option><option value="ROUND_ROBIN">Round Robin</option></select></label><label>Bắt đầu<input name="start_date" type="date" required /></label><label>Kết thúc<input name="end_date" type="date" /></label><label>Khu vực<select name="area_id" defaultValue=""><option value="">Toàn cầu</option>{areas.map((area) => <option key={area.area_id} value={area.area_id}>{area.name}</option>)}</select></label><label className="wide-field">Mô tả<textarea name="description" maxLength={2000} placeholder="Thông tin giải, luật thi đấu, phần thưởng..." /></label><button className="button" disabled={tournamentLoading}>Tạo giải đấu</button>
      </form></details>}
      {selectedTournament && <div className="tournament-detail">
        <div className="detail-header"><div><span className="eyebrow">TOURNAMENT PROFILE</span><h3>{selectedTournament.name}</h3><p>{games.find((game) => game.game_id === selectedTournament.game_id)?.name ?? "Game"} · {selectedTournament.format.replace("_", " ")}</p></div><button className="link-button" onClick={closeTournamentDetail}>Đóng ×</button></div>
                <div className="detail-stats">
          <div><span>Trạng thái</span><strong className={`status status-${selectedTournament.status.toLowerCase()}`}>{selectedTournament.status}</strong></div>
          <div><span>Đội hình</span><strong className={tournamentCapabilities?.roster_locked || rosterLock?.locked ? "status status-completed" : "status status-upcoming"}>{tournamentCapabilities?.roster_locked || rosterLock?.locked ? "Đã khóa" : "Chưa khóa"}</strong></div>
          <div><span>Ngày bắt đầu</span><strong>{new Date(selectedTournament.start_date).toLocaleDateString("vi-VN")}</strong></div>
          <div><span>Khu vực</span><strong>{areas.find((area) => area.area_id === selectedTournament.area_id)?.name ?? "Toàn cầu"}</strong></div>
        </div>
        {selectedTournament.description && <p className="detail-description">{selectedTournament.description}</p>}
        {capabilityError && <div className="error-banner"><span>{capabilityError}</span><button className="button secondary" onClick={() => void loadTournamentCapabilities(selectedTournament.tournament_id, token, tournamentViewVersion.current, sessionVersion.current)}>Thử lại</button></div>}
                {tournamentCapabilities?.can_manage && <div className="manage-panel">
          <div className="panel-title"><h4>Điều hành giải</h4><span>CAPABILITY VERIFIED</span></div>
          {selectedTournament.status === "UPCOMING" && (
            <div className="start-conditions-box">
              {tournamentCapabilities.roster_locked || rosterLock?.locked ? (
                <div className="condition-item met">
                  <span className="condition-icon">✓</span>
                  <span>Đội hình giải đấu đã được khóa{rosterLock?.locked_at ? ` (${new Date(rosterLock.locked_at).toLocaleString("vi-VN")})` : ""}. Đã đủ điều kiện khóa để bắt đầu giải đấu.</span>
                </div>
              ) : (
                <div className="condition-item unmet">
                  <span className="condition-icon">⚠️</span>
                  <div>
                    <strong>Điều kiện bắt đầu giải đấu (chuyển sang ONGOING):</strong>
                    <p>Giải đấu cần phải khóa đội hình và mỗi đội đã duyệt phải có ít nhất một tuyển thủ (PLAYER). Nút "Chuyển sang ONGOING" sẽ tự động hiển thị sau khi khóa thành công.</p>
                    {rosterStatusWarning && (
                      <p className="condition-warning-detail text-warning">⚠️ {rosterStatusWarning}</p>
                    )}
                    {approvedTeams.length === 0 ? (
                      <p className="condition-warning-detail text-warning">Chưa có đội tuyển nào được duyệt (APPROVED) vào giải.</p>
                    ) : (
                      (() => {
                        const missing = approvedTeams.filter(
                          (t) => approvedRosterStatuses[t.team_id]?.loaded && !approvedRosterStatuses[t.team_id]?.hasPlayer
                        );
                        if (missing.length > 0) {
                          return (
                            <p className="condition-warning-detail text-warning">
                              ⚠️ Đội chưa có tuyển thủ PLAYER: <strong>{missing.map((t) => t.name).join(", ")}</strong>. Cần bổ sung PLAYER trước khi khóa.
                            </p>
                          );
                        }
                        const allLoaded = approvedTeams.every((t) => approvedRosterStatuses[t.team_id]?.loaded);
                        if (allLoaded && approvedTeams.length > 0) {
                          return (
                            <p className="condition-warning-detail text-success">
                              ✓ Tất cả {approvedTeams.length} đội đã có PLAYER. Sẵn sàng để khóa đội hình!
                            </p>
                          );
                        }
                        return null;
                      })()
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {selectedTournament.status === "UPCOMING" && (
            <div className="roster-lock-controls">
              {tournamentCapabilities.can_lock_roster && !(tournamentCapabilities.roster_locked || rosterLock?.locked) && (
                <div className="lock-prompt">
                  <button
                    type="button"
                    className="button warning"
                    disabled={lockLoading || tournamentLoading}
                    onClick={() => void handleLockRoster()}
                  >
                    {lockLoading ? <><span className="spinner" /> Đang khóa đội hình...</> : "🔒 Khóa đội hình giải đấu"}
                  </button>
                </div>
              )}
              {lockError && (
                <div className="error-banner">
                  <span>{lockError}</span>
                  <button type="button" className="button secondary" onClick={() => void handleLockRoster()}>Thử lại</button>
                </div>
              )}
              {lockNotice && <div className="notice-banner">{lockNotice}</div>}
            </div>
          )}
          <div className="status-actions">{tournamentCapabilities.allowed_status_transitions.map((status) => <button className="button secondary" key={status} disabled={tournamentLoading} onClick={() => void changeTournamentStatus(status)}>Chuyển sang {status}</button>)}</div>{tournamentCapabilities.can_update && tournamentCapabilities.editable_fields.length > 0 && (
          <form className="tournament-form edit-form" onSubmit={updateTournament}>
            {tournamentCapabilities.editable_fields.includes("name") && (
              <label>Tên giải đấu<input name="name" defaultValue={selectedTournament.name} minLength={3} maxLength={150} required /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("game_id") && (
              <label>Tựa game<select name="game_id" defaultValue={selectedTournament.game_id} required>
                {games.map((game) => <option key={game.game_id} value={game.game_id}>{game.name}</option>)}
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("format") && (
              <label>Thể thức<select name="format" defaultValue={selectedTournament.format}>
                <option value="SINGLE_ELIM">Single Elimination</option>
                <option value="DOUBLE_ELIM">Double Elimination</option>
                <option value="ROUND_ROBIN">Round Robin</option>
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("start_date") && (
              <label>Bắt đầu<input name="start_date" type="date" defaultValue={selectedTournament.start_date.slice(0, 10)} required /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("end_date") && (
              <label>Kết thúc<input name="end_date" type="date" defaultValue={selectedTournament.end_date ? selectedTournament.end_date.slice(0, 10) : ""} /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("area_id") && (
              <label>Khu vực<select name="area_id" defaultValue={selectedTournament.area_id ?? ""}>
                <option value="">Toàn cầu</option>
                {areas.map((area) => <option key={area.area_id} value={area.area_id}>{area.name}</option>)}
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("description") && (
              <label className="wide-field">Mô tả<textarea name="description" maxLength={2000} defaultValue={selectedTournament.description ?? ""} /></label>
            )}
            <button className="button" disabled={tournamentLoading}>Lưu thay đổi</button>
          </form>
        )}</div>}

        <div className="stages-section" data-testid="tournament-stages-section">
          <div className="section-header">
            <div>
              <h4>Vòng đấu / Giai đoạn ({stages.length})</h4>
              <p className="muted small-text">Các vòng đấu theo thứ tự diễn ra trong giải.</p>
            </div>
            {tournamentCapabilities?.can_manage_stages && !isCreatingStage && (
              <button
                type="button"
                className="button small"
                onClick={() => {
                  setIsCreatingStage(true);
                  setNewStageName("");
                  setNewStageOrder(String(stages.length > 0 ? Math.max(...stages.map((s) => s.sequence_order)) + 1 : 1));
                  setStageFormError("");
                }}
              >
                + Thêm vòng đấu
              </button>
            )}
          </div>

          {stagesNotice && <div className="notice-banner">{stagesNotice}</div>}
          {stagesError && (
            <div className="error-banner">
              <span>{stagesError}</span>
              <button
                type="button"
                className="button secondary small"
                onClick={() => void loadTournamentStages(selectedTournament.tournament_id, tournamentViewVersion.current)}
              >
                Thử lại
              </button>
            </div>
          )}

          {isCreatingStage && (
            <form className="stage-form create-form" onSubmit={(e) => void handleCreateStage(e)} data-testid="stage-create-form">
              <h5>Thêm vòng đấu mới</h5>
              {stageFormError && <div className="error-banner">{stageFormError}</div>}
              <div className="form-grid">
                <label>
                  Tên vòng đấu <span className="required">*</span>
                  <input
                    type="text"
                    required
                    maxLength={80}
                    placeholder="Ví dụ: Vòng bảng, Tứ kết, Chung kết..."
                    value={newStageName}
                    onChange={(e) => setNewStageName(e.target.value)}
                    disabled={stageActionLoading}
                  />
                </label>
                <label>
                  Thứ tự (#) <span className="required">*</span>
                  <input
                    type="number"
                    required
                    min="1"
                    value={newStageOrder}
                    onChange={(e) => setNewStageOrder(e.target.value)}
                    disabled={stageActionLoading}
                  />
                </label>
              </div>
              <div className="form-actions">
                <button type="submit" className="button small" disabled={stageActionLoading}>
                  {stageActionLoading ? <><span className="spinner" /> Đang thêm...</> : "Lưu vòng đấu"}
                </button>
                <button
                  type="button"
                  className="button secondary small"
                  disabled={stageActionLoading}
                  onClick={() => {
                    setIsCreatingStage(false);
                    setStageFormError("");
                  }}
                >
                  Hủy
                </button>
              </div>
            </form>
          )}

          {stagesLoading ? (
            <div className="loading-state">
              <span className="spinner" /> Đang tải danh sách vòng đấu...
            </div>
          ) : stages.length === 0 ? (
            <p className="muted">Giải đấu chưa có vòng đấu nào được thiết lập.</p>
          ) : (
            <div className="stage-list" data-testid="stage-list">
              {stages.map((stage, index) => {
                const isEditing = editingStageId === stage.stage_id;
                return (
                  <div
                    className={`stage-card ${isEditing ? "editing" : ""}`}
                    key={stage.stage_id}
                    data-stage-id={stage.stage_id}
                    data-sequence-order={stage.sequence_order}
                  >
                    {isEditing ? (
                      <form
                        className="stage-inline-edit"
                        onSubmit={(e) => void handleUpdateStage(stage.stage_id, e)}
                        data-testid={`stage-edit-form-${stage.stage_id}`}
                      >
                        {stageFormError && <div className="error-banner">{stageFormError}</div>}
                        <div className="form-grid">
                          <label>
                            Tên vòng đấu
                            <input
                              type="text"
                              required
                              maxLength={80}
                              value={editingStageName}
                              onChange={(e) => setEditingStageName(e.target.value)}
                              disabled={stageActionLoading}
                            />
                          </label>
                          <label>
                            Thứ tự (#)
                            <input
                              type="number"
                              required
                              min="1"
                              value={editingStageOrder}
                              onChange={(e) => setEditingStageOrder(e.target.value)}
                              disabled={stageActionLoading}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button type="submit" className="button small" disabled={stageActionLoading}>
                            {stageActionLoading ? "Đang lưu..." : "Lưu"}
                          </button>
                          <button
                            type="button"
                            className="button secondary small"
                            disabled={stageActionLoading}
                            onClick={() => {
                              setEditingStageId(null);
                              setStageFormError("");
                            }}
                          >
                            Hủy
                          </button>
                        </div>
                      </form>
                    ) : (
                      <div className="stage-row">
                        <div className="stage-info">
                          <span className="stage-badge">#{stage.sequence_order}</span>
                          <strong className="stage-name">{stage.name}</strong>
                        </div>
                        {tournamentCapabilities?.can_manage_stages && (
                          <div className="stage-actions">
                            <button
                              type="button"
                              className="button secondary small"
                              title="Chuyển lên"
                              disabled={index === 0 || stageActionLoading}
                              onClick={() => void handleMoveStage(index, "up")}
                            >
                              ▲ Lên
                            </button>
                            <button
                              type="button"
                              className="button secondary small"
                              title="Chuyển xuống"
                              disabled={index === stages.length - 1 || stageActionLoading}
                              onClick={() => void handleMoveStage(index, "down")}
                            >
                              ▼ Xuống
                            </button>
                            <button
                              type="button"
                              className="button secondary small"
                              disabled={stageActionLoading}
                              onClick={() => {
                                setEditingStageId(stage.stage_id);
                                setNewStageName("");
                                setNewStageOrder("");
                                setEditingStageName(stage.name);
                                setEditingStageOrder(String(stage.sequence_order));
                                setStageFormError("");
                              }}
                            >
                              Sửa
                            </button>
                            <button
                              type="button"
                              className="button secondary small danger-link"
                              disabled={stageActionLoading}
                              onClick={() => void handleDeleteStage(stage)}
                            >
                              Xóa
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="approved-teams-section">
          <h4>Đội tuyển tham gia ({approvedTeamsTotal})</h4>
          {approvedTeams.length === 0 ? (
            <p className="muted">Chưa có đội tuyển nào được nhận vào giải.</p>
          ) : (
            <>
              <div className="approved-teams-grid">
                {approvedTeams.map((team) => (
                  <div className="approved-team-card" data-team-id={team.team_id} key={team.team_id}>
                    <div className="team-basic-info">
                      <strong>{team.name}</strong>
                      <span className="tag">#{team.tag}</span>
                      {approvedRosterStatuses[team.team_id]?.loaded &&
                        !(tournamentCapabilities?.roster_locked || rosterLock?.locked) && (
                          approvedRosterStatuses[team.team_id]?.hasPlayer ? (
                            <span className="status-badge ready">Đã có PLAYER</span>
                          ) : (
                            <span className="status-badge missing-player">Chưa có PLAYER</span>
                          )
                        )}
                    </div>
                    <button
                      type="button"
                      className="link-button roster-btn"
                      onClick={() => void openTeamRoster(team.team_id, team.name, team.tag)}
                    >
                      {selectedRosterTeam?.team_id === team.team_id ? "Đóng đội hình ▲" : "Đội hình ▼"}
                    </button>
                  </div>
                ))}
              </div>

              {approvedTeamsTotal > APPROVED_TEAMS_PER_PAGE && (
                <div className="pagination-controls" data-testid="approved-teams-pagination">
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={approvedTeamsPage === 0}
                    onClick={() => void handleApprovedTeamsPageChange(approvedTeamsPage - 1)}
                  >
                    ‹ Trước
                  </button>
                  <span className="pagination-info">
                    Trang {approvedTeamsPage + 1} / {Math.max(1, Math.ceil(approvedTeamsTotal / APPROVED_TEAMS_PER_PAGE))} (Tổng {approvedTeamsTotal} đội)
                  </span>
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={approvedTeamsPage >= Math.ceil(approvedTeamsTotal / APPROVED_TEAMS_PER_PAGE) - 1}
                    onClick={() => void handleApprovedTeamsPageChange(approvedTeamsPage + 1)}
                  >
                    Sau ›
                  </button>
                </div>
              )}
            </>
          )}

          {selectedRosterTeam && (
            <div className="team-roster-panel" data-team-id={selectedRosterTeam.team_id}>
              <div className="panel-header">
                <div>
                  <span className="eyebrow">TOURNAMENT ROSTER</span>
                  <h5>
                    Đội hình: {selectedRosterTeam.name}
                    {selectedRosterTeam.tag && <span className="tag"> #{selectedRosterTeam.tag}</span>}
                  </h5>
                </div>
                <div className="header-badges">
                  {rosterData?.locked || rosterLock?.locked || tournamentCapabilities?.roster_locked ? (
                    <span className="status status-completed">🔒 Đã khóa (Snapshot)</span>
                  ) : (
                    <span className="status status-upcoming">📝 Bản nháp (Chưa khóa)</span>
                  )}
                  <button
                    type="button"
                    className="link-button"
                    onClick={resetRosterState}
                  >
                    Đóng ×
                  </button>
                </div>
              </div>

              {rosterLoading && (
                <div className="loading-state">
                  <span className="spinner" /> Đang tải dữ liệu đội hình...
                </div>
              )}

              {rosterError && (
                <div className="error-banner">
                  <span>{rosterError}</span>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void loadTeamRosterData(selectedRosterTeam.team_id, tournamentViewVersion.current)}
                  >
                    Thử lại
                  </button>
                </div>
              )}

              {rosterNotice && <div className="notice-banner">{rosterNotice}</div>}

              {!rosterLoading && (rosterData || !rosterError) && (
                <>
                  {!Boolean(rosterData?.locked || rosterLock?.locked || tournamentCapabilities?.roster_locked) &&
                  selectedTournament.status === "UPCOMING" &&
                  rosterCapabilities?.can_edit_roster ? (
                    <div className="roster-editor">
                      <div className="editor-heading">
                        <strong>Danh sách tuyển thủ tham gia giải đấu:</strong>
                        <span className="muted">
                          (Yêu cầu tối thiểu 1 tuyển thủ PLAYER để đủ điều kiện khóa giải)
                        </span>
                      </div>

                      {rosterDraftMembers.length === 0 ? (
                        <p className="muted empty-roster-msg">Chưa có tuyển thủ nào trong đội hình tham dự.</p>
                      ) : (
                        <div className="roster-members-list">
                          {rosterDraftMembers.map((m) => {
                            const displayName =
                              m.display_name ??
                              m.username ??
                              teamEligibleMembers.find((em) => em.user_id === m.user_id)?.username ??
                              `User #${m.user_id}`;
                            return (
                              <div className="roster-member-row" key={m.user_id}>
                                <div className="member-name-role">
                                  <strong>{displayName}</strong>
                                  <span className={`role-badge role-${m.role_in_team.toLowerCase()}`}>
                                    {m.role_in_team === "PLAYER" ? "Chính thức (PLAYER)" : "Dự bị (SUBSTITUTE)"}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="link-button danger-link"
                                  disabled={rosterSaving}
                                  onClick={() => removeMemberFromRosterDraft(m.user_id)}
                                >
                                  Gỡ khỏi đội hình
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {teamEligibleMembers.filter((em) => !rosterDraftMembers.some((m) => m.user_id === em.user_id)).length > 0 && (
                        <div className="add-member-form">
                          <label>
                            Thêm tuyển thủ từ danh sách đội:
                            <select
                              value=""
                              onChange={(e) => {
                                const uid = Number(e.target.value);
                                if (uid) {
                                  addMemberToRosterDraft(uid);
                                }
                              }}
                            >
                              <option value="" disabled>-- Chọn thành viên để thêm --</option>
                              {teamEligibleMembers
                                .filter((em) => !rosterDraftMembers.some((m) => m.user_id === em.user_id))
                                .map((em) => (
                                  <option key={em.user_id} value={em.user_id}>
                                    {em.username} ({em.role})
                                  </option>
                                ))}
                            </select>
                          </label>
                        </div>
                      )}

                      {teamEligibleMembers.length === 0 && (
                        <p className="muted small-text">
                          Đội chưa có thành viên PLAYER hoặc SUBSTITUTE đang hoạt động nào. Hãy thêm tuyển thủ vào đội tuyển trước.
                        </p>
                      )}

                      <div className="roster-save-actions">
                        <button
                          type="button"
                          className="button"
                          disabled={rosterSaving}
                          onClick={() => void saveRoster()}
                        >
                          {rosterSaving ? <><span className="spinner" /> Đang lưu...</> : "Lưu đội hình"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="roster-viewer">
                      {(!rosterData?.members || rosterData.members.length === 0) ? (
                        <p className="muted">Đội tuyển chưa có danh sách tuyển thủ.</p>
                      ) : (
                        <div className="roster-members-grid">
                          {rosterData.members.map((m) => (
                            <div className="roster-member-card" key={m.user_id}>
                              <strong>{m.display_name ?? `User #${m.user_id}`}</strong>
                              <span className={`role-badge role-${m.role_in_team.toLowerCase()}`}>
                                {m.role_in_team === "PLAYER" ? "Chính thức (PLAYER)" : "Dự bị (SUBSTITUTE)"}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </> 
              )}
            </div>
          )}
        </div>

        {selectedTournament.status === "UPCOMING" && tournamentCapabilities?.roster_locked === false && token && (
          (() => {
            const availableTeams = managedTeamsForTournament.filter(
              (team) => !allTournamentRegistrations.some((r) => r.team_id === team.team_id)
            );
            return availableTeams.length > 0 ? (
              <form className="registration-form" onSubmit={submitRegistration}>
                <h4>Đăng ký đội tham gia giải</h4>
                <div className="form-row">
                  <label>
                    Chọn đội tuyển
                    <select name="team_id" required defaultValue={availableTeams[0].team_id}>
                      {availableTeams.map((team) => (
                        <option key={team.team_id} value={team.team_id}>
                          {team.name} (#{team.tag})
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="button" disabled={registrationLoading}>Gửi đơn đăng ký</button>
                </div>
              </form>
            ) : null;
          })()
        )}

        {selectedTournament.status === "UPCOMING" && (tournamentCapabilities?.roster_locked || rosterLock?.locked) && token && (
          <div className="info-banner" style={{ marginTop: "16px" }}>
            🔒 Đội hình giải đấu đã khóa — Không thể gửi đơn đăng ký mới.
          </div>
        )}

        {(registrations.length > 0 || tournamentCapabilities?.can_review_registrations || registrationError) && (
          <div className="registrations-section">
            {(tournamentCapabilities?.roster_locked || rosterLock?.locked) && selectedTournament.status === "UPCOMING" && (
              <div className="info-banner">
                🔒 Đội hình giải đấu đã khóa — Thao tác duyệt đơn mới bị tạm dừng. Người quản lý giải vẫn có thể từ chối và quản lý đội vẫn có thể hủy đơn đang chờ.
              </div>
            )}
            <div className="section-header">
              <h4>Đơn đăng ký giải ({registrationTotal})</h4>
              {tournamentCapabilities?.can_review_registrations && (
                <select
                  className="filter-select"
                  value={registrationStatusFilter}
                  onChange={(e) => handleRegistrationFilterChange(e.target.value)}
                >
                  <option value="">Tất cả trạng thái</option>
                  <option value="PENDING">Chờ duyệt (PENDING)</option>
                  <option value="APPROVED">Đã duyệt (APPROVED)</option>
                  <option value="REJECTED">Từ chối (REJECTED)</option>
                  <option value="CANCELLED">Đã hủy (CANCELLED)</option>
                </select>
              )}
            </div>

            {registrationError && (
              <div className="error-banner">
                <span>{registrationError}</span>
                <button className="button secondary" onClick={() => void reloadTournamentDetailsData(selectedTournament)}>Thử lại</button>
              </div>
            )}
            {registrationNotice && <div className="notice-banner">{registrationNotice}</div>}

            {registrations.length === 0 ? (
              <p className="muted">Không có đơn đăng ký nào.</p>
            ) : (
              <>
                <div className="registration-list">
                {registrations.map((reg) => {
                  const teamName = teams.find((t) => t.team_id === reg.team_id)?.name ??
                                   managedTeamsForTournament.find((t) => t.team_id === reg.team_id)?.name ??
                                   `Đội #${reg.team_id}`;
                  const teamTag = teams.find((t) => t.team_id === reg.team_id)?.tag ??
                                  managedTeamsForTournament.find((t) => t.team_id === reg.team_id)?.tag;
                  const isMyManagedTeam = managedTeamsForTournament.some((t) => t.team_id === reg.team_id);
                  const canReview = tournamentCapabilities?.can_review_registrations;

                  return (
                    <div className="registration-card" data-registration-id={reg.registration_id} data-team-id={reg.team_id} key={reg.registration_id}>
                      <div className="reg-info">
                        <strong>{teamName} {teamTag && <span className="tag">#{teamTag}</span>}</strong>
                        <span className={`reg-badge reg-badge-${reg.status.toLowerCase()}`}>{reg.status}</span>
                        <p className="reg-meta">
                          Gửi: {new Date(reg.submitted_at).toLocaleString("vi-VN")}
                          {reg.rejection_reason && <span className="reg-reason"> · Lý do: {reg.rejection_reason}</span>}
                        </p>
                      </div>
                      <div className="reg-actions">
                        {canReview && reg.status === "PENDING" && selectedTournament.status === "UPCOMING" && (
                          <>
                            {tournamentCapabilities?.can_approve_registrations && (
                            <button
                              className="button small"
                              disabled={registrationLoading}
                              onClick={() => void decideRegistration(reg.registration_id, "APPROVED")}
                            >
                              Duyệt
                            </button>
                            )}
                            <button
                              className="button secondary small danger"
                              disabled={registrationLoading}
                              onClick={() => void decideRegistration(reg.registration_id, "REJECTED")}
                            >
                              Từ chối
                            </button>
                          </>
                        )}
                        {isMyManagedTeam && reg.status === "PENDING" && selectedTournament.status === "UPCOMING" && (
                          <button
                            className="button secondary small danger"
                            disabled={registrationLoading}
                            onClick={() => void cancelRegistration(reg.registration_id)}
                          >
                            Hủy đơn
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {registrationTotal > REGISTRATIONS_PER_PAGE && (
                <div className="pagination-controls" data-testid="registrations-pagination">
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={registrationPage === 0 || registrationLoading}
                    onClick={() => void handleRegistrationPageChange(registrationPage - 1)}
                  >
                    ‹ Trước
                  </button>
                  <span className="pagination-info">
                    Trang {registrationPage + 1} / {Math.max(1, Math.ceil(registrationTotal / REGISTRATIONS_PER_PAGE))} (Tổng {registrationTotal} đơn)
                  </span>
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={registrationPage >= Math.ceil(registrationTotal / REGISTRATIONS_PER_PAGE) - 1 || registrationLoading}
                    onClick={() => void handleRegistrationPageChange(registrationPage + 1)}
                  >
                    Sau ›
                  </button>
                </div>
              )}
            </>
          )}
          </div>
        )}
      </div>}
    </section>
    <section className="panel catalog-panel">
      <div className="panel-title"><h2>Quản trị catalog</h2><span>CAPABILITY</span></div>
      {globalCapabilityError && <div className="error-banner"><span>{globalCapabilityError}</span><button className="button secondary" onClick={() => void loadGlobalCapabilities()}>Thử lại</button></div>}
      {!globalCapabilityError && !globalCapabilities?.can_manage_catalog && <p className="muted">Bạn chưa được cấp quyền quản lý publisher, game và khu vực.</p>}
      {globalCapabilities?.can_manage_catalog && <>
        <div className="catalog-forms">
          <form onSubmit={submitPublisher}>
            <h3>Publisher</h3>
            <label>Tên publisher<input name="name" minLength={2} maxLength={120} required /></label>
            <button className="button" disabled={catalogLoading}>Thêm publisher</button>
          </form>
          <form onSubmit={submitGame}>
            <h3>Game</h3>
            <label>Tên game<input name="name" maxLength={120} required /></label>
            <label>Slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" maxLength={120} required /></label>
            <label>Publisher<select name="publisher_id" defaultValue="" required><option value="" disabled>Chọn publisher</option>{publishers.map((publisher) => <option key={publisher.publisher_id} value={publisher.publisher_id}>{publisher.name}</option>)}</select></label>
            <button className="button" disabled={catalogLoading}>Thêm game</button>
          </form>
          <form onSubmit={submitArea}>
            <h3>Khu vực</h3>
            <label>Tên khu vực<input name="name" minLength={2} maxLength={120} required /></label>
            <label>Mã<input name="code" minLength={2} pattern="[A-Z0-9]+(?:-[A-Z0-9]+)*" maxLength={30} required /></label>
            <label>Khu vực cha<select name="parent_id" defaultValue=""><option value="">Không có</option>{areas.map((area) => <option key={area.area_id} value={area.area_id}>{area.code} · {area.name}</option>)}</select></label>
            <button className="button" disabled={catalogLoading}>Thêm khu vực</button>
          </form>
        </div>
      </>}
      {catalogReloadError && <div className="catalog-reload">
        <p>Danh sách catalog có thể chưa phản ánh thao tác gần nhất.</p>
        <button className="button secondary" onClick={retryCatalogLoad} disabled={catalogLoading}>Thử tải lại danh sách</button>
      </div>}
      <div className="catalog-lists">
        <div><h3>Publishers</h3>{publishers.map((publisher) => <p className="catalog-item" key={publisher.publisher_id}><span>{publisher.name}</span>{globalCapabilities?.can_manage_catalog && <span><button className="link-button" onClick={() => editCatalogItem("publishers", publisher)}>Sửa</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("publishers", publisher.publisher_id, publisher.name)}>Xóa</button></span>}</p>)}</div>
        <div><h3>Games</h3>{games.map((game) => <p className="catalog-item" key={game.game_id}><span>{game.name} <small>({game.slug})</small></span>{globalCapabilities?.can_manage_catalog && <span><button className="link-button" onClick={() => editCatalogItem("games", game)}>Sửa</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("games", game.game_id, game.name)}>Xóa</button></span>}</p>)}</div>
        <div><h3>Khu vực</h3>{areas.map((area) => <p className="catalog-item" key={area.area_id}><span>{area.name} <small>({area.code})</small></span>{globalCapabilities?.can_manage_catalog && <span><button className="link-button" onClick={() => editCatalogItem("areas", area)}>Sửa</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("areas", area.area_id, area.name)}>Xóa</button></span>}</p>)}</div>
      </div>
    </section>
    <section className="panel teams-panel">
      <div className="panel-title"><h2>Đội tuyển</h2><span>{teams.length} đội</span></div>
      {user ? <form className="team-form" onSubmit={createTeam}>
        <label>Tên đội<input name="name" placeholder="Phoenix Gaming" minLength={2} maxLength={100} required /></label>
        <label>Tag<input name="tag" placeholder="PHX" minLength={2} maxLength={10} pattern="[A-Za-z0-9]+" required /></label>
        <label>Game<select name="game_id" defaultValue="" required><option value="" disabled>Chọn game</option>{games.map((game) => <option key={game.game_id} value={game.game_id}>{game.name}</option>)}</select></label>
        <button className="button" disabled={loading}>Tạo đội</button>
      </form> : <p className="muted">Đăng nhập để tạo đội mới. Danh sách đội vẫn được xem công khai.</p>}
      {teams.length === 0 ? <p className="muted">Chưa có đội tuyển.</p> : <div className="team-list">{teams.map((team) => <article data-team-id={team.team_id} key={team.team_id}>
        <div><h3>{team.name}</h3><p>#{team.tag} · {games.find((game) => game.game_id === team.game_id)?.name ?? "Game"}</p></div>
        <button className="link-button" onClick={() => viewTeam(team.team_id)}>Xem đội</button>
      </article>)}</div>}
      {selectedTeam && <div className="team-detail">
      <div className="panel-title"><h3>{selectedTeam.name} <span>#{selectedTeam.tag}</span></h3><button className="link-button" onClick={() => { setSelectedTeam(null); setTeamCapabilities(null); setTeamCapabilityError(""); }}>Đóng</button></div>
        <p>{games.find((game) => game.game_id === selectedTeam.game_id)?.name ?? "Game"}</p>
        {teamCapabilityError && <div className="error-banner"><span>{teamCapabilityError}</span><button className="button secondary" onClick={() => void loadTeamCapabilities(selectedTeam.team_id)}>Thử lại</button></div>}
        {canManageSelectedTeam && <form className="member-form" onSubmit={addMember}>
          <label>Tên đăng nhập<input name="username" placeholder="username" maxLength={50} required /></label>
          <label>Vị trí<select name="role_in_team" defaultValue="PLAYER"><option value="MANAGER">MANAGER</option><option value="COACH">COACH</option><option value="PLAYER">PLAYER</option><option value="SUBSTITUTE">SUBSTITUTE</option></select></label>
          <button className="button" disabled={memberLoading}>Thêm thành viên</button>
        </form>}
        <h4>Thành viên và lịch sử ({selectedTeam.members.length})</h4>
        {selectedTeam.members.length === 0 ? <p className="muted">Chưa có thành viên.</p> : <div className="member-list">{selectedTeam.members.map((member) => <div className={`member-row ${member.status === "ENDED" ? "ended" : ""}`} key={member.membership_id}>
          <div>
            <strong>{member.username}</strong>
            <p>{member.role} · {member.status === "ACTIVE" ? "Đang hoạt động" : "Đã rời đội"} · Tham gia {member.joined_date}{member.left_date ? ` · Rời đội ${member.left_date}` : ""}</p>
          </div>
          {user && <div className="member-actions">
            {canManageSelectedTeam && member.status === "ACTIVE" && <select aria-label={`Vị trí của ${member.username}`} value={member.role} disabled={memberLoading} onChange={(event) => updateMemberRole(member.membership_id, event.target.value)}>
              <option value="MANAGER">MANAGER</option><option value="COACH">COACH</option><option value="PLAYER">PLAYER</option><option value="SUBSTITUTE">SUBSTITUTE</option>
            </select>}
            {member.status === "ACTIVE" && (canManageSelectedTeam || member.user_id === user.id) && <button className="link-button danger-link" disabled={memberLoading} onClick={() => endMembership(member)}>{member.user_id === user.id ? "Rời đội" : "Kết thúc"}</button>}
          </div>}
        </div>)}</div>}
      </div>}
    </section>
  </main>;
}
