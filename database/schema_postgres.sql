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
    created_by INT REFERENCES users(user_id) ON DELETE SET NULL,
    roster_locked_at TIMESTAMPTZ,
    roster_locked_by INT CONSTRAINT fk_tournaments_roster_locked_by REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (format IN ('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN')),
    CONSTRAINT ck_tournaments_status CHECK (status IN ('UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT ck_tournaments_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_tournaments_roster_lock CHECK (roster_locked_at IS NOT NULL OR roster_locked_by IS NULL)
);
CREATE TABLE stages (
    stage_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    sequence_order INT NOT NULL,
    CONSTRAINT uq_stages_tournament_order UNIQUE (tournament_id, sequence_order),
    CONSTRAINT ck_stages_positive_order CHECK (sequence_order > 0),
    CONSTRAINT uq_stages_id_tournament UNIQUE (stage_id, tournament_id),
    CONSTRAINT ck_stages_name CHECK (length(trim(name)) BETWEEN 1 AND 80)
);
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    stage_id INT NOT NULL CONSTRAINT fk_matches_stage REFERENCES stages(stage_id) ON DELETE RESTRICT,
    round_no INT NOT NULL,
    team1_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    team2_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    winner_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    score_team1 INT NOT NULL DEFAULT 0,
    score_team2 INT NOT NULL DEFAULT 0,
    next_match_id INT REFERENCES matches(match_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    scheduled_at TIMESTAMPTZ,
    CONSTRAINT fk_matches_stage_tournament FOREIGN KEY (stage_id, tournament_id)
        REFERENCES stages(stage_id, tournament_id) ON DELETE RESTRICT,
    CONSTRAINT ck_matches_status CHECK (status IN ('PENDING', 'ONGOING', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT ck_matches_round CHECK (round_no > 0),
    CONSTRAINT ck_matches_scores CHECK (score_team1 >= 0 AND score_team2 >= 0),
    CONSTRAINT ck_matches_distinct_teams CHECK (team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id),
    CONSTRAINT ck_matches_winner_team CHECK (winner_id IS NULL OR (team1_id IS NOT NULL AND team2_id IS NOT NULL AND winner_id IN (team1_id, team2_id))),
    CONSTRAINT ck_matches_result CHECK ((status = 'COMPLETED' AND winner_id IS NOT NULL)
                                        OR (status <> 'COMPLETED' AND winner_id IS NULL))
);
CREATE INDEX ix_matches_tournament_stage ON matches (tournament_id, stage_id, round_no, match_id);
CREATE INDEX ix_matches_team1 ON matches (team1_id);
CREATE INDEX ix_matches_team2 ON matches (team2_id);
CREATE TABLE tournament_rosters (
    roster_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    team_id INT NOT NULL CONSTRAINT fk_rosters_team REFERENCES teams(team_id) ON DELETE RESTRICT,
    user_id INT NOT NULL CONSTRAINT fk_rosters_user REFERENCES users(user_id) ON DELETE RESTRICT,
    role_in_team VARCHAR(30) NOT NULL DEFAULT 'PLAYER',
    display_name VARCHAR(100),
    CONSTRAINT uq_rosters_tournament_user UNIQUE (tournament_id, user_id),
    CONSTRAINT ck_rosters_role CHECK (role_in_team IN ('PLAYER', 'SUBSTITUTE')),
    CONSTRAINT ck_rosters_display_name CHECK (display_name IS NULL OR length(trim(display_name)) > 0)
);
CREATE INDEX ix_rosters_tournament_team ON tournament_rosters(tournament_id, team_id);
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

-- W46-01 managed bracket metadata; legacy matches are not adopted.
ALTER TABLE matches ADD CONSTRAINT uq_matches_bracket_identity UNIQUE (match_id, tournament_id, stage_id);
CREATE TABLE tournament_brackets (
    bracket_id SERIAL NOT NULL,
    tournament_id INTEGER NOT NULL,
    stage_id INTEGER NOT NULL,
    team_count INTEGER NOT NULL,
    round_count INTEGER NOT NULL,
    team_order JSON NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (bracket_id),
    CONSTRAINT uq_bracket_tournament UNIQUE (tournament_id),
    CONSTRAINT uq_bracket_stage UNIQUE (stage_id),
    CONSTRAINT uq_bracket_identity UNIQUE (bracket_id, tournament_id, stage_id, round_count),
    CONSTRAINT ck_bracket_size CHECK (team_count IN (2,4,8,16,32,64) AND team_count = (1 << round_count) AND round_count BETWEEN 1 AND 6),
    FOREIGN KEY(tournament_id) REFERENCES tournaments (tournament_id) ON DELETE RESTRICT,
    FOREIGN KEY(stage_id) REFERENCES stages (stage_id) ON DELETE RESTRICT,
    FOREIGN KEY(created_by) REFERENCES users (user_id) ON DELETE RESTRICT
);
CREATE TABLE bracket_matches (
    match_id INTEGER NOT NULL,
    bracket_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    stage_id INTEGER NOT NULL,
    round_count INTEGER NOT NULL,
    round_index INTEGER NOT NULL,
    position INTEGER NOT NULL,
    next_round INTEGER,
    next_position INTEGER,
    next_slot INTEGER,
    PRIMARY KEY (match_id),
    CONSTRAINT fk_bracket_match_identity FOREIGN KEY(match_id, tournament_id, stage_id) REFERENCES matches (match_id, tournament_id, stage_id) ON DELETE RESTRICT,
    CONSTRAINT fk_bracket_match_bracket FOREIGN KEY(bracket_id, tournament_id, stage_id, round_count) REFERENCES tournament_brackets (bracket_id, tournament_id, stage_id, round_count) ON DELETE RESTRICT,
    CONSTRAINT uq_bracket_match_position UNIQUE (bracket_id, round_index, position),
    CONSTRAINT fk_bracket_match_destination FOREIGN KEY(bracket_id, next_round, next_position) REFERENCES bracket_matches (bracket_id, round_index, position) ON DELETE RESTRICT,
    CONSTRAINT ck_bracket_match_position CHECK (round_count BETWEEN 1 AND 6 AND round_index BETWEEN 1 AND round_count AND position BETWEEN 1 AND (1 << (round_count-round_index))),
    CONSTRAINT ck_bracket_match_destination CHECK ((round_index = round_count AND next_round IS NULL AND next_position IS NULL AND next_slot IS NULL) OR (round_index < round_count AND next_round IS NOT NULL AND next_position IS NOT NULL AND next_slot IS NOT NULL AND next_round = round_index+1 AND next_position = (position+1)/2 AND next_slot = 1+((position-1)%2)))
);
