"""adding visitor data table

Revision ID: 89565db550c8
Revises: f38cde446d8f
Create Date: 2026-08-17 15:24:48.005213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89565db550c8'
down_revision: Union[str, Sequence[str], None] = 'f38cde446d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the visitor dataset table."""
    op.create_table(
        "visitor",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("avg_daily_visits", sa.Float(), nullable=False),
        sa.Column("location_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("street_address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_visitor_city_local_date", "visitor", ["city", "local_date"])


def downgrade() -> None:
    """Remove the visitor dataset table."""
    op.drop_index("ix_visitor_city_local_date", table_name="visitor")
    op.drop_table("visitor")
