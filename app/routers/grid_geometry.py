"""File handles most of the routes of creating grid and getting the grid cells in geojson format"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session 
from database import get_db
from models import grid_cell_tables
from schemas import grid_schemas
from services.national_weather import get_state_bbox, split_bbox_into_cell
from shapely.geometry import Point, shape 
router = APIRouter(prefix="/grid", tags=["grid"])


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
def get_lat_lon(city, state):
    """Function gets the lat/lon of a city"""
    from geopy.geocoders import Nominatim

    city = city.capitalize()
    state = state.capitalize()
    geolocator = Nominatim(user_agent="rice_heat_safe")
    location = geolocator.geocode(f"{city}, {state}")
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LOCATION NOT FOUND",
        )
    return location.latitude, location.longitude


def get_state_grid_cells(state: str, db: Session):
    """Return all grid cells for a state."""
    data = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.state == state.title())
        .all()
    )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return data


def get_city_neighbor_cells(city: str, state: str, radius: int, db: Session):
    """Return the center city grid cell and nearby grid cells."""
    lat, lon = get_lat_lon(city, state)
    point = Point(lon, lat)
    data = get_state_grid_cells(state, db)

    center_cell = None
    for cell in data:
        polygon = shape(cell.geometry)
        if polygon.contains(point):
            center_cell = cell
            break
    if not center_cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CITY NOT FOUND INSIDE ANY GRID CELL"
        )

    min_row = center_cell.row - radius
    max_row = center_cell.row + radius
    min_col = center_cell.col - radius
    max_col = center_cell.col + radius

    neighbors = (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.state == state.title())
        .filter(grid_cell_tables.GridCellGeometry.row >= min_row)
        .filter(grid_cell_tables.GridCellGeometry.row <= max_row)
        .filter(grid_cell_tables.GridCellGeometry.col >= min_col)
        .filter(grid_cell_tables.GridCellGeometry.col <= max_col)
        .all()
    )

    return {
        "city": city,
        "state": state.title(),
        "lat": lat,
        "lon": lon,
        "center_cell": center_cell,
        "neighbors": neighbors,
        "neighbor_count": len(neighbors),
        "radius": radius,
    }


# route for getting state mask -> splitting it into nxn grids -> saving it into db :_)
@router.post("/generate_nxn_grid")
async def generate_nxn_grid(state_name:str, n:int=40, db:Session=Depends(get_db)):
    """Function gets a state mask splits it into nxn grid and saves it into the database"""
    
    state_bbox_geojson = get_state_bbox(state_name)
    nxn_grid = split_bbox_into_cell(state_bbox_geojson, n=n)
    cell_created = 0
    normalized_state = state_name.title()
    existing_cell_ids = {
        cell_id
        for (cell_id,) in (
            db.query(grid_cell_tables.GridCellGeometry.cell_id)
            .filter(grid_cell_tables.GridCellGeometry.state == normalized_state)
            .all()
        )
    }
    existing_row_cols = {
        (row, col)
        for row, col in (
            db.query(grid_cell_tables.GridCellGeometry.row, grid_cell_tables.GridCellGeometry.col)
            .filter(grid_cell_tables.GridCellGeometry.state == normalized_state)
            .all()
        )
    }
    new_cells = []

    for _, row in nxn_grid.iterrows():
        cell_id = f"{normalized_state.lower()}_{row['cell_id']}"
        row_col = (int(row["row"]), int(row["col"]))
        # This grid already exists we skip
        if cell_id in existing_cell_ids or row_col in existing_row_cols:
            continue 
        # New cell!
        new_cell = grid_cell_tables.GridCellGeometry(
            cell_id=cell_id,
            row=row["row"],
            col=row["col"],
            grid_centroid_lat=row["centroid_lat"],
            grid_centroid_lon=row["centroid_lon"],
            geometry=row["geometry"].__geo_interface__,
            state=normalized_state,
        )
        new_cells.append(new_cell)
        cell_created += 1

    if new_cells:
        db.add_all(new_cells)
        db.commit()
        
    return {
    "message": "Grid generated successfully",
    "state": state_name,
    "n": n,
    "cells_created": cell_created,
}
        

# Route gets all cells (not in geojson format) 
@router.get("/all", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grids(db:Session = Depends(get_db)):
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
async def get_all_grid_state(state:str, db:Session = Depends(get_db)):
    """Function gets all the grids associated with a state :)"""
    return get_state_grid_cells(state, db)


@router.get("/state/{state}/geojson")
async def get_all_grid_state_geojson(state:str, db:Session = Depends(get_db)):
    """Function gets all state grids as GeoJSON."""
    data = get_state_grid_cells(state, db)
    return grid_cells_to_geojson(data)

# Returning all grids beloing to a specific city (backend) + some neighbors within a certain radius
@router.get("/city/neighbors", response_model=grid_schemas.CityGridNeighborsResponse)
async def get_city_cells(city:str, state:str, radius:int=1, db:Session=Depends(get_db)):
    """fucntion gets all cells related with the city + some neighbors for padding
    This is a separaete function due to routes in grid_metrics also relying on the functionaility of this function
    """
    city_data = get_city_neighbor_cells(city, state, radius, db)
    center_cell = city_data["center_cell"]
    return {
        "city": city_data["city"],
        "state": city_data["state"],
        "lat": city_data["lat"],
        "lon": city_data["lon"],
        "center_cell_id": center_cell.id,
        "center_cell_cell_id": center_cell.cell_id,
        "neighbors": city_data["neighbors"],
        "neighbor_count": city_data["neighbor_count"],
        "radius": city_data["radius"],
    }


# Function for getting city and its neighbors
def get_city_neighbors_grid_geojson(city:str, state:str, radius:int=1, db:Session=Depends(get_db)):
    city_data = get_city_neighbor_cells(city, state, radius, db)
    center_cell = city_data["center_cell"]
    geojson = grid_cells_to_geojson(city_data["neighbors"])
    geojson["properties"] = {
        "city": city_data["city"],
        "state": city_data["state"],
        "lat": city_data["lat"],
        "lon": city_data["lon"],
        "center_cell_id": center_cell.id,
        "center_cell_cell_id": center_cell.cell_id,
        "neighbor_count": city_data["neighbor_count"],
        "radius": city_data["radius"],
    }
    return geojson


@router.get("/city/neighbors/geojson")
async def get_city_cells_geojson(city:str, state:str, radius:int=1, db:Session=Depends(get_db)):
    """Function gets city neighbor cells as GeoJSON."""
    return get_city_neighbors_grid_geojson(city, state, radius, db)
    

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
async def get_grid_id(id:int, db:Session = Depends(get_db)):
    """Function gets a specific nxn grid by its ID"""
    grid = db.query(grid_cell_tables.GridCellGeometry).filter(grid_cell_tables.GridCellGeometry.id == id).first()
    if not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grid 
