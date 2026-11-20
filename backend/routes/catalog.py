from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from core.audit import record_audit
from middleware.auth import get_current_user, require_role
from modules.identity.models import User
from modules.catalog.models import CompetitionArea, Country, Game, Publisher
from modules.teams.models import Team
from modules.tournaments.models import Tournament

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
AREA_CODE_PATTERN = r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$"
# ISO 3166-1 alpha-2; input is upper-cased before this check.
COUNTRY_CODE_PATTERN = r"^[A-Z]{2}$"


class CatalogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PatchInput(CatalogInput):
    @field_validator("*")
    @classmethod
    def reject_null(cls, value, info):
        # parent_id and country_code are the only columns that may be cleared with null.
        if value is None and info.field_name not in ("parent_id", "country_code"):
            raise ValueError("Không được để trống trường này")
        return value


class PublisherCreate(CatalogInput):
    name: str = Field(min_length=2, max_length=120)


class PublisherUpdate(PatchInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)


class PublisherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    publisher_id: int
    name: str


class GameCreate(CatalogInput):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120, pattern=SLUG_PATTERN)
    publisher_id: int = Field(gt=0)


class GameUpdate(PatchInput):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=SLUG_PATTERN)
    publisher_id: int | None = Field(default=None, gt=0)


class GameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    game_id: int
    name: str
    slug: str
    publisher_id: int


def upper_code(value):
    return value.strip().upper() if isinstance(value, str) else value


CountryCode = Annotated[str, BeforeValidator(upper_code), Field(pattern=COUNTRY_CODE_PATTERN)]


class AreaCreate(CatalogInput):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=30, pattern=AREA_CODE_PATTERN)
    parent_id: int | None = Field(default=None, gt=0)
    country_code: CountryCode | None = None


class AreaUpdate(PatchInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=AREA_CODE_PATTERN)
    parent_id: int | None = Field(default=None, gt=0)
    country_code: CountryCode | None = None


class AreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    area_id: int
    name: str
    code: str
    parent_id: int | None
    country_code: str | None


class CountryCreate(CatalogInput):
    country_code: CountryCode
    name: str = Field(min_length=2, max_length=120)


class CountryUpdate(CatalogInput):
    name: str = Field(min_length=2, max_length=120)


class CountryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    country_code: str
    name: str


def get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy {label}")
    return item


def ensure_unique(db: Session, column, value, current_id=None, id_column=None, message="Dữ liệu đã tồn tại"):
    query = select(column).where(column == value)
    if current_id is not None:
        query = query.where(id_column != current_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail=message)


def ensure_unused(db: Session, column, value, message: str):
    if db.scalar(select(exists().where(column == value))):
        raise HTTPException(status_code=409, detail=message)


def ensure_publisher(db: Session, publisher_id: int):
    if db.get(Publisher, publisher_id) is None:
        raise HTTPException(status_code=422, detail="Nhà phát hành không tồn tại")


def ensure_country(db: Session, country_code: str | None):
    if country_code is not None and db.get(Country, country_code) is None:
        raise HTTPException(status_code=422, detail="Quốc gia không tồn tại")


def ensure_valid_parent(db: Session, parent_id: int | None, area_id: int | None = None):
    """Reject a missing parent, and any parent that would close a cycle."""
    current = parent_id
    while current is not None:
        if current == area_id:
            raise HTTPException(status_code=422, detail="Khu vực cha không được là chính nó hoặc khu vực con của nó")
        parent = db.get(CompetitionArea, current)
        if parent is None:
            raise HTTPException(status_code=422, detail="Khu vực cha không tồn tại")
        current = parent.parent_id


def snapshot(item) -> dict:
    return jsonable_encoder({column.name: getattr(item, column.name) for column in item.__table__.columns})


def audit_change(db: Session, user, action: str, resource: str, item, before: dict | None, deleted=False):
    """W47-02: catalog writes are audited in the same commit as the change."""
    # Flush for the new ID; a concurrent duplicate surfaces here, so map it to 409 like commit_or_409.
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu vi phạm ràng buộc, vui lòng kiểm tra lại")
    after = None if deleted else snapshot(item)
    resource_id = (before or after)[f'{resource}_id']
    record_audit(db, getattr(user, 'user_id', None), action, resource,
                 {f'{resource}_id': resource_id, 'before': before, 'after': after})


