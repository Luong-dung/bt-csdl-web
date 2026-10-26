from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.validation import DbId, INT_MAX, ResourceId
from core.rosters import lock_membership_team
from middleware.auth import ensure_team_manager, get_current_user, managed_teams_query
from modules.catalog.models import Game
from modules.identity.models import AuditLog, User
from modules.teams.models import Team, TeamMembership

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])

ACTIVE = "ACTIVE"
ENDED = "ENDED"
MANAGER = "MANAGER"
TeamRole = Literal["MANAGER", "COACH", "PLAYER", "SUBSTITUTE"]


class TeamInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TeamCreate(TeamInput):
    name: str = Field(min_length=2, max_length=100)
    tag: str = Field(min_length=2, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    game_id: DbId


class MemberCreate(TeamInput):
    username: str = Field(min_length=1, max_length=50)
    role_in_team: TeamRole = "PLAYER"


class MemberUpdate(TeamInput):
    role_in_team: TeamRole


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    team_id: int
    name: str
    tag: str
    game_id: int


class MemberRead(BaseModel):
    membership_id: int
    user_id: int
    username: str
    role: str
    status: str
    joined_date: date
    left_date: date | None


class TeamDetail(TeamRead):
    members: list[MemberRead]


def member_read(membership: TeamMembership) -> MemberRead:
    return MemberRead(
        membership_id=membership.membership_id,
        user_id=membership.user_id,
        username=membership.user.username,
        role=membership.role_in_team,
        status=membership.status,
        joined_date=membership.joined_date,
        left_date=membership.left_date,
    )


def get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    return team


def get_membership_or_404(db: Session, team_id: int, membership_id: int) -> TeamMembership:
    membership = db.get(TeamMembership, membership_id, populate_existing=True)
    if membership is None or membership.team_id != team_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thành viên trong đội")
    return membership


def ensure_not_active_elsewhere(db: Session, user_id: int, message: str):
    current = db.scalar(select(TeamMembership).where(
        TeamMembership.user_id == user_id, TeamMembership.status == ACTIVE,
    ))
    if current is not None:
        raise HTTPException(status_code=409, detail=f"{message} (đang thuộc đội {current.team.name})")


def ensure_other_manager(db: Session, membership: TeamMembership):
    """Keep at least one active manager so the team can still be administered."""
    if membership.role_in_team != MANAGER:
        return
    managers = db.scalar(select(func.count()).select_from(TeamMembership).where(
        TeamMembership.team_id == membership.team_id,
        TeamMembership.status == ACTIVE,
        TeamMembership.role_in_team == MANAGER,
    ))
    if managers <= 1:
        raise HTTPException(status_code=409, detail="Đội phải còn ít nhất một quản lý đang hoạt động")


def audit(db: Session, user: User, action: str, membership: TeamMembership, **details):
    db.add(AuditLog(
        user_id=user.user_id,
        action=action,
        resource="team_membership",
        details={"team_id": membership.team_id, "membership_id": membership.membership_id,
                 "member_user_id": membership.user_id, **details},
    ))


def save_or_409(db: Session, message: str, commit: bool = True):
    # Fallback for concurrent requests that slip past the pre-checks.
    try:
        db.commit() if commit else db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=message)


@router.get("", response_model=list[TeamRead])
def list_teams(game_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None, db: Session = Depends(get_db)):
    query = select(Team).order_by(Team.name)
    if game_id is not None:
        query = query.where(Team.game_id == game_id)
    return db.scalars(query).all()


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(data: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Game, data.game_id) is None:
        raise HTTPException(status_code=422, detail="Game không tồn tại")
    tag = data.tag.upper()
    if db.scalar(select(Team.team_id).where(Team.tag == tag)) is not None:
        raise HTTPException(status_code=409, detail="Tag đội đã tồn tại")
    ensure_not_active_elsewhere(db, user.user_id, "Bạn đang là thành viên của một đội khác")
    team = Team(name=data.name, tag=tag, game_id=data.game_id)
    db.add(team)
    save_or_409(db, "Tag đội đã tồn tại", commit=False)
    membership = TeamMembership(team_id=team.team_id, user_id=user.user_id,
                                joined_date=date.today(), role_in_team=MANAGER)
    db.add(membership)
    save_or_409(db, "Bạn đang là thành viên của một đội khác", commit=False)
    audit(db, user, "TEAM_MEMBER_ADDED", membership, role=MANAGER)
    save_or_409(db, "Không thể tạo đội, tag hoặc thành viên bị trùng")
    return team


