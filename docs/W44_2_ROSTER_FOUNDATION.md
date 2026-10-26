# W44-2-01 — Nền tảng roster và bàn giao khóa snapshot

## Phạm vi đã triển khai

- Tái sử dụng `tournament_rosters`, không tạo bảng roster thứ hai. Migration mới `cb86835f3e5f` sau `1d9de90694b3`, tạo bằng `alembic revision`.
- Thêm `tournaments.roster_locked_at` (TIMESTAMPTZ, nullable) và `roster_locked_by` (FK users, SET NULL). `locked_at IS NOT NULL` là nguồn xác định đã khóa; không thêm boolean có thể lệch trạng thái. CHECK không cho actor khi chưa có thời điểm khóa. Actor có thể NULL khi tài khoản bị xóa, trạng thái khóa vẫn giữ.
- Unique `(tournament_id, user_id)` ngăn user xuất hiện hai đội trong cùng giải; index `(tournament_id, team_id)` phục vụ đọc roster đội. CHECK chỉ cho PLAYER/SUBSTITUTE.
- `display_name VARCHAR(100)` lưu tên hiển thị snapshot. Cho phép NULL với dữ liệu cũ/chưa chụp; nếu có thì không được rỗng. W44-2-03 điền từ username khi lưu, W44-2-04 chụp lại username tại thời điểm khóa; sau khóa không dựng lại từ User/membership. Không đưa email/real_name vào response công khai.
- FK roster → user/team đổi CASCADE thành RESTRICT để xóa user/đội không làm mất lịch sử. FK roster → tournament vẫn CASCADE; W44(2) không cung cấp xóa giải. Không có FK sang membership: kết thúc/chuyển membership không xóa snapshot.
- Bổ sung hai GET nền tảng, schema request/response dùng chung và các helper khóa không tự commit. Chưa triển khai PUT roster hoặc POST khóa: thuộc W44-2-03/04. Chưa thay điều kiện bắt đầu giải: W44-2-04 sẽ nối vào `POST /status` và capability trong cùng PR.

## Migration và dữ liệu cũ

Migration hỗ trợ cả database W44 có sẵn và cài mới (migration đầu tiên gọi live `Base.metadata.create_all`, nên cột/constraint mới có thể đã tồn tại). Reconcile tên unique, FK và CHECK; không chỉ bỏ qua cả bảng khi thấy tồn tại.

- Không tự backfill thời điểm/người khóa, không tạo snapshot giả cho giải ONGOING/COMPLETED cũ. Giữ nguyên các hàng roster và display_name NULL nếu chưa có snapshot.
- Nếu dữ liệu cũ có user trùng trong một giải hoặc role ngoài PLAYER/SUBSTITUTE, migration dừng với lỗi rõ trước khi đổi schema. Người vận hành đối chiếu dữ liệu trước khi chạy lại; không tự xóa bản ghi hoặc đổi role.
- Downgrade giữ roster rows, trả FK về CASCADE và gỡ cột/constraint/index thêm trong revision này. Downgrade mất thông tin khóa/display_name: chỉ thực hiện trên database test hoặc theo quy trình rollback có backup, không coi là thao tác giữ nguyên snapshot.
- Alembic là cách cập nhật database hiện có; `Base.metadata.create_all` không thay schema cũ. File SQL chỉ được đồng bộ phần roster/lock, không thay thế chuỗi migration.

## API hiện có trong W44-2-01

### Trạng thái khóa công khai

`GET /api/v1/tournaments/{tournament_id}/roster-lock`

```json
{"tournament_id": 12, "locked": false, "locked_at": null}
```

Sau khóa: `locked: true`, `locked_at` là ISO timestamp. Không trả actor hoặc roster nháp. 404 giải không tồn tại; path ID phải trong PostgreSQL INTEGER dương. Response và lỗi dùng `Cache-Control: private, no-store` để không giữ trạng thái cũ.

### Capability theo giải/đội

`GET /api/v1/tournaments/{tournament_id}/teams/{team_id}/roster/capabilities` — cần JWT.

```json
{"tournament_id": 12, "team_id": 7, "can_view_roster": true, "can_edit_roster": true}
```

