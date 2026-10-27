# Đăng ký đề tài nhóm – Nền tảng quản lý giải đấu Esports

## 1. Thành viên và vai trò

Nhóm gồm bốn thành viên. Mỗi thành viên phụ trách một mảng chính và review chéo Pull Request của các thành viên còn lại.

| STT | Họ và tên | MSSV | Vai trò | Phụ trách chính |
|---:|---|---:|---|---|
| 1 | Lường Tiến Dũng (nhóm trưởng) | 24001657 | Tech Lead – Dữ liệu & Định danh | Kiến trúc hệ thống, PostgreSQL, Alembic, tài khoản, phân quyền và audit log |
| 2 | Nguyễn Quốc Doanh | 24001656 | Backend – Nghiệp vụ thi đấu | Mô hình và API cho game, khu vực, tổ chức, đội tuyển và giải đấu |
| 3 | Nguyễn Tùng Dương | 24001661 | Frontend Lead | React + TypeScript, khung ứng dụng, đăng nhập và màn hình quản trị |
| 4 | Đồng Đức Dương | 24001659 | QA – DevOps | Script chạy dự án, GitHub Actions, staging và kiểm thử API bằng Postman/pytest |

## 2. Tên đề tài

**Xây dựng nền tảng quản lý giải đấu Esports đa game**  
(*Esports Tournament Management Platform*)

## 3. Bài toán và mục tiêu

Giải đấu esports thường được quản lý bằng nhiều bảng tính rời rạc. Cách làm này khó kiểm soát đội hình, kết quả, lịch thi đấu và lịch sử chuyển nhượng. Hệ thống được xây dựng để:

- Quản lý nhà phát hành, tựa game, khu vực, tổ chức, đội tuyển và tuyển thủ.
- Quản lý vòng đời giải đấu từ đăng ký, duyệt đội, khóa đội hình, thi đấu đến bảng xếp hạng.
- Lưu lịch sử thay đổi thay vì xóa dữ liệu nghiệp vụ.
- Phân quyền theo vai trò và phạm vi; ví dụ trọng tài chỉ được nhập điểm ở giải được phân công.
- Ghi nhật ký các hành động quan trọng để truy vết.

## 4. Công nghệ và kiến trúc

| Thành phần | Công nghệ |
|---|---|
| Cơ sở dữ liệu | PostgreSQL |
| Quản lý schema | SQLAlchemy 2 và Alembic |
| Backend | Python, FastAPI |
| Frontend | React, TypeScript, Vite |
| Xác thực | JWT, mật khẩu băm Argon2 |
| Kiểm thử | pytest, FastAPI TestClient, Postman |
| Quản lý mã nguồn | GitHub, feature branch, Pull Request và review chéo |

Backend dùng kiến trúc **modular monolith**. Các module dùng chung một ứng dụng và database nhưng tách rõ phạm vi:

- `modules/identity`: người dùng, vai trò, quyền và nhật ký.
- `modules/catalog`: publisher, game, quốc gia và khu vực.
- `modules/teams`: tổ chức, đội tuyển và lịch sử thành viên.
- `modules/tournaments`: giải đấu, vòng, trận, roster và standings.

## 5. Thiết kế dữ liệu

### 5.1. Tài khoản và phân quyền

- `users`: username, email, mật khẩu đã mã hóa và thông tin cá nhân.
- `roles`: nhóm công việc như quản trị viên, trọng tài hoặc quản lý đội.
- `permissions`: hành động cụ thể được phép thực hiện.
- `role_assignments`: gán vai trò theo phạm vi toàn hệ thống, tổ chức hoặc giải đấu.
- `audit_logs`: ai thực hiện hành động nào, trên tài nguyên nào và vào thời điểm nào.

### 5.2. Danh mục

- `publishers` và `games`: nhà phát hành có nhiều tựa game.
- `countries`: mã quốc gia theo ISO.
- `competition_areas`: khu vực phân cấp bằng `parent_id`, ví dụ toàn cầu → APAC → Việt Nam → TP.HCM.

### 5.3. Tổ chức và đội tuyển

- `organizations`: tổ chức esports.
- `teams`: đội thuộc một tổ chức và một game.
- `team_memberships`: lịch sử hợp đồng/thành viên, gồm vị trí, ngày vào, ngày rời và trạng thái.

### 5.4. Giải đấu

