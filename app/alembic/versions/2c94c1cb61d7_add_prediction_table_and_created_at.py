"""add prediction table and created_at columns

Revision ID: 2c94c1cb61d7
Revises: 10d56f2d7925
Create Date: 2026-06-25 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2c94c1cb61d7"
down_revision: Union[str, Sequence[str], None] = "10d56f2d7925"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "core_poi_geometry",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "daily_spend_brand_state_rice",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "daily_weather_rice",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "spend_patterns_rice",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "urban_heat_index",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_table(
        "prediction_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pred_longitude", sa.Float(), nullable=False),
        sa.Column("pred_latitude", sa.Float(), nullable=False),
        sa.Column("pred_model_name", sa.Text(), nullable=False),
        sa.Column("pred_metrics", sa.JSON(), nullable=False),
        sa.Column("pred_color", sa.Text(), nullable=False),
        sa.Column("pred_polygon_grid", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("prediction_table")
    op.drop_column("urban_heat_index", "created_at")
    op.drop_column("spend_patterns_rice", "created_at")
    op.drop_column("daily_weather_rice", "created_at")
    op.drop_column("daily_spend_brand_state_rice", "created_at")
    op.drop_column("core_poi_geometry", "created_at")