- Trước khóa: quản lý đúng đội hoặc đúng giải được xem; chỉ quản lý đúng đội APPROVED mới được sửa khi UPCOMING. ADMIN có quyền quản lý cả hai theo checker hiện có.
- Sau khóa: quyền xem công khai, quyền sửa false. Endpoint capability vẫn yêu cầu JWT; API đọc roster công khai sau khóa do W44-2-03 triển khai với optional authentication để cũng đọc được nháp có quyền.
- TEAM_MANAGER role/assignment GLOBAL không cho quản lý mọi đội. Membership MANAGER ACTIVE chưa có left_date, assignment TEAM/ORGANIZATION và ADMIN GLOBAL dùng đúng checker hiện có. ORGANIZER khác không tự quản lý giải; assignment ORGANIZER TOURNAMENT phải đúng ID. Giải không có created_by vẫn ADMIN-only.
- 401 thiếu/sai JWT, 404 giải/đội không tồn tại, 422 ID sai. Capability không lộ member/registration/email, kể cả đội không có đơn. Response/lỗi luôn no-store.

`GET /api/v1/tournaments/{id}/capabilities` thêm `roster_locked` và `can_lock_roster`; giữ nguyên trường cũ. `can_lock_roster` thể hiện quyền và lifecycle (quản lý đúng giải, UPCOMING, chưa khóa), không bảo đảm dữ liệu đã đầy đủ để khóa. W44-2-04 phải kiểm tra roster của mọi đội APPROVED, trả 409 nếu thiếu/không hợp lệ. Không tự ẩn nút và bỏ qua lý do nghiệp vụ.

`can_review_registrations` cho phép xử lý/từ chối đơn khi quản lý đúng giải và còn UPCOMING, kể cả roster đã khóa. Field mới `can_approve_registrations` chỉ true khi có quyền đó và chưa khóa. UI dùng field mới cho nút Duyệt, giữ nút Từ chối theo can_review_registrations; ẩn form tạo đơn khi roster_locked, giữ Hủy đơn cho quản lý đúng đội khi UPCOMING. Sau ONGOING/COMPLETED/CANCELLED cả duyệt, từ chối và hủy đều bị chặn như W44.

## Contract bàn giao W44-2-03

Schema dùng chung ở `modules/tournaments/roster_schemas.py`; consumer import trực tiếp, không khai báo bản khác.

`PUT /api/v1/tournaments/{id}/teams/{team_id}/roster`

```json
{"members": [{"user_id": 24, "role_in_team": "PLAYER"}, {"user_id": 25, "role_in_team": "SUBSTITUTE"}]}
```

Body không nhận trường lạ; user_id phải là số nguyên dương trong INTEGER (không nhận bool hoặc chuỗi); role chỉ PLAYER/SUBSTITUTE; không trùng user. Tối đa 100 phần tử/request là giới hạn tài nguyên, không phải quota theo game. `members: []` hợp lệ cho nháp, không đủ điều kiện khóa. Thay toàn bộ danh sách trong một transaction và ghi audit cùng commit.

Response PUT/GET roster dùng `RosterRead`:

```json
{"tournament_id": 12, "team_id": 7, "locked": false, "members": [{"user_id": 24, "display_name": "player24", "role_in_team": "PLAYER"}]}
```

GET trả trọn roster đội (tối đa 100 phần tử do writer áp giới hạn), thứ tự user_id tăng dần. Không trả roster_id, username động, email hoặc chi tiết membership. Dữ liệu cũ display_name NULL phải thể hiện chưa có tên snapshot, không giả mạo tên đã chụp. Draft chỉ cho quản lý đúng đội/giải; sau khóa public. GET cho cặp giải/đội chưa APPROVED trả 404; PUT cùng trường hợp trả 409 sau khi kiểm tra quyền.

Luồng ghi:

1. `get_editable_roster_context(db, tid, team_id, user)` kiểm tra tồn tại/quyền trước khi xếp hàng, khóa giải, reload actor, khóa đội rồi kiểm tra lại quyền, UPCOMING/chưa khóa và APPROVED. Trả `(tournament, refreshed_user)`; dùng actor trả về cho audit.
2. `lock_roster_memberships(db, [team_id])` trả mọi membership đã refresh và khóa. Chỉ chọn membership ACTIVE, left_date NULL, vai trò PLAYER/SUBSTITUTE của đúng đội; role gửi lên phải khớp vai trò membership tại thời điểm lưu. User ở đội khác hoặc hết ACTIVE trả 422; không cho biến MANAGER/COACH thành PLAYER bằng body.
3. Khóa hàng roster nếu cần bằng `lock_roster_rows`; kiểm tra user chưa nằm roster đội khác trong giải. Xóa/thêm nguyên tử, flush, ghi `TOURNAMENT_ROSTER_UPDATED` với before/after theo user_id/role, rồi commit; rollback cả roster/audit khi lỗi. Unique conflict trả 409.

