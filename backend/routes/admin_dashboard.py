"""W48-05 read-only Admin Dashboard metrics, admin capabilities, and user search."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from config.database import get_db
from core.matches import as_utc
from core.permissions import (
    AUDIT_LOG_VIEW_ALL,
    CATALOG_MANAGE,
    ORGANIZATION_CREATE,
    ROLE_ASSIGNMENT_MANAGE,
)
from middleware.auth import get_current_user, has_permission, require_permission
from modules.identity.models import Role, RoleAssignment, User
from modules.teams.models import Organization, Team
from modules.tournaments.models import (
    Match,
    Stage,
    Tournament,
    TournamentRegistration,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin dashboard"])

CANONICAL_ROLES = (
    "ADMIN",
    "ORGANIZER",
    "REFEREE",
    "TEAM_MANAGER",
    "PLAYER",
    "VIEWER",
)
TOURNAMENT_STATUSES = ("UPCOMING", "ONGOING", "COMPLETED", "CANCELLED")
ACTIVE_TOURNAMENT_STATUSES = ("UPCOMING", "ONGOING")
AWAITING_MATCH_STATUSES = ("PENDING", "ONGOING")


class AdminCapabilitiesRead(BaseModel):
    can_view_dashboard: bool
    can_manage_catalog: bool
    can_manage_roles: bool
    can_view_audit: bool
    can_create_organization: bool


class UserSummaryRead(BaseModel):
    total: int
    by_role: dict[str, int]


class TournamentStatusSummaryRead(BaseModel):
    total: int
    by_status: dict[str, int]


class PendingMatchItemRead(BaseModel):
    match_id: int
    tournament_id: int
    tournament_name: str
    tournament_status: str
    stage_name: str
    round_no: int
    status: str
    team1_name: str | None
    team2_name: str | None
    scheduled_at: datetime | None


class PendingMatchesSummaryRead(BaseModel):
    total: int
    ongoing: int
    pending_ready: int
    pending_tbd: int
    items: list[PendingMatchItemRead]


class AdminDashboardRead(BaseModel):
    capabilities: AdminCapabilitiesRead
    users: UserSummaryRead
    teams_total: int
    organizations_total: int
    active_role_assignments: int
    pending_registrations: int
    tournaments: TournamentStatusSummaryRead
    matches_awaiting_result: PendingMatchesSummaryRead


class AdminUserCandidateRead(BaseModel):
    """Privacy-safe user lookup for role assignment: never exposes email."""

    user_id: int
    username: str
    real_name: str | None
    role: str


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_admin_capabilities(user: User) -> AdminCapabilitiesRead:
    can_catalog = has_permission(user, CATALOG_MANAGE)
    can_roles = has_permission(user, ROLE_ASSIGNMENT_MANAGE)
    can_audit = has_permission(user, AUDIT_LOG_VIEW_ALL)
    can_org = has_permission(user, ORGANIZATION_CREATE)
    return AdminCapabilitiesRead(
        can_view_dashboard=can_catalog or can_roles or can_audit or can_org,
        can_manage_catalog=can_catalog,
        can_manage_roles=can_roles,
        can_view_audit=can_audit,
        can_create_organization=can_org,
    )


@router.get("/capabilities", response_model=AdminCapabilitiesRead)
def get_admin_capabilities(
    response: Response,
    user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    return build_admin_capabilities(user)


@router.get("/dashboard", response_model=AdminDashboardRead)
def get_admin_dashboard(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    caps = build_admin_capabilities(user)
    if not caps.can_view_dashboard:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền thực hiện thao tác này",
        )
    response.headers["Cache-Control"] = "private, no-store"

    role_rows = db.execute(
        select(Role.role_name, func.count(User.user_id))
        .select_from(Role)
        .outerjoin(User, User.role_id == Role.role_id)
        .group_by(Role.role_name)
    ).all()
    raw_role_counts = {name: int(cnt) for name, cnt in role_rows}
    by_role = {role: raw_role_counts.get(role, 0) for role in CANONICAL_ROLES}
    for role_name, cnt in sorted(raw_role_counts.items()):
        if role_name not in by_role:
            by_role[role_name] = cnt
    users_total = int(db.scalar(select(func.count(User.user_id))) or 0)

    teams_total = int(db.scalar(select(func.count(Team.team_id))) or 0)
    organizations_total = int(
        db.scalar(select(func.count(Organization.organization_id))) or 0
    )
    active_assignments = int(
        db.scalar(
            select(func.count(RoleAssignment.assignment_id)).where(
                RoleAssignment.revoked_at.is_(None)
            )
        )
        or 0
    )
    pending_registrations = int(
        db.scalar(
            select(func.count(TournamentRegistration.registration_id))
            .join(
                Tournament,
                Tournament.tournament_id == TournamentRegistration.tournament_id,
            )
            .where(
                TournamentRegistration.status == "PENDING",
                Tournament.status == "UPCOMING",
            )
        )
        or 0
    )

    t_rows = db.execute(
        select(Tournament.status, func.count(Tournament.tournament_id)).group_by(
            Tournament.status
        )
    ).all()
    raw_t_counts = {status: int(cnt) for status, cnt in t_rows}
    t_by_status = {s: raw_t_counts.get(s, 0) for s in TOURNAMENT_STATUSES}
    tournaments_total = sum(t_by_status.values())

    active_match_filter = (
        Tournament.status.in_(ACTIVE_TOURNAMENT_STATUSES),
        Match.status.in_(AWAITING_MATCH_STATUSES),
    )
    ongoing_count = int(
        db.scalar(
            select(func.count(Match.match_id))
            .join(Tournament, Tournament.tournament_id == Match.tournament_id)
            .where(*active_match_filter, Match.status == "ONGOING")
        )
        or 0
    )
    pending_ready_count = int(
        db.scalar(
            select(func.count(Match.match_id))
            .join(Tournament, Tournament.tournament_id == Match.tournament_id)
            .where(
                *active_match_filter,
                Match.status == "PENDING",
                Match.team1_id.is_not(None),
                Match.team2_id.is_not(None),
            )
        )
        or 0
    )
    pending_tbd_count = int(
        db.scalar(
            select(func.count(Match.match_id))
            .join(Tournament, Tournament.tournament_id == Match.tournament_id)
            .where(
                *active_match_filter,
                Match.status == "PENDING",
                or_(Match.team1_id.is_(None), Match.team2_id.is_(None)),
            )
        )
        or 0
    )

    team1_alias = aliased(Team)
    team2_alias = aliased(Team)
    priority_expr = case(
        (Match.status == "ONGOING", 0),
        (Match.team1_id.is_not(None) & Match.team2_id.is_not(None), 1),
        else_=2,
    )
    sched_null_last = case((Match.scheduled_at.is_(None), 1), else_=0)

    match_rows = db.execute(
        select(
            Match,
            Tournament.name,
            Tournament.status,
            Stage.name,
            team1_alias.name,
            team2_alias.name,
        )
        .join(Tournament, Tournament.tournament_id == Match.tournament_id)
        .join(Stage, Stage.stage_id == Match.stage_id)
        .outerjoin(team1_alias, team1_alias.team_id == Match.team1_id)
        .outerjoin(team2_alias, team2_alias.team_id == Match.team2_id)
        .where(*active_match_filter)
        .order_by(
            priority_expr,
            sched_null_last,
            Match.scheduled_at.asc(),
            Match.match_id.asc(),
        )
        .limit(8)
    ).all()

    items = [
        PendingMatchItemRead(
            match_id=m.match_id,
            tournament_id=m.tournament_id,
            tournament_name=t_name,
            tournament_status=t_status,
            stage_name=s_name,
            round_no=m.round_no,
            status=m.status,
            team1_name=t1_name,
            team2_name=t2_name,
            scheduled_at=as_utc(m.scheduled_at),
        )
        for m, t_name, t_status, s_name, t1_name, t2_name in match_rows
    ]

    return AdminDashboardRead(
        capabilities=caps,
        users=UserSummaryRead(total=users_total, by_role=by_role),
        teams_total=teams_total,
        organizations_total=organizations_total,
        active_role_assignments=active_assignments,
        pending_registrations=pending_registrations,
        tournaments=TournamentStatusSummaryRead(
            total=tournaments_total,
            by_status=t_by_status,
        ),
        matches_awaiting_result=PendingMatchesSummaryRead(
            total=ongoing_count + pending_ready_count + pending_tbd_count,
            ongoing=ongoing_count,
            pending_ready=pending_ready_count,
            pending_tbd=pending_tbd_count,
            items=items,
        ),
    )


@router.get(
    "/users/search",
    response_model=list[AdminUserCandidateRead],
    dependencies=[Depends(require_permission(ROLE_ASSIGNMENT_MANAGE))],
)
def search_admin_users(
    response: Response,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Privacy-safe user search for global/scoped role assignment (never email)."""
    term = q.strip()
    if len(term) < 2:
        raise HTTPException(
            status_code=422,
            detail="Từ khóa tìm kiếm cần tối thiểu 2 ký tự",
        )
    response.headers["Cache-Control"] = "private, no-store"
    pattern = f"%{_escape_like(term)}%"
    rows = db.execute(
        select(User, Role.role_name)
        .join(Role, Role.role_id == User.role_id)
        .where(
            or_(
                User.username.ilike(pattern, escape="\\"),
                User.real_name.ilike(pattern, escape="\\"),
            )
        )
        .order_by(User.username, User.user_id)
        .limit(limit)
    ).all()
    return [
        AdminUserCandidateRead(
            user_id=u.user_id,
            username=u.username,
            real_name=u.real_name,
            role=role_name,
        )
        for u, role_name in rows
    ]
