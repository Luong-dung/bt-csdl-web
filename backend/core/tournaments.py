"""Shared tournament authorization and row-lock order for all writers."""

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from middleware.auth import can_manage_tournament
from modules.identity.models import RoleAssignment, User
from modules.tournaments.models import (
    Match, Stage, Tournament, TournamentBracket, TournamentRegistration, TournamentRoster, TournamentStanding,
)


def get_tournament_or_404(db: Session, tournament_id: int) -> Tournament:
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament


def ensure_tournament_manager(tournament: Tournament, user: User) -> None:
    if not can_manage_tournament(tournament, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản lý giải đấu này")


def lock_tournament(db: Session, tournament_id: int) -> Tournament:
    tournament = db.scalar(select(Tournament).where(Tournament.tournament_id == tournament_id)
                           .with_for_update().execution_options(populate_existing=True))
    if tournament is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giải đấu")
    return tournament


def lock_tournament_as(db: Session, tournament_id: int, user: User) -> tuple[Tournament, User]:
    """Lock the tournament, then reload the actor so callers recheck permissions after waiting."""
    tournament = lock_tournament(db, tournament_id)
    if isinstance(user, User):
        # A role/assignment or the tournament creator may change while waiting.
        user = db.get(User, user.user_id, populate_existing=True)
        if user is None:
            raise HTTPException(status_code=401, detail="Tài khoản không tồn tại", headers={"WWW-Authenticate": "Bearer"})
        db.expire(user, ['role', 'assignments'])
    return tournament, user


def get_managed_tournament(db: Session, tournament_id: int, user: User) -> Tournament:
    # Reject unauthorized callers before they can join the row-lock queue.
    ensure_tournament_manager(get_tournament_or_404(db, tournament_id), user)
    tournament, user = lock_tournament_as(db, tournament_id, user)
    ensure_tournament_manager(tournament, user)
    return tournament


# W47-04 (W05-01): rows that make a tournament part of history. Checked under the tournament lock;
# every writer of these rows locks the tournament first, so none can appear between check and delete.
DELETE_BLOCKERS = (
    (TournamentRegistration, "đơn đăng ký"),
    (TournamentRoster, "đội hình"),
    (Stage, "giai đoạn"),
    (Match, "trận đấu"),
    (TournamentBracket, "bracket"),
    (TournamentStanding, "bảng xếp hạng"),
)


def tournament_delete_blocker(db: Session, tournament: Tournament) -> str | None:
    """Reason the tournament cannot be deleted, or None. Never deletes child rows."""
    if tournament.status != 'UPCOMING' or tournament.roster_locked_at is not None:
        return "Chỉ xóa được giải UPCOMING chưa khóa đội hình; hãy hủy giải (CANCELLED) thay vì xóa"
    tid = tournament.tournament_id
    for model, label in DELETE_BLOCKERS:
        if db.scalar(select(exists().where(model.tournament_id == tid))):
            return f"Giải đã có {label}, không thể xóa; hãy hủy giải (CANCELLED) thay vì xóa"
    # Referee/organizer assignments (active or revoked) are permission history of this tournament.
    if db.scalar(select(exists().where(RoleAssignment.scope_type == 'TOURNAMENT', RoleAssignment.scope_id == tid))):
        return "Giải đã có lịch sử phân quyền (trọng tài/quản lý), không thể xóa; hãy hủy giải (CANCELLED)"
    return None
