# Contract W47-04 — Quốc gia, khu vực và xóa giải

- **Task:** W47-04 (DOANH, review DUNG). Đóng mục lộ trình W03-02 (country) và W05-01 (xóa giải). **Phụ thuộc:** W47-02 (chuẩn audit). **Dùng bởi:** W47-07 (race xóa giải/đăng ký), W47-08 (E2E xóa giải bị 409).
- **Migration:** `f47a04b00001` (sau `e47a02b00001`): thêm `competition_areas.country_code` (nullable, FK `countries` `ON DELETE RESTRICT`, có index). `database/schema_postgres.sql` đã đồng bộ.

## 1. Quốc gia — `/api/v1/catalog/countries`

| Thao tác | Endpoint | Quyền |
|---|---|---|
| Danh sách (theo tên) | `GET /catalog/countries` | Công khai |
| Chi tiết | `GET /catalog/countries/{code}` | Công khai |
| Tạo | `POST /catalog/countries` `{country_code, name}` | ADMIN |
| Đổi tên | `PATCH /catalog/countries/{code}` `{name}` | ADMIN |

- `country_code`: mã ISO 3166-1 alpha-2, nhận chữ thường/khoảng trắng rồi chuẩn hóa thành chữ hoa (`" vn "` → `VN`); khác `^[A-Z]{2}$` → 422. Mã là khóa chính, **không đổi được**. `name` 2–120 ký tự, duy nhất.
- Mã hoặc tên trùng → 409; không tồn tại → 404; tên không đổi → 200, không audit.
- **Không có xóa** (khu vực tham chiếu với `RESTRICT`; ngoài phạm vi W03-02). Không làm bản đồ/đa ngôn ngữ.
- Audit `CATALOG_COUNTRY_CREATED` / `CATALOG_COUNTRY_UPDATED`, `resource = country`, `details = {country_code, before, after}`. Vì khóa là chuỗi nên cột `resource_id` (số nguyên) của W47-02 để `NULL`; lọc theo `resource=country`/`action`.

## 2. Liên kết khu vực

- `AreaCreate`/`AreaUpdate` thêm `country_code` (tùy chọn; `PATCH` gửi `null` để bỏ liên kết). Quốc gia không tồn tại → 422. `AreaRead` thêm `country_code`.
- `GET /catalog/areas?country_code=vn` lọc theo quốc gia (không phân biệt hoa thường).
- Thay đổi liên kết nằm trong audit `CATALOG_AREA_*` sẵn có (before/after là snapshot đủ cột).
- **Seed tối thiểu** (`seed.py`): 8 quốc gia (VN, TH, ID, KR, CN, TW, BR, US) và liên kết cho khu vực thuộc một quốc gia (`VN`, `VN-HCM`, `AOG` → VN; `RPL` → TH; `ASL` → ID; `LCK` → KR; `LPL` → CN; `GCS` → TW; `CBLOL`, `FFWS BR` → BR). Khu vực đa quốc gia giữ `NULL`. Seed chỉ thêm quốc gia còn thiếu và chỉ điền liên kết đang `NULL`, không ghi đè dữ liệu có sẵn.

## 3. Xóa giải — `DELETE /api/v1/tournaments/{tournament_id}`

- **Quyền:** quản lý giải hoặc ADMIN (cùng policy sửa giải). 401/403/404/422 (ID sai) như các endpoint giải khác.
- **Thành công:** `204`, xóa cứng dòng `tournaments`. Audit `TOURNAMENT_DELETED`, `resource = tournament`, `details = {tournament_id, before: <TournamentRead>, after: null}`, cùng transaction (audit lỗi → rollback, giải còn nguyên).
- **409 (không xóa gì)** khi:
  - giải không ở `UPCOMING`, hoặc đã khóa đội hình — dùng hủy giải (`CANCELLED`) thay thế;
  - có bất kỳ đơn đăng ký nào (kể cả `CANCELLED`/`REJECTED`), đội hình, stage, trận, bracket hoặc bảng xếp hạng;
  - có role assignment scope `TOURNAMENT` của giải (trọng tài/quản lý, **kể cả đã thu hồi**) — đó là lịch sử phân quyền.
- Không xóa lan: chỉ xóa khi các bảng con đều rỗng; không dựa vào `ON DELETE CASCADE`.
- **Cạnh tranh:** kiểm tra diễn ra sau khi khóa dòng giải (`get_managed_tournament`) và đọc lại quyền sau khóa. Mọi writer tạo dữ liệu con (đăng ký, stage, trận, bracket, cấp trọng tài) đều khóa giải trước, nên không có dữ liệu mới chen vào giữa kiểm tra và xóa.
- Audit cũ của giải **được giữ** (không FK). Sau khi xóa, `GET /tournaments/{id}/audit-logs` trả 404 vì giải không còn; ADMIN xem qua `GET /admin/audit-logs?tournament_id={id}`.
- **Capability:** `GET /tournaments/{id}/capabilities` thêm `can_delete` = có quyền quản lý và không có lý do chặn ở trên (gợi ý cho UI; DELETE vẫn kiểm tra lại).

## 4. Kiểm thử

- `tests/test_countries.py` (11 ca): seed công khai và lọc khu vực; ADMIN tạo/đổi tên kèm audit, no-op không audit; 6 payload 422; trùng 409, 404; liên kết khu vực tạo/đổi/bỏ, quốc gia không tồn tại 422; audit lỗi → rollback.
- `tests/test_tournament_delete.py` (13 ca): xóa thành công + audit + nhật ký ADMIN còn giữ; ma trận 401/403/404/422; 3 trạng thái không phải UPCOMING; roster khóa; đơn đăng ký (kể cả đã hủy) vẫn còn sau 409; stage; bảng xếp hạng; trọng tài đang hiệu lực/đã thu hồi; audit lỗi → rollback; `can_delete`.
- `tests/test_tournament_delete_concurrency.py` (3 ca, PostgreSQL connection độc lập): xóa chờ khóa giải rồi thấy stage mới → 409; quyền bị chuyển khi chờ → 403; xóa song song với đăng ký luôn nhất quán. Bỏ khóa giải trong xóa thì 2 ca đầu fail.
- `tests/test_area_country_migration.py` (PostgreSQL): hạ về `e47a02b00001` rồi nâng lại giữ nguyên khu vực, có FK `RESTRICT` + index; FK chặn mã lạ và chặn xóa quốc gia đang dùng.
- `tests/test_seed.py`: cập nhật số lượng, thêm ca giữ quốc gia/liên kết có sẵn.
