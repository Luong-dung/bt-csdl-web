import { FormEvent, useEffect, useRef, useState } from "react";
import "./styles.css";

type User = { id: number; username: string; email?: string; role: string };
type Game = { game_id: number; name: string; slug: string };
type Team = { team_id: number; name: string; tag: string; game_id: number };
type AuthMode = "login" | "register";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "esports_access_token";

class RequestError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new RequestError(body?.detail ?? "Yêu cầu không thành công", response.status);
  }
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
  const [teams, setTeams] = useState<Team[]>([]);
  const sessionVersion = useRef(0);

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

  useEffect(() => {
    loadTeams();
  }, []);

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
          localStorage.removeItem(TOKEN_KEY);
          setToken("");
          setUser(null);
          setError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
          return;
        }
        setError("Không thể kiểm tra phiên đăng nhập. Hãy thử lại.");
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [token, authCheckAttempt]);

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
    setNotice("Bạn đã đăng xuất.");
  };

  const createTeam = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setError("");
    setNotice("");
    setLoading(true);
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
      event.currentTarget.reset();
      await loadTeams();
      setNotice("Tạo đội thành công. Bạn đã trở thành MANAGER của đội.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return <main className="shell">
    <header className="hero">
      <div>
        <span className="eyebrow">W42-06 · TEAMS</span>
        <h1>Danh sách và tạo đội</h1>
        <p>Khám phá các đội tuyển và tạo đội mới bằng tài khoản đã xác thực.</p>
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
        <a href={`#team-${team.team_id}`}>Xem đội</a>
      </article>)}</div>}
    </section>
  </main>;
}
