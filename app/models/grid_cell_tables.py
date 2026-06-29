from database import Base 
from sqlalchemy import Column, Integer, Float, TIMESTAMP, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text


class GridCellGeometry(Base):
    """Table handles storing the data of the core geojson polygon structures output from 
    geopandas.GeoDataFrame

    This stores only the single cell in the database 
    """
    __tablename__ = "grid_cell_geometry"
    __table_args__ = (
        UniqueConstraint("cell_id", name="uq_grid_cell_geometry_cell_id"),
        UniqueConstraint("row", "col", "state", name="uq_grid_cell_geometry_row_col_state"),
    )

    id = Column(Integer, primary_key=True, nullable=False)
    # nxn Grid identification
    cell_id = Column(Text, nullable=False, index=True)
    row = Column(Integer, nullable=False, index=True)
    col = Column(Integer, nullable=False, index=True)
    
    # nxn grid geometry information
    grid_centroid_lat = Column(Float, nullable=False)
    grid_centroid_lon = Column(Float, nullable=False)
    geometry = Column(JSONB, nullable=False)

    state = Column(Text, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class GridCellMetrics(Base):
    """Table stores metrics/information to each nxn information."""
    __tablename__ = "grid_cell_metrics"

    id = Column(Integer, primary_key=True, nullable=False)

    grid_cell_id = Column(
        Integer,
        ForeignKey("grid_cell_geometry.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    heat_index = Column(Float)
    heat_risk = Column(Float)
    crowd_density = Column(Float)
    population = Column(Float)
    cooling_centers = Column(Integer)
    cooling_centers_impact_radius = Column(Float)
    infrastructure_strain = Column(Float)

    # Colors for frontend map visualization based on metric costs etc
    heat_index_color = Column(Text, default="#00BFFF")
    heat_risk_color = Column(Text, default="#00BFFF")
    crowd_density_color = Column(Text, default="#00BFFF")
    population_color = Column(Text, default="#00BFFF")
    cooling_centers_color = Column(Text, default="#00BFFF")
    infrastructure_strain_color = Column(Text, default="#00BFFF")

    # Optional overall color
    overall_risk_color = Column(Text, default="#00BFFF")

    grid_cell = relationship("GridCellGeometry")

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
