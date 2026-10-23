"""Registration writers must lock tournament first, then registration, until commit."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.tournaments.models import Tournament, TournamentRegistration


def lock_registration_tournament(db: Session, tournament_id: int) -> Tournament:
    tournament = db.scalar(select(Tournament).where(Tournament.tournament_id == tournament_id)
                           .with_for_update().execution_options(populate_existing=True))
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament


def ensure_registration_open(tournament: Tournament) -> None:
    if tournament.status != "UPCOMING":
        raise HTTPException(status_code=409, detail="Giải đấu đã đóng đăng ký")


def lock_registration(db: Session, tournament_id: int, registration_id: int) -> TournamentRegistration:
    registration = db.scalar(select(TournamentRegistration).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.registration_id == registration_id,
    ).with_for_update().execution_options(populate_existing=True))
    if registration is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký trong giải")
    return registration
