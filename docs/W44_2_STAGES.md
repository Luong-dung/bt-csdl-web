# W44-2-02 — API quản lý stage và thứ tự vòng

## Phạm vi và quyền

Tái sử dụng bảng `stages`; không thêm format/trạng thái stage, chưa tạo match/bracket hoặc nhập kết quả. GET công khai chỉ trả ID giải/stage, tên và thứ tự. Mọi mutation cần JWT và checker quản lý đúng giải (`get_managed_tournament`): ADMIN, ORGANIZER tạo giải còn quyền hợp lệ, hoặc assignment ORGANIZER đúng TOURNAMENT. ORGANIZER toàn cục không tự sửa giải người khác; giải không có created_by vẫn ADMIN-only.

Chỉ ghi khi UPCOMING. Roster đã khóa không khóa stage; ONGOING/COMPLETED/CANCELLED chặn mọi ghi stage. Capability giải thêm `can_manage_stages`, dùng cùng `stages_editable` với mutation và no-store như các capability hiện có. Quyền này không cấp quyền xem roster nháp.

## Endpoint và wire contract

Prefix: `/api/v1/tournaments/{tournament_id}/stages`.

| Thao tác | Method/path | Body | Kết quả |
|---|---|---|---|
| Danh sách | `GET /stages?offset=0&limit=50` | — | 200, mảng StageRead; `X-Total-Count` |
| Chi tiết | `GET /stages/{stage_id}` | — | 200 StageRead, chỉ khi thuộc đúng giải |
| Tạo | `POST /stages` | name, sequence_order | 201 StageRead |
| Sửa | `PATCH /stages/{stage_id}` | name và/hoặc sequence_order | 200 StageRead |
| Xóa | `DELETE /stages/{stage_id}` | — | 204, không body |
| Sắp lại toàn bộ | `PUT /stages/order` | stage_ids theo thứ tự mới | 200 mảng StageRead theo thứ tự mới |

StageRead:

```json
{"stage_id": 17, "tournament_id": 12, "name": "Vòng bảng", "sequence_order": 1}
```

Tạo hoặc sửa:

```json
{"name": "  Vòng bảng  ", "sequence_order": 3}
```

- Tên strip khoảng trắng, 1–80 ký tự sau strip. Stage trong cùng giải có thể cùng tên; nhận diện bằng stage_id, không dùng tên làm khóa.
- sequence_order là số nguyên dương ≤ 2147483647, body không nhận bool, chuỗi, số thập phân hoặc null; duy nhất trong một giải. Không tự đẩy thứ tự vòng khác khi POST/PATCH đụng vị trí; trả 409 để UI dùng endpoint sắp lại.
- POST yêu cầu cả hai trường. PATCH yêu cầu ít nhất một trường, không nhận null/trường lạ. PATCH cùng giá trị hiện tại trả dữ liệu hiện có và không tạo audit lặp.
- Không nhận tournament_id/stage_id/status từ body. Path và query ID/offset phải trong INTEGER dương hoặc không âm theo từng trường.
- List sắp theo sequence_order rồi stage_id; offset mặc định 0, limit mặc định 50/tối đa 100. Tổng không bị ảnh hưởng bởi offset/limit; CORS đã expose `X-Total-Count`. Giải tồn tại chưa có stage trả [] và tổng 0; giải không tồn tại trả 404.
- Xóa stage đã có bất kỳ match nào trả 409, không xóa trận dây chuyền. Stage chưa có match có thể xóa khi UPCOMING; các khoảng trống thứ tự được giữ, không tự đánh lại các vòng khác.

## Sắp thứ tự nguyên tử

```json
{"stage_ids": [19, 17, 23]}
```

Phải gửi đúng tập ID stage hiện có của giải, mỗi ID một lần; mảng chỉ ra thứ tự cuối, server gán sequence_order = 1..N. ID giải khác/không tồn tại/trùng/thiếu/thừa trả 422. Route `/order` đăng ký trước route ID động. Danh sách rỗng chỉ hợp lệ khi giải không có stage; hoán vị đúng như hiện tại là no-op không audit.

Giới hạn tài nguyên của một request reorder là 1000 ID, không phải quota stage của một giải. Với giải có hơn 50 vòng, consumer phải lấy mọi trang trước khi gửi; không gửi chỉ trang hiện tại. Nếu có hơn 1000 stage thì hiện chưa hỗ trợ reorder toàn bộ qua endpoint này; list/detail/PATCH vẫn dùng được. Body không bị cắt âm thầm.

