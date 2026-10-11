"""Use timezone-aware timestamps for teams and tournaments."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261011_2000"
down_revision: Union[str, Sequence[str], None] = "53bbc0801b4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "teams",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "tournaments",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "tournaments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "teams",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
