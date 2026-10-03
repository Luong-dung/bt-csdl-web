-- ========================================================
-- POSTGRESQL SCHEMA FOR ESPORTS TOURNAMENT
-- ========================================================

DROP TABLE IF EXISTS tournament_standings CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS stages CASCADE;
DROP TABLE IF EXISTS tournament_rosters CASCADE;
DROP TABLE IF EXISTS tournaments CASCADE;
DROP TABLE IF EXISTS team_memberships CASCADE;
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;

-- 1. BẢNG PHÂN QUYỀN
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

-- 2. BẢNG NGƯỜI DÙNG / TUYỂN THỦ
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    role_id INT NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(100) DEFAULT '',
    email VARCHAR(100) NOT NULL UNIQUE,
    avatar_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT
);

-- 3. BẢNG ĐỘI TUYỂN
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL UNIQUE,
    tag VARCHAR(10) NOT NULL UNIQUE,
    logo_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. BẢNG QUẢN LÝ THÀNH VIÊN & CHUYỂN NHƯỢNG (SCD)
CREATE TABLE team_memberships (
    membership_id SERIAL PRIMARY KEY,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    role_in_team VARCHAR(50) DEFAULT 'PLAYER',
    joined_date DATE NOT NULL,
    left_date DATE NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'TRANSFERRED', 'TERMINATED', 'DISBANDED', 'RETIRED')),
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 5. BẢNG GIẢI ĐẤU
CREATE TABLE tournaments (
    tournament_id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    format VARCHAR(50) NOT NULL DEFAULT 'SINGLE_ELIM' CHECK (format IN ('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN')),
    start_date DATE NOT NULL,
    end_date DATE NULL,
    status VARCHAR(50) DEFAULT 'UPCOMING' CHECK (status IN ('UPCOMING', 'ONGOING', 'FINISHED'))
);

-- 6. BẢNG ĐỘI HÌNH ĐĂNG KÝ THEO MÙA GIẢI
CREATE TABLE tournament_rosters (
    roster_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    is_captain BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT uq_tournament_player UNIQUE (tournament_id, user_id)
);

-- 7. BẢNG GIAI ĐOẠN GIẢI ĐẤU
CREATE TABLE stages (
    stage_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL,
    stage_name VARCHAR(50) NOT NULL,
    sequence_order INT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE
);

-- 8. BẢNG TRẬN ĐẤU (TỰ THAM CHIẾU NHÁNH ĐẤU)
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL,
    stage_id INT NOT NULL,
    round_no INT NOT NULL,
    team1_id INT NULL,
    team2_id INT NULL,
    winner_id INT NULL,
    score_team1 INT DEFAULT 0,
    score_team2 INT DEFAULT 0,
    next_match_id INT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'READY', 'PLAYING', 'FINISHED')),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    FOREIGN KEY (stage_id) REFERENCES stages(stage_id) ON DELETE CASCADE,
    FOREIGN KEY (team1_id) REFERENCES teams(team_id) ON DELETE SET NULL,
    FOREIGN KEY (team2_id) REFERENCES teams(team_id) ON DELETE SET NULL,
    FOREIGN KEY (winner_id) REFERENCES teams(team_id) ON DELETE SET NULL,
    FOREIGN KEY (next_match_id) REFERENCES matches(match_id) ON DELETE SET NULL,
    CONSTRAINT chk_different_teams CHECK (team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id)
);

-- 9. BẢNG SNAPSHOT BẢNG XẾP HẠNG CUỐI CÙNG (LƯU LỊCH SỬ)
CREATE TABLE tournament_standings (
    tournament_id INT NOT NULL,
    team_id INT NOT NULL,
    final_rank INT NOT NULL,
    matches_played INT DEFAULT 0,
    wins INT DEFAULT 0,
    losses INT DEFAULT 0,
    points INT DEFAULT 0,
    prize_money DECIMAL(12, 2) DEFAULT 0.00,
    PRIMARY KEY (tournament_id, team_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
);
