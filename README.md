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
python seed.py
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

Sau đó chạy lại `alembic upgrade head` và `python seed.py` trong thư mục `backend`.

## Seed dữ liệu nền — W42-01

Lệnh `python seed.py` dùng cấu hình PostgreSQL trong `backend/.env`. Chạy migration hoặc tạo schema trước khi seed; script không tự tạo bảng.

- Role: `ADMIN`, `ORGANIZER`, `REFEREE`, `TEAM_MANAGER`, `PLAYER`, `VIEWER`.
- Nhà phát hành: Riot Games và Valve.
- Game: League of Legends, VALORANT, Counter-Strike 2 và Dota 2.
- Khu vực: `GLOBAL` → `APAC` → `VN` → `VN-HCM`.

Script chạy trong một transaction, chỉ thêm bản ghi còn thiếu và giữ nguyên dữ liệu đã có. Có thể chạy lại mà không tạo bản ghi trùng. ID được database cấp tự động; seed không tạo tài khoản hay gán quyền cho người dùng. Tên role là dữ liệu nền cho phần phân quyền W42-02.

Kiểm tra seed từ thư mục `backend`:

```powershell
python -m pytest tests/test_seed.py -q
```

## API catalog — W42-03

Prefix `/api/v1/catalog`. `GET` mở công khai; `POST`/`PATCH`/`DELETE` cần JWT (phân quyền theo role bổ sung ở W42-02).

| Tài nguyên | Endpoint | Lọc danh sách |
|---|---|---|
| Nhà phát hành | `/publishers`, `/publishers/{id}` | — |
| Game | `/games`, `/games/{id}` | `?publisher_id=` |
| Khu vực | `/areas`, `/areas/{id}` | `?parent_id=` |

- `slug` game dạng `league-of-legends`; `code` khu vực dạng `VN-HCM`. Trường lạ trong body bị từ chối.
- Trùng tên/slug/mã trả `409`; nhà phát hành hoặc khu vực cha không tồn tại trả `422`.
- Khu vực không được nhận chính nó hoặc khu vực con làm cha (`422`). `PATCH` với `parent_id: null` để tách khỏi khu vực cha.
- Không xóa được nhà phát hành còn game, game đang được đội/giải đấu dùng, khu vực còn khu vực con hoặc đang được giải đấu dùng (`409`).

Kiểm tra từ thư mục `backend`:

```powershell
python -m pytest tests/test_catalog_api.py -q
```

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

Nhật ký các yêu cầu đã gửi AI và phần code đã áp dụng được lưu tại [docs/AI_WORK_LOG.md](docs/AI_WORK_LOG.md).

## Lộ trình 10 tuần

1. Tuần 1–2: chuẩn hóa kiến trúc, identity, role và audit log.
2. Tuần 3–4: catalog game/khu vực và quản lý tổ chức–đội.
3. Tuần 5–7: đăng ký giải, roster, stage, match và standings.
4. Tuần 8–10: frontend quản trị, kiểm thử, CI và staging.
