"""W46 shared input/plan/read contract (W46-01), preview/create DTOs (W46-03)."""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.validation import INT_MAX
from modules.tournaments.match_schemas import MatchRead

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


class BracketTeam(BaseModel):
    team_id: int
    name: str


class BracketPreviewRead(BaseModel):
    """Planned structure only: no match_id is invented and nothing is written."""
    tournament_id: int
    stage_id: int
    team_ids: list[int]
    teams: list[BracketTeam]  # same order as team_ids, names for display only
    team_count: int
    round_count: int
    matches: list[BracketPlanMatch]
    preview_token: str
    expires_in: int


class BracketNodeRead(BaseModel):
    round_index: int
    position: int
    next_round: int | None
    next_position: int | None
    next_slot: int | None
    next_match_id: int | None  # resolved from metadata, never from legacy Match.next_match_id
    match: MatchRead


class BracketRead(BaseModel):
    """Public header plus every node (at most 63), ordered by (round_index, position)."""
    bracket_id: int
    tournament_id: int
    stage_id: int
    team_count: int
    round_count: int
    team_ids: list[int]
    created_at: datetime
    matches: list[BracketNodeRead]
