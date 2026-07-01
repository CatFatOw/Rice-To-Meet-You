"""Routes for creating grid cells and returning them in GeoJSON format."""
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import grid_cell_tables, weather_tables
from schemas import grid_schemas
from services.national_weather import get_state_bbox, split_bbox_into_cell
from shapely.geometry import box, shape

router = APIRouter(prefix="/grid", tags=["grid"])


def normalize_state(state: str):
    """Keep state names stored consistently."""
    return state.strip().title()


def grid_cells_to_geojson(cells):
    """Convert grid cell rows into a GeoJSON FeatureCollection."""
    features = []

    for cell in cells:
        features.append({
            "type": "Feature",
            "properties": {
                "id": cell.id,
                "cell_id": cell.cell_id,
                "row": cell.row,
                "col": cell.col,
                "centroid_lat": cell.grid_centroid_lat,
                "centroid_lon": cell.grid_centroid_lon,
                "state": cell.state,
            },
            "geometry": cell.geometry,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# No need to bind engine as alembic handles that automatically
def get_city_polygon(city: str, state: str):
    """Get a city boundary from OpenStreetMap as a GeoJSON FeatureCollection."""
    params = {
        "q": f"{city}, {state}",
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
    }
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers={"User-Agent": "rice_heat_safe"},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CITY NOT FOUND",
        )

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": data[0].get("display_name"),
                    "place_id": data[0].get("place_id"),
                },
                "geometry": data[0]["geojson"],
            }
        ],
    }


def get_city_bbox(city: str, state: str):
    """Get a clean bounding box around a city boundary."""
    city_geojson = get_city_polygon(city, state)
    city_geometry = shape(city_geojson["features"][0]["geometry"])
    min_lon, min_lat, max_lon, max_lat = city_geometry.bounds
    bbox_geometry = box(min_lon, min_lat, max_lon, max_lat)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": city_geojson["features"][0]["properties"],
                "geometry": bbox_geometry.__geo_interface__,
            }
        ],
    }


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


@router.post("/generate_nxn_grid_city")
async def generate_nxn_grid_city(
    city: str,
    state: str,
    n: int = 40,
    db: Session = Depends(get_db),
):
    """Generate an n x n grid for a city boundary."""
    normalized_city = city.strip().title()
    normalized_state = normalize_state(state)
    city_bbox_geojson = get_city_bbox(normalized_city, normalized_state)
    nxn_grid = split_bbox_into_cell(city_bbox_geojson, n=n)
    grid_result = save_nxn_grid_cells(
        nxn_grid=nxn_grid,
        state=normalized_state,
        cell_id_prefix=f"{normalized_city.lower()}_{normalized_state.lower()}",
        db=db,
    )

    return {
        "message": "Grid generated successfully",
        "state": normalized_state,
        "city": normalized_city,
        "n": n,
        "cells_deleted": grid_result["cells_deleted"],
        "cells_created": grid_result["cells_created"],
    }


def get_state_grid_cells(state: str, db: Session):
    """Return all grid cells for a state."""
    normalized_state = normalize_state(state)
    data = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.state == normalized_state)
        .all()
    )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return data


def get_city_grid_cells(city: str, state: str, db: Session):
    """Return grid cells generated for a city."""
    normalized_city = city.strip().title()
    normalized_state = normalize_state(state)
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

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO CITY GRID CELLS FOUND"
        )

    return data


# route for getting state mask -> splitting it into nxn grids -> saving it into db :_)
@router.post("/generate_nxn_grid")
async def generate_nxn_grid(state_name: str, n: int = 40, db: Session = Depends(get_db)):
    """Function gets a state mask splits it into nxn grid and saves it into the database"""
    normalized_state = normalize_state(state_name)
    state_bbox_geojson = get_state_bbox(state_name)
    nxn_grid = split_bbox_into_cell(state_bbox_geojson, n=n)
    grid_result = save_nxn_grid_cells(
        nxn_grid=nxn_grid,
        state=normalized_state,
        cell_id_prefix=normalized_state.lower(),
        db=db,
    )

    return {
        "message": "Grid generated successfully",
        "state": normalized_state,
        "n": n,
        "cells_deleted": grid_result["cells_deleted"],
        "cells_created": grid_result["cells_created"],
    }


# Route gets all cells (not in geojson format) 
@router.get("/all", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grids(db: Session = Depends(get_db)):
    """function gets all grid cell coordinates so we can plot it onto """
    grids = db.query(grid_cell_tables.GridCellGeometry).all()
    if not grids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grids


@router.get("/cell/{cell_id}", response_model=grid_schemas.GridCellResponse)
async def get_grid_cell_by_cell_id(cell_id: str, db: Session = Depends(get_db)):
    data = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.cell_id == cell_id)
        .first()
    )

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GRID CELL NOT FOUND"
        )

    return data


# Return grid beloing to all state (backend)
@router.get("/state/{state}", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grid_state(state: str, db: Session = Depends(get_db)):
    """Function gets all the grids associated with a state :)"""
    return get_state_grid_cells(state, db)


@router.get("/city", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grid_city(city: str, state: str, db: Session = Depends(get_db)):
    """Return all grid cells generated for a city."""
    return get_city_grid_cells(city, state, db)


@router.get("/state/{state}/geojson")
async def get_all_grid_state_geojson(state: str, db: Session = Depends(get_db)):
    """Function gets all state grids as GeoJSON."""
    data = get_state_grid_cells(state, db)
    return grid_cells_to_geojson(data)

# Turns the backend end into usable geojson format for frontend
@router.get("/map/geojson")
async def get_grid_map(db: Session = Depends(get_db)):
    cells = db.query(grid_cell_tables.GridCellGeometry).all()

    if not cells:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )

    return grid_cells_to_geojson(cells)


# Route gets grid cells by their ID 
@router.get("/id/{id}", response_model=grid_schemas.GridCellResponse)
async def get_grid_id(id: int, db: Session = Depends(get_db)):
    """Function gets a specific nxn grid by its ID"""
    grid = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.id == id)
        .first()
    )
    if not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grid
