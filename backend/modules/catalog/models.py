from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from config.database import Base


class Publisher(Base):
    __tablename__ = "publishers"
    publisher_id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    games = relationship("Game", back_populates="publisher")


class Game(Base):
    __tablename__ = "games"
    game_id = Column(Integer, primary_key=True)
    publisher_id = Column(Integer, ForeignKey("publishers.publisher_id"), nullable=False)
    name = Column(String(120), nullable=False, unique=True)
    slug = Column(String(120), nullable=False, unique=True)
    publisher = relationship("Publisher", back_populates="games")


class Country(Base):
    __tablename__ = "countries"
    country_code = Column(String(2), primary_key=True)
    name = Column(String(120), nullable=False, unique=True)


class CompetitionArea(Base):
    __tablename__ = "competition_areas"
    area_id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("competition_areas.area_id"), nullable=True)
    name = Column(String(120), nullable=False)
    code = Column(String(30), nullable=False, unique=True)
    # W47-04 (W03-02): optional country of the area; a country in use cannot be removed.
    country_code = Column(String(2), ForeignKey("countries.country_code", ondelete="RESTRICT",
                                                name="fk_competition_areas_country"), nullable=True, index=True)
    parent = relationship("CompetitionArea", remote_side=[area_id])
