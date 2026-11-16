# Contract W47-01 — Cấp/thu hồi quyền theo scope

- **Task:** W47-01 (DUNG, review DOANH). **Phụ thuộc:** W47-05 (UI trọng tài), W47-07 (integration/race), W47-08 (E2E).
- **Migration:** `d47a01b00001` (sau `c46a01b00001`).

## 1. Dữ liệu

`role_assignments` thêm 4 cột, đều nullable:

| Cột | Ý nghĩa |
|---|---|
| `granted_by`, `granted_at` | Người/thời điểm cấp. Dòng cũ trước W47 giữ NULL (không rõ), không backfill |
| `revoked_by`, `revoked_at` | Người/thời điểm thu hồi. `revoked_at IS NULL` = đang hiệu lực |

- Unique index một phần `uq_role_assignments_active` trên `(user_id, role_id, scope_type, coalesce(scope_id, 0)) WHERE revoked_at IS NULL`: mỗi user/role/scope chỉ có **một** assignment hiệu lực; dòng đã thu hồi giữ làm lịch sử, cấp lại tạo dòng mới.
- `User.assignments` chỉ chứa assignment hiệu lực (viewonly). Mọi checker hiện có (`has_role`, `can_manage_tournament`, `is_tournament_referee`, `managed_teams_query`) tự bỏ qua quyền đã thu hồi. Code mới **không** ghi qua `user.assignments`; thêm/sửa trực tiếp `RoleAssignment`.
- Upgrade dừng (không gộp/xóa ngầm) nếu dữ liệu cũ có assignment hiệu lực trùng. Downgrade dừng nếu đã có dòng bị thu hồi (xóa cột sẽ làm chúng hiệu lực lại).

## 2. API trọng tài của giải

Quyền: quản lý đúng giải (`can_manage_tournament`) hoặc ADMIN. REFEREE, VIEWER, quản lý giải khác: 403. Thiếu/sai token: 401.

| Thao tác | Endpoint | Ghi chú |
|---|---|---|
| Danh sách | `GET /api/v1/tournaments/{id}/referees?include_revoked=false&offset=0&limit=50` | `X-Total-Count`; sắp theo `assignment_id`; mặc định chỉ hiệu lực |
| Cấp | `POST /api/v1/tournaments/{id}/referees` body `{"user_id": int}` (strict, không nhận field lạ) | 201 |
| Thu hồi | `DELETE /api/v1/tournaments/{id}/referees/{assignment_id}` | 200, trả bản ghi đã thu hồi |

Response (`RefereeRead`): `assignment_id, tournament_id, user_id, username, real_name, granted_by, granted_at, revoked_by, revoked_at, active`. **Không** trả email.

Thứ tự kiểm tra khi cấp: 401 → 404 giải → 403 → khóa giải, đọc lại quyền actor → 409 giải `COMPLETED`/`CANCELLED` → 409 người được cấp đang thi đấu trong giải (roster snapshot, hoặc thành viên ACTIVE của đội có đơn PENDING/APPROVED) → 422 tự cấp cho mình → 404 user không tồn tại → 409 đã có quyền hiệu lực.

Thu hồi: được phép ở mọi trạng thái giải (bỏ quyền luôn an toàn). Assignment không thuộc giải này, không phải REFEREE scope TOURNAMENT, hoặc không tồn tại: 404. Đã thu hồi: 409 (retry sau timeout cũng nhận 409, UI coi là đã xong và tải lại danh sách).

Capability: `GET /api/v1/tournaments/{id}/capabilities` thêm `can_manage_referees` = quản lý được giải và giải chưa `COMPLETED`/`CANCELLED`. Khi `false`, UI vẫn có thể hiện danh sách (nếu `can_manage`) và nút thu hồi.

## 3. API ADMIN

Chỉ ADMIN (role toàn cục hoặc assignment ADMIN GLOBAL). Prefix `/api/v1/admin/role-assignments`.

| Thao tác | Endpoint |
|---|---|
| Danh sách | `GET ?user_id=&scope_type=&scope_id=&include_revoked=false&offset=&limit=` (`X-Total-Count`) |
| Cấp | `POST` body `{"user_id", "role": ADMIN\|ORGANIZER\|TEAM_MANAGER\|REFEREE\|VIEWER, "scope_type": GLOBAL\|TOURNAMENT\|TEAM\|ORGANIZATION, "scope_id"}` |
| Thu hồi | `DELETE /{assignment_id}` |

- `scope_id` phải null khi GLOBAL, bắt buộc khi scope khác; scope không tồn tại: 422. Tự cấp/tự thu hồi của chính mình: 422 (tránh tự khóa tài khoản quản trị). Trùng: 409.
- Scope TOURNAMENT khóa giải trước khi ghi, cùng thứ tự khóa với mọi writer của giải.

## 4. Transaction và audit

- Một transaction: khóa giải (nếu scope là giải) → đọc lại actor → khóa assignment → ghi → audit → commit. Lỗi ở bất kỳ bước nào rollback cả assignment và audit.
- Audit `resource='role_assignment'`, `action` = `ROLE_ASSIGNMENT_GRANTED` | `ROLE_ASSIGNMENT_REVOKED`, `details = {tournament_id (null nếu không phải scope giải), role, before, after}`; `before/after` gồm `assignment_id, user_id, role_id, scope_type, scope_id, revoked_at`. Request bị từ chối không ghi audit.
- Thu hồi có hiệu lực ngay với mutation đang chờ khóa giải: các route kết quả/bắt đầu trận đọc lại quyền sau lock (W45), nên quyền đã thu hồi không còn trong `User.assignments`.

## 5. Kiểm thử (W47-01)

- `tests/test_referee_assignments.py` (25 ca): luồng cấp → bắt đầu trận → thu hồi → bị chặn → cấp lại; trùng 409 không audit; ma trận 401/403; quản lý giải khác; tự cấp/user không tồn tại/payload sai; người đang thi đấu; giải đóng; thu hồi hai lần/khác role; capability; fault injection audit → rollback; ràng buộc DB một assignment hiệu lực (kể cả GLOBAL `scope_id` NULL); checker bỏ qua quyền thu hồi; API ADMIN mọi scope, scope sai, chỉ ADMIN, không tự cấp.
- `tests/test_role_assignment_migration.py` (3 ca PostgreSQL): upgrade giữ dòng cũ hiệu lực và không bịa lịch sử; dừng khi trùng; downgrade dừng khi có dòng thu hồi.
- Race cấp/cấp trùng và thu hồi trong lúc nhập kết quả trên connection PostgreSQL độc lập thuộc W47-07 theo phân công.
