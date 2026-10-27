"""Stage configuration: tournament lock serializes all writers, including reorders."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.tournament_policy import stages_editable
from core.tournaments import get_managed_tournament, get_tournament_or_404
from core.validation import INT_MAX, ResourceId
from middleware.auth import get_current_user
from modules.identity.models import User
from modules.tournaments.models import Match, Stage
from routes.tournaments import paginate

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}/stages', tags=['Tournament stages'])
Order = Annotated[int, Field(strict=True, gt=0, le=INT_MAX)]
Name = Annotated[str, Field(min_length=1, max_length=80)]


class StageInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class StageCreate(StageInput):
    name: Name
    sequence_order: Order


class StageUpdate(StageInput):
    name: Name | None = None
    sequence_order: Order | None = None

    @model_validator(mode='after')
    def require_changes(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Gửi ít nhất một trường cập nhật, không nhận null')
        return self


class StageOrder(StageInput):
    stage_ids: list[Order] = Field(max_length=1000)

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.stage_ids)) != len(self.stage_ids):
            raise ValueError('Danh sách vòng đấu không được trùng ID')
        return self


class StageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage_id: int
    tournament_id: int
    name: str
    sequence_order: int


def stage_or_404(db: Session, tournament_id: int, stage_id: int) -> Stage:
    stage = db.scalar(select(Stage).where(Stage.tournament_id == tournament_id, Stage.stage_id == stage_id)
                      .execution_options(populate_existing=True))
    if stage is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy vòng đấu trong giải')
    return stage


def stage_writer(db: Session, tournament_id: int, user: User):
    tournament = get_managed_tournament(db, tournament_id, user)
    if not stages_editable(tournament.status):
        raise HTTPException(status_code=409, detail='Chỉ cấu hình vòng đấu khi giải UPCOMING')
    return tournament


def state(stage: Stage) -> dict:
    return {field: getattr(stage, field) for field in ('stage_id', 'name', 'sequence_order')}


def commit_stage(db: Session, user: User, tournament_id: int, action: str, before, after):
    # Callers provide snapshots after flush; errors from either flush or audit roll back all writes.
    record_audit(db, user.user_id, action, 'tournament_stage', {
        'tournament_id': tournament_id, 'before': before, 'after': after,
    })
    db.commit()


def conflict(db: Session):
    db.rollback()
    return HTTPException(status_code=409, detail='Thứ tự vòng đấu bị trùng hoặc dữ liệu vi phạm ràng buộc')


@router.get('', response_model=list[StageRead])
def list_stages(tournament_id: ResourceId, response: Response, db: Session = Depends(get_db),
                offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
                limit: Annotated[int, Query(ge=1, le=100)] = 50):
    get_tournament_or_404(db, tournament_id)
    query = select(Stage).where(Stage.tournament_id == tournament_id).order_by(Stage.sequence_order, Stage.stage_id)
    return paginate(db, query, response, offset, limit)


@router.post('', response_model=StageRead, status_code=201)
def create_stage(tournament_id: ResourceId, data: StageCreate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stage_writer(db, tournament_id, user)
    stage = Stage(tournament_id=tournament_id, **data.model_dump())
    try:
        db.add(stage)
        db.flush()
        after = state(stage)
        result = StageRead.model_validate(stage)
        commit_stage(db, user, tournament_id, 'TOURNAMENT_STAGE_CREATED', None, after)
    except IntegrityError:
        raise conflict(db)
    except Exception:
        db.rollback()
        raise
    return result


# Static /order must precede the dynamic ID routes.
@router.put('/order', response_model=list[StageRead])
def reorder_stages(tournament_id: ResourceId, data: StageOrder,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stage_writer(db, tournament_id, user)
    stages = list(db.scalars(select(Stage).where(Stage.tournament_id == tournament_id)
                             .order_by(Stage.sequence_order, Stage.stage_id)
                             .with_for_update().execution_options(populate_existing=True)))
    by_id = {stage.stage_id: stage for stage in stages}
    if set(data.stage_ids) != set(by_id):
        raise HTTPException(status_code=422, detail='Cần gửi đúng toàn bộ ID vòng đấu của giải')
    before = [state(stage) for stage in stages]
    if all(by_id[sid].sequence_order == index for index, sid in enumerate(data.stage_ids, 1)):
        return stages  # also the empty-list no-op; no duplicate audit
    try:
        # Use free positive slots, not max(order)+N (which can overflow INTEGER).
        # Reserve both old values and final 1..N, so immediate UNIQUE/CHECK work
        # on PostgreSQL and SQLite without exposing a partially ordered list.
        occupied = {stage.sequence_order for stage in stages} | set(range(1, len(stages) + 1))
        candidate = 1
        for stage in stages:
            while candidate in occupied:
                candidate += 1
            stage.sequence_order = candidate
            occupied.add(candidate)
        db.flush()
        for index, sid in enumerate(data.stage_ids, 1):
            by_id[sid].sequence_order = index
        db.flush()
        ordered = [by_id[sid] for sid in data.stage_ids]
        after = [state(stage) for stage in ordered]
        result = [StageRead.model_validate(stage) for stage in ordered]
        commit_stage(db, user, tournament_id, 'TOURNAMENT_STAGES_REORDERED', before, after)
    except IntegrityError:
        raise conflict(db)
    except Exception:
        db.rollback()
        raise
    return result


@router.get('/{stage_id}', response_model=StageRead)
def get_stage(tournament_id: ResourceId, stage_id: ResourceId, db: Session = Depends(get_db)):
    get_tournament_or_404(db, tournament_id)
    return stage_or_404(db, tournament_id, stage_id)


@router.patch('/{stage_id}', response_model=StageRead)
def update_stage(tournament_id: ResourceId, stage_id: ResourceId, data: StageUpdate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stage_writer(db, tournament_id, user)
    stage = stage_or_404(db, tournament_id, stage_id)
    before = state(stage)
    changes = data.model_dump(exclude_unset=True)
    if all(getattr(stage, field) == value for field, value in changes.items()):
        return stage
    try:
        for field, value in changes.items():
            setattr(stage, field, value)
        db.flush()
        result = StageRead.model_validate(stage)
        commit_stage(db, user, tournament_id, 'TOURNAMENT_STAGE_UPDATED', before, state(stage))
    except IntegrityError:
        raise conflict(db)
    except Exception:
        db.rollback()
        raise
    return result


@router.delete('/{stage_id}', status_code=204)
def delete_stage(tournament_id: ResourceId, stage_id: ResourceId,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stage_writer(db, tournament_id, user)
    stage = stage_or_404(db, tournament_id, stage_id)
    if db.scalar(select(Match.match_id).where(Match.stage_id == stage_id).limit(1)) is not None:
        raise HTTPException(status_code=409, detail='Không thể xóa vòng đấu đã có trận')
    before = state(stage)
    try:
        db.delete(stage)
        db.flush()  # FK RESTRICT is the fallback for concurrent match inserts.
        commit_stage(db, user, tournament_id, 'TOURNAMENT_STAGE_DELETED', before, None)
    except IntegrityError:
        raise conflict(db)
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
