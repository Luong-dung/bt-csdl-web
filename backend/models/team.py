from typing import Literal
from pydantic import BaseModel, Field

TeamRole = Literal["MID", "DS_LANE", "TOP", "JUNGLE", "AD_CARRY", "SUPPORT", "SUB", "MANAGER", "PLAYER"]

class TeamCreate(BaseModel):
    team_name: str = Field(..., min_length=2, max_length=100)
    tag: str = Field(..., min_length=2, max_length=10)

class MemberAdd(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    role_in_team: TeamRole

class MemberUpdate(BaseModel):
    role_in_team: TeamRole

    

