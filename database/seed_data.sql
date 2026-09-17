-- ========================================================
-- 1. BẢNG ROLES
-- ========================================================
INSERT INTO roles (role_id, role_name) VALUES
(1, 'ADMIN'),
(2, 'ORGANIZER'),
(3, 'TEAM_MANAGER'),
(4, 'REFEREE'),
(5, 'PLAYER'),
(6, 'VIEWER'),
(7, 'CASTER');

-- ========================================================
-- 2. LÀM LẠI BẢNG TEAMS (8 Đội chuẩn từ danh sách)
-- ========================================================
TRUNCATE TABLE teams;
INSERT INTO teams (team_id, team_name, tag, logo_url) VALUES
(1, 'Saigon Phantom', 'SGP', 'https://logo.com/sgp.png'),
(2, 'One Star Esports', '1S', 'https://logo.com/1s.png'),
(3, 'FPT x Flash', 'FPT', 'https://logo.com/fpt.png'),
(4, 'GAM Esports', 'GAM', 'https://logo.com/gam.png'),
(5, 'FPT Polytechnic', 'FPL', 'https://logo.com/fpl.png'),
(6, 'BOX Gaming', 'BOX', 'https://logo.com/box.png'),
(7, 'Team Secret', 'TS', 'https://logo.com/ts.png'),
(8, 'RRQ', 'RRQ', 'https://logo.com/rrq.png');

-- ========================================================
-- 3. LÀM LẠI BẢNG USERS (Giữ ID Ban quản trị + Thêm 53 Player)
-- ========================================================
TRUNCATE TABLE users;
INSERT INTO users (user_id, role_id, username, password_hash, real_name, email, avatar_url) VALUES
-- --- STAFF (Giữ nguyên ID cũ) ---
(1, 1, 'admin_super', '$2b$10$EpRnTzVlq...', 'Lường Tiến Dũng', 'admin@esports.vn', 'https://avatar.com/admin.png'),
(2, 4, 'referee_Doanh', '$2b$10$EpRnTzVlq...', 'Nguyễn Quốc Doanh', 'referee@esports.vn', 'https://avatar.com/ref.png'),
(3, 2, 'organizer_Tung_Duong', '$2b$10$EpRnTzVlq...', 'Tùng Dương', 'organizer@esports.vn', 'https://avatar.com/organizer.png'),
(12, 3, 'manager_yamate', '$2b$10$EpRnTzVlq...', 'Phan Anh Dũng', 'yamate@sgp.vn', 'https://avatar.com/yamate.png'),
(13, 3, 'manager_quyhai', '$2b$10$EpRnTzVlq...', 'Trần Quý Hải', 'quyhai@1s.vn', 'https://avatar.com/quyhai.png'),
(14, 6, 'viewer_Sahur', '$2b$10$EpRnTzVlq...', 'Nguyễn Sahur', 'viewer@esports.vn', 'https://avatar.com/viewer.png'),
(15, 7, 'caster_Dong', '$2b$10$EpRnTzVlq...', 'Đồng Đức Dương', 'caster@esports.vn', 'https://avatar.com/caster.png'),

-- --- ĐỘI 1: SAIGON PHANTOM (7 người) ---
(4, 5, 'sgp_khoa', '$2b$10$EpRnTzVlq...', 'Đinh Tấn Khoa', 'khoa@sgp.vn', 'https://avatar.com/khoa.png'),
(5, 5, 'sgp_nolan', '$2b$10$EpRnTzVlq...', 'Nguyễn Hoàng Em', 'nolan@sgp.vn', 'https://avatar.com/nolan.png'),
(6, 5, 'sgp_fish', '$2b$10$EpRnTzVlq...', 'Lương Hoàng Phúc', 'fish@sgp.vn', 'https://avatar.com/fish.png'),
(7, 5, 'sgp_yuu', '$2b$10$EpRnTzVlq...', 'Nguyễn Lê Long Nhật', 'yuu@sgp.vn', 'https://avatar.com/yuu.png'),
(8, 5, 'sgp_shin', '$2b$10$EpRnTzVlq...', 'Nguyễn Như Đức', 'shin@sgp.vn', 'https://avatar.com/shin.png'),
(9, 5, 'sgp_23xjuly', '$2b$10$EpRnTzVlq...', 'Nguyễn Đình Chắc', '23xjuly@sgp.vn', 'https://avatar.com/23xjuly.png'),
(10, 5, 'sgp_soul', '$2b$10$EpRnTzVlq...', 'Đinh Xuân Sung', 'soul@sgp.vn', 'https://avatar.com/soul.png'),