@router.get("/managed", response_model=list[TeamRead])
def managed_teams(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    game_id: Annotated[int | None, Query(gt=0, le=INT_MAX)] = None,
    offset: Annotated[int, Query(ge=0, le=INT_MAX)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = managed_teams_query(user).order_by(Team.name, Team.team_id)
    if game_id is not None:
        query = query.where(Team.game_id == game_id)
    return db.scalars(query.offset(offset).limit(limit)).all()


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: ResourceId, db: Session = Depends(get_db)):
    team = get_team_or_404(db, team_id)
    members = sorted(team.memberships, key=lambda m: (m.status != ACTIVE, m.joined_date, m.membership_id))
    return TeamDetail(
        team_id=team.team_id, name=team.name, tag=team.tag, game_id=team.game_id,
        members=[member_read(member) for member in members],
    )


@router.get("/{team_id}/members", response_model=list[MemberRead])
def list_members(team_id: ResourceId, include_history: bool = False, db: Session = Depends(get_db)):
    get_team_or_404(db, team_id)
    query = select(TeamMembership).where(TeamMembership.team_id == team_id)
    if not include_history:
        query = query.where(TeamMembership.status == ACTIVE)
    query = query.order_by(TeamMembership.joined_date, TeamMembership.membership_id)
    return [member_read(member) for member in db.scalars(query)]


@router.post("/{team_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(team_id: ResourceId, data: MemberCreate, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    get_team_or_404(db, team_id)
    ensure_team_manager(db, team_id, user)
    user = lock_membership_team(db, team_id, user)
    ensure_team_manager(db, team_id, user)
    member = db.scalar(select(User).where(User.username == data.username))
    if member is None:
        raise HTTPException(status_code=404, detail="Tài khoản không tồn tại")
    ensure_not_active_elsewhere(db, member.user_id, "Tài khoản đang là thành viên hoạt động của một đội")
    # (team, user, joined_date) is unique, so a member who left today cannot rejoin until tomorrow.
    if db.scalar(select(TeamMembership.membership_id).where(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == member.user_id,
        TeamMembership.joined_date == date.today(),
    )) is not None:
        raise HTTPException(status_code=409, detail="Thành viên đã rời đội hôm nay, có thể thêm lại từ ngày mai")
    membership = TeamMembership(team_id=team_id, user_id=member.user_id,
                                role_in_team=data.role_in_team, joined_date=date.today())
    db.add(membership)
    save_or_409(db, "Tài khoản đang là thành viên hoạt động của một đội", commit=False)
    audit(db, user, "TEAM_MEMBER_ADDED", membership, role=data.role_in_team)
    save_or_409(db, "Không thể thêm thành viên")
    return member_read(membership)


@router.patch("/{team_id}/members/{membership_id}", response_model=MemberRead)
def update_member_role(team_id: ResourceId, membership_id: ResourceId, data: MemberUpdate,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_team_or_404(db, team_id)
    ensure_team_manager(db, team_id, user)
    user = lock_membership_team(db, team_id, user)
    ensure_team_manager(db, team_id, user)
    membership = get_membership_or_404(db, team_id, membership_id)
    if membership.status != ACTIVE:
        raise HTTPException(status_code=409, detail="Không thể đổi vị trí của thành viên đã rời đội")
    if data.role_in_team != membership.role_in_team:
        if data.role_in_team != MANAGER:
            ensure_other_manager(db, membership)
        audit(db, user, "TEAM_MEMBER_ROLE_CHANGED", membership,
              old_role=membership.role_in_team, new_role=data.role_in_team)
        membership.role_in_team = data.role_in_team
        save_or_409(db, "Không thể đổi vị trí thành viên")
    return member_read(membership)


@router.post("/{team_id}/members/{membership_id}/end", response_model=MemberRead)
def end_membership(team_id: ResourceId, membership_id: ResourceId, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """End a membership instead of deleting it, so transfer history is kept."""
    get_team_or_404(db, team_id)
    membership = get_membership_or_404(db, team_id, membership_id)
    # Members may leave on their own; ending someone else needs manager rights.
    if membership.user_id != user.user_id:
        ensure_team_manager(db, team_id, user)
    user = lock_membership_team(db, team_id, user)
    membership = get_membership_or_404(db, team_id, membership_id)
    if membership.user_id != user.user_id:
        ensure_team_manager(db, team_id, user)
    if membership.status != ACTIVE:
        raise HTTPException(status_code=409, detail="Thành viên đã rời đội trước đó")
    ensure_other_manager(db, membership)
    membership.status = ENDED
    membership.left_date = date.today()
    audit(db, user, "TEAM_MEMBER_ENDED", membership, role=membership.role_in_team)
    save_or_409(db, "Không thể kết thúc thành viên")
    return member_read(membership)
