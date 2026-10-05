# Hệ Thống Tài Liệu Dự Án (Documentation)

Thư mục này chứa toàn bộ tài liệu kỹ thuật và quản lý của dự án **Esports Tournament Web**. Để tránh lộn xộn, các thành viên vui lòng tuân thủ cấu trúc lưu trữ sau:

## Cấu trúc thư mục

- 📂 **ADR/ (Architecture Decision Records)**
  - Chứa các quyết định lớn về mặt kiến trúc, công nghệ (VD: Chọn Database gì, thiết kế theo mô hình nào). Các quyết định này là "luật" của dự án, mọi người phải tuân theo.
  - *Ví dụ: `001-modular-monolith.md`*

- 📂 **sprints/**
  - Nơi lưu trữ tài liệu quản lý theo từng tuần/Sprint. Mỗi tuần sẽ có một thư mục riêng để dễ theo dõi lịch sử.
  - 📂 **sprint-1/**
    - `plan.md`: Kế hoạch công việc chi tiết chia cho 4 người.
    - `evaluation.md`: Bảng đánh giá thành viên cuối tuần của Tech Lead.
  - 📂 **sprint-2/** ...

- 📂 **api/** *(Dự kiến)*
  - Nơi lưu trữ tài liệu đặc tả API (Swagger/OpenAPI config hoặc Markdown thủ công) để Frontend và Backend dễ dàng giao tiếp.

- 📂 **setup/** *(Dự kiến)*
  - Hướng dẫn cài đặt môi trường cho người mới (cài Python, Node.js, kéo Database...).
