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
  editable_fields: string[]; allowed_status_transitions: string[];
};
type RegistrationStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
type TournamentRegistrationItem = {
  registration_id: number; tournament_id: number; team_id: number;
  status: RegistrationStatus; submitted_by: number | null; submitted_at: string;
  reviewed_by: number | null; reviewed_at: string | null; rejection_reason: string | null;
  cancelled_by: number | null; cancelled_at: string | null;
};
type ApprovedTeam = { team_id: number; name: string; tag: string; game_id: number };
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
  const sessionVersion = useRef(0);
  const tournamentViewVersion = useRef(0);

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
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
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
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
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
    setManagedTeamsForTournament([]);
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationError("");
    setRegistrationNotice("");
    setRegistrationStatusFilter("");
  };

  const loadTournamentCapabilities = async (tournamentId: number, authToken = token, expectedVersion?: number) => {
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setTournamentCapabilities(null);
      setCapabilityError("");
      return;
    }
    try {
      setCapabilityError("");
      const caps = await request<TournamentCapabilities>(`/tournaments/${tournamentId}/capabilities`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setTournamentCapabilities(caps);
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setTournamentCapabilities(null);
      setCapabilityError((reason as Error).message || "Không thể tải quyền quản lý giải đấu.");
    }
  };

  // Lưu ý: Endpoint /tournaments/{id}/teams mặc định limit 50; trong phạm vi demo W44 danh sách hiển thị tối đa 50 đội.
  const loadApprovedTeams = async (tournamentId: number, expectedVersion?: number) => {
    try {
      const list = await request<ApprovedTeam[]>(`/tournaments/${tournamentId}/teams`);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setApprovedTeams(list);
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setApprovedTeams([]);
      setRegistrationError((reason as Error).message);
    }
  };

  // Lưu ý: Endpoint /teams/managed mặc định limit 50; trong phạm vi demo W44 danh sách hiển thị tối đa 50 đội.
  const loadManagedTeamsForTournament = async (gameId: number, authToken = token, expectedVersion?: number): Promise<Team[]> => {
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      setManagedTeamsForTournament([]);
      return [];
    }
    try {
      const list = await request<Team[]>(`/teams/managed?game_id=${gameId}`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      setManagedTeamsForTournament(list);
      return list;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      setManagedTeamsForTournament([]);
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return [];
      }
      setRegistrationError((reason as Error).message);
      return [];
    }
  };

  // Lưu ý: Endpoint /tournaments/{id}/registrations mặc định limit 50, hỗ trợ tối đa 100 qua limit param.
  const loadTournamentRegistrations = async (
    tournamentId: number,
    statusFilter?: string,
    authToken = token,
    expectedVersion?: number,
    managedTeams?: Team[],
  ) => {
    setRegistrationError("");
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      return;
    }
    try {
      const unfilteredPromise = request<TournamentRegistrationItem[]>(`/tournaments/${tournamentId}/registrations?limit=100`, {}, authToken);
      const filteredPromise = statusFilter
        ? request<TournamentRegistrationItem[]>(`/tournaments/${tournamentId}/registrations?status=${statusFilter}&limit=100`, {}, authToken)
        : unfilteredPromise;

      const [unfilteredList, fetchedFilteredList] = await Promise.all([unfilteredPromise, filteredPromise]);
      // Không lọc thì hai promise trả cùng một mảng; sao chép để bổ sung bên dưới không nhân đôi đơn.
      const filteredList = statusFilter ? fetchedFilteredList : [...fetchedFilteredList];

      // Nếu danh sách đủ limit 100 (có thể còn trang sau) và có đội người dùng quản lý:
      // Kiểm tra thêm từng đội quản lý chưa có trong unfilteredList qua ?team_id= để đảm bảo không bị sót đơn ngoài trang
      const teamsToCheck = managedTeams ?? managedTeamsForTournament;
      if (unfilteredList.length >= 100 && teamsToCheck.length > 0) {
        const existingTeamIds = new Set(unfilteredList.map((r) => r.team_id));
        const missingTeams = teamsToCheck.filter((t) => !existingTeamIds.has(t.team_id));
        if (missingTeams.length > 0) {
          const extraResults = await Promise.all(
            missingTeams.map((t) =>
              request<TournamentRegistrationItem[]>(`/tournaments/${tournamentId}/registrations?team_id=${t.team_id}`, {}, authToken).catch(() => [])
            )
          );
          for (const extraList of extraResults) {
            for (const item of extraList) {
              if (!existingTeamIds.has(item.team_id)) {
                unfilteredList.push(item);
                existingTeamIds.add(item.team_id);
                if (!statusFilter || item.status === statusFilter) {
                  filteredList.push(item);
                }
              }
            }
          }
        }
      }

      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setAllTournamentRegistrations(unfilteredList);
      setRegistrations(filteredList);
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      if ((reason as RequestError).status === 403) {
        setRegistrations([]);
        setAllTournamentRegistrations([]);
      } else {
        setRegistrationError((reason as Error).message);
      }
    }
  };

  const reloadTournamentDetailsData = async (tournament: Tournament) => {
    const version = tournamentViewVersion.current;
    setRegistrationError("");
    const managedTeams = await loadManagedTeamsForTournament(tournament.game_id, token, version);
    if (tournamentViewVersion.current !== version) return;
    await Promise.all([
      loadTournamentCapabilities(tournament.tournament_id, token, version),
      loadApprovedTeams(tournament.tournament_id, version),
      loadTournamentRegistrations(tournament.tournament_id, registrationStatusFilter, token, version, managedTeams),
    ]);
  };

  useEffect(() => {
    if (!selectedTournament) return;
    if (!token) {
      setTournamentCapabilities(null);
      setCapabilityError("");
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      setManagedTeamsForTournament([]);
      setRegistrationError("");
      setRegistrationNotice("");
      return;
    }
    const version = tournamentViewVersion.current;
    void (async () => {
      const managedTeams = await loadManagedTeamsForTournament(selectedTournament.game_id, token, version);
      if (tournamentViewVersion.current !== version) return;
      await Promise.all([
        loadTournamentCapabilities(selectedTournament.tournament_id, token, version),
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, version, managedTeams),
      ]);
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
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter),
        loadManagedTeamsForTournament(selectedTournament.game_id),
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
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter),
        loadManagedTeamsForTournament(selectedTournament.game_id),
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
      await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter),
        loadApprovedTeams(selectedTournament.tournament_id),
        loadTournamentCapabilities(selectedTournament.tournament_id),
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

  const handleRegistrationFilterChange = async (status: string) => {
    setRegistrationStatusFilter(status);
    if (!selectedTournament || !token) return;
    const version = tournamentViewVersion.current;
    try {
      const query = status ? `?status=${status}&limit=100` : `?limit=100`;
      const list = await request<TournamentRegistrationItem[]>(
        `/tournaments/${selectedTournament.tournament_id}/registrations${query}`,
        {},
        token
      );
      if (tournamentViewVersion.current !== version) return;
      setRegistrations(list);
    } catch (reason) {
      if (tournamentViewVersion.current !== version) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      if ((reason as RequestError).status === 403) {
        setRegistrations([]);
      } else {
        setRegistrationError((reason as Error).message);
      }
    }
  };

  const viewTournament = async (tournamentId: number) => {
    const version = ++tournamentViewVersion.current;
    setError("");
    setNotice("");
    setRegistrationError("");
    setRegistrationNotice("");
    try {
      const tournament = await request<Tournament>(`/tournaments/${tournamentId}`);
      if (tournamentViewVersion.current !== version) return;
      setSelectedTournament(tournament);

      const managedTeamsPromise = loadManagedTeamsForTournament(tournament.game_id, token, version);
      const capsPromise = loadTournamentCapabilities(tournamentId, token, version);
      const approvedPromise = loadApprovedTeams(tournamentId, version);

      const managedTeams = await managedTeamsPromise;
      if (tournamentViewVersion.current !== version) return;

      await Promise.all([
        capsPromise,
        approvedPromise,
        loadTournamentRegistrations(tournamentId, registrationStatusFilter, token, version, managedTeams),
      ]);
    } catch (reason) {
      if (tournamentViewVersion.current !== version) return;
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
      await loadTournamentCapabilities(updated.tournament_id);
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
      await loadTournamentCapabilities(updated.tournament_id);
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
        return <article className="tournament-card" key={tournament.tournament_id} onClick={() => void viewTournament(tournament.tournament_id)}>
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
        <div className="detail-stats"><div><span>Trạng thái</span><strong className={`status status-${selectedTournament.status.toLowerCase()}`}>{selectedTournament.status}</strong></div><div><span>Ngày bắt đầu</span><strong>{new Date(selectedTournament.start_date).toLocaleDateString("vi-VN")}</strong></div><div><span>Khu vực</span><strong>{areas.find((area) => area.area_id === selectedTournament.area_id)?.name ?? "Toàn cầu"}</strong></div></div>
        {selectedTournament.description && <p className="detail-description">{selectedTournament.description}</p>}
        {capabilityError && <div className="error-banner"><span>{capabilityError}</span><button className="button secondary" onClick={() => void loadTournamentCapabilities(selectedTournament.tournament_id)}>Thử lại</button></div>}
        {tournamentCapabilities?.can_manage && <div className="manage-panel"><div className="panel-title"><h4>Điều hành giải</h4><span>CAPABILITY VERIFIED</span></div><div className="status-actions">{tournamentCapabilities.allowed_status_transitions.map((status) => <button className="button secondary" key={status} disabled={tournamentLoading} onClick={() => void changeTournamentStatus(status)}>Chuyển sang {status}</button>)}</div>{tournamentCapabilities.can_update && tournamentCapabilities.editable_fields.length > 0 && (
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

        <div className="approved-teams-section">
          <h4>Đội tuyển tham gia ({approvedTeams.length}{approvedTeams.length >= 50 ? "+" : ""})</h4>
          {approvedTeams.length === 0 ? (
            <p className="muted">Chưa có đội tuyển nào được nhận vào giải.</p>
          ) : (
            <div className="approved-teams-grid">
              {approvedTeams.map((team) => (
                <div className="approved-team-card" key={team.team_id}>
                  <strong>{team.name}</strong>
                  <span className="tag">#{team.tag}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {selectedTournament.status === "UPCOMING" && token && (
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

        {(registrations.length > 0 || tournamentCapabilities?.can_review_registrations || registrationError) && (
          <div className="registrations-section">
            <div className="section-header">
              <h4>Đơn đăng ký giải ({registrations.length})</h4>
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
                    <div className="registration-card" key={reg.registration_id}>
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
                            <button
                              className="button small"
                              disabled={registrationLoading}
                              onClick={() => void decideRegistration(reg.registration_id, "APPROVED")}
                            >
                              Duyệt
                            </button>
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
      {teams.length === 0 ? <p className="muted">Chưa có đội tuyển.</p> : <div className="team-list">{teams.map((team) => <article key={team.team_id}>
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
