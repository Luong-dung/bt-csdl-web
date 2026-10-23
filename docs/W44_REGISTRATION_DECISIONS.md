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

- Unique `(tournament_id, team_id)`; index riêng `ix_tournament_registrations_team_id`; FK giải/đội/actor; CHECK trạng thái và thời điểm phù hợp trạng thái. Tạo đơn mặc định PENDING, thời điểm gửi do DB cấp. Xóa actor không xóa lịch sử; xóa đội có đơn bị chặn, xóa giải cascade đơn.
- Schema cho phép CANCELLED giữ reviewed_by/reviewed_at và rejection_reason lịch sử nếu có; chỉ bắt buộc cancelled_at khác null. Đây là khả năng lưu trữ cho mở rộng sau này, chưa cho phép rút đơn đã duyệt/từ chối qua API W44.
- Migration hỗ trợ database W43 và database mới. Nếu bảng đã được create_all tạo trước đó, migration bổ sung unique/index còn thiếu, thay CHECK theo định nghĩa hiện tại; thiếu cột bắt buộc sẽ báo lỗi thay vì stamp head. Downgrade xóa bảng đăng ký và dữ liệu đơn, giữ các bảng W43.
- PATCH, đổi trạng thái giải và duyệt đơn dùng chung `core/tournaments.get_managed_tournament`: đọc/kiểm tra quyền trước khóa, khóa hàng giải và đọc mới dữ liệu, tải lại quyền rồi kiểm tra lần hai. User không có quyền nhận 403 mà không chờ parent lock; tài khoản bị xóa trong lúc chờ nhận 401.
- Sau parent lock mới khóa đơn, kiểm tra trạng thái, ghi đơn/audit và commit. `lock_registration_tournament` là alias của helper khóa chung để W44-03 dùng tiếp cho gửi/hủy đơn.
- Thời điểm duyệt lấy từ đồng hồ DB; PostgreSQL dùng clock_timestamp() sau khi chờ lock để không dùng thời gian cũ ở đầu transaction. W44-03 dùng lại `registration_timestamp` cho cancelled_at.
- PATCH đổi game khi giải có bất kỳ đơn nào trả 409 ngay trong W44-02; gửi cùng game_id hiện tại vẫn hợp lệ. Các writer dùng cùng parent lock nên đổi game không thể làm sai game của đội đã duyệt. W44-04 dùng lại guard này khi bổ sung API còn lại.
- Audit `TOURNAMENT_REGISTRATION_APPROVED`/`TOURNAMENT_REGISTRATION_REJECTED`, resource `tournament_registration`, chứa actor, ID giải/đơn/đội, before/after lấy từ dữ liệu thực tế. Ghi audit và quyết định cùng transaction; lỗi rollback cả hai.

## Kiểm tra

```powershell
# Từ backend, sau khi cài requirements trong venv
python -m pytest -q
python -m pytest tests/test_registration_decisions.py tests/test_registration_concurrency.py tests/test_registration_migration.py tests/test_postgres_migrations.py --postgres -q --basetemp=.pytest_cache/w44-migration-check
```

Test PostgreSQL dùng schema tạm. Test cạnh tranh cần các connection độc lập và schema có dữ liệu commit riêng; luôn dọn schema sau test. Bao phủ hai người duyệt cùng đơn, quyết định chờ hủy/đóng giải, endpoint đổi trạng thái cạnh tranh với quyết định, audit/rollback, constraint và upgrade/downgrade từ W43. SQLite bỏ qua các bài chỉ có ý nghĩa trên PostgreSQL.

Test bổ sung sau review #41: chặn đổi game ở mọi trạng thái đơn, CANCELLED giữ lịch sử duyệt, lệch đồng hồ app, audit snapshot thực tế, writer sai quyền không chờ lock, thu hồi assignment/xóa tài khoản khi đang chờ, PATCH game cạnh tranh với duyệt và sửa constraint/index trên bảng create_all cũ.

Kiểm tra lại sau review ngày 23/10/2026: backend 228 passed, 13 skipped; toàn bộ PostgreSQL marked suite 238 passed, 3 deselected. Các bài skip trong suite mặc định cần PostgreSQL thật. Một cảnh báo deprecation từ Starlette/AnyIO.

Sau đó bổ sung trường hợp assignment đổi sang scope khác khi đang chờ: chạy riêng nhóm thu hồi/đổi scope/xóa tài khoản trên PostgreSQL đạt 3 passed. Phần code nghiệp vụ không thay đổi sau lượt hồi quy toàn bộ trên.
