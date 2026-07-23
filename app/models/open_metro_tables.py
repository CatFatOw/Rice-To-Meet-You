from database import Base

from sqlalchemy import (
    Column,
    Float,
    Integer,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import text


class OpenMeteoForecast(Base):
    """
    Stores the complete response returned by the Open-Meteo Forecast API.

    The full API response is stored in JSONB because requested weather
    variables can differ between requests.
    """

    __tablename__ = "open_meteo_forecasts"

    id = Column(
        Integer,
        primary_key=True,
        nullable=False,
    )

    # Requested location
    latitude = Column(
        Float,
        nullable=False,
        index=True,
    )

    longitude = Column(
        Float,
        nullable=False,
        index=True,
    )

    # Location metadata returned by Open-Meteo
    elevation = Column(Float)
    timezone = Column(Text)
    timezone_abbreviation = Column(Text)
    utc_offset_seconds = Column(Integer)

    # API-generation information
    generation_time_ms = Column(Float)

    # Entire Open-Meteo response
    response_data = Column(
        JSONB,
        nullable=False,
    )

    # Optional request information
    requested_current = Column(JSONB)
    requested_hourly = Column(JSONB)
    requested_daily = Column(JSONB)
    forecast_days = Column(Integer)

    source = Column(
        Text,
        nullable=False,
        server_default=text("'open_meteo'"),
    )

    fetched_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        index=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )