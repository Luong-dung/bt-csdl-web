from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from modules.catalog.models import CompetitionArea, Game, Publisher

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


@router.get("/games")
def list_games(db: Session = Depends(get_db)):
    return db.scalars(select(Game).order_by(Game.name)).all()


@router.get("/publishers")
def list_publishers(db: Session = Depends(get_db)):
    return db.scalars(select(Publisher).order_by(Publisher.name)).all()


@router.get("/areas")
def list_areas(db: Session = Depends(get_db)):
    return db.scalars(select(CompetitionArea).order_by(CompetitionArea.name)).all()
