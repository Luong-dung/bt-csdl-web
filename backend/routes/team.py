from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from middleware.auth import get_current_user
from modules.identity.models import User
from modules.teams.models import Team, TeamMembership

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    tag: str = Field(min_length=2, max_length=10)
    game_id: int


class MemberCreate(BaseModel):
    username: str
    role_in_team: str = "PLAYER"


@router.get("")
def list_teams(db: Session = Depends(get_db)):
    return db.scalars(select(Team).order_by(Team.name)).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_team(data: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = Team(name=data.name, tag=data.tag, game_id=data.game_id)
    db.add(team)
    db.flush()
    db.add(TeamMembership(team_id=team.team_id, user_id=user.user_id, joined_date=date.today(), role_in_team="MANAGER"))
    db.commit()
    return {"team_id": team.team_id, "name": team.name, "tag": team.tag}


@router.get("/{team_id}")
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    return {
        "team_id": team.team_id,
        "name": team.name,
        "tag": team.tag,
        "game_id": team.game_id,
        "members": [
            {"user_id": member.user_id, "role": member.role_in_team, "status": member.status}
            for member in team.memberships
        ],
    }


@router.post(
    "/{team_id}/members",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
def add_member(team_id: int, data: MemberCreate, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    member = db.scalar(select(User).where(User.username == data.username))
    if team is None or member is None:
        raise HTTPException(status_code=404, detail="Đội tuyển hoặc tài khoản không tồn tại")
    db.add(TeamMembership(team_id=team_id, user_id=member.user_id, role_in_team=data.role_in_team, joined_date=date.today()))
    db.commit()
    return {"message": "Đã thêm thành viên", "team_id": team_id, "user_id": member.user_id}
