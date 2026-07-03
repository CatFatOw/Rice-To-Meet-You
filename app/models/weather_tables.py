from database import Base 
from sqlalchemy import Column, Integer, Float, TIMESTAMP, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from .grid_cell_tables import GridCellGeometry


class WeatherObservation(Base):
    """table serves to store data from the NWS weather api"""
    __tablename__ = "weather_observation"
    __table_args__ = (
        UniqueConstraint("grid_cell_id", "timestamp", "source", name="uq_weather_observation_cell_timestamp_source"),
    )

    id = Column(Integer, primary_key=True, nullable=False)
    # Specific grid cell where this weather observation is linked to :) (lat/lon detered via nws)
    grid_cell_id = Column(Integer, ForeignKey("grid_cell_geometry.id"), nullable=False, index=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    # The actual data from the NWS etc
    # Every metric should be U.S cenetered
    temperature = Column(Float)
    humidity = Column(Float)
    dewpoint = Column(Float)
    wind_direction = Column(Text)
    precipitation_prob = Column(Float)
    detailed_forecast = Column(Text)
    source = Column(Text, default="NWS")
    grid_cell = relationship("GridCellGeometry")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
