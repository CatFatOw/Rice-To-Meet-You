"""Database access helpers for grid metric routes."""
from sqlalchemy import and_, func, text
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


def assign_demo_metrics_to_existing_rows(state: str | None, db: Session):
    """Update existing metric rows with varied demo values.

    This intentionally mutates only rows that already exist in grid_cell_metrics.
    It does not delete grid cells, delete metric rows, or create new metric rows.
    """
    result = db.execute(
        text(
            """
            WITH bounds AS (
                SELECT
                    state,
                    min(row) AS min_row,
                    max(row) AS max_row,
                    min(col) AS min_col,
                    max(col) AS max_col
                FROM grid_cell_geometry
                WHERE (:state IS NULL OR state ILIKE :state)
                GROUP BY state
            ), positioned AS (
                SELECT
                    m.id AS metric_id,
                    g.cell_id,
                    COALESCE((g.row - b.min_row)::float / NULLIF(b.max_row - b.min_row, 0), 0.5) AS y,
                    COALESCE((g.col - b.min_col)::float / NULLIF(b.max_col - b.min_col, 0), 0.5) AS x
                FROM grid_cell_metrics m
                JOIN grid_cell_geometry g ON g.id = m.grid_cell_id
                JOIN bounds b ON b.state = g.state
            ), scored AS (
                SELECT
                    metric_id,
                    LEAST(112, GREATEST(82,
                        88
                        + 10 * (1 - y)
                        + 12 * exp(-(power(x - 0.52, 2) + power(y - 0.48, 2)) / 0.030)
                        + 7 * exp(-(power(x - 0.68, 2) + power(y - 0.58, 2)) / 0.045)
                        + random() * 4
                    )) AS heat_index,
                    LEAST(100, GREATEST(8,
                        28
                        + 42 * exp(-(power(x - 0.52, 2) + power(y - 0.48, 2)) / 0.035)
                        + 18 * (1 - y)
                        + random() * 10
                    )) AS heat_risk,
                    LEAST(100, GREATEST(5,
                        12
                        + 58 * exp(-(power(x - 0.50, 2) + power(y - 0.50, 2)) / 0.040)
                        + 22 * exp(-(power(x - 0.34, 2) + power(y - 0.44, 2)) / 0.030)
                        + random() * 12
                    )) AS crowd_density,
                    ROUND((250 + 5200 * exp(-(power(x - 0.52, 2) + power(y - 0.50, 2)) / 0.050))::numeric, 0) AS population,
                    LEAST(100, GREATEST(12,
                        24
                        + 35 * exp(-(power(x - 0.57, 2) + power(y - 0.52, 2)) / 0.050)
                        + random() * 18
                    )) AS infrastructure_strain
                FROM positioned
            ), final_scores AS (
                SELECT
                    *,
                    CASE
                        WHEN heat_risk >= 80 THEN '#DC2626'
                        WHEN heat_risk >= 60 THEN '#F97316'
                        WHEN heat_risk >= 40 THEN '#FACC15'
                        ELSE '#22C55E'
                    END AS risk_color
                FROM scored
            )
            UPDATE grid_cell_metrics m
            SET
                heat_index = ROUND(s.heat_index::numeric, 1),
                heat_risk = ROUND(s.heat_risk::numeric, 1),
                crowd_density = ROUND(s.crowd_density::numeric, 1),
                population = s.population,
                cooling_centers = CASE WHEN s.heat_risk >= 75 THEN 1 ELSE 0 END,
                cooling_centers_impact_radius = CASE WHEN s.heat_risk >= 75 THEN 0.75 ELSE 0 END,
                infrastructure_strain = ROUND(s.infrastructure_strain::numeric, 1),
                heat_index_color = s.risk_color,
                heat_risk_color = s.risk_color,
                crowd_density_color = s.risk_color,
                population_color = s.risk_color,
                cooling_centers_color = CASE WHEN s.heat_risk >= 75 THEN '#2563EB' ELSE '#94A3B8' END,
                infrastructure_strain_color = s.risk_color,
                overall_risk_color = s.risk_color
            FROM final_scores s
            WHERE m.id = s.metric_id
            """
        ),
        {"state": state},
    )
    db.commit()
    return result.rowcount


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
                predicted_heat_index=latest.predicted_heat_index,
                predicted_heat_risk=latest.predicted_heat_risk,
                predicted_crowd_density=latest.predicted_crowd_density,
                predicted_population=latest.predicted_population,
                predicted_visitor_count=latest.predicted_visitor_count,
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