Mọi writer khóa hàng tournament trước và kiểm tra lại quyền/lifecycle sau khi chờ; reorder tiếp tục khóa các stage hiện có. Không dùng nhiều request PATCH để hoán đổi thứ tự. Server chuyển các stage sang vị trí dương còn trống (không nằm trong các giá trị cũ hoặc 1..N), flush, sau đó gán thứ tự cuối và flush trong cùng transaction. Không dùng `max(sequence_order)+N`, nên dữ liệu cũ ở INTEGER_MAX vẫn đổi được. Không nới CHECK/UNIQUE hoặc tạm commit vị trí trung gian.

Hai request reorder được serialize theo giải; một request không thể quan sát tập stage cũ rồi bỏ qua stage vừa thêm khi đã lấy khóa. Nếu tạo/xóa stage trước khi reorder lấy khóa thì yêu cầu tập ID được kiểm tra trên dữ liệu mới và có thể trả 422. Response mutation dùng DTO được chụp trước commit, không reload từng ORM row sau commit và vô tình đọc kết quả writer kế tiếp.

## Audit, rollback và lỗi

- Resource `tournament_stage`; action `TOURNAMENT_STAGE_CREATED`, `TOURNAMENT_STAGE_UPDATED`, `TOURNAMENT_STAGE_DELETED`, `TOURNAMENT_STAGES_REORDERED`.
- Details gồm tournament_id, before/after: một snapshot có stage_id/name/sequence_order cho CRUD; mảng snapshot cho reorder. Actor là user hiện tại sau refresh quyền. Tạo before null, xóa after null.
- Flush nghiệp vụ, thêm audit rồi commit một lần; lỗi audit/commit rollback toàn bộ, kể cả các vị trí tạm. Không log success cho request bị từ chối, trùng order hoặc no-op.
- 401 thiếu/sai phiên; 403 không quản lý đúng giải; 404 giải/stage không tồn tại hoặc stage sai giải; 409 lifecycle, thứ tự trùng, xóa vòng có trận hoặc lỗi ràng buộc; 422 body/query/path và tập ID reorder không hợp lệ.

## Schema và migration

Revision `5f2d5fc3a731`, sau `cb86835f3e5f`, được tạo bằng `alembic revision`; không sửa migration cũ.

- Unique `uq_stages_tournament_order` trên (tournament_id, sequence_order), đồng thời phục vụ tra cứu theo giải/thứ tự.
- CHECK `ck_stages_positive_order` và `ck_stages_name`.
- Đổi FK matches.stage_id thành RESTRICT (`fk_matches_stage`), bảo vệ cả đường SQL/match insert cạnh tranh với DELETE; API còn kiểm tra match trước để trả thông báo cụ thể. Không thay FK matches.tournament_id hoặc tự sinh trận. Chưa cung cấp API xóa giải; nếu thêm sau này phải thiết kế transaction xóa/hủy lịch sử riêng.
- Migration kiểm tra dữ liệu cũ trước DDL: trùng order trong giải, order ≤ 0 hoặc tên rỗng sẽ dừng với lỗi rõ, không tự đổi ID/thứ tự/tên/xóa dữ liệu. Người vận hành sửa dữ liệu có kiểm soát rồi chạy lại.
- Hỗ trợ cài mới vì revision đầu sử dụng live metadata và constraint có thể đã tồn tại. Nâng/hạ giữ nguyên stage/match; downgrade gỡ constraint mới và trả FK về CASCADE, vì vậy chỉ rollback theo quy trình backup/test thích hợp.
- `database/schema_postgres.sql` đồng bộ phần stage/match; database đang dùng phải nâng bằng Alembic, không dùng create_all để thay schema cũ.

## Bàn giao UI W44-2-06 và test W44-2-07

UI dùng can_manage_stages, giữ form khi lỗi 409/422, tải lại danh sách sau mutation và lấy đủ trang trước reorder. Không suy quyền từ role trong frontend. Xóa có xác nhận; lỗi 409 vì có match cần hiển thị rõ, không tự xóa match. Sau giải bắt đầu, bỏ thao tác ghi nhưng vẫn cho xem list/detail.

Test API bao gồm phân quyền/scoped assignment, vòng đời, roster đã khóa, CRUD/audit/no-op, body/ID, >50 stage, hoán đổi vị trí với immediate UNIQUE và INTEGER_MAX, rollback khi audit lỗi và xóa stage có trận. Migration được kiểm tra cài mới/nâng-hạ với dữ liệu/match và dừng khi dữ liệu cũ sai; cạnh tranh dùng connection PostgreSQL độc lập, không dùng savepoint thay cho race thật.

Bằng chứng lệnh và kết quả cập nhật tại [kế hoạch W44(2)](./weeks/2026-W44-2.md). Task chờ DOANH review và CI trước khi chuyển DONE.
