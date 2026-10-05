# ADR 001: Lựa Chọn Kiến Trúc Modular Monolith Và Tech Stack Cốt Lõi

- **Trạng thái (Status):** Đã chấp thuận (Accepted)
- **Ngày quyết định (Date):** 05/10/2026
- **Người tham gia quyết định (Deciders):** Nhóm phát triển nền tảng Esports (4 thành viên)
- **Tài liệu liên quan (Context Docs):** `docs/KE_HOACH_TAI_TO_CHUC_NEN_TANG_ESPORTS.md`, `docs/KE_HOACH_CONG_VIEC_TUAN_1.md`

---

## 1. Bối Cảnh (Context)

Dự án hiện tại là một MVP cơ bản:
- Backend: FastAPI gọi trực tiếp cơ sở dữ liệu qua raw SQL (`psycopg2`), chưa có tầng abstraction/ORM, chưa có migration theo phiên bản.
- Database: PostgreSQL với schema sơ khai, các bảng chưa gắn với khái niệm Nhà phát hành (Publisher), tựa game (Game), tổ chức (Organization) hay khu vực thi đấu (Competition Area).
- Frontend: Các trang HTML/JavaScript tĩnh gọi API trực tiếp, chưa có component hóa, chưa có type safety.
- Nhân lực: Đội ngũ gồm 4 thành viên.

Mục tiêu mới của sản phẩm:
- Nâng cấp thành nền tảng giải đấu eSports đa game, đa tổ chức, đa vùng thi đấu.
- Hệ thống phân quyền chặt chẽ dựa trên phạm vi (Scope-based RBAC) thay vì chỉ gán 1 role toàn cục.
- Cần một nền móng kiến trúc vững chắc, dễ phân chia công việc cho 4 người, chi phí vận hành thấp, dễ debug và sẵn sàng mở rộng mà không bị sa đà vào sự phức tạp không cần thiết (over-engineering).

---

## 2. Quyết Định (Decision)

Nhóm thống nhất đưa ra các quyết định kiến trúc và công nghệ cốt lõi như sau:

### 2.1. Kiến Trúc Ứng Dụng: Modular Monolith
- **Quyết định:** Xây dựng hệ thống dưới dạng **Modular Monolith** trên nền tảng **FastAPI**.
- **Cách tổ chức:** Toàn bộ API chạy chung trong một tiến trình (single process/deployable unit), nhưng mã nguồn backend được chia tách nghiêm ngặt thành các module độc lập theo nghiệp vụ (Domain-driven Bounded Contexts):
  - `identity`: Quản lý tài khoản, phân quyền Scope-based RBAC, audit log.
  - `catalog`: Quản lý nhà phát hành (Publisher), tựa game (Game).
  - `geo`: Quản lý khu vực thi đấu (Competition Area), quốc gia (Country).
  - `org`: Quản lý tổ chức (Organization), đội tuyển theo game (Team), hồ sơ tuyển thủ.
  - `competition`: Quản lý chuỗi giải, mùa giải, vòng đấu (Stage), nhánh đấu (Bracket), trận đấu (Match) và bảng xếp hạng (Standings).
- **Nguyên tắc giao tiếp:** Các module không truy cập trực tiếp bảng dữ liệu nội bộ của nhau mà phải đi qua Service / Repository layer công khai của từng module.

### 2.2. Cơ Sở Dữ Liệu: PostgreSQL (Single Source of Truth)
- **Quyết định:** Sử dụng duy nhất **PostgreSQL** làm cơ sở dữ liệu lưu trữ chính.
- **Quy chuẩn dữ liệu:**
  - Khóa chính sử dụng `UUID` cho các thực thể công khai (public entities) để tránh đoán ID tuần tự trên URL/API.
  - Lưu thời gian bằng `timestamptz` chuẩn UTC; múi giờ địa phương chỉ xử lý khi hiển thị hoặc theo khu vực thi đấu.
  - Tận dụng `JSONB` cho các trường metadata mở rộng (luật thi đấu đặc thù của từng game).

### 2.3. Tầng Truy Cập Dữ Liệu & Migration: SQLAlchemy 2.x + Alembic
- **Quyết định:** 
  - Sử dụng **SQLAlchemy 2.0+ (Mapped Annotations)** làm ORM quản lý mô hình dữ liệu.
  - Dùng **Alembic** để kiểm soát phiên bản schema cơ sở dữ liệu (versioned migrations).
  - **Quy định nghiêm ngặt:** Tuyệt đối loại bỏ các file SQL chứa lệnh `DROP TABLE`. Mọi thay đổi schema đều phải tạo revision migration thông qua Alembic (`alembic revision --autogenerate`).
  - Dùng **Pydantic v2** cho tầng Request/Response Schemas để tự động sinh OpenAPI contract chuẩn.

