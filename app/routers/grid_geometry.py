"""HTTP endpoints for generated grid cells."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import grid_schemas
from services.grid_geometry_services import (
    all_grid_centroids,
    all_grid_centroids_geojson,
    generate_city_grid,
    generate_state_grid,
    get_all_grid_cells,
    get_city_grid_cells,
    get_grid_cell_by_cell_id,
    get_grid_cell_by_db_id,
    get_state_grid_cells,
    grid_cells_centroids_geojson,
    grid_cells_to_centroids,
    grid_cells_to_geojson,
)

router = APIRouter(prefix="/grid", tags=["grid"])


@router.post("/generate_nxn_grid_city")
async def generate_nxn_grid_city(city: str, state: str, n: int = 40, db: Session = Depends(get_db)):
    return generate_city_grid(city, state, n, db)


@router.post("/generate_nxn_grid")
async def generate_nxn_grid(state_name: str, n: int = 40, db: Session = Depends(get_db)):
    return generate_state_grid(state_name, n, db)


@router.get("/all", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grids(db: Session = Depends(get_db)):
    return get_all_grid_cells(db)


@router.get("/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_centroids(db: Session = Depends(get_db)):
    return all_grid_centroids(db)


@router.get("/centroids/geojson")
async def get_all_grid_centroids_geojson(db: Session = Depends(get_db)):
    return all_grid_centroids_geojson(db)


@router.get("/cell/{cell_id}", response_model=grid_schemas.GridCellResponse)
async def get_grid_cell_by_cell_id_route(cell_id: str, db: Session = Depends(get_db)):
    return get_grid_cell_by_cell_id(cell_id, db)


@router.get("/state/{state}", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grid_state(state: str, db: Session = Depends(get_db)):
    return get_state_grid_cells(state, db)


@router.get("/state/{state}/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_state_centroids(state: str, db: Session = Depends(get_db)):
    return grid_cells_to_centroids(get_state_grid_cells(state, db))


@router.get("/city", response_model=list[grid_schemas.GridCellResponse])
async def get_all_grid_city(city: str, state: str, db: Session = Depends(get_db)):
    return get_city_grid_cells(city, state, db)


@router.get("/city/centroids", response_model=list[grid_schemas.GridCentroidResponse])
async def get_all_grid_city_centroids(city: str, state: str, db: Session = Depends(get_db)):
    return grid_cells_to_centroids(get_city_grid_cells(city, state, db))


@router.get("/state/{state}/geojson")
async def get_all_grid_state_geojson(state: str, db: Session = Depends(get_db)):
    return grid_cells_to_geojson(get_state_grid_cells(state, db))


@router.get("/state/{state}/centroids/geojson")
async def get_all_grid_state_centroids_geojson(state: str, db: Session = Depends(get_db)):
    return grid_cells_centroids_geojson(get_state_grid_cells(state, db))


@router.get("/city/centroids/geojson")
async def get_all_grid_city_centroids_geojson(city: str, state: str, db: Session = Depends(get_db)):
    return grid_cells_centroids_geojson(get_city_grid_cells(city, state, db))


@router.get("/map/geojson")
async def get_grid_map(db: Session = Depends(get_db)):
    return grid_cells_to_geojson(get_all_grid_cells(db))


@router.get("/id/{grid_id}", response_model=grid_schemas.GridCellResponse)
async def get_grid_id(grid_id: int, db: Session = Depends(get_db)):
    return get_grid_cell_by_db_id(grid_id, db)
