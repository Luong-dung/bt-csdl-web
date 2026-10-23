# W44-01 — Quyền thao tác cho giao diện

Các endpoint dưới đây cần JWT. Dữ liệu được tính từ checker backend cho từng request, trả `Cache-Control: private, no-store`; frontend tải lại khi đổi tài khoản/tài nguyên và sau thay đổi quyền. Đây là gợi ý hiển thị: mọi API ghi vẫn kiểm tra quyền và trạng thái hiện tại.

| Endpoint | Response |
|---|---|
| `GET /api/v1/auth/capabilities` | `can_manage_catalog`, `can_create_tournament` |
| `GET /api/v1/teams/managed?game_id=&offset=0&limit=50` | Danh sách đội có quyền quản lý, cùng schema phần tử như `GET /teams`; tên tăng dần, ID phân định khi trùng tên |
| `GET /api/v1/teams/{id}/capabilities` | `team_id`, `can_manage_members`, `can_register_for_tournament` |
| `GET /api/v1/tournaments/{id}/capabilities` | `tournament_id`, `can_manage`, `can_update`, `can_change_status`, `can_review_registrations`, `editable_fields`, `allowed_status_transitions` |

`limit` từ 1 đến 100; offset từ 0 đến 2147483647. Danh sách managed phân trang sau khi lọc quyền, có thể trả rỗng. Các ID và game filter phải là số nguyên dương trong phạm vi PostgreSQL INTEGER. Thiếu/sai JWT trả 401; tài nguyên không tồn tại trả 404; dữ liệu đường dẫn/query sai trả 422. User hợp lệ không có quyền nhận cờ false hoặc danh sách rỗng, không nhận thông tin assignment của người khác.

## Quy tắc

- Catalog: ADMIN trong role hoặc assignment GLOBAL hợp lệ. ADMIN theo scope tài nguyên không được quản trị catalog toàn hệ thống.
- Tạo giải: ADMIN/ORGANIZER toàn cục; assignment ORGANIZER trên một giải không cấp quyền tạo giải mới.
- Đội: ADMIN toàn cục, membership MANAGER ACTIVE chưa có ngày rời, hoặc TEAM_MANAGER được gán đúng TEAM/ORGANIZATION. Role TEAM_MANAGER hoặc assignment GLOBAL TEAM_MANAGER không tự cấp quyền quản lý mọi đội, giữ nguyên chính sách hiện có.
- Giải: ADMIN toàn cục, người tạo có quyền ORGANIZER toàn cục, hoặc assignment ORGANIZER đúng TOURNAMENT. Giải không có người tạo chỉ ADMIN quản lý.
- `can_manage` thể hiện quyền với tài nguyên. Các cờ update/change_status xét thêm vòng đời W43; giải COMPLETED/CANCELLED trả false cùng danh sách trường/trạng thái rỗng. ONGOING chỉ sửa name/description/end_date.
- `can_review_registrations` cần quyền quản lý và UPCOMING. `can_register_for_tournament` trên đội chỉ thể hiện quyền đại diện đội; API đăng ký vẫn phải kiểm tra game, trạng thái giải và đơn trùng.
- Chính sách đội được dùng chung trong `managed_teams_query` cho cả mutation checker, capability và bộ chọn đội; không sao chép logic role trong frontend.

W44-05 dùng các cờ này thay cho suy quyền từ `user.role` trên catalog/membership và UI giải mới. W44-01 không thay giao diện và không cung cấp API cấp/thu hồi assignment.

## Kiểm tra

Từ thư mục backend, dùng Python trong venv của dự án:

```powershell
python -m pytest -q
python -m pytest tests/test_capabilities.py --postgres -q
```

Test dùng JWT thật và schema PostgreSQL tạm rollback; bao phủ role, GLOBAL/TEAM/ORGANIZATION/TOURNAMENT, quyền sai scope, membership hết hiệu lực, thu hồi quyền, đổi tài khoản, phân trang và đối chiếu capability với API ghi.

Kiểm tra ngày 23/10/2026: backend 214 passed, 1 skipped; toàn bộ PostgreSQL marked suite 212 passed, 3 deselected; 41 test capability chạy riêng đạt trên cả SQLite và PostgreSQL. Một cảnh báo deprecation từ Starlette/AnyIO.
