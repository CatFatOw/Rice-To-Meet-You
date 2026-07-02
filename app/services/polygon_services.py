"""Business logic for polygon impact calculations."""
from sqlalchemy.orm import Session
from schemas import polygon_schemas
from models import polygon_tables
from shapely.geometry import Point, Polygon
from repository.grid_geometry_repository import get_all_cells, get_all_city_grid_cells, get_all_state_grid_cells
from typing import List


def polygon_from_geojson(geometry: dict) -> Polygon:
    """Build a Shapely polygon from GeoJSON Polygon geometry."""
    if geometry.get("type") != "Polygon":
        raise ValueError("Only GeoJSON Polygon geometry is supported")

    coordinates = geometry.get("coordinates")
    if not coordinates or not coordinates[0]:
        raise ValueError("Polygon geometry must include coordinates")

    exterior_ring = coordinates[0]
    if len(exterior_ring) < 3:
        raise ValueError("Polygon must include at least three points")

    polygon = Polygon(exterior_ring)
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("Polygon geometry is invalid")

    return polygon


def find_impact_grids(
    polygon_id: int,
    polygon: polygon_schemas.PolygonGeometryCreate,
    db: Session,
    city: str = None,
    state: str = None,
) -> List[polygon_tables.PolygonImpactGrids]:
    """Function handles core logic of finding girds that the polygon has impacted.
    Essentially, users want to see if the grid centroid is inside the polygon area"""
    drawn_polygon = polygon_from_geojson(polygon.geometry)
    
    # If city and state are specified only find grid cells in that region
    if city and state:
        grid_cells = get_all_city_grid_cells(state, city, db)
    elif state:
        grid_cells = get_all_state_grid_cells(state, db)
    else:
        grid_cells = get_all_cells(db)
    
    impacted_grid_rows = []
    # iterate through all grid_cell candidates
    for grid in grid_cells:
        centroid = Point(grid.grid_centroid_lon, grid.grid_centroid_lat)
        # Covers includes points on the boundary, which users expect once a polygon shades a cell edge.
        if drawn_polygon.covers(centroid):
            # Save the information
            impacted_grid_rows.append(
                polygon_tables.PolygonImpactGrids(
                    polygon_geometry_id=polygon_id,
                    grid_cell_id=grid.id,
                )
            )

    return impacted_grid_rows