-- --- ĐỘI 2: ONE STAR ESPORTS (6 người - Bỏ qua ID 12-15) ---
(11, 5, '1s_libr4', '$2b$10$EpRnTzVlq...', 'Huỳnh Trung Nhựt', 'libr4@1s.vn', 'https://avatar.com/libr4.png'),
(16, 5, '1s_stark', '$2b$10$EpRnTzVlq...', 'Nguyễn Minh Thuận', 'stark@1s.vn', 'https://avatar.com/stark.png'),
(17, 5, '1s_zet', '$2b$10$EpRnTzVlq...', 'Đào Trần Xuân Thương', 'zet@1s.vn', 'https://avatar.com/zet.png'),
(18, 5, '1s_sea', '$2b$10$EpRnTzVlq...', 'Nguyễn Đức Toàn', 'sea@1s.vn', 'https://avatar.com/sea.png'),
(19, 5, '1s_spiris', '$2b$10$EpRnTzVlq...', 'Nguyễn Phước Thiện', 'spiris@1s.vn', 'https://avatar.com/spiris.png'),
(20, 5, '1s_nammilk', '$2b$10$EpRnTzVlq...', 'Nguyễn Hào Nam', 'nammilk@1s.vn', 'https://avatar.com/nammilk.png'),

-- --- ĐỘI 3: FPT x FLASH (7 người) ---
(21, 5, 'fpt_huyhoang', '$2b$10$EpRnTzVlq...', 'Nguyễn Huy Hoàng', 'huyhoang@fpt.vn', 'https://avatar.com/huyhoang.png'),
(22, 5, 'fpt_julius', '$2b$10$EpRnTzVlq...', 'Nguyễn Hồng Đăng', 'julius@fpt.vn', 'https://avatar.com/julius.png'),
(23, 5, 'fpt_maris', '$2b$10$EpRnTzVlq...', 'Nguyễn Quốc Huy', 'maris@fpt.vn', 'https://avatar.com/maris.png'),
(24, 5, 'fpt_betroc', '$2b$10$EpRnTzVlq...', 'Phạm Nhật Hào', 'betroc@fpt.vn', 'https://avatar.com/betroc.png'),
(25, 5, 'fpt_yutan', '$2b$10$EpRnTzVlq...', 'Lê Thành Duy', 'yutan@fpt.vn', 'https://avatar.com/yutan.png'),
(26, 5, 'fpt_nang', '$2b$10$EpRnTzVlq...', 'Nguyễn Trung Kiên', 'nang@fpt.vn', 'https://avatar.com/nang.png'),
(27, 5, 'fpt_hieuduc', '$2b$10$EpRnTzVlq...', 'Đặng Nguyễn Hiếu Đức', 'hieuduc@fpt.vn', 'https://avatar.com/hieuduc.png'),

-- --- ĐỘI 4: GAM ESPORTS (7 người) ---
(28, 5, 'gam_adonis', '$2b$10$EpRnTzVlq...', 'Nguyễn Thái Sơn', 'adonis@gam.vn', 'https://avatar.com/adonis.png'),
(29, 5, 'gam_yiuling', '$2b$10$EpRnTzVlq...', 'Nguyễn Hiếu', 'yiuling@gam.vn', 'https://avatar.com/yiuling.png'),
(30, 5, 'gam_aliyah', '$2b$10$EpRnTzVlq...', 'Nguyễn Thanh Thi', 'aliyah@gam.vn', 'https://avatar.com/aliyah.png'),
(31, 5, 'gam_tienphat', '$2b$10$EpRnTzVlq...', 'Ngô Hà Tiến Phát', 'tienphat@gam.vn', 'https://avatar.com/tienphat.png'),
(32, 5, 'gam_phuhoang', '$2b$10$EpRnTzVlq...', 'Nguyễn Trần Hoàng Phú', 'phuhoang@gam.vn', 'https://avatar.com/phuhoang.png'),
(33, 5, 'gam_kuga', '$2b$10$EpRnTzVlq...', 'Lê Quang Thiện', 'kuga@gam.vn', 'https://avatar.com/kuga.png'),
(34, 5, 'gam_owen', '$2b$10$EpRnTzVlq...', 'Nguyễn Thiệu Thái Hoàng', 'owen@gam.vn', 'https://avatar.com/owen.png'),

