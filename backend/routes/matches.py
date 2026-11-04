"""W45-03/-04: public match list/detail, manual schedule and start/cancel lifecycle.

Every writer locks tournament -> match and rechecks permission after the wait (see
``core.matches``); the match change and its audit row commit in one transaction.
Result submission lives in ``routes.match_results``.
"""

from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.matches import (
    as_utc, can_cancel_match, can_manage_matches, can_start_match, can_submit_result, ensure_match_teams,
    ensure_match_writable_tournament, ensure_stage_in_tournament, get_match_or_404, lock_match_context,
    match_cancellable, match_editable, match_result_open, match_startable, match_state, matches_writable, to_utc,
)
from core.tournaments import get_managed_tournament, get_tournament_or_404
from core.validation import INT_MAX, ResourceId
from middleware.auth import get_current_user
from modules.identity.models import User
from modules.tournaments.match_schemas import MatchRead, match_read, match_reads
from modules.tournaments.models import Match, Stage, Tournament
from routes.tournaments import paginate

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}/matches', tags=['Matches'])

MatchStatus = Literal['PENDING', 'ONGOING', 'COMPLETED', 'CANCELLED']
PositiveId = Annotated[StrictInt, Field(gt=0, le=INT_MAX)]
EDITABLE_FIELDS = ['round_no', 'scheduled_at', 'stage_id', 'team1_id', 'team2_id']


def _iso_text_only(value):
    # AwareDatetime would also read a JSON number as a Unix timestamp; the contract only takes ISO text.
    if value is not None and not isinstance(value, str):
        raise ValueError('Giờ thi đấu phải là chuỗi ISO 8601 kèm múi giờ')
    return value


ScheduledAt = Annotated[AwareDatetime, BeforeValidator(_iso_text_only)]


class MatchCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stage_id: PositiveId
    round_no: PositiveId
    team1_id: PositiveId
    team2_id: PositiveId
    scheduled_at: ScheduledAt | None = None


class MatchUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stage_id: PositiveId | None = None
    round_no: PositiveId | None = None
    team1_id: PositiveId | None = None
    team2_id: PositiveId | None = None
    scheduled_at: ScheduledAt | None = None  # explicit null clears the schedule

    @model_validator(mode='after')
    def require_changes(self):
        fields = self.model_fields_set
        if not fields or any(getattr(self, field) is None for field in fields - {'scheduled_at'}):
            raise ValueError('Gửi ít nhất một trường cập nhật; chỉ scheduled_at được nhận null')
        return self


class MatchStatusInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['ONGOING', 'CANCELLED']


class MatchCapabilities(BaseModel):
    match_id: int
    can_update: bool
    can_delete: bool
    can_start: bool
    can_submit_result: bool
    can_cancel: bool
    editable_fields: list[str]


def can_manage_match(db: Session, tournament: Tournament, match: Match, user: User) -> bool:
    """``lock_match_context`` checker for the manager-only schedule writes."""
    return can_manage_matches(tournament, user)


def has_bracket_link(db: Session, match: Match) -> bool:
    """Historical bracket links stay untouched: W45 does not read or rewrite next_match_id."""
    return match.next_match_id is not None or db.scalar(
        select(Match.match_id).where(Match.next_match_id == match.match_id).limit(1)) is not None


def ensure_schedule_writable(db: Session, tournament: Tournament, match: Match) -> None:
    ensure_match_writable_tournament(tournament)
    if not match_editable(tournament, match):
        raise HTTPException(status_code=409, detail='Chỉ sửa hoặc xóa trận PENDING')
    if has_bracket_link(db, match):
        raise HTTPException(status_code=409, detail='Trận có liên kết nhánh đấu cũ, W45 không sửa hoặc xóa')


def record_match(db: Session, user: User, action: str, tournament_id: int, match_id: int, before, after) -> None:
    record_audit(db, user.user_id, action, 'match', {
        'tournament_id': tournament_id, 'match_id': match_id, 'before': before, 'after': after,
    })


@contextmanager
def match_write(db: Session):
    try:
        yield
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Dữ liệu trận vi phạm ràng buộc hoặc đã thay đổi') from None
    except Exception:
        db.rollback()
        raise


@router.get('', response_model=list[MatchRead])
def list_matches(tournament_id: ResourceId, response: Response, db: Session = Depends(get_db),
                 stage_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
                 team_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
                 status: MatchStatus | None = None,
                 offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
                 limit: Annotated[int, Query(ge=1, le=100)] = 50):
    get_tournament_or_404(db, tournament_id)
    query = select(Match).join(Stage, Stage.stage_id == Match.stage_id).where(Match.tournament_id == tournament_id)
    if stage_id is not None:
        query = query.where(Match.stage_id == stage_id)
    if team_id is not None:
        query = query.where(or_(Match.team1_id == team_id, Match.team2_id == team_id))
    if status is not None:
        query = query.where(Match.status == status)
    query = query.order_by(Stage.sequence_order, Match.round_no, Match.match_id)
    return match_reads(db, paginate(db, query, response, offset, limit))


