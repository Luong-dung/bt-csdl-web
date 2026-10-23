"""Registration writers must lock tournament first, then registration, until commit."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.tournaments.models import Tournament, TournamentRegistration
from core.tournament_policy import registrations_open
from core.tournaments import lock_tournament as lock_registration_tournament


def registration_timestamp(db: Session):
    # PostgreSQL now() is fixed at transaction start, possibly before a lock wait.
    # clock_timestamp() uses the DB wall clock after the lock has been acquired.
    clock = func.clock_timestamp() if db.get_bind().dialect.name == 'postgresql' else func.current_timestamp()
    return db.scalar(select(clock))


def ensure_registration_open(tournament: Tournament) -> None:
    if not registrations_open(tournament.status):
        raise HTTPException(status_code=409, detail="Giải đấu đã đóng đăng ký")


def lock_registration(db: Session, tournament_id: int, registration_id: int) -> TournamentRegistration:
    registration = db.scalar(select(TournamentRegistration).where(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.registration_id == registration_id,
    ).with_for_update().execution_options(populate_existing=True))
    if registration is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký trong giải")
    return registration
