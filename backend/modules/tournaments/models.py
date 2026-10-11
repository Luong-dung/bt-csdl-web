from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    stages = relationship("Stage", back_populates="tournament", cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("format IN ('SINGLE_ELIM', 'DOUBLE_ELIM', 'ROUND_ROBIN')"),)


class Stage(Base):
    __tablename__ = "stages"
    stage_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(80), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    tournament = relationship("Tournament", back_populates="stages")


class Match(Base):
    __tablename__ = "matches"
    match_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False)
    round_no = Column(Integer, nullable=False)
    team1_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    team2_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    winner_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    score_team1 = Column(Integer, nullable=False, default=0)
    score_team2 = Column(Integer, nullable=False, default=0)
    next_match_id = Column(Integer, ForeignKey("matches.match_id"), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")


class TournamentRoster(Base):
    __tablename__ = "tournament_rosters"
    roster_id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role_in_team = Column(String(30), nullable=False, default="PLAYER")


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
