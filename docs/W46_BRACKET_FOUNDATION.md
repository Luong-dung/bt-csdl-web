# W46-01 — Nền tảng bracket và contract bàn giao

Code nền: W45; phạm vi nghiệp vụ theo [kế hoạch W46](./weeks/2026-W46.md). W46-01 cung cấp schema/helper/input/capability. **Cập nhật W46-02:** result API đã chuyển winner theo metadata và bảo vệ lifecycle, xem mục 7. **Cập nhật W46-03/-04:** preview/tạo bracket xem mục 8; GET bracket và bảng kết quả xem mục 9.

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
| `issue_preview_token(tid,fingerprint)` | JWT HS256 có purpose riêng, audience `bracket-preview` bắt buộc, giải, fingerprint và hạn 15 phút; không phải access token |
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
- W46-03/-04/-05 cần cho người dùng biết lý do không thể tạo (số đội không hỗ trợ, không có stage trống, đội chưa đủ điều kiện). Không coi capability hint là bằng chứng input hợp lệ; không chỉ hiển thị nút rồi bỏ qua lỗi 409/422. Góp ý review #89 được chuyển tiếp rõ sang phần API/UI này.
- Response preview/create cũng phải `Cache-Control: private, no-store` khi W46-03 nối route, vì có token và dữ liệu quản lý; GET công khai không trả preview token.

## 6. Bàn giao W46-02

- Dùng helper khóa source/đích theo ID. Không gọi helper W45 khóa source trước rồi mới khóa đích có ID nhỏ hơn. Mọi mutation cùng giải vẫn dùng khóa tournament làm điểm tuần tự chung.
- Result + slot winner + audit cùng transaction, lỗi bất kỳ bước rollback cả ba. Replay cùng kết quả kiểm state đã nhất quán, không thêm audit/đội; khác kết quả 409. Slot khác đội hoặc đích không còn PENDING khi cần điền → 409.
- Bảo vệ API/capability W45 với match có metadata: chỉ sửa scheduled_at khi PENDING; cấm xóa/hủy và đổi stage/round/đội. Chặn tạo match thủ công vào stage đã có header, kể cả trước khi đọc node.
- Guard COMPLETED giải phải xét toàn bộ trận dở và chung kết bracket; CANCELLED giữ lịch sử và chặn ghi. Không tự hoàn tất giải khi ghi kết quả chung kết.
- W46-01 ban đầu chỉ bàn giao contract, chưa enforce các guard này. W46-02 đã tích hợp vào result/lifecycle API theo mục 7; việc đưa route tạo vào sử dụng phải chờ các PR phụ thuộc được review/merge.
- PR tạo bracket W46-03 phải ghi dependency vào các guard W46-02 và không merge route tạo trước guard. Có thể dựng preview/read và test độc lập trên branch trong lúc chờ; không để bracket đã tạo đi qua mutation W45 chưa được bảo vệ.

## 7. Triển khai W46-02 — kết quả và lifecycle

