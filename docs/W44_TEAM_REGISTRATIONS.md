# W44-03 — Đội gửi, hủy và xem đơn đăng ký giải

## Phạm vi

Dùng lại bảng `tournament_registrations`, migration `1d9de90694b3` và helper khóa của [W44-02](W44_REGISTRATION_DECISIONS.md); không thêm bảng hoặc migration. PR này bổ sung endpoint gửi/hủy đơn và mở rộng GET hiện có cho người quản lý đội. Danh sách đội APPROVED công khai và lọc giải thuộc W44-04.

## Quyền

Quyền quản lý đội dùng `can_manage_team`/`managed_teams_query` của W44-01: ADMIN; MANAGER đang ACTIVE của đội; hoặc TEAM_MANAGER được gán đúng TEAM hay ORGANIZATION chứa đội. Role TEAM_MANAGER toàn cục không kèm scope không tự có quyền với đội nào. ORGANIZER quản lý giải không được gửi/hủy đơn thay đội.

## API

Mọi request cần JWT.

- `POST /api/v1/tournaments/{id}/registrations` body `{"team_id": 1}`: tạo đơn PENDING, response 201 cùng schema `RegistrationRead` của W44-02. `team_id` 1–2147483647, không nhận trường lạ.
- `POST /api/v1/tournaments/{id}/registrations/{registration_id}/cancel`: không có body; chuyển đơn PENDING sang CANCELLED, ghi `cancelled_by`/`cancelled_at`, response 200.
- `GET /api/v1/tournaments/{id}/registrations?team_id=&status=&offset=&limit=`:
  - Người quản lý giải xem mọi đơn như W44-02, có thêm bộ lọc `team_id`.
  - Người quản lý đội chỉ nhận đơn của các đội mình đang quản lý; danh sách rỗng nếu đội chưa đăng ký. Lọc `team_id` của đội không quản lý trả 403.
  - Người không quản lý giải và không quản lý đội nào trả 403.

| Mã | Trường hợp |
|---|---|
| 401 | Thiếu/sai JWT; tài khoản bị xóa khi đang chờ khóa |
| 403 | Không quản lý đúng đội (gửi/hủy/lọc), hoặc không có quyền xem |
| 404 | Giải, đội hoặc đơn không tồn tại; đơn thuộc giải khác URL |
| 409 | Giải không còn UPCOMING; đội đã có đơn trong giải (kể cả REJECTED/CANCELLED, W44 chưa cho đăng ký lại); hủy đơn không còn PENDING; vi phạm ràng buộc |
| 422 | Payload/ID/query sai; game của đội khác game giải |

## Transaction

- Gửi và hủy kiểm tra quyền quản lý đội trước khi khóa để người không có quyền không phải chờ khóa giải. Sau đó dùng `lock_tournament_as` (tách từ `get_managed_tournament`): khóa hàng giải, nạp lại tài khoản/assignment rồi kiểm tra quyền lần hai. Hủy khóa đơn sau giải, giữ thứ tự giải → đơn như duyệt/đổi trạng thái giải.
- Sau khi khóa mới kiểm tra giải còn UPCOMING, đọc lại game của đội, kiểm tra đơn trùng; unique `(tournament_id, team_id)` ở DB là lớp chặn cuối, lỗi trả 409.
- `submitted_at` và `cancelled_at` lấy từ `registration_timestamp` (đồng hồ DB sau khi có khóa) như `reviewed_at`.
- Audit `TOURNAMENT_REGISTRATION_CREATED` (before `null`) và `TOURNAMENT_REGISTRATION_CANCELLED` (before/after trạng thái và thông tin hủy) ghi cùng transaction; lỗi audit rollback cả đơn.

## Kiểm tra

```powershell
# Từ backend
python -m pytest -q
python -m pytest --postgres -m postgres -q
```

- `tests/test_team_registrations.py`: quyền theo membership/TEAM/ORGANIZATION/ADMIN, người ngoài đội/ORGANIZER/role không scope, payload/ID sai, game khác, giải đóng, gửi lại sau REJECTED/CANCELLED, hủy đơn đã xử lý, đơn khác giải, phạm vi GET của quản lý đội, thu hồi quyền, rollback khi lỗi audit.
- `tests/test_team_registration_concurrency.py` (PostgreSQL, connection độc lập): hai lần gửi cùng đội chỉ tạo một đơn; hủy và duyệt cạnh tranh chỉ một bên thành công; gửi/hủy đang chờ khóa thấy giải đã đóng; quyền bị thu hồi khi chờ được kiểm tra lại; người không có quyền không chờ khóa.
- Kết quả ngày 23/10/2026: backend 330 passed, 22 skipped; PostgreSQL marked suite 349 passed, 3 deselected. Cố ý bỏ kiểm tra quyền lần hai sau khóa thì test thu hồi quyền khi chờ fail.
