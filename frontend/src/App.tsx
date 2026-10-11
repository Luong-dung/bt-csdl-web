import { useEffect, useState } from "react";
import "./styles.css";

type Tournament = { tournament_id: number; name: string; format: string; status: string; start_date: string };
const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export default function App() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/tournaments`)
      .then((response) => {
        if (!response.ok) throw new Error("Không thể tải danh sách giải đấu");
        return response.json();
      })
      .then(setTournaments)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  return <main className="shell">
    <header><span className="eyebrow">ESPORTS OPERATIONS</span><h1>Quản lý giải đấu đa game</h1><p>Một nền tảng thống nhất cho đội tuyển, lịch thi đấu và bảng xếp hạng.</p></header>
    <section className="stats"><div><strong>{tournaments.length}</strong><span>Giải đấu</span></div><div><strong>4</strong><span>Phạm vi vai trò</span></div><div><strong>10</strong><span>Tuần triển khai</span></div></section>
    <section className="panel"><div className="panel-title"><h2>Giải đấu sắp diễn ra</h2><span>API v1</span></div>
      {error && <p className="error">{error}. Hãy khởi động backend để xem dữ liệu.</p>}
      {!error && tournaments.length === 0 && <p className="muted">Chưa có giải đấu. Dữ liệu sẽ xuất hiện sau khi chạy seed.</p>}
      <div className="tournament-list">{tournaments.map((item) => <article key={item.tournament_id}><div><h3>{item.name}</h3><p>{item.format} · {item.start_date}</p></div><b>{item.status}</b></article>)}</div>
    </section>
  </main>;
}
