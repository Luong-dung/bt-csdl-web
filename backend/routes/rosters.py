"""Foundation reads only. Roster replace/lock mutations are W44-2-03/04."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config.database import get_db
from core.rosters import roster_permissions
from core.tournaments import get_tournament_or_404
from core.validation import ResourceId
from middleware.auth import can_manage_tournament, get_current_user
from modules.identity.models import User
from modules.teams.models import Team
from modules.tournaments.roster_schemas import RosterCapabilities, RosterLockRead

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}', tags=['Tournament rosters'])


@router.get('/roster-lock', response_model=RosterLockRead)
def roster_lock_state(tournament_id: ResourceId, db: Session = Depends(get_db)):
    tournament = get_tournament_or_404(db, tournament_id)
    return RosterLockRead(tournament_id=tournament_id, locked=tournament.roster_locked_at is not None,
                          locked_at=tournament.roster_locked_at)


@router.get('/teams/{team_id}/roster/capabilities', response_model=RosterCapabilities)
def roster_capabilities(tournament_id: ResourceId, team_id: ResourceId,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tournament = get_tournament_or_404(db, tournament_id)
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy đội tuyển')
    view, edit = roster_permissions(db, tournament, team_id, user, can_manage_tournament(tournament, user))
    return RosterCapabilities(tournament_id=tournament_id, team_id=team_id,
                              can_view_roster=view, can_edit_roster=edit)