-- --- ĐỘI 5: FPT POLYTECHNIC (6 người) ---
(35, 5, 'fpl_vit', '$2b$10$EpRnTzVlq...', 'Lê Văn Việt', 'vit@fpl.vn', 'https://avatar.com/vit.png'),
(36, 5, 'fpl_thanhduy', '$2b$10$EpRnTzVlq...', 'Nguyễn Thành Duy', 'thanhduy@fpl.vn', 'https://avatar.com/thanhduy.png'),
(37, 5, 'fpl_sleepy', '$2b$10$EpRnTzVlq...', 'Võ Minh Thắng', 'sleepy@fpl.vn', 'https://avatar.com/sleepy.png'),
(38, 5, 'fpl_sindhu', '$2b$10$EpRnTzVlq...', 'Đỗ Mạnh Hùng', 'sindhu@fpl.vn', 'https://avatar.com/sindhu.png'),
(39, 5, 'fpl_thekhang', '$2b$10$EpRnTzVlq...', 'Nguyễn Thế Khang', 'thekhang@fpl.vn', 'https://avatar.com/thekhang.png'),
(40, 5, 'fpl_chu', '$2b$10$EpRnTzVlq...', 'Hoàng Anh Khánh', 'chu@fpl.vn', 'https://avatar.com/chu.png'),

-- --- ĐỘI 6: BOX GAMING (6 người) ---
(41, 5, 'box_tringuyen', '$2b$10$EpRnTzVlq...', 'Nguyễn Minh Trí', 'tringuyen@box.vn', 'https://avatar.com/tringuyen.png'),
(42, 5, 'box_08qt', '$2b$10$EpRnTzVlq...', 'Phạm Quang Thắng', '08qt@box.vn', 'https://avatar.com/08qt.png'),
(43, 5, 'box_peak', '$2b$10$EpRnTzVlq...', 'Đinh Ngọc Sơn', 'peak@box.vn', 'https://avatar.com/peak.png'),
(44, 5, 'box_ciara', '$2b$10$EpRnTzVlq...', 'Đào Xuân Thọ', 'ciara@box.vn', 'https://avatar.com/ciara.png'),
(45, 5, 'box_mapu', '$2b$10$EpRnTzVlq...', 'Lương Quốc Tuấn', 'mapu@box.vn', 'https://avatar.com/mapu.png'),
(46, 5, 'box_chip', '$2b$10$EpRnTzVlq...', 'Võ Văn Tài', 'chip@box.vn', 'https://avatar.com/chip.png'),

-- --- ĐỘI 7: TEAM SECRET (7 người) ---
(47, 5, 'ts_acacia', '$2b$10$EpRnTzVlq...', 'Trần Văn Quân', 'acacia@ts.vn', 'https://avatar.com/acacia.png'),
(48, 5, 'ts_kaisa', '$2b$10$EpRnTzVlq...', 'Nguyễn Võ Phước Thịnh', 'kaisa@ts.vn', 'https://avatar.com/kaisa.png'),
(49, 5, 'ts_boka', '$2b$10$EpRnTzVlq...', 'Hồ Văn Thảo', 'boka@ts.vn', 'https://avatar.com/boka.png'),
(50, 5, 'ts_tnhan', '$2b$10$EpRnTzVlq...', 'Trần Văn Nhân', 'tnhan@ts.vn', 'https://avatar.com/tnhan.png'),
(51, 5, 'ts_tlinhhh', '$2b$10$EpRnTzVlq...', 'Nguyễn Sỹ Tuấn Linh', 'tlinhhh@ts.vn', 'https://avatar.com/tlinhhh.png'),
(52, 5, 'ts_trphuoc', '$2b$10$EpRnTzVlq...', 'Trần Trường Phước', 'trphuoc@ts.vn', 'https://avatar.com/trphuoc.png'),
(53, 5, 'ts_ducky', '$2b$10$EpRnTzVlq...', 'Lê Phúc Đức', 'ducky@ts.vn', 'https://avatar.com/ducky.png'),

