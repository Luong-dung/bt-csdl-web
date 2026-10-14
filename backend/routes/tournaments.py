from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from middleware.auth import require_role
from modules.identity.models import User
from modules.tournaments.models import Tournament

router = APIRouter(prefix="/api/v1/tournaments", tags=["Tournaments"])


class TournamentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    game_id: int
    area_id: int | None = None
    format: str = "SINGLE_ELIM"
    start_date: date
    end_date: date | None = None
    description: str | None = None


@router.get("")
def list_tournaments(db: Session = Depends(get_db)):
    return db.scalars(select(Tournament).order_by(Tournament.start_date.desc())).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_tournament(
    data: TournamentCreate,
    _: User = Depends(require_role("ADMIN", "ORGANIZER")),
    db: Session = Depends(get_db),
):
    if data.format not in {"SINGLE_ELIM", "DOUBLE_ELIM", "ROUND_ROBIN"}:
        raise HTTPException(status_code=422, detail="Thể thức giải không hợp lệ")
    tournament = Tournament(**data.model_dump())
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return tournament


@router.get("/{tournament_id}")
def get_tournament(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament
