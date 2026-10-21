"""Track tournament creator and constrain status and dates."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261021_1200"
down_revision: Union[str, Sequence[str], None] = "20261011_2000"
branch_labels = None
depends_on = None

STATUS_CHECK = "status IN ('UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED')"
DATES_CHECK = "end_date IS NULL OR end_date >= start_date"


def _state():
    # The base revision runs create_all from the current models, so a fresh
    # database may already have these objects.
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("tournaments")}
    checks = {c["name"] for c in inspector.get_check_constraints("tournaments")}
    fk_columns = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("tournaments")}
    return columns, checks, fk_columns


def upgrade() -> None:
    columns, checks, fk_columns = _state()
    if "created_by" not in columns:
        op.add_column("tournaments", sa.Column("created_by", sa.Integer(), nullable=True))
    if ("created_by",) not in fk_columns:
        op.create_foreign_key("fk_tournaments_created_by", "tournaments", "users",
                              ["created_by"], ["user_id"], ondelete="SET NULL")
    if "ck_tournaments_status" not in checks:
        op.create_check_constraint("ck_tournaments_status", "tournaments", STATUS_CHECK)
    if "ck_tournaments_dates" not in checks:
        op.create_check_constraint("ck_tournaments_dates", "tournaments", DATES_CHECK)


def downgrade() -> None:
    columns, checks, _ = _state()
    for name in ("ck_tournaments_dates", "ck_tournaments_status"):
        if name in checks:
            op.drop_constraint(name, "tournaments", type_="check")
    if "created_by" in columns:
        op.drop_column("tournaments", "created_by")
