from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from config.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    organization_id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, unique=True)
    teams = relationship("Team", back_populates="organization")


class Team(Base):
    __tablename__ = "teams"
    team_id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    name = Column(String(100), nullable=False)
    tag = Column(String(10), nullable=False, unique=True)
    logo_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    organization = relationship("Organization", back_populates="teams")
    memberships = relationship("TeamMembership", back_populates="team")


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    membership_id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role_in_team = Column(String(30), nullable=False, default="PLAYER")
    joined_date = Column(Date, default=date.today, nullable=False)
    left_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    team = relationship("Team", back_populates="memberships")
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", "joined_date"),
        Index(
            "uq_one_active_team_per_user", "user_id", unique=True,
            postgresql_where=(status == "ACTIVE"), sqlite_where=(status == "ACTIVE"),
        ),
    )
