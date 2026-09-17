-- 1. BẢNG PHÂN QUYỀN
CREATE TABLE roles (
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

-- 2. BẢNG NGƯỜI DÙNG / TUYỂN THỦ
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    role_id INT NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    avatar_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

-- 3. BẢNG ĐỘI TUYỂN
CREATE TABLE teams (
    team_id INT PRIMARY KEY AUTO_INCREMENT,
    team_name VARCHAR(100) NOT NULL UNIQUE,
    tag VARCHAR(10) NOT NULL UNIQUE,
    logo_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. BẢNG QUẢN LÝ THÀNH VIÊN & CHUYỂN NHƯỢNG (SCD)
CREATE TABLE team_memberships (
    membership_id INT PRIMARY KEY AUTO_INCREMENT,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    role_in_team VARCHAR(50) DEFAULT 'PLAYER',
    joined_date DATE NOT NULL,
    left_date DATE NULL,
    status ENUM('ACTIVE', 'TRANSFERRED', 'TERMINATED', 'DISBANDED', 'RETIRED') DEFAULT 'ACTIVE',
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 5. BẢNG GIẢI ĐẤU
CREATE TABLE tournaments (
    tournament_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(150) NOT NULL,
    format ENUM('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN') NOT NULL DEFAULT 'SINGLE_ELIM',
    start_date DATE NOT NULL,
    end_date DATE NULL,
    status ENUM('UPCOMING', 'ONGOING', 'FINISHED') DEFAULT 'UPCOMING'
);

-- 6. BẢNG ĐỘI HÌNH ĐĂNG KÝ THEO MÙA GIẢI
CREATE TABLE tournament_rosters (
    roster_id INT PRIMARY KEY AUTO_INCREMENT,
    tournament_id INT NOT NULL,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    is_captain BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT uq_tournament_player UNIQUE (tournament_id, user_id)
);

-- 7. BẢNG GIAI ĐOẠN GIẢI ĐẤU
CREATE TABLE stages (
    stage_id INT PRIMARY KEY AUTO_INCREMENT,
    tournament_id INT NOT NULL,
    stage_name VARCHAR(50) NOT NULL,
    sequence_order INT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
);

-- 8. BẢNG TRẬN ĐẤU (TỰ THAM CHIẾU NHÁNH ĐẤU)
CREATE TABLE matches (
    match_id INT PRIMARY KEY AUTO_INCREMENT,
    tournament_id INT NOT NULL,
    stage_id INT NOT NULL,
    round_no INT NOT NULL,
    team1_id INT NULL,
    team2_id INT NULL,
    winner_id INT NULL,
    score_team1 INT DEFAULT 0,
    score_team2 INT DEFAULT 0,
    next_match_id INT NULL,
    status ENUM('PENDING', 'READY', 'PLAYING', 'FINISHED') DEFAULT 'PENDING',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (stage_id) REFERENCES stages(stage_id),
    FOREIGN KEY (team1_id) REFERENCES teams(team_id),
    FOREIGN KEY (team2_id) REFERENCES teams(team_id),
    FOREIGN KEY (winner_id) REFERENCES teams(team_id),
    FOREIGN KEY (next_match_id) REFERENCES matches(match_id),
    CONSTRAINT chk_different_teams CHECK (team1_id <> team2_id)
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
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);