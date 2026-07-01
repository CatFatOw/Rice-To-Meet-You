"""Database access helpers for grid interpolation routes."""
from sqlalchemy.orm import Session, joinedload

from models import grid_cell_tables
from repository.grid_geometry_repository import get_all_city_grid_cells


def get_all_points(db: Session):
    """Get every saved interpolated point."""
    return db.query(grid_cell_tables.InterpolatedPoint).all()


def get_interpolated_point_by_id(interpolated_id: int, db: Session):
    """Get one interpolated point by primary key."""
    return (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.id == interpolated_id)
        .first()
    )


def get_interpolated_points_query(db: Session, city=None, state=None, timestamp=None):
    """Build a filtered interpolated-points query."""
    query = (
        db.query(grid_cell_tables.InterpolatedPoint)
        .options(joinedload(grid_cell_tables.InterpolatedPoint.grid_cell))
    )

    if city and state:
        grid_cells = get_all_city_grid_cells(state, city, db)
        grid_cell_ids = [cell.id for cell in grid_cells]
        query = query.filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(grid_cell_ids))

    if timestamp:
        query = query.filter(grid_cell_tables.InterpolatedPoint.timestamp == timestamp)

    return query


def get_metrics_for_grid_cells(grid_cell_ids, timestamp, db: Session):
    """Get metric rows for grid cells at a timestamp."""
    return (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids))
        .filter(grid_cell_tables.GridCellMetrics.timestamp == timestamp)
        .all()
    )


def delete_interpolated_points_for_cells(grid_cell_ids, timestamp, db: Session):
    """Delete interpolated points for grid cells at a timestamp."""
    return (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(grid_cell_ids))
        .filter(grid_cell_tables.InterpolatedPoint.timestamp == timestamp)
        .delete(synchronize_session=False)
    )


def create_interpolated_points(results, timestamp, source_count, metric_keys, db: Session):
    """Create interpolated point rows from interpolation result dictionaries."""
    interpolated_points = []

    for result in results:
        point = grid_cell_tables.InterpolatedPoint(
            grid_cell_id=result["grid_cell_id"],
            timestamp=timestamp,
            latitude=result["latitude"],
            longitude=result["longitude"],
            interpolation_method="kriging",
            source_count=source_count,
            confidence=result["confidence"],
        )
        for metric_key in metric_keys:
            setattr(point, metric_key, result[metric_key])
        interpolated_points.append(point)

    db.add_all(interpolated_points)
    db.commit()
    return interpolated_points


def get_interpolated_points_for_cells(grid_cell_ids, timestamp, db: Session):
    """Get saved interpolated points for grid cells at a timestamp."""
    return (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(grid_cell_ids))
        .filter(grid_cell_tables.InterpolatedPoint.timestamp == timestamp)
        .all()
    )


def update_interpolated_point(point, payload, db: Session):
    """Update an interpolated point row from a Pydantic payload."""
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(point, key, value)

    db.commit()
    db.refresh(point)
    return point


def delete_interpolated_point(point, db: Session):
    """Delete one interpolated point row."""
    db.delete(point)
    db.commit()
    return True
