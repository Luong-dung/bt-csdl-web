# W48-03: Dựng môi trường từ clone sạch theo README

Người làm: DOANH. Ngày 28/11/2026, Windows 11, Python 3.13.7, Node 24.19.0 / npm 11.17.0, PostgreSQL 17.11 local. Clone `main` tại `30f5f1b` vào thư mục trống, chỉ làm theo README và tài liệu README trỏ tới. Database dùng tên tạm, xóa sau khi xong.

## 1. Thời gian

| Bước | Từ clone | Ghi chú |
|---|---|---|
| Clone | 0:00 | |
| `.env`, `venv`, `pip install -r requirements.txt` | ~1:00 | Cài thư viện ~30 giây |
| `alembic upgrade head` + `seed.py` | ~1:15 | Lỗi lần đầu vì chưa tạo database (mục 2, lỗi 1) |
| API `/health` trả `{"status":"up"}` | ~1:25 | |
| Frontend `npm install` + `npm run build` | ~1:40 | Build ~1 giây |
| Cài E2E (Playwright + Chromium 91 MB, `npm ci`), seed DB `_test` | ~3:30 | |
| Browser E2E toàn bộ | ~11:20 | 7 phút 50 giây cho 46 ca |

Không tính thời gian xử lý lỗi, backend + frontend chạy được sau **khoảng 2 phút**, và đủ E2E sau **khoảng 11–12 phút**.

## 2. Lỗi/thiếu tìm thấy và cách sửa

| # | Bước | Hiện tượng | Sửa |
|---|---|---|---|
| 1 | Migrate | README ghi `CREATE DATABASE` **sau** khối lệnh có `alembic upgrade head` → làm theo thứ tự thì lỗi `database "…" does not exist` | README: tạo database là bước 1 |
| 2 | Tạo DB | Máy không có `psql` trong PATH; README không nói chạy SQL bằng gì | README: pgAdmin/`psql`, hoặc lệnh Python dùng chính `.env` (đã chạy thử) |
| 3 | `.env` | `.env.example` để trống `DB_PASSWORD`, README không dặn sửa; dòng cuối không có xuống dòng nên nối thêm dòng sẽ dính vào `DB_PASSWORD=` | README: bắt buộc sửa `DB_PASSWORD`, `JWT_SECRET`; thêm xuống dòng cuối `.env.example` |
| 4 | Phiên bản | README không ghi cần Python/Node/PostgreSQL bản nào | README: bảng "Cài đặt cần có" theo CI (Python 3.12, Node 24, PostgreSQL 17) và bản đã kiểm |
| 5 | Đăng nhập | Sau `seed.py` không có tài khoản nào; README không chỉ sang `seed_demo.py` | README: bước 4 trỏ tới [DEMO_DATA.md](DEMO_DATA.md) |
| 6 | Frontend | `npm install` không cố định phiên bản như CI; npm 11 in cảnh báo `allow-scripts` cho `esbuild` gây lo ngại | README: dùng `npm ci`, ghi chú cảnh báo vô hại (build và dev chạy được) |
| 7 | E2E | Đoạn E2E trong README thiếu `E2E_DB_NAME`, `E2E_DATABASE_URL`, `E2E_API_BASE_URL` và bước cài Playwright → chạy theo README thì các ca ghi DB lỗi | README: trỏ hẳn sang [BROWSER_TESTING.md](BROWSER_TESTING.md), bỏ đoạn lệnh thiếu |
| 8 | E2E | Mật khẩu PostgreSQL có ký tự đặc biệt mà ghép thẳng vào `E2E_DATABASE_URL` → 4 ca dùng DB lỗi `password authentication failed`, 42 ca còn lại đạt | BROWSER_TESTING: ghi phải URL-encode mật khẩu, kèm lệnh |
| 9 | Tài liệu | Mục "Phân quyền API" còn ghi "chưa có API cấp/thu hồi assignment" (đã có từ W47) | README: trỏ `/api/v1/admin/role-assignments` và W47_ROLE_ASSIGNMENTS.md |

Không phát hiện lỗi code: migrate, seed, API, build và E2E đều đạt khi môi trường đúng.

## 3. Kết quả

- Backend: `alembic upgrade head` tới head, `seed.py` thêm `roles +6, publishers +2, games +5, competition_areas +31, countries +8`, `/health` đạt.
- Frontend: `npm run build` đạt.
- Browser E2E theo BROWSER_TESTING.md: **46/46 đạt** (lần đầu 42 đạt và 4 lỗi do lỗi 8; URL-encode mật khẩu rồi chạy lại 4 ca thì đạt).

## 4. Nghiệm thu

Reviewer (DUONG) làm lại từ clone sạch **chỉ theo README đã sửa**, ghi thời gian và bước nào còn vướng vào PR. Không dùng `.env` hay database có sẵn.
