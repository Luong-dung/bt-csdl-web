# Kế hoạch dữ liệu quy mô lớn (dự kiến W49)

- **Ngày lập:** `2026-11-23`; **người lập:** DUNG. **Trạng thái:** đề xuất, chưa triển khai.
- **Bối cảnh:** giáo viên yêu cầu ≥ 20 bảng, có thông tin một số bảng cần cỡ **triệu dòng**. Giảng viên đã đồng ý **dùng AI để tạo đủ dữ liệu** (DUNG hỏi trực tiếp, ghi nhận 23/11). **Cần xác nhận lại với giáo viên:** bao nhiêu bảng phải đạt triệu dòng, ngưỡng tối thiểu, có cho phép dữ liệu tổng hợp (synthetic) và có phải nộp file dump không.
- **Liên quan:** [W48](./weeks/2026-W48.md) (W48-04 làm `permissions`/`tournament_standings` có dữ liệu, thêm `role_permissions`), [ADR-002 chatbot](./ADR/002-chatbot-tra-cuu.md) (W49).

## 1. Nguyên tắc

- **Danh mục dùng dữ liệu thật** (ít dòng). **Dữ liệu nghiệp vụ quy mô lớn sinh bằng script**, tên người/đội/tổ chức **giả** (Faker, email `@example.com`), random seed cố định để tái lập được.
- **Cách dùng AI:** (1) AI viết script sinh dữ liệu (tạo khối lượng triệu dòng); (2) AI sinh phần cần tự nhiên — ~2.000 tên đội/tổ chức, vài trăm mô tả giải, vài nghìn câu hỏi mẫu chatbot — lưu thành file mẫu trong repo kèm prompt/cách sinh, script trộn mẫu để nhân lên. Không cho LLM sinh trực tiếp từng dòng (chậm, tốn, trùng lặp, sai ràng buộc). Ghi vào [AI_WORK_LOG.md](./AI_WORK_LOG.md).
- **Kết quả trận có quy luật:** mỗi đội có sức mạnh ẩn thay đổi theo thời gian (đổi thành viên, phong độ); kết quả sinh theo xác suất từ chênh lệch sức mạnh, để dữ liệu trông thật và dùng được cho phân tích/dự đoán.
- Không gắn kết quả giả cho đội/tuyển thủ/tổ chức có thật. Nếu sau này có dữ liệu thật (Liquipedia, Kaggle) thì để riêng, không trộn với kết quả giả.
- Dữ liệu sinh phải đúng ràng buộc và luật nghiệp vụ: winner thuộc hai đội, bracket đúng nhánh, roster chỉ gồm thành viên đội được duyệt, trạng thái/ngày hợp lệ.
- Nạp vào database riêng (ví dụ `esports_tournament_bigdata`), không dùng DB demo/CI/cá nhân. Báo cáo ghi rõ: "dữ liệu quy mô lớn là dữ liệu tổng hợp, sinh bằng script, tên là giả".

## 2. Số dòng dự kiến theo bảng

Quy ước: giải 16 đội → 15 trận; roster 5 người/đội (5v5); BO3 trung bình 2,5 ván/trận. **(đo)** = đo thật 23/11 trên PostgreSQL local với 1 triệu dòng; **(ước tính)** = suy ra, chưa đo.

### Danh mục — dữ liệu thật

| Bảng | Số dòng | Nguồn |
|---|---|---|
| `roles` | 6 | Seed hiện có |
| `permissions` | ~30 | Định nghĩa theo hệ thống (W48-04) |
| `role_permissions` | ~100 | Gán quyền theo role (W48-04) |
| `publishers` | ~15 | Thật (Riot, Valve, Blizzard…); seed hiện có 2, bổ sung tay |
| `games` | ~10 | Thật; seed hiện có 5 |
| `countries` | ~250 | Danh sách quốc gia ISO 3166; seed hiện có 8 |
| `competition_areas` | 31 | Seed hiện có |

### Nghiệp vụ — sinh bằng script

| Bảng | Số dòng | Cách sinh | Dung lượng |
|---|---|---|---|
| `users` | **1.000.000** | Faker `real_name`, `sim_user_0000001@example.com`, một hash mật khẩu dùng chung (bcrypt từng user quá chậm) | 324 MB (đo) |
| `organizations` | 10.000 | Tên giả | ~2 MB (ước tính) |
| `teams` | 50.000 | Tên/tag giả, gắn organization | 6 MB (đo) |
| `team_memberships` | **1.000.000** | ~400k ACTIVE (8 người/đội), ~600k ENDED (lịch sử rời đội) | 142 MB (đo) |
| `role_assignments` | ~64.000 | 1 trọng tài/giải | ~8 MB (ước tính) |
| `tournaments` | 64.000 | Đủ trạng thái, đa số COMPLETED | ~8 MB (ước tính) |
| `stages` | 64.000 | 1 stage/giải | ~8 MB (ước tính) |
| `tournament_registrations` | **~1.300.000** | 16 APPROVED + ~4 REJECTED/CANCELLED/PENDING mỗi giải | ~180 MB (ước tính) |
| `tournament_rosters` | **~5.000.000** | 5 người × đội được duyệt | ~800 MB (ước tính) |
| `tournament_brackets` | 64.000 | 1 bracket 16 đội/giải | ~6 MB (ước tính) |
| `matches` | **~1.000.000** | 15 trận/giải, winner đi đúng nhánh | 196 MB (đo) |
| `bracket_matches` | **~1.000.000** | 1 dòng/trận | ~80 MB (ước tính) |
| `match_games` (bảng mới W49) | **~2.500.000** | BO3, ~2,5 ván/trận | ~370 MB (ước tính) |
| `tournament_standings` | **~1.000.000** | 16 dòng/giải COMPLETED | ~80 MB (ước tính) |
| `audit_logs` | 300.000 | Thao tác gần đây; JSON before/after ~1,1 KB/dòng | ~335 MB (ước tính từ số đo) |
| `chat_messages` (bảng mới W49) | 50.000 | Câu hỏi mẫu chatbot | ~15 MB (ước tính) |

