# Dữ liệu demo (W43-01, mở rộng W48-01)

`backend/seed_demo.py` tạo tài khoản, đội và (từ W48) bộ giải demo đủ trạng thái. `python seed.py` vẫn chỉ tạo dữ liệu nền, không tạo tài khoản.

## 1. Chuẩn bị database riêng

Dùng cùng PostgreSQL host/user/password trong `backend/.env`, tạo một database riêng, ví dụ:

```sql
CREATE DATABASE esports_tournament_demo;
```

Database này phải khác `DB_NAME` hiện tại trong `.env`; tên phải kết thúc bằng `_demo` hoặc `_test`. Script không tự tạo/xóa database và không tự chọn database ứng dụng làm đích.

## 2. Chạy migration và seed demo

Từ thư mục gốc, dùng PowerShell:

```powershell
cd backend
$demoCredential = Get-Credential -UserName 'demo' -Message 'Nhap mat khau chung cho tai khoan demo (8-128 ky tu)'
$env:DEMO_PASSWORD = $demoCredential.GetNetworkCredential().Password
try {
    .\.venv\Scripts\python.exe seed_demo.py --database esports_tournament_demo --migrate
    if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed' }
} finally {
    Remove-Item Env:DEMO_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable demoCredential
}
```

**Reset sạch bằng một lệnh** (thay cho lệnh trên khi muốn làm lại từ đầu):

```powershell
.\.venv\Scripts\python.exe seed_demo.py --database esports_tournament_demo --reset
```

`--reset` **xóa toàn bộ schema `public` của database demo** (`DROP SCHEMA public CASCADE`), tạo lại, migrate tới `head` rồi seed; chỉ chạy được với PostgreSQL và tên database đuôi `_demo`/`_test`, khác `DB_NAME` trong `.env`. Đo local 23/11/2026: khoảng 8–9 giây. `--base-only` chỉ tạo phần W43 (dùng cho Browser E2E/CI).

`--migrate` chạy Alembic tới `head` bằng connection trỏ vào đúng database chỉ định. Có thể bỏ tùy chọn này nếu database đó đã migrate. Migration và seed chạy trong một transaction PostgreSQL; lỗi sẽ rollback. Không ghi mật khẩu vào source, log hay tài liệu.

## 3. Tài khoản và dữ liệu

| Username | Role tài khoản | Dữ liệu/phạm vi demo |
|---|---|---|
| `demo_admin` | ADMIN | Quản trị catalog, quản lý đội và tạo giải |
| `demo_organizer` | ORGANIZER | Tạo giải; không được ghi catalog |
| `demo_manager` | TEAM_MANAGER | Membership MANAGER đang ACTIVE trong đội DEMO43; không tự có quyền quản lý mọi đội |
| `demo_player` | PLAYER | Membership PLAYER đang ACTIVE trong đội DEMO43 |
| `demo_free_player` | PLAYER | Chưa thuộc đội, dùng để thử thêm thành viên hoặc tạo đội |
| `demo_viewer` | VIEWER | Chưa thuộc đội; dùng kiểm tra quyền đọc và từ chối thao tác quản trị |

Bổ sung từ W48-01:

| Username | Role tài khoản | Dữ liệu/phạm vi demo |
|---|---|---|
| `demo_referee` | VIEWER | Trọng tài được `demo_organizer` cấp **qua API** cho `W48 Demo Cup` và `W48 Demo Open`; đã tự nhập kết quả trận chung kết Cup |
| `demo_manager_b/c/d` | TEAM_MANAGER | Quản lý đội `DEMO48B/C/D` (W48 Demo Bravo/Charlie/Delta) |
| `demo_player_b/c/d` | PLAYER | Tuyển thủ của đội tương ứng |

| Giải (người tạo `demo_organizer`, VALORANT) | Trạng thái | Dùng để demo |
|---|---|---|
| `W48 Demo Cup` | COMPLETED | 4 đội, roster khóa, bracket đã đấu xong, standings FINAL, nhật ký audit đầy đủ |
| `W48 Demo Open` | ONGOING | Bracket 4 đội, đã xong 1 bán kết; còn bán kết 2 và chung kết để nhập kết quả trực tiếp (organizer hoặc `demo_referee`), thử thu hồi trọng tài |
| `W48 Demo League` | UPCOMING (+14 ngày) | 1 đơn APPROVED (DEMO43), 2 đơn PENDING (DEMO48B/C) để duyệt/từ chối, khóa roster |
| `W48 Demo Draft` | UPCOMING (+30 ngày) | Chưa có dữ liệu thi đấu, xóa được (W47-04) |

Mọi thao tác nghiệp vụ của kịch bản W48 (tạo đội, đăng ký, duyệt, roster, khóa, stage, bracket, cấp trọng tài, kết quả) đi qua API thật trong cùng transaction nên có audit đúng actor; ngày bắt đầu tính theo ngày chạy seed.

Tài khoản mới dùng mật khẩu nhập tại bước 2; email có dạng `<username>@example.com`. Dữ liệu kèm theo: dữ liệu nền từ `seed.py`, tổ chức `W43 Demo Organization`, đội VALORANT `W43 Demo Team` với tag `DEMO43` và hai membership ACTIVE. Phần giải/roster/match/trọng tài do kịch bản W48 ở trên tạo.

## 4. Chạy ứng dụng với database demo

Trong terminal backend riêng, sau khi seed xong:

```powershell
$env:DB_NAME = 'esports_tournament_demo'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
# Sau khi dung server (Ctrl+C):
Remove-Item Env:DB_NAME
```

