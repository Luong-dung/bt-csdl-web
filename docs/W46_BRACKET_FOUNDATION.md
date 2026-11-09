# W46-01 — Nền tảng bracket và contract bàn giao

Code nền: W45; phạm vi nghiệp vụ theo [kế hoạch W46](./weeks/2026-W46.md). W46-01 cung cấp schema/helper/input/capability; **chưa có endpoint tạo/đọc bracket hoặc tự chuyển winner**. W46-02/-03/-04 nối các phần đó sau review/merge nền tảng.

## 1. Khảo sát và lựa chọn dữ liệu

- `matches` đã có `round_no`, `next_match_id`, đội nullable, winner và lịch UTC. `next_match_id` không có slot và có thể là dữ liệu lịch sử; tuyệt đối không suy membership W46 từ trường này.
- Giữ nguyên mọi match/edge/standing cũ. Một match chỉ được quản lý như bracket W46 nếu có hàng trong **`bracket_matches`**. Không backfill metadata từ match cũ.
- `tournament_standings.final_rank` NOT NULL và có points/prize_money; W46 không sửa hoặc ghi bảng đó. API W46-04 sẽ dẫn xuất bảng kết quả từ managed matches, với rank NULL khi chưa bị loại/chưa vô địch.
- `tournament_brackets`: định danh bracket, unique tournament/stage, số đội/số vòng, JSON thứ tự team IDs đã xác nhận, người tạo/thời gian UTC. Giới hạn 2/4/8/16/32/64 đội; `round_count=log2(team_count)`.
- `bracket_matches`: liên kết match thật với bracket và tọa độ `(round_index,position)`, cùng tọa độ trận đích `next_round/next_position/next_slot`. Round/position đều bắt đầu từ 1. Các vòng tương lai là match thật có hai đội NULL; không tạo đội hoặc kết quả giả.
- `Match.round_no` của trận được sinh bằng round_index để list W45 có thứ tự phù hợp; metadata W46 mới là nguồn cấu trúc. `Match.next_match_id` giữ NULL trên trận W46; cạnh chỉ lưu ở metadata, không duy trì hai bản cạnh.

## 2. Constraint và giới hạn DB/service

- Unique một bracket/giải, một bracket/stage, một match/metadata và một vị trí/bracket.
- FK ghép metadata → header chứng minh cùng giải/stage/số vòng; FK ghép metadata → match chứng minh cùng match/giải/stage. `matches` thêm unique `uq_matches_bracket_identity` làm đích FK.
- FK tự tham chiếu metadata chứng minh đích tồn tại trong chính bracket. CHECK bắt buộc cạnh đi lên đúng một vòng, đúng vị trí cha và slot lẻ→1/chẵn→2; chung kết phải có cả ba trường đích NULL. CHECK có IS NOT NULL rõ ràng để SQL NULL không làm lọt cạnh thiếu dữ liệu. Vị trí bị giới hạn theo số vòng.
- FK header → stage/giải là FK đơn: **header.stage thuộc đúng giải được kiểm tra ở service**, không phải constraint ghép trên header. Khi đã gắn node, các FK ghép cộng FK stage của match bảo vệ giải/stage của node. Không công bố DB bảo đảm điều mà schema chưa enforce.
- Lý do tương thích migration: initial revision dựng live metadata, trong khi W45 drop/tạo lại unique ghép của stages; FK mới từ header tới unique đó sẽ làm cài mới thất bại trước khi tới migration W46. Giữ FK đơn ở header và không sửa revision cũ.
- JSON team_order đầy đủ/unique, tất cả đội APPROVED/cùng game/có PLAYER, đủ N−1 node, đội vòng đầu và slot winner nhất quán là trách nhiệm writer/service. Không coi metadata tạo thủ công bằng SQL là bracket hợp lệ chỉ vì vượt qua constraint.
- FK RESTRICT không cho xóa header/match/stage khi có metadata. Writer W46-03 phải tạo header + toàn bộ match/node + audit trong một transaction; tạo node theo vòng giảm dần để đích tồn tại trước nguồn. Trạng thái không đầy đủ không được commit.

## 3. Migration `c46a01b00001`

- Parent `b45a01c0ffee`. Thêm unique identity trên matches và hai bảng mới; không đổi status, điểm, next_match_id hoặc standings cũ. Unique mới có match_id PK nên dữ liệu W45 hợp lệ không cần sửa để upgrade.
- Initial revision dùng live metadata; migration nhận biết object đã có trên cài mới. Không sửa các revision cũ. Kiểm thử cả cài mới và nâng từ W45.
- Downgrade khi **chưa có bracket** xóa hai bảng metadata/unique mới, giữ nguyên match/lịch sử/standing.
- Có bracket thì downgrade dừng **trước DDL** bằng `RuntimeError`, không xóa metadata để âm thầm biến trận managed thành trận thủ công. Người vận hành cần export, xác định xử lý dữ liệu và có kế hoạch riêng trước khi hạ; không có API xóa/reset bracket trong W46.
- SQLite tests dùng metadata; Alembic DDL nâng/hạ kiểm thử PostgreSQL trên DB riêng. SQL tham chiếu: `database/schema_postgres.sql`.

## 4. Helper bàn giao

Module `backend/core/brackets.py`; caller sở hữu transaction, helper không commit/audit.

| Helper | Contract |
|---|---|
| `get_bracket(db,tid)` | Header hoặc None; không tự tạo |
| `managed_match(db,match_id)` | Metadata hoặc None; không lần theo legacy edge |
| `can_create_bracket(db,tournament,user)` | Hint cho capability: quản lý đúng giải, SINGLE_ELIM, UPCOMING, roster khóa, chưa có bracket; chưa kiểm tra input đội/stage |
| `lock_bracket_context(db,tid,user)` | Chặn quyền trước chờ, khóa giải, tải lại user/assignment rồi kiểm tra quyền; trả tournament/user. Chưa chặn bracket tồn tại để caller xử lý replay |
| `ensure_bracket_input(db,tournament,data)` | 409 lifecycle/format/roster/stage có trận; 422 stage sai giải, thiếu/thừa đội APPROVED, game sai hoặc thiếu PLAYER snapshot; trả fingerprint live input hợp lệ |
| `bracket_plan(data)` | N−1 node theo round/position tăng dần, vòng đầu cặp liền kề, vòng sau TBD, cạnh/slot rõ ràng; không ghi DB |
| `issue_preview_token(tid,fingerprint)` | JWT HS256 có purpose riêng, giải, fingerprint và hạn 15 phút; không phải access token |
| `verify_preview_token(token,tid,fingerprint)` | Token sai/hết hạn/khác giải/khác fingerprint → 409; không thay validation live |
| `lock_bracket_match_context(db,tid,mid,user,checker)` | Dành W46-02: kiểm quyền trước chờ, khóa giải, tải metadata rồi khóa source/đích theo match_id tăng dần, đọc lại actor/match và kiểm quyền; trả `(tournament,match,destination_or_None,user)`; match thủ công/legacy không truyền đích |

Fingerprint v1 gồm giải/game/stage, team IDs theo thứ tự, thời điểm khóa chuẩn UTC và snapshot roster (team/user/role). Preview không ghi DB; tạo phải validate lại sau lock. Tên hiển thị thay đổi không đổi cấu trúc, không làm token hết hiệu lực. Thay input/thứ tự/roster hoặc token hết hạn phải preview lại.

## 5. Wire contract cho W46-03/-04

Các route dưới đây **chưa triển khai trong W46-01**; W46-03/-04 phải giữ contract hoặc cập nhật thống nhất trước khi UI nối.

