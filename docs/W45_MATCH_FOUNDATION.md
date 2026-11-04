# W45-01 — Nền tảng match và contract nghiệp vụ

Bàn giao cho W45-02 (kết quả), W45-03 (API lịch/vòng đời), W45-04 (capability), W45-05/-06 (UI), W45-07/-08 (test). Phần checker nền W45-04 nằm cùng PR này để -02/-03 không phải chờ.

## 1. Khảo sát bảng `matches` trước W45

| Trường | Hiện trạng | Quyết định W45 |
|---|---|---|
| `round_no` | INT NOT NULL, không check | Thêm `ck_matches_round` (> 0). Không suy thứ tự từ giờ đấu |
| `team1_id`, `team2_id` | Nullable | Giữ nullable cho dữ liệu nhánh đấu cũ; API W45 bắt buộc đủ hai đội. `ck_matches_distinct_teams` |
| `score_team1/2` | DEFAULT 0 | `ck_matches_scores` (≥ 0). 0 mặc định **không** phải kết quả 0–0; chỉ COMPLETED mới có kết quả |
| `winner_id` | Tự do | `ck_matches_winner_team` (là team1 hoặc team2), `ck_matches_result` (có winner ⇔ COMPLETED) |
| `next_match_id` | FK tự tham chiếu | Giữ nguyên, W45 không đọc/ghi |
| `status` | VARCHAR tự do | `ck_matches_status` ∈ PENDING, ONGOING, COMPLETED, CANCELLED |
| `stage_id` | FK RESTRICT (W44-2) | Thêm FK ghép `fk_matches_stage_tournament (stage_id, tournament_id) → stages` để stage luôn thuộc đúng giải; FK cũ giữ nguyên |
| — | — | Thêm `scheduled_at TIMESTAMPTZ NULL` |

Index: `ix_matches_tournament_stage (tournament_id, stage_id, round_no, match_id)`, `ix_matches_team1`, `ix_matches_team2`.

## 2. Migration `b45a01c0ffee` (sau `7a1b2c3d4e5f`)

- **Dữ liệu cũ:** trước mọi DDL, kiểm tra từng ràng buộc mới (gồm stage khác giải). Có vi phạm → `RuntimeError("Match migration blocked …")` liệt kê tối đa 20 `match_id` mỗi luật, schema không đổi. Migration **không** sửa/xóa/tự điền dữ liệu; người vận hành tự xử lý rồi chạy lại.
- **Cài mới:** revision đầu dựng từ metadata hiện tại nên đối tượng có thể đã tồn tại; migration xóa-rồi-tạo theo tên.
- **Hạ cấp:** giữ mọi dòng `matches`; chỉ mất giá trị `scheduled_at` (cột mới). FK RESTRICT `fk_matches_stage` của W44(2) không bị đụng.
- Test: `tests/test_match_migration.py` (cần `--postgres`).

## 3. Module dùng chung `backend/core/matches.py`

**Thứ tự khóa:** giải → trận → (đội theo ID tăng nếu cần). Không khóa ngược. Caller tự commit/rollback và ghi audit trong cùng transaction.

