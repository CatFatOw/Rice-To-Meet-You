"""add polygon display metadata

Revision ID: 8fd6f7b21c3a
Revises: d8832c36f5b3
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8fd6f7b21c3a"
down_revision: Union[str, Sequence[str], None] = "d8832c36f5b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("polygon_geometry", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("polygon_geometry", sa.Column("city_name", sa.Text(), nullable=True))
    op.add_column("polygon_geometry", sa.Column("state_name", sa.Text(), nullable=True))
    op.add_column(
        "polygon_geometry",
        sa.Column("color", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(op.f("ix_polygon_geometry_city_name"), "polygon_geometry", ["city_name"], unique=False)
    op.create_index(op.f("ix_polygon_geometry_state_name"), "polygon_geometry", ["state_name"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_polygon_geometry_state_name"), table_name="polygon_geometry")
    op.drop_index(op.f("ix_polygon_geometry_city_name"), table_name="polygon_geometry")
    op.drop_column("polygon_geometry", "color")
    op.drop_column("polygon_geometry", "state_name")
    op.drop_column("polygon_geometry", "city_name")
    op.drop_column("polygon_geometry", "name")
