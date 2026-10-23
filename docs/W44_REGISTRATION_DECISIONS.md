# W44-02 — Xem và duyệt/từ chối đơn đăng ký giải

## Phạm vi và phụ thuộc W44-03

Repo W43 chưa có bảng đơn đăng ký. W44-02 bổ sung nền tảng dùng chung `TournamentRegistration`, migration `1d9de90694b3` và helper khóa transaction để API quyết định có thể triển khai/kiểm thử độc lập. W44-03 phải dùng lại bảng/helper này; không tạo migration bảng đăng ký thứ hai.

Chưa có endpoint gửi/hủy đơn hoặc UI đăng ký trong PR này. Test tạo đơn qua fixture; không có endpoint seed/test trong ứng dụng. W44-03 bổ sung quyền đọc đơn của người quản lý đội vào GET hiện có; W44-02 chỉ cho người quản lý giải đọc mọi đơn. Các thay đổi contract này cần đồng bộ vào kế hoạch W44 khi gộp PR.

## API

Mọi request cần JWT. Quyền quản lý giải dùng `can_manage_tournament`: ADMIN toàn cục; người tạo có quyền ORGANIZER toàn cục; hoặc ORGANIZER được gán đúng TOURNAMENT. ORGANIZER khác không tự được xem/duyệt. Giải không có người tạo chỉ ADMIN.

- `GET /api/v1/tournaments/{id}/registrations?status=PENDING&offset=0&limit=50`: xem đơn, kể cả khi giải đã đóng; lọc PENDING/APPROVED/REJECTED/CANCELLED, sắp theo thời điểm gửi và ID tăng dần. Limit 1–100, offset 0–2147483647. Chỉ trả đơn thuộc giải trong URL.
- `POST /api/v1/tournaments/{id}/registrations/{registration_id}/decision`: body `{"status":"APPROVED"}` hoặc `{"status":"REJECTED","rejection_reason":"Không đủ điều kiện"}`. Lý do từ chối tùy chọn, nếu gửi phải có 1–500 ký tự sau trim; không nhận lý do cho APPROVED, không nhận trường lạ.
- Response 200 gồm registration_id, tournament_id, team_id, status, submitted_by/submitted_at, reviewed_by/reviewed_at, rejection_reason, cancelled_by/cancelled_at. Actor đã bị xóa có thể null; lịch sử thời điểm vẫn giữ lại.
- Chỉ quyết định đơn PENDING khi giải UPCOMING. APPROVED/REJECTED là cuối; gửi lại trả 409 và không ghi audit lần hai. APPROVED kiểm tra lại game đội khớp giải; REJECTED vẫn dùng được để xử lý đơn sai game.
- 401: thiếu/sai JWT; 403: không có quyền quản lý giải; 404: giải/đơn không tồn tại hoặc đơn thuộc giải khác; 409: giải đóng, đơn đã xử lý, game không khớp khi duyệt hoặc xung đột ràng buộc; 422: payload/ID/query sai.

## Dữ liệu, migration và transaction

- Unique `(tournament_id, team_id)`; FK giải/đội/actor; CHECK trạng thái, thời điểm phù hợp trạng thái và lý do chỉ có cho REJECTED. Tạo đơn mặc định PENDING, thời điểm gửi do DB cấp. Xóa actor không xóa lịch sử; xóa đội có đơn bị chặn, xóa giải cascade đơn.
- Migration hỗ trợ database W43 đã có dữ liệu và database mới. Revision đầu của repo gọi metadata hiện tại nên bảng có thể đã được tạo ở lượt cài mới; migration mới kiểm tra tồn tại để không tạo trùng. Downgrade xóa bảng đăng ký và dữ liệu đơn, giữ các bảng W43.
- Thứ tự khóa chung: `lock_registration_tournament` → `lock_registration` → kiểm tra trạng thái → ghi đơn/audit → commit. Helper đọc lại dữ liệu sau khi chờ khóa, tránh dùng giá trị cũ trong identity map.
- Endpoint đổi trạng thái giải W43 đã khóa cùng hàng giải; không thể duyệt dựa trên UPCOMING cũ sau khi giải đã đóng. W44-03 gửi/hủy đơn và W44-04 đổi game phải dùng cùng parent lock. Việc cấm đổi game khi có đơn thuộc W44-04.
- Audit `TOURNAMENT_REGISTRATION_APPROVED`/`TOURNAMENT_REGISTRATION_REJECTED`, resource `tournament_registration`, chứa actor, ID giải/đơn/đội, before/after. Ghi audit và quyết định cùng transaction; lỗi rollback cả hai.

## Kiểm tra

```powershell
# Từ backend, sau khi cài requirements trong venv
python -m pytest -q
python -m pytest tests/test_registration_decisions.py tests/test_registration_concurrency.py tests/test_registration_migration.py tests/test_postgres_migrations.py --postgres -q --basetemp=.pytest_cache/w44-migration-check
```

Test PostgreSQL dùng schema tạm. Test cạnh tranh cần các connection độc lập và schema có dữ liệu commit riêng; luôn dọn schema sau test. Bao phủ hai người duyệt cùng đơn, quyết định chờ hủy/đóng giải, endpoint đổi trạng thái cạnh tranh với quyết định, audit/rollback, constraint và upgrade/downgrade từ W43. SQLite bỏ qua các bài chỉ có ý nghĩa trên PostgreSQL.

Kiểm tra ngày 23/10/2026: backend 220 passed, 6 skipped; toàn bộ PostgreSQL marked suite 223 passed, 3 deselected; nhóm test mới/migration chạy PostgreSQL riêng 53 passed. Một cảnh báo deprecation từ Starlette/AnyIO.
