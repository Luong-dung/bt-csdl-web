# 📋 Kế Hoạch Công Việc Sprint 1 (Tuần 1: Chốt Thiết Kế & Nền Móng)

> **Dự án:** Esports Tournament Web Platform  
> **Thời gian:** 05/10/2026 – 11/10/2026  
> **Tài liệu tham chiếu:** `docs/KE_HOACH_TAI_TO_CHUC_NEN_TANG_ESPORTS.md`  
> **Đặc tả môi trường:** Không sử dụng Docker. Chạy môi trường Native (PostgreSQL cục bộ + Python `venv` + React Vite).

---

## 🎯 1. Mục Tiêu Sprint (Sprint Goal)
- Thống nhất mô hình nghiệp vụ, thuật ngữ (glossary) và ERD v1.
- Chuyển giao diện sang dự án **React + TypeScript (Vite)** chuẩn chỉnh (thay thế web HTML tĩnh).
- Chuẩn hóa backend **FastAPI** với **SQLAlchemy 2.x + Alembic** (bỏ hoàn toàn file SQL chạy lại từ đầu).
- Thiết lập kịch bản tự động hóa (scripts chạy nhanh 1-lệnh, CI GitHub Actions, database staging cloud).

---

## 👥 2. Phân Công Chi Tiết Từng Thành Viên

### 👑 Dũng: Tech Lead / Data & Identity
*Trách nhiệm chính: Kiến trúc hệ thống, PostgreSQL, Alembic, Account/RBAC/Audit, chuẩn hóa FastAPI.*

- [ ] **Họp Kick-off (Toàn đội - 90 phút):** Chủ trì chốt Glossary, thống nhất phạm vi MVP (1 game mẫu, 1 format giải, 1 luồng roster).
- [ ] **Tài liệu kiến trúc (ADR):** Tạo file `docs/ADR/001-modular-monolith.md` ghi lại các quyết định kỹ thuật đã chốt.
- [ ] **Tái cấu trúc FastAPI:**
  - Chuyển cấu trúc backend sang mô hình App Factory.
  - Quản lý cấu hình bằng `pydantic-settings` đọc từ `.env`.
  - Cấu hình logging tập trung và thêm endpoints `/health`, `/ready`.
- [ ] **Khởi tạo Alembic & SQLAlchemy 2.x:**
  - Thiết lập Alembic baseline trên PostgreSQL.
  - Thiết kế models và migration ban đầu cho module **Identity** (`users`, `roles`, `permissions`, `role_assignments` theo scope, `audit_logs`).
  - Viết policy/dependency kiểm tra quyền theo scope (RBAC).
- [ ] **Review chéo:** Review PR migrations module Catalog của Người 2 và PR scripts của Người 4.

**📦 Sản phẩm bàn giao (Deliverables):**
- Tài liệu ADR 001.
- Core FastAPI App Factory chạy mượt mà.
- Migration Alembic module Identity.

---

### ⚔️ Doanh: Backend Competition
*Trách nhiệm chính: Data Modeling, Modules Catalog (Publisher/Game), Geo (Area/Country), Org (Organization/Team).*

- [ ] **Chốt ERD v1:** Phối hợp cùng Người 1 hoàn thiện lược đồ dữ liệu và quy ước đặt tên endpoint OpenAPI.
- [ ] **Xây dựng Models & Migrations:**
  - **Catalog:** Bảng `publishers`, `games`.
  - **Geo:** Bảng `competition_areas`, `countries`.
  - **Org:** Bảng `organizations`, `teams` (gắn chặt với game cụ thể), `team_memberships` / `player_profiles`.
- [ ] **Viết API CRUD cơ bản:**
  - Viết Pydantic schemas (request validation và response serialization).
  - Viết API endpoints: Quản lý Publisher $\rightarrow$ Game; Quản lý Organization $\rightarrow$ Teams trực thuộc.
- [ ] **Kế hoạch chuyển đổi dữ liệu cũ (Legacy Migration):**
  - Viết script dry-run và bảng ánh xạ (mapping report) chuyển 9 đội tuyển và 60 người dùng hiện có sang schema mới.
- [ ] **Review chéo:** Review API Client contract của Người 3.

**📦 Sản phẩm bàn giao (Deliverables):**
- Migration và API CRUD cho Catalog, Geo, Organization.
- File OpenAPI specs chuẩn hóa.
- Script mapping dữ liệu cũ an toàn.

---

### 🎨 T. Dương: Frontend Lead
*Trách nhiệm chính: Chuyển đổi sang React + TypeScript, Design System, App Shell, Typed API Client.*

- [ ] **Khởi tạo dự án React:**
  - Dựng thư mục `frontend` mới dùng React + TypeScript + Vite.
  - Cấu hình Path Alias (`@/components`, `@/api`...), ESlint, Prettier.