**Tổng:** 23 bảng, **9 bảng ≥ 1 triệu dòng**, khoảng **2,6 GB** (chưa đo toàn bộ). Ổ đĩa cần trống gấp 2–3 lần khi nạp (WAL, file tạm).

## 3. Số đo thực tế (23/11/2026, PostgreSQL local, 1 triệu dòng/bảng)

| Bảng | Dung lượng (heap + index) | Byte/dòng | Thời gian nạp (`INSERT … SELECT generate_series`) |
|---|---|---|---|
| `users` | 324 MB (195 + 129) | 340 | 42 s |
| `matches` | 196 MB (89 + 107) | 205 | 102 s |
| `tournament_rosters` | 156 MB (65 + 91) | 164 | 65 s |
| `team_memberships` | 142 MB (57 + 85) | 149 | 54 s |
| `tournament_registrations` | 138 MB (73 + 65) | 145 | 57 s |
| `audit_logs` (JSON thật của `MATCH_RESULT_SUBMITTED`) | 1.115 MB (977 + 138) | 1.169 | 52 s |

Database thử nghiệm tạo riêng và đã xóa sau khi đo. Dữ liệu đo sinh cơ học (xoay vòng id), chỉ để đo dung lượng/thời gian, không phải dữ liệu nộp.

## 4. Lựa chọn và rủi ro

- `tournament_rosters` chiếm ~1/3 dung lượng (5v5). Muốn nhẹ: một phần giải dùng game 1v1 (roster 1 người) → ~3 triệu dòng, ~500 MB.
- `audit_logs` rất nặng/dòng; giữ ~300k thay vì triệu dòng.
- Nạp dự kiến ~15 phút với cách hiện tại; có thể nhanh hơn bằng `COPY`, tạm bỏ index rồi tạo lại (chưa thử).
- **Liquipedia:** điều khoản API (đọc 23/11) không hỗ trợ dùng MediaWiki API cho mục đích lấy dữ liệu, cấm cào HTML; dữ liệu có cấu trúc qua LiquipediaDB API cần đăng ký và được duyệt; nội dung CC-BY-SA 3.0 (phải ghi nguồn). Không phụ thuộc nguồn này cho kế hoạch.

## 5. Phân phối dữ liệu (không đưa dữ liệu lên GitHub)

- GitHub chặn file > 100 MB; Git LFS miễn phí ~1 GB, không đủ; dữ liệu trong repo làm clone rất nặng. **Commit script + file mẫu, không commit dữ liệu.**
- Script dùng random seed cố định → ai chạy cũng ra cùng bộ dữ liệu; mỗi người tự nạp vào DB riêng (ước tính ~15 phút, chưa đo toàn bộ), in tiến độ từng bảng.
- Nếu cần nộp: `pg_dump -Fc` (ước tính vài trăm MB, chưa đo) đưa lên **GitHub Releases** (asset ≤ 2 GB/file, không vào lịch sử git) hoặc Google Drive, kèm file ghi số dòng từng bảng và checksum.

## 6. Thứ tự trong W49 (dự kiến)

1. **Đầu tuần:** chốt schema `match_games`, `chat_messages` (script sinh cần biết). Chatbot phát triển và test trên **dữ liệu demo W48-01** (`seed_demo.py --reset`); CI dùng mock, không cần dữ liệu lớn.
2. **Giữa tuần:** script sinh dữ liệu xong, mọi người chạy local.
3. **Cuối tuần:** chạy chatbot trên DB lớn, đo thời gian trả lời, `EXPLAIN ANALYZE`; xuất dump nếu cần nộp.

## 7. Đầu ra dự kiến khi triển khai (W49)

- Script sinh dữ liệu (seed cố định, in tiến độ từng bảng, kiểm tra ràng buộc sau khi nạp) và hướng dẫn chạy.
- Báo cáo: số dòng/dung lượng thật từng bảng, thời gian nạp, kích thước `pg_dump -Fc`.
- `EXPLAIN ANALYZE` các truy vấn chính (danh sách giải, standings, nhật ký audit có phân trang/đếm, đăng nhập) trước/sau index; xử lý truy vấn chậm.
