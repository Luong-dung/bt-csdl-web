from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from middleware.auth import get_current_user
from modules.catalog.models import CompetitionArea, Game, Publisher
from modules.teams.models import Team
from modules.tournaments.models import Tournament

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
AREA_CODE_PATTERN = r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$"


class CatalogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PatchInput(CatalogInput):
    @field_validator("*")
    @classmethod
    def reject_null(cls, value, info):
        # parent_id is the only column that may be cleared with null.
        if value is None and info.field_name != "parent_id":
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


class AreaCreate(CatalogInput):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=30, pattern=AREA_CODE_PATTERN)
    parent_id: int | None = Field(default=None, gt=0)


class AreaUpdate(PatchInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=AREA_CODE_PATTERN)
    parent_id: int | None = Field(default=None, gt=0)


class AreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    area_id: int
    name: str
    code: str
    parent_id: int | None


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
    dependencies=[Depends(get_current_user)],
)
def create_publisher(data: PublisherCreate, db: Session = Depends(get_db)):
    ensure_unique(db, Publisher.name, data.name, message="Tên nhà phát hành đã tồn tại")
    publisher = Publisher(name=data.name)
    db.add(publisher)
    commit_or_409(db)
    return publisher


@router.patch("/publishers/{publisher_id}", response_model=PublisherRead, dependencies=[Depends(get_current_user)])
def update_publisher(publisher_id: int, data: PublisherUpdate, db: Session = Depends(get_db)):
    publisher = get_or_404(db, Publisher, publisher_id, "nhà phát hành")
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        ensure_unique(db, Publisher.name, changes["name"], publisher_id, Publisher.publisher_id,
                      "Tên nhà phát hành đã tồn tại")
    for field, value in changes.items():
        setattr(publisher, field, value)
    commit_or_409(db)
    return publisher


@router.delete(
    "/publishers/{publisher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_publisher(publisher_id: int, db: Session = Depends(get_db)):
    publisher = get_or_404(db, Publisher, publisher_id, "nhà phát hành")
    ensure_unused(db, Game.publisher_id, publisher_id, "Nhà phát hành vẫn còn game, không thể xóa")
    db.delete(publisher)
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
    dependencies=[Depends(get_current_user)],
)
def create_game(data: GameCreate, db: Session = Depends(get_db)):
    ensure_publisher(db, data.publisher_id)
    ensure_unique(db, Game.name, data.name, message="Tên game đã tồn tại")
    ensure_unique(db, Game.slug, data.slug, message="Slug game đã tồn tại")
    game = Game(**data.model_dump())
    db.add(game)
    commit_or_409(db)
    return game


@router.patch("/games/{game_id}", response_model=GameRead, dependencies=[Depends(get_current_user)])
def update_game(game_id: int, data: GameUpdate, db: Session = Depends(get_db)):
    game = get_or_404(db, Game, game_id, "game")
    changes = data.model_dump(exclude_unset=True)
    if "publisher_id" in changes:
        ensure_publisher(db, changes["publisher_id"])
    if "name" in changes:
        ensure_unique(db, Game.name, changes["name"], game_id, Game.game_id, "Tên game đã tồn tại")
    if "slug" in changes:
        ensure_unique(db, Game.slug, changes["slug"], game_id, Game.game_id, "Slug game đã tồn tại")
    for field, value in changes.items():
        setattr(game, field, value)
    commit_or_409(db)
    return game


@router.delete(
    "/games/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_game(game_id: int, db: Session = Depends(get_db)):
    game = get_or_404(db, Game, game_id, "game")
    ensure_unused(db, Team.game_id, game_id, "Game đang được đội tuyển sử dụng, không thể xóa")
    ensure_unused(db, Tournament.game_id, game_id, "Game đang được giải đấu sử dụng, không thể xóa")
    db.delete(game)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Competition areas


@router.get("/areas", response_model=list[AreaRead])
def list_areas(parent_id: int | None = None, db: Session = Depends(get_db)):
    query = select(CompetitionArea).order_by(CompetitionArea.name)
    if parent_id is not None:
        query = query.where(CompetitionArea.parent_id == parent_id)
    return db.scalars(query).all()


@router.get("/areas/{area_id}", response_model=AreaRead)
def get_area(area_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, CompetitionArea, area_id, "khu vực")


@router.post(
    "/areas",
    response_model=AreaRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
def create_area(data: AreaCreate, db: Session = Depends(get_db)):
    ensure_valid_parent(db, data.parent_id)
    ensure_unique(db, CompetitionArea.code, data.code, message="Mã khu vực đã tồn tại")
    area = CompetitionArea(**data.model_dump())
    db.add(area)
    commit_or_409(db)
    return area


@router.patch("/areas/{area_id}", response_model=AreaRead, dependencies=[Depends(get_current_user)])
def update_area(area_id: int, data: AreaUpdate, db: Session = Depends(get_db)):
    area = get_or_404(db, CompetitionArea, area_id, "khu vực")
    changes = data.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        ensure_valid_parent(db, changes["parent_id"], area_id)
    if "code" in changes:
        ensure_unique(db, CompetitionArea.code, changes["code"], area_id, CompetitionArea.area_id,
                      "Mã khu vực đã tồn tại")
    for field, value in changes.items():
        setattr(area, field, value)
    commit_or_409(db)
    return area


@router.delete(
    "/areas/{area_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_area(area_id: int, db: Session = Depends(get_db)):
    area = get_or_404(db, CompetitionArea, area_id, "khu vực")
    ensure_unused(db, CompetitionArea.parent_id, area_id, "Khu vực vẫn còn khu vực con, không thể xóa")
    ensure_unused(db, Tournament.area_id, area_id, "Khu vực đang được giải đấu sử dụng, không thể xóa")
    db.delete(area)
    commit_or_409(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