@router.post('', response_model=MatchRead, status_code=201)
def create_match(tournament_id: ResourceId, data: MatchCreate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with match_write(db):
        tournament = get_managed_tournament(db, tournament_id, user)
        ensure_match_writable_tournament(tournament)
        ensure_stage_in_tournament(db, tournament_id, data.stage_id)
        ensure_match_teams(db, tournament, data.team1_id, data.team2_id)
        match = Match(**data.model_dump(exclude={'scheduled_at'}), tournament_id=tournament_id,
                      scheduled_at=to_utc(data.scheduled_at), status='PENDING', score_team1=0, score_team2=0)
        db.add(match)
        db.flush()
        record_match(db, user, 'MATCH_CREATED', tournament_id, match.match_id, None, match_state(match))
        result = match_read(db, match)
        db.commit()
    return result


@router.get('/{match_id}', response_model=MatchRead)
def get_match(tournament_id: ResourceId, match_id: ResourceId, db: Session = Depends(get_db)):
    get_tournament_or_404(db, tournament_id)
    return match_read(db, get_match_or_404(db, tournament_id, match_id))


@router.patch('/{match_id}', response_model=MatchRead)
def update_match(tournament_id: ResourceId, match_id: ResourceId, data: MatchUpdate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with match_write(db):
        tournament, match, user = lock_match_context(db, tournament_id, match_id, user, can_manage_match)
        ensure_schedule_writable(db, tournament, match)
        changes = data.model_dump(exclude_unset=True)
        if 'scheduled_at' in changes:
            changes['scheduled_at'] = to_utc(changes['scheduled_at'])
        if 'stage_id' in changes:
            ensure_stage_in_tournament(db, tournament_id, changes['stage_id'])
        if 'team1_id' in changes or 'team2_id' in changes:
            team1_id, team2_id = changes.get('team1_id', match.team1_id), changes.get('team2_id', match.team2_id)
            if team1_id is None or team2_id is None:
                raise HTTPException(status_code=422, detail='Trận phải có đủ hai đội')
            ensure_match_teams(db, tournament, team1_id, team2_id)
        if all((as_utc(match.scheduled_at) if field == 'scheduled_at' else getattr(match, field)) == value
               for field, value in changes.items()):
            result = match_read(db, match)
            db.rollback()
            return result
        before = match_state(match)
        for field, value in changes.items():
            setattr(match, field, value)
        db.flush()
        record_match(db, user, 'MATCH_UPDATED', tournament_id, match_id, before, match_state(match))
        result = match_read(db, match)
        db.commit()
    return result


@router.delete('/{match_id}', status_code=204)
def delete_match(tournament_id: ResourceId, match_id: ResourceId,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with match_write(db):
        tournament, match, user = lock_match_context(db, tournament_id, match_id, user, can_manage_match)
        ensure_schedule_writable(db, tournament, match)
        before = match_state(match)
        db.delete(match)
        db.flush()
        record_match(db, user, 'MATCH_DELETED', tournament_id, match_id, before, None)
        db.commit()
    return Response(status_code=204)


def start_match(db: Session, tournament: Tournament, match: Match) -> str | None:
    """Return the audit action, or None for an idempotent restart of an ONGOING match."""
    restart = match.status == 'ONGOING'
    # Same gate for a restart: match_startable only differs by requiring PENDING.
    startable = match_startable(tournament, match) or (restart and tournament.status == 'ONGOING'
                                                       and tournament.roster_locked_at is not None
                                                       and None not in (match.team1_id, match.team2_id))
    if not startable:
        raise HTTPException(status_code=409,
                            detail='Chỉ bắt đầu trận PENDING đủ hai đội khi giải ONGOING và đã khóa đội hình')
    ensure_match_teams(db, tournament, match.team1_id, match.team2_id)
    if restart:
        return None
    match.status = 'ONGOING'
    return 'MATCH_STARTED'


def cancel_match(tournament: Tournament, match: Match) -> str | None:
    """Return the audit action, or None when the match is already cancelled."""
    if match.status == 'CANCELLED':
        return None
    if not match_cancellable(tournament, match):
        raise HTTPException(status_code=409, detail='Chỉ hủy trận PENDING/ONGOING khi giải UPCOMING hoặc ONGOING')
    match.status = 'CANCELLED'
    return 'MATCH_CANCELLED'


@router.post('/{match_id}/status', response_model=MatchRead)
def change_match_status(tournament_id: ResourceId, match_id: ResourceId, data: MatchStatusInput,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    checker = can_start_match if data.status == 'ONGOING' else can_cancel_match
    with match_write(db):
        tournament, match, user = lock_match_context(db, tournament_id, match_id, user, checker)
        before = match_state(match)
        action = (start_match(db, tournament, match) if data.status == 'ONGOING'
                  else cancel_match(tournament, match))
        if action is None:
            result = match_read(db, match)
            db.rollback()
            return result
        db.flush()
        record_match(db, user, action, tournament_id, match_id, before, match_state(match))
        result = match_read(db, match)
        db.commit()
    return result


@router.get('/{match_id}/capabilities', response_model=MatchCapabilities)
def match_capabilities(tournament_id: ResourceId, match_id: ResourceId,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hints for the current user only; every mutation above rechecks the same policies."""
    tournament = get_tournament_or_404(db, tournament_id)
    match = get_match_or_404(db, tournament_id, match_id)
    editable = (can_manage_matches(tournament, user) and match_editable(tournament, match)
                and not has_bracket_link(db, match))
    return MatchCapabilities(
        match_id=match_id,
        can_update=editable,
        can_delete=editable,
        can_start=match_startable(tournament, match) and can_start_match(db, tournament, match, user),
        can_submit_result=match_result_open(tournament, match) and can_submit_result(db, tournament, match, user),
        can_cancel=match_cancellable(tournament, match) and can_cancel_match(db, tournament, match, user),
        editable_fields=EDITABLE_FIELDS if editable else [],
    )