-- --- ĐỘI 8: RRQ (7 người) ---
(54, 5, 'rrq_tkien', '$2b$10$EpRnTzVlq...', 'Đào Nguyễn Trung Kiên', 'tkien@rrq.vn', 'https://avatar.com/tkien.png'),
(55, 5, 'rrq_yang', '$2b$10$EpRnTzVlq...', 'Phạm Văn Thái Dương', 'yang@rrq.vn', 'https://avatar.com/yang.png'),
(56, 5, 'rrq_tack4', '$2b$10$EpRnTzVlq...', 'Dương Thành Đạt', 'tack4@rrq.vn', 'https://avatar.com/tack4.png'),
(57, 5, 'rrq_triet', '$2b$10$EpRnTzVlq...', 'Nguyễn Phan Hoài Triết', 'triet@rrq.vn', 'https://avatar.com/triet.png'),
(58, 5, 'rrq_karl', '$2b$10$EpRnTzVlq...', 'Nguyễn Thanh Toàn', 'karl@rrq.vn', 'https://avatar.com/karl.png'),
(59, 5, 'rrq_littleq', '$2b$10$EpRnTzVlq...', 'Trương Đình Quyền', 'littleq@rrq.vn', 'https://avatar.com/littleq.png'),
(60, 5, 'rrq_veritas', '$2b$10$EpRnTzVlq...', 'Bùi Minh Huy', 'veritas@rrq.vn', 'https://avatar.com/veritas.png');


