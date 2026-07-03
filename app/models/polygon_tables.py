from database import Base 
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text


class PolygonGeometry(Base):
    """table handles the actual polygon geometry value"""
    __tablename__ = "polygon_geometry"

    id = Column(Integer, primary_key=True, nullable=False)
    # Optional frontend display metadata for saved POI/region polygons.
    name = Column(Text, nullable=True)
    city_name = Column(Text, nullable=True, index=True)
    state_name = Column(Text, nullable=True, index=True)
    color = Column(JSONB, nullable=True)
    # Stores a closed GeoJSON Polygon from the labeling tool.
    geometry = Column(JSONB, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    impacted_grids = relationship(
        "PolygonImpactGrids",
        back_populates="polygon",
        cascade="all, delete-orphan",
    )


class PolygonImpactGrids(Base):
    """Table contains information on which grids are impacted by the simulation polygon"""
    __tablename__ = "polygon_impact_grids"
    __table_args__ = (
        UniqueConstraint("polygon_geometry_id", "grid_cell_id", name="uq_polygon_impact_grid"),
    )

    id = Column(Integer, primary_key=True, nullable=False)

    polygon_geometry_id = Column(
        Integer,
        ForeignKey("polygon_geometry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    grid_cell_id = Column(
        Integer,
        ForeignKey("grid_cell_geometry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = Column(TIMESTAMP(timezone=True), nullable=True, server_default=text("now()"))

    polygon = relationship("PolygonGeometry", back_populates="impacted_grids")
    grid_cell = relationship("GridCellGeometry")
