"""W46 shared input/plan contract. Routes are delivered by W46-03/-04."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.validation import INT_MAX

BracketId = Annotated[int, Field(strict=True, gt=0, le=INT_MAX)]


class BracketInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stage_id: BracketId
    team_ids: Annotated[list[BracketId], Field(min_length=2, max_length=64)]

    @model_validator(mode='after')
    def supported_teams(self):
        count = len(self.team_ids)
        if count & (count-1):
            raise ValueError('Số đội phải là lũy thừa hai, từ 2 đến 64; chưa hỗ trợ bye')
        if len(set(self.team_ids)) != count:
            raise ValueError('Danh sách đội không được trùng')
        return self


class BracketCreate(BracketInput):
    preview_token: Annotated[str, Field(min_length=1, max_length=8192)]


class BracketPlanMatch(BaseModel):
    round_index: int
    position: int
    team1_id: int | None
    team2_id: int | None
    next_round: int | None
    next_position: int | None
    next_slot: int | None
