"""Database access helpers for grid metric routes."""
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from models import grid_cell_tables


def latest_metrics_query(db: Session):
    """Query latest metric row for each grid cell."""
    # PostgreSQL supports DISTINCT ON, which lets us pick the newest row per grid cell.
    # SQLite does not support that syntax, so local testing uses the grouped fallback below.
    if db.bind and db.bind.dialect.name == "postgresql":
        return (
            db.query(grid_cell_tables.GridCellMetrics)
            .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
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
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .join(
            latest,
            and_(
                grid_cell_tables.GridCellMetrics.grid_cell_id == latest.c.grid_cell_id,
                grid_cell_tables.GridCellMetrics.timestamp == latest.c.latest_time,
            ),
        )
    )


def get_all_grid_cells(db: Session):
    """Get every grid cell."""
    return db.query(grid_cell_tables.GridCellGeometry).all()


def get_grid_cell_by_id(grid_cell_id: int, db: Session):
    """Get one grid cell by primary key."""
    return (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.id == grid_cell_id)
        .first()
    )


def create_grid_metric(payload, db: Session):
    """Create one metric snapshot."""
    metrics = grid_cell_tables.GridCellMetrics(**payload.model_dump())
    db.add(metrics)
    db.commit()
    db.refresh(metrics)
    return metrics


def delete_metrics_for_cells_at_timestamp(grid_cell_ids, timestamp, db: Session):
    """Delete metric snapshots for grid cells at one timestamp."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids))
        .filter(grid_cell_tables.GridCellMetrics.timestamp == timestamp)
        .delete(synchronize_session=False)
    )


def create_metrics_for_grid_cells(grid_cell_ids, metric_values, db: Session):
    """Create the same metric snapshot for many grid cells."""
    metrics = [
        grid_cell_tables.GridCellMetrics(
            grid_cell_id=grid_cell_id,
            **metric_values,
        )
        for grid_cell_id in grid_cell_ids
    ]

    db.add_all(metrics)
    db.commit()

    if metrics:
        db.refresh(metrics[0])

    return metrics


def get_all_metrics(db: Session):
    """Get every saved metric snapshot."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .all()
    )


def get_metrics_by_grid_id(grid_cell_id: int, db: Session):
    """Get all metric snapshots for one grid cell."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id == grid_cell_id)
        .all()
    )


def get_latest_metric_by_grid_id(grid_cell_id: int, db: Session):
    """Get the latest metric snapshot for one grid cell."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id == grid_cell_id)
        .order_by(grid_cell_tables.GridCellMetrics.timestamp.desc())
        .first()
    )


def get_metrics_for_grid_ids(grid_cell_ids, db: Session):
    """Get all metric snapshots for a set of grid cell IDs."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids))
        .all()
    )


def get_latest_metrics_for_grid_ids(grid_cell_ids, db: Session):
    """Get the latest metric snapshots for a set of grid cell IDs."""
    return latest_metrics_query(db).filter(
        grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids)
    ).all()


def get_metric_by_id(id: int, db: Session):
    """Get one metric row by primary key."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .options(joinedload(grid_cell_tables.GridCellMetrics.grid_cell))
        .filter(grid_cell_tables.GridCellMetrics.id == id)
        .first()
    )


def update_metric(metric, payload, db: Session):
    """Replace a metric row's values."""
    for key, value in payload.model_dump().items():
        setattr(metric, key, value)

    db.commit()
    db.refresh(metric)
    return metric


def delete_metric(metric, db: Session):
    """Delete one metric row."""
    db.delete(metric)
    db.commit()
    return True
