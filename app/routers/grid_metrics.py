"""File handles the assignment of metrics to each grid cell"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.responses import Response
from database import get_db
from models import grid_cell_tables
from schemas import grid_schemas
from routers.grid_geometry import get_state_grid_cells
from sqlalchemy import func, and_
router = APIRouter(prefix="/grid_metrics", tags=["grid_metrics"])


def add_cell_id(metric):
    """Attach the readable grid cell_id to a metric response."""
    if metric and metric.grid_cell:
        metric.cell_id = metric.grid_cell.cell_id
    return metric


def add_cell_ids(metrics):
    """Attach readable grid cell_id values to metric responses."""
    return [add_cell_id(metric) for metric in metrics]


def latest_metrics_query(db: Session):
    """Query latest metric row for each grid cell."""
    # PostgreSQL supports DISTINCT ON, which lets us pick the newest row per grid cell.
    # SQLite does not support that syntax, so local testing uses the grouped fallback below.
    if db.bind and db.bind.dialect.name == "postgresql":
        return (
            db.query(grid_cell_tables.GridCellMetrics)
            .order_by(
                grid_cell_tables.GridCellMetrics.grid_cell_id,
                grid_cell_tables.GridCellMetrics.timestamp.desc(),
                grid_cell_tables.GridCellMetrics.id.desc(),
            )
            .distinct(grid_cell_tables.GridCellMetrics.grid_cell_id)
        )

    latest = (
        db.query(
            grid_cell_tables.GridCellMetrics.grid_cell_id,
            func.max(grid_cell_tables.GridCellMetrics.timestamp).label("latest_time"),
        )
        .group_by(grid_cell_tables.GridCellMetrics.grid_cell_id)
        .subquery()
    )
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .join(
            latest,
            and_(
                grid_cell_tables.GridCellMetrics.grid_cell_id == latest.c.grid_cell_id,
                grid_cell_tables.GridCellMetrics.timestamp == latest.c.latest_time,
            )
        )
    )


# Create one metric snapshot for a specific grid cell.
@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=grid_schemas.GridCellMetricsResponse)
async def create_grid_metrics(payload:grid_schemas.GridCellMetricsCreate, db:Session=Depends(get_db)):
    """Function creates metrics for a grid cell."""
    grid_cell = db.query(grid_cell_tables.GridCellGeometry).filter(grid_cell_tables.GridCellGeometry.id == payload.grid_cell_id).first()
    if not grid_cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"GRID CELL NOT FOUND")

    metrics = grid_cell_tables.GridCellMetrics(**payload.model_dump())
    db.add(metrics)
    db.commit()
    db.refresh(metrics)
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
    if state:
        grid_cells = get_state_grid_cells(state, db)
    else:
        grid_cells = db.query(grid_cell_tables.GridCellGeometry).all()

    if not grid_cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NO GRID CELLS FOUND")

    grid_cell_ids = [cell.id for cell in grid_cells]
    metric_values = payload.model_dump()

    deleted_count = 0
    if replace_existing:
        deleted_count = (
            db.query(grid_cell_tables.GridCellMetrics)
            .filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids))
            .filter(grid_cell_tables.GridCellMetrics.timestamp == payload.timestamp)
            .delete(synchronize_session=False)
        )

    metrics = [
        grid_cell_tables.GridCellMetrics(
            grid_cell_id=grid_cell_id,
            **metric_values,
        )
        for grid_cell_id in grid_cell_ids
    ]

    db.add_all(metrics)
    db.commit()

    first_metric = metrics[0]
    db.refresh(first_metric)
    add_cell_id(first_metric)

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

# Get every saved metric snapshot across all grid cells.
@router.get("/all", response_model=list[grid_schemas.GridCellMetricsResponse])
async def get_all_metrics(db:Session = Depends(get_db)):
    """Function gets all metris for every single grid"""
    metrics = db.query(grid_cell_tables.GridCellMetrics).all()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return add_cell_ids(metrics)

# Get every metric snapshot for one grid cell database ID.
@router.get("/grid/{grid_cell_id}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def get_metrics_grid_id(grid_cell_id:int, db:Session=Depends(get_db)):
    """Function gets all metrics based on a grid id"""
    metrics = db.query(grid_cell_tables.GridCellMetrics).filter(grid_cell_tables.GridCellMetrics.grid_cell_id == grid_cell_id).all()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return add_cell_ids(metrics)


# Get only the newest metric snapshot for one grid cell database ID.
@router.get("/grid/{grid_cell_id}/latest", response_model=grid_schemas.GridCellMetricsResponse)
async def get_latest_metrics_grid_id(grid_cell_id:int, db:Session=Depends(get_db)):
    """Function gets latest metrics for a grid id"""
    metrics = (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id == grid_cell_id)
        .order_by(grid_cell_tables.GridCellMetrics.timestamp.desc())
        .first()
    )
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return add_cell_id(metrics)


# Get the newest metric snapshot for each grid cell that has metrics.
@router.get("/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def get_latest_metrics(db: Session = Depends(get_db)):
    """Function gets the latest metrics for each grid"""
    metrics = latest_metrics_query(db).all()

    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")

    return add_cell_ids(metrics)


# Get all metric snapshots for every grid cell in a state.
@router.get("/state/{state}", response_model=list[grid_schemas.GridCellMetricsResponse])
async def get_metrics_state_grid(state:str, db:Session=Depends(get_db)):
    """Function finds all metrics related to grids in a specific state"""
    state_cells = get_state_grid_cells(state, db)
    cell_ids = [cell.id for cell in state_cells]

    # Query the databse
    state_grid_metrics = db.query(grid_cell_tables.GridCellMetrics).filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(cell_ids)).all()
    if not state_grid_metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    
    # otherwise return the metrics
    return add_cell_ids(state_grid_metrics)


# Get the newest metric snapshot for each grid cell in a state.
@router.get("/state/{state}/latest", response_model=list[grid_schemas.GridCellMetricsResponse])
async def get_latest_metrics_state_grid(state:str, db:Session=Depends(get_db)):
    """Function finds latest metrics related to grids in a specific state"""
    state_cells = get_state_grid_cells(state, db)
    cell_ids = [cell.id for cell in state_cells]
    metrics = latest_metrics_query(db).filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(cell_ids)).all()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return add_cell_ids(metrics)


# Replace one saved metric snapshot by metric row ID.
@router.put("/update/{id}", response_model=grid_schemas.GridCellMetricsResponse)
async def update_grid_metrics(id:int, payload:grid_schemas.GridCellMetricsCreate, db:Session=Depends(get_db)):
    """Function updates a metric row."""
    metrics = (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.id == id)
        .first()
    )
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    # update the model
    for key, value in payload.model_dump().items():
        setattr(metrics, key, value)
    db.commit()
    db.refresh(metrics)
    return add_cell_id(metrics)


# Delete one saved metric snapshot by metric row ID.
@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grid_metrics(id:int, db:Session=Depends(get_db)):
    """Function deletes a metric row."""
    metrics = (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.id == id)
        .first()
    )
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    db.delete(metrics)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
