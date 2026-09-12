"""Routes for assigning and reading metrics for grid cells."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from repository.grid_metrics_repository import (
    assign_demo_metrics_to_existing_rows,
    create_grid_metric,
    create_metrics_for_grid_cells,
    delete_metric,
    delete_metrics_for_cells_at_timestamp,
    get_all_grid_cells,
    get_all_metrics,
    get_grid_cell_by_id,
    get_latest_metric_by_grid_id,
    get_latest_metrics_for_grid_ids,
    get_metric_by_id,
    get_metrics_by_grid_id,
    get_metrics_for_grid_ids,
    latest_metrics_query,
    update_metric,
)
from routers.grid_geometry import get_state_grid_cells
from schemas import grid_schemas
from services.grid_metrics_services import add_cell_id, add_cell_ids

router = APIRouter(prefix="/grid_metrics", tags=["grid_metrics"])


def grid_ids_from_cells(cells):
    """Return DB IDs from grid cell rows."""
    return [cell.id for cell in cells]


# Create one metric snapshot for a specific grid cell.
@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=grid_schemas.GridCellMetricsResponse,
)
async def create_grid_metrics(
    payload: grid_schemas.GridCellMetricsCreate,
    db: Session = Depends(get_db),
):
    """Create metrics for one grid cell."""
    grid_cell = get_grid_cell_by_id(payload.grid_cell_id, db)
    if not grid_cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRID CELL NOT FOUND")

    metrics = create_grid_metric(payload, db)
    return add_cell_id(metrics)


# Create one metric snapshot for every current grid cell.
@router.post("/assign_all", status_code=status.HTTP_201_CREATED)
async def assign_metrics_all_grids(
    payload: grid_schemas.GridCellMetricsAssignAll,
    state: str | None = None,
    replace_existing: bool = True,
    db: Session = Depends(get_db),
):
    """Assign the same metric snapshot to every grid cell, optionally within one state."""
    grid_cells = get_state_grid_cells(state, db) if state else get_all_grid_cells(db)

    if not grid_cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NO GRID CELLS FOUND")

    grid_cell_ids = grid_ids_from_cells(grid_cells)
    metric_values = payload.model_dump()

    deleted_count = 0
    if replace_existing:
        deleted_count = delete_metrics_for_cells_at_timestamp(
            grid_cell_ids,
            payload.timestamp,
            db,
        )

    metrics = create_metrics_for_grid_cells(grid_cell_ids, metric_values, db)
    first_metric = add_cell_id(metrics[0])

    return {
        "message": "Metrics assigned successfully",
        "state": state,
        "replace_existing": replace_existing,
        "metrics_deleted": deleted_count,
        "metrics_created": len(metrics),
        "first_metric_id": first_metric.id,
        "first_grid_cell_id": first_metric.grid_cell_id,
        "first_grid_cell_cell_id": first_metric.cell_id,
    }


# Update existing metric rows with varied demo values for heatmap previews.
@router.post("/assign_demo", status_code=status.HTTP_200_OK)
async def assign_demo_metrics(
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Randomize existing grid metric rows into realistic demo ranges."""
    updated_count = assign_demo_metrics_to_existing_rows(state, db)
    if not updated_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO EXISTING METRIC ROWS FOUND. Run /grid_metrics/assign_all first.",
        )

    return {
        "message": "Demo metrics assigned successfully",
        "state": state,
        "metrics_updated": updated_count,
        "note": "Existing grid_cell_metrics rows were updated in place; no grid cells or metric rows were deleted.",
    }


# Get every saved metric snapshot across all grid cells.
@router.get("/all", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_all_metrics(db: Session = Depends(get_db)):
    """Get all metric snapshots."""
    metrics = get_all_metrics(db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return add_cell_ids(metrics)


# Get every metric snapshot for one grid cell database ID.
@router.get("/grid/{grid_cell_id}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_metrics_grid_id(grid_cell_id: int, db: Session = Depends(get_db)):
    """Get all metrics for one grid cell."""
    metrics = get_metrics_by_grid_id(grid_cell_id, db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return add_cell_ids(metrics)


# Get only the newest metric snapshot for one grid cell database ID.
@router.get("/grid/{grid_cell_id}/latest", response_model=grid_schemas.GridCellMetricsResponse)
async def read_latest_metrics_grid_id(grid_cell_id: int, db: Session = Depends(get_db)):
    """Get latest metrics for one grid cell."""
    metrics = get_latest_metric_by_grid_id(grid_cell_id, db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return add_cell_id(metrics)


# Get the newest metric snapshot for each grid cell that has metrics.
@router.get("/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_latest_metrics(db: Session = Depends(get_db)):
    """Get the latest metrics for each grid cell."""
    metrics = latest_metrics_query(db).all()

    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return add_cell_ids(metrics)


# Get all metric snapshots for every grid cell in a state.
@router.get("/state/{state}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_metrics_state_grid(state: str, db: Session = Depends(get_db)):
    """Get all metrics related to grids in one state."""
    state_cells = get_state_grid_cells(state, db)
    metrics = get_metrics_for_grid_ids(grid_ids_from_cells(state_cells), db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return add_cell_ids(metrics)


# Get the newest metric snapshot for each grid cell in a state.
@router.get("/state/{state}/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def read_latest_metrics_state_grid(state: str, db: Session = Depends(get_db)):
    """Get latest metrics related to grids in one state."""
    state_cells = get_state_grid_cells(state, db)
    metrics = get_latest_metrics_for_grid_ids(grid_ids_from_cells(state_cells), db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return add_cell_ids(metrics)


# Replace one saved metric snapshot by metric row ID.
@router.put("/update/{id}", response_model=grid_schemas.GridCellMetricsResponse)
async def update_grid_metrics(
    id: int,
    payload: grid_schemas.GridCellMetricsCreate,
    db: Session = Depends(get_db),
):
    """Update a metric row."""
    metrics = get_metric_by_id(id, db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return add_cell_id(update_metric(metrics, payload, db))


# Delete one saved metric snapshot by metric row ID.
@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grid_metrics(id: int, db: Session = Depends(get_db)):
    """Delete a metric row."""
    metrics = get_metric_by_id(id, db)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    delete_metric(metrics, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