- `tournaments`: tên, game, khu vực, thể thức, thời gian và trạng thái.
- `stages`: các vòng theo thứ tự.
- W44-2-02 triển khai list/detail stage công khai, tạo/sửa/xóa/sắp thứ tự cho quản lý đúng giải khi UPCOMING; roster đã khóa vẫn cấu hình stage được. Thứ tự nguyên dương và unique trong giải; không xóa stage có match (FK RESTRICT), mutation/audit cùng transaction. Reorder gửi đủ tập ID và thực hiện nguyên tử. Chi tiết tại [W44_2_STAGES.md](./W44_2_STAGES.md).
- `matches`: hai đội, tỉ số, đội thắng và trận kế tiếp.
- `tournament_rosters`: snapshot đội hình tại thời điểm đăng ký.
- `tournament_standings`: thứ hạng, số trận, thắng/thua, điểm và tiền thưởng.

#### Nền tảng roster W44-2-01

`tournaments.roster_locked_at/by` lưu trạng thái khóa; `tournament_rosters` dùng unique `(tournament_id, user_id)`, index theo giải/đội, role PLAYER/SUBSTITUTE và `display_name` snapshot nullable cho dữ liệu cũ. FK đến user/đội dùng RESTRICT để giữ lịch sử; membership thay đổi không tự cập nhật snapshot. Migration `cb86835f3e5f` không tự khóa/backfill snapshot lịch sử; dừng khi dữ liệu cũ trùng user hoặc role không hợp lệ.

Đã có GET trạng thái khóa công khai, capability roster theo giải/đội và helper transaction/khóa dùng chung. Sau khóa roster, chặn tạo đơn và duyệt APPROVED; khi giải còn UPCOMING vẫn cho quản lý đúng đội hủy và quản lý đúng giải từ chối đơn PENDING, không thay tập đội APPROVED. Capability tách `can_review_registrations` và `can_approve_registrations`; UI giữ thao tác xử lý đơn đang chờ. W44-2-03 thêm `GET/PUT .../teams/{team_id}/roster`: quản lý đúng đội APPROVED thay toàn bộ roster nháp trong một transaction khi UPCOMING và chưa khóa, chỉ chọn membership ACTIVE PLAYER/SUBSTITUTE với vai trò khớp, audit cùng commit; nháp chỉ quản lý đúng đội/giải xem, sau khóa công khai. Thao tác khóa/bắt đầu giải theo điều kiện mới thuộc W44-2-04, chưa ghi nhận đã có. Schema, quyền, request/response và hướng dẫn bàn giao tại [W44_2_ROSTER_FOUNDATION.md](./W44_2_ROSTER_FOUNDATION.md).

#### Vòng đời và quyền sửa giải đấu

| Trạng thái | Được chuyển sang | Sửa thông tin (`PATCH`) |
|---|---|---|
| `UPCOMING` (mặc định) | `ONGOING`, `CANCELLED` | Mọi trường |
| `ONGOING` | `COMPLETED`, `CANCELLED` | Chỉ `name`, `description`, `end_date` |
| `COMPLETED` | — | Không, trả 409 |
| `CANCELLED` | — | Không, trả 409 |

- Chuyển trạng thái qua `POST /api/v1/tournaments/{tournament_id}/status`; `PATCH` không nhận `status`. Chuyển sai trạng thái hoặc sửa trường bị khóa trả 409.
- Ngày bắt đầu không được ở quá khứ khi tạo giải hoặc khi đổi ngày bắt đầu; ngày kết thúc không trước ngày bắt đầu. Database có CHECK `ck_tournaments_status` và `ck_tournaments_dates`.
- Quyền sửa và chuyển trạng thái: ADMIN; ORGANIZER đã tạo giải (`created_by`) và vẫn còn vai trò ORGANIZER; ORGANIZER được gán phạm vi `TOURNAMENT` của giải đó. Người khác trả 403, chưa đăng nhập trả 401. Giải cũ không có `created_by` chỉ ADMIN sửa được.

## 6. Kỹ thuật cơ sở dữ liệu

- Khóa ngoại tự tham chiếu `matches.next_match_id` biểu diễn nhánh đấu loại trực tiếp.
- Partial unique index bảo đảm một tuyển thủ chỉ có một membership `ACTIVE` tại một thời điểm.
- Membership được chuyển trạng thái thay vì xóa để giữ lịch sử chuyển nhượng.
- Roster được snapshot theo từng giải để lịch sử không thay đổi khi tuyển thủ chuyển đội.
- Ghi kết quả trận và cập nhật bảng xếp hạng trong cùng transaction.

### Audit thao tác ghi giải đấu

