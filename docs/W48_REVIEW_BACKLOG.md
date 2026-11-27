# W48-04: Rà góp ý review còn mở W42–W47 (backend)

Rà 28/11/2026 trên `main` `30f5f1b`: review/inline comment của mọi PR backend #6–#111 (và PR frontend có nhắc backend), mục "giới hạn đã biết"/"theo dõi" trong `docs/W4x_*.md` và `docs/weeks/2026-W4*.md`. Không có issue GitHub mở và không có TODO/FIXME trong code. W48-03 không phát hiện lỗi code ([W48_README_CHECK.md](W48_README_CHECK.md)).

## 1. Đã sửa (mỗi lỗi có test tái hiện viết trước, fail trước khi sửa)

| # | Nguồn | Lỗi | Sửa | Test |
|---|---|---|---|---|
| 1 | Review #101 (mục 5–6) | **Xung đột lợi ích:** kiểm tra từng trận (`plays_in_match`) yếu hơn lúc cấp. Trọng tài được cấp trước, sau đó có assignment TEAM_MANAGER phạm vi TEAM/ORGANIZATION của đội đang đấu (không phải thành viên) vẫn bắt đầu trận và **nhập kết quả trận của chính đội mình** (capability `can_start = true`) | `core/matches.py`: `plays_in_match` thêm `manages_team` (TEAM_MANAGER phạm vi TEAM là một trong hai đội, hoặc ORGANIZATION chứa đội), cùng quy tắc `plays_in_tournament` lúc cấp | `test_match_result_api.py::test_referee_who_later_manages_a_playing_team_cannot_start_or_submit[TEAM/ORGANIZATION]`: start/result 403, capability false, trận không đổi, không audit |
| 2 | Review #33 | PATCH giải gửi giá trị giống hiện tại vẫn ghi `TOURNAMENT_UPDATED` (before = after); giải ONGOING gửi lại nguyên form (kèm `start_date` không đổi) bị 409 | `routes/tournaments.py`: bỏ trường không đổi trước mọi kiểm tra; không còn gì thì trả giải, không audit; audit chỉ ghi trường đổi thật. Giải COMPLETED/CANCELLED vẫn 409 | `test_tournament_api.py::test_unchanged_values_are_not_audited` |
| 3 | Review #57 (W44-2) | Duyệt/đăng ký khi giải UPCOMING nhưng đã khóa đội hình báo "Giải đấu đã đóng đăng ký", không nói lý do | `core/registrations.py`: 409 "Giải đã khóa đội hình, không thể đăng ký hoặc duyệt thêm đội" khi UPCOMING + khóa; các trạng thái khác giữ thông báo cũ | `test_registration_decisions.py::test_approve_after_roster_lock_says_the_roster_is_locked` |

## 2. Để lại, có lý do

| # | Nguồn | Mô tả | Lý do để lại |
|---|---|---|---|
| 4 | Review #101 (mục 7) | Hai ADMIN (chỉ có ADMIN qua assignment GLOBAL) thu hồi lẫn nhau cùng lúc thì cả hai thành công | Cần khóa toàn bộ assignment ADMIN và test race 2 kết nối PostgreSQL; ADMIN theo `users.role_id` vẫn còn nên không mất quyền quản trị hoàn toàn. Đã ghi giới hạn trong W47_ROLE_ASSIGNMENTS.md §6 |
| 5 | Re-review #101 | Danh sách assignment ADMIN vẫn hiện tổ hợp role–scope cũ không checker nào dùng (vd. REFEREE/GLOBAL) | API ADMIN đã chặn tạo mới (422); chỉ ảnh hưởng dữ liệu tạo trước W47. Sửa cần đổi DTO (`effective`) → chờ thống nhất với UI (DUONG) |
| 6 | Review #108 (mục 4) | API tìm ứng viên trọng tài trả cả người không cấp được (chính người quản lý, trọng tài đang hiệu lực) | Không sai dữ liệu: cấp vẫn trả 409/422 rõ ràng. Đổi kết quả tìm kiếm là đổi contract UI W47-05 → làm cùng DUONG nếu cần |

## 3. Đã kiểm, đã được sửa trước đây

#6 (rời đội đồng thời), #14, #32, #33 (audit đội), #40 (7 mục), #41 (8 mục), #57 (đơn PENDING sau khóa), #62.1, #80, #82, #89/#92/#93, #101.1–4 và 6 (lúc cấp), #107, #111, lệch FK trận W45. Bỏ qua: #84.14 (không xảy ra được sau khóa roster), #62.2 (chỉ là style), các mục chỉ frontend/tài liệu.

## 4. Bằng chứng

- SQLite toàn bộ: **956 passed / 103 skipped**. PostgreSQL `--postgres -m postgres` các file sửa (`test_match_result_api`, `test_tournament_api`, `test_registration_decisions`, `test_referee_assignments`, `test_match_api`): **289 passed**. Ruff đạt.
