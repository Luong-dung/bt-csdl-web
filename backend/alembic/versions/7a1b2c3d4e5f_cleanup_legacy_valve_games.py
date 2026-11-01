"""Cleanup legacy valve games and publisher

Revision ID: 7a1b2c3d4e5f
Revises: 5f2d5fc3a731
Create Date: 2026-11-01 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '5f2d5fc3a731'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Clean up legacy CS2 and Dota 2 games if unreferenced
    bind.execute(sa.text("""
        DELETE FROM games
        WHERE slug IN ('cs2', 'dota-2')
          AND game_id NOT IN (SELECT DISTINCT game_id FROM tournaments WHERE game_id IS NOT NULL)
          AND game_id NOT IN (SELECT DISTINCT game_id FROM teams WHERE game_id IS NOT NULL)
    """))
    # Clean up legacy Valve publisher if unreferenced
    bind.execute(sa.text("""
        DELETE FROM publishers
        WHERE name = 'Valve'
          AND publisher_id NOT IN (SELECT DISTINCT publisher_id FROM games WHERE publisher_id IS NOT NULL)
    """))


def downgrade() -> None:
    pass