Helper không commit/rollback thay caller; `get_db` đóng session rollback khi exception, nhưng endpoint phải xử lý rollback rõ khi bắt lỗi commit. Không giữ ORM object nháp sau rollback để trả response thành công.

## Contract bàn giao W44-2-04

`POST /api/v1/tournaments/{id}/roster-lock`, không có body bắt buộc; response `RosterLockRead` như GET. Ghi `TOURNAMENT_ROSTER_LOCKED` một lần trong cùng transaction (actor, tournament_id, thời điểm, số đội/số thành viên; không cần log email).

1. Dùng `get_managed_tournament` để chặn người ngoài trước khi lock và kiểm tra lại quyền sau chờ. Nếu đã khóa, trả trạng thái hiện có không ghi lại audit, kể cả giải đã bắt đầu/hủy; quyền quản lý vẫn phải hợp lệ. Nếu chưa khóa mà không UPCOMING: 409.
2. Giữ khóa giải, lấy toàn bộ đội APPROVED, khóa các đội theo team_id tăng dần, rồi khóa membership/roster bằng helper. Không có đội APPROVED, đội thiếu PLAYER, user không còn ACTIVE, left_date khác NULL, role không khớp hoặc snapshot sai đội/game: 409. Không mặc định game nào cần 5 người.
3. Chụp display_name từ username, lưu role đã xác minh, lấy thời điểm DB sau khi giữ đủ lock (có thể dùng `registration_timestamp` hiện có), đặt locked_at/by và audit rồi commit. Thất bại không để khóa hoặc snapshot dở dang.
4. Policy tách hai nhánh: tạo đơn và APPROVED dùng `ensure_registration_open` (UPCOMING, chưa khóa); REJECTED và hủy đơn PENDING dùng `ensure_registration_resolution_open` (chỉ cần UPCOMING). Sau khóa vẫn cho quản lý đúng đội hủy, quản lý đúng giải từ chối đơn PENDING, có audit và không thay tập APPROVED; không tự đóng đơn hoặc mở khóa snapshot. Capability phân biệt quyền xử lý và duyệt như trên. Endpoint quyết định/hủy giữ khóa giải và đơn như trước; không đổi tập APPROVED sau snapshot.
5. Bổ sung điều kiện UPCOMING → ONGOING yêu cầu khóa vào API và capability trong W44-2-04, test cả hai. Không cản ONGOING → COMPLETED/CANCELLED của dữ liệu cũ; không khóa bù lịch sử. Giao diện cũ vẫn hoạt động trong W44-2-01 vì chưa kích hoạt điều kiện bắt đầu mới trước khi có endpoint khóa.

## Thứ tự khóa và đường ghi membership

Roster writer: **giải → đội theo ID tăng dần → membership theo membership_id tăng dần → roster theo roster_id tăng dần**. Nếu cần registration, giữ thứ tự giải trước đơn; không lấy đội sau khi đã khóa các hàng con theo thứ tự ngược. Lock không kéo qua request hoặc tách commit ở giữa.

`lock_roster_memberships` khóa đội trước, kể cả đội chưa có membership; khóa này ngăn cả phantom insert nếu các writer tuân thủ giao thức. Đường thêm/đổi vai trò/kết thúc membership trong `routes/team.py` đã lấy cùng khóa đội và kiểm tra lại quyền/đọc lại membership sau chờ; chỉ giữ khóa đội, không lấy khóa giải về sau. Tạo đội mới có membership ban đầu chưa thể được một roster tham chiếu trước khi transaction tạo đội commit. Script/admin SQL tương lai thay membership phải tuân thủ khóa đội; không có trigger tự khóa cho SQL ngoài ứng dụng.

Test cạnh tranh dùng connection PostgreSQL độc lập đã xác minh writer kết thúc membership phải chờ khi snapshot validation giữ khóa đội và helper roster từ chối quyền manager bị thu hồi trong lúc chờ khóa đội. Đây là kiểm chứng giao thức nền tảng, không thay cho test idempotency/lock-vs-approve/start của endpoint W44-2-04 chưa triển khai.

## Kiểm tra và trạng thái

Bằng chứng lệnh/kết quả cập nhật ở [kế hoạch W44(2)](./weeks/2026-W44-2.md). W44-2-01 đã nghiệm thu ngày 26/10: DOANH approve head `dfb9345`, [CI 40347479342](https://github.com/Luong-dung/bt-csdl-web/actions/runs/40347479342) đạt cả 3 job, PR #57 merge `f538524`. Không xem nền tảng này là đã hoàn thành W44-2-03/04 hoặc stage W44-2-02.
