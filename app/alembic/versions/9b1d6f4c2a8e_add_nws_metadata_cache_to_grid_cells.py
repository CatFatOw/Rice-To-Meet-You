"""add nws metadata cache to grid cells

Revision ID: 9b1d6f4c2a8e
Revises: 017aa869b17f
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b1d6f4c2a8e"
down_revision: Union[str, Sequence[str], None] = "017aa869b17f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("grid_cell_geometry", sa.Column("nws_grid_id", sa.Text(), nullable=True))
    op.add_column("grid_cell_geometry", sa.Column("nws_grid_x", sa.Integer(), nullable=True))
    op.add_column("grid_cell_geometry", sa.Column("nws_grid_y", sa.Integer(), nullable=True))
    op.add_column("grid_cell_geometry", sa.Column("forecast_hourly", sa.Text(), nullable=True))
    op.add_column(
        "grid_cell_geometry",
        sa.Column("nws_metadata_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_grid_cell_geometry_nws_grid",
        "grid_cell_geometry",
        ["nws_grid_id", "nws_grid_x", "nws_grid_y"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_grid_cell_geometry_nws_grid", table_name="grid_cell_geometry")
    op.drop_column("grid_cell_geometry", "nws_metadata_checked_at")
    op.drop_column("grid_cell_geometry", "forecast_hourly")
    op.drop_column("grid_cell_geometry", "nws_grid_y")
    op.drop_column("grid_cell_geometry", "nws_grid_x")
    op.drop_column("grid_cell_geometry", "nws_grid_id")
