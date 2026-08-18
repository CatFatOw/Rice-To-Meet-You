"""added new polygon tables

Revision ID: d8832c36f5b3
Revises: 4e1a9bc8d2f3
Create Date: 2026-07-02 11:45:15.723397

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d8832c36f5b3"
down_revision: Union[str, Sequence[str], None] = "4e1a9bc8d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_grid_cell_geometry_nws_grid"), table_name="grid_cell_geometry")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index(
        op.f("ix_grid_cell_geometry_nws_grid"),
        "grid_cell_geometry",
        ["nws_grid_id", "nws_grid_x", "nws_grid_y"],
        unique=False,
    )
