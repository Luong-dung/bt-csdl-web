"""Authenticated permission hints; mutations always recheck the same policies."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_db
from middleware.auth import (
    can_manage_team, can_manage_tournament, get_current_user, has_role, managed_teams_query,
)
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import Tournament
from routes.team import TeamRead
from routes.tournaments import INT_MAX, ONGOING_EDITABLE, TRANSITIONS, TournamentId, TournamentUpdate

def prevent_permission_caching(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(tags=["Capabilities"], dependencies=[Depends(prevent_permission_caching)])


class GlobalCapabilities(BaseModel):
    can_manage_catalog: bool
    can_create_tournament: bool


class TeamCapabilities(BaseModel):
    team_id: int
    can_manage_members: bool
    can_register_for_tournament: bool


class TournamentCapabilities(BaseModel):
    tournament_id: int
    can_manage: bool
    can_update: bool
    can_change_status: bool
    can_review_registrations: bool
    editable_fields: list[str]
    allowed_status_transitions: list[str]


@router.get("/api/v1/auth/capabilities", response_model=GlobalCapabilities)
def global_capabilities(user: User = Depends(get_current_user)):
    return GlobalCapabilities(
        can_manage_catalog=has_role(user, "ADMIN"),
        can_create_tournament=has_role(user, "ADMIN", "ORGANIZER"),
    )


# This router is included before /teams/{team_id}, so "managed" is not parsed as an ID.
@router.get("/api/v1/teams/managed", response_model=list[TeamRead])
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


@router.get("/api/v1/teams/{team_id}/capabilities", response_model=TeamCapabilities)
def team_capabilities(
    team_id: TournamentId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    allowed = can_manage_team(db, team_id, user)
    return TeamCapabilities(team_id=team_id, can_manage_members=allowed, can_register_for_tournament=allowed)


@router.get("/api/v1/tournaments/{tournament_id}/capabilities", response_model=TournamentCapabilities)
def tournament_capabilities(
    tournament_id: TournamentId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    allowed = can_manage_tournament(tournament, user)
    transitions = sorted(TRANSITIONS[tournament.status]) if allowed else []
    fields = []
    if transitions:
        fields = sorted(ONGOING_EDITABLE if tournament.status == "ONGOING" else TournamentUpdate.model_fields)
    return TournamentCapabilities(
        tournament_id=tournament_id,
        can_manage=allowed,
        can_update=bool(fields),
        can_change_status=bool(transitions),
        can_review_registrations=allowed and tournament.status == "UPCOMING",
        editable_fields=fields,
        allowed_status_transitions=transitions,
    )
