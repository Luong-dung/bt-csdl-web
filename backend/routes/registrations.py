from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.registrations import (
    ensure_registration_open, ensure_registration_resolution_open, lock_registration, registration_timestamp,
)
from core.tournaments import get_managed_tournament, get_tournament_or_404, lock_tournament_as
from core.validation import DbId
from middleware.auth import can_manage_tournament, ensure_team_manager, get_current_user, managed_teams_query
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import TournamentRegistration
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


class RegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: DbId


class RegistrationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["APPROVED", "REJECTED"]
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def reason_only_for_rejection(self):
        if self.status != "REJECTED" and self.rejection_reason is not None:
            raise ValueError("Chỉ đơn bị từ chối mới có lý do từ chối")
        return self


def registration_state(registration: TournamentRegistration, *fields: str) -> dict:
    values = {field: getattr(registration, field) for field in fields}
    return {field: value.isoformat() if isinstance(value, datetime) else value for field, value in values.items()}


def commit_registration(db: Session, registration: TournamentRegistration, user: User, action: str,
                        before: dict | None, fields: tuple[str, ...]) -> TournamentRegistration:
    # The registration change and its audit entry succeed or roll back together.
    try:
        db.flush()
        record_audit(db, user.user_id, action, 'tournament_registration', {
            'tournament_id': registration.tournament_id,
            'registration_id': registration.registration_id,
            'team_id': registration.team_id,
            'before': before,
            'after': registration_state(registration, *fields),
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Đơn đăng ký bị trùng hoặc vi phạm ràng buộc")
    except Exception:
        db.rollback()
        raise
    db.refresh(registration)
    return registration


@router.get("", response_model=list[RegistrationRead])
def list_registrations(
    tournament_id: TournamentId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: RegistrationStatus | None = None,
    team_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
    offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    tournament = get_tournament_or_404(db, tournament_id)
    query = select(TournamentRegistration).where(TournamentRegistration.tournament_id == tournament_id)
    if not can_manage_tournament(tournament, user):
        # Team managers only see registrations of teams they currently manage.
        managed_ids = managed_teams_query(user).with_only_columns(Team.team_id).correlate(None)
        if team_id is not None:
            ensure_team_manager(db, team_id, user)
        elif db.scalar(managed_ids.limit(1)) is None:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem đơn đăng ký của giải này")
        query = query.where(TournamentRegistration.team_id.in_(managed_ids))
    if team_id is not None:
        query = query.where(TournamentRegistration.team_id == team_id)
    if status is not None:
        query = query.where(TournamentRegistration.status == status)
    query = query.order_by(TournamentRegistration.submitted_at, TournamentRegistration.registration_id)
    return db.scalars(query.offset(offset).limit(limit)).all()


@router.post("", response_model=RegistrationRead, status_code=201)
def create_registration(
    tournament_id: TournamentId,
    data: RegistrationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_tournament_or_404(db, tournament_id)
    if db.get(Team, data.team_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    # Reject unauthorized callers before they can join the row-lock queue.
    ensure_team_manager(db, data.team_id, user)
    tournament, user = lock_tournament_as(db, tournament_id, user)
    ensure_team_manager(db, data.team_id, user)
    ensure_registration_open(tournament)
    team = db.get(Team, data.team_id, populate_existing=True)
    if team is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    if team.game_id != tournament.game_id:
        raise HTTPException(status_code=422, detail="Game của đội không khớp với giải đấu")
    if db.scalar(select(TournamentRegistration.registration_id).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.team_id == data.team_id,
    )) is not None:
        raise HTTPException(status_code=409, detail="Đội đã có đơn đăng ký trong giải này")
    registration = TournamentRegistration(
        tournament_id=tournament_id, team_id=data.team_id, status="PENDING",
        submitted_by=user.user_id, submitted_at=registration_timestamp(db),
    )
    db.add(registration)
    return commit_registration(db, registration, user, 'TOURNAMENT_REGISTRATION_CREATED', None,
                               ('status', 'submitted_by', 'submitted_at'))


@router.post("/{registration_id}/cancel", response_model=RegistrationRead)
def cancel_registration(
    tournament_id: TournamentId,
    registration_id: TournamentId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_tournament_or_404(db, tournament_id)
    registration = db.scalar(select(TournamentRegistration).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.registration_id == registration_id,
    ))
    if registration is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký trong giải")
    ensure_team_manager(db, registration.team_id, user)
    tournament, user = lock_tournament_as(db, tournament_id, user)
    registration = lock_registration(db, tournament_id, registration_id)
    ensure_team_manager(db, registration.team_id, user)
    ensure_registration_resolution_open(tournament)
    if registration.status != "PENDING":
        raise HTTPException(status_code=409, detail="Chỉ hủy được đơn đang chờ duyệt")
    fields = ('status', 'cancelled_by', 'cancelled_at')
    before = registration_state(registration, *fields)
    registration.status = "CANCELLED"
    registration.cancelled_by = user.user_id
    registration.cancelled_at = registration_timestamp(db)
    return commit_registration(db, registration, user, 'TOURNAMENT_REGISTRATION_CANCELLED', before, fields)


@router.post("/{registration_id}/decision", response_model=RegistrationRead)
def decide_registration(
    tournament_id: TournamentId,
    registration_id: TournamentId,
    data: RegistrationDecision,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tournament = get_managed_tournament(db, tournament_id, user)
    registration = lock_registration(db, tournament_id, registration_id)
    if data.status == 'APPROVED':
        ensure_registration_open(tournament)
    else:
        ensure_registration_resolution_open(tournament)
    if registration.status != "PENDING":
        raise HTTPException(status_code=409, detail="Đơn đăng ký không còn chờ duyệt")
    team = db.get(Team, registration.team_id)
    if data.status == "APPROVED" and (team is None or team.game_id != tournament.game_id):
        raise HTTPException(status_code=409, detail="Game của đội không khớp với giải đấu")
    before = {
        'status': registration.status, 'reviewed_by': registration.reviewed_by,
        'reviewed_at': registration.reviewed_at.isoformat() if registration.reviewed_at else None,
        'rejection_reason': registration.rejection_reason,
    }
    try:
        registration.status = data.status
        registration.reviewed_by = user.user_id
        registration.reviewed_at = registration_timestamp(db)
        registration.rejection_reason = data.rejection_reason
        db.flush()
        record_audit(db, user.user_id, 'TOURNAMENT_REGISTRATION_' + data.status, 'tournament_registration', {
            'tournament_id': tournament_id,
            'registration_id': registration_id,
            'team_id': registration.team_id,
            'before': before,
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
