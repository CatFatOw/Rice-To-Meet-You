"""File used to handle core processing logic for grid_geometry route"""
import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from shapely.geometry import shape, box
from repository.grid_geometry_repository import (
    get_all_cells,
    get_all_city_grid_cells,
    get_all_state_grid_cells,
    get_grid_by_cell_id,
    get_grid_by_db_id,
    grid_cells_to_centroids,
    grid_centroids_to_geojson,
    save_nxn_grid_cells,
)
from services.nws_weather_service import get_state_bbox, split_bbox_into_cell

def normalize_state(state: str):
    """Keep state names stored consistently."""
    return state.strip().title()

def normalize_city(city:str):
    """Keep city names stored consistanently"""
    return city.strip().title()

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


def get_city_polygon(city: str, state: str):
    """Get a city boundary from OpenStreetMap as a GeoJSON FeatureCollection.
    
    This function gets the actual shape of the city"""
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
    """Get a clean bounding box around a city boundary.This function creates a box"""
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


def generate_city_grid(city: str, state: str, n: int, db: Session):
    """Build and persist an n-by-n grid for a city bounding box."""
    normalized_city = city.strip().title()
    normalized_state = normalize_state(state)
    grid_result = save_nxn_grid_cells(
        nxn_grid=split_bbox_into_cell(get_city_bbox(normalized_city, normalized_state), n=n),
        state=normalized_state,
        cell_id_prefix=f"{normalized_city.lower()}_{normalized_state.lower()}",
        db=db,
    )
    return {"message": "Grid generated successfully", "state": normalized_state, "city": normalized_city, "n": n, **grid_result}


def generate_state_grid(state: str, n: int, db: Session):
    """Build and persist an n-by-n grid for a state bounding box."""
    normalized_state = normalize_state(state)
    grid_result = save_nxn_grid_cells(
        nxn_grid=split_bbox_into_cell(get_state_bbox(normalized_state), n=n),
        state=normalized_state,
        cell_id_prefix=normalized_state.lower(),
        db=db,
    )
    return {"message": "Grid generated successfully", "state": normalized_state, "n": n, **grid_result}


def _require_cells(cells, detail: str):
    if not cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return cells


def get_all_grid_cells(db: Session):
    return _require_cells(get_all_cells(db), "NO GRID CELLS FOUND")


def get_state_grid_cells(state: str, db: Session):
    return _require_cells(get_all_state_grid_cells(state, db), "NO GRID CELLS FOUND")


def get_city_grid_cells(city: str, state: str, db: Session):
    return _require_cells(get_all_city_grid_cells(state, city, db), "NO CITY GRID CELLS FOUND")


def get_grid_cell_by_cell_id(cell_id: str, db: Session):
    cell = get_grid_by_cell_id(cell_id, db)
    if not cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRID CELL NOT FOUND")
    return cell


def get_grid_cell_by_db_id(grid_id: int, db: Session):
    cell = get_grid_by_db_id(grid_id, db)
    if not cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NO GRID CELLS FOUND")
    return cell


def all_grid_centroids(db: Session):
    return grid_cells_to_centroids(get_all_grid_cells(db))


def all_grid_centroids_geojson(db: Session):
    return grid_centroids_to_geojson(get_all_grid_cells(db))


def grid_cells_centroids_geojson(cells):
    """Serialize an already-filtered set of grid-cell centroids as GeoJSON."""
    return grid_centroids_to_geojson(cells)
