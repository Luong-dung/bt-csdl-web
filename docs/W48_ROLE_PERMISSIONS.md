# W48-04 (a): Quyền toàn cục đọc từ `role_permissions`

Trước W48-04, bảng `permissions` chỉ có model, luôn 0 dòng và không được code nào dùng. Các quyền toàn cục được viết cứng bằng `has_role("ADMIN")` / `require_role(...)`. W48-04 thêm bảng nối `role_permissions`, seed danh sách quyền và chuyển các checker toàn cục sang đọc từ bảng. **Kết quả quyền mặc định không đổi**, API và DTO giữ nguyên.

## 1. Dữ liệu

| Bảng | Cột | Ràng buộc |
|---|---|---|
| `role_permissions` | `role_id`, `permission_id` | PK `(role_id, permission_id)`; FK `roles` và `permissions` đều `ON DELETE CASCADE`; index `ix_role_permissions_permission_id` |

Danh sách quyền nằm ở [`backend/core/permissions.py`](../backend/core/permissions.py):

| Quyền | Mặc định cấp cho | Thay cho kiểm tra cũ | Nơi dùng |
|---|---|---|---|
| `CATALOG_MANAGE` | ADMIN | `require_role("ADMIN")` | Ghi publisher/game/khu vực/quốc gia; `can_manage_catalog` |
| `ORGANIZATION_CREATE` | ADMIN | `require_role("ADMIN")` | `POST /organizations`; `can_create_organization` |
| `TOURNAMENT_CREATE` | ADMIN, ORGANIZER | `require_role("ADMIN", "ORGANIZER")` | `POST /tournaments`; `can_create_tournament` |
| `AUDIT_LOG_VIEW_ALL` | ADMIN | `require_role("ADMIN")` | `GET /admin/audit-logs`; `can_view_audit` toàn cục |
| `ROLE_ASSIGNMENT_MANAGE` | ADMIN | `require_role("ADMIN")` + `has_role(user, "ADMIN")` sau lock | `/admin/role-assignments` |

## 2. Luật kiểm tra

- `has_permission(user, name)` đúng khi role tài khoản **hoặc** role của một assignment còn hiệu lực với scope `GLOBAL` có quyền đó trong `role_permissions`. Assignment theo scope (TOURNAMENT/TEAM/ORGANIZATION) và assignment đã thu hồi không cấp quyền toàn cục. Cách tính này giống `has_role` cũ với scope GLOBAL.
- `require_permission(name)` là dependency trả 401 nếu chưa đăng nhập và 403 nếu thiếu quyền, giống `require_role`.
- Quyền gắn với tài nguyên vẫn nằm trong checker riêng vì phụ thuộc quan hệ: quản lý giải (người tạo/ORGANIZER được gán), trọng tài của giải, quản lý đội/tổ chức. Những checker này giữ lối tắt `has_role("ADMIN")`.
- Quyền toàn cục không còn ngoại lệ cho tên role: nếu xóa grant của ADMIN thì ADMIN cũng bị 403 ở các API trên.
- **Khôi phục khi gỡ nhầm grant của ADMIN:** khi đã mất `ROLE_ASSIGNMENT_MANAGE` thì không còn API nào cấp lại, và `seed.py` cũng không khôi phục grant đã gỡ (xem mục 3). Cấp lại bằng SQL trên DB (mỗi quyền một lần, chạy lại vô hại):

  ```sql
  INSERT INTO role_permissions (role_id, permission_id)
  SELECT r.role_id, p.permission_id FROM roles r, permissions p
  WHERE r.role_name = 'ADMIN'
    AND p.permission_name IN ('CATALOG_MANAGE', 'ORGANIZATION_CREATE', 'TOURNAMENT_CREATE',
                              'AUDIT_LOG_VIEW_ALL', 'ROLE_ASSIGNMENT_MANAGE')
  ON CONFLICT DO NOTHING;
  ```

## 3. Migration và seed

- Migration `g48a04b00001` tạo bảng nếu chưa có. Với DB đã có role ADMIN/ORGANIZER (DB đang chạy), migration ghi 5 quyền và 6 grant mặc định. Với DB rỗng, migration chỉ tạo bảng, còn `seed.py` tạo role rồi tạo quyền cùng grant. Downgrade xóa bảng nối và xóa theo tên cả 5 quyền mặc định, **kể cả quyền cùng tên đã có từ trước** (upgrade thì bỏ qua quyền có sẵn). Chấp nhận vì trước W48 bảng `permissions` luôn rỗng; backup trước khi downgrade theo [OPERATIONS.md](OPERATIONS.md) mục 1.3.
- `seed_reference_data` chỉ ghi grant mặc định **cùng lúc tạo quyền mới**. Grant mà người vận hành đã cố ý gỡ sẽ không bị seed khôi phục. Kết quả seed có thêm hai khóa `permissions`, `role_permissions`.
- `database/schema_postgres.sql` có thêm `role_permissions`.

## 4. Kiểm thử

[`backend/tests/test_role_permissions.py`](../backend/tests/test_role_permissions.py), chạy trên SQLite và `--postgres`:

- Grant mặc định khớp kiểm tra role cũ cho cả 6 role × 5 quyền, ở cả `has_permission` lẫn `GET /auth/capabilities`.
- Assignment GLOBAL cấp quyền; assignment theo scope hoặc đã thu hồi thì không.
- Sửa bảng thì API đổi theo: gỡ `TOURNAMENT_CREATE` của ORGANIZER thì tạo giải bị 403; cấp `CATALOG_MANAGE` thì ghi catalog được 201; gỡ grant của ADMIN thì các API admin trả 403.
- Seed lại không khôi phục grant đã gỡ.
- PostgreSQL: downgrade/upgrade, PK/FK CASCADE và grant mặc định khi nâng cấp DB đã có role.
