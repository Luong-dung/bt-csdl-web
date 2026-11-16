# ADR 002: Chatbot Tra Cứu Giải Đấu (Tùy Chọn, Làm Khi Còn Thời Gian)

- **Trạng thái (Status):** Đề xuất (Proposed) — **tùy chọn**, không thuộc phạm vi bắt buộc
- **Ngày đề xuất (Date):** 16/11/2026
- **Người đề xuất (Proposer):** Lường Tiến Dũng (`DUNG`)
- **Hạn nộp sản phẩm:** **04/01/2027**
- **Tài liệu liên quan:** [ADR-001](./001-modular-monolith.md), [kế hoạch tổng](../TEAM_WORK_PLAN.md), [đặc tả](../PROJECT_SPECIFICATION.md)

---

## 1. Bối cảnh

- Tính đến W46 (chốt 16/11/2026), nhóm đã xong giai đoạn 1–7 của lộ trình 10 giai đoạn; W47 làm giai đoạn 8. Nhóm đang đi trước lộ trình khoảng hai đợt.
- Hạn nộp là 04/01/2027, còn khoảng 7 tuần lịch sau W47. Giai đoạn 9 (kiểm thử, CI, staging) và 10 (ổn định, demo, bàn giao) dự kiến cần khoảng 2–3 tuần, nên có thể còn thời gian cho một tính năng mở rộng.
- Backend đã có API công khai cho giải, bracket, bảng kết quả và lịch trận. Người xem hiện phải tự tìm qua nhiều màn hình; một chatbot hỏi đáp bằng tiếng Việt giúp tra cứu nhanh và làm điểm nhấn khi demo.

## 2. Quyết định

**Chỉ làm chatbot sau khi giai đoạn 8–10 đạt nghiệm thu.** Nếu làm, theo thiết kế sau:

- **Module mới** `backend/modules/chatbot` trong modular monolith (ADR-001), endpoint `POST /api/v1/chat`. Không tách service riêng.
- **Mô hình:** Claude API qua SDK `anthropic` chính thức, mặc định `claude-haiku-5-5` (rẻ, nhanh); chỉ nâng lên `claude-sonnet-5-5` nếu chất lượng trả lời không đạt khi thử.
- **Tool use, không RAG:** bot trả lời bằng cách gọi các tool bọc lại **service/API đọc công khai đã có** (danh sách giải, chi tiết giải, bracket, bảng kết quả, lịch trận, đội). Không sinh SQL, không truy cập DB trực tiếp.
- **Chỉ đọc:** không có tool ghi. Bot không tạo giải, duyệt đội, nhập kết quả hay cấp quyền, kể cả khi người dùng có quyền đó.
- **Quyền:** dữ liệu trả về giống hệt người dùng ẩn danh xem được qua API công khai; không trả email, roster nháp, assignment, audit.
- **Khóa API:** `ANTHROPIC_API_KEY` chỉ ở biến môi trường backend, không commit, không đưa xuống frontend. Thiếu khóa thì endpoint trả 503 và UI ẩn khung chat; phần còn lại của hệ thống chạy bình thường.
- **Giới hạn chi phí:** rate limit theo IP/phiên, giới hạn độ dài câu hỏi và số vòng gọi tool mỗi câu, giới hạn `max_tokens`.
- **UI:** khung chat nổi trên frontend React, hiển thị loading/lỗi/thử lại; câu trả lời có link tới trang giải/bracket liên quan.

## 3. Phương án đã cân nhắc

| Phương án | Lý do không chọn |
|---|---|
| Bot sinh SQL từ câu hỏi | Rủi ro lộ dữ liệu/ghi nhầm, khó kiểm soát quyền |
| RAG trên tài liệu/dump dữ liệu | Dữ liệu giải thay đổi liên tục, dễ trả lời số liệu cũ |
| Bot có quyền ghi (nhập kết quả, duyệt đội) | Trái với nguyên tắc transaction/audit/khóa đã xây; không cần cho demo |
| Không làm | Vẫn là phương án mặc định nếu giai đoạn 8–10 chưa xong |

## 4. Điều kiện bắt đầu và kế hoạch dự kiến

- **Điều kiện:** giai đoạn 8 (W47), 9, 10 đều `DONE`, CI xanh trên main, demo flow chính chạy ổn. Nhóm trưởng xác nhận trong file tuần trước khi giao task.
- **Mốc dừng:** nếu đến **21/12/2026** chưa bắt đầu thì bỏ, dành thời gian còn lại cho ổn định và báo cáo. Không merge chatbot vào main sau **28/12/2026** để giữ một tuần đóng băng trước hạn 04/01/2027.
- **Phân công gợi ý (một đợt, 4 task):** backend module + tool + giới hạn (DUNG, review DOANH); bộ tool đọc giải/bracket/bảng hạng và test (DOANH, review DUNG); UI khung chat (DUONG, review DUC); test quyền/không lộ dữ liệu/không có đường ghi + E2E với API mock (DUC, review DUONG).
- **Nghiệm thu:** trả lời đúng ít nhất các câu mẫu (hạng của đội trong giải, trận tiếp theo, đội vô địch, đội còn lại trong bracket); câu hỏi ngoài phạm vi được từ chối lịch sự; test chứng minh không có tool ghi và không lộ trường nhạy cảm; CI không gọi Claude thật (dùng mock).

## 5. Hệ quả

- **Tích cực:** điểm nhấn demo, tái sử dụng API sẵn có, không đổi schema.
- **Tiêu cực:** phụ thuộc dịch vụ ngoài và chi phí theo lượt gọi; cần khóa API khi demo; câu trả lời của mô hình có thể sai nên UI phải ghi nguồn/link để người xem kiểm tra.
