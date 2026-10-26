"""Authenticated permission hints; mutations always recheck the same policies."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from core.tournament_policy import registration_resolution_open, registrations_open
from core.validation import ResourceId
from middleware.auth import (
    can_manage_tournament, get_current_user, has_role, managed_teams_query,
)
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.models import Tournament
from routes.tournaments import ONGOING_EDITABLE, TRANSITIONS, TournamentUpdate

router = APIRouter(tags=["Capabilities"])


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
    can_approve_registrations: bool
    roster_locked: bool
    can_lock_roster: bool
    editable_fields: list[str]
    allowed_status_transitions: list[str]


@router.get("/api/v1/auth/capabilities", response_model=GlobalCapabilities)
def global_capabilities(user: User = Depends(get_current_user)):
    return GlobalCapabilities(
        can_manage_catalog=has_role(user, "ADMIN"),
        can_create_tournament=has_role(user, "ADMIN", "ORGANIZER"),
    )


@router.get("/api/v1/teams/{team_id}/capabilities", response_model=TeamCapabilities)
def team_capabilities(
    team_id: ResourceId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    managed_ids = managed_teams_query(user).with_only_columns(Team.team_id).correlate(None)
    team = db.execute(select(Team.team_id, Team.team_id.in_(managed_ids).label('can_manage'))
                      .where(Team.team_id == team_id)).one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")
    allowed = team.can_manage
    return TeamCapabilities(team_id=team_id, can_manage_members=allowed, can_register_for_tournament=allowed)


@router.get("/api/v1/tournaments/{tournament_id}/capabilities", response_model=TournamentCapabilities)
def tournament_capabilities(
    tournament_id: ResourceId,
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
        can_review_registrations=allowed and registration_resolution_open(tournament.status),
        can_approve_registrations=allowed and registrations_open(tournament.status, tournament.roster_locked_at),
        roster_locked=tournament.roster_locked_at is not None,
        can_lock_roster=allowed and registrations_open(tournament.status, tournament.roster_locked_at),
        editable_fields=fields,
        allowed_status_transitions=transitions,
    )
