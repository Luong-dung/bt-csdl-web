"""W45-02: atomic match result submission with audit.

One transaction: lock tournament -> match, recheck permission and state after the
wait, update the match and queue the audit row, then commit. Any failure rolls back both.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.matches import can_submit_result, lock_match_context, match_result_open, match_state
from core.validation import ResourceId
from middleware.auth import get_current_user
from modules.identity.models import User
from modules.tournaments.match_schemas import MatchRead, ResultInput, match_read

router = APIRouter(prefix='/api/v1/tournaments/{tournament_id}/matches', tags=['Match results'])


@router.put('/{match_id}/result', response_model=MatchRead)
def submit_result(tournament_id: ResourceId, match_id: ResourceId, data: ResultInput,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        tournament, match, user = lock_match_context(db, tournament_id, match_id, user, can_submit_result)
        winner_id = match.team1_id if data.score_team1 > data.score_team2 else match.team2_id
        if match.status == 'COMPLETED':
            # Idempotent replay of the stored result: no second audit row.
            if (match.score_team1, match.score_team2, match.winner_id) == (data.score_team1, data.score_team2, winner_id):
                result = match_read(db, match)
                db.rollback()
                return result
            raise HTTPException(status_code=409, detail='Trận đã có kết quả khác, không thể ghi đè')
        if not match_result_open(tournament, match):
            raise HTTPException(status_code=409, detail='Chỉ nhập kết quả cho trận ONGOING khi giải ONGOING')
        if match.team1_id is None or match.team2_id is None:
            raise HTTPException(status_code=409, detail='Trận chưa đủ hai đội')
        before = match_state(match)
        match.score_team1, match.score_team2 = data.score_team1, data.score_team2
        match.winner_id, match.status = winner_id, 'COMPLETED'
        db.flush()
        record_audit(db, user.user_id, 'MATCH_RESULT_SUBMITTED', 'match', {
            'tournament_id': tournament_id, 'match_id': match_id, 'before': before, 'after': match_state(match),
        })
        result = match_read(db, match)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Kết quả vi phạm ràng buộc dữ liệu trận')
    except Exception:
        db.rollback()
        raise