| Hàm | Dùng cho |
|---|---|
| `can_start_match(db, tournament, match, user) -> bool` | Quản lý giải **hoặc** REFEREE assignment `TOURNAMENT` đúng giải |
| `can_submit_result(db, tournament, match, user) -> bool` | Như trên |
| `can_cancel_match(db, tournament, match, user) -> bool`, `can_manage_matches(tournament, user)` | Chỉ quản lý giải (`can_manage_tournament` hiện có) |
| `is_tournament_referee(tournament, user)` | Role REFEREE trên user, assignment GLOBAL hoặc giải khác **không** tính |
| `lock_match_context(db, tid, match_id, user, checker)` | Kiểm tra quyền trước khi xếp hàng → khóa giải (đọc lại user) → khóa trận → kiểm tra lại quyền. Trả `(tournament, match, user)`; ném 404/403. Không kiểm tra lifecycle để caller xử lý gửi lặp |
| `match_editable / match_startable / match_result_open / match_cancellable` | Luật vòng đời (bảng mục 4), dùng chung cho mutation và capability |
| `ensure_match_writable_tournament(tournament)` | 409 nếu giải COMPLETED/CANCELLED hoặc roster chưa khóa |
| `ensure_stage_in_tournament`, `ensure_match_teams` | 422 nếu stage khác giải; đội trùng, khác game, không APPROVED hoặc không có PLAYER trong snapshot |
| `to_utc(dt)` / `as_utc(dt)` | Ghi: bắt buộc có offset (thiếu → 422), đổi sang UTC. Đọc: SQLite trả naive → gắn UTC |
| `match_state(match)` | Snapshot before/after cho audit |

Checker chỉ kiểm tra quyền; tham số `match` giữ để mở rộng mà không đổi chữ ký. Route **không** tự viết lại checker.

## 4. Vòng đời

| Trạng thái | Thao tác hợp lệ | Điều kiện giải |
|---|---|---|
| PENDING | sửa, xóa (quản lý) | UPCOMING/ONGOING, roster đã khóa |
| PENDING → ONGOING | bắt đầu (quản lý/trọng tài) | ONGOING, roster đã khóa, đủ hai đội |
| ONGOING → COMPLETED | ghi kết quả (quản lý/trọng tài) | ONGOING |
| PENDING/ONGOING → CANCELLED | hủy (quản lý) | UPCOMING/ONGOING |
| COMPLETED | gửi lại đúng kết quả → 200 không audit; khác → 409 | — |
| CANCELLED | hủy lại → 200 không audit | — |

Kết quả: tỉ số nguyên ≥ 0 (strict, không bool/float), không hòa; server tự tính `winner_id`.

## 5. Wire contract đề xuất cho W45-02/-03 (chốt khi mở PR tương ứng)

`MatchRead`:

```json
{"match_id": 31, "tournament_id": 12, "stage_id": 17, "stage_name": "Vòng bảng", "round_no": 1,
 "team1": {"team_id": 4, "name": "Alpha"}, "team2": {"team_id": 9, "name": "Beta"},
 "scheduled_at": "2026-11-05T12:00:00Z", "status": "COMPLETED",
 "result": {"score_team1": 2, "score_team2": 1, "winner_id": 4}}
```

- `result` là `null` khi chưa COMPLETED (UI không hiển thị 0–0).
- List: `offset` (≥ 0), `limit` 1–100 mặc định 50, lọc `stage_id`, `team_id`, `status`; header `X-Total-Count`; sắp `stages.sequence_order, round_no, match_id`.
- Ghi kết quả: `PUT …/result` body `{"score_team1": 2, "score_team2": 1}` (`extra='forbid'`).
- Đổi trạng thái: `POST …/status` body `{"status": "ONGOING" | "CANCELLED"}`.
- Thứ tự lỗi: 401 → 404 giải/trận → 403 → 422 payload/liên kết → 409 lifecycle.
- Audit `resource='match'`, action `MATCH_CREATED/UPDATED/DELETED/STARTED/CANCELLED/RESULT_SUBMITTED`, details `{tournament_id, match_id, before, after}`.

## 6. Giới hạn đã biết

- `scheduled_at` không chống trùng lịch (chưa có thời lượng/sân).
- FK team của `matches` trong model không có ON DELETE; `schema_postgres.sql` ghi SET NULL. Đội đang có đăng ký bị chặn xóa bởi FK RESTRICT của `tournament_registrations`; nếu SET NULL chạm trận COMPLETED thì `ck_matches_result` chặn. Theo dõi cùng mục FK khi có tính năng xóa giải/đội.
- PostgreSQL test chưa chạy local trên máy tác giả (không có database test riêng); dựa vào CI.
