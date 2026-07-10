"""Routes for creating grid cells and returning them in GeoJSON format."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import grid_schemas
from services.nws_weather_service import get_state_bbox, split_bbox_into_cell
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
from services.grid_geometry_services import normalize_state, grid_cells_to_geojson, get_city_bbox


router = APIRouter(prefix="/grid", tags=["grid"])



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
    data = get_all_state_grid_cells(state, db)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return data


def get_city_grid_cells(city: str, state: str, db: Session):
    """Return grid cells generated for a city."""
    data = get_all_city_grid_cells(state, city, db)
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
    grids = get_all_cells(db)
    if not grids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grids


@router.get("/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_centroids(db: Session = Depends(get_db)):
    """Return every grid cell centroid as lightweight click targets."""
    cells = get_all_cells(db)
    if not cells:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grid_cells_to_centroids(cells)


@router.get("/centroids/geojson")
async def get_all_grid_centroids_geojson(db: Session = Depends(get_db)):
    """Return every grid cell centroid as point GeoJSON."""
    cells = get_all_cells(db)
    if not cells:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grid_centroids_to_geojson(cells)


@router.get("/cell/{cell_id}", response_model=grid_schemas.GridCellResponse)
async def get_grid_cell_by_cell_id(cell_id: str, db: Session = Depends(get_db)):
    """Function gets cells by specific ID """
    data = get_grid_by_cell_id(cell_id, db)
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


@router.get("/state/{state}/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_state_centroids(state: str, db: Session = Depends(get_db)):
    """Return centroid click targets for one state."""
    return grid_cells_to_centroids(get_state_grid_cells(state, db))


@router.get("/city", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grid_city(city: str, state: str, db: Session = Depends(get_db)):
    """Return all grid cells generated for a city."""
    return get_city_grid_cells(city, state, db)


@router.get("/city/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_city_centroids(city: str, state: str, db: Session = Depends(get_db)):
    """Return centroid click targets for one generated city grid."""
    return grid_cells_to_centroids(get_city_grid_cells(city, state, db))


@router.get("/state/{state}/geojson")
async def get_all_grid_state_geojson(state: str, db: Session = Depends(get_db)):
    """Function gets all state grids as GeoJSON."""
    data = get_state_grid_cells(state, db)
    return grid_cells_to_geojson(data)


@router.get("/state/{state}/centroids/geojson")
async def get_all_grid_state_centroids_geojson(state: str, db: Session = Depends(get_db)):
    """Return centroid click targets for one state as point GeoJSON."""
    return grid_centroids_to_geojson(get_state_grid_cells(state, db))


@router.get("/city/centroids/geojson")
async def get_all_grid_city_centroids_geojson(city: str, state: str, db: Session = Depends(get_db)):
    """Return centroid click targets for one generated city grid as point GeoJSON."""
    return grid_centroids_to_geojson(get_city_grid_cells(city, state, db))

# Turns the backend end into usable geojson format for frontend
@router.get("/map/geojson")
async def get_grid_map(db: Session = Depends(get_db)):
    cells = get_all_cells(db)

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
    grid = get_grid_by_db_id(id, db)
    if not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO GRID CELLS FOUND"
        )
    return grid
