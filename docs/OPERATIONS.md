# Vận hành: migration, backup/restore, staging và release checklist (W48-02)

- **Ngày lập:** `2026-11-26`; **người viết:** DUNG; kiểm chứng trên PostgreSQL 18.6 local (Windows).
- **Nguồn chuẩn của schema:** migration Alembic trong `backend/alembic`. [`database/schema_postgres.sql`](../database/schema_postgres.sql) là bản đọc được, phải khớp đúng `alembic upgrade head` — test `tests/test_schema_sql_sync.py` bắt lệch.
- Mọi lệnh dưới đây chạy trên **database riêng** (`_demo`, `_test`, `_staging`), không chạy trên DB cá nhân/production. Không ghi mật khẩu vào lệnh, file hay log; nhập qua biến môi trường trong phiên terminal rồi xóa.

## 1. Migration

### Lệnh

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current          # phiên bản hiện tại
.\.venv\Scripts\python.exe -m alembic history          # chuỗi migration
.\.venv\Scripts\python.exe -m alembic upgrade head     # nâng lên mới nhất
.\.venv\Scripts\python.exe -m alembic downgrade -1     # hạ một bước (BACKUP TRƯỚC, xem 1.3)
```

Head hiện tại: `f47a04b00001` (W47-04). Bản cuối trước W47: `c46a01b00001` (W46).

### Kết quả kiểm tra 26/11/2026

| Kiểm tra | Cách làm | Kết quả |
|---|---|---|
| `schema_postgres.sql` khớp migration | `test_schema_sql_sync.py`: migrate `head` vào schema tạm, nạp file SQL vào schema tạm khác, so cột/kiểu/nullable/default, PK/UNIQUE/FK, CHECK/FK action, index | Đạt sau khi sửa file SQL (xem 1.2); đã thử cài lệch cố ý → test báo đúng cột |
| Hạ W47 → W46 → `head` (schema rỗng) | `test_w47_migrations_downgrade_and_upgrade_cleanly` | Đạt, schema sau = trước |
| Hạ về `base` → `head` | `test_full_downgrade_to_base_and_back` | Đạt |
| Hạ W47 → W46 → `head` **có dữ liệu** | DB `_test` riêng seed demo đầy đủ (W48-01) rồi downgrade/upgrade | Đạt, số dòng 20 bảng giữ nguyên, version `f47a04b00001`; DB đã xóa |

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_schema_sql_sync.py --postgres -m postgres -q
```

### 1.2. Lệch đã sửa trong `schema_postgres.sql`

Đối chiếu ngày 26/11 cho thấy file SQL đã trôi khỏi migration từ lâu (CI không kiểm):

- **Thiếu hẳn bảng `tournament_registrations`** (cùng UNIQUE, 3 CHECK, 5 FK, index `team_id`).
- `team_memberships`: CHECK chỉ cho `ACTIVE/TRANSFERRED/TERMINATED/RETIRED` trong khi app ghi `ENDED` → DB dựng từ file SQL sẽ lỗi khi kết thúc membership; thiếu UNIQUE `(team_id, user_id, joined_date)`.
- Khác kiểu/ràng buộc: `users.username/email` CITEXT (migration: VARCHAR), `audit_logs.details` JSONB (migration: JSON), `log_id` BIGSERIAL, `roles.description` (migration không có), nhiều DEFAULT/NOT NULL và `ON DELETE SET NULL` (matches team/winner/next, teams.organization) không có trong DB thật.

File đã sửa để phản ánh **đúng DB thật**. Các điểm file cũ "tốt hơn" (CITEXT cho username/email không phân biệt hoa thường, JSONB, DEFAULT, `ON DELETE SET NULL`, bỏ 5 index trùng khóa chính) là **đề xuất migration sau này**, cần nhóm quyết vì đổi hành vi (CITEXT đổi cách so trùng username/email).

### 1.3. Lưu ý khi downgrade

- `d47a01b00001` (W47-01) **từ chối downgrade** nếu đã có assignment bị thu hồi (nếu không, trọng tài đã thu hồi sẽ có quyền lại) và xóa `granted_by/at`, `revoked_by/at`.
- `f47a04b00001` (W47-04) xóa `competition_areas.country_code` → **mất liên kết khu vực–quốc gia**; nâng lại không khôi phục.
- `e47a02b00001` (W47-02) xóa `audit_logs.tournament_id/resource_id` (suy ra từ `details`).
- Quy tắc: **backup (mục 2) trước mọi downgrade** trên DB có dữ liệu; downgrade chỉ để thử/khắc phục sự cố, khôi phục bằng restore thay vì downgrade nếu có thể.

## 2. Backup và restore PostgreSQL

Công cụ: `pg_dump`/`pg_restore` đi kèm PostgreSQL (`C:\Program Files\PostgreSQL\18\bin`, không có sẵn trong PATH). Dùng định dạng custom `-Fc` (nén, restore chọn lọc được).

