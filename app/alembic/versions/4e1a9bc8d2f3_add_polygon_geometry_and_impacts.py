"""add polygon geometry and impacts

Revision ID: 4e1a9bc8d2f3
Revises: 9b1d6f4c2a8e
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4e1a9bc8d2f3"
down_revision: Union[str, Sequence[str], None] = "9b1d6f4c2a8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "polygon_geometry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "polygon_impact_grids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("polygon_geometry_id", sa.Integer(), nullable=False),
        sa.Column("grid_cell_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["grid_cell_id"], ["grid_cell_geometry.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["polygon_geometry_id"], ["polygon_geometry.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("polygon_geometry_id", "grid_cell_id", name="uq_polygon_impact_grid"),
    )
    op.create_index(
        op.f("ix_polygon_impact_grids_grid_cell_id"),
        "polygon_impact_grids",
        ["grid_cell_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_polygon_impact_grids_polygon_geometry_id"),
        "polygon_impact_grids",
        ["polygon_geometry_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_polygon_impact_grids_polygon_geometry_id"), table_name="polygon_impact_grids")
    op.drop_index(op.f("ix_polygon_impact_grids_grid_cell_id"), table_name="polygon_impact_grids")
    op.drop_table("polygon_impact_grids")
    op.drop_table("polygon_geometry")