### 2.4. Frontend: React + TypeScript + Vite
- **Quyết định:** Xây dựng một Single Page Application (SPA) duy nhất bằng **React 18+, TypeScript và Vite**.
- **Lý do lựa chọn:**
  - Đảm bảo tính an toàn kiểu dữ liệu (End-to-End Type Safety) khi kết hợp cùng OpenAPI từ FastAPI.
  - Tập trung nguồn lực của đội ngũ vào một framework duy nhất; **chưa sử dụng Vue.js hay Micro-frontends** trong giai đoạn này để tránh lãng phí tài nguyên và phân tán thiết kế.
  - Sử dụng một Design System thống nhất (Tailwind CSS + Shadcn UI).

### 2.5. Môi Trường Phát Triển & Triển Khai (Deployment)
- **Local Development:** Chạy môi trường Native trực tiếp trên máy (PostgreSQL local port 5432 + Python virtual environment `venv` + Vite dev server). Không bắt buộc dùng Docker để giảm tải tài nguyên máy và tăng tốc độ setup.
- **Staging / Production:** Tận dụng các dịch vụ Cloud PaaS giá rẻ / miễn phí:
  - Database: PostgreSQL Managed trên Neon / Supabase.
  - Backend API: Deploy dạng web service trên Render / Railway.
  - Frontend: Deploy static build lên Vercel.
- **CI:** Thiết lập GitHub Actions tự động lint, typecheck và chạy unit/integration test trên mỗi Pull Request.

---

## 3. Các Phương Án Đã Cân Nhắc (Alternatives Considered)

| Phương án | Lý do không chọn |
| :--- | :--- |
| **Microservices (FastAPI tách lẻ nhiều service)** | Quá phức tạp cho nhóm 4 người trong giai đoạn đầu. Tốn kém chi phí hạ tầng, khó debug giao dịch phân tán (distributed transactions) và network latency không cần thiết. |
| **Monolith truyền thống không chia module** | Dễ dẫn đến "Spaghetti code", các thành viên dẫm chân lên nhau, khó chia ownership cho 4 người và không thể tách service độc lập sau này nếu có module cần tải cao. |
| **Dùng song song cả React và Vue** | Tạo ra sự phân mảnh lớn về UI/UX, tốn gấp đôi công sức bảo trì và viết API client cho 2 framework khác nhau. |
| **Dùng Raw SQL thuần (psycopg2) không có ORM/Alembic** | Dễ gặp lỗi SQL Injection, khó tái cấu trúc quan hệ phức tạp, việc migrate database thủ công khi làm việc nhóm rất dễ xung đột và mất dữ liệu. |

---

## 4. Hệ Quả & Đánh Đổi (Consequences)

### 4.1. Tích cực (Pros)
- **Tốc độ phát triển nhanh:** Cả nhóm có thể code và chạy thử toàn bộ hệ thống ngay trên máy cá nhân mà không gặp rào cản phức tạp.
- **Dễ bảo trì và kiểm thử:** Debug dễ dàng, toàn bộ stack có type checking chặt chẽ (Pydantic ở Backend, TypeScript ở Frontend).
- **Phân công rành mạch:** 4 người có thể phụ trách 4 domain/tầng riêng biệt (Identity, Competition, Frontend, Platform/QA) mà ít bị xung đột code.
- **Tiết kiệm chi phí:** Có thể triển khai giai đoạn Staging/Beta hoàn toàn trên hạ tầng miễn phí.
- **Khả năng mở rộng tương lai:** Khi một module có tải đột biến (ví dụ: live bracket/match updates), cấu trúc Modular Monolith cho phép bóc tách riêng module đó thành Worker/Microservice độc lập một cách dễ dàng.

### 4.2. Thách thức cần lưu ý (Cons & Mitigations)
- **Kỷ luật nhóm:** Phải tuân thủ không gọi trực tiếp model/DB xuyên module. Cần có code review chéo bắt buộc trước khi merge PR.
- **Khởi tạo ban đầu:** Cần thời gian tuần đầu tiên để dựng khung App Factory, Alembic và React shell trước khi bắt đầu viết tính năng nghiệp vụ.
