"""Create the platform schema.

Revision ID: 53bbc0801b4f
"""

from typing import Sequence, Union

from alembic import op

from config.database import Base
from modules.catalog.models import CompetitionArea, Country, Game, Publisher
from modules.identity.models import AuditLog, Permission, Role, RoleAssignment, User
from modules.teams.models import Organization, Team, TeamMembership
from modules.tournaments.models import Match, Stage, Tournament, TournamentRoster, TournamentStanding

_MODEL_TYPES = (
    CompetitionArea,
    Country,
    Game,
    Publisher,
    AuditLog,
    Permission,
    Role,
    RoleAssignment,
    User,
    Organization,
    Team,
    TeamMembership,
    Match,
    Stage,
    Tournament,
    TournamentRoster,
    TournamentStanding,
)

revision: str = "53bbc0801b4f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _MODEL_TYPES:
        raise RuntimeError("No SQLAlchemy models were loaded")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
