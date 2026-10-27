"""Shared roster wire contract for W44-2-03/04; IDs never accept bool/string bodies."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.validation import INT_MAX


class RosterSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: Annotated[int, Field(strict=True, gt=0, le=INT_MAX)]
    role_in_team: Literal['PLAYER', 'SUBSTITUTE']


class RosterReplace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    members: list[RosterSelection] = Field(max_length=100)

    @model_validator(mode='after')
    def unique_users(self):
        ids = [member.user_id for member in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError('Mỗi tuyển thủ chỉ xuất hiện một lần trong đội hình')
        return self


class RosterMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    display_name: str | None
    role_in_team: Literal['PLAYER', 'SUBSTITUTE']


class RosterRead(BaseModel):
    tournament_id: int
    team_id: int
    locked: bool
    members: list[RosterMemberRead]


class RosterLockRead(BaseModel):
    tournament_id: int
    locked: bool
    locked_at: datetime | None


class RosterCapabilities(BaseModel):
    tournament_id: int
    team_id: int
    can_view_roster: bool
    can_edit_roster: bool
