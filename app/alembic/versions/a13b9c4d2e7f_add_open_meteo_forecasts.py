"""add Open-Meteo forecast cache

Revision ID: a13b9c4d2e7f
Revises: f38cde446d8f
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a13b9c4d2e7f"
down_revision: Union[str, Sequence[str], None] = "f38cde446d8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the raw Open-Meteo forecast cache table."""
    op.create_table(
        "open_meteo_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("elevation", sa.Float(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("timezone_abbreviation", sa.Text(), nullable=True),
        sa.Column("utc_offset_seconds", sa.Integer(), nullable=True),
        sa.Column("generation_time_ms", sa.Float(), nullable=True),
        sa.Column("response_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_current", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_hourly", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_daily", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("forecast_days", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'open_meteo'"), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_open_meteo_forecasts_latitude", "open_meteo_forecasts", ["latitude"])
    op.create_index("ix_open_meteo_forecasts_longitude", "open_meteo_forecasts", ["longitude"])
    op.create_index("ix_open_meteo_forecasts_fetched_at", "open_meteo_forecasts", ["fetched_at"])


def downgrade() -> None:
    """Drop the raw Open-Meteo forecast cache table."""
    op.drop_index("ix_open_meteo_forecasts_fetched_at", table_name="open_meteo_forecasts")
    op.drop_index("ix_open_meteo_forecasts_longitude", table_name="open_meteo_forecasts")
    op.drop_index("ix_open_meteo_forecasts_latitude", table_name="open_meteo_forecasts")
    op.drop_table("open_meteo_forecasts")