API demo: <http://127.0.0.1:8001/docs>. Biến môi trường trong terminal ghi đè `.env`, không cần sửa `.env` đang dùng cho database cá nhân.

Trong terminal frontend riêng, từ thư mục gốc:

```powershell
cd frontend
$env:VITE_API_URL = 'http://127.0.0.1:8001/api/v1'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
# Sau khi dung server (Ctrl+C):
Remove-Item Env:VITE_API_URL
```

Dừng frontend cũ nếu đang chiếm port 5173. Mở <http://127.0.0.1:5173>, đăng xuất phiên cũ trước khi chuyển tài khoản/database. Dùng `demo_manager` để mở đội `W43 Demo Team` và thử xem lịch sử, thêm thành viên `demo_free_player`, đổi vị trí hoặc kết thúc membership; dùng `demo_admin` để xem và CRUD publisher/game/khu vực. `demo_viewer` không có quyền quản trị catalog, giải đấu hoặc đội hiện có; tuy nhiên, user đã đăng nhập vẫn được tạo đội mới trên UI/API. Mật khẩu là mật khẩu test-only đã nhập lúc seed; không ghi vào source hoặc log. Các endpoint API vẫn có thể kiểm tra qua Swagger tại <http://127.0.0.1:8001/docs>.

Để demo API giải đấu và audit trên database demo, gọi `POST /api/v1/auth/login` với JSON `{"username":"demo_organizer","password":"<MẬT_KHẨU_DEMO>"}`, rồi dán `access_token` vào nút Authorize của Swagger. Lấy ID game từ `GET /api/v1/catalog/games`, sau đó thực hiện lần lượt. Thay `<GAME_ID>` bằng ID số và `<NGÀY TƯƠNG LAI>` bằng ngày hợp lệ dạng `YYYY-MM-DD` trước khi gửi request:

1. `POST /api/v1/tournaments` với `{"name":"W43 Demo Cup","game_id":<GAME_ID>,"format":"SINGLE_ELIM","start_date":"<NGÀY TƯƠNG LAI>"}`.
2. Dùng `tournament_id` trả về để gọi `PATCH /api/v1/tournaments/{tournament_id}` với `{"name":"W43 Demo Cup Updated"}`.
3. Gọi `POST /api/v1/tournaments/{tournament_id}/status` với `{"status":"ONGOING"}`.
4. Trong PostgreSQL query tool, thay `<TOURNAMENT_ID>` bằng ID ở bước 1 và xác nhận ba dòng audit:

```sql
SELECT l.action, u.username, l.details, l.created_at
FROM audit_logs AS l
LEFT JOIN users AS u ON u.user_id = l.user_id
WHERE l.resource = 'tournament'
  AND l.details->>'tournament_id' = '<TOURNAMENT_ID>'
ORDER BY l.log_id;
```

Kết quả mong đợi gồm `TOURNAMENT_CREATED`, `TOURNAMENT_UPDATED` và `TOURNAMENT_STATUS_CHANGED`, cùng actor `demo_organizer` và dữ liệu before/after. Luồng này chỉ ghi vào database demo đã cấu hình; không dùng database production.

`start_date` không được ở quá khứ; ngày hôm nay cũng hợp lệ. Endpoint chuyển trạng thái sang `ONGOING` hiện không kiểm tra `start_date`, nên theo API hiện tại giải có ngày bắt đầu trong tương lai vẫn có thể chuyển sang `ONGOING`.

## 5. Chạy lại và xử lý dữ liệu đã thay đổi

- Kịch bản W48: nếu đủ 4 giải demo thì chạy lại không ghi gì; nếu chỉ còn một phần (ví dụ đã xóa `W48 Demo Draft` khi demo) hoặc tag `DEMO48*` bị chiếm, seed báo lỗi và rollback — dùng `--reset`.
- Chạy lại cùng lệnh trên dữ liệu demo chưa đổi sẽ thêm 0 bản ghi; không đổi ID hoặc mật khẩu của tài khoản đã có. Đổi DEMO_PASSWORD chỉ áp dụng cho tài khoản tạo mới.
- Không ghi đè user có username demo nhưng khác email/role; email bị chiếm hoặc tag đội trùng dữ liệu khác sẽ báo lỗi và rollback toàn bộ lượt seed.
- Membership demo đã đổi vị trí, chuyển đội hoặc kết thúc sẽ báo lỗi; không tự khôi phục lịch sử hay đưa người đã rời trở lại đội. Dữ liệu khác được giữ nguyên.
- Muốn một kịch bản sạch sau khi demo: chạy `--reset` (mục 2), hoặc tạo database riêng mới có hậu tố `_demo`/`_test`, chạy seed vào đó rồi trỏ server demo sang database mới. Không cần xóa database cá nhân. Dữ liệu demo cũ có thể giữ lại để đối chiếu.

## 6. Kiểm tra tự động

Từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_seed_demo.py tests/test_seed_demo_scenario.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_seed_demo.py tests/test_seed_demo_scenario.py --postgres -m postgres -q
```

Mặc định dùng SQLite in-memory. Để chạy PostgreSQL, đặt `TEST_DATABASE_URL` tới database test riêng như hướng dẫn tại README rồi dùng `--postgres -m postgres`; test dùng schema tạm và rollback, không seed tài khoản vào schema ứng dụng. Kiểm tra gồm chạy lại, bảo toàn dữ liệu/mật khẩu, rollback khi xung đột, không phục hồi membership đã kết thúc, đăng nhập thật bằng JWT và quyền catalog/đội/giải.
