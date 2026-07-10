"""add predicted metric columns

Revision ID: 5f0c3e9a7b21
Revises: e3cf8eeaf0c4
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f0c3e9a7b21"
down_revision: Union[str, Sequence[str], None] = "e3cf8eeaf0c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PREDICTED_COLUMNS = (
    "predicted_heat_index",
    "predicted_heat_risk",
    "predicted_crowd_density",
    "predicted_population",
    "predicted_visitor_count",
)


def column_exists(table_name: str, column_name: str) -> bool:
    """Return whether a column exists in the current migration connection."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Upgrade schema."""
    for column_name in PREDICTED_COLUMNS:
        if not column_exists("grid_cell_metrics", column_name):
            op.add_column("grid_cell_metrics", sa.Column(column_name, sa.Float(), nullable=True))
        if not column_exists("interpolated_points", column_name):
            op.add_column("interpolated_points", sa.Column(column_name, sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for column_name in reversed(PREDICTED_COLUMNS):
        if column_exists("interpolated_points", column_name):
            op.drop_column("interpolated_points", column_name)
        if column_exists("grid_cell_metrics", column_name):
            op.drop_column("grid_cell_metrics", column_name)
