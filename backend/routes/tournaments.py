from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from middleware.auth import require_role
from modules.catalog.models import CompetitionArea, Game
from modules.identity.models import User
from modules.tournaments.models import Tournament

router = APIRouter(prefix="/api/v1/tournaments", tags=["Tournaments"])

# Ids outside the INTEGER range make PostgreSQL raise instead of returning no row.
INT_MAX = 2147483647
DbId = Annotated[int, Field(gt=0, le=INT_MAX)]
TournamentFormat = Literal["SINGLE_ELIM", "DOUBLE_ELIM", "ROUND_ROBIN"]


class TournamentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TournamentCreate(TournamentInput):
    name: str = Field(min_length=3, max_length=150)
    game_id: DbId
    area_id: DbId | None = None
    format: TournamentFormat = "SINGLE_ELIM"
    start_date: date
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Ngày kết thúc không được trước ngày bắt đầu")
        return self


class TournamentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tournament_id: int
    name: str
    game_id: int
    area_id: int | None
    format: str
    start_date: date
    end_date: date | None
    status: str
    description: str | None
    created_at: datetime


def ensure_references(db: Session, data: TournamentCreate):
    if db.get(Game, data.game_id) is None:
        raise HTTPException(status_code=422, detail="Game không tồn tại")
    if data.area_id is not None and db.get(CompetitionArea, data.area_id) is None:
        raise HTTPException(status_code=422, detail="Khu vực không tồn tại")


@router.get("", response_model=list[TournamentRead])
def list_tournaments(
    game_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
    area_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
    db: Session = Depends(get_db),
):
    query = select(Tournament).order_by(Tournament.start_date.desc(), Tournament.tournament_id.desc())
    if game_id is not None:
        query = query.where(Tournament.game_id == game_id)
    if area_id is not None:
        query = query.where(Tournament.area_id == area_id)
    return db.scalars(query).all()


@router.post("", response_model=TournamentRead, status_code=status.HTTP_201_CREATED)
def create_tournament(
    data: TournamentCreate,
    _: User = Depends(require_role("ADMIN", "ORGANIZER")),
    db: Session = Depends(get_db),
):
    ensure_references(db, data)
    tournament = Tournament(**data.model_dump())
    db.add(tournament)
    # Fallback for a game/area deleted between the check and the insert.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu vi phạm ràng buộc, vui lòng kiểm tra lại")
    db.refresh(tournament)
    return tournament


@router.get("/{tournament_id}", response_model=TournamentRead)
def get_tournament(tournament_id: Annotated[int, Path(gt=0, le=INT_MAX)], db: Session = Depends(get_db)):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament
