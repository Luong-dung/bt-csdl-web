# Nhật ký sử dụng AI

Tài liệu này lưu lại những yêu cầu mỗi thành viên đã gửi cho AI trong quá trình phát triển dự án. Mục đích là minh bạch cách sử dụng AI, truy vết thay đổi và chứng minh người thực hiện đã kiểm tra, hiểu và chịu trách nhiệm với phần code được tạo hoặc chỉnh sửa.

## 1. Quy tắc ghi nhật ký

- Chỉ ghi nội dung AI hỗ trợ viết/sửa code, migration, test, cấu hình build/CI và review kỹ thuật liên quan. Không ghi trao đổi riêng, chấm/điều chỉnh điểm, phân công hay lập kế hoạch nhóm vào nhật ký này.
- Yêu cầu mới dùng mã `AI-YYYY-Www-NGUOI-NNN`, ví dụ `AI-2026-W42-DUONG-001`. `NGUOI` là mã thành viên ở các mục bên dưới (`DUNG`, `DOANH`, `DUONG`, `DUC`); `NNN` tăng riêng cho từng người trong từng tuần. Kiểm tra mã chưa tồn tại trước khi thêm. Giữ nguyên mã lịch sử để không làm hỏng tham chiếu cũ.
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
| `AI-2026-W43-DUNG-001` | `2026-10-18` | W43-01 / `feature/W43-01-demo-seed` | Triển khai script dữ liệu và tài khoản demo theo vai trò trên nhánh riêng | Thêm `seed_demo.py`: 6 user, tổ chức, đội VALORANT và 2 membership; mật khẩu lấy từ môi trường; chỉ nhận database demo/test riêng; tùy chọn migrate đúng đích; chạy lại không trùng, giữ mật khẩu/dữ liệu cũ, báo lỗi khi xung đột; hướng dẫn demo | `backend/seed_demo.py`, `backend/tests/test_seed_demo.py`, `docs/DEMO_DATA.md`, README | AI chạy 16 test PostgreSQL trong schema tạm đạt; CLI migrate + seed hai lần trên database tạm đạt, lần hai thêm 0; xác nhận commit và dọn database tạm; test có đăng nhập JWT/quyền thật. Chưa có review DUC | `APPLIED` |
| `AI-2026-W42-001` | `2026-10-11` | Reset platform | Tái cấu trúc project theo đặc tả nền tảng quản lý giải đấu Esports | Đã áp dụng và đưa lên PR | Backend, database, frontend, docs | Backend smoke test, Alembic check, frontend build | `VERIFIED` |
| `AI-2026-W42-002` | `2026-10-11` | W42-01 / PR #10 | Bổ sung seed tối thiểu cho role, publisher, game và khu vực | Script seed trong một transaction, chạy lại không trùng và giữ dữ liệu hiện có | `backend/seed.py`, `backend/tests/test_seed.py`, README, tài liệu W42 | 3 pytest đạt; cả hai migration + seed trên schema PostgreSQL tạm rỗng đạt; seed lần 2 thêm 0 bản ghi; rollback schema tạm | `VERIFIED` |
| `AI-2026-W42-004` | `2026-10-13` | W42-02 / chưa mở PR | Hoàn thiện kiểm tra role/scope, không commit; kiểm tra thêm PostgreSQL | Helper và kiểm tra quyền ghi catalog, tạo giải, quản lý đúng đội; xử lý subject JWT sai; fixture PostgreSQL tùy chọn `--postgres` | Middleware auth, routes, tests, README, tài liệu W42 | AI chạy SQLite: 58 test đạt; PostgreSQL: 55 test quyền/catalog đạt, 42 test quyền dùng JWT thật qua TestClient; hai migration + seed mỗi schema tạm, rollback và xác nhận schema biến mất. Chờ DOANH review | `APPLIED` |

