# W44-04 — Danh sách giải và đội được nhận

## Phạm vi

Bổ sung lọc/phân trang cho danh sách giải và danh sách công khai các đội APPROVED. Hai yêu cầu còn lại của W44-04 đã có từ [W44-02](W44_REGISTRATION_DECISIONS.md) và được giữ nguyên:

- Đổi `game_id` khi giải đã có bất kỳ đơn nào trả 409, cùng parent lock với duyệt đơn (`tests/test_registration_decisions.py`, `tests/test_registration_concurrency.py`).
- Giải rời UPCOMING đóng mọi thao tác trên đơn qua `core/tournament_policy.registrations_open`; duyệt (W44-02) và gửi/hủy ([W44-03](W44_TEAM_REGISTRATIONS.md)) đều kiểm tra sau khi khóa giải.

## API

Cả hai endpoint công khai, không cần JWT.

- `GET /api/v1/tournaments?game_id=&area_id=&status=&offset=0&limit=50`
  - Lọc thêm theo `status` (`UPCOMING`/`ONGOING`/`COMPLETED`/`CANCELLED`, phân biệt hoa thường); kết hợp được với `game_id`, `area_id`.
  - `limit` 1–100, mặc định 50; `offset` 0–2147483647. Trước đây trả toàn bộ, nay mặc định tối đa 50 bản ghi.
  - Sắp xếp giữ như W43: ngày bắt đầu giảm dần, rồi ID giảm dần.
  - Response vẫn là mảng `TournamentRead`, không đổi schema.
- `GET /api/v1/tournaments/{id}/teams?offset=0&limit=50`
  - Chỉ đội có đơn APPROVED trong giải, sắp theo tên rồi ID; vẫn xem được sau khi giải đóng.
  - Mỗi phần tử chỉ gồm `team_id`, `name`, `tag`, `game_id`; không lộ người gửi/duyệt, thời điểm hay lý do từ chối.
  - 404 nếu giải không tồn tại; 422 nếu ID/phân trang sai.
- Cả hai trả header `X-Total-Count`: tổng số bản ghi khớp bộ lọc, không tính offset/limit, để UI dựng điều khiển trang. CORS đã `expose_headers` header này cho trình duyệt.

## Kiểm tra

```powershell
# Từ backend
python -m pytest -q
python -m pytest --postgres -m postgres -q
```

`tests/test_tournament_listing.py` (32 test, chạy cả SQLite và PostgreSQL): lọc theo game/trạng thái và kết hợp, phân trang và tổng theo bộ lọc, giới hạn mặc định 50, query sai, header CORS; danh sách đội chỉ APPROVED, không lộ dữ liệu đơn, tách giải khác, phân trang/rỗng, đọc được sau khi giải đóng, giải không tồn tại/ID sai.

Kết quả ngày 23/10/2026: backend 321 passed, 14 skipped; PostgreSQL marked suite 332 passed, 3 deselected. Sau khi gộp main có W44-03 (24/10/2026): backend 362 passed, 22 skipped; PostgreSQL marked suite 381 passed, 3 deselected.