- [ ] **Dựng App Shell & Design System:**
  - Cài đặt Tailwind CSS + bộ component tối thiểu (Shadcn UI hoặc Ant Design).
  - Dựng khung Layout chuẩn: Header, Sidebar, các component trạng thái `Loading`, `Error`, `Empty State`.
- [ ] **Luồng Auth & Quản lý phiên:**
  - Xây dựng Auth Context (Đăng nhập, Đăng xuất, lưu trữ token an toàn, Route Guard bảo vệ trang quản trị).
- [ ] **Tích hợp Typed API Client:**
  - Tạo API wrapper có type-safe tự động đồng bộ từ OpenAPI của Backend.
- [ ] **Dựng khung giao diện Quản trị ban đầu:**
  - Xây dựng trang danh sách và form tạo Game, Khu vực, Đội tuyển (kết nối thử API của Người 2).

**📦 Sản phẩm bàn giao (Deliverables):**
- Khung dự án React TS chạy tốt lệnh `npm run dev`.
- Màn hình Đăng nhập và App Shell hoàn chỉnh.
- Bộ API client có type-safe.

---

### 🛠️ Đ Dương: Platform QA / Automation / DevOps
*Trách nhiệm chính: Tự động hóa Local không Docker, CI GitHub Actions, Staging Cloud, Bộ Test API.*

- [ ] **Script 1-Click khởi động Local (Không Docker):**
  - Viết script `setup-dev.ps1` (hoặc `.bat`): tự động tạo `venv`, cài `requirements.txt`, và `npm install`.
  - Viết script `start-dev.ps1`: tự động mở song song cả Backend (`uvicorn`) và Frontend (`npm run dev`).
  - Chuẩn hóa file mẫu `.env.example` và `frontend/.env.example`.
- [ ] **Tài liệu hướng dẫn cài đặt (`docs/LOCAL_SETUP.md`):**
  - Viết hướng dẫn 3 bước cho thành viên mới (cài Postgres $\rightarrow$ chạy script setup $\rightarrow$ chạy script start).
- [ ] **Thiết lập CI/CD (GitHub Actions):**
  - Tạo pipeline `.github/workflows/ci.yml`: tự động chạy Linting $\rightarrow$ Typecheck $\rightarrow$ Test $\rightarrow$ Build Frontend/Backend khi có Pull Request (CI chạy Postgres service container miễn phí trên cloud).
- [ ] **Tạo môi trường Staging Cloud miễn phí (PaaS):**
  - Tạo database PostgreSQL staging trên **Neon** hoặc **Supabase**.
  - Kết nối Backend lên **Render** / **Railway** (chạy native Python command).
  - Kết nối Frontend lên **Vercel** (tự động build từ repo GitHub).
- [ ] **Bộ Test API tự động:**
  - Viết test case cơ bản bằng `pytest` hoặc export file **Postman / Thunder Client Collection** dùng chung cho nhóm.

**📦 Sản phẩm bàn giao (Deliverables):**
- Bộ scripts `setup-dev` và `start-dev` chạy 1 lệnh.
- GitHub Actions CI xanh.
- Link Staging online test được `/health`.
- Tài liệu `docs/LOCAL_SETUP.md`.

---

## 🔄 3. Quy Trình Làm Việc Hàng Ngày

1. **Quy tắc nhánh (Branching):**
   - Nhánh chính: `main` (chỉ merge khi CI xanh và có review).
   - Nhánh tính năng: `feature/<ten-nguoi>-<ten-task>`, ví dụ: `feature/nguoi2-catalog-api`.
2. **Quy tắc Commit:** Dùng chuẩn ngắn gọn:
   - `feat: ...` (tính năng mới)
   - `fix: ...` (sửa lỗi)
   - `docs: ...` (tài liệu)
   - `refactor: ...` (tái cấu trúc code)
3. **Quy tắc Review PR:**
   - Người 1 review Schema / Database / Bảo mật.
   - Người 3 review Ảnh hưởng UI / API Contract.
   - Người 4 kiểm tra CI / Build / Script.
   - *Không ai được tự bấm Merge PR của chính mình.*

---

## 🏁 4. Tiêu Chí Nghiệm Thu Cuối Tuần (Definition of Done)

Vào buổi họp review cuối tuần, cả nhóm cần kiểm tra đạt đủ các tiêu chí:

| STT | Tiêu chí nghiệm thu | Trạng thái |
| :---: | :--- | :---: |
| 1 | Clone repo về máy mới $\rightarrow$ Chạy script `start-dev` là lên cả Frontend + Backend. | ⏳ |
| 2 | Toàn bộ schema mới chạy qua lệnh `alembic upgrade head`, không còn `DROP TABLE`. | ⏳ |
| 3 | Frontend React TS mở lên đăng nhập được với tài khoản test (`123456`). | ⏳ |
| 4 | Mọi Pull Request tạo trên GitHub đều được GitHub Actions kiểm tra tự động và pass xanh. | ⏳ |
| 5 | Có đường link Staging online kiểm tra được endpoint `/health`. | ⏳ |