-- ========================================================
-- 4. LÀM LẠI BẢNG TEAM_MEMBERSHIPS (Map 53 người chuẩn role)
-- ========================================================
TRUNCATE TABLE team_memberships;
INSERT INTO team_memberships (membership_id, team_id, user_id, role_in_team, joined_date, left_date, status) VALUES
-- SGP
(1, 1, 4, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(2, 1, 5, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(3, 1, 6, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(4, 1, 7, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(5, 1, 8, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(6, 1, 9, 'SUB', '2023-01-01', NULL, 'ACTIVE'),
(7, 1, 10, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- 1S
(8, 2, 11, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(9, 2, 16, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(10, 2, 17, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(11, 2, 18, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(12, 2, 19, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(13, 2, 20, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- FPT x Flash
(14, 3, 21, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(15, 3, 22, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(16, 3, 23, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(17, 3, 24, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(18, 3, 25, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(19, 3, 26, 'SUB', '2023-01-01', NULL, 'ACTIVE'),
(20, 3, 27, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- GAM
(21, 4, 28, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(22, 4, 29, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(23, 4, 30, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(24, 4, 31, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(25, 4, 32, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(26, 4, 33, 'SUB', '2023-01-01', NULL, 'ACTIVE'),
(27, 4, 34, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- FPoly
(28, 5, 35, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(29, 5, 36, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(30, 5, 37, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(31, 5, 38, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(32, 5, 39, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(33, 5, 40, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- BOX
(34, 6, 41, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(35, 6, 42, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(36, 6, 43, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(37, 6, 44, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(38, 6, 45, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(39, 6, 46, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- Secret
(40, 7, 47, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(41, 7, 48, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(42, 7, 49, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(43, 7, 50, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(44, 7, 51, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(45, 7, 52, 'SUB', '2023-01-01', NULL, 'ACTIVE'),
(46, 7, 53, 'SUB', '2023-01-01', NULL, 'ACTIVE'),

-- RRQ
(47, 8, 54, 'DS_LANE', '2023-01-01', NULL, 'ACTIVE'),
(48, 8, 55, 'JUNGLE', '2023-01-01', NULL, 'ACTIVE'),
(49, 8, 56, 'MID', '2023-01-01', NULL, 'ACTIVE'),
(50, 8, 57, 'AD_CARRY', '2023-01-01', NULL, 'ACTIVE'),
(51, 8, 58, 'SUPPORT', '2023-01-01', NULL, 'ACTIVE'),
(52, 8, 59, 'SUB', '2023-01-01', NULL, 'ACTIVE'),
(53, 8, 60, 'SUB', '2023-01-01', NULL, 'ACTIVE');

-- Cập nhật Quản lý (ID 12, 13)
(54, 1, 12, 'MANAGER', '2019-01-01', NULL, 'ACTIVE'),
(55, 2, 13, 'MANAGER', '2021-01-01', NULL, 'ACTIVE');

-- ========================================================
-- 5. BẢNG TOURNAMENTS (3 Trạng thái giải)
-- ========================================================
INSERT INTO tournaments (tournament_id, title, format, start_date, end_date, status) VALUES
(1, 'Đấu Trường Danh Vọng Mùa Đông 2025', 'SINGLE_ELIM', '2025-08-15', '2025-10-26', 'FINISHED'),
(2, 'Đấu Trường Danh Vọng Mùa Xuân 2026', 'SINGLE_ELIM', '2026-02-20', '2026-05-10', 'ONGOING'),
(3, 'Đấu Trường Danh Vọng Mùa Đông 2026', 'SINGLE_ELIM', '2026-08-15', '2026-10-30', 'UPCOMING');

-- ========================================================
-- 6. BẢNG TOURNAMENT_ROSTERS (Danh sách đăng ký mùa)
-- ========================================================
INSERT INTO tournament_rosters (tournament_id, team_id, user_id, is_captain) VALUES
-- ===== GIẢI 1 (Mùa Đông 2025 - FINISHED) =====
-- Team 1: SGP (ID: 4 -> 10)
(1, 1, 4, FALSE), (1, 1, 5, FALSE), (1, 1, 6, FALSE), (1, 1, 7, TRUE), (1, 1, 8, FALSE), (1, 1, 9, FALSE), (1, 1, 10, FALSE),
-- Team 2: 1S (ID: 11, 16 -> 20)
(1, 2, 11, FALSE), (1, 2, 16, TRUE), (1, 2, 17, FALSE), (1, 2, 18, FALSE), (1, 2, 19, FALSE), (1, 2, 20, FALSE),
-- Team 3: FPT x Flash (ID: 21 -> 27)
(1, 3, 21, FALSE), (1, 3, 22, FALSE), (1, 3, 23, TRUE), (1, 3, 24, FALSE), (1, 3, 25, FALSE), (1, 3, 26, FALSE), (1, 3, 27, FALSE),
-- Team 4: GAM (ID: 28 -> 34)
(1, 4, 28, FALSE), (1, 4, 29, FALSE), (1, 4, 30, TRUE), (1, 4, 31, FALSE), (1, 4, 32, FALSE), (1, 4, 33, FALSE), (1, 4, 34, FALSE),

-- ===== GIẢI 2 (Mùa Xuân 2026 - ONGOING) =====
-- Team 1: SGP
(2, 1, 4, FALSE), (2, 1, 5, FALSE), (2, 1, 6, FALSE), (2, 1, 7, TRUE), (2, 1, 8, FALSE), (2, 1, 9, FALSE), (2, 1, 10, FALSE),
-- Team 2: 1S 
(2, 2, 11, FALSE), (2, 2, 16, TRUE), (2, 2, 17, FALSE), (2, 2, 18, FALSE), (2, 2, 19, FALSE), (2, 2, 20, FALSE),
-- Team 3: FPT x Flash
(2, 3, 21, FALSE), (2, 3, 22, FALSE), (2, 3, 23, TRUE), (2, 3, 24, FALSE), (2, 3, 25, FALSE), (2, 3, 26, FALSE), (2, 3, 27, FALSE),
-- Team 4: GAM
(2, 4, 28, FALSE), (2, 4, 29, FALSE), (2, 4, 30, TRUE), (2, 4, 31, FALSE), (2, 4, 32, FALSE), (2, 4, 33, FALSE), (2, 4, 34, FALSE);

-- ========================================================
-- 7. BẢNG STAGES
-- ========================================================
INSERT INTO stages (stage_id, tournament_id, stage_name, sequence_order) VALUES
(1, 1, 'Playoffs - Bán Kết', 1),
(2, 1, 'Playoffs - Chung Kết', 2),
(3, 2, 'Playoffs - Bán Kết', 1),
(4, 2, 'Playoffs - Chung Kết', 2);

-- ========================================================
-- 8. BẢNG MATCHES (Nhánh đấu tự tham chiếu next_match_id)
-- ========================================================
-- [Giải 1 - FINISHED]: Trận 3 Chung kết (BO7), Trận 1 và 2 Bán kết (BO5)
INSERT INTO matches (match_id, tournament_id, stage_id, round_no, team1_id, team2_id, winner_id, score_team1, score_team2, next_match_id, status) VALUES
(3, 1, 2, 2, 1, 2, 1, 4, 3, NULL, 'FINISHED'), -- SGP thắng 1S 4-3 nghẹt thở ở Chung kết
(1, 1, 1, 1, 1, 4, 1, 3, 0, 3, 'FINISHED'),    -- SGP đè bẹp GAM 3-0 ở Bán kết 1 -> vào trận 3
(2, 1, 1, 1, 2, 3, 2, 3, 2, 3, 'FINISHED');    -- 1S thắng FPT 3-2 ở Bán kết 2 -> vào trận 3

-- [Giải 2 - ONGOING]: Trận 6 Chung kết sẵn sàng, Trận 4 và 5 đã xong Bán kết
INSERT INTO matches (match_id, tournament_id, stage_id, round_no, team1_id, team2_id, winner_id, score_team1, score_team2, next_match_id, status) VALUES
(6, 2, 4, 2, 1, 2, NULL, 0, 0, NULL, 'READY'), -- Chung kết trong mơ SGP vs 1S chưa đánh
(4, 2, 3, 1, 1, 3, 1, 3, 1, 6, 'FINISHED'),    -- SGP thắng FPT 3-1
(5, 2, 3, 1, 2, 4, 2, 3, 0, 6, 'FINISHED');    -- 1S thắng GAM 3-0

-- ========================================================
-- 9. BẢNG TOURNAMENT_STANDINGS (Snapshot - Chỉ giải FINISHED mới có)
-- ========================================================
INSERT INTO tournament_standings (tournament_id, team_id, final_rank, matches_played, wins, losses, points, prize_money) VALUES
(1, 1, 1, 2, 2, 0, 6, 1800000000.00), -- SGP Vô địch (1 tỷ 8)
(1, 2, 2, 2, 1, 1, 3, 1000000000.00), -- 1S Á quân (1 tỷ) - Đã fix lại hạng 2
(1, 3, 3, 1, 0, 1, 0, 600000000.00),  -- FPT Hạng 3 (600 triệu)
(1, 4, 4, 1, 0, 1, 0, 400000000.00);  -- GAM Hạng 4 (400 triệu)

-- 1. Thêm team vào bảng TEAMS (Lấy ID = 9)
INSERT INTO teams (team_id, team_name, tag, logo_url) VALUES
(9, 'team_csdlweb', 'CSDL', 'https://logo.com/csdl.png');

-- 2. Ghi nhận lịch sử thi đấu và giải tán vào TEAM_MEMBERSHIPS
-- (Tận dụng luôn ID của Admin, Trọng tài, BTC, Caster đã có)
INSERT INTO team_memberships (membership_id, team_id, user_id, role_in_team, joined_date, left_date, status) VALUES
(56, 9, 1, 'A+', '2021-01-01', '2022-12-31', 'DISBANDED'),  -- Lường Tiến Dũng (ID 1)
(57, 9, 2, 'DI_TU', '2021-01-01', '2022-12-31', 'DISBANDED'),   -- Nguyễn Quốc Doanh (ID 2)
(58, 9, 15, 'THAM_TU', '2021-01-01', '2022-12-31', 'DISBANDED'),     -- Đồng Đức Dương (ID 15)
(59, 9, 3, 'DI_TU', '2021-01-01', '2022-12-31', 'DISBANDED');  -- Tùng Dương (ID 3)