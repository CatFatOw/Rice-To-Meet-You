"""rename visitor table

Revision ID: 07423c6d56ad
Revises: 89565db550c8
Create Date: 2026-08-17 15:28:31.971649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07423c6d56ad'
down_revision: Union[str, Sequence[str], None] = '89565db550c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename the visitor dataset table and its index."""
    op.rename_table("visitor", "final_visitor_table")
    op.execute(
        "ALTER INDEX ix_visitor_city_local_date "
        "RENAME TO ix_final_visitor_table_city_local_date"
    )


def downgrade() -> None:
    """Restore the prior visitor table and index names."""
    op.execute(
        "ALTER INDEX ix_final_visitor_table_city_local_date "
        "RENAME TO ix_visitor_city_local_date"
    )
    op.rename_table("final_visitor_table", "visitor")
