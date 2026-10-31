# Kế hoạch làm việc và đánh giá theo tuần

Tài liệu này là bảng điều hành chính của nhóm trong 10 tuần. Nhóm trưởng cập nhật trực tiếp sau buổi họp tuần và dùng nội dung đã ghi để đánh giá tiến độ.

## 1. Cách sử dụng

Mỗi tuần phải có đủ bốn phần:

1. **Kế hoạch:** việc cần làm, người phụ trách, người review và đầu ra.
2. **Thực hiện:** cập nhật trạng thái và liên kết Pull Request/commit.
3. **Nghiệm thu:** kiểm tra code, test, tài liệu và demo.
4. **Đánh giá:** chấm điểm, ghi trở ngại và điều chỉnh kế hoạch tuần sau.

### Trạng thái công việc

| Trạng thái | Ý nghĩa |
|---|---|
| `TODO` | Chưa bắt đầu |
| `IN PROGRESS` | Đang thực hiện |
| `BLOCKED` | Bị chặn, phải ghi rõ nguyên nhân |
| `REVIEW` | Đã mở Pull Request, chờ review |
| `DONE` | Đã nghiệm thu |

### Quy tắc phân công

- Mỗi việc có **một người chịu trách nhiệm chính**.
- Mỗi Pull Request có ít nhất **một người review khác**.
- Không đánh dấu `DONE` nếu chưa có test hoặc bằng chứng kiểm tra phù hợp.
- Việc chưa hoàn thành phải được chuyển sang tuần sau, không xóa khỏi lịch sử.
- Nhóm trưởng chịu trách nhiệm cập nhật phần đánh giá; người phụ trách cập nhật trạng thái và link PR.
- Nếu task có dùng AI, ghi lại yêu cầu và bằng chứng kiểm tra trong [AI_WORK_LOG.md](./AI_WORK_LOG.md).

## Tuần đang thực hiện

Kế hoạch chi tiết của tuần hiện tại được tách riêng để dễ cập nhật và giữ lịch sử:

- [2026-W42 — 12/10/2026 đến 18/10/2026](./weeks/2026-W42.md)
- [2026-W43 — Tuần 2, 19/10/2026 đến 25/10/2026](./weeks/2026-W43.md): cập nhật 23/10/2026, `8/8 DONE`, `0 IN PROGRESS`, `0 TODO`; backend/PostgreSQL, frontend build và kiểm thử trình duyệt đạt. Chi tiết bằng chứng và giới hạn xác minh CI/review ghi trong W43.

