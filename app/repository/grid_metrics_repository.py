"""Database access helpers for grid metric routes."""
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from models import grid_cell_tables
from repository.grid_geometry_repository import get_all_city_grid_cells, get_all_state_grid_cells


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


def clamp_metric(value, minimum=0, maximum=100):
    """Clamp derived simulation scores to the frontend's 0-100 range."""
    if value is None:
        return None
    return max(minimum, min(maximum, value))


def create_simulated_metrics_from_latest(latest_metrics, timestamp: datetime, adjustments: dict, db: Session):
    """Create adjusted metric snapshots from latest rows.

    Simulation apply is intentionally append-only: it preserves the original
    metric rows and writes a new timestamped snapshot for the impacted grid
    cells, so users can compare before/after states.
    """
    metrics = []

    for latest in latest_metrics:
        heat_index = clamp_metric(
            (latest.heat_index if latest.heat_index is not None else latest.heat_risk) + adjustments["heat_index_delta"]
            if latest.heat_index is not None or latest.heat_risk is not None
            else None
        )
        heat_risk = clamp_metric(
            (latest.heat_risk if latest.heat_risk is not None else latest.heat_index) + adjustments["heat_risk_delta"]
            if latest.heat_risk is not None or latest.heat_index is not None
            else None
        )
        infrastructure_strain = clamp_metric(
            latest.infrastructure_strain + adjustments["infrastructure_strain_delta"]
            if latest.infrastructure_strain is not None
            else None
        )

        metrics.append(
            grid_cell_tables.GridCellMetrics(
                grid_cell_id=latest.grid_cell_id,
                timestamp=timestamp,
                heat_index=heat_index,
                heat_risk=heat_risk,
                crowd_density=latest.crowd_density,
                population=latest.population,
                cooling_centers=(latest.cooling_centers or 0) + adjustments["cooling_centers_delta"],
                cooling_centers_impact_radius=latest.cooling_centers_impact_radius,
                infrastructure_strain=infrastructure_strain,
                heat_index_color=latest.heat_index_color,
                heat_risk_color=latest.heat_risk_color,
                crowd_density_color=latest.crowd_density_color,
                population_color=latest.population_color,
                cooling_centers_color=latest.cooling_centers_color,
                infrastructure_strain_color=latest.infrastructure_strain_color,
                overall_risk_color=latest.overall_risk_color,
            )
        )

    if metrics:
        db.add_all(metrics)
        db.commit()
        for metric in metrics:
            db.refresh(metric)

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


def get_latest_metrics_for_city(city: str | None, state: str | None, db: Session):
    """Get latest grid metrics scoped to a city/state view.

    The frontend statistics panel asks for either a named city or the national
    view. City filtering follows the grid generation convention, where city and
    state are encoded in the readable grid cell id. For the national view we can
    still scope to a state when supplied, which keeps the default Texas demo fast
    and consistent with the rest of the heatmap routes.
    """
    query = latest_metrics_query(db)
    normalized_city = city.strip().lower() if city else None

    if normalized_city and normalized_city != "nationally":
        if not state:
            return []
        grid_cells = get_all_city_grid_cells(state, city, db)
        grid_cell_ids = [cell.id for cell in grid_cells]
        if not grid_cell_ids:
            return []
        return query.filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids)).all()

    if state:
        grid_cells = get_all_state_grid_cells(state, db)
        grid_cell_ids = [cell.id for cell in grid_cells]
        if not grid_cell_ids:
            return []
        return query.filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids)).all()

    return query.all()


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
