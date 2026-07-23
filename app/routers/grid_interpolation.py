"""HTTP endpoints for persisted metric interpolation."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from schemas import interpolate_schemas
from services.grid_interpolation_service import (
    city_grid_cells_geojson,
    read_all_interpolated_points,
    read_interpolated_heatmap,
    read_interpolated_mesh,
    remove_interpolated_point,
    replace_interpolated_point,
    run_interpolation,
)

router = APIRouter(prefix="/grid_interpolation", tags=["grid_interpolation"])


@router.get("/grid_cells_city")
async def get_grid_cells_city(city: str, state: str, db: Session = Depends(get_db)):
    return city_grid_cells_geojson(city, state, db)


@router.post("/interpolate", response_model=list[interpolate_schemas.InterpolatedPointResponse])
async def interpolate(payload: interpolate_schemas.InterpolationRunRequest, db: Session = Depends(get_db)):
    return run_interpolation(payload, db)


@router.get("/all")
async def get_all(db: Session = Depends(get_db)):
    return read_all_interpolated_points(db)


@router.get("/mesh")
async def get_interpolated_mesh(city: str | None = None, state: str | None = None, timestamp: datetime | None = None, color_metric: str = "heat_index", db: Session = Depends(get_db)):
    return read_interpolated_mesh(city, state, timestamp, color_metric, db)


@router.get("/heatmap")
async def get_interpolated_heatmap(city: str | None = None, state: str | None = None, timestamp: datetime | None = None, metric_key: str = "heat_index", db: Session = Depends(get_db)):
    return read_interpolated_heatmap(city, state, timestamp, metric_key, db)


@router.put("/update/{interpolated_id}", response_model=interpolate_schemas.InterpolatedPointResponse)
async def update_cell(interpolated_id: int, payload: interpolate_schemas.InterpolatedPointUpdate, db: Session = Depends(get_db)):
    return replace_interpolated_point(interpolated_id, payload, db)


@router.delete("/delete/{interpolated_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell_id(interpolated_id: int, db: Session = Depends(get_db)):
    remove_interpolated_point(interpolated_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