- Vẫn dùng `PUT /api/v1/tournaments/{tid}/matches/{mid}/result`, body/MatchRead W45 giữ contract. `lock_bracket_match_context` khóa giải rồi source/đích theo match_id tăng dần, tải lại actor và quyền sau chờ. Legacy `next_match_id` không làm phát sinh chuyển đội.
- Source result + đúng slot đích + một audit `MATCH_RESULT_SUBMITTED` nằm trong một transaction. Lỗi audit, FK hoặc commit rollback cả ba. Chi tiết audit cũ giữ nguyên; match managed thêm `bracket_id` và `advancement={match_id,slot,before,after}`; chung kết `advancement=null`.
- Ghi mới chỉ khi giải/trận ONGOING. Đích phải PENDING, slot rỗng hoặc đã chứa cùng winner và slot còn lại không chứa chính winner. Không tự bắt đầu trận đích, không tự hoàn tất giải.
- Replay cùng kết quả trả 200, không audit/điền lại slot; đích đã bắt đầu vẫn replay được khi slot còn đúng winner. Slot bị mất/đổi thì 409, không tự sửa lại. Replay nhất quán sau COMPLETED/CANCELLED của giải là đọc thuần túy, vẫn kiểm quyền hiện tại; ghi kết quả mới bị chặn.
- Managed match chỉ PATCH `scheduled_at` khi PENDING; cấm mọi field cấu trúc kể cả gửi lại cùng giá trị, cấm DELETE và POST status CANCELLED. Capability trả `can_delete=false`, `can_cancel=false`, `editable_fields=["scheduled_at"]` khi còn sửa được; TBD không có `can_start`.
- Chặn POST match thủ công vào stage đã có header bracket và PATCH match thủ công sang stage đó bằng 409 trước khi ghi. Không dựa vào FK để biến lỗi thành 500. Cấm đổi format giải sau khi có bracket; capability giải bỏ field format tương ứng.
- Guard COMPLETED áp dụng mọi giải: không còn match PENDING/ONGOING ở bất cứ stage nào. Nếu có bracket, cần đủ N−1 metadata/match COMPLETED và một chung kết có winner hợp lệ; bracket thiếu node hoặc có trận CANCELLED bị chặn. `allowed_status_transitions` dùng cùng checker để ẩn COMPLETED khi chưa đạt. CANCELLED giữ nguyên trạng thái lịch sử của từng match và chặn ghi tiếp.
- Kiểm thử mới: 32 ca API và 6 ca PostgreSQL race bằng connection độc lập (hai bán kết, replay cùng/khác kết quả, chung kết/hoàn tất giải, hủy giải/kết quả, thu hồi trọng tài khi chờ). Coverage W45 được ghi riêng trong bảng tuần/work log.

## 8. Triển khai W46-03 — preview và tạo bracket

