# Nhật ký sử dụng AI

Tài liệu này lưu lại những yêu cầu mỗi thành viên đã gửi cho AI trong quá trình phát triển dự án. Mục đích là minh bạch cách sử dụng AI, truy vết thay đổi và chứng minh người thực hiện đã kiểm tra, hiểu và chịu trách nhiệm với phần code được tạo hoặc chỉnh sửa.

## 1. Quy tắc ghi nhật ký

- Mỗi yêu cầu có một mã duy nhất, ví dụ `AI-2026-W42-001`.
- Người gửi yêu cầu phải tự ghi hoặc cập nhật bản ghi sau khi hoàn thành.
- Ghi tóm tắt đúng ý định ban đầu; không cần sao chép dữ liệu bí mật, token hoặc mật khẩu vào tài liệu.
- Nếu AI đề xuất code, người phụ trách phải đọc, chỉnh sửa nếu cần và chạy kiểm tra phù hợp.
- Không đánh dấu hoàn thành chỉ vì AI đã trả lời; phải có bằng chứng như test, build, migration check hoặc review.
- Một yêu cầu có thể liên kết với nhiều task/PR, nhưng phải ghi rõ file và kết quả thực tế.

## 2. Trạng thái

| Trạng thái | Ý nghĩa |
|---|---|
| `REQUESTED` | Đã gửi yêu cầu cho AI |
| `APPLIED` | Đã áp dụng một phần hoặc toàn bộ đề xuất |
| `VERIFIED` | Đã tự kiểm tra bằng test/build/review |
| `REJECTED` | Không áp dụng đề xuất |
| `FOLLOW-UP` | Cần yêu cầu tiếp theo để hoàn thiện |

## 3. Nhật ký theo thành viên

### Lường Tiến Dũng — `DUNG`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W42-001` | `2026-10-11` | Reset platform | Tái cấu trúc project theo đặc tả nền tảng quản lý giải đấu Esports | Đã áp dụng và đưa lên PR | Backend, database, frontend, docs | Backend smoke test, Alembic check, frontend build | `VERIFIED` |
| `AI-2026-W42-002` | `2026-10-11` | W42-01 / PR #10 | Bổ sung seed tối thiểu cho role, publisher, game và khu vực | Script seed trong một transaction, chạy lại không trùng và giữ dữ liệu hiện có | `backend/seed.py`, `backend/tests/test_seed.py`, README, tài liệu W42 | 3 pytest đạt; cả hai migration + seed trên schema PostgreSQL tạm rỗng đạt; seed lần 2 thêm 0 bản ghi; rollback schema tạm | `VERIFIED` |
| `AI-2026-W42-004` | `2026-10-13` | W42-02 / chưa mở PR | Hoàn thiện kiểm tra role/scope, không commit; kiểm tra thêm PostgreSQL | Helper và kiểm tra quyền ghi catalog, tạo giải, quản lý đúng đội; xử lý subject JWT sai; fixture PostgreSQL tùy chọn `--postgres` | Middleware auth, routes, tests, README, tài liệu W42 | AI chạy SQLite: 58 test đạt; PostgreSQL: 55 test quyền/catalog đạt, 42 test quyền dùng JWT thật qua TestClient; hai migration + seed mỗi schema tạm, rollback và xác nhận schema biến mất. Chờ DOANH review | `APPLIED` |

### Nguyễn Quốc Doanh — `DOANH`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W42-003` | `2026-10-13` | W42-03 / PR #12 | Hoàn thiện API catalog: CRUD/list + validation cho publisher, game, competition area | Schema Pydantic, kiểm tra trùng/khóa ngoại/vòng lặp khu vực cha, chặn xóa bản ghi đang được dùng; ghi cần JWT | `backend/routes/catalog.py`, `backend/tests/test_catalog_api.py`, README, tài liệu W42 | `pytest -q`: 16 passed; cố ý gỡ kiểm tra vòng lặp và kiểm tra giải đấu thì test tương ứng fail | `VERIFIED` |
| `AI-2026-W42-004` | `2026-10-13` | W42-04 / PR #13 | Hoàn thiện nghiệp vụ tạo đội và quản lý membership, kèm kiểm tra quyền quản lý đội | Thêm/đổi vị trí/kết thúc thành viên; chỉ `MANAGER` của đội hoặc `ADMIN`; một membership `ACTIVE` mỗi người; giữ ít nhất một quản lý; audit log; sửa partial index cho SQLite | `backend/routes/team.py`, `backend/modules/teams/models.py`, `backend/tests/test_team_api.py`, README, tài liệu W42 | `pytest -q`: 26 passed; test phát hiện lỗi 500 khi thêm lại thành viên cùng ngày và đã sửa; cố ý gỡ từng kiểm tra thì test fail | `VERIFIED` |
| `AI-2026-W42-005` | `2026-10-15` | Review PR #14; W42-04 lên `main` | Review PR #14 (chạy test, đối chiếu với W42-04); đưa code W42-04 (PR #13 merge nhầm vào `feature/W42-catalog-api`) lên `main` và gỡ conflict với PR #14 | Review Request changes trên PR #14; gộp kiểm tra quyền quản lý đội vào `ensure_team_manager` trong `middleware/auth.py`, dùng chung cho thêm/đổi vị trí/kết thúc thành viên; thêm test quyền theo TEAM/ORGANIZATION cho đổi vị trí và kết thúc | `backend/middleware/auth.py`, `backend/routes/team.py`, `backend/tests/test_permissions.py`, `backend/tests/test_team_api.py`, tài liệu W42 | `pytest -q`: 71 passed (SQLite) | `APPLIED` |

