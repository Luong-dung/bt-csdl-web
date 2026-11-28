# W48-04 (b): Bảng xếp hạng chốt lưu trong `tournament_standings`

Trước W48-04, bảng `tournament_standings` có sẵn từ schema ban đầu nhưng luôn 0 dòng. Standings W46 ([W46_BRACKET_FOUNDATION.md](W46_BRACKET_FOUNDATION.md)) được tính lại từ kết quả trận mỗi lần đọc. W48-04 ghi **bảng chốt** vào bảng khi giải chuyển COMPLETED. **API và DTO giữ nguyên**: cùng shape, cùng giá trị, cùng thứ tự.

## 1. Khi nào ghi

- Trong `POST /tournaments/{id}/status` với `COMPLETED`, sau khi `tournament_completion_error` đã kiểm tra mọi trận bracket COMPLETED và có chung kết hợp lệ, trên giải đã khóa. Ghi **cùng transaction** với đổi trạng thái: lỗi ở bất kỳ bước nào thì rollback cả hai, giải vẫn ONGOING.
- Mỗi đội trong `team_order` một dòng: `final_rank` = hạng W46 (1, 2, 3, 3, 5…), `matches_played`, `wins`, `losses` như API; `points = wins` (single-elimination không có hệ điểm, mỗi trận thắng 1 điểm); `prize_money = 0` (chưa có tính năng tiền thưởng).
- Audit `TOURNAMENT_STANDINGS_FINALIZED` (resource `tournament`, actor là người chuyển trạng thái) với `bracket_id` và danh sách `{team_id, rank}` theo thứ tự bảng. Dòng này đứng ngay trước audit `TOURNAMENT_STATUS_CHANGED` của cùng request.
- Giải **không có bracket** vẫn COMPLETED được như cũ. Không có gì để xếp hạng nên không ghi dòng nào và không có audit.
- Sau COMPLETED, kết quả trận bị khóa (`match_result_open` cần giải ONGOING) và COMPLETED là trạng thái cuối, nên bảng chốt không thể lệch so với kết quả.

## 2. Khi nào đọc

`GET /tournaments/{id}/bracket/standings`:

- Giải **COMPLETED** có bảng chốt phủ đúng các đội của bracket → trả từ bảng, `status = FINAL`.
- Giải COMPLETED nhưng không có dòng nào (hoàn tất trước khi backfill), hoặc bảng không khớp bracket → tính lại như W46 và ghi log cảnh báo nếu không khớp.
- Giải UPCOMING/ONGOING/CANCELLED → tính như W46, không đổi.

## 3. Migration `h48a04b00002`

- Không đổi schema: bảng đã có trong `schema_postgres.sql` và migration gốc.
- **Backfill** các giải đã COMPLETED có bracket và chưa có dòng nào: tính lại bảng từ kết quả trận theo đúng quy tắc trên. Bracket chưa phân định đủ (thiếu trận, trận không COMPLETED, winner không hợp lệ, chưa có chung kết) thì bỏ qua, API vẫn tính lại cho giải đó. Không ghi audit vì đây không phải thao tác của người dùng.
- Downgrade **giữ nguyên các dòng**: bản trước không đọc bảng, và không phân biệt được dòng do app ghi với dòng do backfill ghi.

## 4. Kiểm thử

[`backend/tests/test_tournament_standings.py`](../backend/tests/test_tournament_standings.py), chạy trên SQLite và `--postgres`:

- Chuyển COMPLETED ghi đúng 8 dòng (hạng 1, 2, 3, 3, 5, 5, 5, 5) cùng 1 audit. Response API trước và sau khi chốt giống hệt, kể cả phân trang. Gửi COMPLETED lần hai bị 409 và không ghi thêm.
- Đọc từ bảng: sửa một dòng trong bảng thì API đổi theo. Bảng thiếu đội hoặc rỗng thì API quay về tính lại.
- Giải không có bracket: không ghi dòng, không audit.
- Lỗi khi ghi audit thì rollback cả trạng thái giải và bảng.
- Backfill: tạo lại đúng bảng đã xóa, chạy lần hai không nhân đôi, bỏ qua bracket chưa phân định. Hàm xếp hạng của migration không đoán khi dữ liệu thiếu hoặc sai.

Đo trên DB demo `--reset` (PostgreSQL, 28/11/2026): **21/21 bảng có dữ liệu**. `W48 Demo Cup` có 4 dòng hạng 1/2/3/3 và 1 audit chốt. Xóa bảng rồi `alembic downgrade -1` + `upgrade head` cho lại đúng 4 dòng đó.
