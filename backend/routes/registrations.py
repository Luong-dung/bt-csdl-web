from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.registrations import ensure_registration_open, lock_registration, lock_registration_tournament
from middleware.auth import can_manage_tournament, get_current_user
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import Tournament, TournamentRegistration
from routes.tournaments import INT_MAX, TournamentId

router = APIRouter(prefix="/api/v1/tournaments/{tournament_id}/registrations", tags=["Tournament registrations"])
RegistrationStatus = Literal["PENDING", "APPROVED", "REJECTED", "CANCELLED"]


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    tournament_id: int
    team_id: int
    status: RegistrationStatus
    submitted_by: int | None
    submitted_at: datetime
    reviewed_by: int | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    cancelled_by: int | None
    cancelled_at: datetime | None


class RegistrationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["APPROVED", "REJECTED"]
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def reason_only_for_rejection(self):
        if self.status != "REJECTED" and self.rejection_reason is not None:
            raise ValueError("Chỉ đơn bị từ chối mới có lý do từ chối")
        return self


def ensure_reviewer(tournament: Tournament, user: User) -> None:
    if not can_manage_tournament(tournament, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xử lý đăng ký giải này")


@router.get("", response_model=list[RegistrationRead])
def list_registrations(
    tournament_id: TournamentId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: RegistrationStatus | None = None,
    offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    ensure_reviewer(tournament, user)
    query = select(TournamentRegistration).where(TournamentRegistration.tournament_id == tournament_id)
    if status is not None:
        query = query.where(TournamentRegistration.status == status)
    query = query.order_by(TournamentRegistration.submitted_at, TournamentRegistration.registration_id)
    return db.scalars(query.offset(offset).limit(limit)).all()


@router.post("/{registration_id}/decision", response_model=RegistrationRead)
def decide_registration(
    tournament_id: TournamentId,
    registration_id: TournamentId,
    data: RegistrationDecision,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tournament = lock_registration_tournament(db, tournament_id)
    ensure_reviewer(tournament, user)
    registration = lock_registration(db, tournament_id, registration_id)
    ensure_registration_open(tournament)
    if registration.status != "PENDING":
        raise HTTPException(status_code=409, detail="Đơn đăng ký không còn chờ duyệt")
    team = db.get(Team, registration.team_id)
    if data.status == "APPROVED" and (team is None or team.game_id != tournament.game_id):
        raise HTTPException(status_code=409, detail="Game của đội không khớp với giải đấu")
    registration.status = data.status
    registration.reviewed_by = user.user_id
    registration.reviewed_at = datetime.now(timezone.utc)
    registration.rejection_reason = data.rejection_reason
    try:
        db.flush()
        record_audit(db, user.user_id, 'TOURNAMENT_REGISTRATION_' + data.status, 'tournament_registration', {
            'tournament_id': tournament_id,
            'registration_id': registration_id,
            'team_id': registration.team_id,
            'before': {'status': 'PENDING', 'reviewed_by': None, 'reviewed_at': None, 'rejection_reason': None},
            'after': {'status': registration.status, 'reviewed_by': registration.reviewed_by,
                      'reviewed_at': registration.reviewed_at.isoformat(), 'rejection_reason': registration.rejection_reason},
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Không thể lưu quyết định đăng ký")
    except Exception:
        db.rollback()
        raise
    db.refresh(registration)
    return registration
