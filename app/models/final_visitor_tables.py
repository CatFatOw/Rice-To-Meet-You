"""Table that stores data from: final_visitors_DF"""
from database import Base
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    Index,
    Integer,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import text


class VisitorData(Base):
    __tablename__ = "final_visitor_table"

    id = Column(Integer, primary_key=True, nullable=False)
    city = Column(Text, nullable=False)
    local_date = Column(Date, nullable=False)
    avg_daily_visits = Column(Float, nullable=False)
    location_name = Column(Text, nullable=False)
    heat_risk_score = Column(Float)
    brand = Column(Text, nullable=False)
    street_address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # --- core POI geometry -------------------------------------------------
    # Denormalized from the core POI geometry source. Every column here is
    # nullable: a visitor row is not guaranteed to resolve to a POI, which is
    # what `core_poi_geometry_id IS NOT NULL` filters on.
    core_poi_geometry_id = Column(Integer, nullable=True)
    core_poi_geometry_brands = Column(JSON, nullable=True)
    core_poi_geometry_category_tags = Column(JSON, nullable=True)
    core_poi_geometry_city = Column(Text, nullable=True)
    core_poi_geometry_closed_on = Column(Date, nullable=True)
    core_poi_geometry_domains = Column(JSON, nullable=True)
    core_poi_geometry_enclosed = Column(Boolean, nullable=True)
    core_poi_geometry_geometry_type = Column(Text, nullable=True)
    core_poi_geometry_includes_parking_lot = Column(Boolean, nullable=True)
    core_poi_geometry_iso_country_code = Column(Text, nullable=True)
    core_poi_geometry_is_synthetic = Column(Boolean, nullable=True)
    core_poi_geometry_latitude = Column(Float, nullable=True)
    core_poi_geometry_location_name = Column(Text, nullable=True)
    core_poi_geometry_longitude = Column(Float, nullable=True)
    core_poi_geometry_market = Column(Text, nullable=True)
    core_poi_geometry_naics_code = Column(Integer, nullable=True)
    core_poi_geometry_naics_code_2022 = Column(Integer, nullable=True)
    core_poi_geometry_opened_on = Column(Date, nullable=True)
    core_poi_geometry_open_hours = Column(JSON, nullable=True)
    core_poi_geometry_parent_placekey = Column(Text, nullable=True)
    core_poi_geometry_phone_number = Column(Text, nullable=True)
    core_poi_geometry_placekey = Column(Text, nullable=True)
    core_poi_geometry_polygon_class = Column(Text, nullable=True)
    core_poi_geometry_polygon_wkt = Column(Text, nullable=True)
    core_poi_geometry_postal_code = Column(Text, nullable=True)
    core_poi_geometry_region = Column(Text, nullable=True)
    core_poi_geometry_safegraph_place_id = Column(Text, nullable=True)
    core_poi_geometry_store_id = Column(Text, nullable=True)
    core_poi_geometry_street_address = Column(Text, nullable=True)
    core_poi_geometry_sub_category = Column(Text, nullable=True)
    core_poi_geometry_sub_category_2022 = Column(Text, nullable=True)
    core_poi_geometry_top_category = Column(Text, nullable=True)
    core_poi_geometry_top_category_2022 = Column(Text, nullable=True)
    core_poi_geometry_tracking_closed_since = Column(Date, nullable=True)
    core_poi_geometry_website = Column(Text, nullable=True)
    core_poi_geometry_wkt_area_sq_meters = Column(Float, nullable=True)
    core_poi_geometry_created_at = Column(TIMESTAMP(timezone=True), nullable=True)
    core_poi_geometry_user_id = Column(Integer, nullable=True)
    core_poi_geometry_provided = Column(Boolean, nullable=True)
    core_poi_geometry_market_code = Column(Text, nullable=True)
    # USER-DEFINED in information_schema -- PostGIS. Adjust geometry_type/srid
    # to match the actual typmod on the column.
    core_poi_geometry_polygon_geom = Column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
        nullable=True,
    )
    # data type was truncated in the schema dump -- assumed Text, verify.
    core_poi_geometry_color = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_final_visitor_table_city_local_date", "city", "local_date"),
        # Supports the core_poi_geometry_id IS NOT NULL reads. Partial, so it
        # only indexes rows that actually resolved to a POI.
        Index(
            "ix_final_visitor_table_city_date_poi",
            "city",
            "local_date",
            postgresql_where=text("core_poi_geometry_id IS NOT NULL"),
        ),
    )