### Nguyễn Tùng Dương — `DUONG`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W42-006` | `2026-10-16` | [W42-05 / PR #17](https://github.com/Luong-dung/bt-csdl-web/pull/17) | Tạo giao diện đăng ký/đăng nhập và lưu JWT bằng API thật | Thêm form đăng ký, đăng nhập, lưu access token trong `localStorage`, gọi `/auth/me`, hiển thị tài khoản và đăng xuất; chỉ xóa token khi `/auth/me` trả `401/403`, giữ token khi lỗi mạng/server và hủy phản hồi cũ sau đăng xuất | `frontend/src/App.tsx`, `frontend/src/styles.css` | TypeScript không có lỗi; `npm run build` thành công | `VERIFIED` |
| `AI-2026-W42-007` | `2026-10-17` | [W42-06 / PR #18](https://github.com/Luong-dung/bt-csdl-web/pull/18) | Tạo giao diện danh sách và tạo đội, sau đó xử lý góp ý review | Tải game và đội qua API; tạo đội có xác thực JWT; lưu form trước `await` để reset đúng; nút “Xem đội” gọi `/teams/{id}` và hiển thị chi tiết thành viên | `frontend/src/App.tsx`, `frontend/src/styles.css` | `npm run build` thành công; `backend/.venv/Scripts/python.exe -m pytest -q`: 71 passed, 1 warning; đã push commit `fb1924b` và cập nhật mô tả PR kèm bằng chứng | `VERIFIED` |

### Đồng Đức Dương — `DUC`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  | `REQUESTED` |

## 4. Mẫu bản ghi chi tiết

Sử dụng mẫu này khi yêu cầu có ảnh hưởng lớn đến kiến trúc, database, API hoặc nhiều file:

```markdown
### AI-YYYY-Www-NNN — Tên ngắn của yêu cầu

- **Người thực hiện:** Tên thành viên (`MA`)
- **Ngày gửi:** `YYYY-MM-DD`
- **Task tuần:** `Wxx-yy`
- **Pull Request/commit:** link
- **Mục tiêu:** Vì sao cần nhờ AI
- **Tóm tắt yêu cầu gửi AI:** Nội dung ngắn gọn, không chứa secret
- **Đề xuất chính của AI:** Các hướng hoặc thay đổi được đề xuất
- **Phần đã áp dụng:** Những thay đổi thực tế đã đưa vào code
- **Phần không áp dụng:** Đề xuất bị loại bỏ và lý do
- **File/module ảnh hưởng:** Danh sách file hoặc module
- **Kiểm tra đã chạy:** test, build, migration, review hoặc demo
- **Kết quả kiểm tra:** đạt/thất bại và thông tin liên quan
- **Người review:** Tên reviewer
- **Trạng thái:** `REQUESTED` / `APPLIED` / `VERIFIED` / `REJECTED` / `FOLLOW-UP`
- **Ghi chú:** Rủi ro, việc cần làm tiếp theo
```

## 5. Mẫu ghi nhanh

| ID | Người | Ngày | Task/PR | Yêu cầu AI | Thay đổi chính | Bằng chứng | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-YYYY-Www-NNN` | `MA` | `YYYY-MM-DD` | `Wxx-yy` / link PR | Tóm tắt yêu cầu | Tóm tắt kết quả | Test/build/review | `REQUESTED` |

## 6. Rà soát cuối tuần

Nhóm trưởng kiểm tra nhật ký cùng với [TEAM_WORK_PLAN.md](./TEAM_WORK_PLAN.md):

- Mỗi task đã dùng AI có bản ghi tương ứng.
- Bản ghi có người thực hiện và link PR/commit.
- Có bằng chứng kiểm tra trước khi đánh dấu `VERIFIED`.
- Không có secret, token, mật khẩu hoặc dữ liệu cá nhân nhạy cảm.
- Thành viên hiểu và trình bày được phần code mình đã áp dụng.