```powershell
$pg = 'C:\Program Files\PostgreSQL\18\bin'
$env:PGHOST = '127.0.0.1'; $env:PGPORT = '5432'; $env:PGUSER = 'postgres'
$env:PGPASSWORD = (Get-Credential -UserName postgres -Message 'Mat khau PostgreSQL').GetNetworkCredential().Password

# Backup
& "$pg\pg_dump.exe" -Fc --no-owner --no-privileges -f backup_demo_20261126.dump esports_tournament_demo

# Restore vào DB mới (không ghi đè DB đang dùng)
& "$pg\createdb.exe" esports_tournament_restore_test
& "$pg\pg_restore.exe" --no-owner --no-privileges --exit-on-error -d esports_tournament_restore_test backup_demo_20261126.dump

Remove-Item Env:PGPASSWORD
```

Kiểm tra sau restore: `alembic current` đúng head; số dòng từng bảng khớp nguồn; thêm được bản ghi mới (sequence không lùi).

**Đã chạy thử 26/11/2026** (DB demo W48-01): dump 0,4 s, 83 KB; restore 0,4 s, exit 0; **20/20 bảng khớp số dòng**, `alembic_version` = `f47a04b00001`; 17/17 sequence có `nextval` > `max(id)`, insert mới thành công. DB restore và file dump đã xóa. Với dữ liệu lớn xem [DATA_VOLUME_PLAN.md](./DATA_VOLUME_PLAN.md) (dump nén ước tính vài trăm MB, chưa đo).

- `--no-owner --no-privileges`: restore được dưới role khác; bảng thuộc role chạy restore, server phải dùng role đó.
- Không commit file `.dump` vào git (chứa hash mật khẩu, dữ liệu người dùng).

## 3. Staging

Nhóm chưa có server; "staging" = một môi trường chạy **giống demo/nộp bài** trên máy riêng, tách khỏi môi trường dev:

| Thành phần | Dev | Staging |
|---|---|---|
| Database | DB cá nhân (`DB_NAME` trong `.env`) | DB riêng, ví dụ `esports_tournament_staging`; nạp bằng restore bản backup hoặc `seed_demo.py --reset` (tên `_demo`) |
| Backend | `uvicorn main:app --reload` | `uvicorn main:app --host 127.0.0.1 --port 8001` (không `--reload`) |
| Frontend | `npm run dev` | `npm run build` rồi `npm run preview -- --port 4173` (bản build thật) |
| Bí mật | `.env` cá nhân | Biến môi trường trong phiên: `JWT_SECRET` ngẫu nhiên riêng, `DB_*` riêng |

```powershell
# Backend (terminal 1, thư mục backend)
$env:DB_NAME = 'esports_tournament_staging'
$env:JWT_SECRET = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
$env:CORS_ORIGINS = '["http://127.0.0.1:4173"]'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001

# Frontend (terminal 2, thư mục frontend)
$env:VITE_API_URL = 'http://127.0.0.1:8001/api/v1'
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

`JWT_SECRET` mặc định trong code là `change-me-in-env`: **staging/demo bắt buộc đặt lại**, nếu không ai cũng tự ký được token hợp lệ.

## 4. Release checklist

Chạy trên **đúng commit sẽ demo/nộp** (ghi hash):

1. [ ] `main` sạch, đã pull; ghi commit `____`.
2. [ ] CI trên commit đó xanh 3 job (Backend tests, Frontend build, Browser E2E); ghi link run.
3. [ ] Local: `python -m pytest -q` (SQLite) và `python -m pytest --postgres -m postgres -q`; `python -m ruff check .`.
4. [ ] `tests/test_schema_sql_sync.py` đạt (file SQL khớp migration).
5. [ ] **Backup** DB đích (mục 2) trước khi migrate; kiểm tra được file dump restore được.
6. [ ] `alembic upgrade head` trên DB staging; `alembic current` = head.
7. [ ] Nạp dữ liệu: `seed_demo.py --reset` (DB `_demo`) hoặc restore bản đã chuẩn bị; số dòng đúng kỳ vọng.
8. [ ] `JWT_SECRET` đã đổi, `CORS_ORIGINS` đúng địa chỉ frontend, không dùng `.env` cá nhân.
9. [ ] Frontend `npm run build` + `preview` trỏ đúng API; đăng nhập 3 vai trò (admin, organizer, manager) được.
10. [ ] Chạy kịch bản demo (W48-06) một lượt: tạo đội → tạo giải → đăng ký/duyệt → roster → nhập kết quả → bracket/standings → nhật ký audit.
11. [ ] Ghi kết quả (commit, CI, số test, thời gian) vào file tuần; giữ file dump của bản đã demo.
