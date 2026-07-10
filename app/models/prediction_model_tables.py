from database import Base 
from sqlalchemy import Column, Integer, Float, TIMESTAMP, Boolean, Text, ForeignKey
from sqlalchemy.sql.expression import text
from sqlalchemy.orm import relationship


class HeatDataML(Base):
    """Table for storing and serving the necessary heat datapoints for model training"""
    __tablename__ = "heat_data_ml"
    id = Column(Integer, primary_key=True, nullable=False)
    date = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    avg_temp_c = Column(Float, nullable=False)
    relative_humidity = Column(Float, nullable=False)
    wind_speed_knots = Column(Float, nullable=False)
    urban_heat_idx = Column(Float, nullable=False)
    source = Column(Text, nullable=False, server_default="interpolated")
    distance_nearest_station_km = Column(Float, nullable=True, server_default=text("0.0"))
    passed_threshold = Column(Boolean, nullable=True, server_default=text("true"))

class VisitorDataML(Base):
    """Stores visitor and POI information for ML training and inference."""

    __tablename__ = "visitor_data_ml"

    # Primary key
    id = Column(Integer, primary_key=True, nullable=False)

    # Date of the observation
    date = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )

    # Market (city/state)
    market = Column(Text, nullable=False)

    # Original market string from the source
    source_market = Column(Text, nullable=True)

    # Unique Foursquare POI ID
    fsq_place_id = Column(Text, nullable=True)

    # POI name
    name = Column(Text, nullable=True)

    # Coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Foursquare category
    category = Column(Text, nullable=True)

    # Actual visitor count (if available)
    visitor_count = Column(Integer, nullable=True)

    # Where the visitor count came from
    visitor_count_source = Column(Text, nullable=True)

    # Aggregate visitor count for the brand in the market
    market_brand_visitor_count_total = Column(Integer, nullable=True)

    # Number of candidate POIs matched during lookup
    candidate_foursquare_poi_count = Column(Integer, nullable=True)

    # Matching quality/status
    match_status = Column(Text, nullable=True)

    # Higher-level visitor category
    visitor_categories = Column(Text, nullable=True)

    # Distance from nearest heat map/grid point (km)
    nearest_heat_distance_km = Column(Float, nullable=True)

    # Distance from query center (meters)
    query_center_distance_m = Column(Float, nullable=True)
    # Google maps also provides the API for how congested it is 

    google_maps_congestion = Column(Float, nullable=True)