- Route: [`backend/routes/brackets.py`](../backend/routes/brackets.py). Phụ thuộc guard W46-02 (đã merge ở PR #90/#91) nên bracket vừa tạo không đi qua mutation W45 chưa bảo vệ.
- `POST /bracket/preview` body `BracketInput`: kiểm 404 → 403 (quản lý đúng giải/ADMIN) → 409 nếu giải đã có bracket → `ensure_bracket_input` (409 lifecycle/stage có trận, 422 stage sai giải/đội/game/PLAYER). Không khóa, không ghi DB/audit; luôn rollback. Response đúng mục 5 và **thêm `teams:[{team_id,name}]`** cùng thứ tự `team_ids` để UI hiển thị tên; tên chỉ để hiển thị, không thuộc fingerprint.
- `POST /bracket` body `BracketCreate`: `lock_bracket_context` (403 trước chờ và sau khi tải lại actor) → nếu đã có header: cùng stage + team_order trả 200 bracket hiện có, không ghi/audit, bỏ qua token (kể cả hết hạn/rác); khác input trả 409. Chưa có: validate live lại sau khóa, verify token theo fingerprint live (409 nếu token sai/hết hạn/khác giải/khác input/roster đổi), rồi ghi header + N−1 `Match` PENDING (`round_no=round_index`, vòng 1 có hai đội, vòng sau NULL, `next_match_id` NULL) + metadata theo vòng giảm dần + một audit `BRACKET_CREATED` (`resource=bracket`, details: tournament/bracket/stage, team_ids, team_count, round_count, match_ids). Trả 201. Lỗi bất kỳ, kể cả audit, rollback toàn bộ; `IntegrityError` → 409.
- Response tạo/replay là `BracketRead`: `{bracket_id,tournament_id,stage_id,team_count,round_count,team_ids,created_at,matches:[{round_index,position,next_round,next_position,next_slot,next_match_id,match:MatchRead}]}` theo `(round_index,position)`, `next_match_id` resolve từ metadata. W46-04 dùng lại DTO này cho GET công khai.
- **Sau review #92 (DUNG):** preview token mang `sub` = user đã xem preview; create gọi `verify_preview_token(..., user_id)` nên manager khác (kể cả ADMIN) dùng token đó bị 409 và phải tự preview. Từ W46-04 (re-review #92), `issue_preview_token`/`verify_preview_token` bắt buộc `user_id` và JWT bắt buộc claim `sub`, nên không route nào bỏ qua được ràng buộc này. `round_count` tính từ `len(team_ids)`, không dựa vào thứ tự plan; metadata flush theo từng vòng (chung kết trước), không flush từng node. Replay sau khi giải đã ONGOING và có kết quả vẫn trả 200 với trạng thái hiện tại, không ghi/audit.
- `PermissionCacheMiddleware` gắn `Cache-Control: private, no-store` cho **POST** `/bracket` và `/bracket/preview`, kể cả response lỗi; GET `/bracket` (W46-04) không bị gắn.
- Tạo đồng thời: hai request tuần tự hóa qua khóa giải; request sau thấy header nên cùng input → 200 cùng bracket, khác input → 409. Unique `uq_bracket_tournament/stage` là lớp bảo vệ cuối.
- Test mới: [`test_bracket_create.py`](../backend/tests/test_bracket_create.py) (25 ca: preview chỉ đọc, token gắn người preview, replay sau khi giải ONGOING, cây 2/4/8/64 đội đủ cạnh/slot, replay, token sai/hết hạn/khác giải/access token, roster đổi sau preview, validate lại khi tạo, ma trận lỗi 404/409/422, quyền viewer/TEAM_MANAGER/REFEREE TOURNAMENT/GLOBAL, ADMIN, fault injection audit, guard W46-02 trên bracket vừa tạo) và [`test_bracket_create_concurrency.py`](../backend/tests/test_bracket_create_concurrency.py) (2 ca PostgreSQL connection độc lập: cùng input → 201+200, khác input → 201+409; đúng một header/7 trận/7 node/1 audit).

## 9. Triển khai W46-04 — đọc bracket và bảng kết quả

- `GET /bracket` công khai (không cần đăng nhập, không gắn no-store): 404 khi giải không tồn tại hoặc chưa có bracket. Trả `BracketRead` (mục 8) đủ mọi node, tối đa 63, không phân trang, không có `preview_token`/`created_by`. Header và metadata bất biến sau khi tạo; trạng thái/đội/kết quả của mọi trận lấy từ **một SELECT** join metadata–match; tên đội/stage chỉ để hiển thị.
- `GET /bracket/standings?offset=0&limit=50` công khai: `{bracket_id,status,items,total,offset,limit}` và header `X-Total-Count`. Trạng thái giải và kết quả mọi trận được đọc trong **một SELECT**, nên `status` và hạng luôn cùng snapshot. `offset ≥ 0`, `limit` 1–100, sai → 422.
- Quy tắc: chỉ trận managed COMPLETED có winner, mỗi trận tính một lần cho played/wins/losses; trận manual, PENDING/ONGOING/CANCELLED không tính. Thua ở vòng r → hạng `2^(round_count−r)+1` (thua chung kết 2, bán kết 3, tứ kết 5…); thắng chung kết → 1; còn lại `rank=null`. Sắp rank tăng dần, NULL cuối, đồng hạng theo `team_order`. `status`: giải CANCELLED → `CANCELLED` (giữ hạng đã phát sinh làm lịch sử); chung kết COMPLETED → `FINAL`; còn lại `PROVISIONAL`. Không đọc/ghi `tournament_standings`, không points/tiền thưởng.
- GET không khóa, không ghi, không audit; luôn rollback phiên đọc.
- Test mới: [`test_bracket_read.py`](../backend/tests/test_bracket_read.py) (9 ca: công khai và trùng response tạo, 404, bảng 8 đội qua tứ kết/bán kết/chung kết với hạng 1/2/3/3/5×4, replay không đổi bảng, phân trang + `X-Total-Count`, trận manual không tính, giải hủy, lỗi phân trang, 64 đội đủ 63 trận và 64 dòng).