def commit_or_409(db: Session):
    # Fallback for a concurrent insert that slips past the pre-checks.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu vi phạm ràng buộc, vui lòng kiểm tra lại")


# Publishers


@router.get("/publishers", response_model=list[PublisherRead])
def list_publishers(db: Session = Depends(get_db)):
    return db.scalars(select(Publisher).order_by(Publisher.name)).all()


@router.get("/publishers/{publisher_id}", response_model=PublisherRead)
def get_publisher(publisher_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Publisher, publisher_id, "nhà phát hành")


@router.post(
    "/publishers",
    response_model=PublisherRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_publisher(data: PublisherCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_unique(db, Publisher.name, data.name, message="Tên nhà phát hành đã tồn tại")
    publisher = Publisher(name=data.name)
    db.add(publisher)
    audit_change(db, user, "CATALOG_PUBLISHER_CREATED", "publisher", publisher, None)
    commit_or_409(db)
    return publisher


@router.patch("/publishers/{publisher_id}", response_model=PublisherRead, dependencies=[Depends(require_role("ADMIN"))])
def update_publisher(publisher_id: int, data: PublisherUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    publisher = get_or_404(db, Publisher, publisher_id, "nhà phát hành")
    before = snapshot(publisher)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        ensure_unique(db, Publisher.name, changes["name"], publisher_id, Publisher.publisher_id,
                      "Tên nhà phát hành đã tồn tại")
    for field, value in changes.items():
        setattr(publisher, field, value)
    audit_change(db, user, "CATALOG_PUBLISHER_UPDATED", "publisher", publisher, before)
    commit_or_409(db)
    return publisher


@router.delete(
    "/publishers/{publisher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_publisher(publisher_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    publisher = get_or_404(db, Publisher, publisher_id, "nhà phát hành")
    ensure_unused(db, Game.publisher_id, publisher_id, "Nhà phát hành vẫn còn game, không thể xóa")
    before = snapshot(publisher)
    db.delete(publisher)
    audit_change(db, user, "CATALOG_PUBLISHER_DELETED", "publisher", publisher, before, deleted=True)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Games


@router.get("/games", response_model=list[GameRead])
def list_games(publisher_id: int | None = None, db: Session = Depends(get_db)):
    query = select(Game).order_by(Game.name)
    if publisher_id is not None:
        query = query.where(Game.publisher_id == publisher_id)
    return db.scalars(query).all()


@router.get("/games/{game_id}", response_model=GameRead)
def get_game(game_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Game, game_id, "game")


@router.post(
    "/games",
    response_model=GameRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_game(data: GameCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_publisher(db, data.publisher_id)
    ensure_unique(db, Game.name, data.name, message="Tên game đã tồn tại")
    ensure_unique(db, Game.slug, data.slug, message="Slug game đã tồn tại")
    game = Game(**data.model_dump())
    db.add(game)
    audit_change(db, user, "CATALOG_GAME_CREATED", "game", game, None)
    commit_or_409(db)
    return game


@router.patch("/games/{game_id}", response_model=GameRead, dependencies=[Depends(require_role("ADMIN"))])
def update_game(game_id: int, data: GameUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    game = get_or_404(db, Game, game_id, "game")
    before = snapshot(game)
    changes = data.model_dump(exclude_unset=True)
    if "publisher_id" in changes:
        ensure_publisher(db, changes["publisher_id"])
    if "name" in changes:
        ensure_unique(db, Game.name, changes["name"], game_id, Game.game_id, "Tên game đã tồn tại")
    if "slug" in changes:
        ensure_unique(db, Game.slug, changes["slug"], game_id, Game.game_id, "Slug game đã tồn tại")
    for field, value in changes.items():
        setattr(game, field, value)
    audit_change(db, user, "CATALOG_GAME_UPDATED", "game", game, before)
    commit_or_409(db)
    return game


@router.delete(
    "/games/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_game(game_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    game = get_or_404(db, Game, game_id, "game")
    ensure_unused(db, Team.game_id, game_id, "Game đang được đội tuyển sử dụng, không thể xóa")
    ensure_unused(db, Tournament.game_id, game_id, "Game đang được giải đấu sử dụng, không thể xóa")
    before = snapshot(game)
    db.delete(game)
    audit_change(db, user, "CATALOG_GAME_DELETED", "game", game, before, deleted=True)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Competition areas


@router.get("/areas", response_model=list[AreaRead])
def list_areas(parent_id: int | None = None, country_code: str | None = None, db: Session = Depends(get_db)):
    query = select(CompetitionArea).order_by(CompetitionArea.name)
    if parent_id is not None:
        query = query.where(CompetitionArea.parent_id == parent_id)
    if country_code is not None:
        query = query.where(CompetitionArea.country_code == country_code.strip().upper())
    return db.scalars(query).all()


@router.get("/areas/{area_id}", response_model=AreaRead)
def get_area(area_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, CompetitionArea, area_id, "khu vực")


@router.post(
    "/areas",
    response_model=AreaRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_area(data: AreaCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_valid_parent(db, data.parent_id)
    ensure_country(db, data.country_code)
    ensure_unique(db, CompetitionArea.code, data.code, message="Mã khu vực đã tồn tại")
    area = CompetitionArea(**data.model_dump())
    db.add(area)
    audit_change(db, user, "CATALOG_AREA_CREATED", "area", area, None)
    commit_or_409(db)
    return area


@router.patch("/areas/{area_id}", response_model=AreaRead, dependencies=[Depends(require_role("ADMIN"))])
def update_area(area_id: int, data: AreaUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    area = get_or_404(db, CompetitionArea, area_id, "khu vực")
    before = snapshot(area)
    changes = data.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        ensure_valid_parent(db, changes["parent_id"], area_id)
    if "country_code" in changes:
        ensure_country(db, changes["country_code"])
    if "code" in changes:
        ensure_unique(db, CompetitionArea.code, changes["code"], area_id, CompetitionArea.area_id,
                      "Mã khu vực đã tồn tại")
    for field, value in changes.items():
        setattr(area, field, value)
    audit_change(db, user, "CATALOG_AREA_UPDATED", "area", area, before)
    commit_or_409(db)
    return area


@router.delete(
    "/areas/{area_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_area(area_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    area = get_or_404(db, CompetitionArea, area_id, "khu vực")
    ensure_unused(db, CompetitionArea.parent_id, area_id, "Khu vực vẫn còn khu vực con, không thể xóa")
    ensure_unused(db, Tournament.area_id, area_id, "Khu vực đang được giải đấu sử dụng, không thể xóa")
    before = snapshot(area)
    db.delete(area)
    audit_change(db, user, "CATALOG_AREA_DELETED", "area", area, before, deleted=True)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Countries (W47-04 / W03-02): public read, ADMIN create/rename. The code is the key and never changes;
# no delete endpoint (areas reference countries with ON DELETE RESTRICT).


def country_state(country: Country) -> dict:
    return {"country_code": country.country_code, "name": country.name}


def audit_country(db: Session, user, action: str, country: Country, before: dict | None):
    # country_code is not an integer, so audit resource_id stays NULL; filter by resource/action instead.
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã hoặc tên quốc gia đã tồn tại")
    record_audit(db, getattr(user, "user_id", None), action, "country",
                 {"country_code": country.country_code, "before": before, "after": country_state(country)})


@router.get("/countries", response_model=list[CountryRead])
def list_countries(db: Session = Depends(get_db)):
    return db.scalars(select(Country).order_by(Country.name)).all()


@router.get("/countries/{country_code}", response_model=CountryRead)
def get_country(country_code: str, db: Session = Depends(get_db)):
    return get_or_404(db, Country, country_code.strip().upper(), "quốc gia")


@router.post("/countries", response_model=CountryRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("ADMIN"))])
def create_country(data: CountryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(Country, data.country_code) is not None:
        raise HTTPException(status_code=409, detail="Mã quốc gia đã tồn tại")
    ensure_unique(db, Country.name, data.name, message="Tên quốc gia đã tồn tại")
    country = Country(country_code=data.country_code, name=data.name)
    db.add(country)
    audit_country(db, user, "CATALOG_COUNTRY_CREATED", country, None)
    commit_or_409(db)
    return country


@router.patch("/countries/{country_code}", response_model=CountryRead,
              dependencies=[Depends(require_role("ADMIN"))])
def update_country(country_code: str, data: CountryUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    country = get_or_404(db, Country, country_code.strip().upper(), "quốc gia")
    if country.name == data.name:
        return country
    ensure_unique(db, Country.name, data.name, country.country_code, Country.country_code,
                  "Tên quốc gia đã tồn tại")
    before = country_state(country)
    country.name = data.name
    audit_country(db, user, "CATALOG_COUNTRY_UPDATED", country, before)
    commit_or_409(db)
    return country
