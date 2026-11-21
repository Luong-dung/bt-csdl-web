# Contract W47-02 — Chuẩn audit và API đọc nhật ký

- **Task:** W47-02 (DUNG, review DUC). **Phụ thuộc:** W47-03/-04 (audit theo chuẩn này), W47-06 (UI nhật ký), W47-07/-08.
- **Migration:** `e47a02b00001` (sau `d47a01b00001`). `database/schema_postgres.sql` đã đồng bộ.

## 1. Một đường ghi audit

- Mọi mutation ghi qua `core.audit.record_audit(db, user_id, action, resource, details)` trong **cùng transaction** với thay đổi. Không commit riêng; audit lỗi thì rollback cả thay đổi.
- Giữ nguyên `action`/`resource`/`details` đã có từ W43–W47-01, không đổi tên action cũ. Hàm audit riêng của team (`team_membership`) nay gọi `record_audit`, `details` giữ đúng shape cũ.
- `audit_logs` thêm 2 cột **dẫn xuất từ `details`** (có index, không FK để lịch sử còn khi tài nguyên bị xóa):

| Cột | Lấy từ |
|---|---|
| `tournament_id` | `details.tournament_id` (chỉ số nguyên) |
| `resource_id` | khóa ID theo `resource` trong `details`, hoặc trong `details.after`/`details.before` |

Bảng khóa ID (`core.audit.RESOURCE_ID_KEYS`): `tournament→tournament_id`, `tournament_registration→registration_id`, `tournament_stage→stage_id`, `tournament_roster→team_id`, `match→match_id`, `bracket→bracket_id`, `team_membership→membership_id`, `role_assignment→assignment_id`, `publisher→publisher_id`, `game→game_id`, `area→area_id`, `team→team_id` và `organization→organization_id` (W47-03, [contract](./W47_TEAM_UPDATE.md)). Resource `country` (W47-04, khóa chuỗi) không có `resource_id`; xóa giải ghi `TOURNAMENT_DELETED` ([contract](./W47_COUNTRY_TOURNAMENT_DELETE.md)). **Resource mới phải thêm khóa vào bảng này**, và đặt `tournament_id` trong `details` nếu thuộc một giải.

- Dòng cũ được migration điền 2 cột bằng cùng hàm `derive_ids`; `details` không bị sửa. Dòng không có ID trong `details` để NULL (hiện trong nhật ký ADMIN, không hiện trong nhật ký giải).

## 2. Audit catalog (mới)

Tạo/sửa/xóa publisher, game, khu vực ghi `CATALOG_{PUBLISHER|GAME|AREA}_{CREATED|UPDATED|DELETED}`, `resource` = `publisher`/`game`/`area`, `details = {<resource>_id, before, after}` (`before` null khi tạo, `after` null khi xóa). Request bị từ chối (403/404/409/422) không ghi audit.

## 3. API đọc (chỉ đọc)

| Endpoint | Quyền |
|---|---|
| `GET /api/v1/tournaments/{id}/audit-logs` | Quản lý đúng giải hoặc ADMIN. 401/404/403 |
| `GET /api/v1/admin/audit-logs` | Chỉ ADMIN; thêm lọc `tournament_id` |

- **Lọc:** `resource`, `action`, `actor_id`, `resource_id`, `since`, `until` (ISO 8601 **có múi giờ**, thiếu múi giờ hoặc `since > until` → 422). **Phân trang:** `offset`, `limit` (1–100, mặc định 50), `X-Total-Count` là tổng chính xác theo bộ lọc.
- **Thứ tự:** mới nhất trước theo `log_id` giảm dần (duy nhất, nên trang không trùng/không sót).
- **Response:** `log_id, created_at, action, resource, resource_id, tournament_id, actor {user_id, username} | null, details`. Không trả email. `details` bị lọc đệ quy các khóa `email, password, password_hash, token, access_token, preview_token, secret` (không phân biệt hoa thường). `actor = null` khi người thực hiện đã bị xóa hoặc là hệ thống.
- Đọc không tạo audit, không sửa dữ liệu. Luôn `Cache-Control: private, no-store`.
- **Capability:** `GET /api/v1/auth/capabilities` thêm `can_view_audit` (ADMIN); capability giải thêm `can_view_audit` (= `can_manage`).

## 4. Giới hạn

- Nhật ký giải chỉ gồm dòng có `tournament_id`. Audit `team_membership` và catalog không thuộc giải nào, chỉ ADMIN xem.
- Chưa ghi audit cho đăng ký/đăng nhập (không thuộc phạm vi W47).
- Migration dùng code hiện tại (`core.audit.derive_ids`) để backfill; nếu sau này đổi bảng khóa ID, cần migration mới chứ không sửa migration này.

## 5. Kiểm thử (W47-02)

- `tests/test_audit_logs.py` (23 ca): `derive_ids` 8 ca; API ghi đủ 2 cột; catalog tạo/sửa/xóa có before/after và actor, từ chối không ghi, fault injection rollback; quản lý chỉ thấy giải mình, mới nhất trước; ma trận quyền 401/403/404; bộ lọc và 422; phân trang ổn định, tổng chính xác; lọc khóa nhạy cảm và đọc không ghi; actor null; no-store và capability.
- `tests/test_audit_log_migration.py` (PostgreSQL): backfill từ `details`, `details` không đổi, downgrade/upgrade không mất dữ liệu.
- `test_capabilities.py`: cập nhật kỳ vọng global capability thêm `can_view_audit`.
