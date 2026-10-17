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

Prefix `/api/v1/catalog`. `GET` mở công khai; `POST`/`PATCH`/`DELETE` cần JWT và quyền `ADMIN` toàn hệ thống.

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

## API đội tuyển và thành viên — W42-04

Prefix `/api/v1/teams`. Xem đội và thành viên mở công khai; thao tác ghi cần JWT.

| Thao tác | Endpoint | Ai được làm |
|---|---|---|
| Danh sách / chi tiết đội | `GET /teams?game_id=`, `GET /teams/{id}` | Công khai |
| Tạo đội | `POST /teams` | Người đăng nhập chưa thuộc đội nào; trở thành `MANAGER` |
| Danh sách thành viên | `GET /teams/{id}/members?include_history=true` | Công khai |
| Thêm thành viên | `POST /teams/{id}/members` | `MANAGER` của đội hoặc `ADMIN` |
| Đổi vị trí | `PATCH /teams/{id}/members/{membership_id}` | `MANAGER` của đội hoặc `ADMIN` |
| Kết thúc membership | `POST /teams/{id}/members/{membership_id}/end` | `MANAGER`/`ADMIN`, hoặc chính thành viên tự rời đội |

- Vị trí trong đội: `MANAGER`, `COACH`, `PLAYER`, `SUBSTITUTE`. Tag đội chỉ gồm chữ/số, được lưu dạng in hoa.
- Một tài khoản chỉ có một membership `ACTIVE` tại một thời điểm (`409`, kèm tên đội hiện tại).
- Kết thúc membership chuyển trạng thái sang `ENDED` và ghi `left_date`, không xóa để giữ lịch sử chuyển nhượng. Người đã rời đội chỉ được thêm lại vào cùng đội từ ngày hôm sau.
- Đội luôn phải còn ít nhất một `MANAGER` đang hoạt động (`409`).
- Thêm, đổi vị trí, kết thúc thành viên đều được ghi vào `audit_logs`.

Kiểm tra từ thư mục `backend`:

```powershell
python -m pytest tests/test_team_api.py -q
```

## Smoke tests — W42-07

Auth, catalog và teams API được kiểm tra bằng pytest/FastAPI TestClient trên SQLite in-memory; không cần PostgreSQL hoặc thông tin trong `.env`.

Chạy toàn bộ backend test suite từ thư mục `backend`:

```powershell
python -m pytest -q
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

## Phân quyền API — W42-02

- Ghi catalog: `ADMIN` toàn hệ thống; tạo giải: `ADMIN` hoặc `ORGANIZER` toàn hệ thống.
- Role của user và assignment `GLOBAL` với `scope_id=NULL` cấp quyền toàn hệ thống. Assignment theo tài nguyên chỉ áp dụng khi khớp chính xác loại và ID phạm vi.
- Tạo đội: mọi user đã đăng nhập; người tạo trở thành `MANAGER` của đội mới.
- Thêm thành viên: `ADMIN` toàn hệ thống, membership `MANAGER` đang `ACTIVE` chưa có ngày rời đội, hoặc assignment `TEAM_MANAGER` đúng `TEAM`/`ORGANIZATION` chứa đội. Role `TEAM_MANAGER` của user không tự cấp quyền trên mọi đội.
- Thiếu JWT, JWT sai/hết hạn hoặc subject không hợp lệ: `401`; đăng nhập nhưng thiếu quyền: `403`. Các API đọc catalog, đội và giải vẫn công khai.
- Helper `middleware.auth.has_role` hỗ trợ kiểm tra assignment theo giải cho các endpoint triển khai sau. Chưa có API cấp/thu hồi assignment; không thay schema.

Chạy từ thư mục `backend`: `.\venv\Scripts\python.exe -m pytest -q`. Test quyền dùng JWT thật và SQLite riêng, không thay đổi database local.

Kiểm tra quyền và catalog trên PostgreSQL cấu hình trong `backend/.env`:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_permissions.py tests/test_catalog_api.py --postgres -q
```

Mỗi test chạy hai migration và seed trong schema tạm riêng. Session của API dùng savepoint bên trong transaction ngoài; kết thúc test rollback toàn bộ và xác nhận schema tạm đã biến mất. Không ghi dữ liệu vào schema hiện có. Request chạy qua FastAPI TestClient; test quyền dùng JWT thật, test CRUD catalog dùng user ADMIN giả lập như bộ test SQLite.