- Preview `POST /api/v1/tournaments/{tid}/bracket/preview` body `{"stage_id":17,"team_ids":[4,9,12,15]}`. `BracketInput`: IDs strict int PostgreSQL >0, không bool/float/string, list 2–64 không trùng, số lượng lũy thừa hai, extra forbid. Trả `{tournament_id,stage_id,team_ids,team_count,round_count,matches:[BracketPlanMatch],preview_token,expires_in:900}`; match preview không có match_id thật.
- Create cùng prefix `/bracket`, `BracketCreate` thêm `preview_token` (1–8192 ký tự). Sau khóa giải, kiểm quyền; nếu header đã có và stage/team_order trùng thì trả bracket hiện có 200 không ghi thêm/audit, kể cả token preview đã hết hạn. Nếu input khác thì 409. Nếu chưa có, validate live/verify token, tạo đầy đủ và audit trong một transaction, trả 201.
- GET `/bracket` công khai, 404 nếu chưa có; trả header công khai và toàn bộ tối đa 63 trận theo `(round_index,position)`. Mỗi node có `match: MatchRead` W45, tọa độ, `next_round/next_position/next_slot` và `next_match_id` được resolve từ metadata; NULL ở chung kết. Không dùng phân trang match-list mặc định 50 để dựng bracket.
- GET `/bracket/standings` công khai: `{bracket_id,status,items,total,offset,limit}`. Status `PROVISIONAL`, `FINAL` hoặc `CANCELLED`; offset ≥0, limit 1–100 mặc định 50. Mỗi item `{team:{team_id,name},rank:null|int,matches_played,wins,losses}`; sort rank tăng dần NULL cuối, hòa hạng theo thứ tự team_order; không thêm points/tiền thưởng.
- Bảng hạng chỉ tính COMPLETED managed matches: đội chưa loại rank NULL, thua vòng R đội hạng R/2+1; winner chung kết hạng 1; không tự chia hạng 3/4. Chung kết COMPLETED và giải không CANCELLED → FINAL. Mỗi public response phải đọc một snapshot nhất quán (một SELECT dữ liệu nguồn, hoặc transaction REPEATABLE READ ngay từ đầu); không ghép các commit khác nhau.
- Lỗi theo FastAPI: 401 auth → 422 body → 404 tài nguyên → 403 quyền → 409 lifecycle/existing/preview → 422 liên kết. Validation payload chạy trước handler; helper đầu vào kiểm lifecycle trước liên kết. Create replay vẫn kiểm quyền hiện tại; không phải đường ghi mới vào giải kết thúc.
- Capability giải hiện đã có **`can_create_bracket`**, luôn `private, no-store`; UI dùng để hiển thị preview/tạo, API phải enforce lại. Referee đúng assignment vẫn không được tạo; đội của người gọi không tự cấp quyền.
- Response preview/create cũng phải `Cache-Control: private, no-store` khi W46-03 nối route, vì có token và dữ liệu quản lý; GET công khai không trả preview token.

## 6. Bàn giao W46-02

- Dùng helper khóa source/đích theo ID. Không gọi helper W45 khóa source trước rồi mới khóa đích có ID nhỏ hơn. Mọi mutation cùng giải vẫn dùng khóa tournament làm điểm tuần tự chung.
- Result + slot winner + audit cùng transaction, lỗi bất kỳ bước rollback cả ba. Replay cùng kết quả kiểm state đã nhất quán, không thêm audit/đội; khác kết quả 409. Slot khác đội hoặc đích không còn PENDING khi cần điền → 409.
- Bảo vệ API/capability W45 với match có metadata: chỉ sửa scheduled_at khi PENDING; cấm xóa/hủy và đổi stage/round/đội. Chặn tạo match thủ công vào stage đã có header, kể cả trước khi đọc node.
- Guard COMPLETED giải phải xét toàn bộ trận dở và chung kết bracket; CANCELLED giữ lịch sử và chặn ghi. Không tự hoàn tất giải khi ghi kết quả chung kết.
- Đây là phần việc W46-02, chưa có enforcement trong lifecycle/result API của W46-01. Không đưa bracket vào sử dụng qua SQL hoặc route ngoài contract trước khi các guard này được tích hợp.
- PR tạo bracket W46-03 phải ghi dependency vào các guard W46-02 và không merge route tạo trước guard. Có thể dựng preview/read và test độc lập trên branch trong lúc chờ; không để bracket đã tạo đi qua mutation W45 chưa được bảo vệ.