### Nguyễn Quốc Doanh — `DOANH`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W42-003` | `2026-10-13` | W42-03 / PR #12 | Hoàn thiện API catalog: CRUD/list + validation cho publisher, game, competition area | Schema Pydantic, kiểm tra trùng/khóa ngoại/vòng lặp khu vực cha, chặn xóa bản ghi đang được dùng; ghi cần JWT | `backend/routes/catalog.py`, `backend/tests/test_catalog_api.py`, README, tài liệu W42 | `pytest -q`: 16 passed; cố ý gỡ kiểm tra vòng lặp và kiểm tra giải đấu thì test tương ứng fail | `VERIFIED` |
| `AI-2026-W42-004` | `2026-10-13` | W42-04 / PR #13 | Hoàn thiện nghiệp vụ tạo đội và quản lý membership, kèm kiểm tra quyền quản lý đội | Thêm/đổi vị trí/kết thúc thành viên; chỉ `MANAGER` của đội hoặc `ADMIN`; một membership `ACTIVE` mỗi người; giữ ít nhất một quản lý; audit log; sửa partial index cho SQLite | `backend/routes/team.py`, `backend/modules/teams/models.py`, `backend/tests/test_team_api.py`, README, tài liệu W42 | `pytest -q`: 26 passed; test phát hiện lỗi 500 khi thêm lại thành viên cùng ngày và đã sửa; cố ý gỡ từng kiểm tra thì test fail | `VERIFIED` |
| `AI-2026-W42-005` | `2026-10-15` | Review PR #14; W42-04 lên `main` | Review PR #14 (chạy test, đối chiếu với W42-04); đưa code W42-04 (PR #13 merge nhầm vào `feature/W42-catalog-api`) lên `main` và gỡ conflict với PR #14 | Review Request changes trên PR #14; gộp kiểm tra quyền quản lý đội vào `ensure_team_manager` trong `middleware/auth.py`, dùng chung cho thêm/đổi vị trí/kết thúc thành viên; thêm test quyền theo TEAM/ORGANIZATION cho đổi vị trí và kết thúc | `backend/middleware/auth.py`, `backend/routes/team.py`, `backend/tests/test_permissions.py`, `backend/tests/test_team_api.py`, tài liệu W42 | `pytest -q`: 71 passed (SQLite) | `APPLIED` |
| `AI-2026-W42-006` | `2026-10-17` | Review PR #18 (W42-06); cập nhật trạng thái W42-02/04/05/06 | Kiểm tra PR #18 đã ổn chưa và vì sao không merge được; cập nhật trạng thái các task đã merge sang `DONE` | AI đối chiếu diff PR #18 với API `teams`/`catalog` trên `main`: đã sửa đủ 3 điểm review, kiểu dữ liệu khớp backend; chỉ ra merge bị chặn do review Request changes còn hiệu lực và ruleset `main` cần 1 approve. DOANH approve và merge PR #18 trên giao diện GitHub. AI cập nhật bảng phân công và bằng chứng W42 từ thông tin PR #13–#18 | `docs/weeks/2026-W42.md`, `docs/AI_WORK_LOG.md` | DOANH tự xem diff và approve PR #18; AI không chạy lại build/test của PR #18 (dùng bằng chứng trong mô tả PR) | `APPLIED` |

### Nguyễn Tùng Dương — `DUONG`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W42-DUONG-001` | `2026-10-16` | [W42-05 / PR #17](https://github.com/Luong-dung/bt-csdl-web/pull/17) | Tạo giao diện đăng ký/đăng nhập và lưu JWT bằng API thật | Thêm form đăng ký, đăng nhập, lưu access token trong `localStorage`, gọi `/auth/me`, hiển thị tài khoản và đăng xuất; chỉ xóa token khi `/auth/me` trả `401/403`, giữ token khi lỗi mạng/server và hủy phản hồi cũ sau đăng xuất | `frontend/src/App.tsx`, `frontend/src/styles.css` | TypeScript không có lỗi; `npm run build` thành công | `VERIFIED` |
| `AI-2026-W42-DUONG-002` | `2026-10-17` | [W42-06 / PR #18](https://github.com/Luong-dung/bt-csdl-web/pull/18) | Tạo giao diện danh sách và tạo đội, sau đó xử lý góp ý review | Tải game và đội qua API; tạo đội có xác thực JWT; lưu form trước `await` để reset đúng; nút “Xem đội” gọi `/teams/{id}` và hiển thị chi tiết thành viên | `frontend/src/App.tsx`, `frontend/src/styles.css` | `npm run build` thành công; `backend/.venv/Scripts/python.exe -m pytest -q`: 71 passed, 1 warning; đã push commit `fb1924b` và cập nhật mô tả PR kèm bằng chứng | `VERIFIED` |
| `AI-2026-W43-DUONG-003` | `2026-10-21` | [W43-05 / PR #34](https://github.com/Luong-dung/bt-csdl-web/pull/34) | Hoàn thiện giao diện quản lý thành viên đội và xử lý góp ý review | Thêm thành viên bằng username, đổi vị trí, kết thúc membership/tự rời đội, xem lịch sử; chỉ ADMIN hoặc MANAGER ACTIVE thấy thao tác quản lý; giữ form khi API 403/409; xác nhận trước thao tác không hoàn tác; sửa lỗi refresh sau ghi | `frontend/src/App.tsx`, `frontend/src/styles.css`, `docs/weeks/2026-W43.md` | `npm run build` đạt; kiểm thử trình duyệt với API giả lập xác nhận phân quyền, giữ form khi 409 và hiển thị lỗi 422; PR #34 đã approve và merge commit `00d3eba` | `VERIFIED` |
| `AI-2026-W43-DUONG-004` | `2026-10-21` | [W43-06 / PR #35](https://github.com/Luong-dung/bt-csdl-web/pull/35) | Xây dựng giao diện quản trị catalog và xử lý góp ý về danh sách, form và lỗi tải lại | Hiển thị danh sách publisher/game/khu vực cho mọi user; chỉ ADMIN thấy form và nút ghi; CRUD qua API thật, chọn publisher/khu vực cha; giữ form khi ghi lỗi; xử lý detail validation dạng mảng; phân biệt ghi thành công nhưng GET refresh lỗi và thêm nút tải lại | `frontend/src/App.tsx`, `frontend/src/styles.css`, `docs/weeks/2026-W43.md` | `npm run build` đạt; `python -m pytest tests/test_catalog_api.py tests/test_team_api.py -q`: 23 passed, 1 warning; kiểm thử trình duyệt với API giả lập xác nhận user thường xem danh sách, 409 giữ form, 422 hiển thị rõ và GET refresh lỗi không gửi lại thao tác | `VERIFIED` |

### Đồng Đức Dương — `DUC`

| ID | Ngày | Task/PR | Nội dung đã nhờ AI | Kết quả áp dụng | File/module ảnh hưởng | Kiểm tra của người thực hiện | Trạng thái |
|---|---|---|---|---|---|---|---|
| `AI-2026-W43-DUC-001` | `2026-10-21` | [W43-07 / PR #37](https://github.com/Luong-dung/bt-csdl-web/pull/37), `feature/W43-07-playwright-e2e` | Thêm kiểm thử trình duyệt chạy lại được cho auth, tạo đội, membership và quản trị catalog, tích hợp CI | Thêm Playwright fixtures/tests, lệnh `npm run test:e2e`, hướng dẫn database demo riêng, artifacts screenshot/trace khi fail và job CI riêng dùng PostgreSQL `_test`; bổ sung bằng chứng PR/CI và hướng dẫn virtualenv. W43-07 chờ reviewer kiểm tra lại | `.github/workflows/ci.yml`, `.gitignore`, `README.md`, `docs/BROWSER_TESTING.md`, `docs/weeks/2026-W43.md`, `frontend/e2e/`, `frontend/package.json` | Local Chrome: `npm run test:e2e` — 4 passed; `npm run build` đạt. [CI run #39638654586](https://github.com/Luong-dung/bt-csdl-web/actions/runs/39638654586): Backend tests, Frontend build, Browser E2E đều passed. Reviewer DUONG (`nomkjmchi`) gửi CHANGES_REQUESTED; bằng chứng tuần cập nhật và hướng dẫn test kích hoạt đúng `backend\\.venv`. Chưa approve/merge | `APPLIED` |
| `AI-2026-W42-DUC-002` | `2026-10-17` | W42-08 / PR #22 | Chuẩn bị CI cho backend tests và frontend build trên nhánh riêng, tránh tạo lại workflow đã có | Xác nhận workflow CI đã được merge vào `main` qua PR #22; chỉ cập nhật bằng chứng và trạng thái nghiệm thu trong tài liệu, không tạo workflow trùng lặp | `docs/weeks/2026-W42.md`, `docs/AI_WORK_LOG.md` | GitHub Actions run #1 trên PR #22 và run #2 sau khi push vào `main` đều thành công; PR #22 đã merge. Chờ DUONG xác nhận review theo phân công | `APPLIED` |
| `AI-2026-W42-DUC-001` | `2026-10-17` | W42-07 / PR #23 | Bổ sung smoke tests cho auth, catalog và teams mà không ảnh hưởng code của thành viên khác | Thêm TestClient smoke tests cho auth và luồng đội; tích hợp cùng test nghiệp vụ teams, quyền, catalog và seed từ `main`; cập nhật README và bằng chứng tuần | `backend/tests/test_auth_api.py`, `backend/tests/test_team_smoke_api.py`, `README.md`, `docs/weeks/2026-W42.md` | Sau khi fast-forward tới `main` (`4c6fcb8`), chạy từ `backend`: `python -m pytest -q` — 75 passed, 1 skipped (PostgreSQL-only), 1 deprecation warning; SQLite in-memory, không cần PostgreSQL hoặc `.env` | `VERIFIED` |

## 4. Mẫu bản ghi chi tiết

Sử dụng mẫu này khi yêu cầu có ảnh hưởng lớn đến kiến trúc, database, API hoặc nhiều file:

```markdown
### AI-YYYY-Www-NGUOI-NNN — Tên ngắn của yêu cầu

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
