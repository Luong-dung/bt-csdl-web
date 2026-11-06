from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from config.database import Base


class Tournament(Base):
    __tablename__ = "tournaments"
    tournament_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    area_id = Column(Integer, ForeignKey("competition_areas.area_id"), nullable=True)
    name = Column(String(150), nullable=False)
    format = Column(String(30), nullable=False, default="SINGLE_ELIM")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="UPCOMING")
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    roster_locked_at = Column(DateTime(timezone=True), nullable=True)
    roster_locked_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL",
                                                   name="fk_tournaments_roster_locked_by"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    stages = relationship("Stage", back_populates="tournament", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("format IN ('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN')"),
        CheckConstraint("status IN ('UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED')", name="ck_tournaments_status"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_tournaments_dates"),
        CheckConstraint("roster_locked_at IS NOT NULL OR roster_locked_by IS NULL",
                        name="ck_tournaments_roster_lock"),
    )


class TournamentRegistration(Base):
    __tablename__ = "tournament_registrations"

    registration_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    submitted_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    cancelled_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("tournament_id", "team_id", name="uq_registration_tournament_team"),
        Index("ix_tournament_registrations_team_id", "team_id"),
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')", name="ck_registration_status"),
        CheckConstraint(
            "(status = 'PENDING' AND reviewed_at IS NULL AND cancelled_at IS NULL) OR "
            "(status IN ('APPROVED', 'REJECTED') AND reviewed_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL)",
            name="ck_registration_timestamps",
        ),
        CheckConstraint("status IN ('REJECTED', 'CANCELLED') OR rejection_reason IS NULL", name="ck_registration_reason"),
    )


class Stage(Base):
    __tablename__ = "stages"
    stage_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(80), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    tournament = relationship("Tournament", back_populates="stages")
    __table_args__ = (
        UniqueConstraint('tournament_id', 'sequence_order', name='uq_stages_tournament_order'),
        # Target of the composite FK proving a match's stage belongs to the same tournament.
        UniqueConstraint('stage_id', 'tournament_id', name='uq_stages_id_tournament'),
        CheckConstraint('sequence_order > 0', name='ck_stages_positive_order'),
        CheckConstraint('length(trim(name)) BETWEEN 1 AND 80', name='ck_stages_name'),
    )


class Match(Base):
    __tablename__ = "matches"
    match_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.stage_id", ondelete="RESTRICT",
                                         name="fk_matches_stage"), nullable=False)
    round_no = Column(Integer, nullable=False)
    team1_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    team2_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    winner_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    score_team1 = Column(Integer, nullable=False, default=0)
    score_team2 = Column(Integer, nullable=False, default=0)
    next_match_id = Column(Integer, ForeignKey("matches.match_id"), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    # W45: optional kick-off time, always stored as UTC (timezone-aware).
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    # Keep names/expressions in sync with migration b45a01c0ffee and database/schema_postgres.sql.
    __table_args__ = (
        ForeignKeyConstraint(["stage_id", "tournament_id"], ["stages.stage_id", "stages.tournament_id"],
                             ondelete="RESTRICT", name="fk_matches_stage_tournament"),
        CheckConstraint("status IN ('PENDING', 'ONGOING', 'COMPLETED', 'CANCELLED')", name="ck_matches_status"),
        CheckConstraint("round_no > 0", name="ck_matches_round"),
        CheckConstraint("score_team1 >= 0 AND score_team2 >= 0", name="ck_matches_scores"),
        CheckConstraint("team1_id IS NULL OR team2_id IS NULL OR team1_id <> team2_id",
                        name="ck_matches_distinct_teams"),
        CheckConstraint("winner_id IS NULL OR (team1_id IS NOT NULL AND team2_id IS NOT NULL AND winner_id IN (team1_id, team2_id))",
                        name="ck_matches_winner_team"),
        CheckConstraint("(status = 'COMPLETED' AND winner_id IS NOT NULL) OR "
                        "(status <> 'COMPLETED' AND winner_id IS NULL)", name="ck_matches_result"),
        Index("ix_matches_tournament_stage", "tournament_id", "stage_id", "round_no", "match_id"),
        Index("ix_matches_team1", "team1_id"),
        Index("ix_matches_team2", "team2_id"),
    )


class TournamentRoster(Base):
    __tablename__ = "tournament_rosters"
    roster_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="RESTRICT",
                                        name="fk_rosters_team"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="RESTRICT",
                                        name="fk_rosters_user"), nullable=False)
    role_in_team = Column(String(30), nullable=False, default="PLAYER")
    # Filled by roster writers; frozen at lock time, never reconstructed from membership.
    display_name = Column(String(100), nullable=True)
    __table_args__ = (
        UniqueConstraint("tournament_id", "user_id", name="uq_rosters_tournament_user"),
        Index("ix_rosters_tournament_team", "tournament_id", "team_id"),
        CheckConstraint("role_in_team IN ('PLAYER', 'SUBSTITUTE')", name="ck_rosters_role"),
        CheckConstraint("display_name IS NULL OR length(trim(display_name)) > 0",
                        name="ck_rosters_display_name"),
    )


class TournamentStanding(Base):
    __tablename__ = "tournament_standings"
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), primary_key=True)
    final_rank = Column(Integer, nullable=False)
    matches_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)
    prize_money = Column(Numeric(12, 2), nullable=False, default=0)
