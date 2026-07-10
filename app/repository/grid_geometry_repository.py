"""File contains core querying logic for the grid-geometry routes"""
from sqlalchemy.orm import Session
from models import grid_cell_tables, weather_tables
from services.grid_geometry_services import normalize_state, normalize_city


def get_all_cells(db:Session):
     """function gets every possible grid cell in the db"""
     grids = db.query(grid_cell_tables.GridCellGeometry).all()
     return grids


def grid_cell_to_centroid(cell):
    """Project a grid cell row into a lightweight centroid payload."""
    return {
        "id": cell.id,
        "cell_id": cell.cell_id,
        "row": cell.row,
        "col": cell.col,
        "latitude": cell.grid_centroid_lat,
        "longitude": cell.grid_centroid_lon,
        "state": cell.state,
    }


def grid_cells_to_centroids(cells):
    """Project grid cells into lightweight centroid payloads."""
    return [grid_cell_to_centroid(cell) for cell in cells]


def grid_centroids_to_geojson(cells):
    """Convert grid cell centroids into point GeoJSON."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": cell.id,
                    "cell_id": cell.cell_id,
                    "row": cell.row,
                    "col": cell.col,
                    "state": cell.state,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [cell.grid_centroid_lon, cell.grid_centroid_lat],
                },
            }
            for cell in cells
        ],
    }

def get_all_state_grid_cells(state:str ,db:Session):
    """function handles querying logic to get every single cell belonging to said state"""
    normalized_state = normalize_state(state)
    data = db.query(grid_cell_tables.GridCellGeometry).filter(grid_cell_tables.GridCellGeometry.state == normalized_state).all()
    return data 

def get_all_city_grid_cells(state:str, city:str, db:Session):
    """function handles querying logc to get every single cell belonging to a city"""
    normalized_state = normalize_state(state)
    normalized_city = normalize_city(city)
    cell_id_prefix = f"{normalized_city.lower()}_{normalized_state.lower()}_"
    data = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.state == normalized_state)
        .filter(grid_cell_tables.GridCellGeometry.cell_id.like(f"{cell_id_prefix}%"))
        .order_by(
            grid_cell_tables.GridCellGeometry.row,
            grid_cell_tables.GridCellGeometry.col,
        )
        .all()
    )
    return data


def get_grid_by_cell_id(cell_id: str, db: Session):
    """Get a specific grid cell by readable cell_id."""
    return (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.cell_id == cell_id)
        .first()
    )


def get_grid_by_db_id(id: int, db: Session):
    """Get a specific grid cell by database primary key."""
    return (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.id == id)
        .first()
    )

def delete_grid_cells_for_state(state: str, db: Session):
    """Delete existing grid rows and dependent rows before regenerating."""
    cell_ids = [
        cell_id
        for (cell_id,) in (
            db.query(grid_cell_tables.GridCellGeometry.id)
            .filter(grid_cell_tables.GridCellGeometry.state == state)
            .all()
        )
    ]

    if not cell_ids:
        return 0

    db.query(weather_tables.WeatherObservation).filter(
        weather_tables.WeatherObservation.grid_cell_id.in_(cell_ids)
    ).delete(synchronize_session=False)
    db.query(grid_cell_tables.GridCellMetrics).filter(
        grid_cell_tables.GridCellMetrics.grid_cell_id.in_(cell_ids)
    ).delete(synchronize_session=False)
    deleted_count = db.query(grid_cell_tables.GridCellGeometry).filter(
        grid_cell_tables.GridCellGeometry.id.in_(cell_ids)
    ).delete(synchronize_session=False)
    db.flush()

    return deleted_count


def save_nxn_grid_cells(nxn_grid, state: str, cell_id_prefix: str, db: Session):
    """Replace a state's grid cells with newly generated cells."""
    deleted_count = delete_grid_cells_for_state(state, db)
    new_cells = []

    for _, row in nxn_grid.iterrows():
        cell_id = f"{cell_id_prefix}_{row['cell_id']}"
        new_cell = grid_cell_tables.GridCellGeometry(
            cell_id=cell_id,
            row=row["row"],
            col=row["col"],
            grid_centroid_lat=row["centroid_lat"],
            grid_centroid_lon=row["centroid_lon"],
            geometry=row["geometry"].__geo_interface__,
            state=state,
        )
        new_cells.append(new_cell)

    if new_cells:
        db.add_all(new_cells)

    db.commit()

    return {
        "cells_deleted": deleted_count,
        "cells_created": len(new_cells),
    }

