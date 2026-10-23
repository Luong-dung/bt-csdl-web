from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.tournaments import get_managed_tournament
from middleware.auth import get_current_user, require_role
from modules.catalog.models import CompetitionArea, Game
from modules.identity.models import User
from modules.tournaments.models import Tournament, TournamentRegistration

router = APIRouter(prefix="/api/v1/tournaments", tags=["Tournaments"])

# Ids outside the INTEGER range make PostgreSQL raise instead of returning no row.
INT_MAX = 2147483647
DbId = Annotated[int, Field(gt=0, le=INT_MAX)]
TournamentId = Annotated[int, Path(gt=0, le=INT_MAX)]
TournamentFormat = Literal["SINGLE_ELIM", "DOUBLE_ELIM", "ROUND_ROBIN"]
TournamentStatus = Literal["UPCOMING", "ONGOING", "COMPLETED", "CANCELLED"]

# Allowed status changes; COMPLETED and CANCELLED are final and read-only.
TRANSITIONS = {
    "UPCOMING": {"ONGOING", "CANCELLED"},
    "ONGOING": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
ONGOING_EDITABLE = {"name", "description", "end_date"}
REQUIRED_FIELDS = {"name", "game_id", "format", "start_date"}


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
        if self.start_date < date.today():
            raise ValueError("Ngày bắt đầu không được ở quá khứ")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Ngày kết thúc không được trước ngày bắt đầu")
        return self


class TournamentUpdate(TournamentInput):
    name: str | None = Field(default=None, min_length=3, max_length=150)
    game_id: DbId | None = None
    area_id: DbId | None = None
    format: TournamentFormat | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_fields(self):
        if not self.model_fields_set:
            raise ValueError("Không có trường nào để cập nhật")
        if any(getattr(self, name) is None for name in self.model_fields_set & REQUIRED_FIELDS):
            raise ValueError("Tên, game, thể thức và ngày bắt đầu không được để trống")
        return self


class StatusChange(TournamentInput):
    status: TournamentStatus


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
    created_by: int | None
    created_at: datetime


def ensure_references(db: Session, game_id: int | None, area_id: int | None):
    if game_id is not None and db.get(Game, game_id) is None:
        raise HTTPException(status_code=422, detail="Game không tồn tại")
    if area_id is not None and db.get(CompetitionArea, area_id) is None:
        raise HTTPException(status_code=422, detail="Khu vực không tồn tại")


def commit_tournament(db: Session, tournament: Tournament, user: User, action: str,
                      before: dict, after: dict) -> Tournament:
    # Fallback for a game/area deleted between the check and the write.
    try:
        db.flush()
        record_audit(db, user.user_id, action, "tournament", {
            "tournament_id": tournament.tournament_id, "before": before, "after": after,
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu vi phạm ràng buộc, vui lòng kiểm tra lại")
    db.refresh(tournament)
    return tournament


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
    user: User = Depends(require_role("ADMIN", "ORGANIZER")),
    db: Session = Depends(get_db),
):
    ensure_references(db, data.game_id, data.area_id)
    tournament = Tournament(**data.model_dump(), created_by=user.user_id)
    db.add(tournament)
    return commit_tournament(db, tournament, user, "TOURNAMENT_CREATED", {},
                             {**data.model_dump(mode="json"), "status": "UPCOMING", "created_by": user.user_id})


@router.get("/{tournament_id}", response_model=TournamentRead)
def get_tournament(tournament_id: TournamentId, db: Session = Depends(get_db)):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament


@router.patch("/{tournament_id}", response_model=TournamentRead)
def update_tournament(
    tournament_id: TournamentId,
    data: TournamentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tournament = get_managed_tournament(db, tournament_id, user)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("game_id", tournament.game_id) != tournament.game_id:
        registration = db.scalar(select(TournamentRegistration.registration_id).where(
            TournamentRegistration.tournament_id == tournament_id,
        ).limit(1))
        if registration is not None:
            raise HTTPException(status_code=409, detail="Không thể đổi game khi giải đã có đơn đăng ký")
    if not TRANSITIONS[tournament.status]:
        raise HTTPException(status_code=409, detail="Giải đấu đã kết thúc hoặc bị hủy, không thể chỉnh sửa")
    if tournament.status == "ONGOING" and set(changes) - ONGOING_EDITABLE:
        raise HTTPException(status_code=409, detail="Giải đang diễn ra chỉ được sửa tên, mô tả và ngày kết thúc")
    if changes.get("start_date", tournament.start_date) != tournament.start_date and changes["start_date"] < date.today():
        raise HTTPException(status_code=422, detail="Ngày bắt đầu không được ở quá khứ")
    end_date = changes.get("end_date", tournament.end_date)
    if end_date is not None and end_date < changes.get("start_date", tournament.start_date):
        raise HTTPException(status_code=422, detail="Ngày kết thúc không được trước ngày bắt đầu")
    ensure_references(db, changes.get("game_id"), changes.get("area_id"))
    before = {}
    for field, value in changes.items():
        previous = getattr(tournament, field)
        before[field] = previous.isoformat() if isinstance(previous, date) else previous
        setattr(tournament, field, value)
    return commit_tournament(db, tournament, user, "TOURNAMENT_UPDATED", before,
                             data.model_dump(mode="json", exclude_unset=True))


@router.post("/{tournament_id}/status", response_model=TournamentRead)
def change_tournament_status(
    tournament_id: TournamentId,
    data: StatusChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tournament = get_managed_tournament(db, tournament_id, user)
    if data.status not in TRANSITIONS[tournament.status]:
        raise HTTPException(status_code=409,
                            detail=f"Không thể chuyển giải từ {tournament.status} sang {data.status}")
    before = {"status": tournament.status}
    tournament.status = data.status
    return commit_tournament(db, tournament, user, "TOURNAMENT_STATUS_CHANGED", before, {"status": data.status})