- [2026-W44 — Tuần 3, 26/10/2026 đến 01/11/2026](./weeks/2026-W44.md): chốt sớm ngày 26/10/2026, **`8/8 DONE`, `0 IN PROGRESS`, `0 TODO`**; cả 8 task đã review/merge, CI và nghiệm thu local đạt. Hoàn thành UI giải, capability và đăng ký/duyệt đội. [Đánh giá từng người](./weeks/2026-W44.md#6-đánh-giá-cuối-tuần): DUNG 4,8; DOANH 4,8; DUONG 4,5; DUC 4,7 (điểm đề xuất trên thang 5).

- [W44(2) — 27/10/2026 đến 01/11/2026](./weeks/2026-W44-2.md): đợt tiếp theo trong tuần lịch `2026-W44`; cập nhật 31/10: `3/8 DONE`, `3 REVIEW`, `2 IN PROGRESS`, `0 TODO` (W44-2-01/-05/-06 DONE; -02/-03/-04 chờ DUNG chốt; -07 đã merge PR #71, chờ nghiệm thu; DUC đang làm -08, bổ sung Browser E2E cho snapshot sau đổi membership, assignment scope và phân trang hơn 50 bản ghi). Mỗi người hai task: DUNG nền tảng roster/stage, DOANH API roster/khóa và bắt đầu giải, DUONG UI roster/stage và danh sách lớn, DUC integration/E2E. Mã task dùng `W44-2-01`…`W44-2-08`, không trùng W44 đã chốt; xem [bằng chứng và trạng thái chi tiết](./weeks/2026-W44-2.md).

W42 và W43 đã hoàn thành; W43 chốt `8/8 DONE` ngày 23/10. W44 là tuần hiện tại (26/10–01/11), đã chốt sớm `8/8 DONE` ngày 26/10 theo yêu cầu nhóm trưởng. Đợt tiếp theo dùng tên nội bộ W44(2), thực hiện 27/10–01/11 trong cùng tuần lịch W44 theo phụ thuộc trong kế hoạch. “Tuần 2/3” trong file W43/W44 là tuần triển khai thực tế của nhóm; các mục tuần 1–10 bên dưới là lộ trình theo giai đoạn, có thể được thực hiện sớm hoặc điều chỉnh qua bảng tuần lịch.

### Tiến độ đối chiếu W42 — 18/10/2026

Đánh giá cuối tuần 1, điểm đề xuất từng thành viên và nhận xét quy trình được ghi tại [mục 5 của W42](./weeks/2026-W42.md#5-đánh-giá-cuối-tuần). Chưa ghi nhận buổi họp chốt điểm.

Trạng thái đối chiếu GitHub ngày 18/10/2026 và [W42](./weeks/2026-W42.md): **8/8 DONE, 0 REVIEW**; cả 8 việc đã có code merge. W42-05 đã được Luong-dung approve trên PR #17 sau review. Các bảng trong lộ trình 10 tuần bên dưới mô tả phạm vi dự kiến; những dòng chưa đồng bộ phải đối chiếu W42 trước khi dùng để báo cáo tiến độ.

| Phạm vi | Tiến độ W42 | Đầu ra thực tế |
|---|---|---|
| Seed | W42-01 `DONE` | Dữ liệu nền role, publisher, game và khu vực |
| Phân quyền | W42-02 `DONE` | Helper role/scope và test; PR #21 sửa fixture đã approve, merge, CI đạt |
| Catalog | W42-03 `DONE` | CRUD/list API; chưa có màn hình quản trị catalog |
| Đội và membership | W42-04 `DONE` | API tạo đội, thêm/đổi/kết thúc thành viên; chưa có UI quản lý thành viên |
| Auth UI | W42-05 `DONE` | Đăng ký, đăng nhập, đăng xuất và lưu JWT; PR #17 đã approve |
| Team UI | W42-06 `DONE` | Danh sách, chi tiết và tạo đội |
| Smoke tests | W42-07 `DONE` | PR #23 được Luong-dung approve và merge; CI đạt |
| CI | W42-08 `DONE` | PR #24 được nomkjmchi approve và merge; CI đạt |

Hoàn thành API không đồng nghĩa đã có giao diện thao tác. Luồng tạo/đăng ký giải, roster, lịch đấu, kết quả và standings vẫn thuộc phạm vi phát triển tiếp.

## 2. Ma trận phụ trách và review

| Mã | Thành viên | Phụ trách chính | Review ưu tiên |
|---|---|---|---|
| `DUNG` | Lường Tiến Dũng | Kiến trúc, database, Alembic, identity, phân quyền, audit | DƯƠNG, DOANH |
| `DOANH` | Nguyễn Quốc Doanh | Catalog, teams, tournaments, nghiệp vụ thi đấu | DUNG, ĐỨC |
| `DUONG` | Nguyễn Tùng Dương | React, TypeScript, auth UI, màn hình quản trị | DOANH, DUNG |
| `DUC` | Đồng Đức Dương | Test, CI, script chạy, staging, kiểm thử hồi quy | DUONG, DUNG |

## 3. Tiêu chuẩn nghiệm thu chung

Một đầu việc chỉ được nghiệm thu khi:

- Code nằm đúng module và không phá vỡ API hiện có.
- Có test hoặc lệnh kiểm tra tái hiện được kết quả.
- Migration được tạo bằng Alembic nếu có thay đổi database.
- Có cập nhật tài liệu khi thay đổi API, schema hoặc quy trình.
- Pull Request đã được review và CI đạt.
- Demo được trong môi trường local hoặc staging.

## 4. Lịch 10 tuần

### Tuần 1 — Khởi tạo và thống nhất quy trình

**Mục tiêu:** mọi thành viên chạy được project và thống nhất cách làm việc.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W01-01 | Chốt kiến trúc module và quy ước branch/PR | `DUNG` | `DOANH` | ADR, quy ước branch | `DONE` |
| W01-02 | Chuẩn hóa `.env`, requirements và lệnh chạy backend | `DUC` | `DUNG` | README, script setup | `DONE` |
| W01-03 | Dựng React/Vite shell và cấu trúc giao diện | `DUONG` | `DUC` | Frontend build được | `DONE` |
| W01-04 | Tạo database local và migration đầu tiên | `DUNG` | `DUC` | PostgreSQL + Alembic head | `DONE` |

**Nghiệm thu tuần:** backend `/health`, frontend build và database migration chạy được trên máy thành viên mới.

### Tuần 2 — Identity, JWT và audit

**Mục tiêu:** hoàn thiện nền tảng tài khoản và xác thực.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W02-01 | API đăng ký, đăng nhập, `/me` | `DUNG` | `DUC` | Auth API + test | `DONE` |
| W02-02 | Màn hình đăng nhập/đăng ký và lưu session | `DUONG` | `DUNG` | Auth UI (W42-05) | `DONE` |
| W02-03 | Thiết kế role, permission, role assignment | `DUNG` | `DOANH` | Migration + model | `DONE` |
| W02-04 | Test token hết hạn, token sai và dữ liệu trùng | `DUC` | `DUNG` | Test report (W42-02/W42-07) | `DONE` |

**Nghiệm thu tuần:** đăng ký → đăng nhập → gọi endpoint bảo vệ thành công; lỗi xác thực trả đúng HTTP status.

### Tuần 3 — Catalog game và khu vực

**Mục tiêu:** có danh mục dùng chung cho các nghiệp vụ phía sau.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W03-01 | CRUD publisher và game | `DOANH` | `DUNG` | Catalog API (W42-03) | `DONE` |
| W03-02 | Country và competition area phân cấp | `DOANH` | `DUNG` | API khu vực đã DONE trong W42-03; phần country chưa nghiệm thu riêng | `IN PROGRESS` |
| W03-03 | Seed dữ liệu game/khu vực tối thiểu | `DUNG` | `DUC` | Seed script (W42-01) | `DONE` |
| W03-04 | Kiểm thử ràng buộc unique và parent area | `DUC` | `DOANH` | API tests (W42-03) | `DONE` |

**Nghiệm thu tuần:** tạo được game, gắn publisher và truy vấn được cây khu vực.

### Tuần 4 — Tổ chức, đội tuyển và membership

**Mục tiêu:** quản lý đội và giữ được lịch sử chuyển nhượng.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W04-01 | CRUD organization/team | `DOANH` | `DUNG` | Teams API | `IN PROGRESS` |
| W04-02 | Thêm, đổi vị trí, kết thúc membership | `DOANH` | `DUC` | Membership API (W42-04) | `DONE` |
| W04-03 | Partial unique index membership ACTIVE | `DUNG` | `DOANH` | Migration + test | `DONE` |
| W04-04 | Màn hình danh sách và chi tiết đội | `DUONG` | `DOANH` | Team UI (W42-06) | `DONE` |

**Nghiệm thu tuần:** một tuyển thủ không thể active ở hai đội; membership cũ vẫn còn sau khi rời đội.

### Tuần 5 — Tạo và đăng ký giải đấu

**Mục tiêu:** tạo giải và đăng ký đội tham gia.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W05-01 | CRUD tournament và trạng thái vòng đời | `DOANH` | `DUNG` | Đã tạo/list/chi tiết/cập nhật/chuyển trạng thái (W43, W44-04); chưa có xóa giải | `IN PROGRESS` |
| W05-02 | API đăng ký, duyệt và từ chối đội | `DOANH` | `DUC` | Registration flow (W44-02/03/04; DUNG cùng triển khai) | `DONE` |
| W05-03 | Form tạo giải và danh sách giải | `DUONG` | `DOANH` | Tournament UI (W44-05/06) | `DONE` |
| W05-04 | Test quyền owner/admin và dữ liệu không hợp lệ | `DUC` | `DUNG` | Test/CI và nghiệm thu W44-07/08, kế thừa test nghiệp vụ | `DONE` |

**Nghiệm thu tuần:** người có quyền tạo giải; đội không hợp lệ không thể đăng ký.

### Tuần 6 — Khóa roster và stage

**Mục tiêu:** snapshot đội hình và cấu hình các vòng đấu.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W06-01 | Snapshot tournament roster | `DOANH` | `DUNG` | Roster service/API | `TODO` |
| W06-02 | Khóa roster theo trạng thái giải | `DOANH` | `DUC` | Business rules | `TODO` |
| W06-03 | CRUD stage và thứ tự stage | `DUNG` | `DOANH` | Migration/API | `TODO` |
| W06-04 | Giao diện khóa đội hình | `DUONG` | `DUNG` | Roster UI | `TODO` |

**Nghiệm thu tuần:** thay đổi membership sau khi khóa giải không làm thay đổi roster snapshot.

### Tuần 7 — Match, bracket và standings

**Mục tiêu:** quản lý thi đấu từ lịch đến kết quả.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W07-01 | Tạo stage/match và nhánh đấu | `DOANH` | `DUNG` | Match API | `TODO` |
| W07-02 | Nhập kết quả trong transaction | `DUNG` | `DOANH` | Result service | `TODO` |
| W07-03 | Tính standings và cập nhật đội thắng | `DOANH` | `DUC` | Standings API | `TODO` |
| W07-04 | Hiển thị bracket và bảng xếp hạng | `DUONG` | `DOANH` | Competition UI | `TODO` |

**Nghiệm thu tuần:** nhập một kết quả cập nhật match và standings đồng nhất; dữ liệu lỗi được rollback.

### Tuần 8 — Phân quyền theo scope và audit

**Mục tiêu:** bảo đảm đúng người, đúng phạm vi, đúng nhật ký.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W08-01 | Middleware/checker cho role assignment | `DUNG` | `DOANH` | Scope authorization (W42-02) | `DONE` |
| W08-02 | Giới hạn trọng tài theo tournament scope | `DUNG` | `DUC` | Permission tests | `TODO` |
| W08-03 | Ghi audit cho đổi quyền và nhập điểm | `DUNG` | `DUC` | Audit service | `TODO` |
| W08-04 | Hiển thị lỗi quyền trong frontend | `DUONG` | `DUNG` | Capability và lỗi quyền cho catalog/đội/giải/đơn (W44-05/06) | `DONE` |

**Nghiệm thu tuần:** user chỉ sửa được tài nguyên trong scope được cấp; audit log có actor, action, resource và thời gian.

### Tuần 9 — Kiểm thử, CI và staging

**Mục tiêu:** tự động hóa kiểm tra và chuẩn bị demo ổn định.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W09-01 | Viết integration test cho flow chính | `DUC` | `DUNG` | Auth/catalog/teams đã có test W42-07; còn các luồng giải đấu | `IN PROGRESS` |
| W09-02 | GitHub Actions lint/typecheck/test/build | `DUC` | `DUONG` | Test/typecheck/build đã đạt W42-08; chưa có bước lint riêng | `IN PROGRESS` |
| W09-03 | Seed dữ liệu demo đầy đủ | `DUNG` | `DOANH` | Seed + reset guide | `TODO` |
| W09-04 | Hoàn thiện dashboard quản trị | `DUONG` | `DUC` | Admin UI | `TODO` |

**Nghiệm thu tuần:** Pull Request mới phải chạy CI; một thành viên mới có thể dựng môi trường theo README.

### Tuần 10 — Ổn định, demo và bàn giao

**Mục tiêu:** chốt sản phẩm, tài liệu và đánh giá thành viên.

| ID | Công việc | Phụ trách | Review | Đầu ra | Trạng thái |
|---|---|---|---|---|---|
| W10-01 | Regression test và sửa lỗi ưu tiên cao | `DUC` | Cả nhóm | Test report | `TODO` |
| W10-02 | Kiểm tra migration, backup và staging | `DUNG` | `DUC` | Release checklist | `TODO` |
| W10-03 | Hoàn thiện demo flow và slide | `DUONG` | Cả nhóm | Demo script | `TODO` |
| W10-04 | Tổng hợp báo cáo, đóng việc và đánh giá | `DUNG` | Cả nhóm | Báo cáo cuối kỳ | `TODO` |

**Nghiệm thu tuần:** demo được flow đăng nhập → tạo đội → tạo giải → đăng ký roster → nhập kết quả → xem standings.

## 5. Mẫu đánh giá cuối mỗi tuần

Sao chép mẫu này xuống cuối tài liệu sau mỗi tuần. Không sửa các đánh giá đã chốt; nếu cần điều chỉnh, thêm mục “Cập nhật”.

### Đánh giá tuần __

- **Thời gian họp:** `YYYY-MM-DD`
- **Người ghi:** `DUNG`
- **Mục tiêu tuần:** 
- **Tổng số việc:** `__`
- **DONE:** `__`
- **REVIEW/BLOCKED:** `__`
- **Tỷ lệ hoàn thành:** `__%`
- **PR đã merge:** 
- **Demo/test evidence:** 

| Thành viên | Việc hoàn thành | Điểm đóng góp (0–5) | Chất lượng (0–5) | Review/hỗ trợ (0–5) | Tổng | Nhận xét |
|---|---|---:|---:|---:|---:|---|
| Lường Tiến Dũng |  |  |  |  |  |  |
| Nguyễn Quốc Doanh |  |  |  |  |  |  |
| Nguyễn Tùng Dương |  |  |  |  |  |  |
| Đồng Đức Dương |  |  |  |  |  |  |

**Cách tính điểm:** `Tổng = (Đóng góp + Chất lượng + Review/hỗ trợ) / 3`, làm tròn một chữ số thập phân.

**Việc chưa hoàn thành và nguyên nhân:**

| ID | Nguyên nhân | Người xử lý tiếp | Hạn mới |
|---|---|---|---|
|  |  |  |  |

**Quyết định cho tuần sau:**

- 

**Cập nhật sau cuộc họp (nếu có):**

- 

## 6. Đánh giá cuối kỳ

| Tiêu chí | Trọng số | Bằng chứng |
|---|---:|---|
| Hoàn thành đầu việc được giao | 35% | Bảng công việc và PR đã merge |
| Chất lượng code/sản phẩm | 25% | Test, review, lỗi hồi quy |
| Đóng góp review và hỗ trợ nhóm | 20% | Review comment, xử lý blocker |
| Tài liệu, demo và báo cáo | 10% | Tài liệu cập nhật, demo |
| Tuân thủ quy trình Git/CI | 10% | Branch, PR, CI result |

Điểm cuối kỳ của mỗi thành viên là trung bình có trọng số của các tiêu chí trên, dựa trên bằng chứng trong tài liệu, GitHub và CI; không đánh giá chỉ dựa trên số dòng code.
