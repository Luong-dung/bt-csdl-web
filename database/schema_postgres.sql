CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);
CREATE TABLE permissions (
    permission_id SERIAL PRIMARY KEY,
    permission_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
);
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    role_id INT NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
    username CITEXT NOT NULL UNIQUE,
    email CITEXT NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(100) NOT NULL DEFAULT '',
    avatar_url VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE role_assignments (
    assignment_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'GLOBAL',
    scope_id INT,
    UNIQUE (user_id, role_id, scope_type, scope_id)
);
CREATE TABLE audit_logs (
    log_id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE publishers (
    publisher_id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE
);
CREATE TABLE games (
    game_id SERIAL PRIMARY KEY,
    publisher_id INT NOT NULL REFERENCES publishers(publisher_id),
    name VARCHAR(120) NOT NULL UNIQUE,
    slug VARCHAR(120) NOT NULL UNIQUE
);
CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE
);
CREATE TABLE competition_areas (
    area_id SERIAL PRIMARY KEY,
    parent_id INT REFERENCES competition_areas(area_id),
    name VARCHAR(120) NOT NULL,
    code VARCHAR(30) NOT NULL UNIQUE
);
CREATE TABLE organizations (
    organization_id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE
);
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    organization_id INT REFERENCES organizations(organization_id) ON DELETE SET NULL,
    game_id INT NOT NULL REFERENCES games(game_id),
    name VARCHAR(100) NOT NULL,
    tag VARCHAR(10) NOT NULL UNIQUE,
    logo_url VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE team_memberships (
    membership_id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_in_team VARCHAR(30) NOT NULL DEFAULT 'PLAYER',
    joined_date DATE NOT NULL DEFAULT CURRENT_DATE,
    left_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    CHECK (status IN ('ACTIVE', 'TRANSFERRED', 'TERMINATED', 'RETIRED'))
);
CREATE UNIQUE INDEX uq_one_active_team_per_user ON team_memberships(user_id) WHERE status = 'ACTIVE';
CREATE TABLE tournaments (
    tournament_id SERIAL PRIMARY KEY,
    game_id INT NOT NULL REFERENCES games(game_id),
    area_id INT REFERENCES competition_areas(area_id),
    name VARCHAR(150) NOT NULL,
    format VARCHAR(30) NOT NULL DEFAULT 'SINGLE_ELIM',
    start_date DATE NOT NULL,
    end_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'UPCOMING',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (format IN ('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN'))
);
CREATE TABLE stages (
    stage_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    sequence_order INT NOT NULL
);
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    stage_id INT NOT NULL REFERENCES stages(stage_id) ON DELETE CASCADE,
    round_no INT NOT NULL,
    team1_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    team2_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    winner_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    score_team1 INT NOT NULL DEFAULT 0,
    score_team2 INT NOT NULL DEFAULT 0,
    next_match_id INT REFERENCES matches(match_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    CHECK (team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id)
);
CREATE TABLE tournament_rosters (
    roster_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_in_team VARCHAR(30) NOT NULL DEFAULT 'PLAYER',
    UNIQUE (tournament_id, user_id)
);
CREATE TABLE tournament_standings (
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    final_rank INT NOT NULL,
    matches_played INT NOT NULL DEFAULT 0,
    wins INT NOT NULL DEFAULT 0,
    losses INT NOT NULL DEFAULT 0,
    points INT NOT NULL DEFAULT 0,
    prize_money NUMERIC(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tournament_id, team_id)
);
