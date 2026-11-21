# Contract W47-03 — Cập nhật đội và tổ chức (W04-01)

- **Task:** W47-03 (DOANH, review DUNG). **Phụ thuộc:** W47-02 (chuẩn audit). **Dùng bởi:** W47-06 (form sửa đội/tổ chức), W47-07/-08.
- **Migration:** không cần. Bảng `organizations` và cột `teams.organization_id`, `teams.logo_url` đã có từ migration identity.

## 1. Sửa đội — `PATCH /api/v1/teams/{team_id}`

- **Quyền:** người quản lý đội theo đúng policy hiện có (`managed_teams_query`): MANAGER membership ACTIVE, TEAM_MANAGER scope TEAM/ORGANIZATION, hoặc ADMIN. Kiểm tra quyền trước khi xếp hàng khóa, rồi **kiểm tra lại sau khi khóa đội** (quyền bị thu hồi trong lúc chờ → 403).
- **Payload (cập nhật một phần, `extra="forbid"`):**

| Trường | Ràng buộc | Gửi `null` |
|---|---|---|
| `name` | 2–100 ký tự, cắt khoảng trắng | 422 |
| `tag` | 2–10 ký tự chữ/số, lưu chữ hoa, duy nhất (không phân biệt hoa thường) | 422 |
| `game_id` | game tồn tại | 422 |
| `organization_id` | tổ chức tồn tại | được, = tách khỏi tổ chức |
| `logo_url` | `http(s)://…`, ≤ 255 ký tự | được, = xóa logo |

- Body rỗng → 422. Giá trị giống hiện tại được bỏ qua; nếu không còn gì đổi → 200, **không ghi audit**.
- **Response 200:** `{team_id, name, tag, game_id, organization_id, logo_url}`. `GET /teams/{id}` cũng trả thêm `organization_id`, `logo_url`. Danh sách (`GET /teams`, `/teams/managed`, `/tournaments/{id}/teams`) **giữ nguyên 4 trường** như contract W44.

### Điều kiện chặn (409)

| Thay đổi | Bị chặn khi |
|---|---|
| `game_id`, `organization_id` | Đội có đơn `PENDING`/`APPROVED` trong giải `UPCOMING`/`ONGOING` (đăng ký chưa kết thúc; bao gồm roster đã khóa của giải đang chạy) |
| `game_id` | Đội từng `APPROVED` trong giải đã khóa roster, **kể cả giải đã COMPLETED** — trận/bracket lịch sử gắn với game cũ |
| `tag` | Trùng tag đội khác |

- `name`, `tag`, `logo_url` luôn sửa được (kể cả khi đang thi đấu). Roster đã khóa lưu `display_name` của tuyển thủ, không lưu tên đội, nên không bị ảnh hưởng.
- Đơn `REJECTED`/`CANCELLED`, hoặc giải `CANCELLED`/`COMPLETED` (chưa khóa roster) không chặn.

### Chuyển tổ chức (403)

Chuyển đội làm thay đổi ai quản lý đội qua scope ORGANIZATION, nên ngoài ADMIN, người sửa phải quản lý **cả tổ chức cũ (nếu có) và tổ chức mới (nếu có)** bằng TEAM_MANAGER scope ORGANIZATION. MANAGER membership thông thường không tách/gắn đội vào tổ chức được.

### Thứ tự khóa và cạnh tranh

- `PATCH /teams/{id}` chỉ khóa dòng `teams` (giống writer membership), không khóa giải sau đó.
- **Thay đổi W47-03:** `POST /tournaments/{id}/registrations` nay khóa **giải → đội** (trước đây chỉ đọc đội). Hai request tuần tự hóa trên dòng đội: đổi game commit trước → đăng ký đọc lại thấy game mới → 422; đăng ký commit trước → đổi game thấy đơn PENDING → 409. Không thể có đơn của đội khác game với giải.

### Audit

`action = TEAM_UPDATED`, `resource = team`, `details = {team_id, before, after}`; `before/after` = `{team_id, organization_id, game_id, name, tag, logo_url}`. Ghi cùng transaction, audit lỗi → rollback. Request bị từ chối không ghi.

## 2. Tổ chức — `/api/v1/organizations`

| Thao tác | Endpoint | Quyền |
|---|---|---|
| Danh sách | `GET /organizations` (theo tên) | Công khai |
| Chi tiết | `GET /organizations/{id}` → `{organization_id, name, teams: [TeamRead]}` | Công khai |
| Tạo | `POST /organizations` `{name}` | ADMIN |
| Đổi tên | `PATCH /organizations/{id}` `{name}` | ADMIN hoặc TEAM_MANAGER scope ORGANIZATION của tổ chức đó |
| Capability | `GET /organizations/{id}/capabilities` → `{organization_id, can_update}` | Đăng nhập |

- `name`: 2–150 ký tự, duy nhất → trùng 409. Đổi tên khóa dòng tổ chức và kiểm tra lại quyền sau khóa. Tên không đổi → 200, không audit.
- Audit `ORGANIZATION_CREATED` / `ORGANIZATION_UPDATED`, `resource = organization`, `details = {organization_id, before, after}`.
- **Không có xóa tổ chức** trong W47: đội và role assignment scope ORGANIZATION đang tham chiếu; ngoài phạm vi W04-01.

## 3. Capability

- `GET /api/v1/teams/{id}/capabilities` thêm `can_update` và `editable_fields` (tập con của `name, tag, logo_url, game_id, organization_id` mà PATCH chấp nhận lúc này; bỏ `game_id`/`organization_id` khi đang bị chặn hoặc thiếu quyền tổ chức). Là gợi ý cho UI; PATCH vẫn kiểm tra lại.
- `GET /api/v1/auth/capabilities` thêm `can_create_organization` (ADMIN).

## 4. Audit log W47-02

`core.audit.RESOURCE_ID_KEYS` thêm `team → team_id`, `organization → organization_id`. Hai resource này không thuộc giải nào nên chỉ hiện trong nhật ký ADMIN.

## 5. Kiểm thử

- `tests/test_team_update.py` (36 ca, SQLite và `--postgres`): sửa hồ sơ + audit before/after; ma trận 401/403/404; 13 payload 422 không audit; game/tổ chức không tồn tại 422; tag trùng 409; no-op không audit; chặn theo đơn mở (3 trạng thái) và không chặn với đơn đã kết thúc (4 trạng thái); roster khóa lịch sử chỉ chặn game; quyền chuyển tổ chức hai phía; quản lý scope ORGANIZATION; fault injection audit → rollback; `editable_fields`; danh sách giữ 4 trường; CRUD tổ chức (công khai, ADMIN tạo, đổi tên theo quyền, capability, rollback); lọc nhật ký `resource=team`.
- `tests/test_team_update_concurrency.py` (3 ca, PostgreSQL connection độc lập): đăng ký chờ khóa đội rồi thấy game mới → 422; đổi game chờ khóa đội rồi thấy đơn PENDING → 409 không audit; chạy song song luôn nhất quán. Bỏ khóa đội trong tạo đăng ký thì ca đầu fail.
