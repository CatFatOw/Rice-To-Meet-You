"""HTTP endpoints for grid-cell metric snapshots."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from schemas import grid_schemas
from services.grid_metrics_services import (
    assign_demo_metrics,
    assign_metrics_to_all,
    create_metric,
    read_all_metrics,
    read_latest_metric_for_grid,
    read_latest_metrics,
    read_metrics_for_grid,
    read_metrics_for_state,
    remove_metric,
    replace_metric,
)

router = APIRouter(prefix="/grid_metrics", tags=["grid_metrics"])


@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=grid_schemas.GridCellMetricsResponse)
async def create_grid_metrics(payload: grid_schemas.GridCellMetricsCreate, db: Session = Depends(get_db)):
    return create_metric(payload, db)


@router.post("/assign_all", status_code=status.HTTP_201_CREATED)
async def assign_metrics_all_grids(payload: grid_schemas.GridCellMetricsAssignAll, state: str | None = None, replace_existing: bool = True, db: Session = Depends(get_db)):
    return assign_metrics_to_all(payload, state, replace_existing, db)


@router.post("/assign_demo")
async def assign_demo_metrics_route(state: str | None = None, db: Session = Depends(get_db)):
    return assign_demo_metrics(state, db)


@router.get("/all", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_all_metrics_route(db: Session = Depends(get_db)):
    return read_all_metrics(db)


@router.get("/grid/{grid_cell_id}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_metrics_grid_id(grid_cell_id: int, db: Session = Depends(get_db)):
    return read_metrics_for_grid(grid_cell_id, db)


@router.get("/grid/{grid_cell_id}/latest", response_model=grid_schemas.GridCellMetricsResponse)
async def read_latest_metrics_grid_id(grid_cell_id: int, db: Session = Depends(get_db)):
    return read_latest_metric_for_grid(grid_cell_id, db)


@router.get("/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_latest_metrics_route(db: Session = Depends(get_db)):
    return read_latest_metrics(db)


@router.get("/state/{state}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_metrics_state_grid(state: str, db: Session = Depends(get_db)):
    return read_metrics_for_state(state, False, db)


@router.get("/state/{state}/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_latest_metrics_state_grid(state: str, db: Session = Depends(get_db)):
    return read_metrics_for_state(state, True, db)


@router.put("/update/{metric_id}", response_model=grid_schemas.GridCellMetricsResponse)
async def update_grid_metrics(metric_id: int, payload: grid_schemas.GridCellMetricsCreate, db: Session = Depends(get_db)):
    return replace_metric(metric_id, payload, db)


@router.delete("/delete/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grid_metrics(metric_id: int, db: Session = Depends(get_db)):
    remove_metric(metric_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
