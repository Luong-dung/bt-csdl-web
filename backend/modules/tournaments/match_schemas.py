"""Public match DTOs shared by W45-02 (result) and W45-03 (list/lifecycle).

Only IDs, names, schedule, status and the final result are exposed: no emails,
draft rosters or internal assignments.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy.orm import Session

from core.matches import as_utc
from core.validation import INT_MAX
from modules.teams.models import Team
from modules.tournaments.models import Match, Stage

Score = Annotated[StrictInt, Field(ge=0, le=INT_MAX)]


class MatchTeam(BaseModel):
    team_id: int
    name: str


class MatchResult(BaseModel):
    score_team1: int
    score_team2: int
    winner_id: int


class MatchRead(BaseModel):
    match_id: int
    tournament_id: int
    stage_id: int
    stage_name: str
    round_no: int
    team1: MatchTeam | None
    team2: MatchTeam | None
    scheduled_at: datetime | None
    status: str
    # null until COMPLETED: the default 0-0 columns are not a result.
    result: MatchResult | None


class ResultInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    score_team1: Score
    score_team2: Score

    @model_validator(mode='after')
    def no_draw(self):
        if self.score_team1 == self.score_team2:
            raise ValueError('W45 không hỗ trợ hòa: hai tỉ số phải khác nhau')
        return self


def match_read(db: Session, match: Match) -> MatchRead:
    team_ids = [tid for tid in (match.team1_id, match.team2_id) if tid is not None]
    names = dict(db.query(Team.team_id, Team.name).filter(Team.team_id.in_(team_ids)).all()) if team_ids else {}
    stage_name = db.query(Stage.name).filter(Stage.stage_id == match.stage_id).scalar()

    def team(team_id):
        return None if team_id is None else MatchTeam(team_id=team_id, name=names[team_id])

    result = None
    if match.status == 'COMPLETED':
        result = MatchResult(score_team1=match.score_team1, score_team2=match.score_team2,
                             winner_id=match.winner_id)
    return MatchRead(match_id=match.match_id, tournament_id=match.tournament_id, stage_id=match.stage_id,
                     stage_name=stage_name, round_no=match.round_no, team1=team(match.team1_id),
                     team2=team(match.team2_id), scheduled_at=as_utc(match.scheduled_at),
                     status=match.status, result=result)
