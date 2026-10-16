import { FormEvent, useEffect, useState } from "react";
import "./styles.css";

type User = { id: number; username: string; email?: string; role: string };
type AuthMode = "login" | "register";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "esports_access_token";

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "Yêu cầu không thành công");
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

  useEffect(() => {
    if (!token) return;
    request<User>("/auth/me", {}, token).then(setUser).catch(() => {
      localStorage.removeItem(TOKEN_KEY);
      setToken("");
      setError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    });
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
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setNotice("Bạn đã đăng xuất.");
  };

  return <main className="shell">
    <header className="hero">
      <div>
        <span className="eyebrow">W42-05 · IDENTITY</span>
        <h1>Đăng nhập vào nền tảng esports</h1>
        <p>Đăng ký tài khoản, xác thực bằng API thật và duy trì phiên làm việc bằng JWT.</p>
      </div>
      {user && <div className="account"><span>Xin chào, <strong>{user.username}</strong></span><button className="button secondary" onClick={logout}>Đăng xuất</button></div>}
    </header>

    {(error || notice) && <p className={error ? "message error" : "message success"}>{error || notice}</p>}

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
        <span className="eyebrow">PHẠM VI W42-05</span>
        <h2>Luồng xác thực</h2>
        <ul>
          <li>Đăng ký tài khoản mới qua <code>POST /auth/register</code></li>
          <li>Đăng nhập qua <code>POST /auth/login</code></li>
          <li>Lưu access token vào localStorage</li>
          <li>Xác nhận phiên qua <code>GET /auth/me</code></li>
          <li>Đăng xuất và xóa token khỏi trình duyệt</li>
        </ul>
      </aside>
    </section>
  </main>;
}
