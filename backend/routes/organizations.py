"""W47-03 (W04-01): organizations. Public read; ADMIN creates; ADMIN or the organization's
TEAM_MANAGER (ORGANIZATION scope) renames. No delete: teams and scoped assignments reference it."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from core.validation import ResourceId
from core.permissions import ORGANIZATION_CREATE
from middleware.auth import can_manage_organization, get_current_user, require_permission
from modules.identity.models import User
from modules.teams.models import Organization, Team
from routes.team import TeamRead

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class OrganizationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=150)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    organization_id: int
    name: str


class OrganizationDetail(OrganizationRead):
    teams: list[TeamRead]


class OrganizationCapabilities(BaseModel):
    organization_id: int
    can_update: bool


def get_organization_or_404(db: Session, organization_id: int, lock: bool = False) -> Organization:
    query = select(Organization).where(Organization.organization_id == organization_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    organization = db.scalar(query)
    if organization is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức")
    return organization


def ensure_name_free(db: Session, name: str, organization_id: int | None = None) -> None:
    query = select(Organization.organization_id).where(Organization.name == name)
    if organization_id is not None:
        query = query.where(Organization.organization_id != organization_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="Tên tổ chức đã tồn tại")


def save_with_audit(db: Session, user: User, action: str, organization: Organization, before: dict | None):
    # Change and audit commit together; a concurrent duplicate name surfaces as 409.
    try:
        db.flush()
        record_audit(db, user.user_id, action, "organization", {
            "organization_id": organization.organization_id,
            "before": before,
            "after": {"organization_id": organization.organization_id, "name": organization.name},
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên tổ chức đã tồn tại")
    except Exception:
        db.rollback()
        raise
    db.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationRead])
def list_organizations(db: Session = Depends(get_db)):
    return db.scalars(select(Organization).order_by(Organization.name, Organization.organization_id)).all()


@router.get("/{organization_id}", response_model=OrganizationDetail)
def get_organization(organization_id: ResourceId, db: Session = Depends(get_db)):
    organization = get_organization_or_404(db, organization_id)
    teams = db.scalars(select(Team).where(Team.organization_id == organization_id)
                       .order_by(Team.name, Team.team_id)).all()
    return OrganizationDetail(organization_id=organization.organization_id, name=organization.name,
                              teams=[TeamRead.model_validate(team) for team in teams])


@router.get("/{organization_id}/capabilities", response_model=OrganizationCapabilities)
def organization_capabilities(organization_id: ResourceId, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    get_organization_or_404(db, organization_id)
    return OrganizationCapabilities(organization_id=organization_id,
                                    can_update=can_manage_organization(organization_id, user))


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(ORGANIZATION_CREATE))])
def create_organization(data: OrganizationInput, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    ensure_name_free(db, data.name)
    organization = Organization(name=data.name)
    db.add(organization)
    return save_with_audit(db, user, "ORGANIZATION_CREATED", organization, None)


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_organization(organization_id: ResourceId, data: OrganizationInput,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_organization_or_404(db, organization_id)
    if not can_manage_organization(organization_id, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa tổ chức này")
    organization = get_organization_or_404(db, organization_id, lock=True)
    # Re-read rights after the lock wait: an assignment revoked meanwhile must not still apply.
    user = db.get(User, user.user_id, populate_existing=True)
    if user is None:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại", headers={"WWW-Authenticate": "Bearer"})
    db.expire(user, ["role", "assignments"])
    if not can_manage_organization(organization_id, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa tổ chức này")
    if organization.name == data.name:
        return organization
    ensure_name_free(db, data.name, organization_id)
    before = {"organization_id": organization.organization_id, "name": organization.name}
    organization.name = data.name
    return save_with_audit(db, user, "ORGANIZATION_UPDATED", organization, before)
