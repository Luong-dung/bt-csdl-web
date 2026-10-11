# Esports Tournament Management Platform

Nền tảng quản lý giải đấu esports đa game, được xây dựng theo hướng modular monolith để nhóm có thể phát triển độc lập từng module và review chéo qua Pull Request.

## Kiến trúc

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL.
- **Frontend:** React, TypeScript, Vite.
- **Identity:** JWT, mật khẩu băm Argon2, role assignment theo phạm vi và audit log.
- **Domain:** publisher/game, competition area, organization/team, membership, tournament/stage/match, roster và standings.

## Chạy backend trên Windows

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

API và Swagger: <http://127.0.0.1:8000/docs>. Health check: <http://127.0.0.1:8000/health>.

Tạo database PostgreSQL trước khi migrate:

```sql
CREATE DATABASE esports_tournament;
```

Nếu cần cài đặt nhanh không dùng Alembic, chạy [schema_postgres.sql](database/schema_postgres.sql), sau đó chạy seed tương ứng.

> Project đã được reset theo schema mới. Nếu database đang dùng schema cũ, hãy tạo database mới hoặc xóa database cũ rồi chạy lại migration; không chạy API trên schema cũ vì tên/cấu trúc bảng đã thay đổi.

```sql
DROP DATABASE IF EXISTS esports_tournament;
CREATE DATABASE esports_tournament;
```

Sau đó chạy lại `alembic upgrade head`. Dữ liệu mẫu sẽ được bổ sung cùng module seed khi nghiệp vụ tương ứng hoàn thiện.

## Chạy frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend mặc định gọi `http://127.0.0.1:8000/api/v1`. Có thể đổi bằng biến `VITE_API_URL`.

## Quy ước phát triển

Mỗi thành viên làm trên nhánh `feature/<ten-tinh-nang>`, mở Pull Request vào `main` và review chéo. Migration phải được tạo bằng Alembic; không sửa migration đã chạy trên môi trường dùng chung.

Phân công công việc, trạng thái, tiêu chí nghiệm thu và đánh giá theo tuần được quản lý tại [docs/TEAM_WORK_PLAN.md](docs/TEAM_WORK_PLAN.md).

## Lộ trình 10 tuần

1. Tuần 1–2: chuẩn hóa kiến trúc, identity, role và audit log.
2. Tuần 3–4: catalog game/khu vực và quản lý tổ chức–đội.
3. Tuần 5–7: đăng ký giải, roster, stage, match và standings.
4. Tuần 8–10: frontend quản trị, kiểm thử, CI và staging.