- Tạo, cập nhật và chuyển trạng thái giải ghi vào `audit_logs` với action tương ứng `TOURNAMENT_CREATED`, `TOURNAMENT_UPDATED`, `TOURNAMENT_STATUS_CHANGED`; resource là `tournament`, actor là `user_id` đang đăng nhập.
- `details` chứa `tournament_id`, `before` và `after`. Cập nhật lưu các trường được gửi; chuyển trạng thái lưu trạng thái cũ/mới; tạo lưu dữ liệu đầu vào đã chuẩn hóa, trạng thái ban đầu và người tạo. Ngày được lưu dạng ISO.
- Helper `core/audit.py` chỉ thêm log vào session. Dữ liệu giải và log commit cùng transaction; lỗi ghi một trong hai sẽ rollback, request bị từ chối không ghi log thành công. Dùng bảng hiện có, không cần migration mới.

Schema triển khai nằm tại [database/schema_postgres.sql](../database/schema_postgres.sql); migration nằm tại [backend/alembic/versions/53bbc0801b4f_identity_module.py](../backend/alembic/versions/53bbc0801b4f_identity_module.py).

## 7. Chức năng chính

1. Đăng ký, đăng nhập bằng JWT và xem thông tin tài khoản.
2. Phân quyền theo vai trò và phạm vi.
3. Quản lý game, nhà phát hành, khu vực và tổ chức.
4. Tạo đội, quản lý thành viên, đổi vị trí và kết thúc membership.
5. Tạo giải đấu, quản lý stage, match, roster và standings.
6. Ghi audit log cho đổi quyền, sửa đội hình và nhập kết quả.
7. Frontend quản trị hiển thị danh sách giải đấu và kết nối API v1.

## 8. API hiện có

| Nhóm | Endpoint |
|---|---|
| Identity | `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me` |
| Teams | `/api/v1/teams`, `/api/v1/teams/{team_id}`, `/api/v1/teams/{team_id}/members` |
| Catalog | `/api/v1/catalog/games`, `/api/v1/catalog/publishers`, `/api/v1/catalog/areas` |
| Tournaments | `/api/v1/tournaments`, `/api/v1/tournaments/{tournament_id}`, `/api/v1/tournaments/{tournament_id}/status` |
| Roster foundation | `GET /api/v1/tournaments/{tournament_id}/roster-lock`, `GET /api/v1/tournaments/{tournament_id}/teams/{team_id}/roster/capabilities`, `GET/PUT /api/v1/tournaments/{tournament_id}/teams/{team_id}/roster`; capability giải thêm `roster_locked`, `can_lock_roster`, `can_approve_registrations` |
| Stage | `GET/POST /api/v1/tournaments/{tournament_id}/stages`, `GET/PATCH/DELETE .../stages/{stage_id}`, `PUT .../stages/order`; capability giải thêm `can_manage_stages` |
| Vận hành | `/health`, `/ready`, `/docs` |

## 9. Tiến độ

### Đã hoàn thành

- Khung modular monolith cho FastAPI.
- Cấu hình PostgreSQL, SQLAlchemy và Alembic.
- Mô hình dữ liệu cho identity, catalog, teams và tournaments.
- API nền tảng cho authentication, teams, catalog và tournaments.
- Frontend React + TypeScript + Vite.
- Schema PostgreSQL và partial index cho membership đang hoạt động.

### Đang thực hiện

- Hoàn thiện role assignment theo scope ở các endpoint nghiệp vụ.
- Bổ sung API đăng ký/duyệt đội, khóa roster, nhập kết quả và standings.
- Thêm audit service dùng chung.
- Bổ sung test API, seed dữ liệu và CI GitHub Actions.

## 10. Lộ trình 10 tuần

| Giai đoạn | Tuần | Kết quả |
|---|---:|---|
| Nền tảng | 1–2 | App factory, cấu hình, PostgreSQL, migration, identity và audit |
| Danh mục & đội | 3–4 | Game, khu vực, tổ chức, đội và lịch sử membership |
| Nghiệp vụ giải | 5–7 | Đăng ký, duyệt, roster, stage, match, kết quả và standings |
| Hoàn thiện | 8–10 | Frontend quản trị, kiểm thử, CI, staging và tài liệu bàn giao |

Phân công chi tiết theo từng tuần, trạng thái công việc, tiêu chí nghiệm thu và bảng đánh giá thành viên được quản lý tại [TEAM_WORK_PLAN.md](./TEAM_WORK_PLAN.md).

## 11. Quy trình phát triển

```text
main
 └── feature/<ten-tinh-nang>
```

1. Tạo feature branch từ `main`.
2. Cập nhật migration nếu thay đổi schema.
3. Viết test cho hành vi mới.
4. Mở Pull Request và nhờ thành viên khác review.
5. Chỉ merge khi CI và review đã đạt.
